# config.py
# Project-wide constants and expected column names

REQUIRED_COLUMNS = [
    "call_id",
    "call_ts",        # timestamp string: YYYY-MM-DD HH:MM:SS
    "caller_lat",
    "caller_lon",
    "category",
    "jurisdiction"
]

DATE_COL = "call_ts"
CATEGORY_COL = "category"
JURISDICTION_COL = "jurisdiction"

# festival months (used in synthetic generation and optional feature flags)
FESTIVAL_MONTHS = [2, 3, 8, 9, 10, 11]
# Known festivals and their weeks (example dates, update as per real Goa calendar)
