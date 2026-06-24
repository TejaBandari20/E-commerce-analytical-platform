import os
import logging
import pandas as pd
from etl.load import get_snowflake_connection  # type: ignore

logger = logging.getLogger(__name__)

class BackendDataService:
    def __init__(self):
        """Initializes the backend data service using Snowflake credentials."""
        self.database = os.getenv("SNOWFLAKE_DATABASE")
        self.schema = os.getenv("SNOWFLAKE_SCHEMA")

    def _execute_query(self, query: str) -> pd.DataFrame:
        """Executes a SQL query in Snowflake and returns a Pandas DataFrame."""
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        try:
            # Enforce database and schema selection
            cursor.execute(f"USE DATABASE {self.database};")
            cursor.execute(f"USE SCHEMA {self.schema};")
            cursor.execute(query)
            # Retrieve columns and data
            columns = [col[0] for col in cursor.description]
            data = cursor.fetchall()
            return pd.DataFrame(data, columns=columns)
        except Exception as e:
            logger.error(f"Failed to execute query: {query}. Error: {e}")
            raise e
        finally:
            cursor.close()
            conn.close()

    def _build_where_clause(self, filters: dict = None) -> str:
        """Helper to build a SQL WHERE clause from user-selected filters."""
        if not filters:
            return "1=1"
            
        clauses = []
        
        # 1. Date Range Filter
        date_range = filters.get("date_range")
        if date_range and len(date_range) == 2:
            start_date, end_date = date_range
            clauses.append(f"TO_DATE(o.ORDER_PURCHASE_TIMESTAMP) BETWEEN '{start_date}' AND '{end_date}'")
            
        # 2. State Filter
        states = filters.get("states")
        if states:
            state_list = ", ".join([f"'{s}'" for s in states])
            clauses.append(f"c.CUSTOMER_STATE IN ({state_list})")
            
        # 3. Product Category Filter
        categories = filters.get("categories")
        if categories:
            cat_list = ", ".join([f"'{c}'" for c in categories])
            clauses.append(f"prod.PRODUCT_CATEGORY_NAME IN ({cat_list})")
            
        # 4. Payment Type Filter
        payment_types = filters.get("payment_types")
        if payment_types:
            pay_list = ", ".join([f"'{p}'" for p in payment_types])
            clauses.append(f"p.PAYMENT_TYPE IN ({pay_list})")
            
        if clauses:
            return " AND ".join(clauses)
        return "1=1"

    # --- Distinct Lookups for Filters ---

    def get_distinct_states(self) -> list:
        """Fetches distinct customer states for filter selection."""
        query = "SELECT DISTINCT CUSTOMER_STATE FROM DIM_CUSTOMERS WHERE CUSTOMER_STATE IS NOT NULL ORDER BY CUSTOMER_STATE"
        df = self._execute_query(query)
        return df["CUSTOMER_STATE"].tolist()

    def get_distinct_categories(self) -> list:
        """Fetches distinct product category names for filter selection."""
        query = "SELECT DISTINCT PRODUCT_CATEGORY_NAME FROM DIM_PRODUCTS WHERE PRODUCT_CATEGORY_NAME IS NOT NULL ORDER BY PRODUCT_CATEGORY_NAME"
        df = self._execute_query(query)
        return df["PRODUCT_CATEGORY_NAME"].tolist()

    def get_distinct_payment_types(self) -> list:
        """Fetches distinct payment types for filter selection."""
        query = "SELECT DISTINCT PAYMENT_TYPE FROM FACT_PAYMENTS WHERE PAYMENT_TYPE IS NOT NULL ORDER BY PAYMENT_TYPE"
        df = self._execute_query(query)
        return df["PAYMENT_TYPE"].tolist()

    def get_date_range_bounds(self) -> tuple:
        """Fetches the min and max purchase timestamps in the order fact table."""
        query = "SELECT MIN(ORDER_PURCHASE_TIMESTAMP) AS MIN_DATE, MAX(ORDER_PURCHASE_TIMESTAMP) AS MAX_DATE FROM FACT_ORDERS"
        df = self._execute_query(query)
        if not df.empty:
            row = df.iloc[0]
            min_date = pd.to_datetime(row["MIN_DATE"]).date()
            max_date = pd.to_datetime(row["MAX_DATE"]).date()
            return min_date, max_date
        return None, None

    # --- Filter-Aware Analytical Queries ---

    def get_kpi_summary(self, filters: dict = None) -> dict:
        """Retrieves general warehouse KPI metrics."""
        where_clause = self._build_where_clause(filters)
        
        query = f"""
        SELECT
            COUNT(DISTINCT o.CUSTOMER_ID) AS TOTAL_CUSTOMERS,
            COUNT(DISTINCT o.ORDER_ID) AS TOTAL_ORDERS,
            COALESCE(SUM(p.PAYMENT_VALUE), 0) AS TOTAL_REVENUE,
            COALESCE(AVG(r.REVIEW_SCORE), 0) AS AVG_REVIEW_SCORE,
            COUNT(DISTINCT i.SELLER_ID) AS TOTAL_SELLERS
        FROM FACT_ORDERS o
        LEFT JOIN DIM_CUSTOMERS c ON o.CUSTOMER_ID = c.CUSTOMER_ID
        LEFT JOIN FACT_PAYMENTS p ON o.ORDER_ID = p.ORDER_ID
        LEFT JOIN FACT_REVIEWS r ON o.ORDER_ID = r.ORDER_ID
        LEFT JOIN FACT_ORDER_ITEMS i ON o.ORDER_ID = i.ORDER_ID
        LEFT JOIN DIM_PRODUCTS prod ON i.PRODUCT_ID = prod.PRODUCT_ID
        WHERE {where_clause}
        """
        logger.info("Fetching KPI summary...")
        df = self._execute_query(query)
        if not df.empty:
            row = df.iloc[0]
            orders = int(row["TOTAL_ORDERS"])
            revenue = float(row["TOTAL_REVENUE"])
            aov = revenue / orders if orders > 0 else 0.0
            return {
                "total_customers": int(row["TOTAL_CUSTOMERS"]),
                "total_orders": orders,
                "total_revenue": revenue,
                "avg_review_score": round(float(row["AVG_REVIEW_SCORE"]), 2),
                "avg_order_value": round(aov, 2),
                "total_sellers": int(row["TOTAL_SELLERS"])
            }
        return {}

    def get_revenue_trends(self, filters: dict = None) -> list:
        """Retrieves monthly revenue trends for charting."""
        where_clause = self._build_where_clause(filters)
        
        query = f"""
        SELECT
            d.YEAR,
            d.MONTH,
            COALESCE(SUM(p.PAYMENT_VALUE), 0) AS REVENUE,
            COUNT(DISTINCT o.ORDER_ID) AS ORDERS
        FROM FACT_ORDERS o
        JOIN DIM_DATE d ON TO_DATE(o.ORDER_PURCHASE_TIMESTAMP) = d.FULL_DATE
        LEFT JOIN DIM_CUSTOMERS c ON o.CUSTOMER_ID = c.CUSTOMER_ID
        LEFT JOIN FACT_PAYMENTS p ON o.ORDER_ID = p.ORDER_ID
        LEFT JOIN FACT_ORDER_ITEMS i ON o.ORDER_ID = i.ORDER_ID
        LEFT JOIN DIM_PRODUCTS prod ON i.PRODUCT_ID = prod.PRODUCT_ID
        WHERE {where_clause}
        GROUP BY d.YEAR, d.MONTH
        ORDER BY d.YEAR ASC, d.MONTH ASC
        """
        logger.info("Fetching revenue trends...")
        df = self._execute_query(query)
        return df.to_dict(orient="records")

    def get_state_distribution(self, filters: dict = None) -> list:
        """Retrieves customer state-level distribution of orders and revenue."""
        where_clause = self._build_where_clause(filters)
        
        query = f"""
        SELECT
            c.CUSTOMER_STATE AS STATE,
            COALESCE(SUM(p.PAYMENT_VALUE), 0) AS REVENUE,
            COUNT(DISTINCT o.ORDER_ID) AS ORDERS
        FROM FACT_ORDERS o
        LEFT JOIN DIM_CUSTOMERS c ON o.CUSTOMER_ID = c.CUSTOMER_ID
        LEFT JOIN FACT_PAYMENTS p ON o.ORDER_ID = p.ORDER_ID
        LEFT JOIN FACT_ORDER_ITEMS i ON o.ORDER_ID = i.ORDER_ID
        LEFT JOIN DIM_PRODUCTS prod ON i.PRODUCT_ID = prod.PRODUCT_ID
        WHERE {where_clause}
        GROUP BY c.CUSTOMER_STATE
        ORDER BY REVENUE DESC
        """
        logger.info("Fetching state distribution...")
        df = self._execute_query(query)
        return df.to_dict(orient="records")

    def get_top_products(self, filters: dict = None, limit: int = 10) -> list:
        """Retrieves the top product categories by units sold and revenue."""
        where_clause = self._build_where_clause(filters)
        
        query = f"""
        SELECT
            prod.PRODUCT_CATEGORY_NAME AS CATEGORY,
            COUNT(i.ORDER_ITEM_ID) AS UNITS_SOLD,
            COALESCE(SUM(i.PRICE), 0) AS REVENUE
        FROM FACT_ORDER_ITEMS i
        LEFT JOIN FACT_ORDERS o ON i.ORDER_ID = o.ORDER_ID
        LEFT JOIN DIM_CUSTOMERS c ON o.CUSTOMER_ID = c.CUSTOMER_ID
        LEFT JOIN FACT_PAYMENTS p ON o.ORDER_ID = p.ORDER_ID
        LEFT JOIN FACT_REVIEWS r ON o.ORDER_ID = r.ORDER_ID
        LEFT JOIN DIM_PRODUCTS prod ON i.PRODUCT_ID = prod.PRODUCT_ID
        WHERE {where_clause} AND prod.PRODUCT_CATEGORY_NAME IS NOT NULL
        GROUP BY prod.PRODUCT_CATEGORY_NAME
        ORDER BY REVENUE DESC
        LIMIT {limit}
        """
        logger.info(f"Fetching top {limit} products...")
        df = self._execute_query(query)
        return df.to_dict(orient="records")

    def get_top_sellers(self, filters: dict = None, limit: int = 10) -> list:
        """Retrieves the top sellers by revenue."""
        where_clause = self._build_where_clause(filters)
        
        query = f"""
        SELECT
            i.SELLER_ID,
            s.SELLER_STATE,
            COALESCE(SUM(i.PRICE), 0) AS REVENUE,
            COUNT(i.ORDER_ITEM_ID) AS ITEMS_SOLD
        FROM FACT_ORDER_ITEMS i
        LEFT JOIN DIM_SELLERS s ON i.SELLER_ID = s.SELLER_ID
        LEFT JOIN FACT_ORDERS o ON i.ORDER_ID = o.ORDER_ID
        LEFT JOIN DIM_CUSTOMERS c ON o.CUSTOMER_ID = c.CUSTOMER_ID
        LEFT JOIN FACT_PAYMENTS p ON o.ORDER_ID = p.ORDER_ID
        LEFT JOIN FACT_REVIEWS r ON o.ORDER_ID = r.ORDER_ID
        LEFT JOIN DIM_PRODUCTS prod ON i.PRODUCT_ID = prod.PRODUCT_ID
        WHERE {where_clause}
        GROUP BY i.SELLER_ID, s.SELLER_STATE
        ORDER BY REVENUE DESC
        LIMIT {limit}
        """
        logger.info(f"Fetching top {limit} sellers...")
        df = self._execute_query(query)
        return df.to_dict(orient="records")

    def get_review_distribution(self, filters: dict = None) -> list:
        """Retrieves satisfaction score distribution (1 to 5 stars)."""
        where_clause = self._build_where_clause(filters)
        
        query = f"""
        SELECT
            r.REVIEW_SCORE,
            COUNT(*) AS REVIEW_COUNT
        FROM FACT_REVIEWS r
        LEFT JOIN FACT_ORDERS o ON r.ORDER_ID = o.ORDER_ID
        LEFT JOIN DIM_CUSTOMERS c ON o.CUSTOMER_ID = c.CUSTOMER_ID
        LEFT JOIN FACT_PAYMENTS p ON o.ORDER_ID = p.ORDER_ID
        LEFT JOIN FACT_ORDER_ITEMS i ON o.ORDER_ID = i.ORDER_ID
        LEFT JOIN DIM_PRODUCTS prod ON i.PRODUCT_ID = prod.PRODUCT_ID
        WHERE {where_clause} AND r.REVIEW_SCORE IS NOT NULL
        GROUP BY r.REVIEW_SCORE
        ORDER BY r.REVIEW_SCORE DESC
        """
        logger.info("Fetching review distribution...")
        df = self._execute_query(query)
        return df.to_dict(orient="records")

    def get_payment_type_distribution(self, filters: dict = None) -> list:
        """Retrieves payment type distribution for charting."""
        where_clause = self._build_where_clause(filters)
        
        query = f"""
        SELECT
            p.PAYMENT_TYPE,
            COALESCE(SUM(p.PAYMENT_VALUE), 0) AS REVENUE,
            COUNT(DISTINCT o.ORDER_ID) AS ORDERS
        FROM FACT_PAYMENTS p
        LEFT JOIN FACT_ORDERS o ON p.ORDER_ID = o.ORDER_ID
        LEFT JOIN DIM_CUSTOMERS c ON o.CUSTOMER_ID = c.CUSTOMER_ID
        LEFT JOIN FACT_ORDER_ITEMS i ON o.ORDER_ID = i.ORDER_ID
        LEFT JOIN DIM_PRODUCTS prod ON i.PRODUCT_ID = prod.PRODUCT_ID
        WHERE {where_clause} AND p.PAYMENT_TYPE IS NOT NULL
        GROUP BY p.PAYMENT_TYPE
        ORDER BY REVENUE DESC
        """
        logger.info("Fetching payment type distribution...")
        df = self._execute_query(query)
        return df.to_dict(orient="records")

    def refresh_analytics_summary(self) -> str:
        """Triggers the Snowflake stored procedure to refresh reporting tables."""
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(f"USE DATABASE {self.database};")
            cursor.execute(f"USE SCHEMA {self.schema};")
            logger.info("Calling REFRESH_ALL_ANALYTICS stored procedure...")
            cursor.execute("CALL REFRESH_ALL_ANALYTICS();")
            result = cursor.fetchone()[0]
            return result
        except Exception as e:
            logger.error(f"Failed to refresh analytics summary: {e}")
            raise e
        finally:
            cursor.close()
            conn.close()

    def get_clv_analytics(self, limit: int = 10) -> dict:
        """Retrieves customer lifetime value ranking and overall metrics."""
        top_query = f"""
        SELECT CUSTOMER_UNIQUE_ID, TOTAL_REVENUE, TOTAL_ORDERS, AVG_ORDER_VALUE, LIFETIME_DAYS, CLV_SCORE
        FROM CUSTOMER_CLV_SUMMARY
        ORDER BY CLV_SCORE DESC
        LIMIT {limit}
        """
        top_df = self._execute_query(top_query)
        
        dist_query = """
        SELECT 
            MIN(CLV_SCORE) AS MIN_CLV,
            MAX(CLV_SCORE) AS MAX_CLV,
            AVG(CLV_SCORE) AS AVG_CLV,
            COUNT(*) AS TOTAL_CUSTOMERS
        FROM CUSTOMER_CLV_SUMMARY
        """
        dist_df = self._execute_query(dist_query)
        stats = dist_df.to_dict(orient="records")[0] if not dist_df.empty else {}
        
        return {
            "top_customers": top_df.to_dict(orient="records"),
            "stats": stats
        }

    def get_rfm_segments(self) -> list:
        """Retrieves RFM customer segment distribution counts and revenue contribution."""
        query = """
        SELECT 
            SEGMENT,
            COUNT(*) AS CUSTOMER_COUNT,
            SUM(MONETARY) AS TOTAL_REVENUE,
            AVG(RECENCY_DAYS) AS AVG_RECENCY,
            AVG(FREQUENCY) AS AVG_FREQUENCY
        FROM CUSTOMER_RFM_SEGMENTS
        GROUP BY SEGMENT
        ORDER BY CUSTOMER_COUNT DESC
        """
        df = self._execute_query(query)
        return df.to_dict(orient="records")

    def get_cohort_retention(self) -> list:
        """Generates cohort retention analysis matrix dataset."""
        query = """
        WITH CustomerCohort AS (
            SELECT
                c.CUSTOMER_UNIQUE_ID,
                MIN(DATE_TRUNC('month', TO_DATE(o.ORDER_PURCHASE_TIMESTAMP))) AS COHORT_MONTH
            FROM DIM_CUSTOMERS c
            JOIN FACT_ORDERS o ON c.CUSTOMER_ID = o.CUSTOMER_ID
            GROUP BY c.CUSTOMER_UNIQUE_ID
        ),
        OrderMonths AS (
            SELECT DISTINCT
                c.CUSTOMER_UNIQUE_ID,
                DATE_TRUNC('month', TO_DATE(o.ORDER_PURCHASE_TIMESTAMP)) AS ORDER_MONTH
            FROM DIM_CUSTOMERS c
            JOIN FACT_ORDERS o ON c.CUSTOMER_ID = o.CUSTOMER_ID
        ),
        CohortPeriods AS (
            SELECT
                cc.CUSTOMER_UNIQUE_ID,
                cc.COHORT_MONTH,
                om.ORDER_MONTH,
                DATEDIFF('month', cc.COHORT_MONTH, om.ORDER_MONTH) AS MONTH_INDEX
            FROM CustomerCohort cc
            JOIN OrderMonths om ON cc.CUSTOMER_UNIQUE_ID = om.CUSTOMER_UNIQUE_ID
        ),
        CohortSizes AS (
            SELECT
                COHORT_MONTH,
                COUNT(DISTINCT CUSTOMER_UNIQUE_ID) AS COHORT_SIZE
            FROM CustomerCohort
            GROUP BY COHORT_MONTH
        )
        SELECT
            TO_VARCHAR(cp.COHORT_MONTH, 'YYYY-MM') AS COHORT,
            cp.MONTH_INDEX,
            COUNT(DISTINCT cp.CUSTOMER_UNIQUE_ID) AS ACTIVE_CUSTOMERS,
            cs.COHORT_SIZE
        FROM CohortPeriods cp
        JOIN CohortSizes cs ON cp.COHORT_MONTH = cs.COHORT_MONTH
        WHERE cp.MONTH_INDEX BETWEEN 0 AND 12
        GROUP BY cp.COHORT_MONTH, cp.MONTH_INDEX, cs.COHORT_SIZE
        ORDER BY COHORT, MONTH_INDEX
        """
        df = self._execute_query(query)
        return df.to_dict(orient="records")

    def get_product_affinity(self, limit: int = 15) -> list:
        """Retrieves products frequently bought together (Market Basket analysis)."""
        query = f"""
        SELECT 
            p1.PRODUCT_CATEGORY_NAME AS CATEGORY_A,
            p2.PRODUCT_CATEGORY_NAME AS CATEGORY_B,
            COUNT(DISTINCT i1.ORDER_ID) AS CO_PURCHASE_COUNT
        FROM FACT_ORDER_ITEMS i1
        JOIN FACT_ORDER_ITEMS i2 ON i1.ORDER_ID = i2.ORDER_ID AND i1.PRODUCT_ID < i2.PRODUCT_ID
        JOIN DIM_PRODUCTS p1 ON i1.PRODUCT_ID = p1.PRODUCT_ID
        JOIN DIM_PRODUCTS p2 ON i2.PRODUCT_ID = p2.PRODUCT_ID
        WHERE p1.PRODUCT_CATEGORY_NAME IS NOT NULL 
          AND p2.PRODUCT_CATEGORY_NAME IS NOT NULL 
          AND p1.PRODUCT_CATEGORY_NAME != p2.PRODUCT_CATEGORY_NAME
        GROUP BY CATEGORY_A, CATEGORY_B
        ORDER BY CO_PURCHASE_COUNT DESC
        LIMIT {limit}
        """
        df = self._execute_query(query)
        return df.to_dict(orient="records")

    def get_delivery_performance(self) -> list:
        """Retrieves delivery times and delay frequencies by customer state."""
        query = """
        SELECT
            c.CUSTOMER_STATE AS STATE,
            AVG(DATEDIFF(day, TO_TIMESTAMP(o.ORDER_PURCHASE_TIMESTAMP), TO_TIMESTAMP(o.ORDER_DELIVERED_CUSTOMER_DATE))) AS AVG_DELIVERY_DAYS,
            AVG(DATEDIFF(day, TO_TIMESTAMP(o.ORDER_DELIVERED_CUSTOMER_DATE), TO_TIMESTAMP(o.ORDER_ESTIMATED_DELIVERY_DATE))) AS AVG_EARLY_DAYS,
            SUM(CASE WHEN o.ORDER_DELIVERED_CUSTOMER_DATE > o.ORDER_ESTIMATED_DELIVERY_DATE THEN 1 ELSE 0 END) AS DELAYED_COUNT,
            COUNT(*) AS TOTAL_ORDERS
        FROM FACT_ORDERS o
        JOIN DIM_CUSTOMERS c ON o.CUSTOMER_ID = c.CUSTOMER_ID
        WHERE o.ORDER_DELIVERED_CUSTOMER_DATE IS NOT NULL
          AND o.ORDER_ESTIMATED_DELIVERY_DATE IS NOT NULL
        GROUP BY c.CUSTOMER_STATE
        ORDER BY AVG_DELIVERY_DAYS DESC
        """
        df = self._execute_query(query)
        return df.to_dict(orient="records")

    def get_revenue_forecast(self, months_to_forecast: int = 6) -> dict:
        """Forecasts next months' revenue using trend linear regression and moving average."""
        trends = self.get_revenue_trends()
        trends_df = pd.DataFrame(trends)
        if trends_df.empty or len(trends_df) < 3:
            return {"historical": [], "forecast": []}
        
        trends_df['DATE_STR'] = trends_df.apply(lambda r: f"{int(r['YEAR'])}-{int(r['MONTH']):02d}", axis=1)
        trends_df['MONTH_INDEX'] = range(len(trends_df))
        
        # Linear Regression calculations
        x = trends_df['MONTH_INDEX'].values
        y = trends_df['REVENUE'].values
        n = len(x)
        
        x_mean = x.mean()
        y_mean = y.mean()
        slope = sum((x - x_mean) * (y - y_mean)) / sum((x - x_mean) ** 2) if sum((x - x_mean) ** 2) != 0 else 0
        intercept = y_mean - slope * x_mean
        
        trends_df['MA_3'] = trends_df['REVENUE'].rolling(window=3, min_periods=1).mean()
        
        historical = trends_df.to_dict(orient="records")
        forecast = []
        
        last_index = x[-1]
        last_year = int(trends_df.iloc[-1]['YEAR'])
        last_month = int(trends_df.iloc[-1]['MONTH'])
        
        curr_year = last_year
        curr_month = last_month
        
        for i in range(1, months_to_forecast + 1):
            curr_month += 1
            if curr_month > 12:
                curr_month = 1
                curr_year += 1
            
            next_index = last_index + i
            predicted_rev = max(0.0, slope * next_index + intercept)
            ma_pred = (historical[-1]['MA_3'] + predicted_rev) / 2.0
            
            forecast.append({
                "YEAR": curr_year,
                "MONTH": curr_month,
                "DATE_STR": f"{curr_year}-{curr_month:02d}",
                "FORECAST_REGRESSION": round(predicted_rev, 2),
                "FORECAST_MA": round(ma_pred, 2)
            })
            
        return {
            "historical": historical,
            "forecast": forecast
        }

    def export_report(self, report_type: str, file_path: str, filters: dict = None) -> str:
        """Exports a specified analytic report to a local CSV file."""
        logger.info(f"Exporting report '{report_type}' with filters to '{file_path}'...")
        
        if report_type == "kpi_summary":
            data = [self.get_kpi_summary(filters)]
            df = pd.DataFrame(data)
        elif report_type == "revenue_trends":
            df = pd.DataFrame(self.get_revenue_trends(filters))
        elif report_type == "state_distribution":
            df = pd.DataFrame(self.get_state_distribution(filters))
        elif report_type == "top_products":
            df = pd.DataFrame(self.get_top_products(filters))
        elif report_type == "top_sellers":
            df = pd.DataFrame(self.get_top_sellers(filters))
        elif report_type == "review_distribution":
            df = pd.DataFrame(self.get_review_distribution(filters))
        elif report_type == "payment_type_distribution":
            df = pd.DataFrame(self.get_payment_type_distribution(filters))
        else:
            raise ValueError(f"Unknown report type: {report_type}")
            
        os.makedirs(os.path.dirname(os.path.abspath(file_path)), exist_ok=True)
        df.to_csv(file_path, index=False)
        logger.info(f"Successfully exported report to {file_path}!")
        return file_path
