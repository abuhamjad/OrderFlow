import streamlit as st
import pandas as pd
from io import BytesIO
import gspread
from google.oauth2.service_account import Credentials
import plotly.express as px
from dotenv import load_dotenv
import os

load_dotenv()

username = os.getenv("APP_USERNAME")
password = os.getenv("APP_PASSWORD")

st.set_page_config(page_title="Order Manager", layout="wide")

# ------------------------
# Config
# ------------------------
USERS = {
    username: {
        "password": password,
        "sheet_id": "1agUjycF9vC-CtRGd4FTvUKoR15aUal4GsLWjJogon4c",
        "sheet_name": "order-flow-data",
        "csv_file": "orders.csv"
    },
    "test": {
        "password": "",
        "sheet_id": "1jRVGMtSsfupWb5Ctz4Gqkbyd2n6H142q648M93_u8T4",
        "sheet_name": "order-flow-test",
        "csv_file": "sample_orders.csv"
    }
}


EXPECTED_COLS = [
    "Customer Name", "Number", "Order", "Quantity", "Nameset",
    "Cost Price", "Sale Price", "Profit",
    "Order Status", "Payment Status", "Tracking Detail", "Date"
]

# ------------------------
# Auth Helpers
# ------------------------
def get_gspread_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive",
        "https://www.googleapis.com/auth/spreadsheets"
    ]
    service_account_info = dict(st.secrets["gcp_service_account"])
    creds = Credentials.from_service_account_info(service_account_info, scopes=scope)
    return gspread.authorize(creds)

# ------------------------
# Load from Google Sheets
# ------------------------
def load_data_from_google_sheets(google_sheet_id, sheet_name):
    client = get_gspread_client()
    sheet = client.open_by_key(google_sheet_id)
    worksheet = sheet.worksheet(sheet_name)

    rows = worksheet.get_all_values()
    if not rows or len(rows) < 2:
        return pd.DataFrame(columns=EXPECTED_COLS)
    else:
        df = pd.DataFrame(rows[1:], columns=rows[0])
        for col in ["Quantity", "Cost Price", "Sale Price", "Profit"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        return df


# ------------------------
# Upload to Google Sheets
# ------------------------
def upload_to_google_sheets(df, google_sheet_id, sheet_name):
    client = get_gspread_client()
    sheet = client.open_by_key(google_sheet_id)

    try:
        worksheet = sheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=sheet_name, rows="1000", cols="20")

    df_sorted = df.sort_values(by="Date").reset_index(drop=True)
    df_sorted["Date"] = df_sorted["Date"].dt.strftime("%d-%m-%Y")

    worksheet.clear()
    worksheet.update(
        [df_sorted.columns.values.tolist()] + df_sorted.fillna("").values.tolist()
    )
    print("✅ Google Sheets updated.")


# ------------------------
# Excel Export
# ------------------------
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Orders")
    return output.getvalue()

# ------------------------
# Safe Type Conversion
# ------------------------
def safe_int(value, default=1):
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default

def safe_float(value, default=0.0):
    try:
        return float(value)
    except (ValueError, TypeError):
        return default

# ------------------------
# Summary Dashboard
# ------------------------
def summary_dashboard(data):
    st.subheader("📊 Summary Dashboard")

    if "Date" not in data.columns or data["Date"].isnull().all():
        data["Date"] = pd.to_datetime("today")
    else:
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
        data = data.sort_values(by="Date").reset_index(drop=True)

    data["Month"] = data["Date"].dt.to_period("M").astype(str)

    total_orders = len(data)
    data["Quantity"] = pd.to_numeric(data["Quantity"], errors="coerce")
    data["Profit"] = pd.to_numeric(data["Profit"], errors="coerce")
    data["Sale Price"] = pd.to_numeric(data["Sale Price"], errors="coerce")

    total_quantity = data["Quantity"].sum()
    total_profit = data["Profit"].sum()
    total_sales = data["Sale Price"].sum()

    st.markdown(f"""
    - **Total Orders:** {total_orders}
    - **Total Quantity Ordered:** {total_quantity}
    - **Total Sales:** ₹{total_sales:,.2f}
    - **Total Profit:** ₹{total_profit:,.2f}
    """)

    monthly_summary = data.groupby("Month").agg({
        "Profit": "sum",
        "Order": "count",
        "Quantity": "sum"
    }).rename(columns={"Order": "Total Orders"}).reset_index()

    col1, col2 = st.columns(2)

    with col1:
        if not monthly_summary.empty:
            fig = px.line(
            monthly_summary,
            x="Month",
            y="Profit",
            markers=True,
            line_shape="spline",
            title="📈 Profit Trend",
            template="simple_white",
            color_discrete_sequence=["#0099ff"])

            fig.update_traces(line=dict(width=3))
            fig.update_layout(
            title_font_size=20,
            title_x=0.5,
            font=dict(size=14, color="#333"),
            height=300,
            margin=dict(l=10, r=10, t=40, b=10),)

            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data for profit chart.")

    with col2:
            if not monthly_summary.empty:
                fig = px.bar(
                monthly_summary,
                x="Month",
                y="Total Orders",
                title="📊 Monthly Orders",
                template="simple_white",
                color_discrete_sequence=["#ff7f0e"]
            )
                fig.update_traces(marker_line_width=1, marker_line_color="#333")
                fig.update_layout(
                title_font_size=20,
                title_x=0.5,
                font=dict(size=14, color="#333"),
                height=300,
                margin=dict(l=10, r=10, t=40, b=10),
            )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Not enough data for orders chart.")

    st.markdown("Insights")

    if not monthly_summary.empty:
        most_orders_month = monthly_summary.loc[monthly_summary["Total Orders"].idxmax(), "Month"]
        total_qty = monthly_summary.loc[monthly_summary["Month"] == most_orders_month, "Quantity"].values[0]
        total_profit_month = monthly_summary.loc[monthly_summary["Month"] == most_orders_month, "Profit"].values[0]

        best_selling_item = data["Order"].value_counts().idxmax()
        avg_price = data[data["Order"] == best_selling_item]["Sale Price"].mean()

        st.write(f"**Month with Most Sales:** `{most_orders_month}`")
        st.write(f"**Best-Selling Product:** `{best_selling_item}`")
        st.write(f"**Average Sale Price of Best-Seller:** ₹{avg_price:.2f}")
        st.write(f"**Total Quantity Sold in Best Month:** {total_qty}")
        st.write(f"**Total Profit in Best Month:** ₹{total_profit_month:,.2f}")
    else:
        st.info("Not enough data to generate monthly summary.")

# ------------------------
# Login Page
# ------------------------
def login_page():
    st.title("Login")

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False

    if not st.session_state.logged_in:
        col1, col2 = st.columns(2)

        with col1:
            with st.form("login_form"):
                username = st.text_input("Username")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login")

                if submitted:
                    if username in USERS and USERS[username]["password"] == password:
                        st.session_state.logged_in = True
                        st.session_state.username = username
                        st.success(f"Welcome, {username}!")
                        st.rerun()
                    else:
                        st.error("Invalid username or password.")

        with col2:
            st.markdown("### Quick Login")
            if st.button("Login as Test User"):
                st.session_state.logged_in = True
                st.session_state.username = "test"
                st.success("Logged in as test user!")
                st.rerun()

    else:
        st.toast(f"Logged in as **{st.session_state.username}**")
        if st.button("Logout"):
            st.session_state.clear()
            st.rerun()


# ------------------------
# Main App
# ------------------------
def main():

    if st.session_state["username"] == "test":
        st.warning("⚠️ You are in TEST MODE. Changes will not affect live data.")

    st.title("🧾 Order Flow")

    # Load from Google Sheets
    GOOGLE_SHEET_ID = USERS[st.session_state["username"]]["sheet_id"]
    CSV_FILE = USERS[st.session_state["username"]]["csv_file"]
    GOOGLE_SHEET_NAME = USERS[st.session_state["username"]]["sheet_name"]

    data = load_data_from_google_sheets(GOOGLE_SHEET_ID, GOOGLE_SHEET_NAME)
    data.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")


    tab1, tab2, tab3 = st.tabs(["📝 Manage Orders", "📊 Dashboard", "📋 All Orders"])

    # --------------------
    # Tab 1 - Manage Orders
    # --------------------
    with tab1:
        subtab1, subtab2 = st.tabs(["➕ Add Order", "✏️ Edit/Delete"])

        # Add Order
        with subtab1:
            st.header("Add New Order")
            with st.form("add_order_form"):
                col1, col2 = st.columns(2)
                name = col1.text_input("Customer Name")
                number = col2.text_input("Contact Number")

                order_input = st.text_area("Order Name(s)")
                order_list = [o.strip() for o in order_input.replace('\n', ',').split(',') if o.strip()]
                quantity = st.number_input("Quantity", min_value=1, step=1)
                nameset = st.text_input("Nameset")

                col3, col4 = st.columns(2)
                cost = col3.number_input("Cost Price", min_value=0.0, step=0.1)
                sale = col4.number_input("Sale Price", min_value=0.0, step=0.1)
                profit = sale - cost

                status = st.selectbox("Order Status", ["Pending", "In Production", "Shipped", "Delivered", "Cancelled"])
                payment = st.selectbox("Payment Status", ["Unpaid", "Partially Paid", "Paid"])
                tracking = st.text_input("Tracking Info (if any)")
                order_date = st.date_input("Order Date", value=pd.to_datetime("today").date())

                submitted = st.form_submit_button("Submit")
                if submitted:
                    if name and number and order_list:
                        new_entry = {
                            "Customer Name": name,
                            "Number": number,
                            "Order": "; ".join(order_list),
                            "Quantity": quantity,
                            "Nameset": nameset,
                            "Cost Price": cost,
                            "Sale Price": sale,
                            "Profit": profit,
                            "Order Status": status,
                            "Payment Status": payment,
                            "Tracking Detail": tracking,
                            "Date": pd.to_datetime(order_date)
                        }
                        data = pd.concat([data, pd.DataFrame([new_entry])], ignore_index=True)
                        upload_to_google_sheets(data, GOOGLE_SHEET_ID, GOOGLE_SHEET_NAME)
                        data.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
                        st.success("Order Added!")

                        st.rerun()

                    else:
                        st.error("Please fill in required fields.")

        # Edit/Delete Orders
        with subtab2:
            st.header("Edit / Delete Orders")

            if not data.empty:
                row_id = st.selectbox(
                    "Select Entry to Edit/Delete",
                    options=data.index,
                    format_func=lambda x: f"{x+1} - {data.loc[x, 'Customer Name']}"
                )
                row = data.loc[row_id]

                with st.form("edit_form"):
                    col1, col2 = st.columns(2)
                    name = col1.text_input("Customer Name", row["Customer Name"])
                    number = col2.text_input("Contact Number", row["Number"])
                    order = st.text_input("Order", row["Order"])
                    quantity = st.number_input("Quantity", value=safe_int(row.get("Quantity")), step=1)
                    nameset = st.text_input("Nameset", row["Nameset"])

                    col3, col4 = st.columns(2)
                    cost = col3.number_input("Cost Price", value=safe_float(row.get("Cost Price")), step=0.1)
                    sale = col4.number_input("Sale Price", value=safe_float(row.get("Sale Price")), step=0.1)
                    profit = sale - cost

                    order_status_options = ["Pending", "In Production", "Shipped", "Delivered", "Cancelled"]
                    status_index = order_status_options.index(str(row.get("Order Status", "")).strip()) \
                        if str(row.get("Order Status", "")).strip() in order_status_options else 0
                    status = st.selectbox("Order Status", order_status_options, index=status_index)

                    payment_status_options = ["Unpaid", "Partially Paid", "Paid"]
                    payment_index = payment_status_options.index(str(row.get("Payment Status", "")).strip()) \
                        if str(row.get("Payment Status", "")).strip() in payment_status_options else 0
                    payment = st.selectbox("Payment Status", payment_status_options, index=payment_index)

                    tracking = st.text_input("Tracking Info", row["Tracking Detail"])
                    date = st.date_input(
                        "Order Date",
                        value=row["Date"].date() if pd.notnull(row["Date"]) else pd.to_datetime("today").date()
                    )

                    col_save, col_delete = st.columns(2)
                    save = col_save.form_submit_button("Save")
                    delete = col_delete.form_submit_button("Delete")

                    if save:
                        data.loc[row_id] = [
                            name, number, order, quantity, nameset,
                            cost, sale, profit, status, payment, tracking,
                            pd.to_datetime(date)
                        ]
                        upload_to_google_sheets(data, GOOGLE_SHEET_ID, GOOGLE_SHEET_NAME)
                        data.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
                        st.success("Order Updated!")

                    if delete:
                        data = data.drop(index=row_id).reset_index(drop=True)
                        upload_to_google_sheets(data, GOOGLE_SHEET_ID, GOOGLE_SHEET_NAME)
                        data.to_csv(CSV_FILE, index=False, encoding="utf-8-sig")
                        st.warning("Order Deleted")

            else:
                st.info("No orders to modify.")

    # --------------------
    # Tab 2 - Dashboard
    # --------------------
    with tab2:
        summary_dashboard(data)

    # --------------------
    # Tab 3 - All Orders
    # --------------------
    with tab3:
        st.header("📋 All Orders")

        df_display = data.reset_index(drop=True)
        df_display.index += 1
        if "Date" in df_display.columns:
            df_display["Date"] = pd.to_datetime(df_display["Date"], errors="coerce").dt.strftime("%d-%m-%Y")

        st.dataframe(df_display)

        csv = df_display.to_csv(index=False).encode('utf-8')
        xlsx = to_excel(df_display)

        st.download_button("Download CSV", csv, file_name="orders.csv", mime="text/csv")
        st.download_button("Download Excel", xlsx, file_name="orders.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

login_page()

if st.session_state.get("logged_in", False):
    main()

