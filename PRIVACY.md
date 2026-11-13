# Codex Tempo Privacy Notice

Last updated: 2026-11-13

## Scope

This notice covers the public Codex Tempo plugin package. It contains workflow
instructions for Codex and has no MCP servers, external accounts, analytics,
or telemetry. The package does not independently send information to the
publisher or another service.

When Codex uses the plugin's instructions, prompts and any workspace context
the user chooses to provide are handled by the Codex service under the user's
OpenAI account, settings, and applicable OpenAI privacy terms. Codex Tempo's
publisher does not receive those conversations through this plugin.

## Optional local toolkit

The public plugin package does not install the repository's separate local
toolkit. If a user installs that toolkit, its optional quota snapshot can store
the short-window and weekly usage percentages, their reset timestamps, the
snapshot time, and whether a saved reset is available in a local file under
the user's Codex home directory. It does not store account IDs, credentials,
or secrets. The optional SessionStart hook reads that local snapshot and prints
a reminder; it does not send it to the publisher. The user can remove the file
at any time or use the repository's uninstall instructions.

## Contact

For privacy questions, open an issue in the public repository:
<https://github.com/m1krot1k1/codex-tempo/issues>.
