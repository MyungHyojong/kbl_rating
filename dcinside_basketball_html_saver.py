"""DCInside 농구 갤러리 목록 HTML을 천천히 저장하는 재개 가능 스크립트.

처음 한 번: py -m pip install selenium
실행:       py dcinside_basketball_html_saver.py

목록 페이지의 HTML만 저장합니다. 게시글 상세 페이지는 방문하지 않습니다.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait


# 남자농구 마이너 갤러리. 일반 갤러리(/board/)가 아니라 마이너 갤러리(/mgallery/) 주소입니다.
BOARD_URL = "https://gall.dcinside.com/mgallery/board/lists?id=basketballkorea"
EXPECTED_GALLERY_ID = "basketballkorea"

# 사이트에 부담을 줄이기 위해 한 페이지를 저장한 뒤 이 범위 안에서 무작위로 쉽니다.
DEFAULT_MIN_DELAY_SECONDS = 3.0
DEFAULT_MAX_DELAY_SECONDS = 5.0


def load_progress(progress_file: Path) -> set[int]:
    """이전에 완전히 저장한 페이지 번호를 불러옵니다."""
    if not progress_file.exists():
        return set()
    try:
        data = json.loads(progress_file.read_text(encoding="utf-8"))
        return {int(page) for page in data.get("completed_pages", [])}
    except (json.JSONDecodeError, OSError, ValueError):
        print("진행 기록을 읽지 못했습니다. 기존 HTML 파일은 덮어쓰지 않고 다시 확인합니다.")
        return set()


def save_progress(progress_file: Path, completed_pages: set[int]) -> None:
    payload = {
        "completed_pages": sorted(completed_pages),
        "updated_at": datetime.now().isoformat(timespec="seconds"),
    }
    progress_file.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def looks_blocked(html: str) -> bool:
    """차단 안내로 보이면 더 요청하지 않고 멈춥니다. 우회 시도는 하지 않습니다."""
    signals = ("비정상적인 접근", "접근이 제한", "자동화된 접근", "Access Denied")
    return any(signal.lower() in html.lower() for signal in signals)


def requested_page_is_open(driver: webdriver.Chrome, page: int) -> bool:
    """서버가 요청을 1페이지 등 다른 페이지로 돌리면 저장하지 않습니다."""
    query = parse_qs(urlparse(driver.current_url).query)
    if query.get("id", [""])[0] != EXPECTED_GALLERY_ID:
        return False
    # DCInside currently preserves the requested page in the canonical URL.
    # Prefer this reliable signal; the selected pagination element's class has
    # changed several times and previously caused false stops on page 1.
    if query.get("page", [""])[0] == str(page):
        return True

    # 현재 페이지는 보통 페이지네이션의 em/on/strong 요소로 표시됩니다.
    selectors = (
        ".bottom_paging_box em",
        ".bottom_paging_box .on",
        ".bottom_paging_box strong",
        ".pagination .on",
        ".pagination strong",
    )
    return any(
        element.text.strip() == str(page)
        for selector in selectors
        for element in driver.find_elements(By.CSS_SELECTOR, selector)
    )

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="DCInside 남자농구 갤러리 목록 HTML을 천천히 저장합니다.")
    parser.add_argument("--first-page", type=int, default=1)
    parser.add_argument("--last-page", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).resolve().parent / "runs" / datetime.now().strftime("%Y%m%d") / "html")
    parser.add_argument("--date", default=datetime.now().strftime("%Y%m%d"), help="파일명에 넣을 YYYYMMDD")
    parser.add_argument("--min-delay", type=float, default=DEFAULT_MIN_DELAY_SECONDS)
    parser.add_argument("--max-delay", type=float, default=DEFAULT_MAX_DELAY_SECONDS)
    parser.add_argument("--headless", action="store_true", help="자동화 서버용 headless Chrome")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.first_page < 1 or args.last_page < args.first_page:
        raise ValueError("FIRST_PAGE는 1 이상이고 LAST_PAGE보다 작거나 같아야 합니다.")
    if args.min_delay < 0 or args.max_delay < args.min_delay:
        raise ValueError("대기 시간 설정을 확인하세요.")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    progress_file = output_dir / "progress.json"
    completed_pages = load_progress(progress_file)

    options = Options()
    if args.headless:
        options.add_argument("--headless=new")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--window-size=1440,1200")
    else:
        options.add_argument("--start-maximized")

    driver = webdriver.Chrome(options=options)
    wait = WebDriverWait(driver, 20)
    try:
        for page in range(args.first_page, args.last_page + 1):
            html_file = output_dir / f"dcinside_basketballkorea_{args.date}_p{page}.html"
            if html_file.exists():
                completed_pages.add(page)
                save_progress(progress_file, completed_pages)
                print(f"{page}페이지: 이미 저장됨 - 건너뜀")
                continue

            url = f"{BOARD_URL}&page={page}"
            print(f"{page}페이지 열기: {url}")
            driver.get(url)
            try:
                wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
                wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, ".gall_list, .listwrap")))
            except TimeoutException:
                # 목록 레이아웃이 바뀐 경우에도 현재 HTML을 별도 저장해 확인할 수 있게 합니다.
                html = driver.page_source
                (output_dir / f"dcinside_basketball_unexpected_p{page}.html").write_text(
                    html, encoding="utf-8"
                )
                print(f"{page}페이지: 목록을 확인하지 못해 unexpected HTML 저장 후 중단")
                break

            html = driver.page_source
            if not requested_page_is_open(driver, page):
                (output_dir / f"dcinside_basketballkorea_unexpected_page_p{page}.html").write_text(
                    html, encoding="utf-8"
                )
                print(
                    f"{page}페이지: 실제 선택된 페이지를 확인하지 못했습니다. "
                    "HTML만 남기고 추가 요청 없이 중단합니다."
                )
                break
            if looks_blocked(html):
                (output_dir / f"dcinside_basketball_blocked_p{page}.html").write_text(
                    html, encoding="utf-8"
                )
                print(f"{page}페이지: 차단 안내로 보입니다. HTML 저장 후 추가 요청 없이 중단합니다.")
                break

            html_file.write_text(html, encoding="utf-8")
            completed_pages.add(page)
            save_progress(progress_file, completed_pages)
            print(f"{page}페이지 저장 완료: {html_file.name}")

            if page < args.last_page:
                delay = random.uniform(args.min_delay, args.max_delay)
                print(f"다음 요청 전 {delay:.1f}초 대기")
                time.sleep(delay)
    except WebDriverException as error:
        print(f"브라우저 오류로 중단: {error}")
    finally:
        driver.quit()


if __name__ == "__main__":
    main()
