import pyodbc
import json
import os
from dotenv import load_dotenv
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def get_connection():
    """Create and return a connection to the database"""
    try:
        connection_string = (
            f"""
    DRIVER={{ODBC Driver 17 for SQL Server}};
    SERVER={os.getenv('DB_SERVER')};
    DATABASE={os.getenv('DB_NAME')};
    UID={os.getenv('DB_USER')};
    PWD={os.getenv('DB_PASSWORD')};
"""
        )
        return pyodbc.connect(connection_string)
    except Exception as e:
        logger.error(f"Error connecting to database: {e}")
        return None

def get_tables():
    """Get a list of tables in the database"""
    conn = get_connection()
    if not conn:
        return []
    
    tables = []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                t.name AS table_name,
                s.name AS schema_name
            FROM 
                sys.tables t
            INNER JOIN 
                sys.schemas s ON t.schema_id = s.schema_id
            ORDER BY 
                s.name, t.name
        """)
        
        for row in cursor.fetchall():
            tables.append({
                "name": row.table_name,
                "schema": row.schema_name
            })
        
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error getting tables: {e}")
    
    return tables

def get_columns(schema_name, table_name):
    """Get columns for a specific table"""
    conn = get_connection()
    if not conn:
        return []
    
    columns = []
    try:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT 
                c.name AS column_name,
                t.name AS data_type,
                c.is_nullable
            FROM 
                sys.columns c
            INNER JOIN 
                sys.types t ON c.user_type_id = t.user_type_id
            INNER JOIN 
                sys.tables tbl ON c.object_id = tbl.object_id
            INNER JOIN 
                sys.schemas s ON tbl.schema_id = s.schema_id
            WHERE 
                tbl.name = ? AND s.name = ?
            ORDER BY 
                c.column_id
        """, table_name, schema_name)
        
        for row in cursor.fetchall():
            columns.append({
                "name": row.column_name,
                "type": row.data_type,
                "nullable": row.is_nullable
            })
        
        cursor.close()
        conn.close()
    except Exception as e:
        logger.error(f"Error getting columns for {schema_name}.{table_name}: {e}")
    
    return columns

def create_formatted_schema():
    """Create formatted schema text for the prompt"""
    tables = get_tables()
    
    formatted_schema = []
    formatted_schema.append("Database Schema:")
    
    for table in tables:
        schema_name = table["schema"]
        table_name = table["name"]
        
        formatted_schema.append(f"\nTable: {schema_name}.{table_name}")
        
        columns = get_columns(schema_name, table_name)
        for column in columns:
            nullable = "NULL" if column["nullable"] else "NOT NULL"
            formatted_schema.append(f"  - {column['name']} ({column['type']}, {nullable})")
    
    return "\n".join(formatted_schema)

def save_schema_to_file(filename="simple_schema.txt"):
    """Save the formatted schema to a file"""
    schema_text = create_formatted_schema()
    
    with open(filename, 'w') as f:
        f.write(schema_text)
    
    logger.info(f"Schema saved to {filename}")
    return filename

if __name__ == "__main__":
    save_schema_to_file()