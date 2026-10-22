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

## 공개 팀 페이지와 AI 게임 포스터 (선택)

매 실행이 끝나면 `docs/`에 경기별·팀별 정적 평점 페이지가 생성됩니다. 이 폴더에는 원본 글,
Gemini 응답, API 키가 들어가지 않습니다. GitHub Pages의 배포 원본 또는 Vercel의 Output Directory를
`docs`로 지정하면 됩니다.

아래 환경 변수는 한 번만 설정하면 평일 작업 스케줄러에서도 읽습니다.

```powershell
setx ENABLE_AI_POSTER 1
setx GEMINI_IMAGE_MODEL gemini-nano-banana-2.1
setx PUBLISH_TEAM_PAGES 1
```

- `ENABLE_AI_POSTER=1`: 공식 KBL 선수 사진 2장을 참고해 Gemini 이미지 API로 2K 게임 포스터 배경을 만들고, 정확한 이름·평점·스코어는 코드로 합성합니다. 이미지 모델의 사용 가능 여부와 과금/할당량은 Gemini 프로젝트 설정에 따릅니다. 실패하면 일반 뉴스레터 PNG로 자동 대체합니다.
- `PUBLISH_TEAM_PAGES=1`: 바뀐 `docs/`만 자동 커밋·푸시합니다. GitHub와 연결된 Vercel은 해당 푸시를 배포 트리거로 사용하면 됩니다.

## GitHub Actions 원격 자동화

`.github/workflows/kbl-daily-remote.yml`은 평일 21:30(한국 시간)에 GitHub Actions에서 같은 파이프라인을 실행합니다. GitHub 저장소의 **Settings → Secrets and variables → Actions**에 `GEMINI_API_KEY`를 Repository secret으로 한 번만 등록하세요.

- GitHub Actions → **KBL daily ratings** → **Run workflow**로 수동 검증할 수 있습니다.
- 원본 DCInside HTML, Gemini 판독 CSV, 최종 카드 PNG는 14일 동안 Actions artifact로만 보관합니다.
- 성공한 경우에만 `docs/` 팀 페이지를 `main`에 커밋합니다. Vercel이 이 저장소를 연결해 둔 경우 자동 배포됩니다.
- GitHub 러너 IP에서 DCInside 접근이 차단되면 우회하지 않고 즉시 실패하며, 내려받은 HTML과 로그만 artifact로 남깁니다.

## 현재 범위

이 버전은 **경기코드 1개를 넣으면 한 경기 전체 절차가 끝나는 로컬 실행판**입니다. 당일 모든 경기의 경기코드를 자동으로 찾고 팀별로 반복하는 일정 탐색 단계는, 이 실행판을 실제 경기일에 검증한 뒤 추가합니다.
