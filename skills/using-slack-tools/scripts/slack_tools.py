#!/usr/bin/env python3
"""
Slack Tools - Send messages, upload files, and create canvases.

Usage:
    python slack_tools.py message --channel CHANNEL --text "Hello world"
    python slack_tools.py message --channel CHANNEL --text-file /tmp/message.txt
    python slack_tools.py upload --channel CHANNEL --file /path/to/file
    python slack_tools.py canvas --title "Title" --content "# Markdown content"
    python slack_tools.py channels  # List available channels
    python slack_tools.py download --url URL --name FILENAME  # Download a Slack-hosted file

Requires:
    - SLACK_BOT_TOKEN environment variable
    - pip install slack_sdk

Bot token scopes needed:
    - chat:write (send messages)
    - chat:write.public (post to public channels without joining)
    - files:write (upload files)
    - canvases:write (create/edit canvases)
    - channels:read (list channels)
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from typing import Any

UPLOADS_DIR_ENV = "WOZ_SLACK_UPLOADS_DIR"
MAX_DOWNLOAD_BYTES = 50 * 1024 * 1024  # 50MB


def _default_uploads_dir() -> str:
    configured = os.environ.get(UPLOADS_DIR_ENV, "").strip()
    skill_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if configured:
        expanded = os.path.expanduser(configured)
        if os.path.isabs(expanded):
            return os.path.abspath(expanded)
        return os.path.abspath(os.path.join(skill_dir, expanded))
    return os.path.join(skill_dir, "uploads")


def _require_slack_sdk() -> tuple[Any, Any]:
    """Import slack_sdk lazily so commands like `download` work without it."""
    try:
        from slack_sdk import WebClient
        from slack_sdk.errors import SlackApiError
    except ImportError:
        print(
            "Error: slack_sdk not installed. Run: pip install slack_sdk",
            file=sys.stderr,
        )
        sys.exit(1)
    return WebClient, SlackApiError


def get_client() -> Any:
    """Get authenticated Slack client."""
    WebClient, _ = _require_slack_sdk()
    token = os.environ.get("SLACK_BOT_TOKEN")
    if not token:
        print("Error: SLACK_BOT_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)
    return WebClient(token=token)


def format_response(data: dict) -> str:
    """Format response as JSON."""
    return json.dumps(data, indent=2)


# --- Messages ---


def send_message(
    channel: str,
    text: str,
    thread_ts: str = None,
    blocks: str = None,
    unfurl_links: bool = True,
) -> dict:
    """Send a message to a channel."""
    client = get_client()
    _, SlackApiError = _require_slack_sdk()

    kwargs = {
        "channel": channel,
        "text": text,
        "unfurl_links": unfurl_links,
    }

    if thread_ts:
        kwargs["thread_ts"] = thread_ts

    if blocks:
        try:
            kwargs["blocks"] = json.loads(blocks)
        except json.JSONDecodeError:
            print("Warning: Invalid blocks JSON, sending text only", file=sys.stderr)

    try:
        response = client.chat_postMessage(**kwargs)
        return {
            "success": True,
            "channel": response["channel"],
            "ts": response["ts"],
            "message": response["message"]["text"],
        }
    except SlackApiError as e:
        return {
            "success": False,
            "error": e.response["error"],
            "detail": str(e),
        }


def send_reply(
    channel: str, thread_ts: str, text: str, broadcast: bool = False
) -> dict:
    """Reply to a message thread."""
    client = get_client()
    _, SlackApiError = _require_slack_sdk()

    try:
        response = client.chat_postMessage(
            channel=channel,
            thread_ts=thread_ts,
            text=text,
            reply_broadcast=broadcast,
        )
        return {
            "success": True,
            "channel": response["channel"],
            "ts": response["ts"],
            "thread_ts": thread_ts,
        }
    except SlackApiError as e:
        return {
            "success": False,
            "error": e.response["error"],
        }


# --- Files ---


def upload_file(
    channel: str,
    file_path: str,
    title: str = None,
    initial_comment: str = None,
    thread_ts: str = None,
) -> dict:
    """Upload a file to a channel."""
    client = get_client()
    _, SlackApiError = _require_slack_sdk()

    if not os.path.exists(file_path):
        return {
            "success": False,
            "error": f"File not found: {file_path}",
        }

    kwargs = {
        "channel": channel,
        "file": file_path,
    }

    if title:
        kwargs["title"] = title
    if initial_comment:
        kwargs["initial_comment"] = initial_comment
    if thread_ts:
        kwargs["thread_ts"] = thread_ts

    try:
        # Use files_upload_v2 (the newer API)
        response = client.files_upload_v2(**kwargs)
        file_info = response.get("file", {})
        return {
            "success": True,
            "file_id": file_info.get("id"),
            "name": file_info.get("name"),
            "url": file_info.get("permalink"),
            "size": file_info.get("size"),
        }
    except SlackApiError as e:
        return {
            "success": False,
            "error": e.response["error"],
            "detail": str(e),
        }


def upload_content(
    channel: str, content: str, filename: str, filetype: str = None, title: str = None
) -> dict:
    """Upload text content as a file."""
    client = get_client()
    _, SlackApiError = _require_slack_sdk()

    kwargs = {
        "channel": channel,
        "content": content,
        "filename": filename,
    }

    if filetype:
        kwargs["filetype"] = filetype
    if title:
        kwargs["title"] = title

    try:
        response = client.files_upload_v2(**kwargs)
        file_info = response.get("file", {})
        return {
            "success": True,
            "file_id": file_info.get("id"),
            "name": file_info.get("name"),
            "url": file_info.get("permalink"),
        }
    except SlackApiError as e:
        return {
            "success": False,
            "error": e.response["error"],
        }


# --- Canvases ---


def create_canvas(
    title: str = None, markdown: str = None, channel_id: str = None
) -> dict:
    """Create a new standalone canvas."""
    client = get_client()
    _, SlackApiError = _require_slack_sdk()

    kwargs = {}

    if title:
        kwargs["title"] = title

    if markdown:
        kwargs["document_content"] = {
            "type": "markdown",
            "markdown": markdown,
        }

    try:
        response = client.api_call("canvases.create", json=kwargs)
        if response.get("ok"):
            return {
                "success": True,
                "canvas_id": response.get("canvas_id"),
            }
        else:
            return {
                "success": False,
                "error": response.get("error"),
            }
    except SlackApiError as e:
        return {
            "success": False,
            "error": e.response.get("error", str(e)),
        }


def create_channel_canvas(channel_id: str, markdown: str = None) -> dict:
    """Create a canvas attached to a channel."""
    client = get_client()
    _, SlackApiError = _require_slack_sdk()

    kwargs = {
        "channel_id": channel_id,
    }

    if markdown:
        kwargs["document_content"] = {
            "type": "markdown",
            "markdown": markdown,
        }

    try:
        response = client.api_call("conversations.canvases.create", json=kwargs)
        if response.get("ok"):
            return {
                "success": True,
                "canvas_id": response.get("canvas_id"),
            }
        else:
            return {
                "success": False,
                "error": response.get("error"),
            }
    except SlackApiError as e:
        return {
            "success": False,
            "error": e.response.get("error", str(e)),
        }


def edit_canvas(canvas_id: str, markdown: str, operation: str = "replace") -> dict:
    """Edit an existing canvas."""
    client = get_client()
    _, SlackApiError = _require_slack_sdk()

    # For replace operation, we replace all content
    changes = [
        {
            "operation": operation,
            "document_content": {
                "type": "markdown",
                "markdown": markdown,
            },
        }
    ]

    try:
        response = client.api_call(
            "canvases.edit",
            json={
                "canvas_id": canvas_id,
                "changes": changes,
            },
        )
        if response.get("ok"):
            return {
                "success": True,
                "canvas_id": canvas_id,
            }
        else:
            return {
                "success": False,
                "error": response.get("error"),
            }
    except SlackApiError as e:
        return {
            "success": False,
            "error": e.response.get("error", str(e)),
        }


# --- Channels ---


def list_channels(limit: int = 100, types: str = "public_channel") -> dict:
    """List available channels."""
    client = get_client()
    _, SlackApiError = _require_slack_sdk()

    try:
        response = client.conversations_list(
            limit=limit,
            types=types,
        )
        channels = []
        for ch in response.get("channels", []):
            channels.append(
                {
                    "id": ch.get("id"),
                    "name": ch.get("name"),
                    "is_private": ch.get("is_private", False),
                    "num_members": ch.get("num_members", 0),
                    "topic": ch.get("topic", {}).get("value", ""),
                }
            )
        return {
            "success": True,
            "count": len(channels),
            "channels": channels,
        }
    except SlackApiError as e:
        return {
            "success": False,
            "error": e.response["error"],
        }


def get_channel_id(channel_name: str) -> dict:
    """Get channel ID from channel name."""
    result = list_channels(limit=500)
    if not result["success"]:
        return result

    # Remove # prefix if present
    channel_name = channel_name.lstrip("#")

    for ch in result["channels"]:
        if ch["name"] == channel_name:
            return {
                "success": True,
                "channel_id": ch["id"],
                "channel_name": ch["name"],
            }

    return {
        "success": False,
        "error": f"Channel '{channel_name}' not found",
    }


# --- Downloads ---


def _dedup_path(dest_path: str) -> str:
    """Avoid overwriting existing files by appending a numeric suffix."""
    if not os.path.exists(dest_path):
        return dest_path
    base, ext = os.path.splitext(dest_path)
    idx = 1
    while True:
        candidate = f"{base}_{idx}{ext}"
        if not os.path.exists(candidate):
            return candidate
        idx += 1


def download_file(url: str, name: str, size: int | None = None) -> dict:
    """Download a Slack-hosted file into the sandbox filesystem."""
    token = os.environ.get("SLACK_BOT_TOKEN", "").strip()
    if not token:
        print("Error: SLACK_BOT_TOKEN environment variable not set", file=sys.stderr)
        return {
            "success": False,
            "error": "missing_slack_bot_token",
            "detail": "SLACK_BOT_TOKEN environment variable not set",
        }

    url = (url or "").strip()
    if not url:
        return {"success": False, "error": "missing_url"}

    filename = os.path.basename((name or "").strip())
    if not filename:
        return {"success": False, "error": "missing_name"}

    if size is not None and size > MAX_DOWNLOAD_BYTES:
        return {
            "success": True,
            "skipped": True,
            "reason": "size_limit_exceeded",
            "warning": f"File exceeds size limit ({MAX_DOWNLOAD_BYTES} bytes)",
            "name": filename,
            "size_bytes": size,
            "max_bytes": MAX_DOWNLOAD_BYTES,
        }

    uploads_dir = _default_uploads_dir()
    os.makedirs(uploads_dir, exist_ok=True)
    dest_path = _dedup_path(os.path.join(uploads_dir, filename))
    tmp_path = f"{dest_path}.part"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "User-Agent": "slack-tools/woz",
        },
        method="GET",
    )

    downloaded = 0
    try:
        with urllib.request.urlopen(req) as resp:
            status = getattr(resp, "status", None) or resp.getcode()
            if status != 200:
                return {"success": False, "error": "http_error", "status": status}

            content_length = resp.headers.get("Content-Length")
            if content_length:
                try:
                    content_length_int = int(content_length)
                except ValueError:
                    content_length_int = None
                if (
                    content_length_int is not None
                    and content_length_int > MAX_DOWNLOAD_BYTES
                ):
                    return {
                        "success": True,
                        "skipped": True,
                        "reason": "size_limit_exceeded",
                        "warning": f"File exceeds size limit ({MAX_DOWNLOAD_BYTES} bytes)",
                        "name": filename,
                        "size_bytes": content_length_int,
                        "max_bytes": MAX_DOWNLOAD_BYTES,
                    }

            with open(tmp_path, "wb") as f:
                while True:
                    chunk = resp.read(64 * 1024)
                    if not chunk:
                        break
                    downloaded += len(chunk)
                    if downloaded > MAX_DOWNLOAD_BYTES:
                        return {
                            "success": True,
                            "skipped": True,
                            "reason": "size_limit_exceeded",
                            "warning": f"File exceeded size limit ({MAX_DOWNLOAD_BYTES} bytes) during download",
                            "name": filename,
                            "size_bytes": downloaded,
                            "max_bytes": MAX_DOWNLOAD_BYTES,
                        }
                    f.write(chunk)

        os.replace(tmp_path, dest_path)
        return {
            "success": True,
            "name": os.path.basename(dest_path),
            "path": dest_path,
            "bytes": downloaded,
        }

    except urllib.error.HTTPError as e:
        return {
            "success": False,
            "error": "http_error",
            "status": getattr(e, "code", None),
            "detail": str(e),
        }
    except urllib.error.URLError as e:
        return {
            "success": False,
            "error": "url_error",
            "detail": str(getattr(e, "reason", e)),
        }
    except Exception as e:
        return {
            "success": False,
            "error": "download_failed",
            "detail": str(e),
        }
    finally:
        # Ensure we don't leave partial files around on failure/skip.
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except Exception:
            pass


# --- CLI ---


def _resolve_text_input(
    *,
    text: str | None,
    text_file: str | None,
    text_stdin: bool,
    flag_name: str,
) -> str:
    source_count = (
        (1 if text is not None else 0)
        + (1 if text_file else 0)
        + (1 if text_stdin else 0)
    )
    if source_count != 1:
        raise ValueError(
            f"Provide exactly one of --{flag_name}, --{flag_name}-file, or --{flag_name}-stdin."
        )
    if text is not None:
        return text
    if text_file:
        with open(text_file, "r", encoding="utf-8") as f:
            return f.read()
    return sys.stdin.read()


def _normalize_slack_text(text: str) -> str:
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    normalized = (
        normalized.replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\r", "\n")
        .replace("\\t", "\t")
    )
    # Slack uses *bold* instead of GitHub-style headings.
    normalized = re.sub(
        r"(?m)^[ \t]*#{1,6}[ \t]+(.+?)\s*$",
        lambda match: f"*{match.group(1).strip()}*",
        normalized,
    )
    # Slack uses single-asterisk bold markers.
    normalized = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"*\1*", normalized)
    return normalized


def main():
    parser = argparse.ArgumentParser(description="Slack Tools")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Message command
    msg_p = subparsers.add_parser("message", help="Send a message")
    msg_p.add_argument("--channel", "-c", required=True, help="Channel ID or name")
    msg_text_group = msg_p.add_mutually_exclusive_group(required=True)
    msg_text_group.add_argument("--text", "-t", help="Message text")
    msg_text_group.add_argument("--text-file", help="Read message text from file")
    msg_text_group.add_argument(
        "--text-stdin", action="store_true", help="Read message text from stdin"
    )
    msg_p.add_argument("--thread", help="Thread timestamp to reply to")
    msg_p.add_argument(
        "--literal-text",
        action="store_true",
        help="Disable text normalization for escaped newlines/Markdown.",
    )
    msg_p.add_argument("--blocks", help="Block Kit JSON")
    msg_p.add_argument(
        "--no-unfurl", action="store_true", help="Disable link unfurling"
    )

    # Reply command
    reply_p = subparsers.add_parser("reply", help="Reply to a thread")
    reply_p.add_argument("--channel", "-c", required=True, help="Channel ID")
    reply_p.add_argument("--thread", "-t", required=True, help="Thread timestamp")
    reply_text_group = reply_p.add_mutually_exclusive_group(required=True)
    reply_text_group.add_argument("--text", help="Reply text")
    reply_text_group.add_argument("--text-file", help="Read reply text from file")
    reply_text_group.add_argument(
        "--text-stdin", action="store_true", help="Read reply text from stdin"
    )
    reply_p.add_argument(
        "--literal-text",
        action="store_true",
        help="Disable text normalization for escaped newlines/Markdown.",
    )
    reply_p.add_argument(
        "--broadcast", action="store_true", help="Also post to channel"
    )

    # Upload command
    upload_p = subparsers.add_parser("upload", help="Upload a file")
    upload_p.add_argument("--channel", "-c", required=True, help="Channel ID")
    upload_p.add_argument("--file", "-f", required=True, help="File path")
    upload_p.add_argument("--title", help="File title")
    upload_p.add_argument("--comment", help="Initial comment")
    upload_p.add_argument("--thread", help="Thread timestamp")

    # Upload content command
    content_p = subparsers.add_parser("upload-content", help="Upload text as file")
    content_p.add_argument("--channel", "-c", required=True, help="Channel ID")
    content_p.add_argument("--content", required=True, help="Text content")
    content_p.add_argument("--filename", "-f", required=True, help="Filename")
    content_p.add_argument("--filetype", help="File type (e.g., python, markdown)")
    content_p.add_argument("--title", help="File title")

    # Canvas command
    canvas_p = subparsers.add_parser("canvas", help="Create a canvas")
    canvas_p.add_argument("--title", "-t", help="Canvas title")
    canvas_p.add_argument("--content", "-c", help="Markdown content")
    canvas_p.add_argument("--file", "-f", help="Read content from file")
    canvas_p.add_argument("--channel", help="Create as channel canvas (channel ID)")

    # Edit canvas command
    edit_p = subparsers.add_parser("edit-canvas", help="Edit a canvas")
    edit_p.add_argument("--canvas-id", "-i", required=True, help="Canvas ID")
    edit_p.add_argument("--content", "-c", help="New markdown content")
    edit_p.add_argument("--file", "-f", help="Read content from file")

    # Channels command
    ch_p = subparsers.add_parser("channels", help="List channels")
    ch_p.add_argument("--limit", "-n", type=int, default=100)
    ch_p.add_argument("--private", action="store_true", help="Include private channels")

    # Get channel ID command
    chid_p = subparsers.add_parser("channel-id", help="Get channel ID from name")
    chid_p.add_argument("--name", "-n", required=True, help="Channel name")

    # Download command
    dl_p = subparsers.add_parser("download", help="Download a Slack-hosted file")
    dl_p.add_argument(
        "--url", required=True, help="Slack private URL (e.g., url_private_download)"
    )
    dl_p.add_argument("--name", required=True, help="Destination filename")
    dl_p.add_argument(
        "--size",
        type=int,
        help="Optional file size in bytes (for early size-limit enforcement)",
    )

    args = parser.parse_args()

    if args.command == "message":
        try:
            message_text = _resolve_text_input(
                text=args.text,
                text_file=args.text_file,
                text_stdin=args.text_stdin,
                flag_name="text",
            )
        except (OSError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        if not args.literal_text:
            message_text = _normalize_slack_text(message_text)
        result = send_message(
            args.channel,
            message_text,
            thread_ts=args.thread,
            blocks=args.blocks,
            unfurl_links=not args.no_unfurl,
        )

    elif args.command == "reply":
        try:
            reply_text = _resolve_text_input(
                text=args.text,
                text_file=args.text_file,
                text_stdin=args.text_stdin,
                flag_name="text",
            )
        except (OSError, ValueError) as exc:
            print(f"Error: {exc}", file=sys.stderr)
            sys.exit(1)
        if not args.literal_text:
            reply_text = _normalize_slack_text(reply_text)
        result = send_reply(args.channel, args.thread, reply_text, args.broadcast)

    elif args.command == "upload":
        result = upload_file(
            args.channel,
            args.file,
            title=args.title,
            initial_comment=args.comment,
            thread_ts=args.thread,
        )

    elif args.command == "upload-content":
        result = upload_content(
            args.channel,
            args.content,
            args.filename,
            filetype=args.filetype,
            title=args.title,
        )

    elif args.command == "canvas":
        content = args.content
        if args.file:
            with open(args.file, "r") as f:
                content = f.read()

        if args.channel:
            result = create_channel_canvas(args.channel, markdown=content)
        else:
            result = create_canvas(title=args.title, markdown=content)

    elif args.command == "edit-canvas":
        content = args.content
        if args.file:
            with open(args.file, "r") as f:
                content = f.read()

        if not content:
            print("Error: --content or --file required", file=sys.stderr)
            sys.exit(1)

        result = edit_canvas(args.canvas_id, content)

    elif args.command == "channels":
        types = "public_channel,private_channel" if args.private else "public_channel"
        result = list_channels(args.limit, types)

    elif args.command == "channel-id":
        result = get_channel_id(args.name)

    elif args.command == "download":
        result = download_file(args.url, args.name, size=args.size)

    print(format_response(result))

    if not result.get("success"):
        sys.exit(1)


if __name__ == "__main__":
    main()
