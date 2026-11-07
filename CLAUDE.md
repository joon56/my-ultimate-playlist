# CLAUDE.md — 워크 뮤직 분석 저장소

연세대 Healthcare Biomechanics 팀 프로젝트(A·B·C 3명)의 데이터 분석 저장소다. 주제는 「내 플레이리스트가 걸음을 바꾼다 — 음악 템포에 따른 보행 동조와 진자 역학」. 폰(Sensor Logger) 센서 데이터로 케이던스, 동조율, 속도, 충격, 체공, 진자 주기를 계산하고, 가설 1–4를 사람별로 판정하고, 논문과 발표용 표·그림을 만든다.
사용자는 팀장 A다. 한국어로 답한다. 일정: G1 11/12 · G2 11/18 · G3 11/24(데이터 동결) · G4 11/28 · 발표 11/30 · 논문 12/15.

## 먼저 읽을 것 (필요한 절만 읽는다)

- `docs/SPEC.md` — 정의, 처리 순서, 출력 파일, 테스트 수치(§9). 가장 중요하다.
- `docs/PROTOCOL.md` — 데이터를 어떻게 모았는지(해석에 필요하다)
- `docs/QA_CHECKLIST.md` — 품질 검사 Q01–Q15, 관문 G1–G3 기준
- `docs/DECISIONS.md` — 열린 결정과 변경 기록. 새 결정은 여기에 적는다
- `docs/DATA_FACTS.md` — 실제 파일에서 확인한 사실(Phase 0에서 채운다)
- `docs/CHECKLIST.md` — 열린 할 일과 결정 대기(K-xx). 사용자가 답하거나 해결·변경되면 그 항목을 지운다(결정은 DECISIONS.md, 사실은 DATA_FACTS.md로 옮긴 뒤)
- `data/README.md` — CSV 열 설명 · `config/params.toml` — 모든 문턱과 파라미터

## 어기면 안 되는 것

- IMPORTANT: `data/raw/`는 읽기 전용이다. zip은 `data/interim/`에 풀어서 쓴다. 원본을 고치거나 옮기거나 지우지 않는다.
- IMPORTANT: 위도·경도 값을 화면, 로그, 커밋, 그림, 문서에 쓰지 않는다. 계산에는 쓰되 결과에는 거리·속도·시각만 남긴다. 기기 이름도 적지 않는다.
- IMPORTANT: SPEC §4의 정의와 [확정] 값은 결과를 보기 전에 정해 둔 것이다. 결과가 가설에 맞게 나오도록 정의, 문턱, 제외 규칙을 바꾸지 않는다. 바꿔야 할 것 같으면 멈추고 사용자에게 묻고 `docs/DECISIONS.md`에 적는다.
- IMPORTANT: 숫자를 지어내지 않는다. 필요한 값이 비어 있으면 멈추고 묻는다. `data/music_bpm.csv`의 `duration_s`가 비어 있으면 곡 구간을 계산하지 말고 알린다. 센서 단위와 부호도 가정하지 말고 데이터로 판별한다(SPEC §5.2).
- 기호: T는 템포 비율(%)만, P는 다리 흔들림 주기(s)만, t는 시간, PC는 평소 케이던스다. 변수 이름은 풀어 쓴다(`tempo_ratio_pct`, `swing_period_s`). 케이던스 단위는 걸음/분(spm)이다.
- n=3이라 집단 검정(Wilcoxon, Friedman, ANOVA 등)을 쓰지 않는다. 사람별로 판정하고, 3명 중 2명(가설 4는 3명)이 같으면 '지지'다.
- 문턱과 파라미터는 `config/params.toml`에서 읽는다. 코드에 숫자를 박지 않는다. 값을 바꾸면 DECISIONS.md에 날짜와 이유를 적는다.
- 합성 데이터 결과는 `results_synthetic/`에만 쓰고 그림에 SYNTHETIC 표시를 넣는다. 실제 결과와 섞지 않는다.
- `docs/SPEC.md`와 `data/assignment.csv`는 사용자 승인 없이 고치지 않는다(배정표는 이미 걷기 전에 정해졌다).
- 웹/앱은 11/24 데이터 동결 뒤에 사용자가 요청할 때만 시작한다.

## 작업 방식

- 새 Phase나 큰 변경은 계획부터 보여주고 승인받은 뒤 시작한다(계획 모드를 써도 된다).
- 코드를 쓰면 테스트도 쓰고 `pytest`를 실제로 돌려 출력을 붙인다. 돌리지 않았으면 돌리지 않았다고 쓴다.
- 이상한 데이터나 모호한 명세는 조용히 고치지 말고 보고하거나 DECISIONS.md에 적는다.
- 커밋은 작게, 한국어 메시지로 한다. 원자료, 좌표 파일, 결과 그림은 커밋하지 않는다(.gitignore).
- 보고 순서: ① 확인한 사실 ② 만든 것 ③ 테스트 결과(출력 그대로) ④ 결정이 필요한 것 ⑤ 다음 단계.
- 대화를 요약(compact)할 때 남길 것: 현재 Phase와 남은 작업, DECISIONS의 열린 항목, DATA_FACTS 요약, 마지막 테스트 결과, 고친 파일 목록.

## 명령 (Phase 1에서 만든다)

- `pytest` · `ruff check .`
- `python -m walkmusic inspect <zip>` — 파일 구조와 시간·샘플링 요약(좌표 출력 없음)
- `python -m walkmusic qa <zip>` — 품질 검사 Q01–Q15
- `python -m walkmusic all` — 처리부터 표·그림까지 한 번에(같은 입력이면 같은 출력)

## 지금 상태

Phase 0 끝(2026-11-07, 시범 파일 `TEST_A_1107` 1개 기준: DATA_FACTS, DECISIONS D-27–D-34). Phase 1은 계획 승인 대기다(`docs/CHECKLIST.md` 부록 A). 11/8 사전 점검, 실험 1은 11/9부터, 실험 2·3은 11/14다.
