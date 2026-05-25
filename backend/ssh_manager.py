from __future__ import annotations

import io
import json
import posixpath
import shlex
import socket
import time
from dataclasses import dataclass

import paramiko

from .config import settings


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int
    command: str

    def __iter__(self):
        yield self.stdout
        yield self.stderr
        yield self.exit_code

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def raise_for_error(self) -> "CommandResult":
        if not self.ok:
            detail = self.stderr.strip() or self.stdout.strip() or "no command output"
            raise RuntimeError(f"Command failed ({self.exit_code}): {self.command}\n{detail}")
        return self


class SSHManager:
    def __init__(
        self,
        client: paramiko.SSHClient,
        server_ip: str,
        username: str,
        port: int = 22,
    ) -> None:
        self.client = client
        self.server_ip = server_ip
        self.username = username
        self.port = port

    @classmethod
    def connect(
        cls,
        server_ip: str,
        pem_content: str,
        username: str | None = None,
        timeout: int | None = None,
    ) -> "SSHManager":
        parsed_user, host, port = cls._parse_target(server_ip)
        ssh_user = username or parsed_user or settings.ssh_user
        timeout = timeout or settings.ssh_timeout
        print(f"[SSH] Connecting to {host}:{port} as {ssh_user}", flush=True)
        diagnostics = cls.connectivity_diagnostics(host, port, timeout=min(timeout, 10))
        private_key = cls._load_private_key(pem_content)

        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        try:
            client.connect(
                hostname=host,
                port=port,
                username=ssh_user,
                pkey=private_key,
                timeout=timeout,
                banner_timeout=max(timeout, 30),
                auth_timeout=timeout,
                look_for_keys=False,
                allow_agent=False,
            )
            transport = client.get_transport()
            if transport:
                transport.set_keepalive(30)
            manager = cls(client=client, server_ip=host, username=ssh_user, port=port)
            manager.execute_command("echo SSH_CONNECTED", timeout=15).raise_for_error()
            print(f"[SSH] Connected successfully to {host}:{port}", flush=True)
            return manager
        except Exception as exc:  # noqa: BLE001 - enrich all SSH connection failures for the AI solver.
            client.close()
            error_type = cls._classify_connect_error(exc)
            payload = {
                "error_type": error_type,
                "host": host,
                "port": port,
                "username": ssh_user,
                "diagnostics": diagnostics,
                "message": str(exc),
                "hint": cls._connect_hint(error_type),
            }
            print(f"[SSH] Connection failed: {json.dumps(payload, sort_keys=True)}", flush=True)
            raise RuntimeError(f"SSH connection failed: {json.dumps(payload, sort_keys=True)}") from exc

    @classmethod
    def connectivity_diagnostics(cls, host: str, port: int = 22, timeout: int = 10) -> dict[str, object]:
        diagnostics: dict[str, object] = {
            "host": host,
            "port": port,
            "dns": False,
            "tcp_connect": False,
        }
        try:
            addresses = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
            diagnostics["dns"] = True
            diagnostics["addresses"] = sorted({item[4][0] for item in addresses})
        except OSError as exc:
            diagnostics["dns_error"] = str(exc)
            return diagnostics
        start = time.time()
        try:
            with socket.create_connection((host, port), timeout=timeout):
                diagnostics["tcp_connect"] = True
        except OSError as exc:
            diagnostics["tcp_error"] = str(exc)
        diagnostics["tcp_elapsed_seconds"] = round(time.time() - start, 2)
        return diagnostics

    @staticmethod
    def _classify_connect_error(exc: Exception) -> str:
        text = str(exc).lower()
        if "error reading ssh protocol banner" in text or "protocol banner" in text:
            return "ssh_protocol_banner"
        if "timed out" in text or isinstance(exc, socket.timeout):
            return "ssh_timeout"
        if "authentication" in text or "not found in known_hosts" in text:
            return "ssh_authentication"
        if "no route to host" in text or "network is unreachable" in text:
            return "network_unreachable"
        if "connection refused" in text:
            return "connection_refused"
        return exc.__class__.__name__

    @staticmethod
    def _connect_hint(error_type: str) -> str:
        hints = {
            "ssh_protocol_banner": "TCP port is reachable but did not return a valid SSH banner in time. Check security group, firewall, SSH daemon health, wrong port, or a non-SSH service on the port.",
            "ssh_timeout": "The target did not complete SSH handshake before timeout. Check public IP, inbound port 22, route table, and instance status.",
            "ssh_authentication": "The server rejected authentication. Check username, PEM key, and authorized_keys.",
            "network_unreachable": "The backend cannot route to the target host.",
            "connection_refused": "The host actively refused the TCP connection. SSH may not be running or the wrong port is configured.",
        }
        return hints.get(error_type, "Inspect SSH connectivity, authentication, and target service logs.")

    @staticmethod
    def _parse_target(target: str) -> tuple[str | None, str, int]:
        username = None
        host = target.strip()
        port = 22
        if "@" in host:
            username, host = host.split("@", 1)
        if ":" in host and host.count(":") == 1:
            host_part, port_part = host.rsplit(":", 1)
            if port_part.isdigit():
                host = host_part
                port = int(port_part)
        return username, host, port

    @staticmethod
    def _load_private_key(pem_content: str) -> paramiko.PKey:
        key_stream = io.StringIO(pem_content.replace("\r\n", "\n"))
        key_classes = [
            paramiko.Ed25519Key,
            paramiko.ECDSAKey,
            paramiko.RSAKey,
            paramiko.DSSKey,
        ]
        errors: list[str] = []
        for key_cls in key_classes:
            key_stream.seek(0)
            try:
                return key_cls.from_private_key(key_stream)
            except Exception as exc:  # noqa: BLE001 - keep trying key formats.
                errors.append(f"{key_cls.__name__}: {exc}")
        raise ValueError("Unable to parse PEM private key. " + " | ".join(errors))

    def execute_command(
        self,
        cmd: str,
        timeout: int = 30,
        get_pty: bool = False,
    ) -> CommandResult:
        stdin, stdout, stderr = self.client.exec_command(
            cmd,
            timeout=timeout,
            get_pty=get_pty,
        )
        stdin.close()
        out_chunks: list[bytes] = []
        err_chunks: list[bytes] = []
        channel = stdout.channel
        deadline = time.time() + timeout
        while not channel.exit_status_ready():
            if channel.recv_ready():
                out_chunks.append(channel.recv(65535))
            if channel.recv_stderr_ready():
                err_chunks.append(channel.recv_stderr(65535))
            if time.time() > deadline:
                channel.close()
                raise TimeoutError(f"SSH command timed out after {timeout}s: {cmd}")
            time.sleep(0.1)
        while channel.recv_ready():
            out_chunks.append(channel.recv(65535))
        while channel.recv_stderr_ready():
            err_chunks.append(channel.recv_stderr(65535))
        exit_code = channel.recv_exit_status()
        return CommandResult(
            stdout=b"".join(out_chunks).decode("utf-8", errors="replace"),
            stderr=b"".join(err_chunks).decode("utf-8", errors="replace"),
            exit_code=exit_code,
            command=cmd,
        )

    def execute(self, cmd: str, timeout: int = 30) -> CommandResult:
        return self.execute_command(cmd, timeout=timeout)

    def install_docker(self) -> bool:
        if self.execute_command("command -v docker", timeout=10).ok:
            self.execute_command("sudo systemctl enable --now docker || true", timeout=30)
            return True

        install_cmd = (
            "set -e; "
            "sudo apt-get update -y; "
            "sudo apt-get install -y ca-certificates curl gnupg iproute2 lsb-release; "
            "curl -fsSL https://get.docker.com | sudo sh; "
            "sudo systemctl enable --now docker; "
            f"sudo usermod -aG docker {shlex.quote(self.username)} || true; "
            "docker --version || sudo docker --version"
        )
        self.execute_command(install_cmd, timeout=600, get_pty=True).raise_for_error()
        return True

    def install_docker_compose(self) -> bool:
        if self.execute_command("docker compose version || sudo docker compose version", timeout=15).ok:
            return True

        install_plugin = (
            "set -e; "
            "sudo apt-get update -y; "
            "sudo apt-get install -y docker-compose-plugin || "
            "("
            "ARCH=$(uname -m); "
            "case \"$ARCH\" in x86_64) ARCH=x86_64 ;; aarch64|arm64) ARCH=aarch64 ;; *) ARCH=x86_64 ;; esac; "
            "sudo mkdir -p /usr/local/lib/docker/cli-plugins; "
            "sudo curl -SL "
            "https://github.com/docker/compose/releases/download/v2.27.0/docker-compose-linux-${ARCH} "
            "-o /usr/local/lib/docker/cli-plugins/docker-compose; "
            "sudo chmod +x /usr/local/lib/docker/cli-plugins/docker-compose"
            "); "
            "docker compose version || sudo docker compose version"
        )
        self.execute_command(install_plugin, timeout=300, get_pty=True).raise_for_error()
        return True

    def transfer_file(self, local_content: str | bytes, remote_path: str, mode: str = "0644") -> None:
        remote_dir = posixpath.dirname(remote_path)
        safe_dir = shlex.quote(remote_dir)
        safe_path = shlex.quote(remote_path)
        tmp_path = f"/tmp/devops-ai-{int(time.time() * 1000)}"
        self.execute_command(f"mkdir -p {safe_dir} || sudo mkdir -p {safe_dir}", timeout=30)
        sftp = self.client.open_sftp()
        try:
            write_mode = "wb" if isinstance(local_content, bytes) else "w"
            with sftp.file(tmp_path, write_mode) as remote_file:
                remote_file.write(local_content)
        finally:
            sftp.close()
        self.execute_command(
            f"sudo mv {shlex.quote(tmp_path)} {safe_path} && sudo chmod {mode} {safe_path}",
            timeout=30,
        ).raise_for_error()

    def check_ports_available(self, ports_list: list[int]) -> dict[int, bool]:
        availability: dict[int, bool] = {}
        for port in ports_list:
            cmd = f"sudo ss -ltn '( sport = :{int(port)} )' | tail -n +2 | grep -q ."
            result = self.execute_command(cmd, timeout=10)
            availability[int(port)] = not result.ok
        return availability

    def first_available_port(self, preferred: int, limit: int = 20) -> int:
        ports = list(range(preferred, preferred + limit))
        availability = self.check_ports_available(ports)
        for port, available in availability.items():
            if available:
                return port
        raise RuntimeError(f"No available TCP port found in range {preferred}-{preferred + limit - 1}")

    def close(self) -> None:
        self.client.close()

    def __enter__(self) -> "SSHManager":
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


def assert_host_reachable(host: str, port: int = 22, timeout: int = 5) -> None:
    with socket.create_connection((host, port), timeout=timeout):
        return
