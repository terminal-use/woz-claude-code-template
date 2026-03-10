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
    return value.strip() if isinstance(value, str) and value.strip() else None


def _task_metadata_str(ctx: TaskContext, key: str) -> str | None:
    metadata = getattr(ctx.task, "task_metadata", None)
    if not isinstance(metadata, dict):
        return None
    value = metadata.get(key)
    return value.strip() if isinstance(value, str) and value.strip() else None


def _task_slack_thread_context(ctx: TaskContext) -> tuple[str | None, str | None]:
    channel = _task_param_str(ctx, "slack_channel") or _task_metadata_str(
        ctx, "slack_channel"
    )
    thread_ts = _task_param_str(ctx, "slack_thread_ts") or _task_metadata_str(
        ctx, "slack_thread_ts"
    )
    if channel and thread_ts:
        return (channel, thread_ts)

    thread_key = _task_param_str(ctx, "slack_thread_key") or _task_metadata_str(
        ctx, "slack_thread_key"
    )
    if not thread_key:
        return (channel, thread_ts)

    parts = thread_key.split(":")
    if len(parts) < 3:
        return (channel, thread_ts)

    if not channel:
        candidate = parts[1].strip()
        if candidate:
            channel = candidate
    if not thread_ts:
        candidate = ":".join(parts[2:]).strip()
        if candidate:
            thread_ts = candidate
    return (channel, thread_ts)


def _build_slack_mode_prompt(ctx: TaskContext, user_message: str) -> str:
    channel, thread_ts = _task_slack_thread_context(ctx)
    if not channel or not thread_ts:
        return user_message

    return (
        "[Slack thread response contract]\n"
        "- This task originated from a Slack thread.\n"
        f"- slack_channel: {channel}\n"
        f"- slack_thread_ts: {thread_ts}\n"
        "- REQUIRED: before ending this turn, post at least one user-visible reply in that Slack thread.\n"
        "- REQUIRED: include a short summary of what you changed or checked.\n"
        "- REQUIRED: if blocked/failing, post the exact blocker in that thread before ending.\n"
        "- Use the using-slack-tools skill script at /app/skills/using-slack-tools/scripts/slack_tools.py.\n"
        "- Do not rely only on Terminal Use output; the user reads Slack.\n"
        "[/Slack thread response contract]\n\n"
        "[User request]\n"
        f"{user_message}"
    )
