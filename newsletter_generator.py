"""Create one Instagram-newsletter cover from each team's top rating."""
from __future__ import annotations

import argparse
import csv
import html
import re
import shutil
import subprocess
from pathlib import Path


def value(row: dict[str, str], key: str) -> float:
    try:
        return float(row.get(key) or 0)
    except ValueError:
        return 0.0


def team_slug(team: str) -> str:
    return "red" if "정관장" in team else "blue"


def safe_name(value: str) -> str:
    return re.sub(r"[^a-zA-Z0-9가-힣]+", "_", value).strip("_")


def caption_text(date: str, round_name: str, home: dict[str, str], away: dict[str, str], home_score: str, away_score: str, rows: list[dict[str, str]]) -> str:
    """Make a plain Instagram caption from the same final rating CSV."""
    def best_and_worst(team: str) -> tuple[dict[str, str], dict[str, str]]:
        players = [row for row in rows if row.get("팀") == team]
        return max(players, key=lambda row: value(row, "10점평점")), min(players, key=lambda row: value(row, "10점평점"))

    home_best, home_worst = best_and_worst(home["팀"])
    away_best, away_worst = best_and_worst(away["팀"])
    korean_date = f"{date[:4]}.{date[4:6]}.{date[6:]}"
    return f"""{home['팀']} {home_score} - {away_score} {away['팀']}
{korean_date} / {round_name}

{home['팀']}
Best: {home_best['선수']} {value(home_best, '10점평점'):.1f}
Worst: {home_worst['선수']} {value(home_worst, '10점평점'):.1f}

{away['팀']}
Best: {away_best['선수']} {value(away_best, '10점평점'):.1f}
Worst: {away_worst['선수']} {value(away_worst, '10점평점'):.1f}

커뮤니티 반응과 KBL 공식 경기 기록을 함께 반영한 선수 평점입니다.

#KBL #프로농구 #농구 #농구평점 #{home['팀'].replace(' ', '')} #{away['팀'].replace(' ', '')}"""


def build_html(date: str, round_name: str, home: dict[str, str], away: dict[str, str], home_score: str, away_score: str) -> str:
    """Build a square face-off card without enlarging the official KBL photos."""
    hscore, ascore = value(home, "10점평점"), value(away, "10점평점")

    def face(row: dict[str, str]) -> str:
        return (
            f'<img src="{html.escape(row.get("선수사진URL", ""), quote=True)}" '
            f'alt="{html.escape(row["선수"])}" width="470" height="609">'
        )

    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>KBL Matchup Newsletter</title><style>
*{{box-sizing:border-box}}html,body{{width:1080px;height:1080px;margin:0;overflow:hidden;background:#06090e;font-family:"Malgun Gothic","Noto Sans KR",Arial,sans-serif}}.cover{{position:relative;width:1080px;height:1080px;overflow:hidden;color:#fff;background:linear-gradient(90deg,#051525 0%,#0d1015 47%,#22090f 100%)}}.cover:before{{content:"";position:absolute;inset:0;background:radial-gradient(ellipse at 10% 61%,#1f98e9bb 0%,#1452808a 22%,transparent 52%),radial-gradient(ellipse at 91% 56%,#e43145b8 0%,#6f1623a0 25%,transparent 53%),repeating-radial-gradient(ellipse at 50% 120%,#fff2 0 2px,transparent 4px 36px);filter:contrast(1.13)}}.cover:after{{content:"";position:absolute;left:-90px;right:-90px;bottom:-90px;height:260px;background:linear-gradient(transparent,#030508 76%),repeating-linear-gradient(0deg,transparent 0 20px,#b8d7ed14 21px 23px);transform:perspective(240px) rotateX(35deg);transform-origin:bottom;opacity:.9}}.top{{position:absolute;z-index:8;top:35px;left:46px;right:46px;height:45px;display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #ffffff66}}.top b{{font-size:18px;letter-spacing:3px}}.top span{{font-size:16px;font-weight:700;letter-spacing:1px;color:#d8e0e8}}.headline{{position:absolute;z-index:7;top:112px;left:0;right:0;text-align:center;text-shadow:0 4px 20px #000}}.headline small{{display:block;font-size:15px;letter-spacing:5px;font-weight:700;color:#dae4ec}}.headline h1{{margin:8px 0 0;font-size:46px;line-height:1;font-weight:900;letter-spacing:-2px}}.smoke{{position:absolute;z-index:2;bottom:102px;width:500px;height:310px;filter:blur(34px);opacity:.84}}.smoke.left{{left:-115px;background:radial-gradient(ellipse,#aee7ffcc,transparent 67%)}}.smoke.right{{right:-115px;background:radial-gradient(ellipse,#ffabb3cc,transparent 67%)}}.player{{position:absolute;z-index:4;width:470px;height:609px;bottom:143px}}.player img{{display:block;width:470px;height:609px;object-fit:contain;object-position:center bottom;filter:drop-shadow(0 18px 16px #000b)}}.player.left{{left:18px}}.player.right{{right:18px}}.nameplate{{position:absolute;z-index:7;bottom:160px;width:405px;text-align:center;text-shadow:0 3px 10px #000}}.nameplate.left{{left:26px}}.nameplate.right{{right:26px}}.name{{font-size:39px;line-height:1.08;font-weight:900;letter-spacing:-2.5px}}.rating{{display:inline-block;margin-top:11px;padding:8px 23px;border:1px solid #ffffffbb;border-radius:999px;background:#06121cdd;box-shadow:0 9px 20px #0008;font-size:25px;line-height:1;font-weight:900;letter-spacing:.4px}}.nameplate.left .rating{{background:#1266a8e8}}.nameplate.right .rating{{background:#b51f34e8}}.versus{{position:absolute;z-index:9;left:50%;bottom:42px;transform:translateX(-50%);width:890px;text-align:center;border-top:1px solid #ffffff8a;border-bottom:1px solid #ffffff55;background:linear-gradient(90deg,#07111cdd,#0b0e12f2,#1d090ddd);padding:13px 25px 14px;box-shadow:0 12px 38px #000a}}.round{{font-size:14px;font-weight:800;letter-spacing:3px;color:#d5dde6}}.scoreline{{display:flex;justify-content:center;align-items:center;gap:19px;margin-top:5px}}.club{{width:235px;font-size:22px;font-weight:900;letter-spacing:-1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.score{{font-size:42px;line-height:1;font-weight:900}}.colon{{font-size:25px;color:#a8b4be}}.date{{margin-top:7px;font-size:14px;font-weight:700;letter-spacing:1.5px;color:#c8d0d8}}</style></head><body><main class="cover"><header class="top"><b>KBL COMMUNITY RATINGS</b><span>GAME NIGHT</span></header><section class="headline"><small>TOP RATED MATCHUP</small><h1>GAME NIGHT RECAP</h1></section><div class="smoke left"></div><div class="smoke right"></div><div class="player left">{face(away)}</div><div class="player right">{face(home)}</div><section class="nameplate left"><div class="name">{html.escape(away['선수'])}</div><div class="rating">평점 {ascore:.1f}</div></section><section class="nameplate right"><div class="name">{html.escape(home['선수'])}</div><div class="rating">평점 {hscore:.1f}</div></section><footer class="versus"><div class="round">{html.escape(round_name)} · REGULAR SEASON</div><div class="scoreline"><span class="club">{html.escape(away['팀'])}</span><strong class="score">{away_score}</strong><i class="colon">:</i><strong class="score">{home_score}</strong><span class="club">{html.escape(home['팀'])}</span></div><div class="date">{date[:4]}.{date[4:6]}.{date[6:]} · KBL GAME RECAP</div></footer></main></body></html>'''


def square_html(*args: object) -> str:
    """The newsletter design is natively a 1080×1080 feed card."""
    return build_html(*args)  # type: ignore[arg-type]


def restyle_html(card: str, home: dict[str, str], away: dict[str, str]) -> str:
    """Compatibility hook retained for callers using the existing interface."""
    return card


def ai_poster_html(
    date: str,
    round_name: str,
    home: dict[str, str],
    away: dict[str, str],
    home_score: str,
    away_score: str,
    base_image: Path,
    official_photos: bool = False,
) -> str:
    """Overlay reliable match information on an AI poster base.

    ``official_photos`` deliberately keeps player faces, jerseys, sponsors and
    numbers sourced from KBL rather than asking an image model to reproduce
    them.  The AI image is then used only as the arena/lighting background.
    """
    image_uri = html.escape(base_image.resolve().as_uri(), quote=True)
    players = ""
    if official_photos:
        players = (
            '<div class="official-player left"><img src="%s" alt="%s"></div>'
            '<div class="official-player right"><img src="%s" alt="%s"></div>'
            % (
                html.escape(away.get("선수사진URL", ""), quote=True),
                html.escape(away["선수"], quote=True),
                html.escape(home.get("선수사진URL", ""), quote=True),
                html.escape(home["선수"], quote=True),
            )
        )
    return f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>KBL Game Poster</title><style>
*{{box-sizing:border-box}}html,body{{width:1080px;height:1080px;margin:0;overflow:hidden;background:#05070b;font-family:"Malgun Gothic","Noto Sans KR",Arial,sans-serif}}.poster{{position:relative;width:1080px;height:1080px;overflow:hidden;background:#05070b url("{image_uri}") center/cover no-repeat;color:#fff}}.poster:after{{content:"";position:absolute;z-index:4;left:0;right:0;bottom:0;height:250px;background:linear-gradient(transparent 0%,#04070cf0 34%,#04070cff 100%)}}.official-player{{position:absolute;z-index:2;bottom:112px;width:540px;height:790px;overflow:hidden;filter:drop-shadow(0 18px 20px #000b)}}.official-player img{{width:100%;height:100%;object-fit:contain;object-position:center bottom;transform:scale(1.16);transform-origin:center bottom}}.official-player.left{{left:-25px}}.official-player.right{{right:-25px}}.top{{position:absolute;z-index:6;top:28px;left:42px;right:42px;display:flex;justify-content:space-between;align-items:center;border-bottom:1px solid #fff8;padding-bottom:12px;text-shadow:0 2px 8px #000}}.top b{{font-size:18px;letter-spacing:3px}}.top span{{font-size:16px;font-weight:800;letter-spacing:1px}}.match{{position:absolute;z-index:7;left:48px;right:48px;bottom:20px;text-align:center;text-shadow:0 3px 9px #000}}.round{{font-size:14px;font-weight:800;letter-spacing:3px;color:#d9e1e9}}.matchline{{display:grid;grid-template-columns:1fr 290px 1fr;align-items:center;gap:20px;margin:6px 0 5px}}.player-note{{min-width:0;text-align:left}}.player-note.right{{text-align:right}}.team{{font-size:16px;font-weight:800;color:#d3dce4;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.player-name{{font-size:25px;font-weight:900;letter-spacing:-1.5px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}.rating{{margin-top:2px;font-size:18px;font-weight:800;color:#9ed3ff}}.player-note.right .rating{{color:#ffb0b8}}.scoreline{{display:flex;align-items:center;justify-content:center;gap:16px}}.score{{font-size:66px;line-height:.95;font-weight:900;letter-spacing:-3px}}.colon{{font-size:30px;color:#b8c4d0}}.date{{font-size:14px;font-weight:700;letter-spacing:1.5px;color:#d5dde5}}</style></head><body><main class="poster"><header class="top"><b>KBL COMMUNITY RATINGS</b><span>GAME POSTER</span></header>{players}<footer class="match"><div class="round">{html.escape(round_name)} · REGULAR SEASON</div><div class="matchline"><section class="player-note"><div class="team">{html.escape(away['팀'])}</div><div class="player-name">{html.escape(away['선수'])}</div><div class="rating">평점 {value(away, '10점평점'):.1f}</div></section><div class="scoreline"><strong class="score">{away_score}</strong><i class="colon">:</i><strong class="score">{home_score}</strong></div><section class="player-note right"><div class="team">{html.escape(home['팀'])}</div><div class="player-name">{html.escape(home['선수'])}</div><div class="rating">평점 {value(home, '10점평점'):.1f}</div></section></div><div class="date">{date[:4]}.{date[4:6]}.{date[6:]} · KBL GAME NIGHT</div></footer></main></body></html>'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ratings", type=Path, required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--round", default="1R")
    parser.add_argument("--home", required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--home-score", required=True)
    parser.add_argument("--away-score", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--square", action="store_true", help="1080×1080 인스타 피드 규격으로 렌더링")
    parser.add_argument("--caption", action="store_true", help="인스타그램 게시글 멘트 TXT도 생성")
    parser.add_argument("--ai-base-image", type=Path, help="AI 보정 게임 포스터 배경 PNG를 사용해 정보 오버레이를 생성")
    parser.add_argument("--official-photos", action="store_true", help="AI 배경 위에 KBL 공식 선수 사진을 합성")
    args = parser.parse_args()
    with args.ratings.open(encoding="utf-8-sig", newline="") as f: rows = list(csv.DictReader(f))
    def best(team: str) -> dict[str, str]:
        candidates = [row for row in rows if row.get("팀") == team]
        if not candidates: raise ValueError(f"평점 CSV에 {team} 선수가 없습니다.")
        return max(candidates, key=lambda row: value(row, "10점평점"))
    home, away = best(args.home), best(args.away)
    out = args.output_dir.resolve(); out.mkdir(parents=True, exist_ok=True)
    suffix = "_square_ai_poster" if args.ai_base_image else ("_square" if args.square else "")
    html_path = out / f"newsletter_{args.date}_{args.away}_vs_{args.home}{suffix}.html"
    if args.ai_base_image:
        if not args.ai_base_image.exists():
            raise FileNotFoundError(f"AI 포스터 배경을 찾지 못했습니다: {args.ai_base_image}")
        card = ai_poster_html(args.date, args.round, home, away, args.home_score, args.away_score, args.ai_base_image, args.official_photos)
    else:
        builder = square_html if args.square else build_html
        card = builder(args.date, args.round, home, away, args.home_score, args.away_score)
    html_path.write_text(restyle_html(card, home, away), encoding="utf-8")
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
    png_path = html_path.with_suffix(".png")
    window_size = "1080,1080" if args.square else "1080,1350"
    subprocess.run([str(browser), "--headless", "--disable-gpu", "--hide-scrollbars", "--run-all-compositor-stages-before-draw", "--virtual-time-budget=5000", f"--window-size={window_size}", f"--screenshot={png_path}", html_path.as_uri()], check=True)
    print(f"뉴스레터 HTML: {html_path}\n뉴스레터 PNG: {png_path}")
    if args.caption:
        caption_path = out / f"instagram_caption_{args.date}_{safe_name(args.away)}_vs_{safe_name(args.home)}.txt"
        caption_path.write_text(caption_text(args.date, args.round, home, away, args.home_score, args.away_score, rows), encoding="utf-8")
        print(f"인스타그램 멘트: {caption_path}")


if __name__ == "__main__": main()
