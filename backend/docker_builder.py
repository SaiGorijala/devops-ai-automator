from __future__ import annotations

import json
import re
from pathlib import Path

from .process import run_command


class DockerBuilder:
    def detect_or_generate_dockerfile(self, project_path: str | Path, project_type: str) -> str:
        path = Path(project_path)
        dockerfile = path / "Dockerfile"
        if dockerfile.exists():
            return dockerfile.read_text(encoding="utf-8", errors="replace")
        content = self._generate(project_type, path)
        dockerfile.write_text(content, encoding="utf-8")
        return content

    def build_image(self, project_path: str | Path, tag: str) -> str:
        result = run_command(["docker", "build", "-t", tag, "."], cwd=project_path, timeout=1800)
        result.raise_for_error()
        inspect = run_command(["docker", "image", "inspect", tag, "--format", "{{.Id}}"], timeout=60)
        inspect.raise_for_error()
        return inspect.stdout.strip()

    def login_dockerhub(self, username: str, password: str) -> bool:
        result = run_command(
            ["docker", "login", "-u", username, "--password-stdin"],
            input_text=password,
            timeout=120,
        )
        result.raise_for_error()
        return True

    def push_image(self, tag: str) -> bool:
        result = run_command(["docker", "push", tag], timeout=1800)
        result.raise_for_error()
        return True

    def multi_tag_push(self, image: str, tags: list[str]) -> list[str]:
        pushed: list[str] = []
        for tag in tags:
            if tag != image:
                run_command(["docker", "tag", image, tag], timeout=120).raise_for_error()
            self.push_image(tag)
            pushed.append(tag)
        return pushed

    def infer_container_port(self, project_path: str | Path, project_type: str) -> int:
        dockerfile = Path(project_path) / "Dockerfile"
        if dockerfile.exists():
            match = re.search(r"(?im)^\s*EXPOSE\s+(\d+)", dockerfile.read_text(encoding="utf-8", errors="replace"))
            if match:
                return int(match.group(1))
        if project_type == "nodejs":
            return 3000
        if project_type == "python":
            return 8000
        if project_type in {"java", "go"}:
            return 8080
        return 3000

    def _generate(self, project_type: str, path: Path) -> str:
        if project_type == "nodejs":
            return self._node_dockerfile(path)
        if project_type == "python":
            return self._python_dockerfile(path)
        if project_type == "java":
            return self._java_dockerfile(path)
        if project_type == "go":
            return self._go_dockerfile()
        return self._generic_dockerfile()

    @staticmethod
    def _node_dockerfile(path: Path) -> str:
        package = path / "package.json"
        start_cmd = '["npm", "start"]'
        if package.exists():
            try:
                scripts = json.loads(package.read_text(encoding="utf-8")).get("scripts", {})
                if "start" not in scripts:
                    for candidate in ("server.js", "app.js", "index.js"):
                        if (path / candidate).exists():
                            start_cmd = f'["node", "{candidate}"]'
                            break
            except json.JSONDecodeError:
                pass
        return f"""FROM node:20-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

FROM node:20-alpine AS runtime
WORKDIR /app
ENV NODE_ENV=production
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm prune --omit=dev || true
EXPOSE 3000
CMD {start_cmd}
"""

    @staticmethod
    def _python_dockerfile(path: Path) -> str:
        if (path / "main.py").exists():
            cmd = '["python", "main.py"]'
        elif (path / "app.py").exists():
            cmd = '["python", "app.py"]'
        else:
            cmd = '["python", "-m", "app"]'
        return f"""FROM python:3.10-slim-buster
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
COPY . .
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt; elif [ -f pyproject.toml ]; then pip install --no-cache-dir .; fi
EXPOSE 8000
CMD {cmd}
"""

    @staticmethod
    def _java_dockerfile(path: Path) -> str:
        if (path / "pom.xml").exists():
            return """FROM maven:3.9-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
RUN mvn -q -DskipTests dependency:go-offline
COPY src ./src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/target/*.jar app.jar
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
"""
        return """FROM gradle:8-jdk17 AS build
WORKDIR /app
COPY . .
RUN gradle build -x test --no-daemon

FROM eclipse-temurin:17-jre
WORKDIR /app
COPY --from=build /app/build/libs/*.jar app.jar
EXPOSE 8080
CMD ["java", "-jar", "app.jar"]
"""

    @staticmethod
    def _go_dockerfile() -> str:
        return """FROM golang:1.22-alpine AS build
WORKDIR /src
COPY . .
RUN go mod download
RUN CGO_ENABLED=0 GOOS=linux go build -o /out/app .

FROM alpine:3.20
WORKDIR /app
COPY --from=build /out/app /app/app
EXPOSE 8080
CMD ["/app/app"]
"""

    @staticmethod
    def _generic_dockerfile() -> str:
        return """FROM nginx:alpine
WORKDIR /usr/share/nginx/html
COPY . .
EXPOSE 80
"""
