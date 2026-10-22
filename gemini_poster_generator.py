"""Generate a cinematic poster base locally with Gemini's image API.

The model is sent only the two official KBL player photos and art direction.
Names, team names, ratings and scores are intentionally overlaid later by
``newsletter_generator.py`` so factual Korean text stays correct.
"""
from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen


API_URL = "https://generativelanguage.googleapis.com/v1beta/interactions"
DEFAULT_MODEL = "gemini-nano-banana-2.1"


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def read_best(rows: list[dict[str, str]], team: str) -> dict[str, str]:
    players = [row for row in rows if row.get("팀") == team]
    if not players:
        raise ValueError(f"평점 CSV에 {team} 선수가 없습니다.")
    best = max(players, key=lambda row: number(row.get("10점평점")))
    if not best.get("선수사진URL"):
        raise ValueError(f"{team} 최고 평점 선수의 KBL 사진 URL이 없습니다.")
    return best


def fetch_image(url: str) -> tuple[str, str]:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (KBL rating poster generator)"})
    with urlopen(request, timeout=30) as response:
        data = response.read()
        mime = response.headers.get_content_type() or "image/png"
    if not data:
        raise ValueError(f"선수 사진을 비어 있는 응답으로 받았습니다: {url}")
    return mime, base64.b64encode(data).decode("ascii")


def prompt(away: dict[str, str], home: dict[str, str]) -> str:
    return f"""Create a premium square 2K professional basketball video-game cover art background.

The two attached images are official KBL player photos and must be treated as strict identity and uniform references:
- First image: {away['선수']} of {away['팀']}, place on the left.
- Second image: {home['선수']} of {home['팀']}, place on the right.

Make the two adult athletes stand back-to-back in a powerful shoulders-up to waist-up pose, facing slightly toward camera. Preserve their recognizable face, hairstyle, body type, skin tone, jersey cut, jersey color blocks, number, and sponsor/uniform details from the supplied references. Use realistic cinematic sports photography, sharp face detail, dramatic rim lighting, subtle rain mist and colored smoke matching each actual uniform's main colors. Dark arena atmosphere, reflective court floor, strong depth, premium esports game-poster composition.

Do not add any text, letters, scores, logos, invented team marks, badges, watermarks, or extra people. Keep the bottom 27 percent mostly dark and uncluttered for a later factual score/name overlay. Output exactly one 1:1 image."""


def call_api(api_key: str, model: str, text: str, away_image: tuple[str, str], home_image: tuple[str, str]) -> bytes:
    body = {
        "model": model,
        "input": [
            {"type": "text", "text": text},
            {"type": "image", "mime_type": away_image[0], "data": away_image[1]},
            {"type": "image", "mime_type": home_image[0], "data": home_image[1]},
        ],
        "response_format": {"type": "image", "mime_type": "image/png", "aspect_ratio": "1:1", "image_size": "2K"},
    }
    request = Request(
        API_URL,
        data=json.dumps(body).encode("utf-8"),
        headers={"x-goog-api-key": api_key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=180) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Gemini 이미지 API 오류 {error.code}: {details}") from error
    encoded = (payload.get("output_image") or {}).get("data")
    if not encoded:
        raise RuntimeError("Gemini 이미지 API가 PNG를 반환하지 않았습니다: " + json.dumps(payload, ensure_ascii=False)[:600])
    return base64.b64decode(encoded)


def main() -> None:
    parser = argparse.ArgumentParser(description="공식 KBL 사진 2장으로 AI 게임 포스터 배경 생성")
    parser.add_argument("--ratings", type=Path, required=True)
    parser.add_argument("--away", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--model", default=os.environ.get("GEMINI_IMAGE_MODEL", DEFAULT_MODEL))
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--dry-run", action="store_true", help="API 요청 없이 선택 선수와 모델만 확인")
    args = parser.parse_args()
    with args.ratings.open(encoding="utf-8-sig", newline="") as file:
        rows = list(csv.DictReader(file))
    away, home = read_best(rows, args.away), read_best(rows, args.home)
    print(f"AI 포스터: {away['팀']} {away['선수']} ({number(away.get('10점평점')):.1f}) vs {home['팀']} {home['선수']} ({number(home.get('10점평점')):.1f})")
    print(f"모델: {args.model}")
    if args.dry_run:
        return
    if args.output.exists() and not args.force:
        print(f"기존 AI 포스터 배경 재사용: {args.output}")
        return
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY가 없습니다. Windows 사용자 환경 변수에 설정하세요.")
    away_image, home_image = fetch_image(away["선수사진URL"]), fetch_image(home["선수사진URL"])
    png = call_api(api_key, args.model, prompt(away, home), away_image, home_image)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(png)
    print(f"AI 포스터 배경 저장: {args.output}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"AI 포스터 생성 실패: {error}", file=sys.stderr)
        raise
