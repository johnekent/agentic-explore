from __future__ import annotations

import subprocess
from agentlab.tools.types import ToolResult


def local_exec(command: list[str], timeout_s: int = 60) -> ToolResult:
    try:
        proc = subprocess.run(command, capture_output=True, text=True, timeout=timeout_s, check=False)
        return ToolResult.success(
            {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}
        )
    except Exception as exc:
        return ToolResult.failure("exec_error", str(exc))
