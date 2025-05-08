"""
schema_extractor.py: Extracts schema information from AdventureWorks database
"""
import pyodbc
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SchemaExtractor:
    def __init__(self, connection_string=None):
        """Initialize with connection string or use environment variables"""
        if connection_string:
            self.connection_string = connection_string
        else:
            # Use environment variables
            self.connection_string = (f"""
    DRIVER={{ODBC Driver 17 for SQL Server}};
    SERVER={os.getenv('DB_SERVER')};
    DATABASE={os.getenv('DB_NAME')};
    UID={os.getenv('DB_USER')};
    PWD={os.getenv('DB_PASSWORD')};
"""
            )
        
    def get_connection(self):
        """Create and return a connection to the database"""
        if self.connection_string:
            return pyodbc.connect(self.connection_string)
        else:
            # Use Trusted Connection (Windows Authentication)
            return pyodbc.connect(f"""
    DRIVER=SQL Server;
    SERVER={os.getenv('DB_SERVER')};
    DATABASE={os.getenv('DB_NAME')};
    UID={os.getenv('DB_USER')};
    PWD={os.getenv('DB_PASSWORD')};
"""
            )
    
    def extract_tables(self):
        """Extract all tables from the database"""
        tables = []
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Query to get all tables and their descriptions
            query = """
                SELECT 
                    t.name AS table_name,
                    SCHEMA_NAME(t.schema_id) AS schema_name,
                    ISNULL(ep.value, '') AS table_description
                FROM 
                    sys.tables t
                LEFT JOIN 
                    sys.extended_properties ep 
                    ON ep.major_id = t.object_id 
                    AND ep.minor_id = 0 
                    AND ep.name = 'MS_Description'
                ORDER BY 
                    schema_name, table_name
                """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            for row in rows:
                tables.append({
                    "table_name": row.table_name,
                    "schema_name": row.schema_name,
                    "description": row.table_description
                })
                
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error extracting tables: {e}")
        
        return tables
    
    def extract_columns(self, table_name, schema_name="dbo"):
        """Extract all columns for a specific table"""
        columns = []
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Query to get all columns and their descriptions
            query = """
                    SELECT 
                        c.name AS column_name,
                        t.name AS data_type,
                        c.max_length,
                        c.precision,
                        c.scale,
                        c.is_nullable,
                        ISNULL(ep.value, '') AS column_description,
                        CASE WHEN pk.column_id IS NOT NULL THEN 1 ELSE 0 END AS is_primary_key,
                        CASE WHEN fk.parent_column_id IS NOT NULL THEN 1 ELSE 0 END AS is_foreign_key
                    FROM 
                        sys.columns c
                    INNER JOIN 
                        sys.types t ON c.user_type_id = t.user_type_id
                    INNER JOIN 
                        sys.tables tbl ON c.object_id = tbl.object_id
                    LEFT JOIN 
                        sys.schemas s ON tbl.schema_id = s.schema_id
                    LEFT JOIN 
                        sys.extended_properties ep ON ep.major_id = c.object_id 
                        AND ep.minor_id = c.column_id 
                        AND ep.name = 'MS_Description'
                    LEFT JOIN 
                        sys.index_columns pk ON pk.object_id = c.object_id 
                        AND pk.column_id = c.column_id 
                        AND EXISTS (
                            SELECT 1 FROM sys.indexes i 
                            WHERE i.object_id = pk.object_id 
                            AND i.index_id = pk.index_id 
                            AND i.is_primary_key = 1
                        )
                    LEFT JOIN 
                        sys.foreign_key_columns fk ON fk.parent_object_id = c.object_id 
                        AND fk.parent_column_id = c.column_id
                    WHERE 
                        tbl.name = ? AND s.name = ?
                    ORDER BY 
                        c.column_id
                """
            
            cursor.execute(query, (table_name, schema_name))
            rows = cursor.fetchall()
            
            for row in rows:
                columns.append({
                    "column_name": row.column_name,
                    "data_type": row.data_type,
                    "max_length": row.max_length,
                    "precision": row.precision,
                    "scale": row.scale,
                    "is_nullable": row.is_nullable,
                    "description": row.column_description,
                    "is_primary_key": row.is_primary_key,
                    "is_foreign_key": row.is_foreign_key
                })
                
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error extracting columns for {schema_name}.{table_name}: {e}")
        
        return columns
    
    def extract_relationships(self):
        """Extract all foreign key relationships"""
        relationships = []
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Query to get all foreign key relationships
            query = """
                    SELECT 
                        fk.name AS fk_name,
                        ps.name AS parent_schema,
                        pt.name AS parent_table,
                        pc.name AS parent_column,
                        rs.name AS referenced_schema,
                        rt.name AS referenced_table,
                        rc.name AS referenced_column
                    FROM 
                        sys.foreign_keys fk
                    INNER JOIN 
                        sys.foreign_key_columns fkc ON fk.object_id = fkc.constraint_object_id
                    INNER JOIN 
                        sys.tables pt ON fkc.parent_object_id = pt.object_id
                    INNER JOIN 
                        sys.schemas ps ON pt.schema_id = ps.schema_id
                    INNER JOIN 
                        sys.columns pc ON fkc.parent_object_id = pc.object_id AND fkc.parent_column_id = pc.column_id
                    INNER JOIN 
                        sys.tables rt ON fkc.referenced_object_id = rt.object_id
                    INNER JOIN 
                        sys.schemas rs ON rt.schema_id = rs.schema_id
                    INNER JOIN 
                        sys.columns rc ON fkc.referenced_object_id = rc.object_id AND fkc.referenced_column_id = rc.column_id
                    ORDER BY 
                        ps.name, pt.name, fk.name
                    """
            
            cursor.execute(query)
            rows = cursor.fetchall()
            
            for row in rows:
                relationships.append({
                    "fk_name": row.fk_name,
                    "parent_schema": row.parent_schema,
                    "parent_table": row.parent_table,
                    "parent_column": row.parent_column,
                    "referenced_schema": row.referenced_schema,
                    "referenced_table": row.referenced_table,
                    "referenced_column": row.referenced_column
                })
                
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error extracting relationships: {e}")
        
        return relationships
    
    def extract_sample_data(self, table_name, schema_name="dbo", limit=5):
        """Extract sample data from a table"""
        sample_data = []
        
        try:
            conn = self.get_connection()
            cursor = conn.cursor()
            
            # Query to get sample data
            query = f"SELECT TOP {limit} * FROM [{schema_name}].[{table_name}]"
            
            cursor.execute(query)
            columns = [column[0] for column in cursor.description]
            rows = cursor.fetchall()
            
            for row in rows:
                sample_data.append(dict(zip(columns, row)))
                
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Error extracting sample data for {schema_name}.{table_name}: {e}")
            
        return sample_data
    
    def extract_full_schema(self, include_sample_data=True, sample_data_limit=5):
        """Extract the full database schema with optional sample data"""
        schema = {
            "tables": [],
            "relationships": self.extract_relationships()
        }
        
        tables = self.extract_tables()
        for table in tables:
            table_info = {
                "name": table["table_name"],
                "schema": table["schema_name"],
                "description": table["description"],
                "columns": self.extract_columns(table["table_name"], table["schema_name"])
            }
            
            if include_sample_data:
                table_info["sample_data"] = self.extract_sample_data(
                    table["table_name"], 
                    table["schema_name"],
                    sample_data_limit
                )
                
            schema["tables"].append(table_info)
            
        return schema
    
    def save_schema_to_file(self, filename="schema.json", include_sample_data=True):
        """Extract the schema and save it to a JSON file"""
        schema = self.extract_full_schema(include_sample_data)
        
        with open(filename, 'w') as f:
            json.dump(schema, f, indent=2, default=str)
            
        return filename
    
    def get_formatted_schema_for_prompt(self, include_sample_data=False):
        """Format schema in a way that's optimized for LLM prompts"""
        schema = self.extract_full_schema(include_sample_data, sample_data_limit=2)
        
        formatted_schema = []
        
        # Format tables and columns
        for table in schema["tables"]:
            table_str = f"Table: {table['schema']}.{table['name']}"
            if table["description"]:
                table_str += f" - {table['description']}"
            formatted_schema.append(table_str)
            
            # Add columns
            for column in table["columns"]:
                col_str = f"  - {column['column_name']} ({column['data_type']})"
                
                # Add primary/foreign key indicators
                indicators = []
                if column["is_primary_key"]:
                    indicators.append("PK")
                if column["is_foreign_key"]:
                    indicators.append("FK")
                if indicators:
                    col_str += f" [{', '.join(indicators)}]"
                
                # Add description if available
                if column["description"]:
                    col_str += f" - {column['description']}"
                    
                formatted_schema.append(col_str)
            
            # Add sample data if included
            if include_sample_data and "sample_data" in table and table["sample_data"]:
                formatted_schema.append("  Sample data:")
                for i, row in enumerate(table["sample_data"]):
                    formatted_schema.append(f"    Row {i+1}: {json.dumps(row, default=str)}")
            
            formatted_schema.append("")  # Empty line for readability
        
        # Format relationships
        formatted_schema.append("Relationships:")
        for rel in schema["relationships"]:
            rel_str = (f"  - {rel['parent_schema']}.{rel['parent_table']}.{rel['parent_column']} → "
                      f"{rel['referenced_schema']}.{rel['referenced_table']}.{rel['referenced_column']}")
            formatted_schema.append(rel_str)
        
        return "\n".join(formatted_schema)


if __name__ == "__main__":
    # Example usage
    extractor = SchemaExtractor()
    
    # Save full schema to file
    schema_file = extractor.save_schema_to_file("adventure_works_schema.json", include_sample_data=True)
    print(f"Schema saved to {schema_file}")
    
    # Get formatted schema for prompt
    formatted_schema = extractor.get_formatted_schema_for_prompt(include_sample_data=False)
    print("Formatted Schema for Prompt:")
    print(formatted_schema)