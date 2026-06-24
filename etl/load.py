import os
import logging
import pandas as pd
import snowflake.connector  # type: ignore
from dotenv import load_dotenv

logger = logging.getLogger(__name__)

# Ensure env variables are loaded
load_dotenv()

def init_snowflake_database(conn):
    """Executes the DDL statements in sql/create_tables.sql to initialize database objects."""
    logger.info("DDL initialization started...")
    cursor = conn.cursor()
    try:
        # Resolve absolute path to create_tables.sql
        current_dir = os.path.dirname(os.path.abspath(__file__))
        ddl_path = os.path.join(os.path.dirname(current_dir), "sql", "create_tables.sql")
        
        if not os.path.exists(ddl_path):
            logger.warning(f"DDL file not found at {ddl_path}, skipping initialization.")
            return
            
        with open(ddl_path, "r") as f:
            sql_script = f.read()
            
        # Split statements by semicolon and execute them
        statements = sql_script.split(";")
        for stmt in statements:
            stmt = stmt.strip()
            if stmt:
                # Remove comment lines before checking if statement is empty
                clean_lines = [line for line in stmt.split('\n') if not line.strip().startswith('--')]
                clean_stmt = ' '.join(clean_lines).strip()
                if clean_stmt:
                    logger.info(f"Executing SQL DDL: {clean_stmt[:75]}...")
                    cursor.execute(clean_stmt)
                    
        logger.info("Snowflake database initialization completed successfully!")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise e
    finally:
        cursor.close()

def get_snowflake_connection(force_init=False):
    """Establishes and returns a connection to Snowflake, initializing the database if requested or if it doesn't exist."""
    user = os.getenv("SNOWFLAKE_USER")
    password = os.getenv("SNOWFLAKE_PASSWORD")
    account = os.getenv("SNOWFLAKE_ACCOUNT")
    warehouse = os.getenv("SNOWFLAKE_WAREHOUSE")
    database = os.getenv("SNOWFLAKE_DATABASE")
    schema = os.getenv("SNOWFLAKE_SCHEMA")
    
    if not all([user, password, account]):
        raise ValueError("Snowflake connection credentials (USER, PASSWORD, ACCOUNT) are missing in environment configuration.")
        
    if force_init:
        logger.info(f"Connecting to Snowflake account {account} without database selection for schema initialization...")
        conn = snowflake.connector.connect(
            user=user,
            password=password,
            account=account
        )
        init_snowflake_database(conn)
        cursor = conn.cursor()
        cursor.execute(f"USE WAREHOUSE {warehouse};")
        cursor.execute(f"USE DATABASE {database};")
        cursor.execute(f"USE SCHEMA {schema};")
        cursor.close()
        return conn

    try:
        logger.info(f"Connecting to Snowflake account {account} with database {database}...")
        conn = snowflake.connector.connect(
            user=user,
            password=password,
            account=account,
            warehouse=warehouse,
            database=database,
            schema=schema
        )
        logger.info("Snowflake connection established successfully.")
        return conn
    except Exception as e:
        logger.warning(f"Failed to connect with database {database} directly: {e}")
        logger.info("Retrying connection without database to initialize database objects...")
        conn = snowflake.connector.connect(
            user=user,
            password=password,
            account=account
        )
        try:
            init_snowflake_database(conn)
            cursor = conn.cursor()
            cursor.execute(f"USE WAREHOUSE {warehouse};")
            cursor.execute(f"USE DATABASE {database};")
            cursor.execute(f"USE SCHEMA {schema};")
            cursor.close()
            logger.info("Snowflake connection established and initialized successfully.")
            return conn
        except Exception as init_err:
            conn.close()
            logger.error(f"Failed to initialize database objects on retry: {init_err}")
            raise init_err

def test_connection() -> bool:
    """Tests if Snowflake connection is valid and logs version/session details."""
    try:
        conn = get_snowflake_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT CURRENT_VERSION(), CURRENT_USER(), CURRENT_ROLE(), CURRENT_DATABASE(), CURRENT_SCHEMA();")
        row = cursor.fetchone()
        logger.info(f"Connection Verified!")
        logger.info(f"  Snowflake Version: {row[0]}")
        logger.info(f"  User:              {row[1]}")
        logger.info(f"  Role:              {row[2]}")
        logger.info(f"  Database:          {row[3]}")
        logger.info(f"  Schema:            {row[4]}")
        
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        logger.error(f"Snowflake connection test failed: {e}")
        return False

def load_dataframe_to_snowflake(conn, df: pd.DataFrame, table_name: str) -> bool:
    """
    Loads a single Pandas DataFrame into a Snowflake table by saving it to a local CSV,
    uploading it to ECOMMERCE_STAGE using PUT, and copying it using COPY INTO.
    """
    database = os.getenv("SNOWFLAKE_DATABASE")
    schema = os.getenv("SNOWFLAKE_SCHEMA")
    
    # Create a local tmp directory in the workspace
    current_dir = os.path.dirname(os.path.abspath(__file__))
    workspace_dir = os.path.dirname(current_dir)
    temp_dir = os.path.join(workspace_dir, "tmp_data")
    os.makedirs(temp_dir, exist_ok=True)
    
    temp_file_name = f"{table_name.lower()}.csv"
    temp_file_path = os.path.join(temp_dir, temp_file_name)
    
    logger.info(f"Writing temporary CSV to {temp_file_path}...")
    # Save to CSV - double quote text fields and use standard comma separator
    df.to_csv(temp_file_path, index=False, header=True, sep=',', quotechar='"', doublequote=True)
    
    cursor = conn.cursor()
    try:
        # Select database and schema
        cursor.execute(f"USE DATABASE {database};")
        cursor.execute(f"USE SCHEMA {schema};")
        
        # Prepare file path for Snowflake PUT (forward slashes)
        snowflake_file_path = temp_file_path.replace("\\", "/")
        
        # PUT command (Auto-compress will compress it as gzip)
        put_sql = f"PUT 'file://{snowflake_file_path}' @ECOMMERCE_STAGE/{table_name.lower()} AUTO_COMPRESS=TRUE OVERWRITE=TRUE;"
        logger.info(f"Uploading file to Snowflake stage: {put_sql[:120]}...")
        cursor.execute(put_sql)
        
        # Truncate table for fresh load
        logger.info(f"Truncating table {table_name}...")
        cursor.execute(f"TRUNCATE TABLE {table_name};")
        
        # COPY INTO command (reads from subfolder and purges afterwards)
        copy_sql = f"""
        COPY INTO {table_name}
        FROM @ECOMMERCE_STAGE/{table_name.lower()}/
        FILE_FORMAT = (
            TYPE = CSV
            FIELD_DELIMITER = ','
            FIELD_OPTIONALLY_ENCLOSED_BY = '\"'
            SKIP_HEADER = 1
            NULL_IF = ('', 'None', 'nan', 'NaN')
            EMPTY_FIELD_AS_NULL = TRUE
        )
        PURGE = TRUE;
        """
        logger.info(f"Executing COPY INTO for {table_name}...")
        cursor.execute(copy_sql)
        
        # Verify number of rows loaded
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        count = cursor.fetchone()[0]
        logger.info(f"Successfully loaded {count:,} rows into table {table_name}!")
        return True
        
    except Exception as e:
        logger.error(f"Error loading table {table_name} via stage: {e}")
        return False
    finally:
        cursor.close()
        # Clean up local temp file
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
            except Exception as clean_err:
                logger.warning(f"Failed to remove local temp file {temp_file_path}: {clean_err}")

def load_all_to_snowflake(conn, transformed_dfs: dict):
    """
    Orchestrates the loading of all transformed DataFrames into their respective Snowflake tables.
    """
    logger.info("Starting load phase to Snowflake...")
    
    load_order = [
        ("DIM_CUSTOMERS", "DIM_CUSTOMERS"),
        ("DIM_PRODUCTS", "DIM_PRODUCTS"),
        ("DIM_SELLERS", "DIM_SELLERS"),
        ("DIM_DATE", "DIM_DATE"),
        ("FACT_ORDERS", "FACT_ORDERS"),
        ("FACT_ORDER_ITEMS", "FACT_ORDER_ITEMS"),
        ("FACT_PAYMENTS", "FACT_PAYMENTS"),
        ("FACT_REVIEWS", "FACT_REVIEWS")
    ]
    
    results = {}
    for df_key, table_name in load_order:
        df = transformed_dfs[df_key]
        success = load_dataframe_to_snowflake(conn, df, table_name)
        results[table_name] = success
        if not success:
            logger.error(f"Loading failed at table {table_name}. Aborting pipeline.")
            raise RuntimeError(f"Pipeline failed at loading table {table_name}.")
            
    logger.info("Load phase completed successfully for all tables!")
    return results
