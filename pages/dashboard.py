import streamlit as st
from backend.dashboard_login import get_dashboard_metrics, get_active_orders, get_supplier_id, update_order_status, get_supplier_alerts

#Session Guard
if st.session_state.get("active_supplier_id") is None:
    st.warning("Please select a supplier on the home page first.")
    st.page_link("login.py", label="Go to Login", icon="🔒")
    st.stop()

#Read the session_state values saved on the login page
supplier_id = st.session_state["active_supplier_id"]
supplier_name = st.session_state["active_supplier_name"]


st.set_page_config(layout="wide")
st.title(f"Welcome, {supplier_name}")
st.space("xlarge")



#displays dashboard metrics
with st.container(border=True):
    st.markdown("""
        <style>
        [data-testid="stMetric"] {
            display: flex;
            flex-direction: column;
            align-items: center;
            text-align: center;
        }
        [data-testid="stMetricLabel"] {
            justify-content: center;
        }
        </style>
        """,
        unsafe_allow_html=True
    )
    data = get_dashboard_metrics(supplier_id)
    total,active,completed,products_sold,revenue = st.columns([2,2,2,2,2])
    total.metric(label="total orders",value=data[0])
    active.metric(label="active orders",value=data[1])
    completed.metric(label="completed orders",value=data[2])
    products_sold.metric(label="products sold",value=data[3])
    revenue.metric(label="total revenue",value=f"${data[4]}")


active_orders,alerts = st.columns([1,1])

#displays active orders
with active_orders.container():
    active_df = get_active_orders(supplier_id)

    if active_df.empty:
        st.info("No active orders right now — all caught up!")
    else:
        # Filter & quick-update controls side-by-side
        filter_col, action_col = st.columns([2, 1], vertical_alignment="bottom")

        statuses = ["All"] + sorted(active_df["Status"].unique().tolist())
        selected_status = filter_col.selectbox("Filter by Status", statuses)

        filtered_df = (
            active_df if selected_status == "All"
            else active_df[active_df["Status"] == selected_status]
        )

        # Display clean full-width table
        st.dataframe(
            filtered_df,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Order Total ($)": st.column_config.NumberColumn(format="$%.2f")
            }
        )

        # Quick status update bar beneath the table
        with st.expander("Update an Order's Status"):
            u_col1, u_col2, u_col3 = st.columns([2, 2, 1], vertical_alignment="bottom")
            target_order = u_col1.selectbox("Order ID", active_df["Order ID"].tolist())
            next_status = u_col2.selectbox("New Status", ["Processing", "Shipped", "Completed"])
            if u_col3.button("Update", type="primary", use_container_width=True):
                if update_order_status(target_order, next_status):
                    st.rerun()  # Automatically refreshes both the table and the top KPIs!


with alerts.container(border=True, height=450):
    data = get_supplier_alerts(supplier_id)
    shipments_df = data["shipments"]
    stock_df = data["stock"]
    fleet_df = data["fleet"]

    total_alerts = len(shipments_df) + len(stock_df) + len(fleet_df)

    # Header row with live alert count badge
    hdr_col, badge_col = st.columns([3, 1], vertical_alignment="center")
    hdr_col.subheader("Operational Alerts")
    if total_alerts > 0:
        badge_col.markdown(f":red-badge[{total_alerts} Active]")
    else:
        badge_col.markdown(":green-badge[All Clear]")

    if total_alerts == 0:
        st.success("No delays, stock shortages, or fleet issues right now.")
    else:
        tab_all, tab_ship, tab_stock, tab_fleet = st.tabs([
            f"All ({total_alerts})",
            f"Shipments ({len(shipments_df)})",
            f"Stock ({len(stock_df)})",
            f"Fleet ({len(fleet_df)})",
        ])

        def render_shipment_alerts():
            for _, row in shipments_df.iterrows():
                if row["DeliveryHealth"] == "DELAYED":
                    st.error(
                        f"**Delayed Shipment — Order #{row['OrderID']}** ({row['CustomerName']})  \n"
                        f"Origin: {row['OriginWarehouse']} • ETA was `{row['EstimatedArrival']}`",
                        icon="🚨",
                    )
                else:
                    st.warning(
                        f"**Unscheduled Dispatch — Order #{row['OrderID']}** ({row['CustomerName']})  \n"
                        f"Order needs warehouse assignment and carrier dispatch.",
                        icon="📦",
                    )

        def render_stock_alerts():
            for _, row in stock_df.iterrows():
                is_out = row["QuantityOnHand"] == 0
                msg = (
                    f"**{'Out of Stock' if is_out else 'Low Stock'} — {row['ProductName']}** (`{row['SKU']}`)  \n"
                    f"{row['WarehouseName']}: **{row['QuantityOnHand']}** on hand (Reorder at {row['ReorderLevel']})"
                )
                if is_out:
                    st.error(msg, icon="❌")
                else:
                    st.warning(msg, icon="⚠️")

        def render_fleet_alerts():
            for _, row in fleet_df.iterrows():
                st.info(
                    f"**Vehicle in Maintenance — {row['LicensePlate']}** ({row['VehicleType']})  \n"
                    f"Unavailable for route assignment until cleared.",
                    icon="🔧",
                )

        with tab_all:
            render_shipment_alerts()
            render_stock_alerts()
            render_fleet_alerts()

        with tab_ship:
            if shipments_df.empty:
                st.caption("No shipment delays or unscheduled orders.")
            else:
                render_shipment_alerts()

        with tab_stock:
            if stock_df.empty:
                st.caption("All warehouse inventory levels are above reorder thresholds.")
            else:
                render_stock_alerts()

        with tab_fleet:
            if fleet_df.empty:
                st.caption("No vehicles currently in maintenance.")
            else:
                render_fleet_alerts()
