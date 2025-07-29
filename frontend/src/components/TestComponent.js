import React from 'react';

/**
 * Test component to trigger CI/CD pipeline
 * This component is created to test the GitHub Actions workflows
 */
const TestComponent = () => {
  return (
    <div className="test-component">
      <h2>🚀 CI/CD Pipeline Test</h2>
      <p>This component was created to test the deployment pipeline.</p>
      <div className="status">
        <span className="status-indicator">✅</span>
        <span>Pipeline Active</span>
      </div>
    </div>
  );
};

export default TestComponent;