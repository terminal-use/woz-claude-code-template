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


def _task_slack_reply_identity(
    ctx: TaskContext,
) -> tuple[str | None, str | None, str | None]:
    username = (
        _task_param_str(ctx, "slack_reply_username")
        or _task_metadata_str(ctx, "slack_reply_username")
        or _task_param_str(ctx, "target_agent_branch")
        or _task_metadata_str(ctx, "target_agent_branch")
        or _task_param_str(ctx, "coding_agent_name")
        or _task_metadata_str(ctx, "coding_agent_name")
    )
    if username:
        username = username.strip()[:80]

    icon_emoji = _task_param_str(ctx, "slack_reply_icon_emoji") or _task_metadata_str(
        ctx, "slack_reply_icon_emoji"
    )
    icon_url = _task_param_str(ctx, "slack_reply_icon_url") or _task_metadata_str(
        ctx, "slack_reply_icon_url"
    )
    if username and not icon_emoji:
        icon_emoji = ":robot_face:"
    return (username, icon_emoji, icon_url)


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
        "- Use `using-slack-tools` script when available. Check, in order: /workspace/skills/using-slack-tools/scripts/slack_tools.py, /workspace/.claude/skills/using-slack-tools/scripts/slack_tools.py, /workspace/.codex/skills/using-slack-tools/scripts/slack_tools.py, /app/skills/using-slack-tools/scripts/slack_tools.py.\n"
        "- If no `slack_tools.py` path exists, post directly via Slack Web API `chat.postMessage` with `SLACK_BOT_TOKEN`, `WOZ_SLACK_CHANNEL`, `WOZ_SLACK_THREAD_TS`, and set `username` + icon fields from `WOZ_SLACK_REPLY_USERNAME`, `WOZ_SLACK_REPLY_ICON_EMOJI`, `WOZ_SLACK_REPLY_ICON_URL`.\n"
        "- Do not rely only on Terminal Use output; the user reads Slack.\n"
        "[/Slack thread response contract]\n\n"
        "[User request]\n"
        f"{user_message}"
    )
