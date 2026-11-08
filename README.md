# 수출 잠정치 대시보드 + 텔레그램 알림

관세청 Open API(공공데이터포털)로 **10일 단위 수출 잠정치**와 **국가별·품목별 월 실적**을 모아
전년동기대비(최근 3년)·전월동기대비(최근 12개월) 추이를 대시보드와 텔레그램으로 보여줍니다.

| 데이터 | API | 주기 |
|---|---|---|
| 전체 + 10개국 수출 (1~10일·1~20일·월 전체) | 수출 주요국가별 10일 단위 잠정치 | 11일·21일·익월 1일 |
| 국가별 수출·수입 (월 확정) | 국가별 수출입실적 | 매월 15일경 |
| 16개 주요 품목 × 국가 (월 확정) | 품목별 국가별 수출입실적 | 매월 15일경 |

## 1. 로컬 실행

```powershell
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
copy .env.example .env      # DATA_GO_KR_KEY 등 입력
.venv\Scripts\python scripts\probe.py          # API 응답 구조 확인 (최초 1회)
.venv\Scripts\python -m tradestat backfill     # 과거 데이터 수집 (품목은 오래 걸림)
.venv\Scripts\python -m tradestat notify --dry-run   # 텔레그램 메시지 미리보기
.venv\Scripts\python -m http.server 8000 -d docs     # http://localhost:8000
```

품목 백필은 호출 수가 많아(품목 HS 32개 × 국가 10개 × 4년) 나눠서 실행할 수 있습니다:
`python -m tradestat backfill --only item --countries ALL,US,CN`

## 2. 텔레그램 봇 만들기

1. 텔레그램에서 **@BotFather** → `/newbot` → 이름 입력 → 받은 **토큰**을 `TELEGRAM_BOT_TOKEN` 에
2. 만든 봇과 대화방을 열고 아무 메시지나 전송
3. 브라우저에서 `https://api.telegram.org/bot<토큰>/getUpdates` 열기 → `"chat":{"id": 123456789` 숫자를 `TELEGRAM_CHAT_ID` 에
   (그룹방으로 받으려면 봇을 그룹에 초대 후 같은 방법, id는 `-100…` 형태)

## 3. GitHub 자동화 (Actions + Pages)

1. GitHub에 새 저장소(공개 권장 — 무료 Pages) 생성 후 이 폴더를 push
2. **Settings → Secrets and variables → Actions**
   - Secrets: `DATA_GO_KR_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`
   - Variables: `DASHBOARD_URL` = `https://<아이디>.github.io/<저장소>/`
3. **Settings → Pages → Source: GitHub Actions**
4. 초기 데이터는 저장소에 포함되어 있으므로 **Actions → update → Run workflow** (mode: `update`) 로 배포 확인 — 이후는 자동

자동 실행: 매월 1~3·11~13·21~23일 KST 10시/15시, 15~18일 KST 10시. 새 구간이 나왔을 때만 알림이 갑니다.

## 구성

```
config/settings.yaml      API 주소, 국가, 품목(HS코드 매핑), 알림 임계값  ← 품목 추가/수정은 여기
config/workdays_override.yaml  임시공휴일 등 조업일수 예외
tradestat/                수집(fetch) · 지표(metrics) · 조업일수(workdays) · 차트/알림(charts, notify)
docs/                     대시보드 (GitHub Pages), docs/data/metrics.json 자동 생성
data/*.csv                수집 데이터 (Actions가 커밋)
```

## 지표 정의

- **전년동기대비**: 같은 월·같은 10일 구간(예: 1~20일)의 전년 값 대비
- **전월동기대비**: 전월 같은 구간 대비
- **일평균**: 금액 ÷ 조업일수(평일 1, 토요일 0.5, 일요일·공휴일 0). 명절·주말 수 차이로 인한 왜곡 보정
- **기여도**: (국가 증감액) ÷ (전년 동기 전체 수출) × 100, 단위 %p
- **품목**: 산업부 주력품목을 HS코드로 근사한 분류 → 공식 발표치와 다를 수 있음
