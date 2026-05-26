import React, { useState, useEffect, useRef } from "react";
import "../styles/AgentActivityPanel.css";

/**
 * AgentActivityPanel - Real-time display of multi-agent orchestration activity
 * Shows agent actions and LLM interactions with full observability
 */
function AgentActivityPanel({ sessionId, apiBase = "http://localhost:8000" }) {
  const [activities, setActivities] = useState([]);
  const [llmInteractions, setLlmInteractions] = useState([]);
  const [selectedAgent, setSelectedAgent] = useState("all");
  const [expandedItems, setExpandedItems] = useState({});
  const [activeTab, setActiveTab] = useState("activities");
  const containerRef = useRef(null);

  useEffect(() => {
    if (!sessionId) return;

    const wsUrl = apiBase.replace(/^http/, "ws");
    const ws = new WebSocket(`${wsUrl}/ws/agent-activity/${sessionId}`);

    ws.onopen = () => {
      console.log("[WS] Connected to agent activity stream");
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        if (data.type === "agent_message") {
          setActivities((prev) => [data, ...prev].slice(0, 200));
        } else if (data.type === "llm_interaction") {
          setLlmInteractions((prev) => [data, ...prev].slice(0, 100));
        }
      } catch (error) {
        console.error("[WS] Error parsing message:", error);
      }
    };

    ws.onerror = (error) => {
      console.error("[WS] WebSocket error:", error);
    };

    ws.onclose = () => {
      console.log("[WS] Disconnected from agent activity stream");
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [sessionId]);

  const getAgentColor = (agent) => {
    const colors = {
      RepositoryAnalyzer: "#00d4ff",
      PipelineCommander: "#00ff88",
      ExecutionSolver: "#cc44ff",
      ValidatorSelector: "#ffaa00",
      Orchestrator: "#ff0066",
    };
    return colors[agent] || "#8899bb";
  };

  const getAgentEmoji = (agent) => {
    const emojis = {
      RepositoryAnalyzer: "🔍",
      PipelineCommander: "📋",
      ExecutionSolver: "⚙️",
      ValidatorSelector: "✅",
      Orchestrator: "🧠",
    };
    return emojis[agent] || "🤖";
  };

  const toggleExpand = (id, type) => {
    setExpandedItems((prev) => ({
      ...prev,
      [`${type}_${id}`]: !prev[`${type}_${id}`],
    }));
  };

  const filteredActivities =
    selectedAgent === "all"
      ? activities
      : activities.filter((a) => a.agent === selectedAgent);

  return (
    <div
      style={{
        background: "#0a0a1a",
        border: "1px solid #0d2a4a",
        borderRadius: "8px",
        height: "100%",
        display: "flex",
        flexDirection: "column",
        fontFamily: "'Courier New', monospace",
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "12px 16px",
          borderBottom: "1px solid #0d2a4a",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          background: "linear-gradient(90deg, #0a0a1a 0%, #0d1a2a 100%)",
        }}
      >
        <div>
          <span
            style={{
              fontFamily: "'Orbitron', 'Courier New', monospace",
              fontSize: "12px",
              color: "#00d4ff",
              fontWeight: "bold",
              letterSpacing: "2px",
            }}
          >
            🧠 MULTI-AGENT ORCHESTRATOR
          </span>
          <div
            style={{ fontSize: "10px", color: "#334466", marginTop: "4px" }}
          >
            Session: {sessionId ? sessionId.substring(0, 8) + "..." : "N/A"}
          </div>
        </div>

        <select
          value={selectedAgent}
          onChange={(e) => setSelectedAgent(e.target.value)}
          style={{
            background: "#0d1a2a",
            border: "1px solid #0d3a5a",
            color: "#ccd6f6",
            padding: "6px 10px",
            borderRadius: "4px",
            fontSize: "11px",
            cursor: "pointer",
          }}
        >
          <option value="all">All Agents ({activities.length})</option>
          <option value="RepositoryAnalyzer">
            🔍 Agent 1: Analyzer ({activities.filter((a) => a.agent === "RepositoryAnalyzer").length})
          </option>
          <option value="PipelineCommander">
            📋 Agent 2: Commander ({activities.filter((a) => a.agent === "PipelineCommander").length})
          </option>
          <option value="ExecutionSolver">
            ⚙️ Agent 3: Solver ({activities.filter((a) => a.agent === "ExecutionSolver").length})
          </option>
          <option value="ValidatorSelector">
            ✅ Agent 4: Validator ({activities.filter((a) => a.agent === "ValidatorSelector").length})
          </option>
        </select>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          borderBottom: "1px solid #0d2a4a",
          background: "#0d1a2a",
        }}
      >
        <div
          onClick={() => setActiveTab("activities")}
          style={{
            padding: "8px 16px",
            background: activeTab === "activities" ? "#0d2a4a" : "transparent",
            color: activeTab === "activities" ? "#00d4ff" : "#6688aa",
            fontSize: "11px",
            cursor: "pointer",
            borderBottom: activeTab === "activities" ? "2px solid #00d4ff" : "none",
            fontWeight: activeTab === "activities" ? "bold" : "normal",
          }}
        >
          Agent Actions ({activities.length})
        </div>
        <div
          onClick={() => setActiveTab("llm")}
          style={{
            padding: "8px 16px",
            background: activeTab === "llm" ? "#0d2a4a" : "transparent",
            color: activeTab === "llm" ? "#cc44ff" : "#6688aa",
            fontSize: "11px",
            cursor: "pointer",
            borderBottom: activeTab === "llm" ? "2px solid #cc44ff" : "none",
            fontWeight: activeTab === "llm" ? "bold" : "normal",
          }}
        >
          LLM Conversations ({llmInteractions.length})
        </div>
      </div>

      {/* Content Area */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "12px",
          background: "#0a0a1a",
        }}
      >
        {activeTab === "activities" ? (
          /* Activities List */
          <div>
            {filteredActivities.length === 0 ? (
              <div
                style={{
                  color: "#334466",
                  fontSize: "12px",
                  padding: "20px",
                  textAlign: "center",
                }}
              >
                Waiting for agent activity...
              </div>
            ) : (
              filteredActivities.map((activity, idx) => (
                <div
                  key={idx}
                  style={{
                    marginBottom: "12px",
                    padding: "10px",
                    background: "rgba(0, 20, 40, 0.5)",
                    borderLeft: `3px solid ${getAgentColor(activity.agent)}`,
                    borderRadius: "4px",
                    cursor: "pointer",
                    transition: "all 0.2s",
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.background = "rgba(0, 20, 40, 0.8)";
                    e.currentTarget.style.borderLeftWidth = "5px";
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.background = "rgba(0, 20, 40, 0.5)";
                    e.currentTarget.style.borderLeftWidth = "3px";
                  }}
                  onClick={() => toggleExpand(idx, "activity")}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: "6px",
                      alignItems: "center",
                    }}
                  >
                    <span
                      style={{
                        color: getAgentColor(activity.agent),
                        fontWeight: "bold",
                        fontSize: "11px",
                      }}
                    >
                      {getAgentEmoji(activity.agent)} {activity.agent}
                    </span>
                    <span
                      style={{
                        color: "#334466",
                        fontSize: "10px",
                        background: "#0d1a2a",
                        padding: "2px 6px",
                        borderRadius: "3px",
                      }}
                    >
                      {new Date(activity.timestamp).toLocaleTimeString()}
                    </span>
                  </div>
                  <div
                    style={{
                      color: "#ccd6f6",
                      fontSize: "12px",
                      marginBottom: "6px",
                      fontWeight: "500",
                    }}
                  >
                    <span style={{ color: "#00ff88" }}>→</span> {activity.action}
                  </div>
                  {expandedItems[`activity_${idx}`] && (
                    <div
                      style={{
                        fontSize: "10px",
                        color: "#6688aa",
                        fontFamily: "'Share Tech Mono', monospace",
                        background: "#0a0a1a",
                        padding: "8px",
                        borderRadius: "3px",
                        marginTop: "6px",
                        maxHeight: "200px",
                        overflowY: "auto",
                      }}
                    >
                      <pre style={{ margin: 0, whiteSpace: "pre-wrap" }}>
                        {JSON.stringify(activity.data, null, 2).substring(0, 500)}
                      </pre>
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        ) : (
          /* LLM Interactions */
          <div>
            {llmInteractions.length === 0 ? (
              <div
                style={{
                  color: "#334466",
                  fontSize: "12px",
                  padding: "20px",
                  textAlign: "center",
                }}
              >
                No LLM interactions yet...
              </div>
            ) : (
              llmInteractions.map((interaction, idx) => (
                <div
                  key={idx}
                  style={{
                    marginBottom: "12px",
                    padding: "8px",
                    background: "rgba(204, 68, 255, 0.05)",
                    border: "1px solid rgba(204, 68, 255, 0.2)",
                    borderRadius: "4px",
                    cursor: "pointer",
                  }}
                  onClick={() => toggleExpand(idx, "llm")}
                >
                  <div
                    style={{
                      display: "flex",
                      justifyContent: "space-between",
                      marginBottom: "4px",
                      alignItems: "center",
                    }}
                  >
                    <span style={{ color: "#cc44ff", fontSize: "10px", fontWeight: "bold" }}>
                      🤖 {interaction.agent}
                      <span style={{ color: "#00ff88", margin: "0 4px" }}>→</span>
                      LLM
                      <span
                        style={{
                          background: interaction.direction === "request" ? "#cc4400" : "#00cc44",
                          color: "#fff",
                          padding: "2px 6px",
                          borderRadius: "3px",
                          marginLeft: "6px",
                          fontSize: "9px",
                        }}
                      >
                        {interaction.direction}
                      </span>
                    </span>
                    <span style={{ color: "#334466", fontSize: "9px" }}>
                      {new Date(interaction.timestamp).toLocaleTimeString()}
                    </span>
                  </div>

                  <div style={{ fontSize: "10px", color: "#88aacc", marginTop: "6px" }}>
                    {interaction.prompt?.substring(0, 120)}...
                  </div>

                  {expandedItems[`llm_${idx}`] && (
                    <div style={{ marginTop: "8px", borderTop: "1px solid rgba(204, 68, 255, 0.2)", paddingTop: "8px" }}>
                      <div style={{ fontSize: "9px", color: "#88aacc", marginBottom: "8px" }}>
                        <strong style={{ color: "#00d4ff" }}>Prompt:</strong>
                        <pre
                          style={{
                            background: "#0a0a1a",
                            padding: "8px",
                            borderRadius: "4px",
                            overflowX: "auto",
                            fontSize: "9px",
                            maxHeight: "200px",
                            overflow: "auto",
                            margin: "4px 0",
                          }}
                        >
                          {interaction.prompt}
                        </pre>
                      </div>
                      {interaction.response && (
                        <div style={{ fontSize: "9px", color: "#00ff88" }}>
                          <strong style={{ color: "#00ff88" }}>Response:</strong>
                          <pre
                            style={{
                              background: "#0a0a1a",
                              padding: "8px",
                              borderRadius: "4px",
                              overflowX: "auto",
                              fontSize: "9px",
                              maxHeight: "200px",
                              overflow: "auto",
                              margin: "4px 0",
                            }}
                          >
                            {typeof interaction.response === "string"
                              ? interaction.response
                              : JSON.stringify(interaction.response, null, 2)}
                          </pre>
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))
            )}
          </div>
        )}
      </div>

      {/* Footer Stats */}
      <div
        style={{
          borderTop: "1px solid #0d2a4a",
          padding: "8px 12px",
          fontSize: "9px",
          color: "#334466",
          background: "#0d1a2a",
          display: "flex",
          justifyContent: "space-around",
        }}
      >
        <div>Agents: {new Set(activities.map((a) => a.agent)).size}</div>
        <div>Actions: {activities.length}</div>
        <div>LLM Calls: {llmInteractions.length}</div>
      </div>
    </div>
  );
}

export default AgentActivityPanel;
