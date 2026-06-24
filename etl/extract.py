import os
import pandas as pd
import logging

# Set up logging configuration
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def extract_csv(data_dir: str, file_name: str) -> pd.DataFrame:
    """Helper function to load a single CSV file from the directory."""
    file_path = os.path.join(data_dir, file_name)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Source file not found at: {file_path}")
    
    logger.info(f"Extracting {file_name}...")
    df = pd.read_csv(file_path)
    logger.info(f"Successfully extracted {file_name}: {df.shape[0]} rows, {df.shape[1]} columns.")
    return df

def extract_all_data(data_dir: str) -> dict:
    """
    Extracts all required Olist CSV files and returns a dictionary of DataFrames.
    """
    logger.info(f"Starting extraction phase from directory: {data_dir}")
    
    files_map = {
        "customers": "olist_customers_dataset.csv",
        "products": "olist_products_dataset.csv",
        "sellers": "olist_sellers_dataset.csv",
        "orders": "olist_orders_dataset.csv",
        "order_items": "olist_order_items_dataset.csv",
        "payments": "olist_order_payments_dataset.csv",
        "reviews": "olist_order_reviews_dataset.csv"
    }
    
    extracted_dfs = {}
    for key, file_name in files_map.items():
        try:
            extracted_dfs[key] = extract_csv(data_dir, file_name)
        except Exception as e:
            logger.error(f"Failed to extract {file_name}: {e}")
            raise e
            
    logger.info("Extraction phase completed successfully!")
    return extracted_dfs
