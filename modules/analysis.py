# modules/analysis.py
import pandas as pd

def agg_calls_by_day(df, date_col="date"):
    """Return DataFrame with counts per day."""
    series = df.groupby(date_col).size().reset_index(name="count")
    series = series.sort_values(date_col)
    return series

def agg_calls_by_hour(df, hour_col="hour"):
    """Return DataFrame with counts per hour (0-23)."""
    series = df.groupby(hour_col).size().reset_index(name="count")
    # Ensure hours 0-23 exist
    all_hours = pd.DataFrame({hour_col: list(range(24))})
    series = all_hours.merge(series, on=hour_col, how="left").fillna(0)
    series["count"] = series["count"].astype(int)
    return series

def category_distribution(df, category_col="category"):
    """Return DataFrame with counts and percentage by category."""
    counts = df[category_col].value_counts(dropna=False).reset_index()
    counts.columns = [category_col, "count"]
    counts["pct"] = counts["count"] / counts["count"].sum() * 100.0
    return counts

def compute_kpis(df):
    """Return basic KPIs as dict."""
    total_calls = len(df)
    avg_per_day = None
    try:
        days = (df["date"].max() - df["date"].min()).days + 1
        avg_per_day = total_calls / max(days, 1)
    except Exception:
        avg_per_day = None

    kpis = {
        "total_calls": int(total_calls),
        "avg_per_day": round(avg_per_day, 2) if avg_per_day is not None else None,
        "with_coords_pct": round(df["has_coords"].mean() * 100.0, 2) if "has_coords" in df.columns else None
    }
    return kpis

def interpret_time_series(ts_df):
    """Generate textual insights for time series (calls/day)."""
    insights = []
    if ts_df.empty:
        return ["No data available for selected period."]
    
    top_days = ts_df.nlargest(3, "count")
    low_days = ts_df.nsmallest(3, "count")

    insights.append(f"Peak day: {top_days.iloc[0]['date']} with {top_days.iloc[0]['count']} calls.")
    insights.append(f"Lowest day: {low_days.iloc[0]['date']} with only {low_days.iloc[0]['count']} calls.")

    avg = ts_df['count'].mean()
    if ts_df['count'].iloc[-1] > avg * 1.5:
        insights.append("Recent days show a surge in calls above the monthly average.")
    elif ts_df['count'].iloc[-1] < avg * 0.5:
        insights.append("Recent days show a significant drop in calls compared to average.")

    return insights

def interpret_hourly_distribution(hr_df):
    """Generate textual insights for hourly distribution."""
    insights = []
    if hr_df.empty:
        return ["No data available for selected period."]

    peak_hours = hr_df.nlargest(3, "count")
    low_hours = hr_df.nsmallest(3, "count")

    insights.append(f"Peak hour: {peak_hours.iloc[0]['hour']} with {peak_hours.iloc[0]['count']} calls.")
    insights.append(f"Quietest hour: {low_hours.iloc[0]['hour']} with only {low_hours.iloc[0]['count']} calls.")

    if peak_hours.iloc[0]['hour'] in range(18, 24):
        insights.append("Evening hours are consistently busy — likely crime and safety-related.")
    if peak_hours.iloc[0]['hour'] in range(6, 9):
        insights.append("Morning hours see high call activity — possibly accidents and medical emergencies.")

    return insights
