---
name: codex-app-server
description: Use when building software that must create, resume, stream, or control Codex conversations programmatically. For normal development chats, use native Codex threads and codex resume instead.
---

# Official Codex app-server integration

Use the official Codex app-server or SDK only when an application actually needs a programmatic Codex lifecycle. For ordinary repository work, stay in the current Codex chat and use `codex resume` in CLI workflows.

- Read the current official app-server/SDK docs before implementation; protocols and SDKs evolve.
- Keep Codex-managed model access and app-server thread state in their supported surfaces. Do not extract or inspect OAuth credentials.
- Add a budget gate in the calling application before starting a thread or turn. The app-server does not expose a universal Plus remaining-usage guarantee and does not protect the account from usage in other chats or devices.
- Stream progress and support cancellation; persist only the minimum resume identifiers and application-owned task state. Never store secrets in task journals.
- Honor Codex approval and sandbox decisions. Do not create an unattended process that bypasses approvals or launches hidden background work.
- Use a fresh short-lived quota reading when available. Unknown quota means Luna/Medium, one request at a time, no optional parallel agents, and Fast off.

Primary reference: https://developers.openai.com/blog/codex-as-a-platform
