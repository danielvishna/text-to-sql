// SqlEditor.js - Add this as a new file in your frontend/src directory
import React, { useState, useEffect } from "react";
import SyntaxHighlighter from "react-syntax-highlighter";
import { docco } from "react-syntax-highlighter/dist/esm/styles/hljs";
import "./SqlEditor.css";

const SqlEditor = ({
  initialSql,
  onExecute,
  isReadOnly = false,
  validationResult = null,
  isLoading = false,
}) => {
  const [sql, setSql] = useState(initialSql || "");
  const [isEditing, setIsEditing] = useState(false);

  useEffect(() => {
    setSql(initialSql || "");
  }, [initialSql]);

  const handleEdit = () => {
    setIsEditing(true);
  };

  const handleCancel = () => {
    setSql(initialSql);
    setIsEditing(false);
  };

  const handleExecute = () => {
    onExecute(sql);
    setIsEditing(false);
  };

  const renderValidationBadges = () => {
    if (!validationResult) return null;

    return (
      <div className="validation-badges">
        {validationResult.is_valid ? (
          <span className="badge success">Valid SQL</span>
        ) : (
          <span className="badge error">
            Invalid SQL: {validationResult.error}
          </span>
        )}

        {validationResult.warnings.map((warning, index) => (
          <span key={index} className="badge warning">
            {warning}
          </span>
        ))}
      </div>
    );
  };

  return (
    <div className="sql-editor-container">
      <div className="sql-editor-header">
        <h3>SQL Query</h3>
        {!isReadOnly && (
          <div className="sql-editor-actions">
            {!isEditing ? (
              <button className="edit-button" onClick={handleEdit}>
                Edit SQL
              </button>
            ) : (
              <>
                <button className="cancel-button" onClick={handleCancel}>
                  Cancel
                </button>
                <button
                  className="execute-button"
                  onClick={handleExecute}
                  disabled={isLoading}
                >
                  {isLoading ? "Executing..." : "Execute SQL"}
                </button>
              </>
            )}
          </div>
        )}
      </div>

      {renderValidationBadges()}

      {isEditing ? (
        <textarea
          className="sql-textarea"
          value={sql}
          onChange={(e) => setSql(e.target.value)}
          rows={sql.split("\n").length + 2}
          spellCheck="false"
          autoFocus
        />
      ) : (
        <SyntaxHighlighter
          language="sql"
          style={docco}
          className="sql-code"
          wrapLines={true}
        >
          {sql}
        </SyntaxHighlighter>
      )}

      {isEditing && (
        <div className="editor-footer">
          <p className="editor-info">
            <strong>Tip:</strong> Edit the SQL query directly to customize or
            fix it. Only SELECT statements are allowed.
          </p>
        </div>
      )}
    </div>
  );
};

export default SqlEditor;
