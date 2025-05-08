"""
sql_validator.py: Enhanced SQL validation with schema and column validation
"""
import re
import logging
import os
import pyodbc
import sqlparse
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

logger = logging.getLogger(__name__)

def get_db_connection():
    """Create and return a database connection"""
    try:
        connection_string = (f"""
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

def get_database_schemas():
    """Fetch all schemas from the database"""
    schemas = set()
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            cursor.execute("SELECT SCHEMA_NAME FROM INFORMATION_SCHEMA.SCHEMATA")
            
            for row in cursor.fetchall():
                schemas.add(row[0])
                
            cursor.close()
            conn.close()
    except Exception as e:
        logger.error(f"Error fetching schemas: {e}")
        # Fall back to default AdventureWorks schemas if we can't fetch them
        schemas = {'Person', 'HumanResources', 'Production', 'Purchasing', 'Sales', 'dbo'}
    
    return schemas

def get_database_columns():
    """
    Fetch all columns from all tables in the database
    Returns a dict mapping {schema.table: set(columns)}
    """
    columns_dict = {}
    try:
        conn = get_db_connection()
        if conn:
            cursor = conn.cursor()
            query = """
            SELECT 
                TABLE_SCHEMA, 
                TABLE_NAME, 
                COLUMN_NAME 
            FROM 
                INFORMATION_SCHEMA.COLUMNS
            ORDER BY 
                TABLE_SCHEMA, TABLE_NAME, ORDINAL_POSITION
            """
            cursor.execute(query)
            
            for row in cursor.fetchall():
                schema = row[0]
                table = row[1]
                column = row[2]
                
                table_key = f"{schema}.{table}"
                
                if table_key not in columns_dict:
                    columns_dict[table_key] = set()
                
                columns_dict[table_key].add(column)
                
            cursor.close()
            conn.close()
    except Exception as e:
        logger.error(f"Error fetching columns: {e}")
    
    return columns_dict

class SqlValidator:
    def __init__(self, schemas=None, columns_dict=None):
        # Dangerous operations that should be caught
        self.dangerous_patterns = [
            (r'\bDROP\b', 'DROP operations are not allowed'),
            (r'\bTRUNCATE\b', 'TRUNCATE operations are not allowed'),
            (r'\bDELETE\b', 'DELETE operations are not allowed'),
            (r'\bUPDATE\b', 'UPDATE operations are not allowed'),
            (r'\bINSERT\b', 'INSERT operations are not allowed'),
            (r'\bEXEC\b|\bEXECUTE\b', 'EXEC/EXECUTE operations are not allowed'),
            (r'\bMASTER\b', 'References to master database are not allowed'),
            (r'\bSYSDBA\b', 'SYSDBA operations are not allowed'),
            (r'\bINTO\s+OUTFILE\b', 'INTO OUTFILE operations are not allowed'),
            (r'\bLOAD_FILE\b', 'LOAD_FILE operations are not allowed'),
            (r'\bALTER\b', 'ALTER operations are not allowed'),
            (r'\bCREATE\b', 'CREATE operations are not allowed'),
            (r'--', 'SQL comments are not allowed'),
            (r'/\*', 'SQL comments are not allowed'),
        ]
        
        # Better check for multiple statements that's less likely to give false positives
        self.multiple_statements_pattern = r';\s*(SELECT|INSERT|UPDATE|DELETE|DROP|CREATE|ALTER)\b'
        
        # Allowed SQL operation patterns - only SELECT as per your requirement
        self.allowed_operations = [
            r'\bSELECT\b',
        ]
        
        # Set schemas - either provided or fetch from database
        self.valid_schemas = schemas if schemas else get_database_schemas()
        
        # Set columns dictionary - either provided or fetch from database
        self.columns_dict = columns_dict if columns_dict else get_database_columns()
        
        logger.info(f"Validator initialized with {len(self.valid_schemas)} schemas and {len(self.columns_dict)} tables")
    
    def extract_table_aliases(self, sql):
        """
        Extract table aliases from SQL query
        Returns dict mapping alias -> full table name (with schema)
        """
        aliases = {}
        
        # Parse the SQL
        parsed = sqlparse.parse(sql)
        if not parsed:
            return aliases
        
        stmt = parsed[0]
        
        # Simple regex pattern to find table references with aliases
        # This is a simplified approach and may not catch all cases
        # Format: (FROM|JOIN) schema.table [AS] alias
        table_pattern = r'(?:FROM|JOIN)\s+([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)(?:\s+(?:AS\s+)?([a-zA-Z0-9_]+))?'
        
        matches = re.finditer(table_pattern, sql, re.IGNORECASE)
        for match in matches:
            schema = match.group(1)
            table = match.group(2)
            alias = match.group(3)
            
            full_name = f"{schema}.{table}"
            
            if alias:
                aliases[alias.lower()] = full_name
            else:
                # If no alias is specified, the table name itself serves as an implicit alias
                aliases[table.lower()] = full_name
        
        return aliases
    
    def extract_column_references(self, sql):
        """
        Extract column references from SQL query
        Returns a list of (table_alias, column_name) tuples
        """
        column_refs = []
        
        # This is a simplified approach and may not catch all cases
        # Pattern to find column references: table_alias.column_name
        column_pattern = r'([a-zA-Z0-9_]+)\.([a-zA-Z0-9_]+)'
        
        matches = re.finditer(column_pattern, sql, re.IGNORECASE)
        for match in matches:
            table_alias = match.group(1).lower()
            column_name = match.group(2)
            column_refs.append((table_alias, column_name))
        
        return column_refs
    
    def validate_columns(self, sql):
        """
        Validate that all columns referenced in the query exist in their respective tables
        Returns (is_valid, error_message)
        """
        try:
            # Extract table aliases
            aliases = self.extract_table_aliases(sql)
            if not aliases:
                return True, ""  # Skip validation if we couldn't extract any tables
            
            # Extract column references
            column_refs = self.extract_column_references(sql)
            
            for table_alias, column_name in column_refs:
                # Skip validation for columns that aren't using table aliases
                if table_alias not in aliases:
                    continue
                
                full_table_name = aliases[table_alias]
                
                # Check if the table exists in our columns dictionary
                if full_table_name not in self.columns_dict:
                    return False, f"Referenced table not found: {full_table_name}"
                
                # Check if the column exists in the table
                if column_name not in self.columns_dict[full_table_name]:
                    return False, f"Column '{column_name}' not found in table '{full_table_name}'"
            
            return True, ""
        except Exception as e:
            logger.error(f"Error validating columns: {e}")
            return True, ""  # Skip validation on error
    
    def validate(self, sql):
        """
        Validate SQL query for security and correctness
        Returns (is_valid, error_message)
        """
        sql = sql.strip()
        
        # Check if SQL is empty
        if not sql:
            return False, "SQL query is empty"
        
        # Check for allowed operations
        operation_found = False
        for pattern in self.allowed_operations:
            if re.search(pattern, sql, re.IGNORECASE):
                operation_found = True
                break
                
        if not operation_found:
            return False, "Only SELECT operations are allowed"
        
        # Check for dangerous patterns
        for pattern, message in self.dangerous_patterns:
            if re.search(pattern, sql, re.IGNORECASE):
                return False, message
        
        # Check for multiple statements with a better pattern
        if re.search(self.multiple_statements_pattern, sql, re.IGNORECASE):
            return False, "Multiple SQL statements are not allowed"
        
        # Validate schema references
        schemas_used = set(re.findall(r'FROM\s+([a-zA-Z0-9_]+)\.', sql))
        schemas_used.update(re.findall(r'JOIN\s+([a-zA-Z0-9_]+)\.', sql))
        
        for schema in schemas_used:
            if schema not in self.valid_schemas:
                return False, f"Invalid schema: {schema}. Valid schemas are: {', '.join(self.valid_schemas)}"
        
        # Validate columns if there are schema references
        if schemas_used:
            is_valid, error = self.validate_columns(sql)
            if not is_valid:
                return False, error
        
        # All checks passed
        return True, ""
    
    def check_for_warnings(self, sql):
        """
        Check for non-blocking warnings in SQL
        Returns list of warning messages
        """
        warnings = []
        
        # Check for potentially slow queries
        if (re.search(r'\bLIKE\s+[\'"]%', sql, re.IGNORECASE) or 
            re.search(r'\bOR\b', sql, re.IGNORECASE)):
            warnings.append("This query may be slow due to LIKE '%...' pattern or OR conditions")
        
        # Check for missing indexes (simplified example)
        if re.search(r'ORDER BY', sql, re.IGNORECASE) and not re.search(r'TOP|OFFSET|FETCH', sql, re.IGNORECASE):
            warnings.append("This query uses ORDER BY without LIMIT which may be inefficient")
        
        # Check for semicolons - now just a warning
        if ";" in sql:
            warnings.append("Semicolons in SQL queries are not needed and might cause issues")
            
        return warnings

# Create validator instance - will be reused by get_sql_analysis
_validator = None

def get_sql_analysis(sql, refresh=False):
    """
    Analyze SQL for validity and warnings
    Returns a dict with analysis results
    
    Parameters:
    - sql: The SQL query to analyze
    - refresh: Whether to refresh schema and column information
    """
    global _validator
    
    # Create or refresh the validator if needed
    if _validator is None or refresh:
        _validator = SqlValidator()
    
    is_valid, error = _validator.validate(sql)
    warnings = _validator.check_for_warnings(sql) if is_valid else []
    
    return {
        "is_valid": is_valid,
        "error": error,
        "warnings": warnings,
        "estimated_safe": is_valid and not warnings
    }

def is_select_statement(sql):
    """Check if the SQL is a SELECT statement only"""
    select_pattern = r'^\s*SELECT\b'
    return bool(re.match(select_pattern, sql, re.IGNORECASE))

def refresh_schemas_and_columns():
    """Force refresh of schema and column information"""
    global _validator
    _validator = SqlValidator()
    return {
        "schemas": list(_validator.valid_schemas),
        "tables": list(_validator.columns_dict.keys())
    }

if __name__ == "__main__":
    # Test the validator
    test_queries = [
        "SELECT * FROM Person.Person",
        "SELECT p.FirstName FROM Person.Person p",
        "SELECT p.FirstName, p.LastName, e.HireDate FROM Person.Person p JOIN HumanResources.Employee e ON p.BusinessEntityID = e.BusinessEntityID",
        "SELECT p.NonExistentColumn FROM Person.Person p",
        "SELECT * FROM NonExistentSchema.Table",
    ]
    
    print(f"Using schemas: {get_database_schemas()}")
    print(f"Column info available for {len(get_database_columns())} tables")
    
    for query in test_queries:
        result = get_sql_analysis(query)
        print(f"Query: {query}")
        print(f"Valid: {result['is_valid']}")
        if not result['is_valid']:
            print(f"Error: {result['error']}")
        if result['warnings']:
            print(f"Warnings: {', '.join(result['warnings'])}")
        print("-" * 50)