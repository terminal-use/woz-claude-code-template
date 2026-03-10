"""Coding Workspace Agent.

Clones a GitHub repo on task creation, configures GitHub auth, and proxies
messages to the Claude Agent SDK.
"""

import logging
import os
import subprocess
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import ResultMessage

from .github_ops import _bootstrap_github_auth, _clone_repo, _ensure_valid_github_token
from .helpers import (
    _build_slack_mode_prompt,
    _task_metadata_str,
    _task_param_str,
    _task_slack_thread_context,
)
from terminaluse.lib import (
    AgentServer,
    TaskContext,
    make_logger,
)
from terminaluse.types import Event, TextPart as SDKTextPart

for _name in (
    "httpx", "httpcore", "uvicorn.access", "terminaluse.lib.telemetry",
    "terminaluse.lib.sdk.fastacp", "opentelemetry", "opentelemetry.instrumentation",
):
    logging.getLogger(_name).setLevel(logging.WARNING)

logger = make_logger(__name__)

WORKSPACE_DIR = "/workspace"

SYSTEM_PROMPT = """
After you finish a task, create a commit, push to GitHub, and draft a PR.

If this task includes Slack thread context (`slack_channel` and `slack_thread_ts`):
- Before ending the turn, post at least one user-visible reply in that thread.
- Include a short summary of what you changed or checked.
- If blocked, post the exact blocker in that thread.
- Use `using-slack-tools` script when available. Check, in order: `/workspace/skills/using-slack-tools/scripts/slack_tools.py`, `/workspace/.claude/skills/using-slack-tools/scripts/slack_tools.py`, `/workspace/.codex/skills/using-slack-tools/scripts/slack_tools.py`, `/app/skills/using-slack-tools/scripts/slack_tools.py`.
- If no script path exists, post directly via Slack Web API `chat.postMessage` using `SLACK_BOT_TOKEN`, `WOZ_SLACK_CHANNEL`, and `WOZ_SLACK_THREAD_TS`.
- Do not rely only on Terminal Use output for user-visible communication.
""".strip()

server = AgentServer()


# Handlers
# ---------------------------------------------------------------------------


@server.on_create
async def handle_create(ctx: TaskContext, params: dict[str, Any]):
    repo_url = params.get("repo_url")
    github_token = params.get("github_token")
    logger.info("task_create task_id=%s repo_url=%s", ctx.task.id, repo_url)

    await ctx.state.create(state={"session_id": None, "github_auth_ok": False})

    if not repo_url:
        logger.error("missing_repo_url task_id=%s", ctx.task.id)
        return

    logger.info("cloning task_id=%s repo_url=%s", ctx.task.id, repo_url)

    try:
        result = _clone_repo(repo_url, github_token, workspace_dir=WORKSPACE_DIR)
        if result.returncode != 0:
            stderr = (result.stderr or "").strip() or "Unknown git clone failure"
            if github_token:
                stderr = stderr.replace(github_token, "***")
            if not github_token and "could not read Username" in stderr:
                stderr = "Repository may be private. Reconnect GitHub and retry."
            logger.error("clone_failed task_id=%s reason=%s", ctx.task.id, stderr)
            return

        logger.info("clone_ok task_id=%s", ctx.task.id)

        auth_ok = await _bootstrap_github_auth(
            ctx,
            github_token=github_token,
            github_login=params.get("github_login"),
            git_author_email=params.get("git_author_email"),
            repo_owner=params.get("repo_owner"),
            repo_name=params.get("repo_name"),
            workspace_dir=WORKSPACE_DIR,
        )
        await ctx.state.update({"github_auth_ok": auth_ok})
        if auth_ok:
            logger.info("github_auth_ok task_id=%s", ctx.task.id)

        await ctx.messages.send("Workspace is ready.")

    except subprocess.TimeoutExpired:
        logger.error("clone_timeout task_id=%s", ctx.task.id)
    except Exception as e:
        logger.exception("clone_error task_id=%s", ctx.task.id)


@server.on_event
async def handle_event(ctx: TaskContext, event: Event):
    try:
        if not isinstance(event.content, SDKTextPart):
            raise ValueError("Only text messages supported.")
        user_message = event.content.text
        logger.info("task_event task_id=%s chars=%s", ctx.task.id, len(user_message))

        state = await ctx.state.get()
        session_id = state.get("session_id") if state else None

        await _ensure_valid_github_token(ctx, workspace_dir=WORKSPACE_DIR)
        slack_bot_token = _task_param_str(ctx, "slack_bot_token") or _task_metadata_str(
            ctx, "slack_bot_token"
        )
        if slack_bot_token:
            os.environ["SLACK_BOT_TOKEN"] = slack_bot_token

        slack_channel, slack_thread_ts = _task_slack_thread_context(ctx)
        if slack_channel:
            os.environ["WOZ_SLACK_CHANNEL"] = slack_channel
        if slack_thread_ts:
            os.environ["WOZ_SLACK_THREAD_TS"] = slack_thread_ts
        user_message_for_model = _build_slack_mode_prompt(ctx, user_message)

        options = ClaudeAgentOptions(
            include_partial_messages=True,
            permission_mode="bypassPermissions",
            cwd=WORKSPACE_DIR,
            allowed_tools=[
                "Read",
                "Write",
                "Bash",
                "Edit",
                "Grep",
                "Glob",
                "Task",
                "Skill",
            ],
            resume=session_id,
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": SYSTEM_PROMPT,
            },
        )

        async for message in query(prompt=user_message_for_model, options=options):
            await ctx.messages.send(message)
            if isinstance(message, ResultMessage):
                await ctx.state.update({"session_id": message.session_id})

    except Exception as e:
        logger.exception("task_event_error task_id=%s", ctx.task.id)
        await ctx.messages.send(f"Error: {e}")


@server.on_cancel
async def handle_cancel(ctx: TaskContext):
    logger.info("task_cancelled task_id=%s", ctx.task.id)
