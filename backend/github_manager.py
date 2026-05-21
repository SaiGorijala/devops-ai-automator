from __future__ import annotations

import json
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote, urlparse

import httpx

from .config import settings
from .process import run_command


@dataclass
class RepoInfo:
    path: Path
    project_type: str
    commit_sha: str
    repo_url: str
    branch: str


class GitHubManager:
    def __init__(self, session_id: str) -> None:
        self.session_id = session_id
        self.repo_path = settings.local_workspace / "repos" / session_id / "source"
        self.repo_path.parent.mkdir(parents=True, exist_ok=True)

    def clone_repo(self, repo_url: str, token: str | None, branch: str = "main") -> Path:
        if self.repo_path.exists():
            shutil.rmtree(self.repo_path)
        clone_url = self._with_token(repo_url, token)
        result = run_command(
            ["git", "clone", "--depth", "1", "--branch", branch, clone_url, str(self.repo_path)],
            timeout=600,
        )
        if not result.ok and branch == "main":
            result = run_command(
                ["git", "clone", "--depth", "1", clone_url, str(self.repo_path)],
                timeout=600,
            )
        if not result.ok:
            output = self._mask_secret(result.stderr or result.stdout, token)
            raise RuntimeError(f"git clone failed for {self._mask_secret(repo_url, token)}: {output}")
        return self.repo_path

    def detect_project_type(self, project_path: str | Path | None = None) -> str:
        path = Path(project_path or self.repo_path)
        if (path / "package.json").exists():
            return "nodejs"
        if (path / "pyproject.toml").exists() or (path / "requirements.txt").exists():
            return "python"
        if (path / "pom.xml").exists() or (path / "build.gradle").exists() or (path / "build.gradle.kts").exists():
            return "java"
        if (path / "go.mod").exists():
            return "go"
        return "unknown"

    def get_file_content(self, file_path: str) -> str:
        path = (self.repo_path / file_path).resolve()
        if self.repo_path.resolve() not in path.parents and path != self.repo_path.resolve():
            raise ValueError("Requested file is outside the cloned repository")
        return path.read_text(encoding="utf-8", errors="replace")

    def commit_sha(self, project_path: str | Path | None = None) -> str:
        path = Path(project_path or self.repo_path)
        result = run_command(["git", "rev-parse", "--short", "HEAD"], cwd=path, timeout=30)
        if result.ok:
            return result.stdout.strip()
        return self.session_id[:8]

    def create_pull_request(
        self,
        fixes: str,
        token: str,
        title: str = "AI generated DevOps fixes",
        body: str = "Automated fixes proposed by DevOps AI Automator.",
    ) -> str:
        repo_slug = self._repo_slug()
        if not repo_slug:
            raise ValueError("Unable to infer GitHub owner/repo from origin URL")
        branch = f"ai-fixes/{self.session_id[:8]}"
        run_command(["git", "checkout", "-B", branch], cwd=self.repo_path, timeout=60).raise_for_error()
        run_command(["git", "add", "."], cwd=self.repo_path, timeout=60).raise_for_error()
        diff = run_command(["git", "diff", "--cached", "--stat"], cwd=self.repo_path, timeout=60)
        if not diff.stdout.strip():
            raise RuntimeError(f"No changes to commit for pull request. Last fixes: {fixes}")
        run_command(["git", "commit", "-m", title], cwd=self.repo_path, timeout=120).raise_for_error()
        origin = self._with_token(self._origin_url(), token)
        push = run_command(["git", "push", origin, branch, "--force"], cwd=self.repo_path, timeout=600)
        if not push.ok:
            raise RuntimeError(f"git push failed: {self._mask_secret(push.stderr or push.stdout, token)}")
        response = httpx.post(
            f"https://api.github.com/repos/{repo_slug}/pulls",
            headers={
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            json={"title": title, "head": branch, "base": "main", "body": body},
            timeout=30,
        )
        response.raise_for_status()
        return response.json()["html_url"]

    def package_metadata(self) -> dict:
        package_json = self.repo_path / "package.json"
        if not package_json.exists():
            return {}
        try:
            return json.loads(package_json.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}

    @staticmethod
    def _with_token(repo_url: str, token: str | None) -> str:
        if not token or "github.com" not in repo_url or "@" in repo_url:
            return repo_url
        parsed = urlparse(repo_url)
        if parsed.scheme not in {"http", "https"}:
            return repo_url
        safe_token = quote(token, safe="")
        return parsed._replace(netloc=f"{safe_token}@{parsed.netloc}").geturl()

    @staticmethod
    def _mask_secret(value: str, secret: str | None) -> str:
        if not secret:
            return value
        return value.replace(secret, "***")

    def _origin_url(self) -> str:
        result = run_command(["git", "remote", "get-url", "origin"], cwd=self.repo_path, timeout=30)
        result.raise_for_error()
        return result.stdout.strip()

    def _repo_slug(self) -> str | None:
        origin = self._origin_url()
        origin = re.sub(r"https://[^@]+@", "https://", origin)
        match = re.search(r"github\.com[:/](?P<owner>[^/]+)/(?P<repo>[^/.]+)(?:\.git)?", origin)
        if not match:
            return None
        return f"{match.group('owner')}/{match.group('repo')}"
