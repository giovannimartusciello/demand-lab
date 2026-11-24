"""Scientific invariants and regression checks for forecasting and inventory."""
import csv
import json
import unittest
from unittest.mock import patch
from pathlib import Path
from models import (Scenario, forecast, error_metrics, generate_demand,
                    evaluate_methods, lead_time_errors, anticipation_plan, run_analysis)

ROOT=Path(__file__).resolve().parents[1]
CATALOG=json.loads((ROOT/"data/catalog.json").read_text())

class ForecastTests(unittest.TestCase):
    def test_exact_linear_extrapolation(self):
        values=[10+3*t for t in range(36)]
        self.assertEqual(forecast(values,"linear_trend",3),[118.0,121.0,124.0])

    def test_constant_series_all_methods(self):
        for method in ("moving_average","linear_trend","seasonal_naive"):
            for value in forecast([100]*36,method,12):
                self.assertAlmostEqual(value,100)

    def test_known_moving_average(self):
        self.assertEqual(forecast([10,20,30,40],"moving_average",2),[30,30])

    def test_seasonal_reference_repeats_calendar_months(self):
        self.assertEqual(forecast(list(range(1,25)),"seasonal_naive",14),list(range(13,25))+[13,14])

    def test_error_metrics_known_example(self):
        metrics=error_metrics([10,20],[8,24])
        self.assertEqual(metrics,{"mae":3})

    def test_equal_mae_uses_candidate_order_despite_different_error_spreads(self):
        errors={"moving_average":[0]*6+[2]*6,"linear_trend":[1]*12,"seasonal_naive":[3]*12}
        def predictions(values,method,start,stop):
            return [10-error for error in errors[method]]
        with patch("models.rolling_predictions",side_effect=predictions):
            evaluation=evaluate_methods([10]*60)
        self.assertEqual(evaluation["selected"],"moving_average")
        for row in evaluation["results"][:2]:
            self.assertEqual(row["validation"],{"mae":1})

    def test_future_test_values_cannot_change_selection_or_calibration(self):
        values=generate_demand(CATALOG[2])
        changed=values[:48]+[99999]*12
        first=evaluate_methods(values)
        second=evaluate_methods(changed)
        self.assertEqual(first["selected"],second["selected"])
        for lead in range(1,7):
            self.assertEqual(lead_time_errors(values,first["selected"],lead),lead_time_errors(changed,first["selected"],lead))
        for row1,row2 in zip(first["results"],second["results"]):
            self.assertEqual(row1["validation"],row2["validation"])

    def test_published_dataset_is_reproducible(self):
        with (ROOT/"data/demand.csv").open() as handle:
            rows=list(csv.DictReader(handle))
        self.assertEqual(len(rows),240)
        for item in CATALOG:
            self.assertEqual([int(r["demand"]) for r in rows if r["item_id"]==item["id"]],generate_demand(item))

    def test_noise_zero_removes_variation_for_stationary_item(self):
        self.assertEqual(set(generate_demand(CATALOG[0],Scenario(noise=0))),{500})

    def test_additional_trend_and_seasonality_affect_stationary_item(self):
        initial=generate_demand(CATALOG[0],Scenario(noise=0))
        self.assertGreater(generate_demand(CATALOG[0],Scenario(noise=0,trend=1))[-1],initial[-1])
        self.assertGreater(max(generate_demand(CATALOG[0],Scenario(noise=0,seasonality=60))),max(initial))

class InventoryTests(unittest.TestCase):
    def test_anticipation_satisfies_capacity_and_material_balance(self):
        demand=[40,40,160,160]
        plan=anticipation_plan(demand,100)
        self.assertEqual(plan["buffers"],[0,60,120,60,0])
        for t,receipt in enumerate(plan["receipts"]):
            self.assertGreaterEqual(receipt,-1e-8)
            self.assertLessEqual(receipt,100+1e-8)
            self.assertAlmostEqual(plan["buffers"][t]+receipt-demand[t],plan["buffers"][t+1])

    def test_high_capacity_eliminates_anticipation(self):
        self.assertEqual(anticipation_plan([10,20,30],30)["peak"],0)

    def test_initial_buffer_is_reported(self):
        self.assertEqual(anticipation_plan([200,100],100)["initial"],100)

    def test_lead_time_changes_inventory_without_changing_forecast(self):
        first=run_analysis(CATALOG[0],Scenario())
        second=run_analysis(CATALOG[0],Scenario(lead_time=5))
        self.assertEqual(first["inventory"]["forecast"],second["inventory"]["forecast"])
        self.assertGreater(second["inventory"]["pipeline"],first["inventory"]["pipeline"])

    def test_service_and_order_quantity_effects(self):
        first=run_analysis(CATALOG[1],Scenario())
        second=run_analysis(CATALOG[1],Scenario(service_level=.99,order_quantity=600))
        self.assertGreater(second["inventory"]["safety"],first["inventory"]["safety"])
        self.assertEqual(second["inventory"]["cycle"],2*first["inventory"]["cycle"])
        self.assertEqual(second["inventory"]["forecast"],first["inventory"]["forecast"])

    def test_parameter_boundaries_remain_finite_and_nonnegative(self):
        import math
        for item in CATALOG:
            for scenario in [Scenario(noise=0,trend=-1,seasonality=80,lead_time=6),Scenario(noise=3,trend=2,seasonality=80,service_level=.99)]:
                analysis=run_analysis(item,scenario)
                for key in ["cycle","safety","pipeline","reorder_point"]:
                    self.assertTrue(math.isfinite(analysis["inventory"][key]))
                    self.assertGreaterEqual(analysis["inventory"][key],0)

    def test_invalid_parameters_rejected(self):
        for values in [{"lead_time":0},{"noise":-1},{"service_level":1},{"capacity_factor":.5}]:
            with self.assertRaises(ValueError): Scenario(**values)

if __name__=="__main__":
    unittest.main()
