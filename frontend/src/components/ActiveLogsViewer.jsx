import React, { useState, useEffect, useRef } from "react";

/**
 * ActiveLogsViewer - Real-time execution logs showing agent activities and error recovery
 */
function ActiveLogsViewer({ sessionId }) {
  const [logs, setLogs] = useState([]);
  const [filter, setFilter] = useState("all"); // all, info, warning, error, success
  const [autoScroll, setAutoScroll] = useState(true);
  const logsEndRef = useRef(null);

  useEffect(() => {
    if (!sessionId) return;

    // Connect to WebSocket for real-time logs
    const ws = new WebSocket(`ws://localhost:8000/ws/agent-activity/${sessionId}`);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);

        let logEntry = null;

        if (data.type === "agent_message") {
          logEntry = {
            timestamp: data.timestamp,
            type: "agent",
            level: data.action.includes("❌") ? "error" : data.action.includes("✅") ? "success" : "info",
            agent: data.agent,
            message: `[${data.agent}] ${data.action}`,
          };
        } else if (data.type === "execution_log") {
          logEntry = {
            timestamp: data.timestamp,
            type: "execution",
            level: data.level,
            agent: data.stage_name,
            message: `[${data.stage_name}] ${data.message}`,
          };
        } else if (data.type === "llm_interaction") {
          logEntry = {
            timestamp: data.timestamp,
            type: "llm",
            level: data.direction === "request" ? "info" : "success",
            agent: data.agent,
            message: `[LLM] ${data.agent} → LLM (${data.direction})`,
            preview: data.prompt?.substring(0, 80) + "...",
          };
        } else if (data.type === "error") {
          logEntry = {
            timestamp: data.timestamp,
            type: "error",
            level: "error",
            agent: data.error_type,
            message: `[ERROR] ${data.message}`,
          };
        } else if (data.type === "status") {
          logEntry = {
            timestamp: data.timestamp,
            type: "status",
            level: data.status === "failed" ? "error" : data.status === "completed" ? "success" : "info",
            agent: "Pipeline",
            message: `[Pipeline] ${data.status.toUpperCase()}: ${JSON.stringify(data.details).substring(0, 60)}...`,
          };
        }

        if (logEntry) {
          setLogs((prev) => [...prev, logEntry].slice(-500));
        }
      } catch (error) {
        console.error("[Logs] Error parsing message:", error);
      }
    };

    return () => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.close();
      }
    };
  }, [sessionId]);

  useEffect(() => {
    if (autoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: "smooth" });
    }
  }, [logs, autoScroll]);

  const getLogColor = (level) => {
    const colors = {
      error: "#ff6666",
      warning: "#ffaa00",
      success: "#00ff88",
      info: "#00d4ff",
    };
    return colors[level] || "#8899bb";
  };

  const getLogIcon = (type) => {
    const icons = {
      agent: "🤖",
      execution: "⚙️",
      llm: "🧠",
      error: "❌",
      status: "📊",
    };
    return icons[type] || "📝";
  };

  const filteredLogs =
    filter === "all" ? logs : logs.filter((log) => log.level === filter);

  const handleClearLogs = () => {
    setLogs([]);
  };

  const handleExportLogs = () => {
    const exportText = logs
      .map((log) => `${log.timestamp} [${log.level.toUpperCase()}] ${log.message}`)
      .join("\n");

    const element = document.createElement("a");
    element.setAttribute(
      "href",
      "data:text/plain;charset=utf-8," + encodeURIComponent(exportText)
    );
    element.setAttribute("download", `devops-logs-${Date.now()}.txt`);
    element.style.display = "none";
    document.body.appendChild(element);
    element.click();
    document.body.removeChild(element);
  };

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
          background: "linear-gradient(90deg, #0a0a1a 0%, #0d1a2a 100%)",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <span
            style={{
              fontFamily: "'Orbitron', 'Courier New', monospace",
              fontSize: "12px",
              color: "#00ff88",
              fontWeight: "bold",
              letterSpacing: "2px",
            }}
          >
            📋 LIVE EXECUTION LOG
          </span>
          <div style={{ fontSize: "10px", color: "#334466", marginTop: "4px" }}>
            {logs.length} entries • {filteredLogs.length} visible
          </div>
        </div>

        <div style={{ display: "flex", gap: "6px" }}>
          <button
            onClick={() => setAutoScroll(!autoScroll)}
            style={{
              background: autoScroll ? "#00ff88" : "#0d3a5a",
              border: "1px solid #00ff88",
              color: autoScroll ? "#000" : "#00ff88",
              padding: "6px 12px",
              borderRadius: "4px",
              fontSize: "9px",
              cursor: "pointer",
              fontWeight: autoScroll ? "bold" : "normal",
            }}
          >
            {autoScroll ? "📌 Auto-Scroll" : "Auto-Scroll Off"}
          </button>
        </div>
      </div>

      {/* Filter Bar */}
      <div
        style={{
          display: "flex",
          gap: "6px",
          padding: "8px 12px",
          borderBottom: "1px solid #0d2a4a",
          background: "#0d1a2a",
          overflowX: "auto",
        }}
      >
        {["all", "info", "warning", "error", "success"].map((level) => (
          <button
            key={level}
            onClick={() => setFilter(level)}
            style={{
              background: filter === level ? getLogColor(level) : "transparent",
              border: `1px solid ${getLogColor(level)}`,
              color: filter === level ? "#000" : getLogColor(level),
              padding: "4px 10px",
              borderRadius: "3px",
              fontSize: "9px",
              cursor: "pointer",
              fontWeight: filter === level ? "bold" : "normal",
              whiteSpace: "nowrap",
            }}
          >
            {level.toUpperCase()}
            {level !== "all" && ` (${logs.filter((l) => l.level === level).length})`}
          </button>
        ))}
      </div>

      {/* Logs Container */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "8px 12px",
          background: "#0a0a0a",
          fontFamily: "'Courier New', monospace",
          fontSize: "11px",
          lineHeight: "1.4",
        }}
      >
        {filteredLogs.length === 0 ? (
          <div
            style={{
              color: "#334466",
              fontSize: "12px",
              padding: "40px 20px",
              textAlign: "center",
            }}
          >
            {logs.length === 0 ? "Waiting for activity..." : "No logs match filter"}
          </div>
        ) : (
          filteredLogs.map((log, idx) => (
            <div
              key={idx}
              style={{
                marginBottom: "6px",
                padding: "6px 8px",
                background: log.level === "error" ? "rgba(255, 100, 100, 0.05)" : log.level === "success" ? "rgba(0, 255, 136, 0.05)" : log.level === "warning" ? "rgba(255, 170, 0, 0.05)" : "transparent",
                borderLeft: `2px solid ${getLogColor(log.level)}`,
                borderRadius: "2px",
              }}
            >
              <div
                style={{
                  display: "flex",
                  gap: "8px",
                  fontSize: "10px",
                  color: "#334466",
                }}
              >
                <span style={{ minWidth: "150px" }}>
                  {new Date(log.timestamp).toLocaleTimeString()}
                </span>
                <span
                  style={{
                    background: getLogColor(log.level),
                    color: "#000",
                    padding: "1px 6px",
                    borderRadius: "2px",
                    fontWeight: "bold",
                    minWidth: "60px",
                  }}
                >
                  {log.level.toUpperCase()}
                </span>
                <span style={{ color: "#00d4ff" }}>{getLogIcon(log.type)}</span>
              </div>
              <div
                style={{
                  color: "#ccd6f6",
                  fontSize: "11px",
                  marginTop: "3px",
                  wordBreak: "break-word",
                }}
              >
                {log.message}
              </div>
              {log.preview && (
                <div
                  style={{
                    color: "#6688aa",
                    fontSize: "9px",
                    marginTop: "3px",
                  }}
                >
                  {log.preview}
                </div>
              )}
            </div>
          ))
        )}
        <div ref={logsEndRef} />
      </div>

      {/* Footer Controls */}
      <div
        style={{
          borderTop: "1px solid #0d2a4a",
          padding: "8px 12px",
          background: "#0d1a2a",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          fontSize: "9px",
          color: "#334466",
        }}
      >
        <div>
          Total: {logs.length} • Errors: {logs.filter((l) => l.level === "error").length} • Successes:{" "}
          {logs.filter((l) => l.level === "success").length}
        </div>
        <div style={{ display: "flex", gap: "6px" }}>
          <button
            onClick={handleExportLogs}
            style={{
              background: "transparent",
              border: "1px solid #334466",
              color: "#334466",
              padding: "3px 8px",
              borderRadius: "3px",
              fontSize: "8px",
              cursor: "pointer",
            }}
          >
            Export
          </button>
          <button
            onClick={handleClearLogs}
            style={{
              background: "transparent",
              border: "1px solid #ff6666",
              color: "#ff6666",
              padding: "3px 8px",
              borderRadius: "3px",
              fontSize: "8px",
              cursor: "pointer",
            }}
          >
            Clear
          </button>
        </div>
      </div>
    </div>
  );
}

export default ActiveLogsViewer;
