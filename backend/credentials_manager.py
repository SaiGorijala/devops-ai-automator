"""Credentials Manager - Auto-generates secure credentials for all services."""

from __future__ import annotations

import secrets
import string
from datetime import datetime
from typing import Any


class CredentialsManager:
    """Auto-generate secure credentials for all services.
    
    USER NEVER INPUTS CREDENTIALS - they are generated automatically.
    """

    def __init__(self):
        self.credentials_store: dict[str, Any] = {}

    def generate_all_credentials(self, server_ip: str) -> dict[str, Any]:
        """Generate all credentials at once.
        
        Args:
            server_ip: Target server IP address
            
        Returns:
            Dictionary of all auto-generated credentials.
        """

        credentials = {
            "sonarqube": self._generate_sonarqube_credentials(server_ip),
            "jenkins": self._generate_jenkins_credentials(server_ip),
            "application": self._generate_application_credentials(),
            "database": self._generate_database_credentials(),
            "api_keys": self._generate_api_keys(),
            "generated_at": datetime.now().isoformat(),
        }

        self.credentials_store = credentials
        print(f"[CREDENTIALS] Generated all credentials for {server_ip}")
        return credentials

    def _generate_sonarqube_credentials(self, server_ip: str) -> dict[str, Any]:
        """Generate SonarQube credentials."""
        password = self._generate_password(16)
        return {
            "service": "SonarQube",
            "url": f"http://{server_ip}:9081",
            "username": "admin",
            "password": password,
            "api_token": f"squ_{secrets.token_hex(20)}",
            "admin_token": f"admin_{secrets.token_hex(20)}",
            "display_password": f"Auto-generated: {password[:8]}***",
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_jenkins_credentials(self, server_ip: str) -> dict[str, Any]:
        """Generate Jenkins credentials."""
        password = self._generate_password(20)
        return {
            "service": "Jenkins",
            "url": f"http://{server_ip}:8081",
            "username": "admin",
            "password": password,
            "api_token": secrets.token_hex(32),
            "initial_password": self._generate_password(12),
            "ssh_key": self._generate_ssh_key_pair(),
            "display_password": f"Auto-generated: {password[:8]}***",
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_application_credentials(self) -> dict[str, Any]:
        """Generate application credentials."""
        username = f"appuser_{secrets.token_hex(4)}"
        return {
            "service": "Application",
            "username": username,
            "password": self._generate_password(12),
            "api_key": secrets.token_hex(24),
            "api_secret": secrets.token_hex(32),
            "jwt_secret": secrets.token_hex(64),
            "display_password": f"Auto-generated: AppUser123***",
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_database_credentials(self) -> dict[str, Any]:
        """Generate database credentials."""
        return {
            "service": "PostgreSQL",
            "host": "localhost",
            "port": 5432,
            "username": "devops_user",
            "password": self._generate_password(16),
            "database": "app_db",
            "root_password": self._generate_password(20),
            "connection_string": "postgresql://devops_user:***@localhost:5432/app_db",
            "display_password": f"Auto-generated: DbUser123***",
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_api_keys(self) -> dict[str, Any]:
        """Generate API keys."""
        return {
            "github_token": secrets.token_hex(32),
            "dockerhub_token": secrets.token_hex(32),
            "registry_token": secrets.token_hex(24),
            "sonar_webhook_secret": secrets.token_hex(24),
            "webhook_signing_key": secrets.token_hex(32),
            "encryption_key": secrets.token_hex(32),
            "generated_at": datetime.now().isoformat(),
        }

    def _generate_password(self, length: int = 16) -> str:
        """Generate secure random password with mixed character types.
        
        Args:
            length: Password length
            
        Returns:
            Secure random password.
        """
        alphabet = string.ascii_letters + string.digits + "!@#$%^&*-_=+"
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        # Ensure at least one uppercase, one lowercase, one digit, one special
        while not any(c.isupper() for c in password):
            password = password[:-1] + secrets.choice(string.ascii_uppercase)
        while not any(c.islower() for c in password):
            password = password[:-1] + secrets.choice(string.ascii_lowercase)
        while not any(c.isdigit() for c in password):
            password = password[:-1] + secrets.choice(string.digits)
        while not any(c in "!@#$%^&*-_=+" for c in password):
            password = password[:-1] + secrets.choice("!@#$%^&*-_=+")
        return password

    def _generate_ssh_key_pair(self) -> dict[str, str]:
        """Generate SSH key pair for secure access."""
        # This is a placeholder - in production, use cryptography library
        private_key = f"-----BEGIN RSA PRIVATE KEY-----\n{secrets.token_hex(256)}\n-----END RSA PRIVATE KEY-----"
        public_key = f"ssh-rsa {secrets.token_hex(128)} jenkins@devops"
        return {
            "private_key": private_key,
            "public_key": public_key,
            "fingerprint": secrets.token_hex(16),
        }

    def get_credentials(self) -> dict[str, Any]:
        """Get all stored credentials.
        
        Returns:
            All generated credentials.
        """
        return self.credentials_store

    def get_service_credentials(self, service: str) -> dict[str, Any] | None:
        """Get credentials for specific service.
        
        Args:
            service: Service name (sonarqube, jenkins, application, database)
            
        Returns:
            Service credentials or None if not found.
        """
        return self.credentials_store.get(service, None)

    def regenerate_service(self, service: str, server_ip: str | None = None) -> dict[str, Any]:
        """Regenerate credentials for specific service.
        
        Args:
            service: Service name
            server_ip: Server IP (required for some services)
            
        Returns:
            New credentials for the service.
        """
        if service == "sonarqube":
            new_creds = self._generate_sonarqube_credentials(server_ip or "localhost")
            self.credentials_store["sonarqube"] = new_creds
            return new_creds
        elif service == "jenkins":
            new_creds = self._generate_jenkins_credentials(server_ip or "localhost")
            self.credentials_store["jenkins"] = new_creds
            return new_creds
        elif service == "application":
            new_creds = self._generate_application_credentials()
            self.credentials_store["application"] = new_creds
            return new_creds
        elif service == "database":
            new_creds = self._generate_database_credentials()
            self.credentials_store["database"] = new_creds
            return new_creds
        elif service == "api_keys":
            new_creds = self._generate_api_keys()
            self.credentials_store["api_keys"] = new_creds
            return new_creds
        return {}

    def export_credentials_to_env(self) -> str:
        """Export credentials as environment variables format.
        
        Returns:
            String with environment variable definitions.
        """
        env_vars = []

        # SonarQube
        sonarqube = self.credentials_store.get("sonarqube", {})
        if sonarqube:
            env_vars.append(f"SONARQUBE_URL={sonarqube.get('url')}")
            env_vars.append(f"SONARQUBE_USER={sonarqube.get('username')}")
            env_vars.append(f"SONARQUBE_PASSWORD={sonarqube.get('password')}")
            env_vars.append(f"SONARQUBE_TOKEN={sonarqube.get('api_token')}")

        # Jenkins
        jenkins = self.credentials_store.get("jenkins", {})
        if jenkins:
            env_vars.append(f"JENKINS_URL={jenkins.get('url')}")
            env_vars.append(f"JENKINS_USER={jenkins.get('username')}")
            env_vars.append(f"JENKINS_PASSWORD={jenkins.get('password')}")
            env_vars.append(f"JENKINS_TOKEN={jenkins.get('api_token')}")

        # Database
        database = self.credentials_store.get("database", {})
        if database:
            env_vars.append(f"DB_HOST={database.get('host')}")
            env_vars.append(f"DB_PORT={database.get('port')}")
            env_vars.append(f"DB_USER={database.get('username')}")
            env_vars.append(f"DB_PASSWORD={database.get('password')}")
            env_vars.append(f"DB_NAME={database.get('database')}")

        # API Keys
        api_keys = self.credentials_store.get("api_keys", {})
        if api_keys:
            env_vars.append(f"GITHUB_TOKEN={api_keys.get('github_token')}")
            env_vars.append(f"DOCKERHUB_TOKEN={api_keys.get('dockerhub_token')}")

        return "\n".join(env_vars)

    def export_credentials_to_json(self) -> str:
        """Export credentials as JSON (for storage).
        
        Returns:
            JSON representation of credentials.
        """
        import json

        return json.dumps(self.credentials_store, indent=2, default=str)
