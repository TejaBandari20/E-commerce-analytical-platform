import pandas as pd
import logging

logger = logging.getLogger(__name__)

def clean_string_column(series: pd.Series) -> pd.Series:
    """Trims whitespace and converts empty strings to None."""
    if series.dtype == 'object' or pd.api.types.is_string_dtype(series):
        return series.astype(str).str.strip().replace({'': None, 'nan': None, 'NaN': None, 'None': None, '<NA>': None})
    return series

def transform_customers(df: pd.DataFrame) -> pd.DataFrame:
    """Transforms raw customers data into DIM_CUSTOMERS schema."""
    logger.info("Transforming Customers...")
    df_clean = df.copy()
    
    # Standardize string fields
    for col in ['customer_id', 'customer_unique_id', 'customer_city', 'customer_state']:
        df_clean[col] = clean_string_column(df_clean[col])
        if col in ['customer_city', 'customer_state']:
            df_clean[col] = df_clean[col].str.upper()
            
    # Standardize integer zip code
    df_clean['customer_zip_code_prefix'] = pd.to_numeric(df_clean['customer_zip_code_prefix'], errors='coerce').astype('Int64')
    
    # Map to schema columns
    schema_cols = {
        'customer_id': 'CUSTOMER_ID',
        'customer_unique_id': 'CUSTOMER_UNIQUE_ID',
        'customer_zip_code_prefix': 'CUSTOMER_ZIP_CODE_PREFIX',
        'customer_city': 'CUSTOMER_CITY',
        'customer_state': 'CUSTOMER_STATE'
    }
    df_mapped = df_clean[list(schema_cols.keys())].rename(columns=schema_cols)
    
    logger.info(f"Customers transformed: {df_mapped.shape[0]} rows.")
    return df_mapped

def transform_products(df: pd.DataFrame) -> pd.DataFrame:
    """Transforms raw products data into DIM_PRODUCTS schema."""
    logger.info("Transforming Products...")
    df_clean = df.copy()
    
    # Standardize string fields
    for col in ['product_id', 'product_category_name']:
        df_clean[col] = clean_string_column(df_clean[col])
        
    # Map and rename columns with typos
    rename_map = {
        'product_id': 'PRODUCT_ID',
        'product_category_name': 'PRODUCT_CATEGORY_NAME',
        'product_name_lenght': 'PRODUCT_NAME_LENGTH',
        'product_description_lenght': 'PRODUCT_DESCRIPTION_LENGTH',
        'product_photos_qty': 'PRODUCT_PHOTOS_QTY',
        'product_weight_g': 'PRODUCT_WEIGHT_G',
        'product_length_cm': 'PRODUCT_LENGTH_CM',
        'product_height_cm': 'PRODUCT_HEIGHT_CM',
        'product_width_cm': 'PRODUCT_WIDTH_CM'
    }
    
    # Apply numeric casting to integer columns
    int_cols = [
        'product_name_lenght', 'product_description_lenght', 
        'product_photos_qty', 'product_weight_g', 
        'product_length_cm', 'product_height_cm', 'product_width_cm'
    ]
    for col in int_cols:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce').astype('Int64')
        
    df_mapped = df_clean[list(rename_map.keys())].rename(columns=rename_map)
    logger.info(f"Products transformed: {df_mapped.shape[0]} rows.")
    return df_mapped

def transform_sellers(df: pd.DataFrame) -> pd.DataFrame:
    """Transforms raw sellers data into DIM_SELLERS schema."""
    logger.info("Transforming Sellers...")
    df_clean = df.copy()
    
    # Standardize string fields
    for col in ['seller_id', 'seller_city', 'seller_state']:
        df_clean[col] = clean_string_column(df_clean[col])
        if col in ['seller_city', 'seller_state']:
            df_clean[col] = df_clean[col].str.upper()
            
    # Standardize zip code prefix
    df_clean['seller_zip_code_prefix'] = pd.to_numeric(df_clean['seller_zip_code_prefix'], errors='coerce').astype('Int64')
    
    schema_cols = {
        'seller_id': 'SELLER_ID',
        'seller_zip_code_prefix': 'SELLER_ZIP_CODE_PREFIX',
        'seller_city': 'SELLER_CITY',
        'seller_state': 'SELLER_STATE'
    }
    df_mapped = df_clean[list(schema_cols.keys())].rename(columns=schema_cols)
    logger.info(f"Sellers transformed: {df_mapped.shape[0]} rows.")
    return df_mapped

def generate_date_dimension(start_date: str = '2016-01-01', end_date: str = '2019-12-31') -> pd.DataFrame:
    """Generates the DIM_DATE table dynamically in Python."""
    logger.info(f"Generating Date Dimension ({start_date} to {end_date})...")
    
    # Generate date range
    dates = pd.date_range(start=start_date, end=end_date)
    
    df_date = pd.DataFrame()
    df_date['DATE_ID'] = dates.strftime('%Y%m%d').astype(int)
    # Using datetime64[ns] for full_date so write_pandas transfers it as TIMESTAMP/DATE correctly
    df_date['FULL_DATE'] = dates
    df_date['DAY'] = dates.day.astype('Int64')
    df_date['MONTH'] = dates.month.astype('Int64')
    df_date['QUARTER'] = dates.quarter.astype('Int64')
    df_date['YEAR'] = dates.year.astype('Int64')
    df_date['WEEKDAY'] = dates.strftime('%A')
    
    logger.info(f"Date Dimension generated: {df_date.shape[0]} rows.")
    return df_date

def transform_orders(df: pd.DataFrame) -> pd.DataFrame:
    """Transforms raw orders data into FACT_ORDERS schema."""
    logger.info("Transforming Orders...")
    df_clean = df.copy()
    
    # Clean strings
    for col in ['order_id', 'customer_id', 'order_status']:
        df_clean[col] = clean_string_column(df_clean[col])
        
    # Convert timestamp fields
    timestamp_cols = [
        'order_purchase_timestamp', 'order_approved_at', 
        'order_delivered_carrier_date', 'order_delivered_customer_date', 
        'order_estimated_delivery_date'
    ]
    for col in timestamp_cols:
        df_clean[col] = pd.to_datetime(df_clean[col], errors='coerce')
        
    schema_cols = {
        'order_id': 'ORDER_ID',
        'customer_id': 'CUSTOMER_ID',
        'order_status': 'ORDER_STATUS',
        'order_purchase_timestamp': 'ORDER_PURCHASE_TIMESTAMP',
        'order_approved_at': 'ORDER_APPROVED_AT',
        'order_delivered_carrier_date': 'ORDER_DELIVERED_CARRIER_DATE',
        'order_delivered_customer_date': 'ORDER_DELIVERED_CUSTOMER_DATE',
        'order_estimated_delivery_date': 'ORDER_ESTIMATED_DELIVERY_DATE'
    }
    df_mapped = df_clean[list(schema_cols.keys())].rename(columns=schema_cols)
    logger.info(f"Orders transformed: {df_mapped.shape[0]} rows.")
    return df_mapped

def transform_order_items(df: pd.DataFrame) -> pd.DataFrame:
    """Transforms raw order items data into FACT_ORDER_ITEMS schema."""
    logger.info("Transforming Order Items...")
    df_clean = df.copy()
    
    # Clean strings
    for col in ['order_id', 'product_id', 'seller_id']:
        df_clean[col] = clean_string_column(df_clean[col])
        
    # Cast integers and floats
    df_clean['order_item_id'] = pd.to_numeric(df_clean['order_item_id'], errors='coerce').astype('Int64')
    df_clean['price'] = pd.to_numeric(df_clean['price'], errors='coerce').astype(float)
    df_clean['freight_value'] = pd.to_numeric(df_clean['freight_value'], errors='coerce').astype(float)
    
    # Convert timestamp
    df_clean['shipping_limit_date'] = pd.to_datetime(df_clean['shipping_limit_date'], errors='coerce')
    
    schema_cols = {
        'order_id': 'ORDER_ID',
        'order_item_id': 'ORDER_ITEM_ID',
        'product_id': 'PRODUCT_ID',
        'seller_id': 'SELLER_ID',
        'shipping_limit_date': 'SHIPPING_LIMIT_DATE',
        'price': 'PRICE',
        'freight_value': 'FREIGHT_VALUE'
    }
    df_mapped = df_clean[list(schema_cols.keys())].rename(columns=schema_cols)
    logger.info(f"Order Items transformed: {df_mapped.shape[0]} rows.")
    return df_mapped

def transform_payments(df: pd.DataFrame) -> pd.DataFrame:
    """Transforms raw payments data into FACT_PAYMENTS schema."""
    logger.info("Transforming Payments...")
    df_clean = df.copy()
    
    # Clean strings
    df_clean['order_id'] = clean_string_column(df_clean['order_id'])
    df_clean['payment_type'] = clean_string_column(df_clean['payment_type'])
    
    # Cast integers and floats
    df_clean['payment_sequential'] = pd.to_numeric(df_clean['payment_sequential'], errors='coerce').astype('Int64')
    df_clean['payment_installments'] = pd.to_numeric(df_clean['payment_installments'], errors='coerce').astype('Int64')
    df_clean['payment_value'] = pd.to_numeric(df_clean['payment_value'], errors='coerce').astype(float)
    
    schema_cols = {
        'order_id': 'ORDER_ID',
        'payment_sequential': 'PAYMENT_SEQUENTIAL',
        'payment_type': 'PAYMENT_TYPE',
        'payment_installments': 'PAYMENT_INSTALLMENTS',
        'payment_value': 'PAYMENT_VALUE'
    }
    df_mapped = df_clean[list(schema_cols.keys())].rename(columns=schema_cols)
    logger.info(f"Payments transformed: {df_mapped.shape[0]} rows.")
    return df_mapped

def transform_reviews(df: pd.DataFrame) -> pd.DataFrame:
    """Transforms raw reviews data into FACT_REVIEWS schema."""
    logger.info("Transforming Reviews...")
    df_clean = df.copy()
    
    # Clean strings and handle NaN in comment titles/messages
    for col in ['review_id', 'order_id', 'review_comment_title', 'review_comment_message']:
        df_clean[col] = clean_string_column(df_clean[col])
        
    # Cast integer
    df_clean['review_score'] = pd.to_numeric(df_clean['review_score'], errors='coerce').astype('Int64')
    
    # Convert timestamps
    # review_creation_date is DATE, we convert it to datetime64[ns]
    df_clean['review_creation_date'] = pd.to_datetime(df_clean['review_creation_date'], errors='coerce')
    df_clean['review_answer_timestamp'] = pd.to_datetime(df_clean['review_answer_timestamp'], errors='coerce')
    
    schema_cols = {
        'review_id': 'REVIEW_ID',
        'order_id': 'ORDER_ID',
        'review_score': 'REVIEW_SCORE',
        'review_comment_title': 'REVIEW_COMMENT_TITLE',
        'review_comment_message': 'REVIEW_COMMENT_MESSAGE',
        'review_creation_date': 'REVIEW_CREATION_DATE',
        'review_answer_timestamp': 'REVIEW_ANSWER_TIMESTAMP'
    }
    df_mapped = df_clean[list(schema_cols.keys())].rename(columns=schema_cols)
    logger.info(f"Reviews transformed: {df_mapped.shape[0]} rows.")
    return df_mapped

def transform_all_data(raw_dfs: dict) -> dict:
    """
    Orchestrates the transformation of all Olist datasets and date dimension generation.
    Returns a dictionary of cleaned, mapped DataFrames.
    """
    logger.info("Starting transformation phase...")
    
    transformed_dfs = {
        "DIM_CUSTOMERS": transform_customers(raw_dfs["customers"]),
        "DIM_PRODUCTS": transform_products(raw_dfs["products"]),
        "DIM_SELLERS": transform_sellers(raw_dfs["sellers"]),
        "DIM_DATE": generate_date_dimension('2016-01-01', '2019-12-31'),
        "FACT_ORDERS": transform_orders(raw_dfs["orders"]),
        "FACT_ORDER_ITEMS": transform_order_items(raw_dfs["order_items"]),
        "FACT_PAYMENTS": transform_payments(raw_dfs["payments"]),
        "FACT_REVIEWS": transform_reviews(raw_dfs["reviews"])
    }
    
    logger.info("Transformation phase completed successfully!")
    return transformed_dfs
