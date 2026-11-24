import pandas as pd
import streamlit as st
from backend.shipments import (
    get_supplier_shipments,
    get_order_trace,
    get_fleet_and_drivers,
    dispatch_order,
    complete_shipment_delivery,
)
from backend.warehouse import get_warehouse_overview

st.set_page_config(
    page_title="Shipments & Fleet | Supply Chain Manager",
    layout="wide",
)

#Session State Guard
if "active_supplier_id" not in st.session_state or st.session_state["active_supplier_id"] is None:
    st.warning("Please log in as a supplier first.")
    st.stop()

supplier_id = st.session_state["active_supplier_id"]
supplier_name = st.session_state.get("active_supplier_name", "Supplier")

st.title("Shipments & Fleet Tracking")
st.caption(f"End-to-end order traceability, transit times, and dispatch operations for **{supplier_name}**")

ship_df = get_supplier_shipments(supplier_id)
wh_df = get_warehouse_overview(supplier_id)
vehicles_df, drivers_df = get_fleet_and_drivers(supplier_id)


#delivery metrics
delivered_df = ship_df[ship_df["ActualArrival"].notna()] if not ship_df.empty else pd.DataFrame()
avg_transit = round(float(delivered_df["TransitHours"].mean()), 1) if not delivered_df.empty else 0.0
on_time_count = int((delivered_df["DeliveryHealth"] == "ON TIME").sum()) if not delivered_df.empty else 0
otd_rate = round((on_time_count / len(delivered_df)) * 100, 1) if not delivered_df.empty else 100.0

in_transit_count = int(ship_df["ShipmentStatus"].isin(["In Transit", "Preparing"]).sum()) if not ship_df.empty else 0
delayed_count = int((ship_df["DeliveryHealth"] == "DELAYED").sum()) if not ship_df.empty else 0

with st.container(border=True):
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("On-Time Delivery Rate", f"{otd_rate}%")
    k2.metric("Avg Delivery Time", f"{avg_transit} hrs")
    k3.metric("Active Shipments", in_transit_count)
    k4.metric(
        "Delayed Shipments",
        delayed_count,
        delta=f"{delayed_count} overdue" if delayed_count > 0 else "None overdue",
        delta_color="inverse" if delayed_count > 0 else "normal",
    )

st.space("medium")


#shipment trace
with st.container(border=True):
    st.subheader("End-to-End Order & Product Trace")
    st.caption("Select any order to trace products from origin warehouse through transit legs to the customer.")

    if ship_df.empty:
        st.info("No orders available to trace.")
    else:
        order_options = {
            f"Order #{r['OrderID']} — {r['CustomerName']} [{r['DeliveryHealth']}]": int(r["OrderID"])
            for _, r in ship_df.iterrows()
        }
        selected_label = st.selectbox("Select Order to Inspect", list(order_options.keys()))
        selected_order_id = order_options[selected_label]

        trace = get_order_trace(supplier_id, selected_order_id)
        summary_df = trace["summary"]
        items_df = trace["items"]
        legs_df = trace["legs"]

        if not summary_df.empty:
            s = summary_df.iloc[0]

            # 1. Clean Summary Strip (prevents text truncation on long names)
            t1, t2, t3, t4 = st.columns([1.4, 1.4, 1, 1])
            with t1:
                st.caption("Origin Warehouse")
                st.markdown(f"**{s['OriginWarehouse'] or 'Unassigned'}**")
            with t2:
                st.caption("Destination Customer")
                st.markdown(f"**{s['CustomerName']}**")
            with t3:
                st.caption("Delivery Health")
                health = s["DeliveryHealth"]
                if health == "DELAYED":
                    st.markdown(":red-badge[DELAYED]")
                elif health == "DELIVERED LATE":
                    st.markdown(":orange-badge[DELIVERED LATE]")
                elif health == "ON TIME":
                    st.markdown(":green-badge[ON TIME]")
                else:
                    st.markdown(f":gray-badge[{health}]")
            with t4:
                st.caption("Calculated Transit Time")
                transit_txt = f"{s['TransitHours']} hrs" if pd.notna(s["TransitHours"]) else "In Progress"
                st.markdown(f"**{transit_txt}**")

            st.divider()

            # 2. Products Table
            st.markdown("**1. Products in Shipment**")
            st.dataframe(
                items_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Unit Price ($)": st.column_config.NumberColumn(format="$%.2f"),
                    "Line Total ($)": st.column_config.NumberColumn(format="$%.2f"),
                },
            )

            # 3. Carrier & Transit Legs Table
            st.markdown("**2. Carrier & Transit Legs**")
            if legs_df.empty:
                st.info("No transit legs scheduled yet for this order.")
            else:
                st.dataframe(
                    legs_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={
                        "Leg": st.column_config.NumberColumn(width="small"),
                        "Leg Status": st.column_config.TextColumn(width="small"),
                        "Departed": st.column_config.TextColumn(width="medium"),
                        "Arrived": st.column_config.TextColumn(width="medium"),
                    },
                )

                # 4. Full-Width Route Map inside the card
                map_points = []
                for _, leg in legs_df.iterrows():
                    for col_name, role in [("From Coordinates", "Origin/Hub"), ("To Coordinates", "Stop/Destination")]:
                        coords = leg[col_name]
                        if coords and "," in str(coords):
                            lat, lon = map(float, str(coords).split(","))
                            map_points.append({"lat": lat, "lon": lon, "point": role})
                if map_points:
                    st.markdown("**3. Route Waypoints**")
                    st.map(pd.DataFrame(map_points), zoom=3, height=480)