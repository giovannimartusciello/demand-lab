"""Dependency-free, deterministic demand forecasting and inventory calculations.

The functions accept ordinary Python sequences and return serializable objects.
No interface library or future observation is available to the forecast functions.
"""
from dataclasses import dataclass
from math import cos, pi, isfinite
from random import Random
from statistics import mean, stdev, NormalDist

METHODS = ("moving_average", "linear_trend", "seasonal_naive")

@dataclass(frozen=True)
class Scenario:
    noise: float = 1.0
    trend: float = 0.0
    seasonality: float = 0.0
    lead_time: int = 2
    order_quantity: int = 300
    service_level: float = 0.95
    capacity_factor: float = 1.15

    def __post_init__(self):
        if not isfinite(self.noise) or not 0 <= self.noise <= 3:
            raise ValueError("Noise multiplier must be between zero and three.")
        if not isfinite(self.trend) or not -1 <= self.trend <= 2:
            raise ValueError("Additional monthly trend must be between minus one and two percent.")
        if not isfinite(self.seasonality) or not 0 <= self.seasonality <= 80:
            raise ValueError("Additional seasonal amplitude must be between zero and eighty points.")
        if not isinstance(self.lead_time, int) or not 1 <= self.lead_time <= 6:
            raise ValueError("Lead time must be an integer between one and six months.")
        if self.order_quantity <= 0 or not 0.5 < self.service_level < 1:
            raise ValueError("Invalid order quantity or service level.")
        if not 1 <= self.capacity_factor <= 2:
            raise ValueError("Capacity factor must be between one and two.")


def generate_demand(item, scenario=Scenario(), periods=60):
    """Generate monthly counterfactual demand with common random numbers.

    All series begin in January 2021. Rounding and clipping at zero occur after
    level, linear trend, multiplicative annual seasonality and additive noise.
    """
    rng = Random(item["seed"])
    values = []
    for t in range(periods):
        level = max(0.0, item["base"] + (item["slope"] + item["base"]*scenario.trend/100) * t)
        seasonal = max(0.05, 1 + min(0.95, item["amplitude"] + scenario.seasonality/100) * cos(2*pi*(t % 12 - item["peak_month"])/12))
        shock = rng.gauss(0, item["noise_sd"]) * scenario.noise
        values.append(max(0, int(round(level * seasonal + shock))))
    return values


def linear_fit(values):
    """Return intercept and slope from ordinary least squares on t = 0..n-1."""
    n = len(values)
    center = (n-1)/2
    denominator = sum((t-center)**2 for t in range(n))
    slope = sum((t-center)*(v-mean(values)) for t, v in enumerate(values)) / denominator if denominator else 0.0
    return mean(values)-slope*center, slope


def forecast(values, method, horizon=12):
    """Fit fixed-parameter candidate models and forecast without future data.

    Moving average uses the latest three observations and a flat multi-step
    forecast. Linear regression extrapolates a fitted time trend, while the
    seasonal naive method repeats the last observed twelve-month pattern.
    """
    values = list(values)
    if not values or any(not isfinite(v) or v < 0 for v in values):
        raise ValueError("Demand must contain finite nonnegative observations.")
    if horizon < 1 or int(horizon) != horizon:
        raise ValueError("Forecast horizon must be a positive integer.")
    n = len(values)
    if method == "moving_average":
        result = [mean(values[-3:])] * horizon
    elif method == "linear_trend":
        intercept, slope = linear_fit(values)
        result = [intercept + slope*t for t in range(n, n+horizon)]
    elif method == "seasonal_naive":
        if n < 12:
            raise ValueError("Seasonal naive requires twelve monthly observations.")
        result = [values[n-12+(h % 12)] for h in range(horizon)]
    else:
        raise ValueError(f"Unknown forecasting method: {method}")
    return [max(0.0, float(v)) for v in result]


def error_metrics(actual, predicted):
    if not actual or len(actual) != len(predicted):
        raise ValueError("Actual and predicted values must have equal nonzero length.")
    errors = [a-p for a,p in zip(actual, predicted)]
    return {"mae": mean(abs(e) for e in errors)}


def rolling_predictions(values, method, start, stop):
    """Refit at each origin, then predict only the next unseen observation."""
    return [forecast(values[:origin],method,1)[0] for origin in range(start,stop)]


def evaluate_methods(values):
    """Select on 2024 (months 37..48), audit on unseen 2025 (months 49..60).

    Selection uses MAE, then the stable candidate order for ties. Each test
    prediction may use previous test observations, as in monthly operations;
    method identity and hyperparameters are frozen before the test starts.
    """
    if len(values) != 60:
        raise ValueError("The experiment requires exactly sixty monthly observations.")
    results = []
    for method in METHODS:
        validation_predictions = rolling_predictions(values,method,36,48)
        test_predictions = rolling_predictions(values,method,48,60)
        validation = error_metrics(values[36:48],validation_predictions)
        test = error_metrics(values[48:60],test_predictions)
        results.append({"method":method,"validation":validation,"test":test,
                        "test_predictions":test_predictions})
    selected = min(results,key=lambda row:(row["validation"]["mae"],METHODS.index(row["method"])))
    return {"selected":selected["method"],"results":results}


def lead_time_errors(values, method, lead_time):
    """Aggregate rolling forecast errors with targets confined to validation.

    Overlapping windows are allowed and are not statistically independent.
    The test observations are never used to calibrate safety stock.
    """
    return [sum(values[o:o+lead_time])-sum(forecast(values[:o],method,lead_time))
            for o in range(36,49-lead_time)]


def anticipation_plan(predicted, capacity):
    """Backward finite-horizon material balance with zero terminal buffer.

    buffer[t] is the minimum stock needed before month t, assuming receipts up
    to capacity can arrive before demand. It must already exist at time zero.
    This plan excludes cycle stock, safety stock and stochastic stockouts.
    """
    if capacity < 0 or not predicted:
        raise ValueError("Capacity must be nonnegative and demand nonempty.")
    buffers = [0.0]*(len(predicted)+1)
    for t in range(len(predicted)-1,-1,-1):
        buffers[t] = max(0.0,buffers[t+1]+predicted[t]-capacity)
    receipts = [predicted[t]+buffers[t+1]-buffers[t] for t in range(len(predicted))]
    return {"buffers":buffers,"receipts":receipts,
            "average":mean((buffers[t]+buffers[t+1])/2 for t in range(len(predicted))),
            "peak":max(buffers),"initial":buffers[0],"capacity":capacity}


def inventory_estimates(values, method, scenario, capacity=None):
    predicted = forecast(values,method,12)
    errors = lead_time_errors(values,method,scenario.lead_time)
    sigma = stdev(errors)
    safety = NormalDist().inv_cdf(scenario.service_level)*sigma
    pipeline = sum(predicted[:scenario.lead_time])
    capacity = capacity if capacity is not None else mean(predicted)*scenario.capacity_factor
    anticipation = anticipation_plan(predicted,capacity)
    return {"cycle":scenario.order_quantity/2,"safety":safety,"pipeline":pipeline,
            "reorder_point":pipeline+safety,"sigma_lead":sigma,
            "calibration_windows":len(errors),"anticipation":anticipation,"forecast":predicted}


def run_analysis(item,scenario=Scenario(),capacity=None):
    values = generate_demand(item,scenario)
    evaluation = evaluate_methods(values)
    inventory = inventory_estimates(values,evaluation["selected"],scenario,capacity)
    return {"demand":values,"evaluation":evaluation,"inventory":inventory}
