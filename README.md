# KBL 커뮤니티 평점 로컬 파이프라인

한 경기의 KBL 경기코드를 받아, DCInside 남자농구 갤러리 목록을 천천히 저장하고
19:00~21:30에 올라온 제목을 Gemini로 판독한 뒤 KBL 공식 기록(GmSc)과 결합해
선수별 평점 CSV 및 팀별 1080×1080 인스타그램 카드를 만듭니다.

## 최초 1회

```powershell
py -m pip install -r requirements.txt
$env:GEMINI_API_KEY = "본인의 Gemini API 키"
```

`KBL_선수_별명 총정리.xlsx`는 프로젝트 폴더에 그대로 둡니다. API 키는 파일에 저장하지 않습니다.

## 한 번에 실행

```powershell
py .\daily_kbl_local.py --game-code S49G01N18 --date 20261012 --games-today 1
```

- `--game-code`: KBL 경기코드. KBL 경기 기록 URL/API에서 확인한 코드입니다.
- `--games-today 1`: 1~30페이지를 수집합니다. 두 경기 이상인 날은 `--games-today 2`로 실행해 1~60페이지를 수집합니다.
- 기본 시간 범위는 `19:00` 이상 `21:30` 미만입니다. 필요하면 `--start-time 18:30 --end-time 21:30`처럼 바꿀 수 있습니다.
- Chrome이 보이는 방식이 기본입니다. 점검·서버 실행은 마지막에 `--headless`를 추가할 수 있습니다.

결과는 `runs/YYYYMMDD/경기코드/output/`에 저장됩니다.

- `posts_all.csv`: 목록에서 추출한 전체 글
- `posts_1900_2130.csv`: 시간 필터 통과 글
- `posts_gemini.csv`: Gemini 선수/팀·감성 판독 결과
- `player_ratings_gmsc_YYYYMMDD.csv`: 최종 평점
- `instagram_rating_card_날짜_팀명.html/.png`: 팀별 인스타 카드
- `player_ratings_dashboard.html`: 해당 경기 결과 페이지

수집기는 페이지마다 기본 3~5초를 쉬고, 차단·예상 밖 리디렉션을 발견하면 추가 요청 없이 중단합니다. 목록 HTML만 수집하며 게시글 본문은 방문하지 않습니다.

## 현재 범위

이 버전은 **경기코드 1개를 넣으면 한 경기 전체 절차가 끝나는 로컬 실행판**입니다. 당일 모든 경기의 경기코드를 자동으로 찾고 팀별로 반복하는 일정 탐색 단계는, 이 실행판을 실제 경기일에 검증한 뒤 추가합니다.
