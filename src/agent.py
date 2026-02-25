"""Coding Workspace Agent.

Clones a GitHub repo on task creation, configures GitHub auth, and proxies
messages to the Claude Agent SDK.
"""

import logging
import subprocess
from typing import Any

from claude_agent_sdk import ClaudeAgentOptions, query
from claude_agent_sdk.types import ResultMessage

from .github_ops import _bootstrap_github_auth, _clone_repo, _ensure_valid_github_token
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

SYSTEM_PROMPT = """After you finish a task, create a commit, push to GitHub, and draft a PR."""

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

        options = ClaudeAgentOptions(
            include_partial_messages=True,
            permission_mode="bypassPermissions",
            cwd=WORKSPACE_DIR,
            allowed_tools=["Read", "Write", "Bash", "Edit", "Grep", "Glob", "Task"],
            resume=session_id,
            system_prompt={
                "type": "preset",
                "preset": "claude_code",
                "append": SYSTEM_PROMPT,
            },
        )

        async for message in query(prompt=user_message, options=options):
            await ctx.messages.send(message)
            if isinstance(message, ResultMessage):
                await ctx.state.update({"session_id": message.session_id})

    except Exception as e:
        logger.exception("task_event_error task_id=%s", ctx.task.id)
        await ctx.messages.send(f"Error: {e}")


@server.on_cancel
async def handle_cancel(ctx: TaskContext):
    logger.info("task_cancelled task_id=%s", ctx.task.id)
