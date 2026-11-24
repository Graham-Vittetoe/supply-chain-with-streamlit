import streamlit as st

#Guard the page: redirect or stop if the user hasn't selected a supplier yet
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



# displays order count, total revenue
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
    #TODO: write function that returns list with each of these values in it
    #[total,active,completed,revenue]
    data = [10,8,2,35,100]
    total,active,completed,products_sold,revenue = st.columns([2,2,2,2,2])
    total.metric(label="total orders",value=data[0])
    active.metric(label="active orders",value=data[1])
    completed.metric(label="completed orders",value=data[2])
    products_sold.metric(label="products sold",value=data[3])
    revenue.metric(label="total revenue",value=f"${data[4]}")
