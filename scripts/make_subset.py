from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any, Dict, List

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DEFAULT_INPUT = PROJECT_ROOT / "logs" / "bugfix_commits_all_filtered.json"
DEFAULT_OUTPUT = PROJECT_ROOT / "logs" / "bugfix_commits_subset.json"
DEFAULT_SIZE = 10
DEFAULT_SEED = 42


def sample_entries(entries: List[Dict[str, Any]], size: int, seed: int) -> List[Dict[str, Any]]:
    """Return a random subset of ``entries`` of length ``size``.

    Entries are first sorted by ``(repo_name, fix_commit_hash)`` so that the
    sample depends only on the contents of the input JSON, not on the
    order in which entries happen to be stored on disk.
    """
    ordered = sorted(
        entries,
        key=lambda e: (e.get("repo_name") or "", e.get("fix_commit_hash") or ""),
    )
    rng = random.Random(seed)
    return rng.sample(ordered, size)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create a reproducible random subset of a PySZZ bug-fix JSON.",
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT,
                        help="Filtered bug-fix JSON to sample from.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT,
                        help="Destination for the subset JSON.")
    parser.add_argument("--size", type=int, default=DEFAULT_SIZE,
                        help="Number of bug-fix entries to sample.")
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED,
                        help="Seed for random sampling (fixed -> reproducible).")
    args = parser.parse_args()

    input_path = args.input.resolve()
    output_path = args.output.resolve()
    if input_path == output_path:
        print(f"error: --input and --output resolve to the same file: {input_path}", file=sys.stderr)
        return 2
    if not args.input.exists():
        print(f"error: input JSON not found: {args.input}", file=sys.stderr)
        return 2
    if args.size <= 0:
        print(f"error: --size must be positive, got {args.size}", file=sys.stderr)
        return 2

    with args.input.open("r", encoding="utf-8") as f:
        entries = json.load(f)

    if not isinstance(entries, list):
        print(f"error: input JSON must be a list, got {type(entries).__name__}", file=sys.stderr)
        return 2
    if len(entries) < args.size:
        print(
            f"error: requested subset size {args.size} exceeds available entries {len(entries)}",
            file=sys.stderr,
        )
        return 2

    subset = sample_entries(entries, args.size, args.seed)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8") as f:
        json.dump(subset, f, indent=2)

    print(
        f"sampled {len(subset)} of {len(entries)} entries "
        f"(seed={args.seed}) -> {args.output}"
    )
    print("subset:")
    for e in subset:
        print(f"  {e.get('repo_name')}  {e.get('fix_commit_hash')}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
