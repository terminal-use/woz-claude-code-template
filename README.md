# Claude Agent SDK Template

This repository is a Claude Agent SDK template.

## Slack Reply Contract

- This template includes `skills/using-slack-tools`.
- For Slack-origin tasks (thread context present), the agent is instructed to post at least one user-visible thread reply with a short summary before ending the turn.

## Claude Agent SDK-specific Agent

- [Python SDK][python-sdk]: This is a must read for any changes / creating a new claude agent sdk agent
- [User Approvals and Inputs][user-input]
- [Hooks - Intercept and Control Agent Behavior][hooks]
- [Modifying System Prompts][modifying-system-prompts]
- [MCP - Connect to External Tools][mcp]
- [Custom Tools][custom-tools]
- [Subagents][subagents]
- [Agent Skills][skills]
- [Plugins][plugins]

[python-sdk]: https://platform.claude.com/docs/en/agent-sdk/python
[user-input]: https://platform.claude.com/docs/en/agent-sdk/user-input
[hooks]: https://platform.claude.com/docs/en/agent-sdk/hooks
[modifying-system-prompts]: https://platform.claude.com/docs/en/agent-sdk/modifying-system-prompts
[mcp]: https://platform.claude.com/docs/en/agent-sdk/mcp
[custom-tools]: https://platform.claude.com/docs/en/agent-sdk/custom-tools
[subagents]: https://platform.claude.com/docs/en/agent-sdk/subagents
[skills]: https://platform.claude.com/docs/en/agent-sdk/skills
[plugins]: https://platform.claude.com/docs/en/agent-sdk/plugins
