# modules/festivals_utils.py
from datetime import timedelta
import pandas as pd

def filter_significant_festivals(festivals, df, category='crime', threshold_pct=30.0, min_calls=5):
    """
    Given a list of festivals [(name, start_ts, end_ts), ...] and the dataframe `df`
    (must contain 'date' as datetime.date and 'category' column), return a list of
    significant festival dicts:
    [
      {
        'name': name,
        'start': start_ts,
        'end': end_ts,
        'max_pct': ...,
        'max_count': ...,
        'max_day': datetime.date(...)
      },
      ...
    ]
    Criteria:
      - For each festival day, compute day_count = number of calls where category == category and date == that day.
      - Baseline for that weekday = average daily calls for that weekday for given category across dataset.
      - Percent increase = (day_count - baseline) / baseline * 100
      - If any day in festival has percent_increase >= threshold_pct and day_count >= min_calls,
        the festival is considered significant (we record the day with max_pct).
    """
    if df is None or df.empty:
        return []

    # Ensure 'date' column is datetime.date objects (if not, convert)
    df = df.copy()
    if not pd.api.types.is_datetime64_any_dtype(df['date']):
        df['date'] = pd.to_datetime(df['date'])
    # work with date-only index
    df['__date'] = pd.to_datetime(df['date']).dt.date

    # Series: counts per date for the category
    df_cat = df[df['category'].astype(str).str.lower() == category.lower()]
    if df_cat.empty:
        return []

    counts_by_date = df_cat.groupby('__date').size()  # index = date objects

    results = []
    for name, start_ts, end_ts in festivals:
        start_date = pd.to_datetime(start_ts).date()
        end_date = pd.to_datetime(end_ts).date()

        cur = start_date
        max_pct = -999.0
        max_count = 0
        max_day = None

        while cur <= end_date:
            day_count = int(counts_by_date.get(cur, 0))
            # compute baseline: average for same weekday across all dates in counts_by_date
            weekday = cur.weekday()  # Monday=0
            same_wd_counts = counts_by_date[[d for d in counts_by_date.index if d.weekday() == weekday]] \
                             if len(counts_by_date) > 0 else pd.Series(dtype=float)

            if not same_wd_counts.empty:
                baseline = same_wd_counts.mean()
            else:
                baseline = counts_by_date.mean() if not counts_by_date.empty else 0

            # avoid div by zero
            baseline_adj = baseline if baseline > 0 else 1.0

            pct = (day_count - baseline_adj) / baseline_adj * 100.0

            if day_count >= min_calls and pct > max_pct:
                max_pct = pct
                max_count = day_count
                max_day = cur

            cur = cur + timedelta(days=1)

        # if any day exceeded threshold, mark festival significant
        if max_day is not None and max_pct >= threshold_pct:
            results.append({
                'name': name,
                'start': start_ts,
                'end': end_ts,
                'max_pct': max_pct,
                'max_count': max_count,
                'max_day': pd.to_datetime(max_day)
            })

    return results
