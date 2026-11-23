# CLAUDE.md — 워크 뮤직 분석 저장소

연세대 Healthcare Biomechanics 팀 프로젝트(A·B·C 3명)의 데이터 분석 저장소다. 주제는 「내 플레이리스트가 걸음을 바꾼다 — 음악 템포에 따른 보행 동조와 진자 역학」. 폰(Sensor Logger) 센서 데이터로 케이던스, 동조율, 속도, 충격, 체공, 점프, 다리 강성, 진자 주기(곧은·굽힌 다리)를 계산하고, 가설 1–4를 사람별로 판정하고, 측정 검증표·처방 범위와 논문·발표용 표·그림을 만든다.
사용자는 팀장 A다. 한국어로 답한다. 일정: G1 11/12 · G2 11/18 · G3 11/24(데이터 동결) · G4 11/28 · 발표 11/30 · 논문 12/15.

## 먼저 읽을 것 (필요한 절만 읽는다)

- `docs/SPEC.md` — 정의, 처리 순서, 출력 파일, 테스트 수치(§9). 가장 중요하다.
- `docs/PROTOCOL.md` — 데이터를 어떻게 모았는지(해석에 필요하다)
- `docs/QA_CHECKLIST.md` — 품질 검사 Q01–Q17, 관문 G1–G3 기준
- `docs/DECISIONS.md` — 열린 결정과 변경 기록. 새 결정은 여기에 적는다
- `docs/DATA_FACTS.md` — 실제 파일과 결과에서 확인한 사실(§0–§23). 새 사실은 새 절로 더하고, 결과가 바뀌면 전후 값을 적는다
- `docs/CHECKLIST.md` — 열린 할 일과 결정 대기(K-xx). 사용자가 답하거나 해결·변경되면 그 항목을 지운다(결정은 DECISIONS.md, 사실은 DATA_FACTS.md로 옮긴 뒤)
- `docs/HANDCALC.md` — 손계산 노트(교안 예제와 같은 계산을 우리 데이터로). 숫자는 SPEC §9 테스트와 같다
- `docs/총정리본.md` — 프로젝트 총정리본(결과, 실측으로 다시 푼 손계산, 교안 2–12주차 연결 55짝, 가정 예시). 검산표 `docs/총정리본_검산표.csv`는 `tools/handcalc_check.py`가 만든다. 본문 빌더는 `.handoff/summary/`에 있다
- `docs/CHANGES_1108.md`, `docs/CHANGES_1109.md` — 규칙이 바뀐 날의 기록(무엇이 왜 바뀌었는지)
- `data/README.md` — CSV 열 설명 · `config/params.toml` — 모든 문턱과 파라미터
- `tools/video/README.md` — 영상 판독 도구(패키지 밖, `python -I tools/video/...`). 영상에서 읽은 값은 `data/video_exp2.csv`·`video_checks.csv`·`video_markers.csv`에 둔다(D-83·D-84·D-86·D-87)
- `.handoff/`(git 제외) — 작업 메모, 문서 편집 스크립트, 프로젝트 지도(HTML 아티팩트) 생성기 `.handoff/map/`. 결과가 바뀌면 지도를 다시 빌드해 같은 주소에 올린다

## 어기면 안 되는 것

- IMPORTANT: `data/raw/`는 읽기 전용이다. zip은 `data/interim/`에 풀어서 쓴다. 원본을 고치거나 옮기거나 지우지 않는다.
- IMPORTANT: 위도·경도 값을 화면, 로그, 커밋, 그림, 문서에 쓰지 않는다. 계산에는 쓰되 결과에는 거리·속도·시각만 남긴다. 기기 이름도 적지 않는다.
- IMPORTANT: SPEC §4의 정의와 [확정] 값은 결과를 보기 전에 정해 둔 것이다. 결과가 가설에 맞게 나오도록 정의, 문턱, 제외 규칙을 바꾸지 않는다. 바꿔야 할 것 같으면 멈추고 사용자에게 묻고 `docs/DECISIONS.md`에 적는다.
- IMPORTANT: 분석 고정(SPEC §6 '분석 고정', DECISIONS D-35). git 태그 `analysis-freeze-g2`를 붙이기 전에는 실제 음악 회차로 가설 결과(T·ΔC%·R·S3 요약, 상관, `hypotheses.csv`, 그림 2·3)를 계산하거나 보여 주지 않는다. 걸음 검출·QA 조정은 무음·사전 점검(TEST)·합성 데이터로 한다. 태그는 사용자 승인 후에 붙이고, 태그 뒤에 정의·문턱·제외 규칙을 바꾸면 DECISIONS에 적고 바꾸기 전후 결과를 모두 보고한다.
- IMPORTANT: 숫자를 지어내지 않는다. 필요한 값이 비어 있으면 멈추고 묻는다. `data/music_bpm.csv`의 `duration_s`가 비어 있으면 곡 구간을 계산하지 말고 알린다. 센서 단위와 부호도 가정하지 말고 데이터로 판별한다(SPEC §5.2).
- 기호: T는 템포 비율(%)만, P는 다리 흔들림 주기(s)만, t는 시간, PC는 평소 케이던스다. 변수 이름은 풀어 쓴다(`tempo_ratio_pct`, `swing_period_s`). 케이던스 단위는 걸음/분(spm)이다.
- n=3이라 집단 검정(Wilcoxon, Friedman, ANOVA 등)을 쓰지 않는다. 사람별로 판정한다. 미리 정한 집단 규칙은 3명 중 2명 이상(가설 4는 모두)이고, 실험 2·3은 A·B 2명이 해서 2명 모두여야 한다(D-79).
- 보고·발표·논문·지도에서는 가설을 '지지/지지 안 됨'으로 맺지 않고 기준을 채운 사람 수와 누구인지를 적는다(예: '3명 중 1명, A'). 집단 규칙과 그 결과는 표 주석에 한 번만 적는다. 사람별 기준·문턱과 `hypotheses*.csv`는 그대로다(D-85). 가설 2 충격의 B는 '관계 없음'으로 적고 사람 수에 넣지 않는다(D-94).
- 문턱과 파라미터는 `config/params.toml`에서 읽는다. 코드에 숫자를 박지 않는다. 값을 바꾸면 DECISIONS.md에 날짜와 이유를 적는다.
- 합성 데이터 결과는 `results_synthetic/`에만 쓰고 그림에 SYNTHETIC 표시를 넣는다. 실제 결과와 섞지 않는다.
- `docs/SPEC.md`와 `data/assignment.csv`는 사용자 승인 없이 고치지 않는다(배정표는 이미 걷기 전에 정해졌다).
- 웹/앱은 11/24 데이터 동결 뒤에 사용자가 요청할 때만 시작한다.

## 작업 방식

- 새 Phase나 큰 변경은 계획부터 보여주고 승인받은 뒤 시작한다(계획 모드를 써도 된다).
- 코드를 쓰면 테스트도 쓰고 `pytest`를 실제로 돌려 출력을 붙인다. 돌리지 않았으면 돌리지 않았다고 쓴다.
- 이상한 데이터나 모호한 명세는 조용히 고치지 말고 보고하거나 DECISIONS.md에 적는다.
- 커밋은 작게, 한국어 메시지로 한다. 원자료, 좌표 파일, 영상, 결과 그림은 커밋하지 않는다(.gitignore). 저장소가 공개라(D-64) 커밋·푸시 전에 좌표·기기 이름·몸 치수가 새로 들어가지 않았는지 본다.
- 분석 고정 뒤에 입력을 바로잡으면(예: D-72, D-92·D-93) 결과를 다시 돌리고 바꾸기 전후 값을 DECISIONS 변경 기록과 DATA_FACTS에 함께 적는다(D-35).
- 보고 순서: ① 확인한 사실 ② 만든 것 ③ 테스트 결과(출력 그대로) ④ 결정이 필요한 것 ⑤ 다음 단계.
- 대화를 요약(compact)할 때 남길 것: 현재 Phase와 남은 작업, DECISIONS의 열린 항목, DATA_FACTS 요약, 마지막 테스트 결과, 고친 파일 목록.

## 명령 (`pip install -e .[dev]` 뒤, Windows는 `.venv\Scripts\python`)

- `pytest` · `ruff check .`
- `python -m walkmusic inspect <zip>` — 파일 구조와 시간·샘플링 요약(좌표 출력 없음)
- `python -m walkmusic qa <zip>` · `qa --all` · `qa --gate G1 [--synthetic]` · `qa --links` — 실험 1·시범 기록의 품질 검사 Q01–Q15, 관문 표(G1만). 실험 2·3의 파일 검사와 점프 개수(Q17)는 `exp23`이 `qa_exp23.csv`에 낸다. 걷는 동안 평균 수직 가속도(Q16)는 검사 줄 없이 `walks.csv`의 `mean_av_g`와 검증표로 본다. `--links`는 `data/raw/<사람>/`의 zip을 기록지 시각과 맞춘 연결 제안만 낸다(`results/zip_links.csv`, D-27)
- `python -m walkmusic process` · `stats` · `all [--synthetic]` — 실험 1의 곡 구간·회차·사람 표, 가설 판정·처방 하한·시나리오 신호. 실제 데이터는 분석 고정 태그가 있어야 돈다(D-35, `--allow-unfrozen`은 기록을 남기고 예외로)
- `python -m walkmusic exp23 [--synthetic]` · `exp23 --links [--date YYYY-MM-DD]` — 실험 2·3 표(exp2_stages·exp2_summary·jumps·exp3_swings 등), 가설 1-2·3·4 판정, 현장 당일 점검 표. `--links`는 기록 순서로 zip 연결 제안만(D-55, D-73)
- `python -m walkmusic validation` · `sensitivity` · `figures` `[--synthetic]` — 위 명령들이 만든 결과 표를 읽어 측정 검증표(`validation.csv`, D-38), 민감도 표(`sensitivity.csv`, D-89), 핵심 그림 4장과 그려진 값(`figures/*.png`·`.json`, D-90)을 만든다. 순서: `all` → `exp23` → 이 셋 (`all`은 `prescription.csv`를 다시 쓰므로 그 뒤에 `exp23`을 돌려야 상한이 채워진다)
- `python -m walkmusic freeze --version 1.0` — 결과 표를 `results/frozen/v1.0/`에 동결(D-91). A가 말할 때만 돌린다. 같은 판은 덮어쓰지 않는다
- `python tools/handcalc_check.py` — 결과 표를 읽어 손계산을 식 그대로 다시 풀고 코드 값·검산 기준값과 견준 검산표(`docs/총정리본_검산표.csv`)를 쓴다. 결과 표가 바뀌면 다시 돌리고 `.handoff/summary/build_summary.py`로 총정리본을 다시 만든다

## 지금 상태 (2026-11-23)

- **Phase:** 0–3 끝. Phase 4(전체 표·그림, 동결)는 핵심 그림 4장·측정 검증표·민감도·총정리본(11/23, 동결 전 값)까지 했고 데이터 동결(v1.0)이 남았다. 동결은 A가 '동결해'라고 할 때만 `freeze --version 1.0`을 돌린다(D-91). Phase 5(웹/앱)는 동결 뒤 A가 요청할 때 시작한다.
- **데이터:** 실험 1은 끝났다: A 음악 8·무음 2회, B 음악 12·무음 3회(하루 저녁에 이어서, D-66), C 음악 4·무음 1회. 실험 2·3은 11/21에 A·B가 했다(C 불참, D-79). 분석 고정 태그 `analysis-freeze-g2`는 붙어 있다.
- **결과(기준을 채운 사람 수):** 가설 1은 3명 중 1명(A), 1-2는 2명 중 0명, 2는 충격 3명 중 1명(A. B는 '관계 없음', C는 반대 방향)·속도와 보폭 판정한 2명 중 1명(A)·변동성 2명 중 1명(B), 3은 2명 중 1명(A), 4는 2명 중 2명. 집단 규칙에 닿은 것으로 적는 것은 가설 4다. `hypotheses.csv`에는 규칙(ρ > 0)대로 B의 충격도 지지로 남아 ALL이 2명이다: B의 ρ가 +0.06(p 0.71)으로 0에 가깝고 곡 순서 가정에 따라 부호가 바뀌어(D-92·D-93) 보고에서는 '관계 없음'으로 적는다(D-94). 처방 범위는 A 하한 102.9%(일상 PC 대비, BPM 102.6)·상한 104.3%(실험 2 현장 PC 대비, BPM 105.0), B 하한 105.1%(일상 PC 대비, BPM 103.0, 상한 없음), C 없음. A의 두 값은 기준 PC가 달라 '102.9–104.3%'처럼 한 기준의 범위로 쓰지 않고 기준을 밝히거나 BPM으로 쓴다. 이 줄은 요약이고 숫자의 기준은 `results/` 표다. 값과 근거는 DATA_FACTS §18–§24, 결정은 DECISIONS D-72–D-94.
- **코드에 아직 없는 것:** 그림 3a·4·5·8·9, 논문 표 1–4, `qa --gate G2·G3`, 영상 시각을 센서 시각으로 옮기는 싱크 점프 보완(K-81: 지금 실험 2 분석 창은 걸음 열의 가운데 75%다).
- **열린 일(`docs/CHECKLIST.md`):** K-88 검증표·민감도·그림·동결 세부 확인, K-87 A 보강 측정(선택, D-88), K-84 다리 길이 다시 재기, K-69 종료 설문, K-63 C 값 공개 동의, K-12·K-13·K-54 남은 입력.
- **마지막 확인(2026-11-23):** `pytest` 242개 통과, `ruff check .` 통과. 검산표는 899줄이고 코드 값과 견준 307개가 모두 일치했다.
