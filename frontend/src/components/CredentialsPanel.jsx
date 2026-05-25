import React, { useState, useEffect } from "react";

/**
 * CredentialsPanel - Display auto-generated credentials for all services
 * Shows what was auto-generated, never asks for user input
 */
function CredentialsPanel({ sessionId, serverIp }) {
  const [credentials, setCredentials] = useState(null);
  const [loading, setLoading] = useState(false);
  const [selectedService, setSelectedService] = useState("sonarqube");
  const [copiedField, setCopiedField] = useState(null);
  const [showPassword, setShowPassword] = useState({});

  useEffect(() => {
    fetchCredentials();
  }, [sessionId]);

  const fetchCredentials = async () => {
    if (!sessionId) return;

    setLoading(true);
    try {
      const response = await fetch(`/api/credentials/${sessionId}`);
      if (response.ok) {
        const data = await response.json();
        setCredentials(data);
      }
    } catch (error) {
      console.error("Error fetching credentials:", error);
    } finally {
      setLoading(false);
    }
  };

  const copyToClipboard = (text, field) => {
    navigator.clipboard.writeText(text);
    setCopiedField(field);
    setTimeout(() => setCopiedField(null), 2000);
  };

  const togglePassword = (field) => {
    setShowPassword((prev) => ({
      ...prev,
      [field]: !prev[field],
    }));
  };

  const renderCredentialField = (label, value, isSensitive = false, fieldId = null) => {
    const isPasswordField = isSensitive && label.toLowerCase().includes("password");
    const isHidden = isPasswordField && !showPassword[fieldId];
    const displayValue = isHidden ? "•".repeat(16) : value;

    return (
      <div
        key={fieldId}
        style={{
          marginBottom: "10px",
          padding: "8px",
          background: "rgba(0, 50, 100, 0.3)",
          borderRadius: "4px",
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <div>
          <div style={{ fontSize: "10px", color: "#00d4ff", fontWeight: "bold" }}>
            {label}
          </div>
          <div
            style={{
              fontSize: "11px",
              color: "#ccd6f6",
              fontFamily: "'Courier New', monospace",
              wordBreak: "break-all",
              marginTop: "4px",
            }}
          >
            {displayValue}
          </div>
        </div>
        <div style={{ display: "flex", gap: "6px" }}>
          {isPasswordField && (
            <button
              onClick={() => togglePassword(fieldId)}
              style={{
                background: "#0d3a5a",
                border: "1px solid #0d5a8a",
                color: "#00d4ff",
                padding: "4px 8px",
                borderRadius: "3px",
                fontSize: "9px",
                cursor: "pointer",
              }}
            >
              {isHidden ? "Show" : "Hide"}
            </button>
          )}
          <button
            onClick={() => copyToClipboard(value, fieldId)}
            style={{
              background: copiedField === fieldId ? "#00ff88" : "#0d3a5a",
              border: "1px solid #0d5a8a",
              color: copiedField === fieldId ? "#000" : "#00d4ff",
              padding: "4px 8px",
              borderRadius: "3px",
              fontSize: "9px",
              cursor: "pointer",
              fontWeight: copiedField === fieldId ? "bold" : "normal",
            }}
          >
            {copiedField === fieldId ? "Copied!" : "Copy"}
          </button>
        </div>
      </div>
    );
  };

  const services = [
    "sonarqube",
    "jenkins",
    "application",
    "database",
    "api_keys",
  ];

  const serviceColors = {
    sonarqube: "#00d4ff",
    jenkins: "#00ff88",
    application: "#cc44ff",
    database: "#ffaa00",
    api_keys: "#ff0066",
  };

  const serviceEmojis = {
    sonarqube: "🔍",
    jenkins: "🔧",
    application: "🚀",
    database: "💾",
    api_keys: "🔐",
  };

  if (loading) {
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "#334466" }}>
        Loading credentials...
      </div>
    );
  }

  if (!credentials) {
    return (
      <div style={{ padding: "20px", textAlign: "center", color: "#334466" }}>
        No credentials available
      </div>
    );
  }

  const selectedCreds = credentials[selectedService];

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
        }}
      >
        <span
          style={{
            fontFamily: "'Orbitron', 'Courier New', monospace",
            fontSize: "12px",
            color: "#ffaa00",
            fontWeight: "bold",
            letterSpacing: "2px",
          }}
        >
          🔐 AUTO-GENERATED CREDENTIALS
        </span>
        <div style={{ fontSize: "10px", color: "#334466", marginTop: "4px" }}>
          ✅ All credentials auto-generated. User input NOT required.
        </div>
      </div>

      {/* Service Tabs */}
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
        {services.map((service) => (
          <button
            key={service}
            onClick={() => setSelectedService(service)}
            style={{
              background: selectedService === service ? serviceColors[service] : "transparent",
              border: `1px solid ${serviceColors[service]}`,
              color: selectedService === service ? "#000" : serviceColors[service],
              padding: "6px 12px",
              borderRadius: "4px",
              fontSize: "10px",
              cursor: "pointer",
              fontWeight: selectedService === service ? "bold" : "normal",
              whiteSpace: "nowrap",
            }}
          >
            {serviceEmojis[service]} {service}
          </button>
        ))}
      </div>

      {/* Credentials Display */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "12px",
          background: "#0a0a1a",
        }}
      >
        {selectedCreds ? (
          <div>
            {/* Service Info */}
            <div style={{ marginBottom: "16px", padding: "12px", background: "rgba(0, 20, 40, 0.5)", borderRadius: "4px" }}>
              <div style={{ fontSize: "12px", color: serviceColors[selectedService], fontWeight: "bold", marginBottom: "8px" }}>
                {serviceEmojis[selectedService]} {selectedCreds.service || selectedService.toUpperCase()}
              </div>

              {selectedCreds.url && (
                <div style={{ fontSize: "10px", color: "#6688aa", marginBottom: "4px" }}>
                  <strong>URL:</strong> {selectedCreds.url}
                </div>
              )}

              {selectedCreds.host && (
                <div style={{ fontSize: "10px", color: "#6688aa", marginBottom: "4px" }}>
                  <strong>Host:</strong> {selectedCreds.host}:{selectedCreds.port}
                </div>
              )}

              {selectedCreds.generated_at && (
                <div style={{ fontSize: "9px", color: "#334466", marginTop: "8px" }}>
                  Generated: {new Date(selectedCreds.generated_at).toLocaleString()}
                </div>
              )}
            </div>

            {/* Credentials Fields */}
            <div>
              {Object.entries(selectedCreds).map(([key, value]) => {
                if (
                  key === "service" ||
                  key === "url" ||
                  key === "host" ||
                  key === "port" ||
                  key === "generated_at" ||
                  key === "display_password" ||
                  typeof value === "object"
                ) {
                  return null;
                }

                const isSensitive = key.toLowerCase().includes("password") || key.toLowerCase().includes("token") || key.toLowerCase().includes("secret") || key.toLowerCase().includes("key");

                return renderCredentialField(
                  key.replace(/_/g, " ").toUpperCase(),
                  String(value),
                  isSensitive,
                  `${selectedService}_${key}`
                );
              })}
            </div>

            {/* SSH Key Display (if applicable) */}
            {selectedCreds.ssh_key && (
              <div style={{ marginTop: "16px", padding: "12px", background: "rgba(0, 20, 40, 0.5)", borderRadius: "4px" }}>
                <div style={{ fontSize: "11px", color: "#00ff88", fontWeight: "bold", marginBottom: "8px" }}>
                  🔑 SSH Key Pair
                </div>
                <div style={{ fontSize: "9px", color: "#6688aa" }}>
                  <div>
                    <strong>Fingerprint:</strong> {selectedCreds.ssh_key.fingerprint}
                  </div>
                  <details style={{ marginTop: "8px", cursor: "pointer" }}>
                    <summary style={{ color: "#00d4ff" }}>Show SSH Keys</summary>
                    <div style={{ marginTop: "8px", fontFamily: "'Courier New', monospace" }}>
                      <div style={{ color: "#00ff88", fontSize: "8px", marginBottom: "8px" }}>
                        <strong>Public Key:</strong>
                        <pre
                          style={{
                            background: "#0a0a1a",
                            padding: "8px",
                            borderRadius: "3px",
                            overflowX: "auto",
                            fontSize: "8px",
                          }}
                        >
                          {selectedCreds.ssh_key.public_key}
                        </pre>
                      </div>
                    </div>
                  </details>
                </div>
              </div>
            )}
          </div>
        ) : (
          <div style={{ color: "#334466", fontSize: "12px", textAlign: "center", padding: "20px" }}>
            No credentials for this service
          </div>
        )}
      </div>

      {/* Footer */}
      <div
        style={{
          borderTop: "1px solid #0d2a4a",
          padding: "8px 12px",
          fontSize: "9px",
          color: "#334466",
          background: "#0d1a2a",
        }}
      >
        ✅ All credentials generated and ready to use. Never shared or stored in code.
      </div>
    </div>
  );
}

export default CredentialsPanel;
