import React, { useState, useEffect } from "react";
import "./styles/App.css";
import DeploymentForm from "./components/DeploymentForm";
import AgentActivityPanel from "./components/AgentActivityPanel";
import CredentialsPanel from "./components/CredentialsPanel";
import ActiveLogsViewer from "./components/ActiveLogsViewer";

const API_BASE_URL = "http://16.16.128.193:8000";

export default function App() {
  const [currentView, setCurrentView] = useState("home"); // home, deploy, monitoring
  const [sessionId, setSessionId] = useState(null);
  const [isDeploying, setIsDeploying] = useState(false);
  const [deploymentStatus, setDeploymentStatus] = useState(null);
  const [error, setError] = useState(null);
  const [apiHealth, setApiHealth] = useState(null);

  // Check API health on mount
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const response = await fetch(`${API_BASE_URL}/api/health`);
        if (response.ok) {
          const data = await response.json();
          setApiHealth(data);
        } else {
          setApiHealth({ status: "error", message: "API not responding" });
        }
      } catch (err) {
        setApiHealth({ status: "error", message: err.message });
      }
    };
    checkHealth();
  }, []);

  const handleDeploy = async (formData) => {
    setIsDeploying(true);
    setError(null);
    
    try {
      const response = await fetch(`${API_BASE_URL}/api/multi-agent/deploy`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });

      if (!response.ok) {
        throw new Error(`Deployment failed: ${response.statusText}`);
      }

      const data = await response.json();
      setSessionId(data.session_id);
      setDeploymentStatus(data);
      setCurrentView("monitoring");
    } catch (err) {
      setError(err.message);
      console.error("Deployment error:", err);
    } finally {
      setIsDeploying(false);
    }
  };

  const resetDeployment = () => {
    setSessionId(null);
    setDeploymentStatus(null);
    setCurrentView("home");
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="app-header">
        <div className="header-content">
          <h1>🤖 DevOps AI Automator</h1>
          <p className="tagline">Multi-Agent AI-Powered DevOps Orchestration</p>
        </div>
        <div className="header-status">
          {apiHealth && (
            <div className={`api-status ${apiHealth.status}`}>
              <span className="status-indicator"></span>
              {apiHealth.status === "ok" ? "🟢 Connected" : "🔴 Offline"}
            </div>
          )}
        </div>
      </header>

      {/* Navigation */}
      <nav className="app-nav">
        <button
          className={`nav-btn ${currentView === "home" ? "active" : ""}`}
          onClick={() => setCurrentView("home")}
        >
          🏠 Home
        </button>
        <button
          className={`nav-btn ${currentView === "deploy" ? "active" : ""}`}
          onClick={() => setCurrentView("deploy")}
        >
          🚀 Deploy
        </button>
        {sessionId && (
          <button
            className={`nav-btn ${currentView === "monitoring" ? "active" : ""}`}
            onClick={() => setCurrentView("monitoring")}
          >
            📊 Monitoring
          </button>
        )}
      </nav>

      {/* Main Content */}
      <main className="app-main">
        {/* Home View */}
        {currentView === "home" && (
          <div className="view home-view">
            <div className="hero">
              <h2>Welcome to DevOps AI Automator</h2>
              <p>
                Automate your entire DevOps pipeline with 4 specialized AI agents working
                together to analyze, plan, execute, and validate your deployments.
              </p>

              <div className="features">
                <div className="feature-card">
                  <div className="feature-icon">🔍</div>
                  <h3>Agent 1: Repository Analyzer</h3>
                  <p>Scans your repo, detects app type, extracts dependencies</p>
                </div>

                <div className="feature-card">
                  <div className="feature-icon">📋</div>
                  <h3>Agent 2: Pipeline Commander</h3>
                  <p>Creates optimized 7-stage deployment pipeline</p>
                </div>

                <div className="feature-card">
                  <div className="feature-icon">⚙️</div>
                  <h3>Agent 3: Execution Solver</h3>
                  <p>Executes with AI error recovery and LLM logging</p>
                </div>

                <div className="feature-card">
                  <div className="feature-icon">✅</div>
                  <h3>Agent 4: Validator</h3>
                  <p>Validates deployment and learns from outcomes</p>
                </div>
              </div>

              <div className="system-features">
                <div className="feature-item">
                  <span className="check">✓</span>
                  <span>Auto-Generated Credentials (never ask user)</span>
                </div>
                <div className="feature-item">
                  <span className="check">✓</span>
                  <span>Real-Time WebSocket Streaming</span>
                </div>
                <div className="feature-item">
                  <span className="check">✓</span>
                  <span>Complete LLM Interaction Logging</span>
                </div>
                <div className="feature-item">
                  <span className="check">✓</span>
                  <span>AI-Powered Error Recovery</span>
                </div>
                <div className="feature-item">
                  <span className="check">✓</span>
                  <span>Learning System (improves over time)</span>
                </div>
                <div className="feature-item">
                  <span className="check">✓</span>
                  <span>Production-Ready</span>
                </div>
              </div>

              <button className="cta-btn" onClick={() => setCurrentView("deploy")}>
                🚀 Start Deployment
              </button>
            </div>
          </div>
        )}

        {/* Deploy View */}
        {currentView === "deploy" && (
          <div className="view deploy-view">
            <DeploymentForm onDeploy={handleDeploy} isLoading={isDeploying} />
            {error && (
              <div className="error-message">
                <span className="error-icon">⚠️</span>
                {error}
              </div>
            )}
            {deploymentStatus && (
              <div className="success-message">
                <span className="success-icon">✓</span>
                Deployment started! Session: {deploymentStatus.session_id}
              </div>
            )}
          </div>
        )}

        {/* Monitoring View */}
        {currentView === "monitoring" && sessionId && (
          <div className="view monitoring-view">
            <div className="monitoring-header">
              <div>
                <h2>📊 Live Monitoring Dashboard</h2>
                <p>Session ID: {sessionId}</p>
              </div>
              <button className="reset-btn" onClick={resetDeployment}>
                ↺ New Deployment
              </button>
            </div>

            <div className="monitoring-grid">
              <div className="monitoring-section credentials-section">
                <CredentialsPanel sessionId={sessionId} apiBase={API_BASE_URL} />
              </div>

              <div className="monitoring-section activity-section">
                <AgentActivityPanel sessionId={sessionId} apiBase={API_BASE_URL} />
              </div>

              <div className="monitoring-section logs-section">
                <ActiveLogsViewer sessionId={sessionId} apiBase={API_BASE_URL} />
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <p>DevOps AI Automator • Multi-Agent Deployment Platform • Powered by Claude & Ollama</p>
      </footer>
    </div>
  );
}
