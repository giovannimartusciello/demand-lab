"""Italian display resources; internal identifiers remain in English."""
METHOD_NAMES = {
    "moving_average": "Media mobile (3 mesi)",
    "linear_trend": "Regressione lineare",
    "seasonal_naive": "Naïve stagionale (riferimento)",
}
MONTH_NAMES = ("gen", "feb", "mar", "apr", "mag", "giu", "lug", "ago", "set", "ott", "nov", "dic")


def format_number(value, digits=0):
    return f"{value:,.{digits}f}".replace(",", "_").replace(".", ",").replace("_", ".")


def month_label(index):
    year, month = 2021+index//12, index % 12
    return f"{MONTH_NAMES[month]} {year}"
