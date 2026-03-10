---
name: using-slack-tools
description: Use this skill to send Slack messages/replies, upload or download files, and create or edit canvases with scripts/slack_tools.py.
---

# Using Slack Tools

Use `python ./scripts/slack_tools.py` to send messages, work in threads, upload/download files, and manage canvases.

## Commands

| Command | Description |
|---------|-------------|
| `message -c CHANNEL (--text-file FILE | --text TEXT | --text-stdin) [--literal-text]` | Send message |
| `reply -c CHANNEL -t THREAD (--text-file FILE | --text TEXT | --text-stdin) [--literal-text]` | Reply in thread |
| `upload -c CHANNEL -f FILE` | Upload file |
| `upload-content -c CHANNEL --content TEXT -f NAME` | Upload text as file |
| `download --url URL --name FILENAME [--size BYTES]` | Download Slack file to `./uploads/` (or `$WOZ_SLACK_UPLOADS_DIR`) |
| `canvas --title TITLE --content MD` | Create standalone canvas |
| `canvas --channel ID --content MD` | Create channel canvas |
| `edit-canvas -i ID --content MD` | Edit canvas |
| `channels` | List channels |
| `channel-id -n NAME` | Resolve channel ID by name |

## Send Messages

Default to `--text-file` for anything beyond a short plain-text one-liner.

Warning: do not use `--text` with backticks (`` ` ``) or `$vars`; your shell may execute/expand them before the script receives text.

Use `--text` only for short plain text without special characters. Use `--text-file` for backticks, bullets, formatting, or newlines.
Slack formatting uses `mrkdwn` (for example, `*bold*`), not standard Markdown.

```bash
# Recommended pattern
cat <<'EOF' > /tmp/slack_reply.txt
*Available Coding Agents*
- `main`
- `codex`
EOF
python ./scripts/slack_tools.py reply -c C123456 -t 1234567890.123456 --text-file /tmp/slack_reply.txt

# Safe one-liner only
python ./scripts/slack_tools.py message -c C123456 --text "Build completed successfully"
```

If you need exact input preservation, pass `--literal-text`.

## Upload and Download

```bash
# Upload a local file
python ./scripts/slack_tools.py upload -c C123456 -f ./report.pdf --title "Weekly Report"

# Upload text directly as a file
python ./scripts/slack_tools.py upload-content -c C123456 --content "print('hello')" -f script.py --filetype python

# Download a Slack-hosted file
python ./scripts/slack_tools.py download --url "https://files.slack.com/..." --name "config.yaml"
```

Downloaded files are written to `./uploads/` relative to this skill directory unless `$WOZ_SLACK_UPLOADS_DIR` is set.

## Canvases

```bash
# Create standalone canvas
python ./scripts/slack_tools.py canvas --title "Project Plan" --content "# Goals\n\n- Item 1\n- Item 2"

# Create channel canvas
python ./scripts/slack_tools.py canvas --channel C123456 --content "# Channel Guidelines\n\nRules here..."

# Edit existing canvas
python ./scripts/slack_tools.py edit-canvas -i F123456 --content "# Updated Content"
```

## API Reference

See [references/api_reference.md](references/api_reference.md) for methods, scopes, and rate limits.
