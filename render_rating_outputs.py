"""Create static dashboard and 1080px Instagram cards from a rating CSV."""
from __future__ import annotations

import argparse
import csv
import html
import re
import shutil
import subprocess
from pathlib import Path


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9가-힣]+", "_", value).strip("_")


def grade(value: float) -> str:
    if value >= 9: return "elite"
    if value >= 8: return "great"
    if value >= 6.5: return "good"
    if value >= 5: return "mid"
    if value >= 4: return "low"
    return "poor"


def player_html(row: dict[str, str], klass: str) -> str:
    name, photo = html.escape(row["선수"]), html.escape(row.get("선수사진URL", ""), quote=True)
    score = number(row.get("10점평점"))
    avatar = f'<img src="{photo}" alt="{name}">' if photo else name[-2:]
    return f'<article class="player {klass}"><div class="avatar">{avatar}</div><b class="score {grade(score)}">{score:.1f}</b><div class="player-name">{name}</div></article>'


def card_html(team: str, date: str, players: list[dict[str, str]]) -> str:
    starters = [p for p in players if p.get("선발여부") == "선발"]
    if len(starters) != 5:
        starters = sorted(players, key=lambda p: number(p.get("출전시간초")), reverse=True)[:5]
    bench = [p for p in players if p not in starters]
    bench_html = "".join(
        f'<div class="bench-player"><span class="name-pill"><b>{html.escape(p.get("등번호") or "-")}</b> {html.escape(p["선수"])}</span><b class="score {grade(number(p.get("10점평점")))}">{number(p.get("10점평점")):.1f}</b></div>'
        for p in bench
    ) or '<div class="bench-player">벤치 출전 선수 없음</div>'
    positions = ["pg", "sg", "sf", "pf", "c"]
    starter_html = "".join(player_html(p, positions[i]) for i, p in enumerate(starters))
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>{html.escape(team)} 선수 평점</title><style>
@import url('https://fonts.googleapis.com/css2?family=Black+Han+Sans&family=Noto+Sans+KR:wght@500;700;900&display=swap');*{{box-sizing:border-box}}html,body{{margin:0;width:1080px;height:1080px;overflow:hidden;background:#ef907f;font-family:"Noto Sans KR",sans-serif}}.card{{position:relative;width:1080px;height:1080px;overflow:hidden;background:#ef907f;color:#231c1a;border:12px solid #302522}}.card:before,.card:after{{content:"";position:absolute;pointer-events:none}}.card:before{{width:730px;height:730px;border:7px solid rgba(91,58,53,.36);border-radius:50%;left:175px;top:-515px}}.card:after{{width:864px;height:600px;border:7px solid rgba(91,58,53,.36);border-bottom:0;border-radius:432px 432px 0 0;left:96px;bottom:-74px}}.key,.free{{position:absolute;z-index:1;border-color:rgba(91,58,53,.36);pointer-events:none}}.key{{width:292px;height:222px;border:6px solid rgba(91,58,53,.36);border-bottom:0;left:382px;bottom:0}}.free{{width:166px;height:83px;border:6px solid rgba(91,58,53,.36);border-bottom:0;border-radius:166px 166px 0 0;left:445px;bottom:222px}}.head{{height:80px;background:#fffaf4;padding:16px 36px;display:flex;align-items:center;justify-content:space-between;border-bottom:6px solid #302522;position:relative;z-index:2}}.head h1{{margin:0;font:31px "Black Han Sans",sans-serif;letter-spacing:-1px}}.head span{{font-size:16px;font-weight:900;color:#7a6258}}.bench{{height:264px;padding:21px 38px;position:relative;z-index:1}}.title{{margin:0;color:#fff;font-size:39px;line-height:1;font-weight:500;letter-spacing:-2px}}.bench-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:13px 12px;margin-top:22px}}.bench-player{{display:flex;align-items:center;gap:7px;font-weight:900;font-size:23px;letter-spacing:-1.5px}}.name-pill{{background:white;border-radius:99px;padding:7px 10px;box-shadow:0 5px 12px #5b34232a;white-space:nowrap}}.name-pill b{{color:#e96c5c;font-size:20px}}.score{{display:inline-grid;place-items:center;min-width:70px;height:47px;color:#fff;border-radius:17px;border:3px solid #fff;box-shadow:0 7px 13px #43251c55,inset 0 1px 0 #fff9;font:28px "Black Han Sans",sans-serif}}.elite{{background:#e38b0b;color:#30220a}}.great{{background:#247acf}}.good{{background:#347e2d}}.mid{{background:#536979}}.low{{background:#d64249}}.poor{{background:#6c2442}}.starters{{height:724px;position:relative;padding:25px 38px}}.starters .title{{position:relative;z-index:2}}.player{{position:absolute;width:195px;text-align:center;z-index:3}}.avatar{{width:142px;height:142px;border-radius:50%;margin:auto;background:#fff;border:7px solid white;box-shadow:0 8px 20px #3f211a55;overflow:hidden;display:grid;place-items:center;font-weight:900}}.avatar img{{width:100%;height:100%;object-fit:cover}}.player .score{{position:absolute;right:0;top:-10px}}.player-name{{display:inline-block;margin-top:10px;background:#fff;padding:5px 14px 6px;border-radius:99px;box-shadow:0 4px 11px #3f211a55;font:26px/1.1 "Black Han Sans",sans-serif;letter-spacing:-1px;white-space:nowrap}}.pg{{left:442px;top:85px}}.sg{{left:205px;top:232px}}.sf{{left:680px;top:232px}}.pf{{left:110px;top:464px}}.c{{left:775px;top:464px}}</style></head><body><main class="card"><header class="head"><h1>{html.escape(team)} PLAYER RATINGS</h1><span>{date[:4]}.{date[4:6]}.{date[6:]} · KBL</span></header><section class="bench"><h2 class="title">Bench members</h2><div class="bench-grid">{bench_html}</div></section><div class="key"></div><div class="free"></div><section class="starters"><h2 class="title">Starters</h2>{starter_html}</section></main></body></html>'''


def card_html_v2(team: str, date: str, players: list[dict[str, str]]) -> str:
    """Use a local, deterministic Korean font for the exported card title."""
    card = card_html(team, date, players)
    starters = [p for p in players if p.get("선발여부") == "선발"]
    if len(starters) != 5:
        starters = sorted(players, key=lambda p: number(p.get("출전시간초")), reverse=True)[:5]
    override = '''<style>
      .head h1,.title,.player-name{font-family:"Malgun Gothic","Noto Sans KR",sans-serif!important;font-weight:900!important}
      /* Keep player positions fixed; only lower the English section heading. */
      .pg{top:85px!important}.sg,.sf{top:232px!important}.pf,.c{top:464px!important}
      .starters>.title{transform:translateY(26px)!important}
    </style>'''
    return card.replace("</head>", override + "</head>", 1)


def dashboard_html(date: str, cards: list[tuple[str, str]]) -> str:
    links = "".join(f'<li><a href="{html.escape(file, quote=True)}">{html.escape(team)} 카드 열기</a></li>' for team, file in cards)
    return f'<!doctype html><meta charset="utf-8"><title>KBL Ratings {date}</title><style>body{{font:18px system-ui;margin:40px;background:#fff9f2;color:#201c1a}}h1{{font-size:42px}}a{{display:inline-block;padding:15px 20px;margin:8px;background:#ef907f;color:#201c1a;border-radius:10px;text-decoration:none;font-weight:800}}</style><h1>KBL PLAYER RATINGS</h1><p>{date} 경기별 결과</p><ul>{links}</ul>'


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratings", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--png", action="store_true")
    args = parser.parse_args()
    with args.ratings.open(encoding="utf-8-sig", newline="") as f: rows = list(csv.DictReader(f))
    output = args.output_dir.resolve(); output.mkdir(parents=True, exist_ok=True)
    by_team: dict[str, list[dict[str, str]]] = {}
    for row in rows: by_team.setdefault(row["팀"], []).append(row)
    cards: list[tuple[str, str]] = []
    for team, players in by_team.items():
        filename = f"instagram_rating_card_{args.date}_{safe_name(team)}.html"
        path = output / filename; path.write_text(card_html_v2(team, args.date, players), encoding="utf-8")
        cards.append((team, filename)); print(f"카드 HTML: {path}")
        if args.png:
            browser = next(
                (
                    Path(path)
                    for path in [
                        r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
                        r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
                        shutil.which("google-chrome"),
                        shutil.which("chromium"),
                        shutil.which("chromium-browser"),
                    ]
                    if path and Path(path).exists()
                ),
                None,
            )
            if not browser:
                raise FileNotFoundError("Edge 또는 Chrome/Chromium 실행 파일을 찾지 못했습니다.")
            png = path.with_suffix(".png")
            subprocess.run([str(browser), "--headless", "--disable-gpu", "--hide-scrollbars", "--window-size=1080,1080", f"--screenshot={png}", path.as_uri()], check=True)
            print(f"카드 PNG: {png}")
    (output / "player_ratings_dashboard.html").write_text(dashboard_html(args.date, cards), encoding="utf-8")


if __name__ == "__main__": main()
