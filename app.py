import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from io import BytesIO
from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
from matplotlib.backends.backend_pdf import PdfPages
import gspread
from gspread_dataframe import get_as_dataframe, set_with_dataframe
from oauth2client.service_account import ServiceAccountCredentials


CSV_FILE = "orders.csv"

def init_csv():
    """Create CSV file if it does not exist."""
    try:
        pd.read_csv(CSV_FILE)
    except FileNotFoundError:
        df = pd.DataFrame(columns=[
            "Customer Name", "Number", "Order", "Quantity", "Nameset",
            "Cost Price", "Sale Price", "Profit",
            "Order Status", "Payment Status", "Tracking Detail", "Date"
        ])
        df.to_csv(CSV_FILE, index=False)

def load_data():
    try:
        client = get_gsheet_client()
        sheet = client.open("OrderData").sheet1  # Your sheet name
        df = get_as_dataframe(sheet).dropna(how='all')  # Clean blank rows
        return df
    except Exception as e:
        st.error(f"Error loading data from Google Sheets: {e}")
        return pd.DataFrame(columns=[
            "Customer Name", "Number", "Order", "Quantity", "Nameset",
            "Cost Price", "Sale Price", "Profit",
            "Order Status", "Payment Status", "Tracking Detail", "Date"
        ])

def export_charts_to_pdf(figures):
    """Export matplotlib figures to a PDF."""
    pdf_bytes = BytesIO()
    with PdfPages(pdf_bytes) as pdf:
        for fig in figures:
            pdf.savefig(fig, bbox_inches='tight')
    pdf_bytes.seek(0)
    return pdf_bytes

def save_data(entry):
    df = load_data()
    df = pd.concat([df, pd.DataFrame([entry])], ignore_index=True)

    try:
        client = get_gsheet_client()
        sheet = client.open("OrderData").sheet1
        set_with_dataframe(sheet, df)
    except Exception as e:
        st.error(f"Error saving to Google Sheets: {e}")
    
    # Add today's date if not already present
    df["Date"] = pd.to_datetime("today").normalize()
    
    # Ensure columns are in correct order
    expected_columns = [
        "Customer Name", "Number", "Order", "Quantity", "Nameset",
        "Cost Price", "Sale Price", "Profit",
        "Order Status", "Payment Status", "Tracking Detail", "Date"
    ]
    df = df[expected_columns]

    df.to_csv(CSV_FILE, mode='a', header=not pd.read_csv(CSV_FILE).shape[0], index=False)

def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name="Orders")
    return output.getvalue()

def summary_dashboard(data):
    st.subheader("📈 Summary Dashboard")

    # Parse and ensure datetime
    if "Date" not in data.columns or data["Date"].isnull().all():
        data["Date"] = pd.to_datetime("today")
    else:
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")

    data.dropna(subset=["Date"], inplace=True)
    data["Month"] = data["Date"].dt.to_period("M").astype(str)

    # Summary metrics
    total_orders = len(data)
    total_quantity = data["Quantity"].sum()
    total_profit = data["Profit"].sum()
    total_sales = data["Sale Price"].sum()

    st.markdown(f"""
    - 🧾 **Total Orders:** {total_orders}
    - 📦 **Total Quantity Ordered:** {total_quantity}
    - 💰 **Total Sales:** ₹{total_sales:,.2f}
    - 📈 **Total Profit:** ₹{total_profit:,.2f}
    """)

    figs = []

    # Monthly aggregation
    monthly_summary = data.groupby("Month").agg({
        "Profit": "sum",
        "Order": "count",
        "Quantity": "sum"
    }).rename(columns={"Order": "Total Orders"}).reset_index()

    col1, col2 = st.columns(2)

    # 📉 Profit/Loss over time
    with col1:
        fig1, ax1 = plt.subplots()
        ax1.plot(monthly_summary["Month"], monthly_summary["Profit"], marker='o', color='green')
        ax1.set_title("💹 Monthly Profit/Loss")
        ax1.set_ylabel("Profit (₹)")
        ax1.set_xlabel("Month")
        ax1.grid(True)
        st.pyplot(fig1)
        figs.append(fig1)

    # 📊 Number of sales per month
    with col2:
        fig2, ax2 = plt.subplots()
        ax2.bar(monthly_summary["Month"], monthly_summary["Total Orders"], color='orange')
        ax2.set_title("🛒 Monthly Order Count")
        ax2.set_ylabel("No. of Orders")
        ax2.set_xlabel("Month")
        st.pyplot(fig2)
        figs.append(fig2)

    # --------- Textual Insights ----------
    st.markdown("## 📌 Insights")

    if not monthly_summary.empty:
        most_orders_month = monthly_summary.loc[monthly_summary["Total Orders"].idxmax(), "Month"]
        total_qty = monthly_summary.loc[monthly_summary["Month"] == most_orders_month, "Quantity"].values[0]
        total_profit_month = monthly_summary.loc[monthly_summary["Month"] == most_orders_month, "Profit"].values[0]

        best_selling_item = data["Order"].value_counts().idxmax()
        avg_price = data[data["Order"] == best_selling_item]["Sale Price"].mean()

        st.write(f"📅 **Month with Most Sales:** `{most_orders_month}`")
        st.write(f"🏆 **Best-Selling Product:** `{best_selling_item}`")
        st.write(f"💸 **Average Sale Price of Best-Seller:** ₹{avg_price:.2f}")
        st.write(f"📦 **Total Quantity Sold in Best Month:** {total_qty}")
        st.write(f"💰 **Total Profit in Best Month:** ₹{total_profit_month:,.2f}")
    else:
        st.info("ℹ️ Not enough data to generate monthly summary.")

    pdf_file = export_charts_to_pdf(figs)
    st.download_button("📄 Download Dashboard Charts (PDF)", data=pdf_file, file_name="dashboard_charts.pdf", mime="application/pdf")

def get_gsheet_client():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("credentials.json", scope)
    client = gspread.authorize(creds)
    return client

def main():
    st.set_page_config(page_title="Order Manager", layout="wide")
    st.title("🛍️ Order Management System")

    init_csv()
    data = load_data()

    # Ensure Date column exists
    if "Date" not in data.columns:
        data["Date"] = pd.to_datetime("today")
    else:
        data["Date"] = pd.to_datetime(data["Date"], errors="coerce")
    data.fillna({"Date": pd.to_datetime("today")}, inplace=True)

    tab1, tab2, tab3 = st.tabs(["📝 Manage Orders", "📊 Dashboard", "📂 Import Orders"])

    # TAB 1: Manage Orders
    with tab1:
        subtab1, subtab2, subtab3 = st.tabs(["➕ Add Order", "✏️ Edit/Delete", "📋 All Orders"])

        # Add Order
        with subtab1:
            st.header("➕ Add New Order")
            with st.form("add_order_form"):
                col1, col2 = st.columns(2)
                name = col1.text_input("Customer Name")
                number = col2.text_input("Contact Number")

                order = st.text_input("Order Name")
                quantity = st.number_input("Quantity", min_value=1, step=1)
                nameset = st.text_input("Nameset (optional)")

                col3, col4 = st.columns(2)
                cost = col3.number_input("Cost Price", min_value=0.0, step=0.1)
                sale = col4.number_input("Sale Price", min_value=0.0, step=0.1)
                profit = sale - cost

                status = st.selectbox("Order Status", ["Pending", "In Production", "Shipped", "Delivered", "Cancelled"])
                payment = st.selectbox("Payment Status", ["Unpaid", "Partially Paid", "Paid"])
                tracking = st.text_input("Tracking Info (if any)")
                date = st.date_input("Order Date")

                submitted = st.form_submit_button("Submit")
                if submitted:
                    if name and number and order:
                        new_entry = {
                            "Customer Name": name,
                            "Number": number,
                            "Order": order,
                            "Quantity": quantity,
                            "Nameset": nameset,
                            "Cost Price": cost,
                            "Sale Price": sale,
                            "Profit": profit,
                            "Order Status": status,
                            "Payment Status": payment,
                            "Tracking Detail": tracking,
                            "Date": pd.to_datetime(date)
                        }
                        save_data(new_entry)
                        st.success("✅ Order Added!")
                    else:
                        st.error("❌ Please fill in required fields.")

        # Edit/Delete Orders
        with subtab2:
            st.header("✏️ Edit / Delete Orders")

            if not data.empty:
                row_id = st.selectbox("Select Entry to Edit/Delete", options=data.index, format_func=lambda x: f"{x+1} - {data.loc[x, 'Customer Name']}")
                row = data.loc[row_id]

                with st.form("edit_form"):
                    col1, col2 = st.columns(2)
                    name = col1.text_input("Customer Name", row["Customer Name"])
                    number = col2.text_input("Contact Number", row["Number"])
                    order = st.text_input("Order", row["Order"])
                    quantity = st.number_input("Quantity", value=int(row["Quantity"]), step=1)
                    nameset = st.text_input("Nameset", row["Nameset"])

                    col3, col4 = st.columns(2)
                    cost = col3.number_input("Cost Price", value=float(row["Cost Price"]), step=0.1)
                    sale = col4.number_input("Sale Price", value=float(row["Sale Price"]), step=0.1)
                    profit = sale - cost

                    status = st.selectbox("Order Status", ["Pending", "In Production", "Shipped", "Delivered", "Cancelled"], index=["Pending", "In Production", "Shipped", "Delivered", "Cancelled"].index(row["Order Status"]))
                    payment = st.selectbox("Payment Status", ["Unpaid", "Partially Paid", "Paid"], index=["Unpaid", "Partially Paid", "Paid"].index(row["Payment Status"]))
                    tracking = st.text_input("Tracking Info", row["Tracking Detail"])
                    date = st.date_input("Order Date", value=pd.to_datetime(row["Date"]).date())

                    col_save, col_delete = st.columns(2)
                    save = col_save.form_submit_button("💾 Save")
                    delete = col_delete.form_submit_button("🗑️ Delete")

                    if save:
                        data.loc[row_id] = [
                            name, number, order, quantity, nameset,
                            cost, sale, profit, status, payment, tracking, pd.to_datetime(date)
                        ]
                        data.to_csv(CSV_FILE, index=False)
                        st.success("✅ Order Updated!")

                    if delete:
                        data = data.drop(index=row_id)
                        data.to_csv(CSV_FILE, index=False)
                        st.warning("⚠️ Order Deleted")
            else:
                st.info("ℹ️ No orders to modify.")

        # All Orders
        with subtab3:
            st.header("📋 All Orders")
            df_display = data.reset_index(drop=True)
            df_display.index += 1  # Start from 1
            st.dataframe(df_display)

            # Download Buttons
            csv = df_display.to_csv(index=False).encode('utf-8')
            xlsx = to_excel(df_display)

            st.download_button("⬇️ Download CSV", csv, file_name="orders.csv", mime="text/csv")
            st.download_button("⬇️ Download Excel", xlsx, file_name="orders.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # TAB 2: Dashboard
    with tab2:
        summary_dashboard(data)

    # TAB 3: Import Orders
    with tab3:
        st.header("📂 Import Orders from CSV")

        st.download_button(
            label="⬇️ Download CSV Template",
            data=pd.DataFrame(columns=[
                "Customer Name", "Number", "Order", "Quantity", "Nameset",
                "Cost Price", "Sale Price", "Profit",
                "Order Status", "Payment Status", "Tracking Detail", "Date"
            ]).to_csv(index=False).encode("utf-8"),
            file_name="order_template.csv",
            mime="text/csv"
        )

        uploaded_file = st.file_uploader("Upload CSV", type=["csv"])
        if uploaded_file:
            try:
                uploaded_df = pd.read_csv(uploaded_file)
                st.dataframe(uploaded_df)

                expected_cols = [
                    "Customer Name", "Number", "Order", "Quantity", "Nameset",
                    "Cost Price", "Sale Price", "Profit",
                    "Order Status", "Payment Status", "Tracking Detail", "Date"
                ]

                if list(uploaded_df.columns) == expected_cols:
                    if st.button("📥 Import Orders"):
                        combined = pd.concat([data, uploaded_df], ignore_index=True)
                        combined.to_csv(CSV_FILE, index=False)
                        st.success("✅ Orders Imported Successfully!")
                else:
                    st.error("❌ Column structure mismatch. Use the provided template.")
            except Exception as e:
                st.error(f"❌ Error reading file: {e}")
                
if __name__ == "__main__":
    main()
