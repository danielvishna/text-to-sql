// FeedbackComponent.js - Add this as a new file in your frontend/src directory
import React, { useState } from "react";
import "./FeedbackComponent.css";

const FeedbackComponent = ({ question, sql, onSubmit }) => {
  const [isCorrect, setIsCorrect] = useState(null);
  const [correctedSql, setCorrectedSql] = useState("");
  const [additionalFeedback, setAdditionalFeedback] = useState("");
  const [feedbackSubmitted, setFeedbackSubmitted] = useState(false);
  const [showTextarea, setShowTextarea] = useState(false);

  const handleYesClick = () => {
    setIsCorrect(true);
    setShowTextarea(false);
  };

  const handleNoClick = () => {
    setIsCorrect(false);
    setShowTextarea(true);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    onSubmit({
      is_correct: isCorrect,
      corrected_sql: isCorrect ? null : correctedSql,
      additional_feedback: additionalFeedback,
    });
    setFeedbackSubmitted(true);
  };

  if (feedbackSubmitted) {
    return (
      <div className="feedback-message">
        <h4>Thank you for your feedback!</h4>
        <p>Your input helps improve the system for everyone.</p>
      </div>
    );
  }

  return (
    <div className="feedback-container">
      <h4>Was this SQL correct and helpful?</h4>

      <div className="feedback-buttons">
        <button
          className={`feedback-button ${isCorrect === true ? "selected" : ""}`}
          onClick={handleYesClick}
        >
          Yes, it was helpful
        </button>
        <button
          className={`feedback-button negative ${
            isCorrect === false ? "selected" : ""
          }`}
          onClick={handleNoClick}
        >
          No, it needs improvement
        </button>
      </div>

      {isCorrect !== null && (
        <form onSubmit={handleSubmit} className="feedback-form">
          {showTextarea && (
            <div className="feedback-field">
              <label htmlFor="corrected-sql">Corrected SQL (optional):</label>
              <textarea
                id="corrected-sql"
                value={correctedSql}
                onChange={(e) => setCorrectedSql(e.target.value)}
                placeholder="If you know the correct SQL, please provide it here..."
                rows={5}
              />
            </div>
          )}

          <div className="feedback-field">
            <label htmlFor="additional-feedback">
              Additional comments (optional):
            </label>
            <textarea
              id="additional-feedback"
              value={additionalFeedback}
              onChange={(e) => setAdditionalFeedback(e.target.value)}
              placeholder="Any other thoughts or suggestions..."
              rows={3}
            />
          </div>

          <button type="submit" className="feedback-submit">
            Submit Feedback
          </button>
        </form>
      )}
    </div>
  );
};

export default FeedbackComponent;
