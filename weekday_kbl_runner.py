"""Weekday entry point for KBL regular-season player-rating runs.

The official KBL API is the source of truth. We resolve regular-season fixtures
and confirm box-score participants before making any DCInside request.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import kbl_rating_pipeline as kbl


BASE = Path(__file__).resolve().parent
KBL_HEADERS = {
    "Channel": "WEB",
    "TeamCode": "DefaultTeam",
    "X-Requested-With": "XMLHttpRequest",
    "lang": "ko",
}


def regular_round_label(game_no: object) -> str:
    """A 10-team KBL regular-season round contains 45 games."""
    try:
        return f"{math.ceil(int(game_no) / 45)}R"
    except (TypeError, ValueError):
        return "정규리그"


def fetch_regular_season_games(game_date: str) -> list[dict[str, str]]:
    """Return only domestic KBL regular-season fixtures for one date."""
    query = urlencode({"fromDate": game_date, "toDate": game_date})
    request = Request(f"https://api.kbl.or.kr/match/list?{query}", headers=KBL_HEADERS)
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("KBL 일정 API가 경기 배열을 반환하지 않았습니다.")

    games: list[dict[str, str]] = []
    for item in payload:
        if not isinstance(item, dict) or str(item.get("seasonCategory", "")) != "R":
            continue  # EASL 등 정규리그 이외 대회는 이 자동화에서 제외한다.
        code, home, away = (str(item.get(key, "")).strip() for key in ("gmkey", "tnameH", "tnameA"))
        if code and home and away:
            games.append({
                "code": code,
                "home": home,
                "away": away,
                "home_score": str(item.get("scoreH", "")),
                "away_score": str(item.get("scoreA", "")),
                "start": str(item.get("gameStart", "")),
                "round": regular_round_label(item.get("gameNo")),
            })
    return games


def confirm_participants(game_code: str) -> list[dict[str, str]]:
    """Confirm actual participants from KBL's final player-stat response."""
    kbl.GAME_CODE = game_code
    rows = kbl.fetch_box_score()
    teams = {str(row["팀"]) for row in rows if row["팀"]}
    roster = [
        {"team": str(row["팀"]), "player": str(row["선수"])}
        for row in rows
        if int(row["출전시간초"]) > 0
    ]
    if len(teams) != 2 or not roster:
        raise RuntimeError(f"{game_code}: KBL 공식 기록에서 실제 출전 명단을 확인하지 못했습니다.")
    return roster


def run(*args: object) -> None:
    command = [sys.executable, *map(str, args)]
    print("$", " ".join(command), flush=True)
    subprocess.run(command, check=True)


def community_time_window(game_date: str, game_start: str) -> tuple[str, str]:
    """Use actual weekend tip-off through tip-off + 2h30m, inclusive.

    Weekday games retain the established 19:00–21:30 community window.
    """
    target = datetime.strptime(game_date, "%Y%m%d").date()
    if target.weekday() < 5:
        return "19:00", "21:30"
    if len(game_start) != 4 or not game_start.isdigit():
        raise ValueError(f"주말 경기 시작 시각을 KBL API에서 읽지 못했습니다: {game_start!r}")
    start = datetime.strptime(game_date + game_start, "%Y%m%d%H%M")
    end = start + timedelta(hours=2, minutes=30)
    return start.strftime("%H:%M"), end.strftime("%H:%M")


def main() -> None:
    parser = argparse.ArgumentParser(description="KBL 공식 API 우선 평일 자동 평점 실행기")
    parser.add_argument("--date", default=date.today().strftime("%Y%m%d"))
    parser.add_argument(
        "--pages",
        type=int,
        help="이번 실행에만 적용할 DCInside 마지막 페이지 (기본: 1경기 30, 2경기 이상 60)",
    )
    parser.add_argument(
        "--from-game",
        type=int,
        default=1,
        help="재개할 경기 순번(1부터). 앞선 경기는 건너뜁니다.",
    )
    args = parser.parse_args()

    games = fetch_regular_season_games(args.date)
    if not games:
        print(f"{args.date}: KBL 정규리그 경기 없음. DCInside 수집 없이 종료합니다.")
        return

    # Confirm the official roster before any community-page request.
    confirmed: list[dict[str, object]] = []
    for game in games:
        roster = confirm_participants(game["code"])
        game["roster"] = roster
        confirmed.append(game)
        print(f"공식 확인: {game['away']} vs {game['home']} / 실제 출전 {len(roster)}명 / 코드 {game['code']}")

    default_pages = 30 if len(confirmed) == 1 else 60
    pages = args.pages or default_pages
    if pages < 1 or pages > 60:
        raise ValueError("--pages는 1~60 범위여야 합니다.")
    if args.from_game < 1 or args.from_game > len(confirmed):
        raise ValueError(f"--from-game은 1~{len(confirmed)} 범위여야 합니다.")
    shared_html = BASE / "runs" / args.date / "shared_html"
    print(f"{args.date}: 정규리그 {len(confirmed)}경기 / {pages}페이지 수집")
    run(BASE / "dcinside_basketball_html_saver.py", "--first-page", 1, "--last-page", pages, "--date", args.date, "--output-dir", shared_html, "--headless")
    for game_index, game in enumerate(confirmed, start=1):
        if game_index < args.from_game:
            print(f"{game_index}번째 경기: 이미 완료된 경기로 간주하고 건너뜀")
            continue
        start_time, end_time = community_time_window(args.date, str(game.get("start", "")))
        print(f"커뮤니티 분석 시간: {game['away']} vs {game['home']} / {start_time}~{end_time}")
        run(
            BASE / "daily_kbl_local.py",
            "--game-code", game["code"],
            "--date", args.date,
            "--games-today", len(confirmed),
            "--html-dir", shared_html,
            "--first-page", 1,
            "--last-page", pages,
            "--home-team", game["home"],
            "--away-team", game["away"],
            "--home-score", game["home_score"],
            "--away-score", game["away_score"],
            "--round", game["round"],
            "--start-time", start_time,
            "--end-time", end_time,
            "--roster-json", json.dumps(game["roster"], ensure_ascii=False),
        )
    # Vercel/GitHub Pages can deploy straight from docs/.  Publishing remains
    # opt-in because it creates a remote Git commit on the user's repository.
    if __import__("os").environ.get("PUBLISH_TEAM_PAGES", "").strip() == "1":
        run(BASE / "publish_team_pages.py", "--message", f"Publish KBL ratings {args.date}")


if __name__ == "__main__":
    main()
