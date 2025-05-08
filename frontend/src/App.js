// App.js
import React, { useState } from "react";
import axios from "axios";
import "./App.css";
import SqlEditor from "./SqlEditor";
import FeedbackComponent from "./FeedbackComponent";

const API_URL = "http://localhost:8000"; // Make sure this matches your backend port

function App() {
  const [question, setQuestion] = useState("");
  const [sql, setSql] = useState("");
  const [explanation, setExplanation] = useState("");
  const [results, setResults] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [executionTime, setExecutionTime] = useState(null);
  const [feedbackGiven, setFeedbackGiven] = useState(false);
  const [retryCount, setRetryCount] = useState(0);
  const [validationResult, setValidationResult] = useState(null);
  const [showExecuteButton, setShowExecuteButton] = useState(false);

  // Sample questions for quick selection
  const sampleQuestions = [
    "Top 5 Customers by Total Purchase Amount",
    "Products with No Sales in the Last 6 Months",
    "List Employees Hired in the Last 5 Years",
    "Average Order Quantity by Product Category",
    "Employees with Above-Average Salaries",
  ];

  const handleSubmit = async (e) => {
    e.preventDefault();
    console.log("Submit button clicked");
    console.log("Question:", question);

    if (!question.trim()) return;

    setLoading(true);
    setError("");
    setSql("");
    setExplanation("");
    setResults([]);
    setExecutionTime(null);
    setFeedbackGiven(false);
    setRetryCount(0); // Reset retry count
    setValidationResult(null);
    setShowExecuteButton(false);

    try {
      console.log("Making API request to:", `${API_URL}/query`);
      const response = await axios.post(`${API_URL}/generate-sql`, {
        question,
      });
      console.log("API response:", response.data);

      setSql(response.data.sql);
      setExplanation(response.data.explanation);
      setValidationResult(response.data.validation_result);
      setShowExecuteButton(true);

      // If the validation result indicates it's valid, show execute button
      if (
        response.data.validation_result &&
        response.data.validation_result.is_valid
      ) {
        setShowExecuteButton(true);
      }

      setLoading(false);
    } catch (err) {
      console.error("API error:", err);
      setError("Error generating SQL query. Please try again.");
      setLoading(false);
    }
  };

  const executeQuery = async (customSql = null) => {
    const sqlToExecute = customSql || sql;

    if (!sqlToExecute.trim()) {
      setError("No SQL query to execute");
      return;
    }

    setLoading(true);
    setError("");
    setResults([]);
    setExecutionTime(null);

    try {
      console.log("Executing SQL:", sqlToExecute);
      const response = await axios.post(`${API_URL}/execute-sql`, {
        sql: sqlToExecute,
      });

      console.log("Execution response:", response.data);
      setResults(response.data.results || []);
      setExecutionTime(response.data.execution_time);

      if (response.data.error) {
        setError(response.data.error);
      }

      // Track retries if they happened
      if (response.headers["x-retry-count"]) {
        setRetryCount(parseInt(response.headers["x-retry-count"]));
      }
    } catch (err) {
      console.error("Execution error:", err);
      setError(
        err.response?.data?.detail ||
          "Error executing SQL query. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const handleSampleQuestion = (sample) => {
    console.log("Sample question selected:", sample);
    setQuestion(sample);
  };

  const handleFeedback = async (feedbackData) => {
    try {
      await axios.post(`${API_URL}/feedback`, {
        question: question,
        sql: sql,
        is_correct: feedbackData.is_correct,
        corrected_sql: feedbackData.corrected_sql,
        additional_feedback: feedbackData.additional_feedback,
      });
      setFeedbackGiven(true);
    } catch (err) {
      console.error("Error sending feedback:", err);
    }
  };

  // Function to render the results table
  const renderResultsTable = () => {
    if (!results || results.length === 0) return null;

    // Get column names from the first result object
    const columns = Object.keys(results[0]);

    return (
      <div className="results-table-container">
        <h3>Query Results ({results.length} rows)</h3>
        <table className="results-table">
          <thead>
            <tr>
              {columns.map((column, index) => (
                <th key={index}>{column}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {results.map((row, rowIndex) => (
              <tr key={rowIndex}>
                {columns.map((column, colIndex) => (
                  <td key={colIndex}>
                    {row[column] !== null ? row[column] : "NULL"}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  };

  return (
    <div className="app-container">
      <header>
        <h1>Text-to-SQL Assistant</h1>
        <p>Ask questions about your data in natural language</p>
      </header>

      <main>
        <section className="query-section">
          <form onSubmit={handleSubmit}>
            <div className="input-container">
              <input
                type="text"
                value={question}
                onChange={(e) => setQuestion(e.target.value)}
                placeholder="Ask a question about your data..."
                className="question-input"
              />
              <button
                type="submit"
                className="submit-button"
                disabled={loading}
              >
                {loading && !showExecuteButton
                  ? "Generating..."
                  : "Generate SQL"}
              </button>
            </div>
          </form>

          <div className="sample-questions">
            <h3>Sample Questions:</h3>
            <div className="sample-buttons">
              {sampleQuestions.map((sample, index) => (
                <button
                  key={index}
                  onClick={(e) => {
                    e.preventDefault();
                    e.stopPropagation();
                    handleSampleQuestion(sample);
                  }}
                  className="sample-button"
                >
                  {sample}
                </button>
              ))}
            </div>
          </div>
        </section>

        {sql && (
          <section className="results-section">
            {retryCount > 0 && (
              <div className="retry-info">
                <p>
                  The system had to correct the SQL {retryCount}{" "}
                  {retryCount === 1 ? "time" : "times"} due to errors.
                </p>
              </div>
            )}

            <SqlEditor
              initialSql={sql}
              onExecute={executeQuery}
              isReadOnly={false}
              validationResult={validationResult}
              isLoading={loading}
            />

            {explanation && (
              <div className="explanation-container">
                <h3>Explanation</h3>
                <p>{explanation}</p>
              </div>
            )}

            {showExecuteButton &&
              validationResult?.is_valid &&
              !loading &&
              !results.length && (
                <div className="execute-container">
                  <button
                    className="execute-main-button"
                    onClick={() => executeQuery()}
                    disabled={loading}
                  >
                    {loading ? "Executing..." : "Execute SQL Query"}
                  </button>
                </div>
              )}

            {executionTime && (
              <div className="execution-time">
                <p>Query executed in {executionTime.toFixed(3)} seconds</p>
              </div>
            )}

            {error && (
              <div className="error-container">
                <h3>Error</h3>
                <p>{error}</p>
              </div>
            )}

            {renderResultsTable()}

            {results && results.length > 0 && !feedbackGiven && (
              <FeedbackComponent
                question={question}
                sql={sql}
                onSubmit={handleFeedback}
              />
            )}
          </section>
        )}
      </main>

      <footer>
        <p>Text-to-SQL Assistant &copy; 2025</p>
      </footer>
    </div>
  );
}

export default App;
