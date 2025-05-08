from fastapi import FastAPI, HTTPException, Body, Depends, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import os
import sys
import pyodbc
import json
import time
import logging
from dotenv import load_dotenv
import openai
from schema_extractor import SchemaExtractor
import sql_validator
# Initialize FastAPI app
app = FastAPI(
    title="Text-to-SQL API",
    description="API for converting natural language to SQL queries",
    version="1.0.0"
)
app.state.db_metadata = sql_validator.refresh_schemas_and_columns()

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logger.info(f"Loaded database metadata: {len(app.state.db_metadata['schemas'])} schemas, {len(app.state.db_metadata['tables'])} tables")


# Check for OpenAI API key
def check_openai_api_key():
    """
    Checks if the OpenAI API key is set in the environment variables.
    Exits if the key is not set.
    """
    if "OPENAI_API_KEY" not in os.environ:
        logging.error("Error: OpenAI API key is not set.")
        logging.error("Please set the environment variable 'OPENAI_API_KEY' with your OpenAI API key.")
        sys.exit()
    # Set your OpenAI API key
    openai.api_key = os.environ["OPENAI_API_KEY"]

check_openai_api_key()



# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define models
class QueryRequest(BaseModel):
    question: str

class ExecuteSqlRequest(BaseModel):
    sql: str

class FeedbackRequest(BaseModel):
    question: str
    sql: str
    is_correct: bool
    corrected_sql: Optional[str] = None
    additional_feedback: Optional[str] = None

class SqlGenerationResponse(BaseModel):
    sql: str
    explanation: str
    validation_result: Dict[str, Any]

class ExecutionResponse(BaseModel):
    results: Optional[List[Dict[str, Any]]] = None
    execution_time: Optional[float] = None
    error: Optional[str] = None
    retry_count: Optional[int] = None

# Database connection
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
        raise HTTPException(status_code=500, detail=f"Database connection error: {str(e)}")

# Load schema information
@app.on_event("startup")
async def startup_event():
    try:
        # Check if schema file exists
        schema_file = "adventure_works_schema.json"
        if not os.path.exists(schema_file):
            logger.info("Schema file not found. Extracting schema...")
            extractor = SchemaExtractor()
            extractor.save_schema_to_file(schema_file, include_sample_data=True)
            logger.info(f"Schema saved to {schema_file}")
        
        # Load schema for prompts
        app.state.extractor = SchemaExtractor()
        app.state.schema_for_prompt = app.state.extractor.get_formatted_schema_for_prompt(include_sample_data=False)
        logger.info("Schema loaded for prompts")
        
        # Generate few-shot examples
        app.state.examples = generate_few_shot_examples()
        logger.info("Few-shot examples generated")
        
        # Initialize the SQL validator
        import sql_validator
        app.state.db_metadata = sql_validator.refresh_schemas_and_columns()
        logger.info(f"Loaded database metadata: {len(app.state.db_metadata['schemas'])} schemas, {len(app.state.db_metadata['tables'])} tables")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        # Continue startup even if schema extraction fails

def generate_few_shot_examples():
    """Generate few-shot examples for the prompt"""
    return """
            Example 1:
            Question: Show me the top 5 customers by total purchase amount
            SQL: 
            SELECT TOP 5 
                c.CustomerID,
                CONCAT(p.FirstName, ' ', p.LastName) AS CustomerName,
                SUM(soh.TotalDue) AS TotalPurchaseAmount
            FROM 
                Sales.Customer c
                JOIN Person.Person p ON c.PersonID = p.BusinessEntityID
                JOIN Sales.SalesOrderHeader soh ON c.CustomerID = soh.CustomerID
            GROUP BY 
                c.CustomerID, CONCAT(p.FirstName, ' ', p.LastName)
            ORDER BY 
                SUM(soh.TotalDue) DESC;

            Example 2:
            Question: Products with no sales in the last 6 months
            SQL:
            SELECT 
                p.ProductID,
                p.Name AS ProductName
            FROM 
                Production.Product p
            WHERE 
                p.ProductID NOT IN (
                    SELECT DISTINCT 
                        sd.ProductID
                    FROM 
                        Sales.SalesOrderDetail sd
                        JOIN Sales.SalesOrderHeader sh ON sd.SalesOrderID = sh.SalesOrderID
                    WHERE 
                        sh.OrderDate >= DATEADD(MONTH, -6, GETDATE())
                );

            Example 3:
            Question: List employees hired in the last 5 years
            SQL:
            SELECT 
                e.BusinessEntityID,
                p.FirstName,
                p.LastName,
                e.HireDate
            FROM 
                HumanResources.Employee e
                JOIN Person.Person p ON e.BusinessEntityID = p.BusinessEntityID
            WHERE 
                e.HireDate >= DATEADD(YEAR, -5, GETDATE())
            ORDER BY 
                e.HireDate DESC;

            Example 4:
            Question: Average order quantity by product category
            SQL:
            SELECT 
                pc.Name AS CategoryName,
                AVG(sod.OrderQty) AS AverageOrderQuantity
            FROM 
                Production.ProductCategory pc
                JOIN Production.ProductSubcategory psc ON pc.ProductCategoryID = psc.ProductCategoryID
                JOIN Production.Product p ON psc.ProductSubcategoryID = p.ProductSubcategoryID
                JOIN Sales.SalesOrderDetail sod ON p.ProductID = sod.ProductID
            GROUP BY 
                pc.Name
            ORDER BY 
                pc.Name;
            """

def generate_prompt(question: str):
    """Generate a prompt for the OpenAI API"""
    return f"""You are a SQL expert assistant that converts natural language questions to SQL queries for the AdventureWorks database.

            Database Schema:
            {app.state.schema_for_prompt}

            Examples:
            {app.state.examples}

            User Question: "{question}"

            Generate a SQL query that answers this question. The query should be syntactically correct for ODBC Driver 17 for SQL Server. Format your response as follows:

            SQL: <the SQL query>

            Explanation: <brief explanation of the query>

            Remember these important security guidelines:
            1. Only write SELECT statements (no INSERT, UPDATE, DELETE, DROP, etc.)
            2. Never include multiple statements (no semicolons followed by another statement)
            3. Never use comments (no -- or /* */)
            4. Always use the proper AdventureWorks schema prefixes (Person, HumanResources, Production, Sales)

            Do not include any other text in your response.
            """

async def generate_sql(question: str):
    """Generate SQL from natural language using OpenAI"""
    try:
        prompt = generate_prompt(question)
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",  # Or your preferred model
            messages=[
                {"role": "system", "content": "You are a SQL expert that converts natural language questions to SQL queries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  # Lower temperature for more deterministic outputs
            max_tokens=1000
        )
        
        # Extract SQL and explanation from response
        content = response.choices[0].message.content.strip()
        
        # Parse the output to extract SQL and explanation
        sql = ""
        explanation = ""
        
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("SQL:"):
                sql = "\n".join(lines[i+1:])
                sql = sql.split("Explanation:")[0].strip()
                break
        
        for i, line in enumerate(lines):
            if line.startswith("Explanation:"):
                explanation = "\n".join(lines[i+1:]).strip()
                break
        
        # Validate the generated SQL
        import sql_validator
        validation_result = sql_validator.get_sql_analysis(sql)
        
        return sql, explanation, validation_result
    except Exception as e:
        logger.error(f"Error generating SQL: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating SQL: {str(e)}")
    
async def generate_sql_with_feedback(question: str, previous_sql: str, error: str):
    """Generate improved SQL based on error feedback"""
    try:
        prompt = f"""You are a SQL expert assistant that converts natural language questions to SQL queries for the AdventureWorks database.

            Database Schema:
            {app.state.schema_for_prompt}

            User Question: "{question}"

            Previous SQL Attempt:
            {previous_sql}

            Error Received:
            {error}

            Please generate a corrected SQL query that fixes this error. The query should be syntactically correct for ODBC Driver 17 for SQL Server. Format your response as follows:

            SQL: <the corrected SQL query>

            Explanation: <brief explanation of what was wrong and how you fixed it>

            Remember these important security guidelines:
            1. Only write SELECT statements (no INSERT, UPDATE, DELETE, DROP, etc.)
            2. Never include multiple statements (no semicolons followed by another statement)
            3. Never use comments (no -- or /* */)
            4. Always use the proper AdventureWorks schema prefixes (Person, HumanResources, Production, Sales)

            Do not include any other text in your response.
            """
        
        response = await openai.ChatCompletion.acreate(
            model="gpt-3.5-turbo",  # Or your preferred model
            messages=[
                {"role": "system", "content": "You are a SQL expert that fixes incorrect SQL queries."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,  # Lower temperature for more deterministic outputs
            max_tokens=1000
        )
        
        # Extract SQL and explanation from response
        content = response.choices[0].message.content.strip()
        
        # Parse the output to extract SQL and explanation
        sql = ""
        explanation = ""
        
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith("SQL:"):
                sql = "\n".join(lines[i+1:])
                sql = sql.split("Explanation:")[0].strip()
                break
        
        for i, line in enumerate(lines):
            if line.startswith("Explanation:"):
                explanation = "\n".join(lines[i+1:]).strip()
                break
        
        return sql, explanation
    except Exception as e:
        logger.error(f"Error generating SQL with feedback: {e}")
        raise HTTPException(status_code=500, detail=f"Error generating SQL with feedback: {str(e)}")

def execute_sql(sql: str):
    """Execute SQL query and return results"""
    try:
        # Check if it's a SELECT statement first
        if not sql_validator.is_select_statement(sql):
            return None, None, "Only SELECT statements are allowed for security reasons"
            
        # Use Windows Authentication
        connection_string = (
           f"""
    DRIVER={{ODBC Driver 17 for SQL Server}};
    SERVER={os.getenv('DB_SERVER')};
    DATABASE={os.getenv('DB_NAME')};
    UID={os.getenv('DB_USER')};
    PWD={os.getenv('DB_PASSWORD')};
"""
        )
        
        conn = pyodbc.connect(connection_string)
        cursor = conn.cursor()
        
        start_time = time.time()
        cursor.execute(sql)
        execution_time = time.time() - start_time
        
        # Get column names
        columns = [column[0] for column in cursor.description]
        
        # Fetch results
        results = []
        for row in cursor.fetchall():
            results.append(dict(zip(columns, [str(x) if isinstance(x, (bytes, bytearray)) else x for x in row])))
        
        cursor.close()
        conn.close()
        
        return results, execution_time, None  # Return None for error
    except Exception as e:
        logger.error(f"Error executing SQL: {e}")
        return None, None, str(e)  # Return the error as a string

@app.post("/generate-sql", response_model=SqlGenerationResponse)
async def generate_sql_endpoint(request: QueryRequest):
    """Generate SQL from natural language question without executing it"""
    try:
        # Generate SQL from natural language
        sql, explanation, validation_result = await generate_sql(request.question)
        
        return {
            "sql": sql,
            "explanation": explanation,
            "validation_result": validation_result
        }
    except Exception as e:
        logger.error(f"Error generating SQL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/execute-sql", response_model=ExecutionResponse)
async def execute_sql_endpoint(request: ExecuteSqlRequest, response: Response):
    """Execute the provided SQL query"""
    max_attempts = 3  # Maximum number of retry attempts
    attempt = 0
    
    while attempt < max_attempts:
        attempt += 1
        try:
            # Validate the SQL first
            validation_result = sql_validator.get_sql_analysis(request.sql)
            if not validation_result["is_valid"]:
                return {
                    "results": None,
                    "execution_time": None,
                    "error": f"Invalid SQL: {validation_result['error']}",
                    "retry_count": 0
                }
            
            # Execute the SQL
            results, execution_time, error = execute_sql(request.sql)
            
            # If there's an error and we have attempts left, try to correct the SQL
            if error and attempt < max_attempts:
                # Generate corrected SQL based on the error
                logger.info(f"Attempt {attempt}: Retrying with error feedback")
                question = "Fix the SQL query"  # Generic placeholder since we don't have the original question
                sql, explanation = await generate_sql_with_feedback(question, request.sql, error)
                request.sql = sql  # Update the SQL for the next attempt
                continue  # Continue to the next attempt with the corrected SQL
            
            # Add retry count header
            if attempt > 1:
                response.headers["X-Retry-Count"] = str(attempt - 1)
            
            return {
                "results": results,
                "execution_time": execution_time,
                "error": error,
                "retry_count": attempt - 1 if attempt > 1 else 0
            }
        except Exception as e:
            logger.error(f"Error executing SQL: {e}")
            if attempt >= max_attempts:
                return {
                    "results": None,
                    "execution_time": None,
                    "error": str(e),
                    "retry_count": attempt - 1
                }
            # If we have attempts left, try again

@app.post("/query")
async def legacy_query_endpoint(request: QueryRequest, response: Response):
    """
    Legacy endpoint for backward compatibility
    Generates and executes SQL in a single step
    """
    try:
        # Generate SQL
        sql, explanation, validation_result = await generate_sql(request.question)
        
        if not validation_result["is_valid"]:
            return {
                "sql": sql,
                "explanation": explanation,
                "results": None,
                "execution_time": None,
                "error": f"Invalid SQL: {validation_result['error']}"
            }
        
        # Execute SQL
        results, execution_time, error = execute_sql(sql)
        
        return {
            "sql": sql,
            "explanation": explanation,
            "results": results,
            "execution_time": execution_time,
            "error": error
        }
    except Exception as e:
        logger.error(f"Error in legacy query endpoint: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/feedback")
async def feedback(request: FeedbackRequest):
    """Store feedback for improving the system"""
    try:
        # In a real system, store feedback in a database
        # For this prototype, just log it
        logger.info(f"Feedback received: {request.dict()}")
        
        # Store feedback in a JSON file for analysis
        try:
            feedback_file = "feedback_data.json"
            
            # Load existing feedback if the file exists
            if os.path.exists(feedback_file):
                with open(feedback_file, 'r') as f:
                    feedback_data = json.load(f)
            else:
                feedback_data = []
            
            # Add the new feedback
            feedback_data.append({
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "question": request.question,
                "sql": request.sql,
                "is_correct": request.is_correct,
                "corrected_sql": request.corrected_sql,
                "additional_feedback": request.additional_feedback
            })
            
            # Save the updated feedback
            with open(feedback_file, 'w') as f:
                json.dump(feedback_data, f, indent=2)
            
            logger.info(f"Feedback saved to {feedback_file}")
        except Exception as e:
            logger.error(f"Error saving feedback to file: {e}")
        
        # Return success message
        return {"message": "Feedback received successfully"}
    except Exception as e:
        logger.error(f"Error processing feedback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Check if the API is running"""
    return {"status": "OK"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ["API_PORT"]))