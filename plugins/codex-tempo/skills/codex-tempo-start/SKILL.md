---
name: codex-tempo-start
description: Introduces Codex Tempo after installation and explains its workflow guidance and optional quota reminder.
---

# Getting started with Codex Tempo

Codex Tempo provides workflow guidance for Codex. Its `codex-tempo` skill contains the complete task-routing, quota-awareness, delegation, and verification workflow. The plugin does not enforce account limits or guarantee lower usage.

## First use

1. Read the `codex-tempo` skill for the complete workflow. Follow any `AGENTS.md` in the user's project as well.
2. Use the smallest workflow that can produce a verified result; delegate only when it materially improves speed or quality.
3. Before costly phases, refresh the official usage meter when available and consider both short and weekly windows.
4. The separate repository installer can add optional roles, scripts, and a local SessionStart reminder: https://github.com/m1krot1k1/codex-tempo. The hook only displays a recent sanitized snapshot. Inspect and trust it in Codex Settings → Hooks before use.

## Manage the installation

- For the extended local toolkit, clone the repository and run `./install.sh` from its directory.
- Check source updates with `./install.sh --check-updates`; update a clean checkout with `./install.sh --update`.
- Remove repository-managed files with `./install.sh --uninstall`; review its preview and confirm.

The public catalog package contains skills only. The local Desktop package may also include a SessionStart hook.
