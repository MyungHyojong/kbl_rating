"""One-command local KBL ratings pipeline.

It deliberately collects only DCInside list pages, with a randomized delay, and
stops at the first block/redirect instead of trying to bypass it.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

import kbl_rating_pipeline as kbl

BASE = Path(__file__).resolve().parent


def run(*parts: object) -> None:
    command = [sys.executable, *map(str, parts)]
    print("\n$", " ".join(command))
    subprocess.run(command, check=True)


def in_window(value: str, start: str, end: str) -> bool:
    value = value.strip()
    # DCInside list rows for today's posts normally use HH:MM.
    # End time is inclusive: a game ending at 16:30 includes a 16:30 post.
    return len(value) == 5 and value[2] == ":" and start <= value <= end


def filter_posts(source: Path, target: Path, start: str, end: str) -> int:
    with source.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f); fields = reader.fieldnames or []; rows = [r for r in reader if in_window(r.get("작성일", ""), start, end)]
    with target.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields); writer.writeheader(); writer.writerows(rows)
    return len(rows)


def game_context(game_code: str) -> tuple[list[str], list[str], list[dict[str, str]], dict[str, int]]:
    kbl.GAME_CODE = game_code
    records = kbl.fetch_box_score()
    teams = list(dict.fromkeys(str(r["팀"]) for r in records if r["팀"]))
    roster = [
        {"team": str(r["팀"]), "player": str(r["선수"])}
        for r in records if int(r["출전시간초"]) > 0
    ]
    players = [row["player"] for row in roster]
    if len(teams) != 2: raise RuntimeError(f"KBL 기록에서 두 팀을 판별하지 못했습니다: {teams}")
    if not roster: raise RuntimeError("KBL 기록에서 실제 출전 선수를 찾지 못했습니다.")
    scores = {team: round(sum(float(r["PTS"]) for r in records if str(r["팀"]) == team)) for team in teams}
    return teams, players, roster, scores


def main() -> None:
    parser = argparse.ArgumentParser(description="로컬 KBL 평점 전체 파이프라인")
    parser.add_argument("--game-code", required=True, help="KBL 경기코드")
    parser.add_argument("--date", default=date.today().strftime("%Y%m%d"))
    parser.add_argument("--games-today", type=int, default=1, help="1이면 30페이지, 2 이상이면 60페이지")
    parser.add_argument("--first-page", type=int, default=1)
    parser.add_argument("--last-page", type=int)
    parser.add_argument("--start-time", default="19:00")
    parser.add_argument("--end-time", default="21:30")
    parser.add_argument("--headless", action="store_true")
    parser.add_argument("--html-dir", type=Path, help="이미 수집한 목록 HTML 폴더를 재사용")
    parser.add_argument("--home-team", help="KBL 일정 API가 확인한 홈 팀명")
    parser.add_argument("--away-team", help="KBL 일정 API가 확인한 원정 팀명")
    parser.add_argument("--home-score", help="KBL 일정 API가 확인한 홈 팀 최종 점수")
    parser.add_argument("--away-score", help="KBL 일정 API가 확인한 원정 팀 최종 점수")
    parser.add_argument("--round", default="정규리그", help="표지와 멘트에 쓸 라운드 표기")
    parser.add_argument("--roster-json", default="", help="KBL API가 확인한 실제 출전 명단 JSON")
    parser.add_argument("--skip-gemini", action="store_true")
    parser.add_argument("--skip-png", action="store_true")
    args = parser.parse_args()
    if not os.environ.get("GEMINI_API_KEY") and not args.skip_gemini:
        raise RuntimeError("GEMINI_API_KEY를 설정한 뒤 실행하세요. Gemini를 생략하려면 --skip-gemini")
    last_page = args.last_page or (30 if args.games_today == 1 else 60)
    root = BASE / "runs" / args.date / args.game_code
    html_dir, output_dir = (args.html_dir.resolve() if args.html_dir else root / "html"), root / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    posts_all, posts_window = output_dir / "posts_all.csv", output_dir / f"posts_{args.start_time.replace(':','')}_{args.end_time.replace(':','')}.csv"
    teams, played, roster, scores = game_context(args.game_code)
    home_team, away_team = args.home_team or teams[0], args.away_team or teams[1]
    home_score = args.home_score or str(scores.get(home_team, "-"))
    away_score = args.away_score or str(scores.get(away_team, "-"))
    roster_json = args.roster_json or json.dumps(roster, ensure_ascii=False)
    print(f"경기: {away_team} vs {home_team} / 실제 출전 {len(played)}명 / 수집 {args.first_page}~{last_page}페이지")
    if args.html_dir:
        print(f"기존 HTML 재사용: {html_dir}")
    else:
        saver = [BASE / "dcinside_basketball_html_saver.py", "--first-page", args.first_page, "--last-page", last_page, "--date", args.date, "--output-dir", html_dir]
        if args.headless: saver.append("--headless")
        run(*saver)
    run(BASE / "dcinside_html_to_csv.py", "--input-dir", html_dir, "--output", posts_all, "--first-page", args.first_page, "--last-page", last_page)
    count = filter_posts(posts_all, posts_window, args.start_time, args.end_time)
    print(f"시간 필터 완료: {count}개 글 → {posts_window}")
    # Preserve each analysis window.  This also avoids overwriting a CSV that
    # may be open in Excel while a corrected time-window analysis is rerun.
    annotations = output_dir / f"posts_gemini_{args.start_time.replace(':', '')}_{args.end_time.replace(':', '')}.csv"
    if args.skip_gemini:
        raise RuntimeError("최종 평점에는 Gemini 평가가 필요합니다. --skip-gemini은 수집 점검용입니다.")
    run(BASE / "gemini_person_candidates.py", "--input", posts_window, "--output", annotations, "--checkpoint", output_dir / "gemini_checkpoint.json", "--home", home_team, "--away", away_team, "--played", "|".join(played), "--roster-json", roster_json, "--date", args.date, "--batch-size", 60)
    run(BASE / "kbl_rating_pipeline.py", "--game-code", args.game_code, "--date", args.date, "--annotations", annotations, "--output-dir", output_dir)
    ratings = output_dir / f"player_ratings_gmsc_{args.date}.csv"
    renderer = [BASE / "render_rating_outputs.py", "--ratings", ratings, "--output-dir", output_dir, "--date", args.date]
    if not args.skip_png: renderer.append("--png")
    run(*renderer)
    # ``docs/`` contains only the public team pages.  Raw posts, Gemini output,
    # API keys and per-run intermediate files remain local under ``runs/``.
    run(
        BASE / "team_pages_generator.py",
        "--ratings", ratings,
        "--date", args.date,
        "--game-code", args.game_code,
        "--home", home_team,
        "--away", away_team,
        "--home-score", home_score,
        "--away-score", away_score,
        "--round", args.round,
    )

    newsletter = [
        BASE / "newsletter_generator.py",
        "--ratings", ratings,
        "--date", args.date,
        "--round", args.round,
        "--home", home_team,
        "--away", away_team,
        "--home-score", home_score,
        "--away-score", away_score,
        "--output-dir", output_dir,
        "--square",
        "--caption",
    ]
    # Image generation is intentionally opt-in: it can require a Gemini image
    # model entitlement / paid quota.  A failure never discards the ratings;
    # the deterministic local newsletter remains the safe fallback.
    if os.environ.get("ENABLE_AI_POSTER", "").strip() == "1":
        base_image = output_dir / f"ai_poster_base_{args.date}_{args.away_team or away_team}_vs_{args.home_team or home_team}.png"
        try:
            run(
                BASE / "gemini_poster_generator.py",
                "--ratings", ratings,
                "--away", away_team,
                "--home", home_team,
                "--output", base_image,
            )
            newsletter.extend(["--ai-base-image", base_image])
        except subprocess.CalledProcessError as error:
            print(f"AI 포스터 생성 실패({error.returncode}). 일반 뉴스레터 PNG로 계속합니다.")
    run(*newsletter)
    print(f"\n완료: {output_dir}")


if __name__ == "__main__": main()
