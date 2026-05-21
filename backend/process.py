from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class LocalCommandResult:
    stdout: str
    stderr: str
    exit_code: int
    command: list[str]

    @property
    def ok(self) -> bool:
        return self.exit_code == 0

    def raise_for_error(self) -> "LocalCommandResult":
        if not self.ok:
            output = self.stderr.strip() or self.stdout.strip() or "no command output"
            raise RuntimeError(f"Local command failed ({self.exit_code}): {' '.join(self.command)}\n{output}")
        return self


def run_command(
    command: list[str],
    cwd: str | Path | None = None,
    timeout: int = 300,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> LocalCommandResult:
    completed = subprocess.run(
        command,
        cwd=str(cwd) if cwd else None,
        input=input_text,
        text=True,
        capture_output=True,
        timeout=timeout,
        env=env,
        check=False,
    )
    return LocalCommandResult(
        stdout=completed.stdout,
        stderr=completed.stderr,
        exit_code=completed.returncode,
        command=command,
    )

