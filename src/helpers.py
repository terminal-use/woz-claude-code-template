"""Shared helper utilities for the coding workspace agent."""

import subprocess

from terminaluse.lib import TaskContext


def _run(
    args: list[str],
    *,
    cwd: str | None = None,
    timeout: int = 120,
    input_text: str | None = None,
    env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=cwd,
        env=env,
        input=input_text,
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _task_param_str(ctx: TaskContext, key: str) -> str | None:
    params = getattr(ctx.task, "params", None)
    if not isinstance(params, dict):
        return None
    value = params.get(key)
    return value if isinstance(value, str) and value.strip() else None
