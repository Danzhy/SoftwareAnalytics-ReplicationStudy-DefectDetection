from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DEFAULT_SUBSET = PROJECT_ROOT / "logs" / "bugfix_commits_subset.json"
DEFAULT_CSV = PROJECT_ROOT / "analyzed_projects_all.csv"
DEFAULT_CLONED = PROJECT_ROOT / "cloned"
DEFAULT_ENV = PROJECT_ROOT / ".env"
DEFAULT_LOG = PROJECT_ROOT / "logs" / "subset_clone_log.csv"
DEFAULT_BRANCH = "pyszz-work"
DEFAULT_TIMEOUT = 900

CSV_FIELDS = ("repo_name", "status", "reason", "elapsed_s")


@dataclass
class CloneResult:
    repo_name: str
    status: str
    reason: str
    elapsed_s: float


def load_subset_repos(subset_path: Path) -> List[str]:
    with subset_path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, list):
        raise ValueError(f"subset JSON must be a list, got {type(data).__name__}")
    repos: Set[str] = {e["repo_name"] for e in data if e.get("repo_name")}
    return sorted(repos)


def load_checkout_map(csv_path: Path) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("repo_name") or "").strip()
            commit = (row.get("last_checkout") or "").strip()
            if name and commit:
                mapping[name] = commit
    return mapping


def run_git(
    args: List[str],
    cwd: Optional[Path] = None,
    timeout: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
) -> Tuple[int, str]:
    """Run a git command and return ``(returncode, stderr_first_line)``."""
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
            env=env,
            stdin=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    except FileNotFoundError:
        return 127, "git executable not found"

    stderr = (proc.stderr or "").strip().splitlines()
    first_err = stderr[0] if stderr else ""
    return proc.returncode, first_err


def _redact(message: str, token: Optional[str]) -> str:
    if token and token in message:
        return message.replace(token, "***")
    return message


def clone_one(
    repo_name: str,
    expected_commit: Optional[str],
    out_root: Path,
    branch: str,
    token: Optional[str],
    timeout: int,
) -> CloneResult:
    start = time.monotonic()

    if not expected_commit:
        return CloneResult(repo_name, "no_last_checkout",
                           "repo missing from analyzed_projects_all.csv", 0.0)

    try:
        owner, name = repo_name.split("/", 1)
    except ValueError:
        return CloneResult(repo_name, "clone_failed",
                           f"malformed repo_name: {repo_name!r}", 0.0)

    dest = out_root / owner / name

    if dest.exists():
        try:
            shutil.rmtree(dest)
        except OSError as exc:
            return CloneResult(repo_name, "clone_failed",
                               f"failed to remove existing dir: {exc}",
                               time.monotonic() - start)

    dest.parent.mkdir(parents=True, exist_ok=True)

    auth = f"{token}@" if token else ""
    clone_url = f"https://{auth}github.com/{repo_name}.git"

    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    env["GIT_ASKPASS"] = "echo"

    rc, err = run_git(
        [
            "clone",
            "--filter=blob:none",
            "--no-checkout",
            "--quiet",
            clone_url,
            str(dest),
        ],
        timeout=timeout,
        env=env,
    )
    if rc != 0:
        return CloneResult(repo_name, "clone_failed",
                           _redact(err, token) or f"git clone exit {rc}",
                           time.monotonic() - start)

    rc, err = run_git(
        ["fetch", "--filter=blob:none", "origin", expected_commit],
        cwd=dest,
        timeout=timeout,
        env=env,
    )
    if rc != 0:
        return CloneResult(repo_name, "fetch_failed",
                           _redact(err, token) or f"git fetch exit {rc}",
                           time.monotonic() - start)

    rc, err = run_git(
        ["checkout", "-B", branch, expected_commit],
        cwd=dest,
        timeout=timeout,
        env=env,
    )
    if rc != 0:
        return CloneResult(repo_name, "checkout_failed",
                           _redact(err, token) or f"git checkout exit {rc}",
                           time.monotonic() - start)

    return CloneResult(repo_name, "success", "", time.monotonic() - start)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fresh-clone the repos referenced by a PySZZ subset JSON "
                    "with HEAD attached to a local branch.",
    )
    parser.add_argument("--subset", type=Path, default=DEFAULT_SUBSET,
                        help="Subset bug-fix JSON (output of make_subset.py).")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV,
                        help="analyzed_projects_all.csv (repo_name -> last_checkout).")
    parser.add_argument("--cloned", type=Path, default=DEFAULT_CLONED,
                        help="Destination root for cloned/<owner>/<repo>/.")
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV,
                        help="Path to .env with GITHUB_TOKEN.")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG,
                        help="Destination CSV log.")
    parser.add_argument("--branch", type=str, default=DEFAULT_BRANCH,
                        help="Branch name to attach HEAD to after checkout.")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT,
                        help="Per-git-command timeout in seconds.")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if not args.subset.exists():
        logging.error("subset JSON not found: %s", args.subset)
        return 2
    if not args.csv.exists():
        logging.error("analyzed_projects_all.csv not found: %s", args.csv)
        return 2

    if args.env and args.env.exists():
        load_dotenv(args.env)
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logging.warning("GITHUB_TOKEN not set; falling back to anonymous clones.")

    try:
        repos = load_subset_repos(args.subset)
    except (ValueError, json.JSONDecodeError) as exc:
        logging.error("failed to parse subset JSON: %s", exc)
        return 2

    if not repos:
        logging.error("subset JSON references no repositories.")
        return 2

    checkout_map = load_checkout_map(args.csv)
    logging.info("Processing %d unique repositories from %s", len(repos), args.subset.name)

    args.log.parent.mkdir(parents=True, exist_ok=True)
    counts = {
        "success": 0,
        "no_last_checkout": 0,
        "clone_failed": 0,
        "fetch_failed": 0,
        "checkout_failed": 0,
    }

    with args.log.open("w", encoding="utf-8", newline="") as log_file:
        writer = csv.DictWriter(log_file, fieldnames=CSV_FIELDS)
        writer.writeheader()
        log_file.flush()

        for idx, repo in enumerate(repos, start=1):
            logging.info("[%d/%d] %s", idx, len(repos), repo)
            result = clone_one(
                repo_name=repo,
                expected_commit=checkout_map.get(repo),
                out_root=args.cloned,
                branch=args.branch,
                token=token,
                timeout=args.timeout,
            )
            counts[result.status] = counts.get(result.status, 0) + 1
            writer.writerow(
                {
                    "repo_name": result.repo_name,
                    "status": result.status,
                    "reason": result.reason,
                    "elapsed_s": f"{result.elapsed_s:.2f}",
                }
            )
            log_file.flush()

            if result.status == "success":
                logging.info("    ok (%.1fs)", result.elapsed_s)
            else:
                logging.error("    %s: %s", result.status, result.reason)

    logging.info(
        "Done. success=%d no_last_checkout=%d clone_failed=%d fetch_failed=%d checkout_failed=%d (log: %s)",
        counts["success"],
        counts["no_last_checkout"],
        counts["clone_failed"],
        counts["fetch_failed"],
        counts["checkout_failed"],
        args.log,
    )

    non_success = sum(v for k, v in counts.items() if k != "success")
    return 3 if non_success > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
