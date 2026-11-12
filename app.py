import pandas as pd
import requests
import streamlit as st
from pyairtable import Api

st.set_page_config(page_title="Bakery Dashboard", page_icon="🥐", layout="wide")

TABLE_NAME = "Imported table"


# Loads the sales data from Airtable (not from a file!) and remembers it for 10 minutes
@st.cache_data(ttl=600, show_spinner="Loading data from Airtable... (about a minute)")
def load_data():
    api = Api(st.secrets["AIRTABLE_TOKEN"])
    table = api.table(st.secrets["AIRTABLE_BASE_ID"], TABLE_NAME)
    records = table.all()
    df = pd.DataFrame([r["fields"] for r in records])
    df["order_datetime"] = pd.to_datetime(df["order_datetime"], errors="coerce")
    df["line_total"] = pd.to_numeric(df["line_total"], errors="coerce")
    df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    return df


# Loads Israeli holidays from the Hebcal public API (free, no token needed)
@st.cache_data(ttl=86400, show_spinner="Loading holidays from Hebcal...")
def load_holidays(start, end):
    url = "https://www.hebcal.com/hebcal"
    params = {
        "v": 1,          # API version (required)
        "cfg": "json",   # send the answer as JSON
        "maj": "on",     # major holidays
        "i": "on",       # Israel holiday schedule
        "start": start,
        "end": end,
    }
    response = requests.get(url, params=params, timeout=20)
    response.raise_for_status()
    holidays = pd.DataFrame(response.json().get("items", []))
    if holidays.empty:
        return holidays
    holidays = holidays[holidays["category"] == "holiday"].copy()
    holidays["date"] = pd.to_datetime(holidays["date"].str[:10])
    return holidays[["date", "hebrew", "title"]]


df = load_data()

st.title("🥐 Bakery Sales Dashboard")
st.caption(f"Live data from Airtable: {len(df):,} rows")

# --- Sidebar ---
st.sidebar.header("Filters")
if st.sidebar.button("🔄 Refresh data"):
    st.cache_data.clear()
    st.rerun()

branches = sorted(df["branch"].dropna().unique())
chosen = st.sidebar.multiselect("Branch", branches, default=branches)

# Only real sales: completed orders in the chosen branches
sales = df[(df["status"] == "completed") & (df["branch"].isin(chosen))]

# --- Main numbers ---
c1, c2, c3, c4 = st.columns(4)
c1.metric("Revenue", f"₪{sales['line_total'].sum():,.0f}")
c2.metric("Orders", f"{sales['order_id'].nunique():,}")
c3.metric("Items sold", f"{sales['quantity'].sum():,.0f}")
avg = sales.groupby("order_id")["line_total"].sum().mean()
c4.metric("Avg order", f"₪{avg:,.1f}")

# --- Charts ---
st.subheader("Revenue by month")
monthly = sales.groupby(sales["order_datetime"].dt.strftime("%Y-%m"))["line_total"].sum()
st.line_chart(monthly)

left, right = st.columns(2)
with left:
    st.subheader("Revenue by branch")
    st.bar_chart(sales.groupby("branch")["line_total"].sum())
with right:
    st.subheader("Top 5 products")
    st.bar_chart(sales.groupby("product")["line_total"].sum().nlargest(5))

st.subheader("Revenue by channel")
st.bar_chart(sales.groupby("channel")["line_total"].sum())

# --- Holidays (external public API) ---
st.subheader("🕎 Israeli holidays and sales")
st.caption("Holiday dates come live from the Hebcal.com public API")

start = df["order_datetime"].min().strftime("%Y-%m-%d")
end = df["order_datetime"].max().strftime("%Y-%m-%d")

try:
    holidays = load_holidays(start, end)
except Exception as e:
    st.warning(f"Could not load holidays from Hebcal: {e}")
    holidays = pd.DataFrame()

if not holidays.empty:
    daily = sales.groupby(sales["order_datetime"].dt.date)["line_total"].sum()
    holidays["revenue"] = holidays["date"].dt.date.map(daily).fillna(0).round(0)
    holidays["open?"] = holidays["revenue"].apply(lambda r: "Open" if r > 0 else "Closed")

    h1, h2, h3 = st.columns(3)
    h1.metric("Holidays in this period", len(holidays))
    h2.metric("Average regular day", f"₪{daily.mean():,.0f}")
    eves = holidays[holidays["title"].str.startswith("Erev")]
    if not eves.empty:
        h3.metric("Average holiday eve", f"₪{eves['revenue'].mean():,.0f}")

    table = holidays.assign(date=holidays["date"].dt.strftime("%Y-%m-%d"))
    st.dataframe(table[["date", "hebrew", "title", "revenue", "open?"]], hide_index=True)

with st.expander("Rows with data issues"):
    if "data_issue" in df.columns:
        st.dataframe(df[df["data_issue"].fillna("") != ""])