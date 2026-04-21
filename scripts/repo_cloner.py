
from __future__ import annotations

import argparse
import csv
import json
import logging
import os
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from dotenv import load_dotenv
from tqdm import tqdm

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent

DEFAULT_INPUT = PROJECT_ROOT / "data" / "json-input-raw" / "bugfix_commits_all.json"
DEFAULT_CSV = PROJECT_ROOT / "analyzed_projects_all.csv"
DEFAULT_OUT = PROJECT_ROOT / "cloned"
DEFAULT_LOG = PROJECT_ROOT / "logs" / "clone_log.csv"
DEFAULT_ENV = PROJECT_ROOT / ".env"

CSV_FIELDS = ("repo_name", "status", "reason", "elapsed_s")


@dataclass
class CloneResult:
    repo_name: str
    status: str
    reason: str
    elapsed_s: float


def load_unique_repos(input_json: Path) -> List[str]:
    with input_json.open("r", encoding="utf-8") as f:
        data = json.load(f)
    repos: Set[str] = {entry["repo_name"] for entry in data if entry.get("repo_name")}
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
        )
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout}s"
    except FileNotFoundError:
        return 127, "git executable not found"

    stderr = (proc.stderr or "").strip().splitlines()
    first_err = stderr[0] if stderr else ""
    return proc.returncode, first_err


def rev_parse_head(repo_dir: Path) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_dir), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def clone_one(
    repo_name: str,
    expected_commit: Optional[str],
    out_root: Path,
    token: Optional[str],
    timeout: int,
) -> CloneResult:
    start = time.monotonic()
    try:
        owner, name = repo_name.split("/", 1)
    except ValueError:
        return CloneResult(repo_name, "clone_failed", f"malformed repo_name: {repo_name!r}", 0.0)

    dest = out_root / owner / name

    if dest.exists() and (dest / ".git").exists():
        if expected_commit:
            head = rev_parse_head(dest)
            if head and (head.lower().startswith(expected_commit.lower())
                         or expected_commit.lower().startswith(head.lower())):
                return CloneResult(repo_name, "skipped_existing", "already at expected commit", time.monotonic() - start)
            rc, err = run_git(["fetch", "--filter=blob:none", "origin", expected_commit], cwd=dest, timeout=timeout)
            if rc != 0:
                return CloneResult(repo_name, "checkout_failed", f"fetch: {err}", time.monotonic() - start)
            rc, err = run_git(["checkout", "--detach", expected_commit], cwd=dest, timeout=timeout)
            if rc != 0:
                return CloneResult(repo_name, "checkout_failed", f"checkout: {err}", time.monotonic() - start)
            return CloneResult(repo_name, "success", "re-checked out existing clone", time.monotonic() - start)
        return CloneResult(repo_name, "skipped_existing", "clone already present", time.monotonic() - start)

    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        return CloneResult(repo_name, "clone_failed", "destination exists but is not a git repo", time.monotonic() - start)

    auth = f"{token}@" if token else ""
    clone_url = f"https://{auth}github.com/{repo_name}.git"

    env = os.environ.copy()
    env.setdefault("GIT_TERMINAL_PROMPT", "0")
    env.setdefault("GIT_ASKPASS", "echo")

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
        redacted = err.replace(token, "***") if token and token in err else err
        return CloneResult(repo_name, "clone_failed", redacted or f"git clone exit {rc}", time.monotonic() - start)

    if not expected_commit:
        return CloneResult(repo_name, "clone_failed", "no last_checkout hash in analyzed_projects_all.csv", time.monotonic() - start)

    rc, err = run_git(
        ["fetch", "--filter=blob:none", "origin", expected_commit],
        cwd=dest,
        timeout=timeout,
        env=env,
    )
    if rc != 0:
        return CloneResult(repo_name, "checkout_failed", f"fetch: {err}", time.monotonic() - start)

    rc, err = run_git(
        ["checkout", "--detach", expected_commit],
        cwd=dest,
        timeout=timeout,
        env=env,
    )
    if rc != 0:
        return CloneResult(repo_name, "checkout_failed", f"checkout: {err}", time.monotonic() - start)

    return CloneResult(repo_name, "success", "", time.monotonic() - start)


def load_existing_log(log_path: Path) -> Set[str]:
    """Return repo_names already recorded with a terminal status in ``log_path``."""
    done: Set[str] = set()
    if not log_path.exists():
        return done
    with log_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name = (row.get("repo_name") or "").strip()
            if name:
                done.add(name)
    return done


def open_log(log_path: Path, resume: bool) -> Tuple["csv.DictWriter", "object"]:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    is_new = not log_path.exists() or not resume
    mode = "a" if (resume and log_path.exists()) else "w"
    f = log_path.open(mode, encoding="utf-8", newline="")
    writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
    if is_new:
        writer.writeheader()
        f.flush()
    return writer, f


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone and checkout repos referenced by a PySZZ bug-fix JSON.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT, help="Path to bug-fix input JSON.")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to analyzed_projects_all.csv (repo -> last_checkout).")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Destination root for cloned/<owner>/<repo>/.")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG, help="Output CSV log path.")
    parser.add_argument("--env", type=Path, default=DEFAULT_ENV, help="Path to .env with GITHUB_TOKEN.")
    parser.add_argument("--workers", type=int, default=8, help="Number of parallel clone workers.")
    parser.add_argument("--timeout", type=int, default=900, help="Per-git-command timeout in seconds.")
    parser.add_argument("--no-resume", action="store_true", help="Ignore existing log and re-process every repo.")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N repos (debug).")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    if args.env and args.env.exists():
        load_dotenv(args.env)
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logging.warning("GITHUB_TOKEN not set; falling back to anonymous clones (60 req/h limit).")

    if not args.input.exists():
        logging.error("Input JSON not found: %s", args.input)
        return 2
    if not args.csv.exists():
        logging.error("analyzed_projects_all.csv not found: %s", args.csv)
        return 2

    repos = load_unique_repos(args.input)
    checkout_map = load_checkout_map(args.csv)
    logging.info("Loaded %d unique repositories from %s", len(repos), args.input.name)
    logging.info("Loaded %d checkout hashes from %s", len(checkout_map), args.csv.name)

    resume = not args.no_resume
    already_done = load_existing_log(args.log) if resume else set()
    if already_done:
        logging.info("Resume: %d repos already recorded in %s, skipping.", len(already_done), args.log)

    pending = [r for r in repos if r not in already_done]
    if args.limit > 0:
        pending = pending[: args.limit]

    if not pending:
        logging.info("Nothing to do.")
        return 0

    writer, log_file = open_log(args.log, resume=resume)
    write_lock = threading.Lock()

    counts = {"success": 0, "clone_failed": 0, "checkout_failed": 0, "skipped_existing": 0}

    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures = {
                pool.submit(
                    clone_one,
                    repo,
                    checkout_map.get(repo),
                    args.out,
                    token,
                    args.timeout,
                ): repo
                for repo in pending
            }

            with tqdm(total=len(futures), desc="cloning", unit="repo") as bar:
                for fut in as_completed(futures):
                    repo = futures[fut]
                    try:
                        result = fut.result()
                    except Exception as exc:
                        result = CloneResult(repo, "clone_failed", f"exception: {exc}", 0.0)
                    counts[result.status] = counts.get(result.status, 0) + 1
                    with write_lock:
                        writer.writerow(
                            {
                                "repo_name": result.repo_name,
                                "status": result.status,
                                "reason": result.reason,
                                "elapsed_s": f"{result.elapsed_s:.2f}",
                            }
                        )
                        log_file.flush()
                    bar.set_postfix(
                        ok=counts["success"],
                        skip=counts["skipped_existing"],
                        clone_err=counts["clone_failed"],
                        co_err=counts["checkout_failed"],
                    )
                    bar.update(1)
    finally:
        log_file.close()

    logging.info(
        "Done. success=%d skipped=%d clone_failed=%d checkout_failed=%d (log: %s)",
        counts["success"],
        counts["skipped_existing"],
        counts["clone_failed"],
        counts["checkout_failed"],
        args.log,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
