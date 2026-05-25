"""Agent 1: Repository Analyzer - Scans and analyzes repository structure."""

from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

from ..llm_client import LLMClient


class RepositoryAnalyzer:
    """Agent 1: Analyzes repository structure and detects application type."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client
        self.analysis_cache: dict[str, dict[str, Any]] = {}

    async def analyze(self, repo_path: str, github_token: str | None = None) -> dict[str, Any]:
        """Complete repository analysis.
        
        Args:
            repo_path: Path to repository (local or URL)
            github_token: Optional GitHub token for private repos
            
        Returns:
            Deployment plan with project type, dependencies, entry points, etc.
        """
        try:
            # Ensure we have local path
            local_path = await self._get_local_repo(repo_path, github_token)

            # Scan files
            files = self._scan_files(local_path)

            # Detect application type
            app_type = self._detect_app_type(files)

            # Extract dependencies
            dependencies = self._extract_dependencies(local_path, app_type)

            # Find entry points
            entry_points = self._find_entry_points(local_path, app_type)

            # Detect ports
            ports = self._detect_ports(local_path, files)

            # Use LLM for enhanced analysis
            llm_analysis = await self._llm_enhance_analysis(
                app_type, dependencies, entry_points, files
            )

            # Build deployment plan
            deployment_plan = {
                "project_type": app_type,
                "dependencies": dependencies[:20],
                "entry_points": entry_points,
                "suggested_ports": ports,
                "build_command": llm_analysis.get(
                    "build_command", self._get_default_build_command(app_type)
                ),
                "start_command": llm_analysis.get(
                    "start_command", self._get_default_start_command(app_type)
                ),
                "environment_variables": llm_analysis.get("env_vars", []),
                "database_required": llm_analysis.get("database", False),
                "special_configs": llm_analysis.get("special_configs", {}),
                "confidence_score": llm_analysis.get("confidence", 0.8),
                "analyzed_at": datetime.now().isoformat(),
                "repo_path": str(local_path),
                "total_files": len(files),
            }

            # Store for agent communication
            self.analysis_cache[repo_path] = deployment_plan

            return deployment_plan
        except Exception as e:
            return {
                "error": str(e),
                "project_type": "unknown",
                "dependencies": [],
                "entry_points": [],
                "suggested_ports": [3000],
                "confidence_score": 0.0,
            }

    async def _llm_enhance_analysis(
        self, app_type: str, dependencies: list[str], entry_points: list[str], files: list[str]
    ) -> dict[str, Any]:
        """Use LLM to enhance repository analysis."""

        key_files = [
            f
            for f in files
            if f.endswith((".json", ".yaml", ".yml", ".toml", ".py", ".js", ".ts"))
        ][:15]

        prompt = f"""Analyze this application and provide deployment instructions:

Application Type: {app_type}
Dependencies: {dependencies[:10]}
Entry Points: {entry_points}
Key Files: {key_files}

Return ONLY valid JSON (no markdown, no extra text):
{{
    "build_command": "exact command to build",
    "start_command": "exact command to start",
    "env_vars": ["PORT=3000", "NODE_ENV=production"],
    "database": false,
    "special_configs": {{}},
    "confidence": 0.9
}}"""

        response = await self.llm.query(prompt, agent="RepositoryAnalyzer")
        if response:
            try:
                return json.loads(response)
            except json.JSONDecodeError:
                # Try to extract JSON
                match = re.search(r"\{.*\}", response, re.DOTALL)
                if match:
                    try:
                        return json.loads(match.group())
                    except json.JSONDecodeError:
                        pass
        return {}

    async def _get_local_repo(self, repo_path: str, github_token: str | None = None) -> Path:
        """Get local repository path, cloning if necessary."""
        path = Path(repo_path)
        if path.exists() and path.is_dir():
            return path

        # Clone from URL
        import tempfile

        temp_dir = Path(tempfile.mkdtemp())
        git_url = repo_path
        if github_token and "github.com" in repo_path:
            git_url = repo_path.replace("https://", f"https://{github_token}@")

        subprocess.run(["git", "clone", git_url, str(temp_dir)], check=True)
        return temp_dir

    def _scan_files(self, repo_path: Path) -> list[str]:
        """Recursively scan repository files."""
        files = []
        try:
            for item in repo_path.rglob("*"):
                if item.is_file() and not str(item).startswith("."):
                    files.append(item.name)
        except Exception:
            pass
        return list(set(files))[:200]

    def _detect_app_type(self, files: list[str]) -> str:
        """Detect application type from files."""
        if any(f.endswith("package.json") for f in files):
            return "nodejs"
        elif any(f.endswith(("requirements.txt", "setup.py", "pyproject.toml")) for f in files):
            return "python"
        elif any(f.endswith("pom.xml") for f in files):
            return "java-maven"
        elif any(f.endswith("go.mod") for f in files):
            return "golang"
        elif any(f.endswith("Dockerfile") for f in files):
            return "dockerized"
        elif any(f.endswith("Gemfile") for f in files):
            return "ruby"
        elif any(f.endswith(".php") for f in files):
            return "php"
        return "unknown"

    def _extract_dependencies(self, repo_path: Path, app_type: str) -> list[str]:
        """Extract dependencies based on app type."""
        deps = []
        try:
            if app_type == "nodejs":
                package_json = repo_path / "package.json"
                if package_json.exists():
                    data = json.loads(package_json.read_text())
                    deps = list(data.get("dependencies", {}).keys())[:20]

            elif app_type == "python":
                req_file = repo_path / "requirements.txt"
                if req_file.exists():
                    deps = [
                        line.split("==")[0].split(">=")[0].strip()
                        for line in req_file.read_text().splitlines()
                        if line.strip() and not line.startswith("#")
                    ][:20]

            elif app_type == "java-maven":
                pom_file = repo_path / "pom.xml"
                if pom_file.exists():
                    pom_content = pom_file.read_text()
                    deps = re.findall(r"<artifactId>(.*?)</artifactId>", pom_content)[:20]

            elif app_type == "golang":
                go_mod = repo_path / "go.mod"
                if go_mod.exists():
                    deps = re.findall(r"require\s+(.*?)(?:\n|$)", go_mod.read_text())[:20]
        except Exception:
            pass

        return deps

    def _find_entry_points(self, repo_path: Path, app_type: str) -> list[str]:
        """Find application entry points."""
        entry_points = []
        try:
            if app_type == "nodejs":
                if (repo_path / "package.json").exists():
                    data = json.loads((repo_path / "package.json").read_text())
                    entry_points.append(data.get("main", "index.js"))
                    entry_points.append("src/index.js")

            elif app_type == "python":
                for file in [
                    "app.py",
                    "main.py",
                    "run.py",
                    "wsgi.py",
                    "manage.py",
                ]:
                    if (repo_path / file).exists():
                        entry_points.append(file)

            elif app_type == "java-maven":
                entry_points.append("target/application.jar")

            elif app_type == "golang":
                entry_points.append("main.go")
        except Exception:
            pass

        return [ep for ep in entry_points if ep][:5]

    def _detect_ports(self, repo_path: Path, files: list[str]) -> list[int]:
        """Detect ports from configuration files."""
        ports = []
        try:
            # Check common config files
            for config_file in [
                ".env",
                "docker-compose.yml",
                "Dockerfile",
                "app.config",
            ]:
                path = repo_path / config_file
                if path.exists():
                    content = path.read_text()
                    port_matches = re.findall(r"PORT\s*[:=]\s*(\d+)", content)
                    ports.extend(int(p) for p in port_matches)
        except Exception:
            pass

        # Default ports by type
        if not ports:
            ports = [3000, 8000, 5000, 8080]

        return list(set(ports))[:5]

    def _get_default_build_command(self, app_type: str) -> str:
        """Get default build command for app type."""
        commands = {
            "nodejs": "npm install && npm run build",
            "python": "pip install -r requirements.txt",
            "java-maven": "mvn clean package",
            "golang": "go build -o app",
            "ruby": "bundle install",
            "php": "composer install",
            "dockerized": "docker build -t app .",
        }
        return commands.get(app_type, 'echo "No build command specified"')

    def _get_default_start_command(self, app_type: str) -> str:
        """Get default start command for app type."""
        commands = {
            "nodejs": "npm start",
            "python": "python app.py",
            "java-maven": "java -jar target/app.jar",
            "golang": "./app",
            "ruby": "bundle exec ruby app.rb",
            "php": "php -S localhost:8000",
            "dockerized": "docker run -p 3000:3000 app",
        }
        return commands.get(app_type, 'echo "No start command specified"')
