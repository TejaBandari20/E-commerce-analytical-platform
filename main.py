import os
import argparse
import time
import logging
from dotenv import load_dotenv

# Import our ETL modules
from etl.extract import extract_all_data
from etl.transform import transform_all_data
from etl.load import test_connection, get_snowflake_connection, load_all_to_snowflake

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Load local environment variables from .env
load_dotenv()

def run_pipeline():
    """Orchestrates the entire ETL pipeline."""
    start_time = time.time()
    logger.info("=========================================")
    logger.info("    STARTING E-COMMERCE ETL PIPELINE     ")
    logger.info("=========================================")
    
    # 0. Test Snowflake Connection first
    if not test_connection():
        logger.error("Could not establish Snowflake connection. Aborting ETL pipeline.")
        return False
        
    data_dir = os.getenv("OLIST_DATA_DIR", r"E:\Downloads-E\archive")
    logger.info(f"Source Data Directory: {data_dir}")
    
    # 1. Extraction Phase
    try:
        raw_dfs = extract_all_data(data_dir)
    except Exception as e:
        logger.error(f"ETL Extraction phase failed: {e}")
        return False
        
    # 2. Transformation & Mapping Phase
    try:
        transformed_dfs = transform_all_data(raw_dfs)
    except Exception as e:
        logger.error(f"ETL Transformation phase failed: {e}")
        return False
        
    # 3. Load Phase
    try:
        conn = get_snowflake_connection()
        try:
            load_all_to_snowflake(conn, transformed_dfs)
        finally:
            conn.close()
    except Exception as e:
        logger.error(f"ETL Loading phase failed: {e}")
        return False
        
    elapsed = time.time() - start_time
    logger.info("=========================================")
    logger.info(f"  ETL PIPELINE COMPLETED SUCCESSFULLY!   ")
    logger.info(f"  Elapsed Time: {elapsed:.2f} seconds")
    logger.info("=========================================")
    return True

def setup_analytical_objects() -> bool:
    """Initializes the database views, stored procedures, streams, tasks, and RBAC in Snowflake."""
    logger.info("=========================================")
    logger.info("  INITIALIZING SNOWFLAKE ANALYTICS DB    ")
    logger.info("=========================================")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sql_path = os.path.join(current_dir, "sql", "create_analytical_objects.sql")
    
    if not os.path.exists(sql_path):
        logger.error(f"SQL script not found at {sql_path}!")
        return False
        
    with open(sql_path, "r") as f:
        sql_script = f.read()
        
    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        
        # Split by semicolon except when inside a stored procedure dollar block ($$...$$)
        statements = []
        in_dollar_block = False
        current_stmt = []
        
        for line in sql_script.split('\n'):
            if "$$" in line:
                in_dollar_block = not in_dollar_block
            
            if not in_dollar_block and ';' in line:
                parts = line.split(';')
                current_stmt.append(parts[0])
                statements.append("\n".join(current_stmt).strip())
                current_stmt = parts[1:]
            else:
                current_stmt.append(line)
        
        if current_stmt:
            stmt = "\n".join(current_stmt).strip()
            if stmt:
                statements.append(stmt)
                
        # Execute each statement
        for stmt in statements:
            stmt = stmt.strip()
            if stmt:
                clean_lines = [l for l in stmt.split('\n') if not l.strip().startswith('--')]
                clean_stmt = ' '.join(clean_lines).strip()
                if clean_stmt:
                    logger.info(f"Executing SQL: {clean_stmt[:75]}...")
                    cursor.execute(stmt)
                    
        logger.info("Snowflake Analytical Objects setup completed successfully!")
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Failed to set up analytical objects: {e}")
        return False

def run_service_demo():
    """Runs a mock dashboard retrieval using BackendDataService and logs output."""
    logger.info("=========================================")
    logger.info("    RUNNING BACKEND DATA SERVICE DEMO    ")
    logger.info("=========================================")
    
    from services.data_service import BackendDataService
    
    try:
        service = BackendDataService()
        
        # 1. Trigger summary refresh first
        logger.info("Refreshing summary KPIs reporting tables...")
        refresh_msg = service.refresh_analytics_summary()
        logger.info(f"Procedure response: {refresh_msg}")
        
        # 2. Get KPI summary
        kpis = service.get_kpi_summary()
        logger.info("KPI Summary retrieved successfully:")
        print(f"\nDashboard KPI Summary:")
        print(f"----------------------------------------")
        print(f"Total Revenue:      ${kpis.get('total_revenue', 0):,.2f}")
        print(f"Total Orders:       {kpis.get('total_orders', 0):,}")
        print(f"Total Customers:    {kpis.get('total_customers', 0):,}")
        print(f"Avg Review Score:   {kpis.get('avg_review_score', 0):.2f} / 5.0")
        print(f"----------------------------------------\n")
        
        # 3. Get Revenue trends
        trends = service.get_revenue_trends()
        print(f"Revenue Trends (Last 3 Months / Entries):")
        print(f"----------------------------------------")
        for t in trends[-3:]:
            print(f"Year: {t['YEAR']}, Month: {t['MONTH']}, Revenue: ${t['REVENUE']:,.2f}, Orders: {t['ORDERS']}")
        print(f"----------------------------------------\n")
        
        # 4. Get Top Products
        products = service.get_top_products(limit=3)
        print(f"Top 3 Product Categories by Revenue:")
        print(f"----------------------------------------")
        for i, p in enumerate(products, 1):
            print(f"{i}. {p['CATEGORY']:<25} | Units: {p['UNITS_SOLD']:<5} | Rev: ${p['REVENUE']:,.2f}")
        print(f"----------------------------------------\n")
        
        # 5. Get Review Distribution
        reviews = service.get_review_distribution()
        print(f"Review Score Distribution:")
        print(f"----------------------------------------")
        for r in reviews:
            print(f"Score {r['REVIEW_SCORE']} stars : {r['REVIEW_COUNT']:,} reviews")
        print(f"----------------------------------------\n")
        
    except Exception as e:
        logger.error(f"Data service demo failed: {e}")

def run_export_report(report_type: str):
    """Exports the specified report to a local CSV file inside the reports directory."""
    from services.data_service import BackendDataService
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    file_name = f"{report_type}_{int(time.time())}.csv"
    file_path = os.path.join(current_dir, "reports", file_name)
    
    try:
        service = BackendDataService()
        exported_path = service.export_report(report_type, file_path)
        logger.info(f"Report exported successfully to: {exported_path}")
    except Exception as e:
        logger.error(f"Failed to export report '{report_type}': {e}")


def run_dashboard():
    """Launches the Streamlit dashboard application in a subprocess."""
    logger.info("=========================================")
    logger.info("    LAUNCHING STREAMLIT BI DASHBOARD     ")
    logger.info("=========================================")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    st_executable = r"E:\snowflake\env\Scripts\streamlit.exe"
    
    import subprocess
    try:
        logger.info("Starting Streamlit server on http://localhost:8501...")
        subprocess.run([st_executable, "run", "app.py"], cwd=current_dir)
    except Exception as e:
        logger.error(f"Failed to launch Streamlit server: {e}")

def run_validation():
    """Queries Snowflake to count rows in each target table and displays a validation summary."""
    logger.info("=========================================")
    logger.info("      VALIDATING SNOWFLAKE TABLES        ")
    logger.info("=========================================")
    
    tables = [
        "DIM_CUSTOMERS",
        "DIM_PRODUCTS",
        "DIM_SELLERS",
        "DIM_DATE",
        "FACT_ORDERS",
        "FACT_ORDER_ITEMS",
        "FACT_PAYMENTS",
        "FACT_REVIEWS"
    ]
    
    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        
        db = os.getenv("SNOWFLAKE_DATABASE")
        schema = os.getenv("SNOWFLAKE_SCHEMA")
        cursor.execute(f"USE DATABASE {db};")
        cursor.execute(f"USE SCHEMA {schema};")
        
        logger.info(f"Table Row Counts in {db}.{schema}:")
        print(f"\n{'-'*40}")
        print(f"{'TABLE NAME':<25} | {'ROW COUNT':<10}")
        print(f"{'-'*40}")
        
        for table in tables:
            try:
                cursor.execute(f"SELECT COUNT(*) FROM {table};")
                count = cursor.fetchone()[0]
                print(f"{table:<25} | {count:<10,}")
            except Exception as ex:
                print(f"{table:<25} | ERROR: {ex}")
                
        print(f"{'-'*40}\n")
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Validation failed: {e}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Olist E-Commerce Snowflake ETL Pipeline")
    parser.add_argument("--test-connection", action="store_true", help="Test connection to Snowflake and exit.")
    parser.add_argument("--run-etl", action="store_true", help="Run the extraction, transformation, and load phases.")
    parser.add_argument("--setup-analytics", action="store_true", help="Set up analytical views, procedures, streams, tasks, and RBAC.")
    parser.add_argument("--run-service-demo", action="store_true", help="Query and print database metrics using BackendDataService.")
    parser.add_argument("--export-report", type=str, help="Export a specific report type (e.g. kpi_summary, revenue_trends, top_products, etc.) to a local CSV.")
    parser.add_argument("--run-dashboard", action="store_true", help="Launch the Streamlit dashboard application.")
    parser.add_argument("--validate", action="store_true", help="Validate row counts in Snowflake tables and exit.")
    
    args = parser.parse_args()
    
    # Check arguments
    any_arg = (args.test_connection or args.run_etl or args.setup_analytics or 
               args.run_service_demo or args.export_report or args.validate or args.run_dashboard)
               
    if not any_arg:
        # Default behavior: run pipeline and validate
        success = run_pipeline()
        if success:
            run_validation()
    else:
        if args.test_connection:
            test_connection()
        if args.run_etl:
            run_pipeline()
        if args.setup_analytics:
            setup_analytical_objects()
        if args.run_service_demo:
            run_service_demo()
        if args.export_report:
            run_export_report(args.export_report)
        if args.run_dashboard:
            run_dashboard()
        if args.validate:
            run_validation()
