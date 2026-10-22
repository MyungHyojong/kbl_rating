"""Commit and push only the generated public ``docs/`` pages.

Run this from the local scheduler after a successful rating run.  It never
stages source code, raw community HTML, CSVs, or credentials.
"""
from __future__ import annotations

import argparse
import os
import subprocess
from pathlib import Path


BASE = Path(__file__).resolve().parent


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(["git", *args], cwd=BASE, text=True, capture_output=True)
    if check and result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RuntimeError(f"git {' '.join(args)} 실패 (exit {result.returncode}): {detail}")
    return result


def configure_actions_identity() -> None:
    """Set a local author only for GitHub-hosted automation commits."""
    if os.getenv("GITHUB_ACTIONS") != "true":
        return
    git("config", "user.name", "github-actions[bot]")
    git("config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com")


def main() -> None:
    parser = argparse.ArgumentParser(description="생성된 docs 팀 페이지 전용 GitHub 발행")
    parser.add_argument("--message", default="Publish KBL team rating pages")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    docs = BASE / "docs"
    if not (docs / "index.html").exists():
        raise FileNotFoundError("docs/index.html이 없습니다. 팀 페이지를 먼저 생성하세요.")
    changed = git("status", "--porcelain", "--", "docs").stdout.strip()
    if not changed:
        print("발행할 팀 페이지 변경이 없습니다.")
        return
    print(changed)
    if args.dry_run:
        print("검증만 완료했습니다. --dry-run이므로 GitHub에 푸시하지 않았습니다.")
        return
    configure_actions_identity()
    git("add", "--", "docs")
    git("commit", "-m", args.message)
    git("push", "origin", "HEAD")
    print("GitHub 발행 완료: docs/ 팀 페이지를 푸시했습니다.")


if __name__ == "__main__":
    main()
