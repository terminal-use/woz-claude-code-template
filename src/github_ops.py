"""GitHub-specific operations for the coding workspace agent."""

import os
import shutil
import subprocess

from terminaluse.lib import TaskContext, make_logger

from .helpers import _run, _task_param_str

logger = make_logger(__name__)

GITHUB_HOST = "github.com"


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GCM_INTERACTIVE"] = "Never"
    return env


def _clone_repo(
    repo_url: str,
    github_token: str | None,
    *,
    workspace_dir: str,
) -> subprocess.CompletedProcess[str]:
    """Clone repo into workspace_dir, embedding token if available."""
    clone_url = repo_url
    used_token_url = False
    if (
        github_token
        and repo_url.startswith("https://github.com/")
        and "@" not in repo_url.split("://", 1)[1]
    ):
        clone_url = repo_url.replace(
            "https://github.com/",
            f"https://x-access-token:{github_token}@github.com/",
            1,
        )
        used_token_url = True

    cmd = ["git"]
    if not github_token:
        cmd.extend(["-c", "credential.helper="])
    cmd.extend(["clone", "--depth", "1", clone_url, workspace_dir])

    result = _run(cmd, timeout=300, env=_git_env())

    if result.returncode == 0 and used_token_url:
        _run(["git", "remote", "set-url", "origin", repo_url], cwd=workspace_dir)

    return result


async def _bootstrap_github_auth(
    ctx: TaskContext,
    *,
    github_token: str | None,
    github_login: str | None,
    repo_owner: str | None,
    repo_name: str | None,
    workspace_dir: str,
) -> bool:
    """Attempt to set up gh CLI auth. Returns True on success."""
    if not github_token:
        logger.warning("no_github_token task_id=%s", ctx.task.id)
        return False

    os.environ["GH_TOKEN"] = github_token
    os.environ["GITHUB_TOKEN"] = github_token

    if shutil.which("gh") is None:
        logger.warning("gh_cli_missing task_id=%s", ctx.task.id)
        return False

    if _run(["gh", "auth", "status", "--hostname", GITHUB_HOST]).returncode != 0:
        login = _run(
            ["gh", "auth", "login", "--hostname", GITHUB_HOST, "--with-token"],
            input_text=github_token,
        )
        if login.returncode != 0:
            logger.warning("gh_auth_login_failed task_id=%s", ctx.task.id)
            return False

    if _run(["gh", "auth", "setup-git"]).returncode != 0:
        logger.warning("gh_setup_git_failed task_id=%s", ctx.task.id)
        return False

    if repo_owner and repo_name:
        check = _run(["gh", "repo", "view", f"{repo_owner}/{repo_name}", "--json", "nameWithOwner"])
        if check.returncode != 0:
            logger.warning(
                "gh_repo_access_failed task_id=%s repo=%s/%s",
                ctx.task.id,
                repo_owner,
                repo_name,
            )
            return False

    name = github_login or "TerminalUse Agent"
    email = (
        f"{github_login}@users.noreply.github.com"
        if github_login
        else "terminaluse-agent@users.noreply.github.com"
    )
    _run(["git", "config", "user.name", name], cwd=workspace_dir)
    _run(["git", "config", "user.email", email], cwd=workspace_dir)
    return True


async def _ensure_valid_github_token(
    ctx: TaskContext,
    *,
    workspace_dir: str,
) -> None:
    """Rehydrate GitHub env vars and re-bootstrap auth if stale or failed."""
    token = _task_param_str(ctx, "github_token")
    if not token:
        return

    os.environ["GH_TOKEN"] = token
    os.environ["GITHUB_TOKEN"] = token

    state = await ctx.state.get()
    auth_ok = state.get("github_auth_ok") if isinstance(state, dict) else False

    if auth_ok and shutil.which("gh"):
        check = _run(["gh", "auth", "status", "--hostname", GITHUB_HOST], timeout=30, env=_git_env())
        if check.returncode == 0:
            return

    logger.info("rebootstrap_github task_id=%s", ctx.task.id)
    ok = await _bootstrap_github_auth(
        ctx,
        github_token=token,
        github_login=_task_param_str(ctx, "github_login"),
        repo_owner=_task_param_str(ctx, "repo_owner"),
        repo_name=_task_param_str(ctx, "repo_name"),
        workspace_dir=workspace_dir,
    )
    await ctx.state.update({"github_auth_ok": ok})
