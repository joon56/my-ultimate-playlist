# START_PROMPT — Claude Code에 처음 붙여 넣을 프롬프트

사용법: 이 폴더를 Claude Code의 작업 폴더로 열고, 시범 측정 zip을 `data/raw/`에 넣은 뒤 아래 상자의 내용을 붙여 넣는다. 대괄호 `[...]` 안은 지우거나 알맞게 고쳐서 보낸다. 계획 모드로 시작해도 된다.

## 1. 첫 프롬프트

```text
이 작업 폴더(walk-music 저장소)에서 일해 줘. 먼저 CLAUDE.md를 읽고, 이어서 docs/SPEC.md, docs/PROTOCOL.md, docs/QA_CHECKLIST.md, docs/DECISIONS.md, data/README.md, config/params.toml을 읽어. 코드는 아직 쓰지 마.

[1단계 · 문서 점검]
문서끼리 어긋나거나, 모호하거나, 빠진 곳을 목록으로 보고해 줘. 고치지는 말고, DECISIONS.md에 적을 후보만 제안해 줘.

[2단계 · Phase 0: 시범 측정 데이터 사실 확인]
data/raw/ 안의 시범 측정 zip을 data/interim/TEST_A_1107/ 에 풀어서 확인해 줘. zip이 여러 개면 어느 것인지 나한테 물어봐. 코드 파일은 만들지 말고 일회용 스크립트(scratch)로 하고, 좌표 값은 출력하지 말고 기기 이름도 적지 마.
- 압축 파일 목록, 센서별 열 이름과 행 수
- 센서별 첫·마지막 time을 한국 시각(Asia/Seoul)으로, 기록 길이
- 샘플링 간격(중앙값, 5·95 백분위, 최대)과 1초 넘는 끊김의 개수와 위치
- Accelerometer가 중력을 포함하는지와 단위(g 또는 m/s²): 서 있을 때와 걷는 동안 크기의 중앙값을 근거로 보여 줘. Gravity와의 부호 관계도
- Gyroscope 값의 범위로 본 단위, Pedometer.csv의 유무와 형식(누적인지 구간 값인지)
- Location: 갱신 간격, speed 열의 범위와 단위 추정, speedAccuracy와 horizontalAccuracy 중앙값, 총 이동 거리(좌표 말고 거리만)
- Metadata.csv의 항목 이름(기기 이름 값은 쓰지 마), recording epoch time과 첫 샘플 time의 차이
- 가속도 크기로 걸음을 대략 세어 본 값과 Pedometer 걸음 수(일회용 계산, magnitude와 수직 성분 두 가지)
결과는 docs/DATA_FACTS.md 표에 채우고, SPEC의 가정과 다른 곳은 DECISIONS.md에 번호를 붙여 적어 줘.
시범 측정에 대해 내가 아는 내용: [없음 / 산책 약 ○분 / ○○걸음을 기록 시작 후 ○분 ○초부터 셌음 / 폰 위치 ○○]. 내가 모르는 건 추측하지 말고 물어봐.

[3단계 · Phase 1 계획]
Phase 0을 마치면 코드를 쓰기 전에 Phase 1 계획을 보여 주고 내 승인을 기다려 줘. 계획에는 다음을 넣어 줘: pyproject.toml과 src/walkmusic/ 뼈대, config 읽기, zip 불러오기(UTC에서 KST로, 공통 시간축), 단위·부호 판별, QA(Q01–Q15) 명령, 걸음 검출 초안과 합성 신호 테스트, SPEC §9 예제 수치 테스트, 합성 zip 생성기(tests/synthetic.py), 시범 파일의 QA 보고와 걸음 검출 대 Pedometer 비교. 항목마다 완료 기준과 테스트 방법을 적어 줘.

[하지 말 것]
웹/앱 만들기, 실험 2·3 구현, 통계와 가설 판정, 좌표 출력, SPEC 정의 수정, data/raw 수정.

[보고]
CLAUDE.md의 순서(① 확인한 사실 ② 만든 것 ③ 테스트 결과 ④ 결정이 필요한 것 ⑤ 다음 단계)로 하고, 커밋은 작게 한국어 메시지로 해 줘.
```

## 2. Phase 1 계획을 승인할 때

```text
계획 승인한다. 단계 순서대로 진행하고, 단계가 끝날 때마다 pytest 출력을 붙여서 보고해 줘. DECISIONS의 D-01, D-02, D-05에 영향을 주는 발견이 있으면 바로 알려 줘.
```

## 3. 실제 회차 데이터가 들어왔을 때

```text
data/raw/ 에 새 zip이 들어왔고 data/manifest.csv에 해당 줄을 채웠어. qa를 돌려서 Q01–Q15 결과를 보고해 줘. WARN과 FAIL만 사유와 함께 표로 줘.
```

## 4. 질문 세션을 따로 열 때

코드 작업을 하는 메인 세션과 같은 `walk-music` 폴더에서 새 Claude Code 세션을 열고 붙여 넣는다. 질문 세션은 파일을 읽기만 한다(두 세션이 같은 파일을 고치다 부딪치지 않게). 질문 세션에서 정한 것은 끝에 받은 요약을 메인 세션에 붙여 넣어 체크리스트와 DECISIONS에 반영한다.

```text
이 작업 폴더(walk-music 저장소)에서 내 질문에 답하는 세션이야. 코드 작업은 다른 세션(메인)이 같은 폴더에서 하고 있으니, 여기서는 파일을 읽기만 하고 고치거나 커밋하지 마.

먼저 CLAUDE.md, docs/CHECKLIST.md(열린 할 일·결정 K-xx, 부록 A는 Phase 1 계획), docs/DATA_FACTS.md(11/7 시범 파일에서 확인한 사실), docs/DECISIONS.md(D-01–D-34)를 읽어. 질문에 따라 docs/SPEC.md, docs/PROTOCOL.md, docs/QA_CHECKLIST.md, data/README.md, config/params.toml에서 필요한 절만 읽어.

지금 상태: Phase 0 끝(시범 파일 TEST_A_1107 하나, iOS, 바지 앞주머니). Phase 1은 계획 승인 대기라 분석 코드는 아직 없다. 사전 점검은 11/8, 실험 1은 11/9부터, 실험 2·3은 11/14다.

답하는 방식:
- 한국어로 짧게 답하고, 근거를 파일과 절로 대 줘(예: SPEC §5.2, DATA_FACTS §4, D-30, K-21).
- 문서에 있는 사실, 데이터로 계산한 값, 네 의견을 나눠서 말해 줘. 모르면 모른다고 하고 숫자를 지어내지 마.
- 선택지가 있으면 추천 하나와 이유를 말해 줘. 결정은 내가 한다.
- SPEC의 정의와 [확정] 값은 결과를 보기 전에 정한 것이다. 바꾸자는 결론을 내지 말고, 문제가 보이면 영향과 선택지만 설명해 줘.
- 데이터를 봐야 답할 수 있으면 data/interim/TEST_A_1107/의 풀린 CSV를 저장소 밖 임시 폴더의 일회용 스크립트로 읽어(numpy·pandas·scipy가 없으면 임시 venv에 설치하고 python -I로 실행). 위도·경도 값, 기기 이름, device id는 출력하지 말고 거리·속도·시각·개수만 써. data/raw/는 건드리지 마.

하지 말 것: 파일 수정·커밋·push, 저장소 안 코드 작성, 웹/앱, 실제 데이터로 통계·가설 판정, 좌표 출력.

내가 "정리해 줘"라고 하면 메인 세션에 붙여 넣을 요약을 만들어 줘: (1) 내가 정한 것(K-xx 번호와 답) (2) 새로 생긴 질문이나 할 일 (3) DECISIONS·DATA_FACTS에 옮길 후보.
```
