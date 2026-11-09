# QA_CHECKLIST — 품질 검사와 관문 기준

작성 2026-11-07, 2026-11-08 수정(11/8 프로토콜 수정판 반영), 2026-11-09 수정(Q16·Q17, 점프 기록의 적용 범위, 관문 표에 결과 전 기준·분석 고정·측정 검증). 숫자는 모두 `config/params.toml`의 키다. 이 문서의 값과 params.toml이 다르면 params.toml이 맞다(그리고 이 문서를 고친다).

## 1. 쓰는 법

- `python -m walkmusic qa <zip>`은 회차 하나에, `qa --all`은 `manifest.csv`의 모든 회차에 Q01–Q14와 Q16·Q17(대상이 맞는 것만)을 돌리고 `results/qa_summary.csv`와 `results/qa/<walk_id>.json`을 쓴다. Q15는 전체에 한 번 돈다.
- 결과 상태: **PASS** · **WARN**(쓸 수 있지만 사람이 본다) · **FAIL**(그 회차를 이 용도로 쓸 수 없다) · **NA**(검사할 입력이 없다) · **INFO**(참고).
- 코드는 FAIL이어도 파일을 지우거나 분석에서 자동으로 빼지 않는다. 빼는 것은 사람이 `manifest.csv`의 `status`로 정한다.
- 좌표(위도·경도)는 검사 계산에만 쓰고 보고에는 거리·시각·정확도만 쓴다.
- 임계값에 걸리면 어느 값이 얼마였는지(값과 문턱)를 같이 적는다.

## 2. 회차 검사 Q01–Q17

적용 대상: **E1** 실험 1, **E2** 실험 2, **E3** 실험 3, **T** 시범 측정.

| ID | 검사 | 방법 | PASS | 아니면 | 키 | 대상 |
|---|---|---|---|---|---|---|
| Q01 | 필수 파일 | zip 안의 파일 목록 | E1·T: Accelerometer·Location 있음 / E2: Accelerometer 있음 / E3: Gyroscope 있음 | 필수가 없으면 FAIL. Gravity·Gyroscope·Metadata가 없으면 WARN. Pedometer와 보정 안 한 가속도계·자이로(Uncalibrated, 11/8부터 켬)가 없으면 INFO. 그 밖의 파일과 빈 Annotation은 목록만(D-47) | — | 모두 |
| Q02 | 샘플링 속도 | Accelerometer의 `time` 간격 중앙값으로 계산한 fs | fs가 `qa.min_fs_hz`(50) 이상 | 50 미만이면 FAIL. 50 이상 100 미만이면 PASS이고 INFO로 '목표(`qa.target_fs_hz`)보다 낮음' | `qa.min_fs_hz`, `qa.target_fs_hz` | 모두 |
| Q03 | 끊김 | Accelerometer의 연속 샘플 간격 | `qa.gap_warn_s`(0.25 s)보다 긴 간격 없음 | 있으면 WARN(개수와 위치). 걷는 동안 `qa.gap_fail_s`(1.0 s)보다 긴 간격이 있으면 FAIL | `qa.gap_warn_s`, `qa.gap_fail_s` | 모두 |
| Q04 | 기록 길이 | 센서 첫~마지막 `time` | E1: `qa.min_walk_duration_s`(480 s) 이상 | E1에서 짧으면 FAIL. 다른 대상은 NA(값만 보고) | `qa.min_walk_duration_s` | E1 |
| Q05 | 출발 전·도착 후 서 있기 | 출발 직전(첫 지속 보행 앞)과 도착 직후(마지막 지속 보행 뒤)의 서 있기를 1 s 움직임으로 찾는다: 움직임이 걷는 동안 중앙값의 `exclude.stand_motion_frac` 미만인 구간이 `exclude.stand_min_s` 이상, 기록 처음·끝 `exclude.stand_search_s` 안. 기록 맨 앞·맨 뒤의 폰 만지는 동작은 보지 않는다(SPEC §5.2, D-29) | 두 서 있기를 모두 찾음(프로토콜은 각 `qa.standing_check_s` 10 s) | 못 찾으면 WARN(서 있은 시간이 모자라거나 움직인 신호) | `exclude.stand_min_s`, `exclude.stand_motion_frac`, `exclude.stand_search_s`, `qa.standing_check_s` | E1 |
| Q06 | 직접 센 걸음 수 | manifest `hand_step_count`와 검출 걸음 수(`hand_step_note`에 `start=MM:SS end=MM:SS`가 있으면 그 창, 없으면 출발 전·도착 후 서 있기 사이(D-29), 서 있기를 못 찾으면 지속 보행 전체). 사전 점검의 100걸음 기록(`steps100`)은 `hand_step_count=100`이다. 지속 보행 전체로 세면 폰 넣기·꺼내기 동작까지 들어간다(DATA_FACTS §10) | 차이가 `qa.hand_count_tol_steps`(2걸음) 이하 | 크면 FAIL. 직접 센 값이 없으면 NA | `qa.hand_count_tol_steps` | E1, T |
| Q07 | Pedometer 참고 | Q06의 창 안 첫·마지막 Pedometer 갱신 사이 증가량과 같은 사이 검출 걸음 수(D-63) | 상대 차이가 `qa.pedometer_tol_pct`(3%) 이하 | 크면 INFO(값만 보고한다. 11/8 사전 점검에서 앱 걸음 수가 직접 센 100걸음을 128로 세었으므로 기준이 아니다, DECISIONS D-30). 파일이 없으면 NA | `qa.pedometer_tol_pct` | E1, T |
| Q08 | GPS | (a) 측정 구간 GPS 거리와 `section_distance_m`의 상대 차이 (b) `horizontalAccuracy` 중앙값 | (a) `qa.gps_distance_tol_pct`(5%) 이하 (b) `qa.gps_accuracy_warn_m`(20 m) 이하 | 아니면 WARN, (a)는 SPEC §5.5(e)의 대안을 쓴다. `sections.csv`가 없으면 (a)는 NA | `qa.gps_distance_tol_pct`, `qa.gps_accuracy_warn_m` | E1, T |
| Q09 | 단위·중력 판별 | SPEC §5.2 | 단위와 중력 포함 여부가 판별됨(중력 제외 신호이면 합성 부호도) | 판별 못 하면 FAIL(멈추고 보고). 같은 사람의 다른 회차와 다르면 WARN | — | 모두 |
| Q10 | zip ↔ manifest 연결 | zip의 기록 시작 시각(UTC → Asia/Seoul)이 같은 사람 manifest 줄의 `date`·`start_time`과 `manifest.start_time_tol_s` 이내이고 일대일. `walk_id`가 SPEC §3.4 규칙대로 만들어짐 | 모두 맞음 | 연결이 없거나 둘 이상이거나 어긋나면 FAIL(T는 `start_time`이 비어 있으면 NA로 두고 채우도록 보고) | `manifest.start_time_tol_s` | E1, T |
| Q11 | 배정표 일치 | manifest의 (사람, 회차)의 `condition`, `start_song`이 `assignment.csv`와 같음. 다시 한 회차(16 이상)는 `redo_of` 회차의 배정과 비교 | 같음 | 다르면 FAIL | — | E1 |
| Q12 | 곡 타임라인 | 음악 회차에 곡 순서(`songs_played` 또는 `start_song`), 곡 길이(`duration_s`), 오프셋이 모두 있음 | 계산 가능 | `duration_s`가 비면 FAIL(멈추고 C에게 채우도록 보고) | `music.default_offset_s` | E1 |
| Q13 | 유효 걸음 | (a) 곡 구간별 유효 걸음 수 (b) 이상 간격 비율 | (a) `qa.min_valid_steps_per_segment`(30) 이상 (b) `qa.max_bad_interval_frac`(5%) 이하 | 아니면 WARN. (a)는 그 구간에 `flags=few_steps` | `qa.min_valid_steps_per_segment`, `qa.max_bad_interval_frac` | E1, E2 |
| Q14 | 폰 방향 일관성 | 같은 사람 회차마다 걷는 동안 Gravity의 중앙 방향 û(폰 좌표계)를 구해, 그 사람의 중앙 방향과의 각도 차이(회차가 3개 이상일 때, D-63) | 중앙 방향과 `qa.phone_tilt_warn_deg`(30°) 이하 | 크면 WARN(폰 위치가 바뀐 신호). 회차가 모자라면 NA | `qa.phone_tilt_warn_deg` | E1 |
| Q15 | 결과에 좌표 없음 | `results/` 아래 모든 CSV·JSON·PNG 메타와 로그에서 위도·경도 열과 값 | 없음 | 있으면 FAIL(전체 실패로 보고) | — | 전체 |
| Q16 | 걷는 동안 평균 수직 가속도 | 유효 창 안 a_v,total의 평균(SPEC §4.3의 ā_v). 등속 보행이면 1 g | 값만 보고 | 항상 INFO(값과 같은 사람 다른 회차의 범위). 측정 검증표(SPEC §5.10)에 쓴다 | — | E1 |
| Q17 | 점프 개수 | 점프 기록(`E2_*_J_*`)에서 체공이 `jump.min_flight_s` 이상인 이벤트 수 | `jump.n_jumps`(3)개 | 다르면 WARN(개수와 체공 시간들). 0개면 FAIL | `jump.min_flight_s`, `jump.n_jumps` | E2(점프) |

실험 2·3의 추가 확인은 SPEC §5.7·§5.8에 있다. 여기서는 실험 2에 Q01–Q03·Q09·Q13, 실험 3에 Q01–Q03·Q09가 적용된다(D-63).

점프 기록(`E2_*_J_*`)에는 Q01–Q03, Q09, Q17을 적용한다.

사전 점검 기록(`T`, 11/8)에는 `steps100`에 Q01–Q03, Q06, Q09를, `rehearsal`에 Q01–Q05, Q08, Q09를 적용한다. 나머지는 NA다.

## 3. 관문 기준과 명령

`python -m walkmusic qa --gate G1|G2|G3`은 아래 표를 사람·항목별로 채워 보여 준다. 사람이 판단할 항목은 'NA(사람)'으로 둔다.

### G1 · 11/12 첫 데이터

| 항목 | 기준 | 확인 방법 |
|---|---|---|
| 첫 데이터 | 셋 다 1–2회차 파일이 올라옴(6개) | manifest에 6줄과 zip 6개 |
| 백그라운드 기록 | 화면을 끈 채 기록이 끊기지 않음 | Q03, Q04 PASS |
| 100걸음 검증 | ±2, 사람마다 사전 점검의 100걸음 기록(`steps100`)으로 판정 | 그 기록의 Q06 PASS |
| GPS | 측정 구간 GPS 거리와 지도 거리 차 5% 이내 | Q08(a) PASS |
| 기타 | zip↔manifest 연결·배정표 일치, 단위 판별 | Q10, Q11, Q09 PASS |
| 결과 전 기준 | 실질적 변화 기준·신뢰구간 방법·분석 고정 시점·처방 범위(DECISIONS D-33–D-36)가 정해짐 | DECISIONS.md에서 네 항목의 상태가 '확정'('NA(사람)') |

통과 못 하면: 폰 위치나 앱 설정을 고치고 그 사람의 1–2회차를 맨 뒤에 다시 한다.

### G2 · 11/18 중간 판단

| 항목 | 기준 | 확인 방법 |
|---|---|---|
| 진행 | 1인 7회 이상 | 사람마다 FAIL이 없는 회차 수 |
| 분석 고정 | 가설 결과를 계산하기 전에 git 태그 `analysis-freeze-g2` | `git tag -l`, `run_info.json`의 태그 기록 |
| 무음 일관성 | 무음 케이던스 변동계수 3% 이하(`g2.silent_cv_max_pct`) | `g2_flags.csv` F5 |
| 실험 2·3 | 데이터 유효 | 실험 2의 Q01–Q03, Q09 PASS(D-63) · 실험 3 Q01–Q03, Q09 PASS · 점프 기록 Q17 PASS · 단계 요약과 진자 주기(곧은·굽힌 다리)가 계산됨 |
| 시나리오 | 결과가 어느 시나리오인지 판정 | `g2_flags.csv` + 사람의 판단('NA(사람)') |

### G3 · 11/24 데이터 동결

| 항목 | 기준 | 확인 방법 |
|---|---|---|
| 처리 | 모든 회차·시행 처리 완료 | 풀리지 않은 FAIL 없음(해결 또는 `status`로 제외 사유 기록) |
| 최소 핵심 데이터 | 사람마다 무음과 P1–P4 각 2회 이상 유효 · 실험 2의 100·120·150% 단계 유효 | `walks.csv`, `exp2_summary.csv` |
| 데이터 표 | v1.0 동결 | `freeze --version 1.0`, `results/frozen/v1.0/SHA256SUMS` |
| 그림 | 핵심 그림 4장(그림 2, 3b, 6, 7) | `results/figures/` |
| 측정 검증 | 검증표와 그림 9 | `validation.csv`, `fig9_validation.png` |
| 처방 범위 | 사람마다 범위 또는 '하한 없음' 문장 | `prescription.csv` |
| 개인정보 | Q15 PASS | — |

G4(슬라이드 동결)는 코드와 무관하다.

## 4. 보고 형식

QA 결과는 이렇게 보고한다. 표는 사람×회차로 줄이고, WARN과 FAIL만 사유를 적는다.

| walk_id | 상태 | WARN·FAIL 요약 |
|---|---|---|
| E1_B_07_P1_1113 | WARN | Q03: 0.31 s 끊김 2곳(문턱 0.25). Q13: 3번째 곡 구간 유효 걸음 22(문턱 30) |
