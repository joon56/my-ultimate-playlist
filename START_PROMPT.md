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
