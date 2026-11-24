import streamlit as st
from backend.general import load_supplier_names, get_supplier_id

st.set_page_config(page_title="Supply Chain Manager", layout="centered")

if "active_supplier_id" not in st.session_state:
    st.session_state["active_supplier_id"] = None
if "active_supplier_name" not in st.session_state:
    st.session_state["active_supplier_name"] = None

@st.cache_data
def get_suppliers():
    return load_supplier_names()

# Add vertical spacing to push the login card toward the vertical middle
st.write("")
st.write("")

# Narrow center column mimics a standard 400px login card
_, login_col, _ = st.columns([1, 2, 1])

with login_col:
    with st.form("supplier_login_form", border=True):
        st.markdown(
            "<h2 style='text-align: center; margin-bottom: 0;'>Supply Chain Manager</h2>"
            "<p style='text-align: center; color: gray; font-size: 0.9rem;'>Select your company portal to continue</p>",
            unsafe_allow_html=True
        )
        
        st.divider()

        selected_company = st.selectbox(
            label="Company",
            options=get_suppliers(),
            index=None,
            placeholder="Choose a supplier..."
        )

        st.write("")  # Slight breathing room above the button

        submitted = st.form_submit_button(
            label="Continue",
            type="primary",
            use_container_width=True
        )

        if submitted:
            if not selected_company:
                st.warning("Please select a company first.")
            else:
                supplier_id = get_supplier_id(selected_company)
                if supplier_id is not None:
                    st.session_state["active_supplier_id"] = supplier_id
                    st.session_state["active_supplier_name"] = selected_company
                    st.rerun()
                else:
                    st.error(f"Could not find ID for {selected_company}")

    # Status banner directly beneath the login card
    if st.session_state["active_supplier_id"] is not None:
        st.success(
            f"Signed in as **{st.session_state['active_supplier_name']}** "
            f"(ID: `{st.session_state['active_supplier_id']}`)"
        )