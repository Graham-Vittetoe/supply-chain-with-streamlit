import streamlit as st
from backend.warehouse import (
    get_warehouse_overview,
    get_supplier_inventory,
    restock_inventory,
)

st.set_page_config(
    page_title="Warehouses & Inventory | Supply Chain Manager",
    layout="wide",
)

# --- Session State Guard ---
if "active_supplier_id" not in st.session_state or st.session_state["active_supplier_id"] is None:
    st.warning("Please log in as a supplier first.")
    st.stop()

supplier_id = st.session_state["active_supplier_id"]
supplier_name = st.session_state.get("active_supplier_name", "Supplier")

# --- Page Header ---
st.title("Warehouses & Inventory")
st.caption(f"Facility utilization, delivery performance, and stock control for **{supplier_name}**")

wh_df = get_warehouse_overview(supplier_id)
inv_df = get_supplier_inventory(supplier_id)

# ==============================================================================
# ROW 1: Top-Level Inventory & Capacity KPIs
# ==============================================================================
total_units = int(inv_df["On Hand"].sum()) if not inv_df.empty else 0
total_value = float(inv_df["Stock Value ($)"].sum()) if not inv_df.empty else 0.0
low_stock_skus = int((inv_df["Stock Status"] != "Healthy").sum()) if not inv_df.empty else 0
total_capacity = int(wh_df["Capacity"].sum()) if not wh_df.empty else 0
overall_util = round((total_units / total_capacity) * 100, 1) if total_capacity > 0 else 0.0

with st.container(border=True):
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total Units Stored", f"{total_units:,}")
    k2.metric("Inventory Valuation", f"${total_value:,.2f}")
    k3.metric("Capacity Utilization", f"{overall_util}%")
    k4.metric(
        "Low / Out-of-Stock SKUs",
        low_stock_skus,
        delta=f"{low_stock_skus} need reorder" if low_stock_skus > 0 else "Healthy",
        delta_color="inverse" if low_stock_skus > 0 else "normal",
    )

st.space("medium")

# ==============================================================================
# ROW 2: Warehouse Capacity Bars & Performance Scorecard
# ==============================================================================
st.subheader("Facility Capacity & Delivery Performance")

if wh_df.empty:
    st.info("No warehouses found for this supplier.")
else:
    wh_cols = st.columns(len(wh_df))
    for col, (_, row) in zip(wh_cols, wh_df.iterrows()):
        with col.container(border=True):
            st.markdown(f"**{row['WarehouseName']}**")
            if row["Address"]:
                st.caption(row["Address"])

            cap = int(row["Capacity"])
            stored = int(row["UnitsStored"])
            ratio = min(stored / cap, 1.0) if cap > 0 else 0.0
            pct = round((stored / cap) * 100, 1) if cap > 0 else 0.0

            st.progress(ratio, text=f"Storage: {stored:,} / {cap:,} units ({pct}%)")

            m1, m2, m3 = st.columns(3)
            m1.metric("On-Time", f"{row['OnTimeRate']}%")
            m2.metric("Avg Transit", f"{row['AvgTransitHours']}h")
            m3.metric("Delayed", int(row["DelayedCount"]))

st.space("medium")

# ==============================================================================
# ROW 3: Interactive Stock Ledger (Left) & Quick Restock Form (Right)
# ==============================================================================
ledger_col, restock_col = st.columns([2.3, 1], vertical_alignment="top")

with ledger_col.container(border=True):
    st.subheader("Warehouse Stock Ledger")

    if inv_df.empty:
        st.info("No inventory records found.")
    else:
        # Filter Controls
        f1, f2, f3 = st.columns([1.2, 1.2, 1.6])
        warehouse_options = ["All Warehouses"] + sorted(inv_df["Warehouse"].unique().tolist())
        selected_wh = f1.selectbox("Warehouse", warehouse_options)

        status_options = ["All Statuses", "Low Stock", "Out of Stock", "Healthy"]
        selected_status = f2.selectbox("Stock Status", status_options)

        search_term = f3.text_input("Search SKU or Product", placeholder="e.g., BRK-500 or Brackets")

        # Apply Filters
        filtered_inv = inv_df.copy()
        if selected_wh != "All Warehouses":
            filtered_inv = filtered_inv[filtered_inv["Warehouse"] == selected_wh]
        if selected_status != "All Statuses":
            filtered_inv = filtered_inv[filtered_inv["Stock Status"] == selected_status]
        if search_term.strip():
            term = search_term.strip().lower()
            filtered_inv = filtered_inv[
                filtered_inv["SKU"].str.lower().str.contains(term)
                | filtered_inv["Product"].str.lower().str.contains(term)
            ]

        display_cols = [
            "Warehouse",
            "SKU",
            "Product",
            "On Hand",
            "Reorder Level",
            "Stock Value ($)",
            "Stock Status",
            "Last Updated",
        ]

        st.dataframe(
            filtered_inv[display_cols],
            use_container_width=True,
            hide_index=True,
            height=420,
            column_config={
                "Stock Value ($)": st.column_config.NumberColumn(format="$%.2f"),
                "On Hand": st.column_config.NumberColumn(format="%d"),
                "Reorder Level": st.column_config.NumberColumn(format="%d"),
            },
        )

with restock_col.container(border=True):
    st.subheader("Receive / Restock Inventory")
    st.caption("Log incoming stock to replenish a warehouse.")

    if inv_df.empty:
        st.info("Add products and warehouses before restocking.")
    else:
        with st.form("restock_form", clear_on_submit=True):
            wh_map = dict(zip(wh_df["WarehouseName"], wh_df["WarehouseID"]))
            chosen_wh_name = st.selectbox("Target Warehouse", list(wh_map.keys()))
            chosen_wh_id = wh_map[chosen_wh_name]

            # Filter products stocked in the chosen warehouse
            wh_products = inv_df[inv_df["WarehouseID"] == chosen_wh_id]
            prod_labels = {
                f"{r['SKU']} — {r['Product']} ({r['On Hand']} on hand)": r["ProductID"]
                for _, r in wh_products.iterrows()
            }

            chosen_prod_label = st.selectbox("Product (SKU)", list(prod_labels.keys()))
            added_qty = st.number_input("Quantity Received", min_value=1, max_value=50000, value=25, step=5)

            submitted = st.form_submit_button("Add to Inventory", type="primary", use_container_width=True)

            if submitted:
                chosen_prod_id = prod_labels[chosen_prod_label]
                if restock_inventory(chosen_wh_id, chosen_prod_id, int(added_qty)):
                    st.success(f"Added {added_qty} units to {chosen_wh_name}.")
                    st.rerun()
                else:
                    st.error("Failed to update inventory. Please try again.")