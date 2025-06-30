import streamlit as st
import pandas as pd
from io import BytesIO

query_params = st.query_params
IS_TEST = query_params.get("test", "0") == "1"

CSV_FILE = "sample_orders.csv" if IS_TEST else "orders.csv"

def init_csv():
    try:
        pd.read_csv(CSV_FILE)
    except FileNotFoundError:
        df = pd.DataFrame(columns=[
    "Customer Name", "Number", "Order", "Quantity", "Nameset",
    "Cost Price", "Sale Price", "Profit",
    "Order Status", "Payment Status", "Tracking Detail"
    ])

        df.to_csv(CSV_FILE, index=False)

def load_data():
    return pd.read_csv(CSV_FILE)
    data["Date"] = pd.to_datetime("today")
    return data


def save_data(entries):
    expected_columns = [
    "Customer Name", "Number", "Order", "Quantity", "Nameset",
    "Cost Price", "Sale Price", "Profit",
    "Order Status", "Payment Status", "Tracking Detail"
    ]

    df = pd.DataFrame(entries)

    # Ensure all expected columns are present
    for col in expected_columns:
        if col not in df.columns:
            df[col] = ""

    df = df[expected_columns]

    save_df = df.drop(columns="Date", errors="ignore")
    save_df.to_csv(
        CSV_FILE,
        mode='a',
        header=not pd.read_csv(CSV_FILE).shape[0],
        index=False
    )

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Orders")
    return output.getvalue()

def summary_dashboard(data):
    st.subheader("Summary Dashboard")

    if "Date" not in data.columns or data["Date"].isnull().all():
        data["Date"] = pd.to_datetime("today")
    else:
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")

    # Add Month column
    data["Month"] = data["Date"].dt.to_period("M").astype(str)

    # Monthly aggregation
    monthly_summary = data.groupby("Month").agg({
        "Profit": "sum",
        "Order": "count",
        "Quantity": "sum"
    }).rename(columns={"Order": "Total Orders"}).reset_index()

    # Summary metrics
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

    # Monthly aggregation
    monthly_summary = data.groupby("Month").agg({
        "Profit": "sum",
        "Order": "count",
        "Quantity": "sum"
    }).rename(columns={"Order": "Total Orders"}).reset_index()

    col1, col2 = st.columns(2)

    # Profit/Loss over time
    with col1:
        if not monthly_summary.empty:
            chart_data = monthly_summary[["Month", "Profit"]].set_index("Month")
            st.line_chart(chart_data, height=300)
        else:
            st.info("Not enough data for profit chart.")

    # Number of sales per month
    with col2:
        if not monthly_summary.empty:
            chart_data = monthly_summary[["Month", "Total Orders"]].set_index("Month")
            st.bar_chart(chart_data, height=300)
        else:
            st.info("Not enough data for orders chart.")

    # --------- Textual Insights ----------
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
        st.info("ℹ Not enough data to generate monthly summary.")


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


def main():
    st.set_page_config(page_title="Order Manager", layout="wide")
    st.title("Order Flow")

    if IS_TEST:
        st.warning("You are currently running in TEST MODE. Data changes will not affect the live system.")

    init_csv()
    data = load_data()

    # Ensure Date column exists
    if "Date" not in data.columns:
        data["Date"] = pd.to_datetime("today")
    else:
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data.fillna({"Date": pd.to_datetime("today")}, inplace=True)

    tab1, tab2, tab3 = st.tabs(["Manage Orders", "Dashboard", "Import Orders"])

    # TAB 1: Manage Orders
    with tab1:
        subtab1, subtab2, subtab3 = st.tabs(["Add Order", "Edit/Delete", "All Orders"])

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
                            "Date": pd.to_datetime("today")
                        }
                        save_data([new_entry])
                        st.success("Order Added!")
                    else:
                        st.error("Please fill in required fields.")

        # Edit/Delete Orders
        with subtab2:
            st.header("Edit / Delete Orders")

            if not data.empty:
                row_id = st.selectbox("Select Entry to Edit/Delete", options=data.index, format_func=lambda x: f"{x+1} - {data.loc[x, 'Customer Name']}")
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
                    try:
                        status_index = order_status_options.index(str(row.get("Order Status", "")).strip())
                    except ValueError:
                        status_index = 0
                    status = st.selectbox("Order Status", order_status_options, index=status_index)

                    payment_status_options = ["Unpaid", "Partially Paid", "Paid"]
                    try:
                        payment_index = payment_status_options.index(str(row.get("Payment Status", "")).strip())
                    except ValueError:
                        payment_index = 0
                    payment = st.selectbox("Payment Status", payment_status_options, index=payment_index)

                    tracking = st.text_input("Tracking Info", row["Tracking Detail"])
                    date = st.date_input("Order Date")


                    col_save, col_delete = st.columns(2)
                    save = col_save.form_submit_button("Save")
                    delete = col_delete.form_submit_button("Delete")

                    if save:
                        data.loc[row_id] = [
                            name, number, order, quantity, nameset,
                            cost, sale, profit, status, payment, tracking
                        ]
                        data.to_csv(CSV_FILE, index=False)
                        st.success("Order Updated!")

                    if delete:
                        data = data.drop(index=row_id)
                        data.to_csv(CSV_FILE, index=False)
                        st.warning("Order Deleted")
            else:
                st.info("ℹNo orders to modify.")

        # All Orders
        with subtab3:
            st.header("All Orders")
            df_display = data.reset_index(drop=True)
            df_display.index += 1  # Start from 1
            st.dataframe(df_display)

            # Download Buttons
            csv = df_display.to_csv(index=False).encode('utf-8')
            xlsx = to_excel(df_display)

            st.download_button("Download CSV", csv, file_name="orders.csv", mime="text/csv")
            st.download_button("Download Excel", xlsx, file_name="orders.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # TAB 2: Dashboard
    with tab2:
        summary_dashboard(data)

    # TAB 3: Import Orders
    with tab3:
        st.header("Import Orders from CSV")

        uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded_file:
            try:
                uploaded_df = pd.read_csv(uploaded_file)
                st.dataframe(uploaded_df)

                expected_cols = [
                    "Customer Name", "Number", "Order", "Quantity", "Nameset",
                    "Cost Price", "Sale Price", "Profit",
                    "Order Status", "Payment Status", "Tracking Detail"
                ]

                if list(uploaded_df.columns) == expected_cols:
                    if st.button("Import Orders"):
                        combined = pd.concat([data, uploaded_df], ignore_index=True)
                        combined.to_csv(CSV_FILE, index=False)
                        st.success("Orders Imported Successfully!")
                else:
                    st.error("Column structure mismatch. Use the provided template.")
            except Exception as e:
                st.error(f"Error reading file: {e}")

        st.download_button(
            label="Download CSV Template",
            data=pd.DataFrame(columns=[
                "Customer Name", "Number", "Order", "Quantity", "Nameset",
                "Cost Price", "Sale Price", "Profit",
                "Order Status", "Payment Status", "Tracking Detail"
            ]).to_csv(index=False).encode("utf-8"),
            file_name="order_template.csv",
            mime="text/csv"
        )
                
if __name__ == "__main__":
    main()
