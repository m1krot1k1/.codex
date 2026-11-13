#!/usr/bin/env python3
"""Build a skills-only Codex Tempo catalog ZIP (lifecycle hooks are excluded)."""
from __future__ import annotations

import argparse
import json
import struct
import zipfile
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("dist/codex-tempo-1.0.1.zip"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1] / "plugins" / "codex-tempo"
    manifest_path = root / ".codex-plugin" / "plugin.json"
    manifest = json.loads(manifest_path.read_text())
    interface = manifest.get("interface", {})
    if interface.get("logo") != "./assets/icon.png" or interface.get("composerIcon") != "./assets/icon.png":
        parser.error("listing logo and composer icon must reference assets/icon.png")
    icon_path = root / "assets" / "icon.png"
    if not icon_path.is_file():
        parser.error("listing logo and composer icon must be present")
    png_header = icon_path.read_bytes()[:24]
    if len(png_header) != 24 or png_header[:8] != b"\x89PNG\r\n\x1a\n":
        parser.error("listing icon must be a valid PNG")
    width, height = struct.unpack(">II", png_header[16:24])
    if width != height or width < 256:
        parser.error("listing icon must be square and at least 256 by 256 pixels")
    output = args.output if args.output.is_absolute() else Path.cwd() / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    files = [manifest_path, icon_path]
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
