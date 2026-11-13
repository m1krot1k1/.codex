---
name: codex-tempo-start
description: Introduces Codex Tempo after installation and explains its workflow guidance and optional quota reminder.
---

# Getting started with Codex Tempo

Codex Tempo is a set of workflow instructions for Codex. It helps choose a suitable level of effort, delegate only when useful, and verify changes. It does not enforce account limits or guarantee lower usage.

## First use

1. Read the installed `AGENTS.md` and this skill.
2. For development work, use the smallest workflow that can produce a verified result.
3. Before costly phases, refresh the official usage meter when available and consider both short and weekly windows.
4. The optional local SessionStart hook only displays a recent sanitized snapshot. Inspect and trust it in Codex Settings → Hooks before use.

## Manage the installation

- Install/update: run `./install.sh` from the source repository.
- Check updates: run `./install.sh --check-updates`.
- Remove managed files: run `python3 scripts/uninstall.py` from the source repository; review the preview and confirm.

The public catalog package contains skills only. The local Desktop package may also include a SessionStart hook.
