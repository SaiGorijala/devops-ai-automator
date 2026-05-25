import { useState, useEffect, useRef, useCallback } from "react";

const STAGES = [
  { id: "init", label: "Server Init", icon: "⚡", substeps: ["SSH Connect", "Check Docker", "Install deps", "Verify env"] },
  { id: "sonar", label: "SonarQube", icon: "🛡", substeps: ["Pull image", "Start container", "Configure DB", "Generate token"] },
  { id: "jenkins", label: "Jenkins CI", icon: "⚙", substeps: ["Deploy container", "Install plugins", "Setup GitHub", "Verify"] },
  { id: "scan", label: "Code Scan", icon: "🔍", substeps: ["Clone repo", "Run analysis", "Quality gate", "AI fix vulns"] },
  { id: "docker", label: "Docker Build", icon: "🐳", substeps: ["Detect base img", "Write Dockerfile", "Build image", "Tag commit"] },
  { id: "push", label: "Hub Push", icon: "☁", substeps: ["Auth DockerHub", "Push latest", "Push tagged", "Verify"] },
  { id: "deploy", label: "Deploy", icon: "🚀", substeps: ["Pull image", "Configure ports", "Start service", "Health check"] },
];

const LOG_STREAMS = {
  init: [
    { t: 400, text: "$ ssh -i key.pem ubuntu@{ip}", type: "cmd" },
    { t: 900, text: "Connected to server successfully", type: "ok" },
    { t: 1200, text: "$ which docker", type: "cmd" },
    { t: 1600, text: "docker not found — initiating install", type: "warn" },
    { t: 1800, text: "[AI] Docker missing detected → running auto-install", type: "ai" },
    { t: 2200, text: "$ curl -fsSL https://get.docker.com | sh", type: "cmd" },
    { t: 3500, text: "Docker 24.0.7 installed ✓", type: "ok" },
    { t: 3800, text: "$ systemctl enable --now docker", type: "cmd" },
    { t: 4200, text: "Service started and enabled ✓", type: "ok" },
    { t: 4500, text: "$ java -version 2>&1", type: "cmd" },
    { t: 4900, text: "openjdk 17.0.9 ✓", type: "ok" },
  ],
  sonar: [
    { t: 300, text: "$ docker pull sonarqube:lts-community", type: "cmd" },
    { t: 1200, text: "Pulling layer sha256:a4b2c3...", type: "info" },
    { t: 2100, text: "Image pulled ✓", type: "ok" },
    { t: 2400, text: "$ docker-compose up -d sonarqube postgres", type: "cmd" },
    { t: 3000, text: "Creating network devops_net ...", type: "info" },
    { t: 3400, text: "Starting postgres ... done", type: "ok" },
    { t: 3800, text: "Starting sonarqube ... done", type: "ok" },
    { t: 4200, text: "Waiting for SonarQube to initialize...", type: "info" },
    { t: 5500, text: "[AI] Health check timeout detected → extending wait", type: "ai" },
    { t: 6000, text: "SonarQube ready at :9000 ✓", type: "ok" },
    { t: 6300, text: "Auto-generating admin token...", type: "info" },
    { t: 6700, text: "Token: sqp_a9f3b2e1c7d8... ✓", type: "ok" },
  ],
  jenkins: [
    { t: 300, text: "$ docker pull jenkins/jenkins:lts-jdk17", type: "cmd" },
    { t: 1400, text: "Image ready ✓", type: "ok" },
    { t: 1700, text: "$ docker run -d -p 8080:8080 jenkins/jenkins:lts-jdk17", type: "cmd" },
    { t: 2300, text: "Container 3a7f9c2d started", type: "ok" },
    { t: 2700, text: "Installing plugins: git, pipeline, sonar, docker...", type: "info" },
    { t: 3500, text: "[AI] Plugin install failed: timeout → retrying with mirror", type: "ai" },
    { t: 4200, text: "All plugins installed ✓", type: "ok" },
    { t: 4600, text: "Initial admin password: 8f3a2b1c...", type: "ok" },
    { t: 5000, text: "Jenkins ready at :8080 ✓", type: "ok" },
  ],
  scan: [
    { t: 200, text: "$ git clone https://***@github.com/repo.git", type: "cmd" },
    { t: 1100, text: "Cloning into './repo'... done", type: "ok" },
    { t: 1400, text: "$ sonar-scanner -Dsonar.projectKey=app ...", type: "cmd" },
    { t: 2500, text: "INFO: Sensor JavaSensor [java]", type: "info" },
    { t: 3200, text: "WARN: 3 high severity vulnerabilities found", type: "warn" },
    { t: 3600, text: "[AI] Vulnerabilities detected → analyzing with DeepSeek-6.7B", type: "ai" },
    { t: 4100, text: "[AI] Fix 1/3: SQL injection → parameterized query patch applied", type: "ai" },
    { t: 4600, text: "[AI] Fix 2/3: XSS vector → output escaping added", type: "ai" },
    { t: 5000, text: "[AI] Fix 3/3: Hardcoded secret → env var migration applied", type: "ai" },
    { t: 5400, text: "Re-running scan after AI fixes...", type: "info" },
    { t: 6200, text: "Quality Gate: PASSED ✓", type: "ok" },
  ],
  docker: [
    { t: 200, text: "Detecting application type...", type: "info" },
    { t: 700, text: "[AI] Detected: Node.js 18 application", type: "ai" },
    { t: 1000, text: "[AI] No Dockerfile found → generating optimized Dockerfile", type: "ai" },
    { t: 1400, text: "Dockerfile written (multi-stage, alpine base)", type: "ok" },
    { t: 1700, text: "$ docker build -t app:$(git rev-parse --short HEAD) .", type: "cmd" },
    { t: 2500, text: "Step 1/12: FROM node:18-alpine", type: "info" },
    { t: 3200, text: "Step 6/12: RUN npm ci --only=production", type: "info" },
    { t: 4100, text: "[AI] Build failed: npm EACCES → fixing permissions", type: "ai" },
    { t: 4600, text: "$ chmod -R 755 /app && npm ci", type: "cmd" },
    { t: 5300, text: "Build successful ✓ (image: 124MB)", type: "ok" },
    { t: 5600, text: "Tagged: app:a3f7c9b, app:latest ✓", type: "ok" },
  ],
  push: [
    { t: 300, text: "$ docker login -u {user} --password-stdin", type: "cmd" },
    { t: 900, text: "Login Succeeded ✓", type: "ok" },
    { t: 1200, text: "$ docker tag app:latest {user}/app:latest", type: "cmd" },
    { t: 1600, text: "$ docker push {user}/app:latest", type: "cmd" },
    { t: 2400, text: "Pushed layer sha256:3b9f1c...", type: "info" },
    { t: 3100, text: "Push complete ✓", type: "ok" },
    { t: 3400, text: "$ docker push {user}/app:a3f7c9b", type: "cmd" },
    { t: 4200, text: "Pushed ✓", type: "ok" },
    { t: 4500, text: "Image URL: hub.docker.com/r/{user}/app ✓", type: "ok" },
  ],
  deploy: [
    { t: 300, text: "$ docker-compose pull", type: "cmd" },
    { t: 1200, text: "Pulling app ... done", type: "ok" },
    { t: 1500, text: "$ docker-compose up -d", type: "cmd" },
    { t: 2100, text: "Starting app_1 ... done", type: "ok" },
    { t: 2400, text: "$ curl -f http://localhost:3000/health", type: "cmd" },
    { t: 2900, text: "[AI] Port 3000 conflict detected → remapping to 3001", type: "ai" },
    { t: 3400, text: "$ docker-compose restart app", type: "cmd" },
    { t: 4000, text: "Health check passed ✓", type: "ok" },
    { t: 4300, text: "Application live at http://{ip}:3001 ✓", type: "ok" },
  ],
};

const AI_EVENTS = [
  { stage: "init", msg: "Docker not found → auto-install triggered", severity: "warn" },
  { stage: "sonar", msg: "Health check timeout → extended wait 30s", severity: "warn" },
  { stage: "jenkins", msg: "Plugin mirror fallback activated", severity: "warn" },
  { stage: "scan", msg: "3 CVEs detected → AI patching in progress", severity: "error" },
  { stage: "scan", msg: "All vulnerabilities patched — rescan passed", severity: "success" },
  { stage: "docker", msg: "No Dockerfile → generated multi-stage build", severity: "warn" },
  { stage: "docker", msg: "EACCES error → permissions fixed automatically", severity: "warn" },
  { stage: "deploy", msg: "Port conflict :3000 → dynamically remapped :3001", severity: "warn" },
  { stage: "deploy", msg: "All services healthy — deployment complete", severity: "success" },
];

export default function App() {
  const [form, setForm] = useState({ repo: "", token: "", ip: "", pem: null, dhUser: "", dhPass: "" });
  const [status, setStatus] = useState("idle"); // idle | running | done | error
  const [stageStatus, setStageStatus] = useState({});
  const [activeStage, setActiveStage] = useState(null);
  const [logs, setLogs] = useState([]);
  const [aiLog, setAiLog] = useState([]);
  const [agentEvents, setAgentEvents] = useState([]);
  const [activeAgentName, setActiveAgentName] = useState("Standby");
  const [progress, setProgress] = useState(0);
  const [creds, setCreds] = useState(null);
  const [pemName, setPemName] = useState("");
  const [glitch, setGlitch] = useState(false);
  const logsEndRef = useRef(null);
  const aiEndRef = useRef(null);
  const timeouts = useRef([]);
  const wsRef = useRef(null);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [logs]);

  useEffect(() => {
    aiEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [aiLog]);

  const addLog = useCallback((entry) => {
    setLogs(prev => [...prev, { ...entry, id: Date.now() + Math.random() }]);
  }, []);

  const addAiLog = useCallback((entry) => {
    setAiLog(prev => [...prev, { ...entry, id: Date.now() + Math.random() }]);
  }, []);

  const clearTimeouts = () => {
    timeouts.current.forEach(clearTimeout);
    timeouts.current = [];
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  };

  const normalizeCreds = (outputs = {}) => ({
    sonar: {
      url: outputs.sonar?.url,
      user: outputs.sonar?.username || "admin",
      pass: outputs.sonar?.password,
      token: outputs.sonar?.token,
    },
    jenkins: {
      url: outputs.jenkins?.url,
      user: outputs.jenkins?.username || "admin",
      pass: outputs.jenkins?.password,
    },
    app: { url: outputs.app?.url },
    docker: outputs.docker?.pull || (outputs.docker?.image ? `docker pull ${outputs.docker.image}` : ""),
  });

  const backendStatus = (value) => {
    if (value === "completed") return "done";
    if (value === "failed") return "error";
    if (value === "running") return "running";
    return "idle";
  };

  const applySnapshot = useCallback((snapshot) => {
    if (!snapshot) return;
    setStatus(backendStatus(snapshot.status));
    setStageStatus(snapshot.stages || {});
    setActiveStage(snapshot.current_stage || null);
    setProgress(snapshot.progress || 0);
    if (Array.isArray(snapshot.logs)) {
      setLogs(snapshot.logs.map(entry => ({ ...entry, id: Date.now() + Math.random() })));
    }
    if (Array.isArray(snapshot.ai_interventions)) {
      setAiLog(snapshot.ai_interventions.map(entry => ({ ...entry, id: Date.now() + Math.random() })));
      const events = snapshot.ai_interventions
        .filter(entry => entry.agent || entry.agent_message)
        .map(entry => entry.agent_message || {
          from_agent: entry.agent,
          to_agent: "ui",
          type: entry.type,
          content: { message: entry.text, stage: entry.stage },
          timestamp: entry.timestamp,
        });
      setAgentEvents(events.map(entry => ({ ...entry, id: Date.now() + Math.random() })));
      if (events.length) setActiveAgentName(events[events.length - 1].from_agent || "Standby");
    }
    if (snapshot.outputs && Object.keys(snapshot.outputs).length) {
      setCreds(normalizeCreds(snapshot.outputs));
    }
  }, []);

  useEffect(() => () => clearTimeouts(), []);

  const websocketUrl = (sessionId) => {
    const protocol = window.location.protocol === "https:" ? "wss" : "ws";
    const host = window.location.host || "localhost:8000";
    return `${protocol}://${host}/ws/${sessionId}`;
  };

  const fetchCredentials = async (sessionId) => {
    const response = await fetch(`/api/credentials/${sessionId}`);
    if (!response.ok) return;
    const data = await response.json();
    if (data.ready) setCreds(normalizeCreds(data));
  };

  const runPipeline = async () => {
    clearTimeouts();
    setStatus("running");
    setLogs([]);
    setAiLog([]);
    setAgentEvents([]);
    setActiveAgentName("Starting");
    setStageStatus({});
    setActiveStage(null);
    setProgress(0);
    setCreds(null);

    try {
      const pemContent = form.pem && typeof form.pem.text === "function" ? await form.pem.text() : form.pem;
      const response = await fetch("/api/deploy", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          repo_url: form.repo,
          github_token: form.token,
          server_ip: form.ip,
          pem_file_content: pemContent,
          dockerhub_user: form.dhUser,
          dockerhub_pass: form.dhPass,
        }),
      });

      if (!response.ok) {
        const error = await response.json().catch(() => ({}));
        throw new Error(error.detail || `Deploy request failed with ${response.status}`);
      }

      const { session_id } = await response.json();
      addLog({ text: `Pipeline session created: ${session_id}`, type: "ok" });

      const ws = new WebSocket(websocketUrl(session_id));
      wsRef.current = ws;

      ws.onmessage = (event) => {
        const message = JSON.parse(event.data);
        const data = message.data || {};

        if (message.type === "status") {
          if (data.logs || data.ai_interventions || data.stages) {
            applySnapshot(data);
          } else {
            if (data.status) setStatus(backendStatus(data.status));
            if (typeof data.progress === "number") setProgress(data.progress);
          }
          if (data.status === "completed") fetchCredentials(session_id);
          return;
        }
        if (message.type === "log") {
          addLog(data);
          return;
        }
        if (message.type === "ai_action") {
          addAiLog(data);
          if (data.agent) setActiveAgentName(data.agent);
          setGlitch(true);
          setTimeout(() => setGlitch(false), 300);
          return;
        }
        if (message.type === "agent_event") {
          setAgentEvents(prev => [...prev, { ...data, id: Date.now() + Math.random() }].slice(-200));
          if (data.from_agent) setActiveAgentName(data.from_agent);
          return;
        }
        if (message.type === "stage_update") {
          setStageStatus(prev => ({ ...prev, [data.stage]: data.status }));
          setActiveStage(data.status === "running" ? data.stage : null);
          return;
        }
        if (message.type === "progress") {
          setProgress(data.progress || 0);
          return;
        }
        if (message.type === "credentials") {
          setCreds(normalizeCreds(data));
          return;
        }
        if (message.type === "error") {
          setStatus("error");
          addLog({ text: data.message || "Pipeline failed", type: "error" });
        }
      };

      ws.onclose = async () => {
        const statusResponse = await fetch(`/api/status/${session_id}`).catch(() => null);
        if (!statusResponse?.ok) return;
        const snapshot = await statusResponse.json();
        applySnapshot(snapshot);
        if (snapshot.status === "completed") fetchCredentials(session_id);
      };

      ws.onerror = () => {
        addLog({ text: "WebSocket connection error; falling back to status polling on close", type: "warn" });
      };

      return;
    } catch (error) {
      setStatus("error");
      addLog({ text: error.message, type: "error" });
      addAiLog({ text: "Pipeline launch failed before the agent could attach", type: "error" });
      return;
    }

    addLog({ text: `Pipeline started for ${form.repo || "github.com/user/app"}`, type: "info" });
    addAiLog({ text: "AI Agent online — monitoring all pipeline events", type: "ok" });
    addAiLog({ text: `Model: deepseek-coder:6.7b @ localhost:11434`, type: "info" });
    addAiLog({ text: "Zero-intervention mode: ACTIVE", type: "ok" });

    let cumulativeTime = 500;
    let aiEventIdx = 0;

    STAGES.forEach((stage, stageIdx) => {
      const stageDelay = cumulativeTime;
      const stageEntries = LOG_STREAMS[stage.id] || [];
      const stageDuration = Math.max(...stageEntries.map(e => e.t), 3000) + 1200;
      cumulativeTime += stageDuration;

      const t1 = setTimeout(() => {
        setActiveStage(stage.id);
        setStageStatus(prev => ({ ...prev, [stage.id]: "running" }));
        addLog({ text: `▶ Stage: ${stage.label}`, type: "stage" });
        setProgress(Math.round((stageIdx / STAGES.length) * 100));
      }, stageDelay);
      timeouts.current.push(t1);

      stageEntries.forEach(entry => {
        const displayEntry = { ...entry, text: entry.text.replace(/{ip}/g, form.ip || "192.168.1.100").replace(/{user}/g, form.dhUser || "devuser") };
        if (entry.type === "ai") {
          const ta = setTimeout(() => {
            addLog(displayEntry);
            addAiLog({ text: displayEntry.text.replace("[AI] ", ""), type: "action", stage: stage.id });
            setGlitch(true);
            setTimeout(() => setGlitch(false), 300);
          }, stageDelay + entry.t);
          timeouts.current.push(ta);
        } else {
          const tl = setTimeout(() => addLog(displayEntry), stageDelay + entry.t);
          timeouts.current.push(tl);
        }
      });

      while (aiEventIdx < AI_EVENTS.length && AI_EVENTS[aiEventIdx].stage === stage.id) {
        const ev = AI_EVENTS[aiEventIdx];
        const evTime = stageDelay + (stageDuration * 0.4);
        const idx = aiEventIdx;
        const ta2 = setTimeout(() => {
          addAiLog({ text: AI_EVENTS[idx].msg, type: AI_EVENTS[idx].severity, ts: new Date().toLocaleTimeString() });
        }, evTime + idx * 200);
        timeouts.current.push(ta2);
        aiEventIdx++;
      }

      const t2 = setTimeout(() => {
        setStageStatus(prev => ({ ...prev, [stage.id]: "done" }));
        setProgress(Math.round(((stageIdx + 1) / STAGES.length) * 100));
        if (stageIdx === STAGES.length - 1) {
          setActiveStage(null);
          setStatus("done");
          setProgress(100);
          const ip = form.ip || "192.168.1.100";
          const user = form.dhUser || "devuser";
          setCreds({
            sonar: { url: `http://${ip}:9000`, user: "admin", pass: "sq_" + Math.random().toString(36).slice(2, 10) },
            jenkins: { url: `http://${ip}:8080`, user: "admin", pass: Math.random().toString(36).slice(2, 14) },
            app: { url: `http://${ip}:3001` },
            docker: `docker pull ${user}/app:latest`,
          });
          addLog({ text: "✓ Pipeline completed successfully!", type: "success" });
          addAiLog({ text: "Pipeline complete — 8 auto-fixes applied, 0 manual interventions", type: "ok" });
        }
      }, stageDelay + stageDuration);
      timeouts.current.push(t2);
    });
  };

  const logTypeStyle = (type) => {
    const map = {
      cmd: { color: "#00d4ff", prefix: "" },
      ok: { color: "#00ff88", prefix: "✓ " },
      warn: { color: "#ffaa00", prefix: "⚠ " },
      error: { color: "#ff3355", prefix: "✗ " },
      ai: { color: "#cc44ff", prefix: "" },
      info: { color: "#8899bb", prefix: "" },
      stage: { color: "#ffffff", prefix: "" },
      success: { color: "#00ff88", prefix: "✓ " },
      action: { color: "#cc44ff", prefix: "→ " },
    };
    return map[type] || { color: "#8899bb", prefix: "" };
  };

  const stageIcon = (stageId) => {
    const s = stageStatus[stageId];
    if (s === "done") return { icon: "✓", color: "#00ff88" };
    if (s === "running") return { icon: "▶", color: "#00d4ff" };
    return { icon: "○", color: "#334466" };
  };

  const canDeploy = status !== "running";

  return (
    <div style={{
      fontFamily: "'Courier New', monospace",
      background: "#050510",
      minHeight: "100vh",
      color: "#ccd6f6",
      overflow: "hidden",
    }}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;700;900&family=Share+Tech+Mono&display=swap');
        * { box-sizing: border-box; margin: 0; padding: 0; }
        ::-webkit-scrollbar { width: 4px; }
        ::-webkit-scrollbar-track { background: #0a0a1a; }
        ::-webkit-scrollbar-thumb { background: #1a3a6a; border-radius: 2px; }
        @keyframes scanline {
          0% { transform: translateY(-100%); }
          100% { transform: translateY(100vh); }
        }
        @keyframes pulse-border {
          0%, 100% { border-color: #0d2a4a; }
          50% { border-color: #00d4ff44; }
        }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @keyframes ai-pulse {
          0%, 100% { box-shadow: 0 0 0 0 #cc44ff44; }
          50% { box-shadow: 0 0 0 8px #cc44ff00; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
        @keyframes glitch {
          0% { transform: translateX(0); }
          20% { transform: translateX(-2px); }
          40% { transform: translateX(2px); }
          60% { transform: translateX(-1px); }
          80% { transform: translateX(1px); }
          100% { transform: translateX(0); }
        }
        @keyframes fadeUp {
          from { opacity: 0; transform: translateY(8px); }
          to { opacity: 1; transform: translateY(0); }
        }
        @keyframes progress-glow {
          0%, 100% { box-shadow: 0 0 6px #00d4ff; }
          50% { box-shadow: 0 0 16px #00d4ff, 0 0 30px #00d4ff44; }
        }
        .panel {
          background: rgba(5, 15, 35, 0.85);
          border: 1px solid #0d2a4a;
          border-radius: 4px;
        }
        .panel-header {
          padding: 10px 14px;
          border-bottom: 1px solid #0d2a4a;
          font-family: 'Orbitron', sans-serif;
          font-size: 9px;
          letter-spacing: 2px;
          color: #00d4ff;
          text-transform: uppercase;
          display: flex;
          align-items: center;
          gap: 8px;
        }
        .neon-input {
          background: rgba(0, 212, 255, 0.03);
          border: 1px solid #0d2a4a;
          border-radius: 2px;
          color: #ccd6f6;
          font-family: 'Share Tech Mono', monospace;
          font-size: 12px;
          padding: 8px 10px;
          width: 100%;
          outline: none;
          transition: border-color 0.2s, background 0.2s;
        }
        .neon-input:focus {
          border-color: #00d4ff44;
          background: rgba(0, 212, 255, 0.06);
        }
        .neon-input::placeholder { color: #2a4a6a; }
        .deploy-btn {
          width: 100%;
          padding: 12px;
          background: transparent;
          border: 1px solid #00d4ff;
          color: #00d4ff;
          font-family: 'Orbitron', sans-serif;
          font-size: 11px;
          letter-spacing: 3px;
          cursor: pointer;
          border-radius: 2px;
          position: relative;
          overflow: hidden;
          transition: all 0.3s;
        }
        .deploy-btn:hover:not(:disabled) {
          background: rgba(0, 212, 255, 0.08);
          box-shadow: 0 0 20px rgba(0, 212, 255, 0.2);
        }
        .deploy-btn:disabled { opacity: 0.4; cursor: not-allowed; border-color: #0d2a4a; color: #0d2a4a; }
        .stage-node {
          display: flex;
          align-items: flex-start;
          gap: 10px;
          padding: 8px 0;
          border-bottom: 1px solid #080820;
          animation: fadeUp 0.3s ease;
          cursor: default;
        }
        .log-line {
          font-family: 'Share Tech Mono', monospace;
          font-size: 11px;
          line-height: 1.6;
          animation: fadeUp 0.2s ease;
          white-space: pre-wrap;
          word-break: break-all;
        }
        .ai-entry {
          padding: 6px 10px;
          border-radius: 2px;
          font-size: 11px;
          font-family: 'Share Tech Mono', monospace;
          line-height: 1.5;
          animation: fadeUp 0.3s ease;
          border-left: 2px solid #cc44ff;
          margin-bottom: 6px;
          background: rgba(204, 68, 255, 0.04);
        }
        .dot-running {
          width: 8px; height: 8px; border-radius: 50%;
          background: #00d4ff;
          animation: ai-pulse 1.5s infinite;
          flex-shrink: 0;
          margin-top: 4px;
        }
        .dot-done { width: 8px; height: 8px; border-radius: 50%; background: #00ff88; flex-shrink: 0; margin-top: 4px; }
        .dot-idle { width: 8px; height: 8px; border-radius: 50%; background: #0d2a4a; flex-shrink: 0; margin-top: 4px; }
        .cred-card {
          background: rgba(0, 212, 255, 0.04);
          border: 1px solid #0d3a5a;
          border-radius: 4px;
          padding: 12px;
          flex: 1;
          min-width: 140px;
        }
        .copy-btn {
          background: transparent;
          border: 1px solid #0d2a4a;
          color: #8899bb;
          font-family: 'Share Tech Mono', monospace;
          font-size: 10px;
          padding: 2px 8px;
          cursor: pointer;
          border-radius: 2px;
          transition: all 0.2s;
        }
        .copy-btn:hover { border-color: #00d4ff44; color: #00d4ff; }
        .spinner { animation: spin 1s linear infinite; display: inline-block; }
        .glitch-effect { animation: glitch 0.3s ease; }
      `}</style>

      {/* Scanline overlay */}
      <div style={{
        position: "fixed", top: 0, left: 0, right: 0, bottom: 0,
        background: "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,0,0,0.03) 2px, rgba(0,0,0,0.03) 4px)",
        pointerEvents: "none", zIndex: 0,
      }} />

      {/* Header */}
      <div style={{
        borderBottom: "1px solid #0d2a4a",
        padding: "12px 20px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: "rgba(5,5,20,0.95)",
        position: "sticky", top: 0, zIndex: 10,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <div style={{
            fontFamily: "'Orbitron', sans-serif",
            fontSize: 18, fontWeight: 900,
            color: "#00d4ff",
            letterSpacing: 4,
            ...(glitch ? { animation: "glitch 0.3s ease" } : {}),
          }}>DEVOPS<span style={{ color: "#cc44ff" }}>·AI</span></div>
          <div style={{ width: 1, height: 20, background: "#0d2a4a" }} />
          <div style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 8, color: "#334466", letterSpacing: 3 }}>AUTONOMOUS PIPELINE CONTROLLER</div>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          {status === "running" && (
            <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 10, color: "#00d4ff", fontFamily: "'Share Tech Mono', monospace" }}>
              <span className="spinner">◌</span> PIPELINE ACTIVE
            </div>
          )}
          {status === "done" && (
            <div style={{ fontSize: 10, color: "#00ff88", fontFamily: "'Share Tech Mono', monospace" }}>✓ DEPLOYMENT COMPLETE</div>
          )}
          <div style={{
            width: 8, height: 8, borderRadius: "50%",
            background: status === "running" ? "#00d4ff" : status === "done" ? "#00ff88" : "#334466",
            boxShadow: status === "running" ? "0 0 10px #00d4ff" : status === "done" ? "0 0 10px #00ff88" : "none",
          }} />
          <div style={{ fontFamily: "'Share Tech Mono', monospace", fontSize: 10, color: "#334466" }}>
            {status === "idle" ? "STANDBY" : status === "running" ? "ONLINE" : status === "done" ? "COMPLETE" : "ERROR"}
          </div>
        </div>
      </div>

      {/* Progress bar */}
      {status === "running" && (
        <div style={{ height: 2, background: "#0a0a1a", position: "relative" }}>
          <div style={{
            height: "100%", width: `${progress}%`,
            background: "#00d4ff",
            transition: "width 0.5s ease",
            animation: "progress-glow 2s infinite",
          }} />
        </div>
      )}
      {status === "done" && (
        <div style={{ height: 2, background: "#00ff88" }} />
      )}

      {/* Main layout */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "280px 1fr 280px",
        gap: 1,
        padding: "1px",
        background: "#0a0f20",
        minHeight: "calc(100vh - 60px)",
        position: "relative", zIndex: 1,
      }}>

        {/* LEFT: Input Panel */}
        <div className="panel" style={{ display: "flex", flexDirection: "column" }}>
          <div className="panel-header">
            <span style={{ color: "#00d4ff" }}>⬡</span> Configuration
          </div>
          <div style={{ padding: "14px 12px", display: "flex", flexDirection: "column", gap: 14, flex: 1, overflowY: "auto" }}>

            <div>
              <div style={{ fontSize: 9, color: "#334466", letterSpacing: 2, marginBottom: 5, fontFamily: "'Orbitron', sans-serif" }}>REPOSITORY</div>
              <input className="neon-input" placeholder="https://github.com/user/app" value={form.repo} onChange={e => setForm(f => ({ ...f, repo: e.target.value }))} />
            </div>

            <div>
              <div style={{ fontSize: 9, color: "#334466", letterSpacing: 2, marginBottom: 5, fontFamily: "'Orbitron', sans-serif" }}>GITHUB TOKEN <span style={{ color: "#0d2a4a" }}>(private repos)</span></div>
              <input className="neon-input" type="password" placeholder="ghp_xxxxxxxxxxxx" value={form.token} onChange={e => setForm(f => ({ ...f, token: e.target.value }))} />
            </div>

            <div>
              <div style={{ fontSize: 9, color: "#334466", letterSpacing: 2, marginBottom: 5, fontFamily: "'Orbitron', sans-serif" }}>TARGET SERVER IP</div>
              <input className="neon-input" placeholder="192.168.1.100" value={form.ip} onChange={e => setForm(f => ({ ...f, ip: e.target.value }))} />
            </div>

            <div>
              <div style={{ fontSize: 9, color: "#334466", letterSpacing: 2, marginBottom: 5, fontFamily: "'Orbitron', sans-serif" }}>PEM KEY FILE</div>
              <label style={{
                display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center",
                padding: "16px 10px",
                border: "1px dashed " + (pemName ? "#00d4ff44" : "#0d2a4a"),
                borderRadius: 2,
                cursor: "pointer",
                background: pemName ? "rgba(0,212,255,0.04)" : "transparent",
                transition: "all 0.2s",
              }}>
                <span style={{ fontSize: 18, marginBottom: 4 }}>{pemName ? "🔑" : "📎"}</span>
                <span style={{ fontSize: 10, color: pemName ? "#00d4ff" : "#334466", fontFamily: "'Share Tech Mono', monospace" }}>
                  {pemName || "drop .pem file here"}
                </span>
                <input type="file" accept=".pem,.key" style={{ display: "none" }} onChange={e => {
                  const f = e.target.files[0];
                  if (f) { setForm(prev => ({ ...prev, pem: f })); setPemName(f.name); }
                }} />
              </label>
            </div>

            <div style={{ borderTop: "1px solid #0d2a4a", paddingTop: 14 }}>
              <div style={{ fontSize: 9, color: "#334466", letterSpacing: 2, marginBottom: 8, fontFamily: "'Orbitron', sans-serif" }}>DOCKERHUB CREDENTIALS</div>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                <input className="neon-input" placeholder="username" value={form.dhUser} onChange={e => setForm(f => ({ ...f, dhUser: e.target.value }))} />
                <input className="neon-input" type="password" placeholder="password / access token" value={form.dhPass} onChange={e => setForm(f => ({ ...f, dhPass: e.target.value }))} />
              </div>
            </div>

            <div style={{ marginTop: "auto", paddingTop: 8 }}>
              {status === "running" ? (
                <div style={{ textAlign: "center", color: "#00d4ff", fontFamily: "'Share Tech Mono', monospace", fontSize: 11 }}>
                  <span className="spinner">◌</span> {progress}% complete
                </div>
              ) : (
                <button className="deploy-btn" onClick={runPipeline} disabled={!canDeploy}>
                  {status === "done" ? "↺ REDEPLOY" : "⟶ INITIATE PIPELINE"}
                </button>
              )}

              {/* AI Status */}
              <div style={{
                marginTop: 12,
                padding: "8px 10px",
                background: "rgba(204,68,255,0.05)",
                border: "1px solid #2a0a4a",
                borderRadius: 2,
                display: "flex", alignItems: "center", gap: 8,
              }}>
                <div style={{
                  width: 6, height: 6, borderRadius: "50%",
                  background: "#cc44ff",
                  animation: "ai-pulse 2s infinite",
                }} />
                <div>
                  <div style={{ fontSize: 9, color: "#cc44ff", letterSpacing: 2, fontFamily: "'Orbitron', sans-serif" }}>ACTIVE AGENT</div>
                  <div style={{ fontSize: 10, color: "#884499", fontFamily: "'Share Tech Mono', monospace" }}>{activeAgentName}</div>
                </div>
                <div style={{ marginLeft: "auto", fontSize: 9, color: "#cc44ff", fontFamily: "'Share Tech Mono', monospace" }}>
                  {aiLog.filter(e => e.type === "action").length} fixes
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* CENTER: Pipeline + Logs */}
        <div style={{ display: "flex", flexDirection: "column", gap: 1 }}>

          {/* Pipeline Stages */}
          <div className="panel" style={{ padding: "12px 16px" }}>
            <div className="panel-header" style={{ marginBottom: 12, padding: "0 0 10px 0", borderBottom: "1px solid #0d2a4a" }}>
              <span style={{ color: "#cc44ff" }}>◈</span> Pipeline Stages
              {status === "running" && <span style={{ marginLeft: "auto", fontSize: 9, color: "#00d4ff" }}>EXECUTING</span>}
              {status === "done" && <span style={{ marginLeft: "auto", fontSize: 9, color: "#00ff88" }}>ALL COMPLETE</span>}
            </div>
            <div style={{ display: "flex", gap: 0, alignItems: "center" }}>
              {STAGES.map((stage, i) => {
                const s = stageStatus[stage.id];
                const isActive = activeStage === stage.id;
                return (
                  <div key={stage.id} style={{ display: "flex", alignItems: "center", flex: 1 }}>
                    <div style={{
                      flex: 1,
                      padding: "10px 8px",
                      textAlign: "center",
                      border: "1px solid " + (isActive ? "#00d4ff44" : s === "done" ? "#00ff8822" : "#0d2a4a"),
                      borderRadius: 2,
                      background: isActive ? "rgba(0,212,255,0.06)" : s === "done" ? "rgba(0,255,136,0.03)" : "transparent",
                      transition: "all 0.3s",
                      position: "relative",
                      overflow: "hidden",
                    }}>
                      {isActive && (
                        <div style={{
                          position: "absolute", top: 0, left: 0, right: 0,
                          height: 2, background: "#00d4ff",
                          animation: "progress-glow 1.5s infinite",
                        }} />
                      )}
                      <div style={{ fontSize: 16, marginBottom: 4 }}>{stage.icon}</div>
                      <div style={{
                        fontFamily: "'Orbitron', sans-serif",
                        fontSize: 7, letterSpacing: 1,
                        color: isActive ? "#00d4ff" : s === "done" ? "#00ff88" : "#334466",
                      }}>{stage.label}</div>
                      <div style={{
                        marginTop: 4, fontSize: 12,
                        color: s === "done" ? "#00ff88" : isActive ? "#00d4ff" : "#1a3a6a",
                      }}>
                        {s === "done" ? "✓" : isActive ? <span className="spinner">◌</span> : "·"}
                      </div>
                    </div>
                    {i < STAGES.length - 1 && (
                      <div style={{
                        width: 16, height: 1,
                        background: stageStatus[STAGES[i+1]?.id] || stageStatus[stage.id] === "done" ? "#00d4ff22" : "#0d2a4a",
                        flexShrink: 0,
                      }} />
                    )}
                  </div>
                );
              })}
            </div>
          </div>

          {/* Terminal Log */}
          <div className="panel" style={{ flex: 1, display: "flex", flexDirection: "column" }}>
            <div className="panel-header">
              <span style={{ color: "#00ff88" }}>▶</span> Terminal Output
              <span style={{ marginLeft: "auto", fontSize: 9, color: "#1a3a6a" }}>{logs.length} lines</span>
            </div>
            <div style={{
              flex: 1, overflowY: "auto", padding: "10px 14px",
              maxHeight: "calc(100vh - 340px)",
              minHeight: 300,
            }}>
              {logs.length === 0 ? (
                <div style={{ color: "#1a3a6a", fontSize: 11, fontFamily: "'Share Tech Mono', monospace", marginTop: 20, textAlign: "center" }}>
                  Awaiting pipeline initialization...<span style={{ animation: "blink 1s infinite", display: "inline-block" }}>█</span>
                </div>
              ) : (
                logs.map(entry => {
                  const style = logTypeStyle(entry.type);
                  return (
                    <div key={entry.id} className="log-line" style={{ color: style.color, marginBottom: 2 }}>
                      {entry.type === "stage" ? (
                        <span style={{ fontFamily: "'Orbitron', sans-serif", fontSize: 9, letterSpacing: 2 }}>━━ {entry.text.replace("▶ Stage: ", "")} ━━</span>
                      ) : (
                        <span>{style.prefix}{entry.text}</span>
                      )}
                    </div>
                  );
                })
              )}
              <div ref={logsEndRef} />
            </div>
          </div>
        </div>

        {/* RIGHT: AI Console */}
        <div className="panel" style={{ display: "flex", flexDirection: "column" }}>
          <div className="panel-header" style={{ borderColor: "#1a0a3a" }}>
            <span style={{ color: "#cc44ff" }}>◉</span>
            <span style={{ color: "#cc44ff" }}>AI Agent Console</span>
          </div>

          {/* AI Stats */}
          <div style={{
            display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 1,
            borderBottom: "1px solid #0d2a4a",
          }}>
            {[
              { label: "FIXES", value: aiLog.filter(e => e.type === "action").length },
              { label: "ERRORS", value: aiLog.filter(e => e.type === "error").length },
              { label: "AGENTS", value: new Set(agentEvents.map(e => e.from_agent).filter(Boolean)).size },
            ].map(stat => (
              <div key={stat.label} style={{ padding: "8px 12px", borderRight: "1px solid #0d2a4a" }}>
                <div style={{ fontSize: 18, fontWeight: 700, color: "#cc44ff", fontFamily: "'Orbitron', sans-serif" }}>{stat.value}</div>
                <div style={{ fontSize: 8, color: "#334466", letterSpacing: 2, fontFamily: "'Orbitron', sans-serif" }}>{stat.label}</div>
              </div>
            ))}
          </div>

          {/* AI Log */}
          <div style={{ flex: 1, overflowY: "auto", padding: "10px 10px", maxHeight: "calc(100vh - 280px)" }}>
            {agentEvents.length > 0 && (
              <div style={{ marginBottom: 10, borderBottom: "1px solid #1a0a3a", paddingBottom: 8 }}>
                <div style={{ fontSize: 8, color: "#884499", letterSpacing: 2, marginBottom: 6, fontFamily: "'Orbitron', sans-serif" }}>AGENT MESSAGES</div>
                {agentEvents.slice(-4).map(entry => (
                  <div key={entry.id} className="ai-entry" style={{ borderLeftColor: "#00d4ff", marginBottom: 4 }}>
                    <div style={{ fontSize: 9, color: "#00d4ff", marginBottom: 2 }}>{entry.from_agent} → {entry.to_agent}</div>
                    <div style={{ color: "#8899bb", fontSize: 10 }}>{entry.content?.message || entry.type}</div>
                  </div>
                ))}
              </div>
            )}
            {aiLog.length === 0 ? (
              <div style={{ color: "#1a1a3a", fontSize: 10, fontFamily: "'Share Tech Mono', monospace", padding: "20px 0", textAlign: "center" }}>
                AI standing by...<span style={{ animation: "blink 1s infinite", display: "inline-block" }}>█</span>
              </div>
            ) : (
              aiLog.map(entry => {
                const colorMap = {
                  ok: "#00ff88", info: "#8899bb", action: "#cc44ff",
                  warn: "#ffaa00", error: "#ff3355", success: "#00ff88",
                };
                const color = colorMap[entry.type] || "#8899bb";
                return (
                  <div key={entry.id} className="ai-entry" style={{ borderLeftColor: color }}>
                    {entry.ts && <div style={{ fontSize: 9, color: "#334466", marginBottom: 2 }}>{entry.ts}</div>}
                    <div style={{ color, fontSize: 10 }}>{entry.text}</div>
                  </div>
                );
              })
            )}
            <div ref={aiEndRef} />
          </div>

          {/* AI Architecture visualization */}
          <div style={{ borderTop: "1px solid #0d2a4a", padding: "10px 12px" }}>
            <div style={{ fontSize: 8, color: "#1a3a6a", letterSpacing: 2, marginBottom: 8, fontFamily: "'Orbitron', sans-serif" }}>AGENT ARCHITECTURE</div>
            <div style={{ display: "flex", alignItems: "center", gap: 3, flexWrap: "wrap" }}>
              {["ANALYZE", "→", "PLAN", "→", "EXECUTE", "→", "VALIDATE"].map((step, i) => (
                <span key={i} style={{
                  fontSize: 8, fontFamily: "'Orbitron', sans-serif",
                  color: step === "→" ? "#0d2a4a" : "#334466",
                  letterSpacing: step === "→" ? 0 : 1,
                  padding: step === "→" ? "0 1px" : "2px 5px",
                  border: step === "→" ? "none" : "1px solid #0d2a4a",
                  borderRadius: 1,
                }}>{step}</span>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* Bottom: Credentials output */}
      {creds && (
        <div style={{
          borderTop: "1px solid #0d2a4a",
          padding: "16px 20px",
          background: "rgba(0,0,20,0.95)",
          animation: "fadeUp 0.5s ease",
        }}>
          <div style={{
            fontFamily: "'Orbitron', sans-serif",
            fontSize: 9, letterSpacing: 3,
            color: "#00ff88",
            marginBottom: 12,
            display: "flex", alignItems: "center", gap: 8,
          }}>
            <span>✓</span> DEPLOYMENT ARTIFACTS
          </div>
          <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
            {[
              { label: "SONARQUBE", icon: "🛡", url: creds.sonar.url, extra: `${creds.sonar.user} / ${creds.sonar.pass}` },
              { label: "JENKINS", icon: "⚙", url: creds.jenkins.url, extra: `${creds.jenkins.user} / ${creds.jenkins.pass}` },
              { label: "APPLICATION", icon: "🚀", url: creds.app.url, extra: "Live" },
              { label: "DOCKERHUB", icon: "🐳", url: creds.docker, extra: "pull ready" },
            ].map(card => (
              <div key={card.label} className="cred-card">
                <div style={{ fontSize: 8, color: "#334466", letterSpacing: 2, marginBottom: 8, fontFamily: "'Orbitron', sans-serif", display: "flex", alignItems: "center", gap: 6 }}>
                  <span>{card.icon}</span> {card.label}
                </div>
                <div style={{ fontSize: 11, color: "#00d4ff", fontFamily: "'Share Tech Mono', monospace", wordBreak: "break-all", marginBottom: 6 }}>{card.url}</div>
                <div style={{ fontSize: 10, color: "#556688", fontFamily: "'Share Tech Mono', monospace", marginBottom: 8 }}>{card.extra}</div>
                <button className="copy-btn" onClick={() => navigator.clipboard?.writeText(card.url)}>COPY</button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
