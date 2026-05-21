FROM node:20-alpine AS frontend
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm ci || npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_BUILD_DIR=/app/frontend/dist

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       bash \
       ca-certificates \
       curl \
       docker.io \
       git \
       openjdk-17-jre-headless \
       openssh-client \
       unzip \
    && rm -rf /var/lib/apt/lists/*

RUN docker --version \
    && curl -fsSLo /tmp/sonar-scanner.zip \
       https://binaries.sonarsource.com/Distribution/sonar-scanner-cli/sonar-scanner-cli-5.0.1.3006-linux.zip \
    && unzip -q /tmp/sonar-scanner.zip -d /opt \
    && mv /opt/sonar-scanner-* /opt/sonar-scanner \
    && ln -sf /opt/sonar-scanner/bin/sonar-scanner /usr/local/bin/sonar-scanner \
    && sonar-scanner --version \
    && rm -f /tmp/sonar-scanner.zip

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY scripts ./scripts
COPY --from=frontend /frontend/dist ./frontend/dist

EXPOSE 8000
CMD ["uvicorn", "backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
