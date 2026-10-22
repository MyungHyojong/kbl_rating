"""Create publishable static team-rating pages from one game's final CSV.

The generated ``docs/`` directory is intentionally plain HTML.  It can be
served by GitHub Pages or used as Vercel's output directory without exposing
the crawler, Gemini key, raw posts, or local run folders.
"""
from __future__ import annotations

import argparse
import csv
import html
import json
import re
from collections import defaultdict
from pathlib import Path


BASE = Path(__file__).resolve().parent


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def slug(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9가-힣]+", "-", value).strip("-")
    return cleaned or "team"


def player_row(row: dict[str, str]) -> str:
    photo = html.escape(row.get("선수사진URL", ""), quote=True)
    image = f'<img src="{photo}" alt="" loading="lazy">' if photo else ""
    source = "커뮤니티" if row.get("평점출처") == "커뮤니티 점수합" else "GmSc 예측"
    return f'''<article class="player">
      <div class="face">{image}</div>
      <div class="identity"><strong>{html.escape(row.get("선수", ""))}</strong><span>#{html.escape(row.get("등번호") or "-")} · {html.escape(row.get("선발여부") or "출전")}</span></div>
      <div class="stat"><b>{number(row.get("10점평점")):.1f}</b><span>평점</span></div>
      <div class="detail"><span>GmSc {number(row.get("GmSc")):.1f}</span><span>언급 {int(number(row.get("언급수")))}</span><small>{source}</small></div>
    </article>'''


def team_page(
    *, team: str, rows: list[dict[str, str]], game_code: str, date: str,
    home: str, away: str, home_score: str, away_score: str, round_name: str,
    root_prefix: str,
) -> str:
    players = sorted(rows, key=lambda row: number(row.get("10점평점")), reverse=True)
    best = players[0]
    average = sum(number(row.get("10점평점")) for row in players) / len(players)
    scoreline = f"{away} {away_score} : {home_score} {home}"
    cards = "".join(player_row(row) for row in players)
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(team)} · KBL 선수 평점</title><style>
:root{{color-scheme:dark;--paper:#10141d;--panel:#171d29;--line:#2c3546;--text:#f2f5fa;--muted:#a7b0c1;--accent:#7fc3ff}}*{{box-sizing:border-box}}body{{margin:0;background:radial-gradient(circle at 10% 0,#1e3d59 0,transparent 34%),#0b0f16;color:var(--text);font-family:"Malgun Gothic","Noto Sans KR",system-ui,sans-serif}}main{{max-width:920px;margin:auto;padding:42px 22px 70px}}a{{color:inherit}}.back{{color:var(--muted);font-size:14px;text-decoration:none}}header{{margin:26px 0 20px;padding:30px;border:1px solid var(--line);border-radius:20px;background:linear-gradient(125deg,#172435,#171b28)}}.eyebrow{{margin:0 0 9px;color:#9fcfff;font-weight:800;font-size:13px;letter-spacing:1.7px}}h1{{margin:0;font-size:clamp(28px,6vw,48px);letter-spacing:-2.5px}}.game{{margin:14px 0 0;color:var(--muted);font-weight:700}}.summary{{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:22px 0}}.summary>div{{padding:19px;border:1px solid var(--line);border-radius:16px;background:var(--panel)}}.summary span{{display:block;color:var(--muted);font-size:13px}}.summary b{{display:block;margin-top:6px;font-size:25px}}.players{{display:grid;gap:11px}}.player{{display:grid;grid-template-columns:62px minmax(120px,1fr) 72px minmax(140px,.9fr);align-items:center;gap:15px;padding:14px 16px;border:1px solid var(--line);border-radius:16px;background:#131924}}.face{{width:62px;height:62px;overflow:hidden;border-radius:50%;background:#283247}}.face img{{width:100%;height:100%;object-fit:cover}}.identity strong,.identity span,.detail span,.detail small,.stat span{{display:block}}.identity strong{{font-size:18px}}.identity span,.detail{{margin-top:3px;color:var(--muted);font-size:13px}}.stat{{text-align:center}}.stat b{{display:block;color:var(--accent);font-size:31px;line-height:1}}.stat span{{margin-top:4px;color:var(--muted);font-size:12px}}.detail{{display:grid;gap:3px}}@media(max-width:640px){{main{{padding:24px 14px 48px}}.player{{grid-template-columns:54px 1fr 64px;gap:10px;padding:12px}}.face{{width:54px;height:54px}}.detail{{display:none}}.identity strong{{font-size:16px}}.stat b{{font-size:27px}}}}
</style></head><body><main><a class="back" href="{root_prefix}index.html">← 전체 경기</a><header><p class="eyebrow">{html.escape(round_name)} · {html.escape(date[:4]+'.'+date[4:6]+'.'+date[6:])}</p><h1>{html.escape(team)} PLAYER RATINGS</h1><p class="game">{html.escape(scoreline)}</p></header><section class="summary"><div><span>TEAM BEST</span><b>{html.escape(best.get("선수", ""))} · {number(best.get("10점평점")):.1f}</b></div><div><span>TEAM AVERAGE</span><b>{average:.1f}</b></div></section><section class="players">{cards}</section></main></body></html>'''


def root_page(entries: list[dict[str, str]]) -> str:
    cards = "".join(
        f'<a class="card" href="{html.escape(entry["url"], quote=True)}"><strong>{html.escape(entry["team"])}</strong><span>{html.escape(entry["date"])} · {html.escape(entry["game"])}</span><b>{html.escape(entry["best_player"])} {entry["best_rating"]}</b></a>'
        for entry in sorted(entries, key=lambda item: (item["date"], item["game"], item["team"]), reverse=True)
    )
    return f'''<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>KBL Community Ratings</title><style>body{{max-width:900px;margin:auto;padding:42px 22px;background:#0b0f16;color:#f2f5fa;font-family:"Malgun Gothic","Noto Sans KR",system-ui,sans-serif}}h1{{font-size:42px;letter-spacing:-2px}}p{{color:#a7b0c1}}.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(245px,1fr));gap:14px}}.card{{display:block;padding:22px;border:1px solid #2c3546;border-radius:16px;background:#171d29;color:inherit;text-decoration:none}}.card strong,.card span,.card b{{display:block}}.card strong{{font-size:22px}}.card span{{margin:7px 0 16px;color:#a7b0c1;font-size:13px}}.card b{{color:#8bcaff}}</style><h1>KBL COMMUNITY RATINGS</h1><p>경기별 팀 선수 평점</p><section class="grid">{cards}</section>'''


def main() -> None:
    parser = argparse.ArgumentParser(description="GitHub/Vercel용 정적 팀 평점 페이지 생성기")
    parser.add_argument("--ratings", type=Path, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--game-code", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--home-score", required=True)
    parser.add_argument("--away-score", required=True)
    parser.add_argument("--round", default="정규리그")
    parser.add_argument("--site-dir", type=Path, default=BASE / "docs")
    args = parser.parse_args()

    with args.ratings.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    if not rows:
        raise ValueError("평점 CSV에 선수가 없습니다.")
    by_team: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("팀"):
            by_team[row["팀"]].append(row)
    if not by_team:
        raise ValueError("평점 CSV에서 팀을 찾지 못했습니다.")

    site = args.site_dir.resolve()
    game_dir = site / "games" / args.date / args.game_code
    game_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = site / "rating_manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        entries = manifest if isinstance(manifest, list) else []
    except FileNotFoundError:
        entries = []
    entries = [entry for entry in entries if not (entry.get("date") == args.date and entry.get("game") == args.game_code)]

    for team, players in by_team.items():
        filename = f"{slug(team)}.html"
        page = game_dir / filename
        page.write_text(team_page(
            team=team, rows=players, game_code=args.game_code, date=args.date,
            home=args.home, away=args.away, home_score=args.home_score,
            away_score=args.away_score, round_name=args.round, root_prefix="../../../",
        ), encoding="utf-8")
        best = max(players, key=lambda row: number(row.get("10점평점")))
        entries.append({
            "date": args.date, "game": args.game_code, "team": team,
            "best_player": best.get("선수", ""), "best_rating": f"{number(best.get('10점평점')):.1f}",
            "url": f"games/{args.date}/{args.game_code}/{filename}",
        })
        print(f"팀 페이지: {page}")

    site.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    (site / "index.html").write_text(root_page(entries), encoding="utf-8")
    print(f"정적 사이트 갱신: {site / 'index.html'}")


if __name__ == "__main__":
    main()
