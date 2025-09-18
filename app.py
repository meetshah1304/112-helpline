# app.py  (final, replace your current file with this)
import os
from datetime import timedelta

import pandas as pd
import plotly.express as px
import streamlit as st
import folium
from modules.data_loader import load_data, preprocess
from modules.analysis import agg_calls_by_day, agg_calls_by_hour, category_distribution, compute_kpis
import os
from modules.mapping import pydeck_points_map, pydeck_heatmap, pydeck_hexbin_map
from streamlit_folium import st_folium
import streamlit.components.v1 as components
from modules.data_loader import load_data, preprocess
from modules.analysis import (
    agg_calls_by_day, agg_calls_by_hour, category_distribution, compute_kpis,
    interpret_time_series, interpret_hourly_distribution
)
from modules.mapping import plot_points_on_map, plot_heatmap
from modules.festivals_ics import fetch_festivals_from_ics
from modules.festivals_utils import filter_significant_festivals
from modules.ui_calendar import render_month_calendar

st.set_page_config(page_title="Goa Police", layout="wide")
st.title("112 Helpline — Analytics Dashboard")

# -------------------------
# Input / Load data
# -------------------------
st.sidebar.header("Data Input")
uploaded_file = st.sidebar.file_uploader("Upload CSV/XLSX (call logs)", type=["csv", "xlsx"])
use_sample = st.sidebar.checkbox("Use sample dummy data", value=True)

df_raw, metadata = None, None
try:
    if uploaded_file is not None:
        df_raw, metadata = load_data(uploaded_file)
        st.sidebar.success(f"Loaded uploaded file ({metadata['record_count']} rows)")
    elif use_sample:
        sample_path = os.path.join("data", "112_calls_synthetic.csv")
        if not os.path.exists(sample_path):
            st.sidebar.error(f"Sample file not found at {sample_path}")
        else:
            df_raw, metadata = load_data(sample_path)
            st.sidebar.info(f"Loaded sample file ({metadata['record_count']} rows)")
    else:
        st.info("Upload a CSV/XLSX file or enable sample dataset from sidebar.")
except Exception as e:
    st.error(f"Error loading data: {e}")
    st.stop()

# -------------------------
# Preprocess
# -------------------------
df = preprocess(df_raw)  # ensures date, hour, weekday columns exist

# -------------------------
# Sidebar filters (date range, category, jurisdiction)
# -------------------------
st.sidebar.header("Filters")
min_date = pd.to_datetime(df["date"]).min()
max_date = pd.to_datetime(df["date"]).max()
date_range = st.sidebar.date_input("Date range", [min_date, max_date])

categories = df["category"].dropna().unique().tolist()
selected_categories = st.sidebar.multiselect("Category", options=categories, default=categories)

jurisdictions = df["jurisdiction"].dropna().unique().tolist()
selected_jurisdictions = st.sidebar.multiselect("Jurisdiction", options=jurisdictions, default=jurisdictions)

# Show festival calendar right below date input (always show all festival days)
# We'll fetch all festivals first (cached in fetch function)
try:
    all_festivals = fetch_festivals_from_ics()
except Exception as e:
    st.sidebar.warning(f"Could not fetch festival ICS: {e}")
    all_festivals = []

if all_festivals:
    # build festival map for the month of the selected start date
    sel_date = pd.to_datetime(date_range[0])
    year, month = sel_date.year, sel_date.month

    festival_dates_map = {}
    for name, fs, fe in all_festivals:
        cur = pd.to_datetime(fs).date()
        endd = pd.to_datetime(fe).date()
        while cur <= endd:
            festival_dates_map.setdefault(cur.isoformat(), []).append(name)
            cur = cur + timedelta(days=1)

    calendar_html = render_month_calendar(year, month, festival_dates_map)
    st.sidebar.markdown("### Festivals Calendar")
    with st.sidebar:
        components.html(calendar_html, height=300)


# -------------------------
# Apply dataset filters to create df_filtered
# -------------------------
mask = (
    (pd.to_datetime(df["date"]) >= pd.to_datetime(date_range[0])) &
    (pd.to_datetime(df["date"]) <= pd.to_datetime(date_range[1])) &
    (df["category"].isin(selected_categories)) &
    (df["jurisdiction"].isin(selected_jurisdictions))
)
df_filtered = df[mask].copy()

# -------------------------
# Determine festivals in selected date range (all) and significant subset
# -------------------------
start_sel = pd.to_datetime(date_range[0])
end_sel = pd.to_datetime(date_range[1])

festivals_in_range_all = []
for name, fs, fe in all_festivals:
    fs_ts = pd.to_datetime(fs)
    fe_ts = pd.to_datetime(fe)
    if (start_sel <= fe_ts) and (end_sel >= fs_ts):
        festivals_in_range_all.append((name, fs_ts, fe_ts))

# Determine significant festivals based on crime spikes (category='crime' default)
significant_festals_info = filter_significant_festivals(festivals_in_range_all, df, category='crime',
                                                        threshold_pct=30.0, min_calls=5)
# create a set of festival names that are significant for quick lookup
significant_names = {f['name'] for f in significant_festals_info}

# -------------------------
# Tag df_filtered rows with festival_name (for stacking & other use)
# -------------------------
def tag_festival_for_row(ts):
    for name, fs, fe in festivals_in_range_all:
        if fs <= ts <= fe:
            return name
    return "Non-Festival"

# Tagging uses all festivals that fall in the selected date range (not only significant)
if festivals_in_range_all:
    # ensure call_ts is datetime
    df_filtered["festival_name"] = df_filtered["call_ts"].apply(tag_festival_for_row)
else:
    df_filtered["festival_name"] = "Non-Festival"

# Show overlap warning only if the selected range is small (<= 31 days)
range_days = (end_sel - start_sel).days
if festivals_in_range_all and range_days <= 31:
    overlapping_texts = []
    for name, fs, fe in festivals_in_range_all:
        overlapping_texts.append(f"**{name}** ({fs.date()} → {fe.date()})")
    st.warning("Selected date range overlaps festival(s): " + "; ".join(overlapping_texts))


# -------------------------
# KPIs
# -------------------------
kpi1, kpi2, kpi3 = st.columns(3)
kpis = compute_kpis(df_filtered)
kpi1.metric("Total calls (filtered)", kpis["total_calls"])
kpi2.metric("Avg calls / day", kpis["avg_per_day"])
kpi3.metric("% with coordinates", f"{kpis['with_coords_pct']}%")

st.markdown("---")
left, right = st.columns([2, 1])

# -------------------------
# Mapping
# -------------------------
st.markdown("## Spatial Mapping")
tab1, tab2, tab3 = st.tabs(["Points Map", "Hotspot Heatmap", "Hexbin Hotspots"])

with tab1:
    # Pydeck points map
    deck_points = pydeck_points_map(df_filtered)
    if deck_points:
        st.pydeck_chart(deck_points)
    else:
        st.info("No valid coordinates to plot.")

with tab2:
    # Pydeck heatmap
    deck_heat = pydeck_heatmap(df_filtered)
    if deck_heat:
        st.pydeck_chart(deck_heat)
    else:
        st.info("No valid coordinates to plot heatmap.")
    st.sidebar.write("Valid coords in filtered data:", df_filtered[['caller_lat', 'caller_lon']].dropna().shape[0])

with tab3:
    # Pydeck hexbin map
    deck_hex = pydeck_hexbin_map(df_filtered)
    if deck_hex:
        st.pydeck_chart(deck_hex)
    else:
        st.info("No valid coordinates to plot hexbin hotspots.")

# -------------------------
# Time series (highlight all festivals, annotate only significant)
# -------------------------
with left:
    st.subheader("Time Series — Calls by Day")
    ts_df = agg_calls_by_day(df_filtered, date_col="date")

    if not ts_df.empty:
        fig = px.line(ts_df, x="date", y="count", labels={"date": "Date", "count": "Calls"})

        # shade all festival intervals (light)
        for name, fs, fe in festivals_in_range_all:
            fig.add_vrect(
                x0=fs, x1=fe,
                fillcolor="orange", opacity=0.12,
                layer="below", line_width=0
            )

        # annotate only significant festivals (give exact day and percent)
        if significant_festals_info:
            # determine y position for annotations
            y_top = ts_df['count'].max() if not ts_df['count'].empty else 1
            y_annot = y_top * 1.05

            for info in significant_festals_info:
                fname = info['name']
                fday = pd.to_datetime(info['max_day'])
                pct = info['max_pct']
                cnt = info['max_count']
                ann_text = f"{fname}: +{pct:.0f}% ({cnt} calls)"
                fig.add_annotation(
                    x=fday, y=y_annot,
                    text=ann_text,
                    showarrow=False,
                    bgcolor="black",
                    bordercolor="orange",
                    borderwidth=1,
                    font=dict(size=10)
                )

        st.plotly_chart(fig, use_container_width=True)

        insights = interpret_time_series(ts_df)
        st.markdown("**Insights:**")
        for ins in insights:
            st.markdown(f"- {ins}")
    else:
        st.info("No data for selected filters.")

    # -------------------------
    # Hourly distribution (stacked by festival_name if present)
    # -------------------------
    st.subheader("Hourly Distribution")
    if festivals_in_range_all:
        hr = df_filtered.groupby(["hour", "festival_name"]).size().reset_index(name="count")
        fig2 = px.bar(hr, x="hour", y="count", color="festival_name", barmode="stack",
                      labels={"hour": "Hour of Day", "count": "Calls"})
        hr_totals = hr.groupby("hour")["count"].sum().reset_index()
        insights = interpret_hourly_distribution(hr_totals)
    else:
        hr = agg_calls_by_hour(df_filtered, hour_col="hour")
        fig2 = px.bar(hr, x="hour", y="count", labels={"hour": "Hour of Day", "count": "Calls"})
        insights = interpret_hourly_distribution(hr)

    st.plotly_chart(fig2, use_container_width=True)
    st.markdown("**Insights:**")
    for ins in insights:
        st.markdown(f"- {ins}")

# -------------------------
# Category distribution (unchanged)
# -------------------------
with right:
    st.subheader("Category Distribution")
    cat_df = category_distribution(df_filtered, category_col="category")
    if not cat_df.empty:
        fig3 = px.pie(cat_df, names="category", values="count", title="Calls by Category", hole=0.3)
        st.plotly_chart(fig3, use_container_width=True)

    st.markdown("### Data Sample")
    st.dataframe(df_filtered.head(10))

st.markdown("---")
st.write("Debug: data source metadata")
st.json(metadata)
