#!/usr/bin/env python3
"""Build a skills-only Codex Tempo catalog ZIP (lifecycle hooks are excluded)."""
from __future__ import annotations

import argparse
import json
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist/codex-tempo-1.0.0.zip"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "plugins" / "codex-tempo"
    manifest_path = root / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("interface", {}).get("composerIcon") != "./assets/icon.svg":
        parser.error("Codex listing manifest is missing its required composer icon")
    if not (root / "assets/icon.svg").is_file():
        parser.error("listing logo and composer icon must be present")
    output = args.output if args.output.is_absolute() else Path.cwd() / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    files = [manifest_path, root / "assets/icon.svg"]
    files.extend(sorted((root / "skills").rglob("*")))
    files = [p for p in files if p.is_file()]
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(root))
    with zipfile.ZipFile(output) as archive:
        names = archive.namelist()
        if any("hook" in name.lower() for name in names):
            output.unlink(missing_ok=True)
            parser.error("catalog package must not contain lifecycle hooks")
        if ".codex-plugin/plugin.json" not in names:
            parser.error("catalog package has no plugin manifest")
    print(f"Created skills-only catalog package: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
