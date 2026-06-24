import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, date
from services.data_service import BackendDataService  # type: ignore

# Set page layout and configuration
st.set_page_config(
    page_title="Olist E-Commerce BI Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom premium styling
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700&display=swap');
    
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        font-family: 'Outfit', sans-serif;
        background-color: #0b0f19;
        color: #f8fafc;
    }
    
    [data-testid="stSidebar"] {
        background-color: #111827;
        border-right: 1px solid #1f2937;
    }
    
    /* Premium Title styling */
    .dashboard-title {
        font-size: 36px;
        font-weight: 700;
        background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 2px;
    }
    
    .dashboard-subtitle {
        font-size: 16px;
        color: #94a3b8;
        margin-bottom: 24px;
    }
    
    /* Glassmorphism Metric Cards */
    .metric-container {
        display: flex;
        gap: 16px;
        margin-bottom: 24px;
        flex-wrap: wrap;
    }
    
    .metric-card {
        flex: 1;
        min-width: 180px;
        background: linear-gradient(135deg, #1f2937 0%, #111827 100%);
        border: 1px solid #374151;
        border-radius: 16px;
        padding: 24px 16px;
        text-align: center;
        box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
        transition: transform 0.2s, border-color 0.2s, box-shadow 0.2s;
    }
    
    .metric-card:hover {
        transform: translateY(-4px);
        border-color: #06b6d4;
        box-shadow: 0 10px 15px -3px rgba(6, 182, 212, 0.1), 0 4px 6px -2px rgba(6, 182, 212, 0.05);
    }
    
    .metric-value {
        font-size: 32px;
        font-weight: 700;
        color: #06b6d4;
        margin-bottom: 6px;
        letter-spacing: -0.025em;
    }
    
    .metric-label {
        font-size: 13px;
        color: #94a3b8;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.05em;
    }
    
    /* Clean up default Streamlit elements */
    button[kind="header"] {
        display: none !important;
    }
    
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: transparent;
    }
    
    .stTabs [data-baseweb="tab"] {
        height: 44px;
        white-space: pre-wrap;
        background-color: #1f2937;
        border-radius: 8px;
        color: #94a3b8;
        border: 1px solid #374151;
        padding: 0 24px;
        font-weight: 500;
        font-size: 14px;
        transition: background-color 0.2s, color 0.2s, border-color 0.2s;
    }
    
    .stTabs [data-baseweb="tab"]:hover {
        background-color: #374151;
        color: #ffffff;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #06b6d4 0%, #3b82f6 100%) !important;
        color: #ffffff !important;
        border-color: transparent !important;
    }
</style>
""", unsafe_allow_html=True)

# Initialize service
service = BackendDataService()

# --- Data Caching helper ---
@st.cache_data(ttl=300)
def load_filters_data():
    """Fetches all filter options from Snowflake once and caches them."""
    try:
        states = service.get_distinct_states()
        categories = service.get_distinct_categories()
        payments = service.get_distinct_payment_types()
        min_date, max_date = service.get_date_range_bounds()
        return states, categories, payments, min_date, max_date
    except Exception as e:
        st.error(f"Failed to connect to Snowflake: {e}")
        return [], [], [], date(2016, 1, 1), date(2019, 12, 31)

# Load filter items
states_options, categories_options, payments_options, min_purchase_date, max_purchase_date = load_filters_data()

# --- Sidebar UI: Filters ---
st.sidebar.markdown("<h2 style='color: #06b6d4; font-weight: 700; margin-bottom: 2px;'>Olist Analytics</h2>", unsafe_allow_html=True)
st.sidebar.markdown("<p style='color: #64748b; font-size: 13px; margin-bottom: 24px;'>Interactive Filter Panel</p>", unsafe_allow_html=True)

# 1. Date Range Filter
st.sidebar.markdown("<label style='font-size: 13px; font-weight: 600; color: #94a3b8;'>ORDER PURCHASE DATE RANGE</label>", unsafe_allow_html=True)
if min_purchase_date and max_purchase_date:
    selected_date_range = st.sidebar.date_input(
        label="Date Range Select",
        value=(min_purchase_date, max_purchase_date),
        min_value=min_purchase_date,
        max_value=max_purchase_date,
        label_visibility="collapsed"
    )
else:
    selected_date_range = (date(2016, 1, 1), date(2019, 12, 31))

# Helper to format date selection
if isinstance(selected_date_range, tuple) and len(selected_date_range) == 2:
    start_date, end_date = selected_date_range
else:
    start_date, end_date = min_purchase_date, max_purchase_date

# 2. Customer State Filter
selected_states = st.sidebar.multiselect(
    label="CUSTOMER STATE",
    options=states_options,
    placeholder="All States"
)

# 3. Product Category Filter
selected_categories = st.sidebar.multiselect(
    label="PRODUCT CATEGORY",
    options=categories_options,
    placeholder="All Categories"
)

# 4. Payment Type Filter
selected_payments = st.sidebar.multiselect(
    label="PAYMENT TYPE",
    options=payments_options,
    placeholder="All Payment Types"
)

# Pack filters dictionary
filters = {
    "date_range": (start_date, end_date),
    "states": selected_states,
    "categories": selected_categories,
    "payment_types": selected_payments
}

# --- Main Dashboard Header ---
st.markdown("<h1 class='dashboard-title'>E-Commerce Analytics Platform</h1>", unsafe_allow_html=True)
st.markdown(f"<p class='dashboard-subtitle'>Olist Marketplace BI Dashboard | Active Filters: "
            f"Date Range {start_date} to {end_date} | "
            f"{len(selected_states) if selected_states else 'All'} States | "
            f"{len(selected_categories) if selected_categories else 'All'} Categories</p>", unsafe_allow_html=True)

# Fetch KPI Summary
with st.spinner("Fetching KPIs from Snowflake..."):
    kpi = service.get_kpi_summary(filters)

# Draw Executive KPI Cards
if kpi:
    cols = st.columns(5)
    
    # Card 1: Total Revenue
    with cols[0]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">${kpi.get('total_revenue', 0):,.2f}</div>
            <div class="metric-label">Total Revenue</div>
        </div>
        """, unsafe_allow_html=True)
        
    # Card 2: Total Orders
    with cols[1]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{kpi.get('total_orders', 0):,}</div>
            <div class="metric-label">Total Orders</div>
        </div>
        """, unsafe_allow_html=True)
        
    # Card 3: Total Customers
    with cols[2]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{kpi.get('total_customers', 0):,}</div>
            <div class="metric-label">Total Customers</div>
        </div>
        """, unsafe_allow_html=True)
        
    # Card 4: Avg Order Value
    with cols[3]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">${kpi.get('avg_order_value', 0):,.2f}</div>
            <div class="metric-label">Avg Order Value</div>
        </div>
        """, unsafe_allow_html=True)
        
    # Card 5: Total Sellers
    with cols[4]:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-value">{kpi.get('total_sellers', 0):,}</div>
            <div class="metric-label">Total Sellers</div>
        </div>
        """, unsafe_allow_html=True)

# --- Dashboard Navigation ---
st.sidebar.markdown("<br><label style='font-size: 13px; font-weight: 600; color: #94a3b8;'>NAVIGATION</label>", unsafe_allow_html=True)
selected_tab = st.sidebar.radio(
    label="Dashboard Navigation",
    options=[
        "📈 Executive Overview",
        "👥 Customer Segmentation (RFM & CLV)",
        "🔄 Cohort & Retention",
        "🗺️ Customer Geography",
        "💰 Revenue Analytics",
        "📦 Product Analytics",
        "🔗 Product Affinity",
        "🚚 Delivery & Operations",
        "🔮 Revenue Forecasting",
        "🤝 Seller Performance",
        "⭐ Review & Satisfaction",
        "📥 Report Center"
    ],
    label_visibility="collapsed"
)

# Global Plotly layout formatting for Dark Theme
def apply_dark_layout(fig):
    fig.update_layout(
        paper_bgcolor='rgba(0,0,0,0)',
        plot_bgcolor='rgba(0,0,0,0)',
        font_color='#94a3b8',
        font_family='Outfit',
        margin=dict(l=40, r=40, t=40, b=40),
        xaxis=dict(gridcolor='#1e293b', linecolor='#334155'),
        yaxis=dict(gridcolor='#1e293b', linecolor='#334155'),
        legend=dict(bgcolor='rgba(0,0,0,0)', bordercolor='rgba(0,0,0,0)')
    )
    return fig

# ----------------- Tab 1: Executive Overview -----------------
if selected_tab == "📈 Executive Overview":
    st.markdown("### High-Level Business Performance")
    
    # Fetch Revenue Trends & Top Products
    with st.spinner("Loading Executive Charts..."):
        rev_trends = service.get_revenue_trends(filters)
        top_cats = service.get_top_products(filters, limit=8)
        payment_dist = service.get_payment_type_distribution(filters)
        
    c1, c2 = st.columns([2, 1])
    
    with c1:
        st.markdown("#### Monthly Sales Performance")
        if rev_trends:
            df_trends = pd.DataFrame(rev_trends)
            # Combine Year and Month into string for X-axis
            df_trends["Period"] = df_trends["YEAR"].astype(str) + "-" + df_trends["MONTH"].astype(str).str.zfill(2)
            
            fig = px.line(
                df_trends, x="Period", y="REVENUE",
                title="Revenue Over Time ($)",
                labels={"REVENUE": "Revenue ($)", "Period": "Month"},
                markers=True,
                color_discrete_sequence=["#06b6d4"]
            )
            apply_dark_layout(fig)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No trend data matches the filter criteria.")
            
    with c2:
        st.markdown("#### Top Product Categories")
        if top_cats:
            df_cats = pd.DataFrame(top_cats)
            fig = px.bar(
                df_cats, x="REVENUE", y="CATEGORY",
                orientation='h',
                title="Revenue by Category ($)",
                labels={"REVENUE": "Revenue ($)", "CATEGORY": "Category"},
                color="REVENUE",
                color_continuous_scale="GnBu"
            )
            apply_dark_layout(fig)
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No category data matches the filter criteria.")

    # Row 2: Payment Distribution
    st.write("")
    st.markdown("#### Payment Types Contribution")
    if payment_dist:
        df_pay = pd.DataFrame(payment_dist)
        fig = px.pie(
            df_pay, names="PAYMENT_TYPE", values="REVENUE",
            hole=0.4,
            title="Revenue Contribution by Payment Method",
            color_discrete_sequence=px.colors.sequential.GnBu_r
        )
        apply_dark_layout(fig)
        st.plotly_chart(fig, use_container_width=True)

# ----------------- Tab 2: Customer Segmentation (RFM & CLV) -----------------
if selected_tab == "👥 Customer Segmentation (RFM & CLV)":
    st.markdown("### Customer Lifetime Value & RFM Segmentation")
    
    with st.spinner("Fetching customer segments..."):
        clv_data = service.get_clv_analytics(limit=10)
        rfm_data = service.get_rfm_segments()
        
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.markdown("#### RFM Customer Segments")
        if rfm_data:
            df_rfm = pd.DataFrame(rfm_data)
            fig = px.bar(
                df_rfm, x="SEGMENT", y="CUSTOMER_COUNT",
                title="Customer Distribution by RFM Segment",
                labels={"CUSTOMER_COUNT": "Customer Count", "SEGMENT": "Segment"},
                color="TOTAL_REVENUE",
                color_continuous_scale="Viridis"
            )
            apply_dark_layout(fig)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No RFM data available.")
            
    with c2:
        st.markdown("#### Customer Segment Value")
        if rfm_data:
            df_rfm = pd.DataFrame(rfm_data)
            fig = px.pie(
                df_rfm, names="SEGMENT", values="TOTAL_REVENUE",
                title="Revenue Share by Segment ($)",
                hole=0.4,
                color_discrete_sequence=px.colors.sequential.Plotly3
            )
            apply_dark_layout(fig)
            st.plotly_chart(fig, use_container_width=True)
            
    st.write("")
    st.markdown("#### Top Customer Lifetime Value (CLV) Rankings")
    if clv_data and clv_data.get("top_customers"):
        df_clv = pd.DataFrame(clv_data["top_customers"])
        st.dataframe(
            df_clv.rename(columns={
                "CUSTOMER_UNIQUE_ID": "Customer ID",
                "TOTAL_REVENUE": "Total Spent ($)",
                "TOTAL_ORDERS": "Orders Count",
                "AVG_ORDER_VALUE": "Avg Order Value ($)",
                "LIFETIME_DAYS": "Lifespan (Days)",
                "CLV_SCORE": "Projected CLV Score"
            }),
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning("No CLV data available.")

# ----------------- Tab 3: Cohort & Retention -----------------
if selected_tab == "🔄 Cohort & Retention":
    st.markdown("### Cohort Retention Analysis")
    st.write("Understand customer return rates based on their first purchase month cohort.")
    
    with st.spinner("Calculating cohort retention..."):
        cohort_data = service.get_cohort_retention()
        
    if cohort_data:
        df_cohort = pd.DataFrame(cohort_data)
        # Calculate retention percentage
        df_cohort['RETENTION_PCT'] = (df_cohort['ACTIVE_CUSTOMERS'] / df_cohort['COHORT_SIZE']) * 100
        
        # 1. Average Retention Line Chart
        st.markdown("#### Average Customer Retention Curve")
        # Exclude Month 0 (always 100%) for a better view of the drop-off
        df_avg = df_cohort[df_cohort['MONTH_INDEX'] > 0].groupby('MONTH_INDEX')['RETENTION_PCT'].mean().reset_index()
        df_avg['MONTH_LABEL'] = "M+" + df_avg['MONTH_INDEX'].astype(int).astype(str)
        
        fig_line = px.line(
            df_avg, x="MONTH_LABEL", y="RETENTION_PCT",
            title="Average Retention Rate After First Purchase",
            labels={"RETENTION_PCT": "Avg Retention (%)", "MONTH_LABEL": "Months Since First Purchase"},
            markers=True,
            line_shape="spline",
            color_discrete_sequence=["#f43f5e"]
        )
        apply_dark_layout(fig_line)
        st.plotly_chart(fig_line, use_container_width=True)
        
        # 2. Detailed Heatmap (Excluding M+0 to fix color scaling)
        st.markdown("#### Detailed Cohort Retention Matrix")
        st.write("*(Month 0 is excluded as it is always 100%, allowing colors to highlight actual return rates)*")
        
        df_filtered = df_cohort[df_cohort['MONTH_INDEX'] > 0]
        df_pivot = df_filtered.pivot(index='COHORT', columns='MONTH_INDEX', values='RETENTION_PCT')
        
        # Get sizes for Y-axis labels
        cohort_sizes = df_cohort[['COHORT', 'COHORT_SIZE']].drop_duplicates().set_index('COHORT')
        y_labels = [f"{idx} (N={cohort_sizes.loc[idx, 'COHORT_SIZE']:,})" for idx in df_pivot.index]
        
        # Renders a Plotly Heatmap
        fig_heat = go.Figure(data=go.Heatmap(
            z=df_pivot.values,
            x=[f"M+{int(col)}" for col in df_pivot.columns],
            y=y_labels,
            colorscale="Viridis",
            text=[[f"{val:.2f}%" if not pd.isna(val) else "" for val in row] for row in df_pivot.values],
            texttemplate="%{text}",
            showscale=True
        ))
        
        fig_heat.update_layout(
            xaxis_title="Months Since First Purchase",
            yaxis_title="First Purchase Cohort"
        )
        apply_dark_layout(fig_heat)
        st.plotly_chart(fig_heat, use_container_width=True)
    else:
        st.warning("No cohort retention data available.")

# ----------------- Tab 4: Customer Geography -----------------
if selected_tab == "🗺️ Customer Geography":
    st.markdown("### Customer Behavior & Geography")
    
    with st.spinner("Loading Customer Geography..."):
        state_dist = service.get_state_distribution(filters)
        
    c1, c2 = st.columns([1, 1])
    
    with c1:
        st.markdown("#### Customer Orders by State")
        if state_dist:
            df_state = pd.DataFrame(state_dist)
            fig = px.bar(
                df_state, x="STATE", y="ORDERS",
                title="Orders Count by Customer State",
                labels={"ORDERS": "Orders", "STATE": "State"},
                color="ORDERS",
                color_continuous_scale="Blues"
            )
            apply_dark_layout(fig)
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No state distribution data matches filters.")
            
    with c2:
        st.markdown("#### Customer Revenue by State")
        if state_dist:
            df_state = pd.DataFrame(state_dist)
            fig = px.pie(
                df_state, names="STATE", values="REVENUE",
                title="Revenue Share by Customer State",
                color_discrete_sequence=px.colors.sequential.GnBu_r
            )
            apply_dark_layout(fig)
            st.plotly_chart(fig, use_container_width=True)

# ----------------- Tab 5: Revenue Analytics -----------------
if selected_tab == "💰 Revenue Analytics":
    st.markdown("### Revenue Growth & Details")
    
    with st.spinner("Loading Revenue Data..."):
        rev_trends = service.get_revenue_trends(filters)
    
    if rev_trends:
        df_rev = pd.DataFrame(rev_trends)
        df_rev["Period"] = df_rev["YEAR"].astype(str) + "-" + df_rev["MONTH"].astype(str).str.zfill(2)
        
        # Dual axis: Revenue & Orders
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df_rev["Period"], y=df_rev["REVENUE"],
            name="Revenue ($)",
            mode="lines+markers",
            line=dict(color="#06b6d4", width=3)
        ))
        fig.add_trace(go.Bar(
            x=df_rev["Period"], y=df_rev["ORDERS"],
            name="Orders Count",
            yaxis="y2",
            marker=dict(color="rgba(59, 130, 246, 0.3)")
        ))
        
        fig.update_layout(
            title="Revenue vs Orders Volume Trend",
            yaxis=dict(title="Revenue ($)"),
            yaxis2=dict(title="Orders Count", overlaying="y", side="right"),
            legend=dict(x=0.01, y=0.99)
        )
        apply_dark_layout(fig)
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No revenue analytics available for selected filters.")

# ----------------- Tab 6: Product Analytics -----------------
if selected_tab == "📦 Product Analytics":
    st.markdown("### Product & Category Contribution")
    
    with st.spinner("Loading Product Data..."):
        top_cats = service.get_top_products(filters, limit=8)
    
    if top_cats:
        df_prod = pd.DataFrame(top_cats)
        
        c1, c2 = st.columns([1, 1])
        with c1:
            st.markdown("#### Top Categories by Units Sold")
            fig = px.bar(
                df_prod, x="CATEGORY", y="UNITS_SOLD",
                title="Units Sold per Category",
                color="UNITS_SOLD",
                color_continuous_scale="Teal"
            )
            apply_dark_layout(fig)
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.markdown("#### Category List Details")
            st.dataframe(
                df_prod.rename(columns={
                    "CATEGORY": "Category Name",
                    "UNITS_SOLD": "Items Sold",
                    "REVENUE": "Revenue Generated ($)"
                }),
                hide_index=True,
                use_container_width=True
            )
    else:
        st.warning("No product data available.")

# ----------------- Tab 7: Product Affinity -----------------
if selected_tab == "🔗 Product Affinity":
    st.markdown("### Product Affinity & Association Analytics (Market Basket)")
    st.write("Identifies product categories frequently bought together in a single transaction.")
    
    with st.spinner("Analyzing market basket data..."):
        affinity_data = service.get_product_affinity(limit=15)
        
    if affinity_data:
        df_aff = pd.DataFrame(affinity_data)
        df_aff["Product Combo"] = df_aff["CATEGORY_A"] + " + " + df_aff["CATEGORY_B"]
        
        fig = px.bar(
            df_aff, x="CO_PURCHASE_COUNT", y="Product Combo",
            orientation='h',
            title="Top Product Category Co-Purchase Combinations",
            labels={"CO_PURCHASE_COUNT": "Co-Purchase Orders", "Product Combo": "Combo Pair"},
            color="CO_PURCHASE_COUNT",
            color_continuous_scale="Purples"
        )
        apply_dark_layout(fig)
        fig.update_layout(coloraxis_showscale=False)
        st.plotly_chart(fig, use_container_width=True)
        
        st.dataframe(
            df_aff.rename(columns={
                "CATEGORY_A": "Category A",
                "CATEGORY_B": "Category B",
                "CO_PURCHASE_COUNT": "Shared Orders Count"
            })[["Category A", "Category B", "Shared Orders Count"]],
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning("No product affinity combinations found in the current datasets.")

# ----------------- Tab 8: Delivery & Operations -----------------
if selected_tab == "🚚 Delivery & Operations":
    st.markdown("### Delivery Operations & Logistical Performance")
    
    with st.spinner("Analyzing delivery performance..."):
        deliv_data = service.get_delivery_performance()
        
    if deliv_data:
        df_deliv = pd.DataFrame(deliv_data)
        
        c1, c2 = st.columns([1, 1])
        
        with c1:
            st.markdown("#### Average Delivery Days by Customer State")
            df_deliv_sorted = df_deliv.sort_values(by="AVG_DELIVERY_DAYS")
            fig = px.bar(
                df_deliv_sorted, x="STATE", y="AVG_DELIVERY_DAYS",
                title="Average Logistical Latency (Purchase to Delivery)",
                labels={"AVG_DELIVERY_DAYS": "Average Days", "STATE": "State"},
                color="AVG_DELIVERY_DAYS",
                color_continuous_scale="Oranges"
            )
            apply_dark_layout(fig)
            fig.update_layout(coloraxis_showscale=False)
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.markdown("#### Operational Summary")
            df_deliv['DELAY_RATE_PCT'] = (df_deliv['DELAYED_COUNT'] / df_deliv['TOTAL_ORDERS']) * 100
            st.dataframe(
                df_deliv.rename(columns={
                    "STATE": "State",
                    "AVG_DELIVERY_DAYS": "Avg In-Transit Days",
                    "AVG_EARLY_DAYS": "Avg Days Early vs Est",
                    "DELAYED_COUNT": "Delayed Orders",
                    "TOTAL_ORDERS": "Total Deliveries",
                    "DELAY_RATE_PCT": "Delay Rate (%)"
                }),
                column_config={
                    "Avg In-Transit Days": st.column_config.NumberColumn(format="%.1f days"),
                    "Avg Days Early vs Est": st.column_config.NumberColumn(format="%.1f days"),
                    "Delay Rate (%)": st.column_config.NumberColumn(format="%.1f%%"),
                    "Total Deliveries": st.column_config.NumberColumn(format="%d")
                },
                hide_index=True,
                use_container_width=True
            )
    else:
        st.warning("No operational delivery data available.")

# ----------------- Tab 9: Revenue Forecasting -----------------
if selected_tab == "🔮 Revenue Forecasting":
    st.markdown("### Predictive Revenue Forecasting")
    st.write("Calculates future monthly revenue using Linear Trend Regression and a 3-Month Moving Average.")
    
    with st.spinner("Running forecasting models..."):
        forecast_data = service.get_revenue_forecast(months_to_forecast=6)
        
    if forecast_data and forecast_data.get("historical"):
        hist_df = pd.DataFrame(forecast_data["historical"])
        fore_df = pd.DataFrame(forecast_data["forecast"])
        
        fig = go.Figure()
        
        # Historical Actuals
        fig.add_trace(go.Scatter(
            x=hist_df["DATE_STR"], y=hist_df["REVENUE"],
            name="Historical Revenue (Actual)",
            mode="lines+markers",
            line=dict(color="#06b6d4", width=3)
        ))
        
        # Connect last actual with forecast values
        conn_x = [hist_df.iloc[-1]["DATE_STR"]] + list(fore_df["DATE_STR"])
        conn_y_reg = [hist_df.iloc[-1]["REVENUE"]] + list(fore_df["FORECAST_REGRESSION"])
        conn_y_ma = [hist_df.iloc[-1]["REVENUE"]] + list(fore_df["FORECAST_MA"])
        
        fig.add_trace(go.Scatter(
            x=conn_x, y=conn_y_reg,
            name="Linear Trend Forecast",
            mode="lines+markers",
            line=dict(color="#fbbf24", width=2, dash="dash")
        ))
        
        fig.add_trace(go.Scatter(
            x=conn_x, y=conn_y_ma,
            name="Moving Average Forecast",
            mode="lines+markers",
            line=dict(color="#10b981", width=2, dash="dot")
        ))
        
        fig.update_layout(
            title="6-Month Revenue Forecast Chart ($)",
            xaxis_title="Reporting Period",
            yaxis_title="Revenue ($)"
        )
        apply_dark_layout(fig)
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("#### Projected Revenue Values Table")
        st.dataframe(
            fore_df.rename(columns={
                "DATE_STR": "Forecast Period",
                "FORECAST_REGRESSION": "Linear Trend Estimate ($)",
                "FORECAST_MA": "Moving Average Estimate ($)"
            })[["Forecast Period", "Linear Trend Estimate ($)", "Moving Average Estimate ($)"]],
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning("Insufficient historical trends to compute forecasting.")

# ----------------- Tab 10: Seller Performance -----------------
if selected_tab == "🤝 Seller Performance":
    st.markdown("### Seller Performance Rankings")
    
    with st.spinner("Fetching Seller Leaderboard..."):
        top_sellers = service.get_top_sellers(filters, limit=10)
        
    if top_sellers:
        df_sellers = pd.DataFrame(top_sellers)
        
        fig = px.bar(
            df_sellers, x="REVENUE", y="SELLER_ID",
            orientation='h',
            title="Top 10 Sellers by Revenue Contribution ($)",
            labels={"REVENUE": "Revenue ($)", "SELLER_ID": "Seller ID"},
            color="ITEMS_SOLD",
            color_continuous_scale="Mint"
        )
        apply_dark_layout(fig)
        st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("#### Seller Performance Summary")
        st.dataframe(
            df_sellers.rename(columns={
                "SELLER_ID": "Seller Identifier",
                "SELLER_STATE": "State",
                "REVENUE": "Total Revenue ($)",
                "ITEMS_SOLD": "Items Shipped"
            }),
            hide_index=True,
            use_container_width=True
        )
    else:
        st.warning("No seller data matches active filters.")

# ----------------- Tab 11: Review & Satisfaction -----------------
if selected_tab == "⭐ Review & Satisfaction":
    st.markdown("### Customer Satisfaction & Feedback")
    
    with st.spinner("Fetching customer reviews..."):
        review_dist = service.get_review_distribution(filters)
        
    if review_dist:
        df_revs = pd.DataFrame(review_dist)
        
        # Calculate positive review score pct (4 & 5 stars)
        tot_reviews = df_revs["REVIEW_COUNT"].sum()
        pos_reviews = df_revs[df_revs["REVIEW_SCORE"] >= 4]["REVIEW_COUNT"].sum()
        pos_pct = (pos_reviews / tot_reviews) * 100 if tot_reviews > 0 else 0
        
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.markdown("#### CSAT Score Card")
            st.markdown(f"""
            <div class="metric-card" style="margin-top: 24px;">
                <div class="metric-value" style="color: #10b981;">{pos_pct:.1f}%</div>
                <div class="metric-label">CSAT Rating (4-5 ★)</div>
            </div>
            """, unsafe_allow_html=True)
            
            avg_score = kpi.get("avg_review_score", 0.0)
            st.markdown(f"""
            <div class="metric-card" style="margin-top: 16px;">
                <div class="metric-value" style="color: #f59e0b;">{avg_score:.2f} / 5.0</div>
                <div class="metric-label">Average Review Score</div>
            </div>
            """, unsafe_allow_html=True)
            
        with col2:
            st.markdown("#### Review Rating Count Distribution")
            fig = px.bar(
                df_revs, x="REVIEW_SCORE", y="REVIEW_COUNT",
                title="Review Counts per Rating Score (1 to 5 Stars)",
                labels={"REVIEW_COUNT": "Number of Reviews", "REVIEW_SCORE": "Rating Score"},
                color="REVIEW_SCORE",
                color_discrete_sequence=["#10b981", "#34d399", "#fbbf24", "#f87171", "#ef4444"]
            )
            apply_dark_layout(fig)
            fig.update_layout(showlegend=False)
            st.plotly_chart(fig, use_container_width=True)
    else:
        st.warning("No review data matches filters.")

# ----------------- Tab 12: Report Center -----------------
if selected_tab == "📥 Report Center":
    st.markdown("### Export Analytical Datasets")
    st.write("Generate and download filtered database datasets directly from Snowflake to your local machine.")
    
    report_options = {
        "kpi_summary": "KPI Summary Metrics",
        "revenue_trends": "Monthly Revenue Trends",
        "state_distribution": "State Revenue & Order breakdown",
        "top_products": "Top Product Categories",
        "top_sellers": "Top Marketplace Sellers Performance",
        "review_distribution": "Customer Review Scores Distribution",
        "payment_type_distribution": "Payment Types Contributions"
    }
    
    selected_report_type = st.selectbox(
        "Choose Report to Export",
        options=list(report_options.keys()),
        format_func=lambda x: report_options[x]
    )
    
    if st.button("Generate & Download Report"):
        with st.spinner("Extracting filtered dataset from Snowflake..."):
            try:
                file_name = f"{selected_report_type}_{int(datetime.now().timestamp())}.csv"
                file_path = f"reports/{file_name}"
                service.export_report(selected_report_type, file_path, filters)
                
                df_download = pd.read_csv(file_path)
                csv_bytes = df_download.to_csv(index=False).encode('utf-8')
                
                st.success(f"Report successfully generated!")
                st.download_button(
                    label="📥 Click Here to Download CSV",
                    data=csv_bytes,
                    file_name=file_name,
                    mime="text/csv"
                )
            except Exception as e:
                st.error(f"Failed to export report: {e}")


