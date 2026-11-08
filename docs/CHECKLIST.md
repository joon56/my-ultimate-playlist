# CHECKLIST — 할 일과 결정 대기

갱신 2026-11-08 밤(A가 ④ 추천안 승인, Phase 1 시작). 열린 항목만 둔다. 한 줄 = 누구 · 할 일/질문 → 추천. 근거는 '근거'를 펼친다.

- 답은 번호로 준다(예: "K-53 351.2 m"). Claude Code는 답을 받거나 해결·변경되면 항목을 지운다. 결정은 `DECISIONS.md`(새 번호는 D-42부터), 사실은 `DATA_FACTS.md`로 옮긴 뒤 지운다. 지운 번호는 다시 쓰지 않는다.
- '점검 #n'은 2026-11-07 문서 점검의 번호다. A = 팀장, B = 데이터, C = 곡.

## 오늘 할 것 (11/9 실험 1 시작 전)

- [ ] **K-59** (A) 팀 문서 [실험 1 프로토콜] 탭에 바뀐 절차를 넣고 B·C에게 알린다 → 이 저장소 PROTOCOL 2.1·2.2·2.5·2.8과 같게
  <details><summary>근거</summary>

  2026-11-08 승인: 폰은 가로·세로 중 하나로 고정(D-35), 매 회차 측정 구간 시작·끝 2초 멈춤(D-26), 출발점에서 기록 시작 → 바로 폰에서 음악 → 폰 넣고 그 자리에서 10초 서기 → 걷기 → 도착해 10초 서기 → 걷지 않고 기록 끝(D-36, D-03), G1 100걸음은 사전 점검 파일로(D-39). 걷는 사람은 저장소가 아니라 팀 문서를 본다.

  </details>
- [ ] **K-53** (A) 측정 구간 지도 거리(342.9 m)를 다시 잰다 → 사진 찍은 두 지점 사이를 실제로 걷는 길을 따라 지도앱으로
  <details><summary>근거</summary>

  리허설에서 GPS 점이 구간 시작점·끝점을 2–3 m 안으로 지났고, 그 사이 217 s 동안 GPS 경로는 274 m였다(코스 전체는 GPS와 지도가 2% 안으로 맞았다). 342.9 m면 그 구간만 1.58 m/s로 걸은 셈이라 코스 평균 1.26 m/s와 맞지 않는다(DATA_FACTS §10). 매 회차 구간 속도(D-26)가 이 거리로 계산된다.

  </details>
- [ ] **K-55** (A) 리허설에서 화면을 끈 채 곡이 순서대로 재생됐는지 알려 준다 → 센서에는 남지 않는다
- [ ] **K-15** (A) 기록지·프로토콜에 'MMDD는 한국 날짜로 쓰고, 내보낸 파일 이름(UTC)의 날짜를 베끼지 않는다'를 넣는다(D-27)
- [ ] **K-08** (B·C) 폰 OS를 알려 준다 → Android면 사전 점검 ① 파일을 먼저 보낸다(DATA_FACTS는 iOS만 확인)
- [ ] **K-01** (B·C) 폰 위치·방향(가로·세로)을 정해 15회 고정하고 `carry_position`과 기록지 첫 장에 적는다 → 허리 파우치 권장(A는 등 쪽 파우치·가로)
  <details><summary>근거</summary>

  충격·마찰 요구비는 몸통 장착이 전제다(SPEC §4.3). 바지 주머니였던 시범은 허벅지 움직임이 커서 자이로 중앙값이 파우치의 약 3배였다.

  </details>
- [ ] **K-02** (B·C) Sensor Logger 설정 → 가속도계·중력·자이로·위치·걸음 수(Uncalibrated 2개도), 100 Hz, 백그라운드·위치 권한, 배터리 최적화 제외, Zipped CSV
- [ ] **K-03** (B·C) 걸을 길(8분 이상)과 측정 구간(평지, 신호등 없이 200 m 이상)을 정한다 → 거리는 `section_distance_m`, 시작·끝 좌표는 `data/private/sections.csv`, 시작·끝 사진(PROTOCOL 2.2)
- [ ] **K-54** (B·C) 사전 점검 기록 두 개 → ① 리허설 10분(PROTOCOL 2.5 새 순서, 구간 2초 멈춤) ② 100걸음, 이름 `TEST_<사람>_<MMDD>_<번호>`
  <details><summary>근거</summary>

  ①로 OS·형식·끊김·음악 앱·구간 GPS를, ②로 걸음 검출을 확인한다(G1의 100걸음 ±2, D-39). ②는 기록 시작 → 폰 넣기 → 10초 서기 → 첫 발 디딤을 1로 세며 100걸음 → 10초 서기 → 기록 끝, manifest `hand_step_count = 100`. Pedometer는 직접 센 100걸음을 128로 세어(D-37) 대신 쓸 수 없다. 하지 않으면 G1(11/12)에서 처음 확인하고 문제가 있으면 그 회차를 다시 한다(PROTOCOL 2.8).

  </details>
- [ ] **K-09** (C) 실험 플레이리스트로 음악 앱 점검(화면 끈 채 셔플 없이 끝까지)과 곡 BPM 30초 박 세기 × 2 → `bpm_count_1`, `bpm_count_2`(PROTOCOL 2.8)
- [ ] **K-12** (C) `music_bpm.csv`의 `duration_s`(12+2곡)를 채우고, Cupid는 고른 버전을 `note`에 적는다 → 비어 있으면 곡 구간을 계산하지 않는다(점검 #24)
- [ ] **K-13** (각자) `participants.csv` → A는 나이·키·체중·폰 기종이 남았고, B·C는 전부(폰 기종은 기기 이름 말고)
- [ ] **K-14** (B) DECISIONS의 11/9 전 남은 항목 D-04·D-05·D-10·D-13을 확인한다 → 확인 전까지 기본값으로 진행(D-01·D-03·D-31은 11/8 결정)

## Phase 1 중 — Claude Code가 추천안으로 구현, 다르면 알려 주기

- [ ] **K-25** (A) QA의 실험 2·3 적용 검사를 표 기준으로 맞춘다 → E2 = Q01–Q03·Q09·Q13, E3 = Q01–Q03·Q09(점검 #1)
  <details><summary>근거</summary>

  세 곳이 다르다: QA_CHECKLIST §2 끝 문장 Q01–Q05·Q09·Q13 / 표의 대상(Q04·Q05는 E1 전용, Q13은 E1·E2) / G2 표 '실험 2 Q01–Q05'.

  </details>
- [ ] **K-28** (A) Q01의 T(시범·사전 점검) 필수 파일 → E1과 같게(Accelerometer·Location)(점검 #21)
- [ ] **K-29** (A) Q07의 '같은 구간' → Q06의 창이 있으면 그 창, 없으면 두 서 있기 사이(D-36). 창 끝은 Pedometer 갱신 시각에 맞추고, D-37이 승인되면 INFO(점검 #17)
- [ ] **K-30** (A) Q14의 폰 방향 û → 걷는 동안(유효 창) Gravity 방향의 중앙값. Q04는 Accelerometer 첫~끝(D-28)(점검 #18)
  <details><summary>근거</summary>

  시범에서 서 있을 때(폰을 든 상태)와 걷는 동안의 방향이 60–70° 달랐다. 사전 점검 세 파일의 걷는 동안 방향은 서로 0.9–4.3°였다.

  </details>
- [ ] **K-31** (A) 기록지 시계 시각(예: 08:47) → `exclusions.csv` t_s 변환 → `inspect`가 KST ↔ t_s 대응을 출력하고, `phone_touch`는 `start_s = end_s`를 허용(점검 #23)

## 문서 정리 — 승인하면 고침

- [ ] **K-26** (A) [확정]/[초안] 표시 충돌 세 곳을 정리할지(점검 #2)
  <details><summary>근거</summary>

  `pendulum.k_over_L`·`d_over_L`(params [확정] ↔ SPEC §4.4 [초안 D-06]), `stats.sd_ddof`(params [초안] ↔ SPEC §4.1·D-14 확정), `qa.pedometer_tol_pct`(params [초안] ↔ SPEC §5.4 '수용 기준은 확정').

  </details>
- [ ] **K-27** (A) D 번호가 없는 [초안] 키 12개를 D 하나로 등록할지(SPEC §0, 점검 #3)
  <details><summary>근거</summary>

  `qa.gap_warn_s`, `qa.gap_fail_s`, `qa.pedometer_tol_pct`, `qa.gps_accuracy_warn_m`, `qa.max_bad_interval_frac`, `qa.phone_tilt_warn_deg`, `exclude.phone_touch_pad_s`, `steps.detect_band_hz`, `speed.doppler_max_speed_accuracy_ms`, `speed.section_radius_m`, `speed.mismatch_tol_pct`, `exp2.pc_field_tol_spm`.

  </details>
- [ ] **K-32** (A) 열 이름의 m/s 접미사 `_ms`(밀리초와 겹침)를 `_mps`로 바꿀지 → Phase 2에서 결과 열을 쓰기 전에(SPEC §7 수정, 점검 #10)

## 실험 1 진행 중 (11/9–11/22)

- [ ] **K-33** (걷는 사람, 매회) PROTOCOL 2.5 새 순서로 걷고, 그날 안에 zip 업로드·앱에서 지우기, 기록지 한 줄 → `manifest.csv`, 폰을 만졌으면 시각 → `exclusions.csv` → 파일 이름 `E1_<사람>_<회차2자리>_<조건>_<MMDD>`(한국 날짜)
- [ ] **K-34** (셋, 11/12 G1) 1–2회차 파일 6개와 manifest 6줄

## 11/14(실험 2·3) 전

- [ ] **K-35** (A·B) H1-2 해석을 정한다(D-38의 선택지 세 가지) → 판정 기준([확정])은 Claude Code가 바꾸지 않는다
  <details><summary>근거</summary>

  사전 점검 메트로놈(100 BPM, 허리 파우치)에서 평균 케이던스는 박자와 0.2% 안이었지만 걸음마다 ±3% 안(S3)은 47–50%, ±5% 안은 79–81%였다. 80%가 ±3% 안에 들려면 걸음 간격 CV가 2.3% 이하여야 한다(지금 4.0–4.1%).

  </details>
- [ ] **K-36** (A) 실험 2 파일 구성 → 시행마다 파일 1개 추천(한 파일에 여러 시행이면 `t_in_sensor_s`·`t_out_sensor_s` 필수)(점검 #8)
  <details><summary>근거</summary>

  파일 이름 규칙 `E2_<사람>_<비율>_<반복>`은 시행 하나 기준이고, D-13 대안(걸음 열 가운데 75%)은 여러 시행이 든 파일에서 시행을 나누지 못한다.

  </details>
- [ ] **K-37** (A·B) 실험 2 템포 범위 밖 처리 → 실험 2용 걸음 간격 하한과 음원 범위 밖 규칙(점검 #7)
  <details><summary>근거</summary>

  현장 PC ≳ 123이면 165% 음원이 205 BPM이라 동조된 걸음 간격이 0.30 s(`steps.min_interval_s`)보다 짧아 이상 간격으로 빠진다. PC ≳ 129이면 165%에 215 BPM 이상이 필요한데 파일은 100–210이고, PC < 97.5이면 100% 음원(95 BPM)이 없다. 조회표(PROTOCOL 3.4)는 PC 100–125만 있다.

  </details>
- [ ] **K-38** (A·B) H3의 '처음 뛴 단계'를 영상(§5.7)과 센서 체공(§2) 중 무엇으로 볼지, `gait_video = mixed`·2회 판정이 갈릴 때·뛰다 다시 걸을 때(점검 #5)
- [ ] **K-39** (A) 실험 3 한 번에 흔드는 시간·주기 수 → 10주기 이상 추천(§5.8이 처음·끝 주기를 뺀다)(점검 #22)
- [ ] **K-40** (각자) `participants.csv`의 `leg_length_m`(대전자~바닥)

## Phase 2·G2(11/18) 전

- [ ] **K-41** (B) DECISIONS D-28·D-29·D-32·D-33·D-34·D-37을 검토한다 → 나머지 '열림'·'검증 후 확정'은 표대로
- [ ] **K-42** (A·B) '곡 BPM'에 쓸 열 → `bpm_public`(박 세기로 ±3 확인을 통과한 값)(점검 #13)
- [ ] **K-43** (B) S3 분모는 유효 간격 수로, `n_valid_steps` 정의, 곡 경계를 걸친 간격은 앞 걸음이 속한 곡으로(점검 #14)
- [ ] **K-44** (A·B) S3_double·super 표시가 구조적으로 0인 문제 → 이상 간격을 빼기 전 c_i로 셀지, 그대로 둘지(점검 #6)
  <details><summary>근거</summary>

  유효 간격이 0.30–1.50 s(40–200 spm)인데 곡 BPM 100–132의 두 배는 200–264 spm이라 BPM 100–103 말고는 나올 수 없다. §9 #11은 c = 240을 분모에 넣는다.

  </details>
- [ ] **K-45** (A·B) H2의 사람별 '지지' 기준(p값, 세 지표 모두인지, 변동성 방향)과 H4의 '실측 PC'(실험 1 / 현장)(점검 #15)
- [ ] **K-46** (B) 속도 분해의 Δ 기준점 → 무음 회차 평균 대비 추천(Δln v ≈ 0 표시 규칙도), μ_req의 창 폭과 수평 성분(점검 #16)
- [ ] **K-47** (A·B) 주머니를 쓰는 사람의 충격·μ_req 처리 → K-01에서 B·C도 파우치면 지운다(점검 #11)
- [ ] **K-48** (A·B) 무음이 3회 미만으로 끝나면 최종 결과에도 `pc_provisional`로 남길지(PROTOCOL 2.9, 점검 #20)
- [ ] **K-49** (C) 곡 사이 전환 시간을 집에서 잰다 → 짧은 곡 3개를 이어 틀고 1번 곡 시작~3번 곡 시작 스톱워치 시간에서 앱의 1·2번 곡 길이 합을 빼고 2로 나눔(점검 #24)
- [ ] **K-50** (A, 낮음) 입력·출력 이름 겹침(`participants.csv`, `exp3_swings.csv`), `hand_count` ↔ `hand_step_count`(점검 #12)

## 기타

- [ ] **K-51** (A) GitHub 저장소를 비공개로 바꾼 뒤 push 요청 → 2026-11-07 확인 때 공개(public), README·SPEC §11은 비공개만 허용
- [ ] **K-52** (A) `data/raw/`의 zip 4개를 읽기 전용으로 잠근다(README 2단계)

## 부록 A. Phase 1 계획 (2026-11-08 승인, 진행 중 — 끝나면 지운다)

범위 밖: 실험 2·3 파이프라인, 통계·판정, 웹. 단계마다 pytest 출력을 붙이고 작은 한국어 커밋을 한다. 목표 11/11(G1 전날). 확정된 선택: 합성 생성기는 `src/walkmusic/synthetic.py`, §9는 D-41 범위, 단위 판별은 D-30, 3.10은 `tomli`(D-40).

| # | 내용 | 완료 기준 | 테스트 |
|---|---|---|---|
| 0 | `.venv`, `pip install -e .[dev]`(numpy·pandas·scipy·matplotlib, pytest·ruff) | 설치 성공 | — |
| 1 | `pyproject.toml`(src 배치, ruff 설정), `src/walkmusic/{__init__,__main__,cli,config}.py`. config는 params.toml을 SPEC 키 이름 그대로 읽고, 없는 키는 KeyError | `python -m walkmusic --help` 동작, `ruff check .` 0건 | `test_config.py`: 문서에 나온 `섹션.키`가 모두 params.toml에 있는지 자동 대조, 타입 확인 |
| 2 | 합성 zip 생성기: DATA_FACTS 형식(z·y·x 열, 중력 제외 Accelerometer, Gravity 9.80665, g 단위 Uncalibrated, 좌표 0 근처의 1 Hz Location, 누적 Pedometer, 가짜 기기 이름·ID, 빈 Annotation, 기록 전 위치 점). 매개변수: 케이던스, 잡음·진폭, 폰 방향(세로·가로, D-35), 시작·끝 서 있기와 그 앞뒤 동작, 끊김, 시드. 정답 걸음 시각을 같이 돌려준다 | 같은 시드면 같은 바이트, 생성한 zip이 로더로 읽힘 | `test_synthetic.py` |
| 3 | `io_sensorlogger.py`와 `inspect`: 풀지 않고 읽기, 열 이름으로 읽기, t_s = (time − epoch) ÷ 1e9(D-28), KST 표시, Location t_s < 0·speed < 0 처리, 빈 파일·모르는 파일은 INFO(D-32), 기기 이름·ID는 읽자마자 버림 | 시범·사전 점검 zip의 `inspect` 출력이 DATA_FACTS §1–3·§10 수치와 같음 | 합성(열 순서 섞기, 끊김, 빈 파일), 실제 파일(있을 때만), 출력에 가짜 좌표·기기 이름이 없는지 |
| 4 | `units.py`: D-29·D-30 방식으로 단위·중력 포함·부호 판별. 실패하면 예외 → Q09 FAIL | 합성 4종 규약 × 세로·가로, 실제 4개 → m/s², 중력 제외, +1 | `test_units.py` |
| 5 | `metrics.py` 순수 함수로 §9 예제 수치(D-41)와 배정표 재현 | 모두 통과 | `test_spec_examples.py`, `test_assignment.py` |
| 6 | `steps.py`: `steps.signal`, 영위상 대역 통과, 최소 간격, 적응 문턱, 봉우리 보간, 걷기 묶음 판정(규칙성·높이, D-33), 출발·도착 = 시작·끝 서 있기(D-36) | 합성 1.5–2.5 Hz 케이던스 오차 ≤ 1%, 걸음 수 ±2, 서 있기 흔들림·폰 넣기·꺼내기 0걸음, ML 축 주 피크 = 걸음 주파수 절반. 실제: 100걸음 파일 100 ± 2, 메트로놈 100 BPM ± 1%, 시범 701–711 s 0걸음, 리허설 t_depart 29.9 ± 1 s·t_arrive 638.9 ± 1 s | `test_steps.py` |
| 7 | `qa.py`: `qa <zip>`, `--all`, `--gate G1`. Q01–Q15 → `qa_summary.csv`, `qa/<walk_id>.json`. 입력이 없으면 NA | 검사마다 PASS·비PASS 사례, Q15는 좌표를 심은 파일에서 FAIL, `qa --gate G1 --synthetic`이 합성 6회차로 표를 냄 | `test_qa.py` |
| 8 | 시범·사전 점검 파일 4개 QA 보고 + 걸음 검출 대 직접 센 값·Pedometer. DATA_FACTS §8·§10 갱신 | 보고 표 | 실제 실행 출력 첨부 |
| 9 | 전체 pytest + ruff, CLAUDE.md '지금 상태' 갱신 | 모두 통과 | 출력 첨부 |
