"""Send generated KBL rating cards and captions to an ntfy topic.

The topic is deliberately supplied through environment variables so no private
notification address or token is committed to GitHub.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen


DEFAULT_SERVER = "https://ntfy.sh"


def find_outputs(root: Path) -> list[Path]:
    patterns = (
        "**/output/instagram_rating_card_*.png",
        "**/output/instagram_caption_*.txt",
    )
    found = {path.resolve() for pattern in patterns for path in root.glob(pattern)}
    return sorted(found, key=lambda path: (path.suffix != ".png", path.name))


def attachment_name(path: Path, position: int) -> str:
    """Use an ASCII attachment name: urllib header values must be latin-1."""
    kind = "rating-card" if path.suffix.lower() == ".png" else "instagram-caption"
    return f"kbl-{kind}-{position:02d}{path.suffix.lower()}"


def publish(
    server: str,
    topic: str,
    token: str,
    path: Path,
    position: int,
    total: int,
) -> None:
    """Upload one attachment with a distinct title and bounded retries."""
    kind = "rating card" if path.suffix.lower() == ".png" else "Instagram caption"
    headers = {
        # A unique title stops mobile clients from presenting all cards as one
        # visually identical grouped notification.
        "Title": f"KBL {kind} {position}/{total}",
        "Tags": "basketball",
        "Priority": "4",
        "Filename": attachment_name(path, position),
        "Content-Type": "image/png" if path.suffix.lower() == ".png" else "text/plain; charset=utf-8",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    endpoint = f"{server.rstrip('/')}/{quote(topic, safe='')}"
    payload = path.read_bytes()

    last_error: Exception | None = None
    for attempt in range(1, 4):
        try:
            request = Request(endpoint, data=payload, headers=headers, method="PUT")
            with urlopen(request, timeout=45) as response:
                if 200 <= response.status < 300:
                    print(f"ntfy 수락: {path.name} (HTTP {response.status})")
                    return
                raise RuntimeError(f"HTTP {response.status}")
        except (HTTPError, URLError, TimeoutError, OSError, RuntimeError) as error:
            last_error = error
            if attempt == 3:
                break
            wait_seconds = attempt * 3
            print(f"ntfy 재시도: {path.name} — {error}; {wait_seconds}초 후")
            time.sleep(wait_seconds)

    raise RuntimeError(f"ntfy 전송 실패 ({path.name}): {last_error}")


def main() -> None:
    parser = argparse.ArgumentParser(description="KBL 결과물을 ntfy 첨부 알림으로 전송")
    parser.add_argument("--input-dir", type=Path, default=Path("runs"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    topic = os.getenv("NTFY_TOPIC", "").strip()
    if not topic:
        print("NTFY_TOPIC이 비어 있어 ntfy 전송을 건너뜁니다.")
        return
    server = os.getenv("NTFY_SERVER", DEFAULT_SERVER).strip() or DEFAULT_SERVER
    token = os.getenv("NTFY_TOKEN", "").strip()
    outputs = find_outputs(args.input_dir)
    if not outputs:
        raise FileNotFoundError(f"전송할 카드 PNG 또는 캡션 TXT가 없습니다: {args.input_dir}")

    total = len(outputs)
    for position, path in enumerate(outputs, start=1):
        print(f"ntfy {'검증' if args.dry_run else '전송'} ({position}/{total}): {path}")
        if not args.dry_run:
            publish(server, topic, token, path, position, total)
            # Keep attachments visibly separate in mobile notification clients
            # without materially delaying the overall workflow.
            if position < total:
                time.sleep(1.5)
    print(f"ntfy 완료: {len(outputs)}개 파일")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"ntfy 전송 오류: {error}", file=sys.stderr)
        raise
