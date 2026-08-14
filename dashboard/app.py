from __future__ import annotations

import os
from pathlib import Path

import duckdb
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


# ---------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB = PROJECT_ROOT / "data" / "sample.duckdb"
DB_PATH = Path(os.getenv("SECTOR_PULSE_DB", DEFAULT_DB))

# If no custom database is supplied, we consider the app to be in demo mode.
IS_DEMO = DB_PATH.resolve() == DEFAULT_DB.resolve()


# ---------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="Sector Pulse",
    page_icon="📈",
    layout="wide",
)

st.title("Sector Pulse")
st.caption(
    "Retail sector alt-data tracker — prices, Google Trends proxies, "
    "SEC filings, anomalies, and peer divergence"
)

if IS_DEMO:
    st.markdown(
        """
        <span style="
            display:inline-block;
            padding:4px 10px;
            border-radius:6px;
            background-color:#3b2f12;
            color:#f3c969;
            font-size:0.78rem;
            font-weight:700;
            letter-spacing:0.04em;
            margin-bottom:8px;">
            DEMO DATA — SYNTHETIC SIGNALS
        </span>
        """,
        unsafe_allow_html=True,
    )
else:
    st.markdown(
        """
        <span style="
            display:inline-block;
            padding:4px 10px;
            border-radius:6px;
            background-color:#12351f;
            color:#75d695;
            font-size:0.78rem;
            font-weight:700;
            letter-spacing:0.04em;
            margin-bottom:8px;">
            LIVE DATA
        </span>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------

if DB_PATH.exists():
    conn = duckdb.connect(str(DB_PATH), read_only=True)
    db_label = str(DB_PATH)
else:
    from src.demo import build_demo

    conn = duckdb.connect(":memory:")
    build_demo(conn)

    db_label = (
        "in-memory deterministic demo "
        "(run `make demo` to persist data/sample.duckdb)"
    )

ticker_df = conn.execute(
    "SELECT * FROM dim_ticker ORDER BY ticker"
).df()

if ticker_df.empty:
    st.warning("No tickers loaded.")
    st.stop()


# ---------------------------------------------------------------------
# Ticker selection
# ---------------------------------------------------------------------

ticker = st.selectbox(
    "Ticker",
    ticker_df["ticker"].tolist(),
    index=0,
)

company = ticker_df.loc[ticker_df["ticker"] == ticker].iloc[0]


# ---------------------------------------------------------------------
# Load selected ticker data
# ---------------------------------------------------------------------

price = conn.execute(
    """
    SELECT *
    FROM fact_price
    WHERE ticker = ?
    ORDER BY date
    """,
    [ticker],
).df()

trends = conn.execute(
    """
    SELECT *
    FROM fact_trends
    WHERE ticker = ?
    ORDER BY date
    """,
    [ticker],
).df()

filings = conn.execute(
    """
    SELECT *
    FROM fact_filings
    WHERE ticker = ?
    ORDER BY filing_date
    """,
    [ticker],
).df()

anomalies = conn.execute(
    """
    SELECT *
    FROM fact_anomaly
    WHERE ticker = ?
      AND flagged
    ORDER BY date DESC
    """,
    [ticker],
).df()

financials = conn.execute(
    """
    SELECT *
    FROM fact_financials
    WHERE ticker = ?
    ORDER BY period_end
    """,
    [ticker],
).df()


# ---------------------------------------------------------------------
# Company header + KPIs
# ---------------------------------------------------------------------

st.subheader(company["company_name"])
st.caption(company["subsector"])

latest = price.iloc[-1] if not price.empty else None

if not anomalies.empty:
    anomaly_dates = pd.to_datetime(anomalies["date"])
    cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=90)
    flagged_90 = anomalies[anomaly_dates >= cutoff]
else:
    flagged_90 = anomalies

latest_filing = (
    pd.to_datetime(filings["filing_date"]).max()
    if not filings.empty
    else None
)

k1, k2, k3, k4 = st.columns(4)

k1.metric(
    "Latest close",
    f"${latest['close']:,.2f}" if latest is not None else "—",
)

k2.metric(
    "90d anomaly flags",
    int(len(flagged_90)),
)

k3.metric(
    "Filings loaded",
    int(len(filings)),
)

k4.metric(
    "Latest filing",
    latest_filing.strftime("%b %d, %Y")
    if latest_filing is not None
    else "—",
)


# ---------------------------------------------------------------------
# Price vs search-interest chart
# ---------------------------------------------------------------------

st.subheader("Price vs. Search Interest")
st.caption(
    "Closing price compared with normalized Google search-interest proxies. "
    "Diamond markers indicate SEC filing dates."
)

fig = make_subplots(
    specs=[[{"secondary_y": True}]]
)

if not price.empty:
    fig.add_trace(
        go.Scatter(
            x=price["date"],
            y=price["close"],
            name="Close Price",
            mode="lines",
        ),
        secondary_y=False,
    )

if not trends.empty:
    weekly = (
        trends.groupby("date", as_index=False)["interest_score"]
        .mean()
        .sort_values("date")
    )

    fig.add_trace(
        go.Scatter(
            x=weekly["date"],
            y=weekly["interest_score"],
            name="Search Interest",
            mode="lines",
        ),
        secondary_y=True,
    )

if not filings.empty and not price.empty:
    price_lookup = price.set_index(
        pd.to_datetime(price["date"])
    )["close"]

    marker_dates = []
    marker_prices = []
    marker_labels = []

    for row in filings.itertuples():
        dt = pd.Timestamp(row.filing_date)

        nearest_idx = price_lookup.index.get_indexer(
            [dt],
            method="nearest",
        )[0]

        marker_dates.append(dt)
        marker_prices.append(price_lookup.iloc[nearest_idx])
        marker_labels.append(row.filing_type)

    fig.add_trace(
        go.Scatter(
            x=marker_dates,
            y=marker_prices,
            mode="markers",
            marker_symbol="diamond",
            marker_size=9,
            name="SEC Filing",
            text=marker_labels,
            hovertemplate=(
                "%{x}<br>"
                "Price: $%{y:.2f}<br>"
                "Filing: %{text}"
                "<extra></extra>"
            ),
        ),
        secondary_y=False,
    )

fig.update_layout(
    height=400,
    margin=dict(l=10, r=10, t=20, b=10),
    legend=dict(
        orientation="h",
        yanchor="bottom",
        y=1.02,
        xanchor="left",
        x=0,
    ),
    hovermode="x unified",
)

fig.update_yaxes(
    title_text="Price ($)",
    secondary_y=False,
)

fig.update_yaxes(
    title_text="Search Interest (0–100)",
    secondary_y=True,
)

st.plotly_chart(
    fig,
    use_container_width=True,
)


# ---------------------------------------------------------------------
# Latest signal
# ---------------------------------------------------------------------

st.subheader("Latest Signal")

if anomalies.empty:
    st.info(
        "No anomaly flags are currently available for this ticker."
    )
else:
    latest_signal = anomalies.iloc[0]

    signal_date = pd.Timestamp(
        latest_signal["date"]
    ).strftime("%b %d, %Y")

    z_score = float(latest_signal["z_score"])

    s1, s2, s3 = st.columns([1, 1, 3])

    s1.metric(
        "Signal date",
        signal_date,
    )

    s2.metric(
        "Z-score",
        f"{z_score:+.2f}σ",
    )

    with s3:
        st.markdown("**Interpretation**")
        st.write(latest_signal["description"])

    if IS_DEMO:
        st.caption(
            "Illustrative signal generated from deterministic synthetic "
            "demo data; not an investment recommendation."
        )


# ---------------------------------------------------------------------
# Detailed anomaly + financial tables
# ---------------------------------------------------------------------

left_table, right_table = st.columns([2, 1])

with left_table:
    st.subheader("Flagged Anomalies")

    if anomalies.empty:
        st.info("No anomaly flags for this ticker.")
    else:
        view = anomalies[
            [
                "date",
                "metric",
                "value",
                "z_score",
                "description",
            ]
        ].copy()

        view["date"] = pd.to_datetime(
            view["date"]
        ).dt.date

        view["z_score"] = (
            view["z_score"]
            .astype(float)
            .round(2)
        )

        st.dataframe(
            view,
            use_container_width=True,
            hide_index=True,
        )


with right_table:
    st.subheader("Latest Financial Facts")

    if financials.empty:
        st.info("No financial facts loaded.")
    else:
        latest_fin = (
            financials
            .sort_values("period_end")
            .groupby("tag", as_index=False)
            .tail(1)
            .copy()
        )

        latest_fin["value"] = latest_fin["value"].map(
            lambda x: f"${x / 1e9:,.1f}B"
        )

        latest_fin["period_end"] = pd.to_datetime(
            latest_fin["period_end"]
        ).dt.date

        st.dataframe(
            latest_fin[
                [
                    "tag",
                    "period_end",
                    "value",
                ]
            ],
            use_container_width=True,
            hide_index=True,
        )


# ---------------------------------------------------------------------
# Peer-pair divergence
# ---------------------------------------------------------------------

st.subheader("Peer Divergence")
st.caption(
    "Standardized divergence in peer returns can surface periods where "
    "normally comparable retailers begin behaving differently."
)

pair_all = conn.execute(
    """
    SELECT *
    FROM fact_pair_divergence
    ORDER BY pair, date
    """
).df()

if not pair_all.empty:

    latest_pairs = (
        pair_all
        .sort_values("date")
        .groupby("pair", as_index=False)
        .tail(1)
        .sort_values("pair")
    )

    summary_columns = st.columns(len(latest_pairs))

    for column, (_, row) in zip(
        summary_columns,
        latest_pairs.iterrows(),
    ):
        z = float(row["z_score"])

        column.metric(
            row["pair"],
            f"{z:+.2f}σ",
        )

    pairs = sorted(
        pair_all["pair"].dropna().unique().tolist()
    )

    selected_pair = st.selectbox(
        "Inspect pair",
        pairs,
    )

    pair_df = (
        pair_all[
            pair_all["pair"] == selected_pair
        ]
        .sort_values("date")
        .copy()
    )

    pair_fig = go.Figure()

    pair_fig.add_trace(
        go.Scatter(
            x=pair_df["date"],
            y=pair_df["z_score"],
            name="Return Divergence Z-score",
            mode="lines",
        )
    )

    flagged = pair_df[
        pair_df["flagged"].astype(bool)
    ]

    if not flagged.empty:
        pair_fig.add_trace(
            go.Scatter(
                x=flagged["date"],
                y=flagged["z_score"],
                mode="markers",
                marker_size=8,
                name="Flagged Divergence",
            )
        )

    pair_fig.add_hline(
        y=2.5,
        line_dash="dash",
        annotation_text="+2.5σ threshold",
    )

    pair_fig.add_hline(
        y=-2.5,
        line_dash="dash",
        annotation_text="-2.5σ threshold",
    )

    pair_fig.update_layout(
        height=300,
        margin=dict(
            l=10,
            r=10,
            t=20,
            b=10,
        ),
        yaxis_title="Divergence Z-score",
        xaxis_title=None,
        hovermode="x unified",
    )

    st.plotly_chart(
        pair_fig,
        use_container_width=True,
    )

else:
    st.info(
        "Load both members of a configured peer pair "
        "to populate divergence analysis."
    )


# ---------------------------------------------------------------------
# Footer
# ---------------------------------------------------------------------

st.divider()

if IS_DEMO:
    st.caption(
        "Sector Pulse • Demo mode • Synthetic deterministic data • "
        "Signals are illustrative and are not investment recommendations."
    )
else:
    st.caption(
        f"Sector Pulse • Database: {db_label}"
    )

conn.close()