"""Build player ratings from community scores and KBL box-score Game Score.

Steps
-----
1. Download the official KBL player box score for one game.
2. Calculate Basketball-Reference/Hollinger Game Score (GmSc).
3. Sum Gemini-labelled community scores by player.
4. Fit a simple OLS regression: community score sum ~ GmSc.
5. Use it only for players with zero mentions; retain actual sums otherwise.

The script does not alter its input CSVs.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
from collections import defaultdict
from pathlib import Path
from urllib.request import Request, urlopen


BASE_DIR = Path(__file__).resolve().parent
ANNOTATED_POSTS = BASE_DIR / "dcinside_basketballkorea_posts_선수평가.csv"
GAME_CODE = os.getenv("KBL_GAME_CODE", "S49G01N18")
GAME_DATE = os.getenv("KBL_GAME_DATE", "20261012")
# Fixed across games: a wider scale prevents a few negative community posts
# from immediately pushing a player to the lower asymptote.
RATING_SCORE_SCALE = float(os.getenv("RATING_SCORE_SCALE", "30"))
BOX_SCORE_CSV = BASE_DIR / f"kbl_boxscore_{GAME_DATE}.csv"
RATINGS_CSV = BASE_DIR / f"player_ratings_gmsc_{GAME_DATE}.csv"
REGRESSION_JSON = BASE_DIR / f"gmsc_regression_{GAME_DATE}.json"


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def calculate_gmsc(record: dict[str, object]) -> float:
    """Hollinger GmSc: PTS + .4FG - .7FGA - .4(FTA-FT) + .7ORB + .3DRB
    + STL + .7AST + .7BLK - .4PF - TOV.
    """
    points = number(record.get("score"))
    fg = number(record.get("fgt"))
    fga = number(record.get("fgtA"))
    ft = number(record.get("ft"))
    fta = number(record.get("ftA"))
    orb = number(record.get("offr"))
    drb = number(record.get("defr"))
    steals = number(record.get("stl"))
    assists = number(record.get("ast"))
    blocks = number(record.get("bs"))
    fouls = number(record.get("foul"))
    turnovers = number(record.get("to"))
    return round(
        points + 0.4 * fg - 0.7 * fga - 0.4 * (fta - ft) + 0.7 * orb + 0.3 * drb
        + steals + 0.7 * assists + 0.7 * blocks - 0.4 * fouls - turnovers,
        2,
    )


def fetch_box_score() -> list[dict[str, object]]:
    """Download the public player-stat endpoint used by KBL's match-record page."""
    url = f"https://api.kbl.or.kr/match/{GAME_CODE}/player-stat"
    headers = {
        "Channel": "WEB",
        "TeamCode": "DefaultTeam",
        "X-Requested-With": "XMLHttpRequest",
        "lang": "ko",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    request = Request(url, headers=headers)
    with urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise ValueError("KBL API가 선수 기록 배열을 반환하지 않았습니다.")

    rows: list[dict[str, object]] = []
    for item in payload:
        player = item.get("player", {})
        record = item.get("records", {})
        if not isinstance(player, dict) or not isinstance(record, dict):
            continue
        seconds = int(number(record.get("playMin")) * 60 + number(record.get("playSec")))
        rows.append({
            "선수": clean(player.get("pname")),
            "팀": clean(player.get("tname")),
            "등번호": clean(player.get("backNum")),
            "KBL선수ID": clean(player.get("pcode")),
            "선수사진URL": clean(player.get("img")),
            "선발여부": "선발" if str(item.get("startFlag", "")).upper() in {"Y", "1", "TRUE"} else "벤치",
            "출전시간초": seconds,
            "PTS": number(record.get("score")),
            "FG": number(record.get("fgt")),
            "FGA": number(record.get("fgtA")),
            "FT": number(record.get("ft")),
            "FTA": number(record.get("ftA")),
            "ORB": number(record.get("offr")),
            "DRB": number(record.get("defr")),
            "AST": number(record.get("ast")),
            "STL": number(record.get("stl")),
            "BLK": number(record.get("bs")),
            "PF": number(record.get("foul")),
            "TOV": number(record.get("to")),
            "GmSc": calculate_gmsc(record),
        })
    if not rows:
        raise ValueError("KBL API에서 읽을 선수 기록이 없습니다.")
    return rows


def clean(value: object) -> str:
    return " ".join(str(value or "").split())


def write_box_score(rows: list[dict[str, object]]) -> None:
    columns = ["선수", "팀", "등번호", "KBL선수ID", "선수사진URL", "선발여부", "출전시간초", "PTS", "FG", "FGA", "FT", "FTA", "ORB", "DRB", "AST", "STL", "BLK", "PF", "TOV", "GmSc"]
    with BOX_SCORE_CSV.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)


def read_community_scores() -> tuple[dict[str, float], dict[str, int]]:
    if not ANNOTATED_POSTS.exists():
        raise FileNotFoundError(
            f"Gemini 평가 결과가 없습니다: {ANNOTATED_POSTS.name}. "
            "gemini_person_candidates.py를 먼저 완료하세요."
        )
    totals: dict[str, float] = defaultdict(float)
    mentions: dict[str, int] = defaultdict(int)
    with ANNOTATED_POSTS.open("r", newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"추정대상", "대상종류", "평가점수"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError("평가 CSV에 필요한 열(추정대상, 대상종류, 평가점수)이 없습니다.")
        for row in reader:
            # Team-wide posts are deliberately not redistributed to individual players.
            if clean(row.get("대상종류")) != "선수":
                continue
            player = clean(row.get("추정대상"))
            if player:
                totals[player] += number(row.get("평가점수"))
                mentions[player] += 1
    return totals, mentions


def fit_ols(samples: list[tuple[float, float]]) -> dict[str, float | int | str]:
    """Fit y = intercept + slope*x without external packages."""
    if len(samples) < 2:
        mean_y = sum(y for _, y in samples) / len(samples) if samples else 0.0
        return {"method": "평균값 대체 (회귀 표본 부족)", "n": len(samples), "intercept": mean_y, "slope": 0.0, "r_squared": 0.0}
    mean_x = sum(x for x, _ in samples) / len(samples)
    mean_y = sum(y for _, y in samples) / len(samples)
    ss_xx = sum((x - mean_x) ** 2 for x, _ in samples)
    if math.isclose(ss_xx, 0.0):
        return {"method": "평균값 대체 (GmSc 분산 없음)", "n": len(samples), "intercept": mean_y, "slope": 0.0, "r_squared": 0.0}
    slope = sum((x - mean_x) * (y - mean_y) for x, y in samples) / ss_xx
    intercept = mean_y - slope * mean_x
    ss_total = sum((y - mean_y) ** 2 for _, y in samples)
    ss_error = sum((y - (intercept + slope * x)) ** 2 for x, y in samples)
    r_squared = 1 - ss_error / ss_total if not math.isclose(ss_total, 0.0) else 0.0
    return {"method": "OLS: 언급 점수합 ~ GmSc", "n": len(samples), "intercept": round(intercept, 6), "slope": round(slope, 6), "r_squared": round(r_squared, 6)}


def build_ratings(box_score: list[dict[str, object]], totals: dict[str, float], mentions: dict[str, int]) -> tuple[list[dict[str, object]], dict[str, float | int | str]]:
    played = [row for row in box_score if int(row["출전시간초"]) > 0]
    samples = [(float(row["GmSc"]), totals[str(row["선수"])]) for row in played if mentions.get(str(row["선수"]), 0) > 0]
    model = fit_ols(samples)
    intercept, slope = float(model["intercept"]), float(model["slope"])
    results: list[dict[str, object]] = []
    for row in played:
        player = str(row["선수"])
        count = mentions.get(player, 0)
        observed = totals.get(player, 0.0)
        predicted = round(intercept + slope * float(row["GmSc"]), 2)
        results.append({
            "선수": player,
            "팀": row["팀"],
            "등번호": row["등번호"],
            "KBL선수ID": row["KBL선수ID"],
            "선수사진URL": row["선수사진URL"],
            "선발여부": row["선발여부"],
            "출전시간초": row["출전시간초"],
            "GmSc": row["GmSc"],
            "언급수": count,
            "커뮤니티점수합": round(observed, 2) if count else "",
            "GmSc_예측점수": predicted,
            "최종평점": round(observed, 2) if count else predicted,
            "평점출처": "커뮤니티 점수합" if count else "GmSc 회귀 예측",
        })
    # Fixed saturating scale, not match-by-match normalization. This keeps
    # zero at 6.5 without forcing any game's best player to exactly 10.
    for row in results:
        score = float(row["최종평점"])
        if score >= 0:
            rating = 6.5 + 3.5 * (1 - math.exp(-score / RATING_SCORE_SCALE))
        else:
            rating = 6.5 - 3.0 * (1 - math.exp(score / RATING_SCORE_SCALE))
        row["10점평점"] = round(max(0.0, min(10.0, rating)), 2)
    model["normalization"] = "고정 포화식: 최종평점 0=6.5, 하한 3.5, 상한 10"
    model["rating_score_scale"] = RATING_SCORE_SCALE
    return results, model


def write_ratings(rows: list[dict[str, object]], model: dict[str, float | int | str]) -> None:
    columns = ["선수", "팀", "등번호", "KBL선수ID", "선수사진URL", "선발여부", "출전시간초", "GmSc", "언급수", "커뮤니티점수합", "GmSc_예측점수", "최종평점", "10점평점", "평점출처"]
    with RATINGS_CSV.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    REGRESSION_JSON.write_text(json.dumps(model, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="KBL 기록과 Gemini 평가를 결합해 선수 평점을 계산합니다.")
    parser.add_argument("--game-code", default=GAME_CODE)
    parser.add_argument("--date", default=GAME_DATE, help="YYYYMMDD")
    parser.add_argument("--annotations", type=Path, default=ANNOTATED_POSTS)
    parser.add_argument("--output-dir", type=Path, default=BASE_DIR)
    return parser.parse_args()


def main() -> None:
    global GAME_CODE, GAME_DATE, ANNOTATED_POSTS, BOX_SCORE_CSV, RATINGS_CSV, REGRESSION_JSON
    args = parse_args()
    GAME_CODE, GAME_DATE = args.game_code, args.date
    ANNOTATED_POSTS = args.annotations.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    BOX_SCORE_CSV = output_dir / f"kbl_boxscore_{GAME_DATE}.csv"
    RATINGS_CSV = output_dir / f"player_ratings_gmsc_{GAME_DATE}.csv"
    REGRESSION_JSON = output_dir / f"gmsc_regression_{GAME_DATE}.json"
    print(f"1/3 KBL 공식 기록 수집: {GAME_CODE}")
    box_score = fetch_box_score()
    write_box_score(box_score)
    print(f"  저장: {BOX_SCORE_CSV.name} ({len(box_score)}명)")
    print("2/3 Gemini 게시글 평가 합산")
    totals, mentions = read_community_scores()
    print("3/3 GmSc 회귀 및 미언급 선수 예측")
    ratings, model = build_ratings(box_score, totals, mentions)
    write_ratings(ratings, model)
    print(f"  회귀 표본: {model['n']}명, 방식: {model['method']}")
    print(f"  저장: {RATINGS_CSV.name}")


if __name__ == "__main__":
    main()
