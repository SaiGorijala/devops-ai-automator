import React, { useState } from "react";
import "../styles/DeploymentForm.css";

export default function DeploymentForm({ onDeploy, isLoading }) {
  const [formData, setFormData] = useState({
    repo_url: "",
    github_token: "",
    server_ip: "",
    username: "ubuntu",
    pem_content: "",
  });

  const [errors, setErrors] = useState({});

  const handleChange = (e) => {
    const { name, value } = e.target;
    setFormData((prev) => ({ ...prev, [name]: value }));
    if (errors[name]) {
      setErrors((prev) => ({ ...prev, [name]: "" }));
    }
  };

  const validateForm = () => {
    const newErrors = {};
    if (!formData.repo_url.trim()) newErrors.repo_url = "Repository URL is required";
    if (!formData.github_token.trim()) newErrors.github_token = "GitHub token is required";
    if (!formData.server_ip.trim()) newErrors.server_ip = "Server IP is required";
    if (!formData.pem_content.trim()) newErrors.pem_content = "PEM key content is required";

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    if (validateForm()) {
      onDeploy(formData);
    }
  };

  return (
    <form className="deployment-form" onSubmit={handleSubmit}>
      <h2>🚀 Start Multi-Agent Deployment</h2>

      <div className="form-group">
        <label>Repository URL *</label>
        <input
          type="url"
          name="repo_url"
          placeholder="https://github.com/user/repo.git"
          value={formData.repo_url}
          onChange={handleChange}
          disabled={isLoading}
        />
        {errors.repo_url && <span className="error">{errors.repo_url}</span>}
      </div>

      <div className="form-group">
        <label>GitHub Personal Access Token *</label>
        <input
          type="password"
          name="github_token"
          placeholder="ghp_xxxxxxxxxxxxx"
          value={formData.github_token}
          onChange={handleChange}
          disabled={isLoading}
        />
        {errors.github_token && <span className="error">{errors.github_token}</span>}
      </div>

      <div className="form-row">
        <div className="form-group">
          <label>Target Server IP *</label>
          <input
            type="text"
            name="server_ip"
            placeholder="192.168.1.100"
            value={formData.server_ip}
            onChange={handleChange}
            disabled={isLoading}
          />
          {errors.server_ip && <span className="error">{errors.server_ip}</span>}
        </div>

        <div className="form-group">
          <label>SSH Username</label>
          <input
            type="text"
            name="username"
            placeholder="ubuntu"
            value={formData.username}
            onChange={handleChange}
            disabled={isLoading}
          />
        </div>
      </div>

      <div className="form-group">
        <label>SSH Private Key (PEM) *</label>
        <textarea
          name="pem_content"
          placeholder="-----BEGIN PRIVATE KEY-----&#10;...&#10;-----END PRIVATE KEY-----"
          value={formData.pem_content}
          onChange={handleChange}
          disabled={isLoading}
          rows={6}
        />
        {errors.pem_content && <span className="error">{errors.pem_content}</span>}
      </div>

      <button type="submit" disabled={isLoading} className="submit-btn">
        {isLoading ? (
          <>
            <span className="spinner">⟳</span> Deploying...
          </>
        ) : (
          <>
            🚀 Start Deployment
          </>
        )}
      </button>

      <div className="form-info">
        <p>ℹ️ Your credentials are secure and never stored on the server.</p>
      </div>
    </form>
  );
}
