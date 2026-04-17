"""PreToolUse hook: protect real participant data from accidental edits.

Blocks Edit/Write operations on:
- Files in any `/data/raw/` directory (real participant recordings)
- Existing `.rrational` files in `/data/processed/` (app-generated)

Allows:
- Files in `/data/demo/` (demo data, safe to modify for testing)
- New `.rrational` files (Claude may need to create test fixtures)
- All source code, docs, tests, configs
"""

import json
import os
import sys


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0

    file_path = data.get("tool_input", {}).get("file_path", "") or data.get(
        "tool_response", {}
    ).get("filePath", "")
    if not file_path:
        return 0

    normalized = file_path.replace("\\", "/")

    if "/data/raw/" in normalized:
        sys.stderr.write(
            f"BLOCKED: {file_path} is in /data/raw/ — real participant data.\n"
            "Raw recordings must never be modified. If you need to test something, "
            "use data/demo/ instead.\n"
        )
        return 2

    if normalized.endswith(".rrational") and "/data/processed/" in normalized:
        if os.path.exists(file_path):
            sys.stderr.write(
                f"BLOCKED: {file_path} is an app-generated .rrational file.\n"
                "These files are managed by RRational itself via 'Export for Analysis'. "
                "Manual edits would corrupt the audit trail.\n"
            )
            return 2

    return 0


if __name__ == "__main__":
    sys.exit(main())
