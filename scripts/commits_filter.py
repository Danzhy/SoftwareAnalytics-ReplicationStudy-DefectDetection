from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Set

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DEFAULT_INPUT = PROJECT_ROOT / "data" / "json-input-raw" / "bugfix_commits_all.json"
DEFAULT_LOG = PROJECT_ROOT / "logs" / "clone_log.csv"
DEFAULT_OUTPUT = PROJECT_ROOT / "logs" / "bugfix_commits_all_filtered.json"

KEEP_STATUSES = {"success", "skipped_existing"}


def load_successful_repos(log_path: Path) -> Set[str]:
    ok: Set[str] = set()
    with log_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if (row.get("status") or "").strip() in KEEP_STATUSES:
                name = (row.get("repo_name") or "").strip()
                if name:
                    ok.add(name)
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description="Filter bug-fix input JSON by clone-log success.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Original bug-fix JSON (read-only).")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG, help="Clone log CSV from repo_cloner.py.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Destination for the filtered JSON.")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if input_path == output_path:
        print(f"error: --input and --output resolve to the same file: {input_path}", file=sys.stderr)
        return 2

    if not args.input.exists():
        print(f"error: input JSON not found: {args.input}", file=sys.stderr)
        return 2
    if not args.log.exists():
        print(f"error: clone log not found: {args.log} (run repo_cloner.py first)", file=sys.stderr)
        return 2

    successful = load_successful_repos(args.log)

    with args.input.open("r", encoding="utf-8") as f:
        entries = json.load(f)

    total_entries = len(entries)
    total_repos = {e.get("repo_name") for e in entries if e.get("repo_name")}
    kept = [e for e in entries if e.get("repo_name") in successful]
    kept_repos = {e.get("repo_name") for e in kept if e.get("repo_name")}

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(kept, f, indent=2)

    print(
        f"kept {len(kept)} of {total_entries} entries "
        f"across {len(kept_repos)} of {len(total_repos)} repositories "
        f"-> {args.output}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
