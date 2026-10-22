"""저장한 DCInside 남자농구 마이너 갤러리 목록 HTML을 CSV로 합칩니다.

실행: py dcinside_html_to_csv.py

사이트에 다시 접속하지 않고, 로컬 HTML 파일만 읽습니다.
"""

from __future__ import annotations

import argparse
import csv
import re
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin


BASE_URL = "https://gall.dcinside.com"


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


class GalleryListParser(HTMLParser):
    """목록 테이블의 일반 게시글 행만 읽는 표준 라이브러리 파서입니다."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.rows: list[dict[str, str]] = []
        self.row: dict[str, str] | None = None
        self.cell_class = ""
        self.cell_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = dict(attrs)
        classes = set((attributes.get("class") or "").split())
        if tag == "tr" and "ub-content" in classes:
            self.row = {"글번호": "", "제목": "", "작성자": "", "작성일": "", "조회": "", "추천": "", "URL": ""}
        elif self.row is not None and tag == "td":
            self.cell_class = attributes.get("class") or ""
            self.cell_text = []
        elif self.row is not None and tag == "a" and "gall_tit" in self.cell_class:
            href = attributes.get("href") or ""
            if "/mgallery/board/view/" in href:
                self.row["URL"] = urljoin(BASE_URL, href)

    def handle_data(self, data: str) -> None:
        if self.row is not None and self.cell_class:
            self.cell_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if self.row is not None and tag == "td":
            text = clean_text(" ".join(self.cell_text))
            if "gall_num" in self.cell_class:
                self.row["글번호"] = text
            elif "gall_tit" in self.cell_class:
                # 댓글 수 표기 [3]는 제목에서 제외합니다.
                self.row["제목"] = re.sub(r"\s*\[\d+\]\s*$", "", text)
            elif "gall_writer" in self.cell_class:
                self.row["작성자"] = text
            elif "gall_date" in self.cell_class:
                self.row["작성일"] = text
            elif "gall_count" in self.cell_class:
                self.row["조회"] = text
            elif "gall_recommend" in self.cell_class:
                self.row["추천"] = text
            self.cell_class = ""
            self.cell_text = []
        elif self.row is not None and tag == "tr":
            # 일반 글만 글번호가 숫자이며, 공지·광고·설문 등은 제외됩니다.
            if self.row["글번호"].isdigit() and self.row["URL"]:
                self.rows.append(self.row)
            self.row = None


def page_number(path: Path) -> int:
    match = re.search(r"_p(\d+)\.html$", path.name)
    return int(match.group(1)) if match else 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="저장한 DCInside 목록 HTML을 CSV로 합칩니다.")
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--first-page", type=int, default=1)
    parser.add_argument("--last-page", type=int, help="지정 시 해당 목록 페이지 범위만 CSV에 반영")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_dir, output_file = args.input_dir.resolve(), args.output.resolve()
    html_files = sorted(
        (path for path in input_dir.glob("dcinside_basketballkorea_*_p*.html")
         if re.fullmatch(r"dcinside_basketballkorea_\d{8}_p\d+\.html", path.name)),
        key=page_number,
    )
    last_page = args.last_page if args.last_page is not None else float("inf")
    html_files = [path for path in html_files if args.first_page <= page_number(path) <= last_page]
    if not html_files:
        raise FileNotFoundError(
            f"HTML 파일을 찾지 못했습니다: {input_dir}\n"
            "먼저 dcinside_basketball_html_saver.py로 목록 HTML을 저장하세요."
        )

    posts_by_id: dict[str, dict[str, str]] = {}
    for html_file in html_files:
        parser = GalleryListParser()
        parser.feed(html_file.read_text(encoding="utf-8"))
        source_page = str(page_number(html_file))
        for row in parser.rows:
            row["목록페이지"] = source_page
            posts_by_id.setdefault(row["글번호"], row)
        print(f"{html_file.name}: 일반 글 {len(parser.rows)}개")

    rows = sorted(posts_by_id.values(), key=lambda row: int(row["글번호"]), reverse=True)
    fields = ["글번호", "제목", "작성자", "작성일", "조회", "추천", "목록페이지", "URL"]
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\n완료: 중복 제거 후 {len(rows)}개 게시글 -> {output_file}")


if __name__ == "__main__":
    main()
