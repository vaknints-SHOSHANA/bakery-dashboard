import pandas as pd
import streamlit as st
from pyairtable import Api

st.set_page_config(page_title="Bakery Dashboard", page_icon="🥐", layout="wide")

TABLE_NAME = "Imported table"


# Loads the data from Airtable (not from a file!) and remembers it for 10 minutes
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

with st.expander("Rows with data issues"):
    if "data_issue" in df.columns:
        st.dataframe(df[df["data_issue"].fillna("") != ""])