# SPEC — 분석 명세 v0.1

작성 2026-11-07 · 읽는 사람: Claude Code(구현), B(데이터 담당), A(팀장)

이 문서는 팀 문서 「내 플레이리스트가 걸음을 바꾼다 — 프로젝트 통합본」의 연구계획·실험 1 프로토콜·실행 스케줄 탭에서 분석 코드에 필요한 부분만 뽑아, 코드가 바로 쓸 수 있게 고쳐 쓴 것이다. [확정] 표시가 붙은 값은 원문 그대로다. 원문 사이(예: 연구계획과 프로토콜)나 원문과 이 문서가 어긋나는 곳은 `DECISIONS.md`에 적고, 사용자가 정하기 전까지는 이 문서의 [초안] 값을 쓴다.

## 0. 읽는 법

- **[확정]** 연구계획서·프로토콜에 있는 정의와 기준. 결과를 보기 전에 정해 둔 것이라 코드가 바꾸지 않는다. 바꿔야 하면 멈추고 사용자에게 묻는다.
- **[초안]** 계획서에 없거나 모호해서 이 문서가 정한 기본값. `DECISIONS.md`에 번호(D-xx)가 있고 B가 11/9 전에 확인한다. 실제 데이터를 본 뒤에는 바꾸지 않는다.
- **[확인 필요]** 실제 파일을 열어 봐야 아는 사실. Phase 0에서 확인해 `DATA_FACTS.md`에 적는다.
- 임계값과 파라미터는 `config/params.toml`의 키 이름으로 가리킨다(예: `exclude.edge_s`).
- §9의 예제 수치는 그대로 테스트가 된다.
- 단계는 Phase 0–5(§12), 판단 관문은 G1 11/12 · G2 11/18 · G3 11/24 · G4 11/28이다.

## 1. 목표와 범위

**목표.** Sensor Logger zip → 품질 점검(QA) → 걸음 검출 → 지표 → 가설 판정·그림·표. 전체를 명령 한 줄로 다시 만들 수 있어야 한다.

**성공 기준**

1. G1(11/12): 셋 다 1–2회차 파일(6개)을 QA로 자동 판정한다.
2. G2(11/18): 실험 1 지표(1인 7회 이상), 무음 케이던스 변동계수, 시나리오 신호(§5.9)를 낸다.
3. G3(11/24): 데이터 표 v1.0(동결)과 핵심 그림 4장(그림 2, 3b, 6, 7).
4. 그 뒤: 논문의 표·그림 전부를 다시 만든다.

**범위 밖.** 웹/앱(Phase 5, 사용자가 요청할 때만), phyphox 백업 파일 읽기(Sensor Logger가 실패해 실제로 쓰게 될 때만 추가), 실시간 처리, 영상 자동 분석(영상에서 사람이 읽은 값은 CSV로 받는다), 집단 검정, 의학적 해석, 데이터를 외부로 보내는 모든 것.

## 2. 연구 설계 요약 (분석 관점)

| | 실험 1 · 일상 보행 | 실험 2 · 템포 챌린지 | 실험 3 · 다리 진자 |
|---|---|---|---|
| 사람 | A·B·C (+ 보강 N1–N4는 별도 표, D-17) | A·B·C | A·B·C |
| 조건 | 무음 3 + 플레이리스트 P1–P4 각 3 = 1인 15회 | PC의 100·120·135·150·165% 음원, 단계마다 2회, 방향 번갈아 | 정강이 폰, 다리 힘 빼고 3회 |
| 한 번 | 평소 길 8분 이상 | 40 m 코스(가운데 30 m 분석) | 흔들기 |
| 지시 | 없음 | 박자 하나에 한 발씩, 걷든 뛰든 | 힘 빼고 흔들기 |
| 폰 | 허리 파우치 | 허리 파우치 | 정강이 밴드 |
| 파일 이름 | `E1_<사람>_<회차2자리>_<조건>_<MMDD>` | `E2_<사람>_<비율>_<반복>` | `E3_<사람>_<반복>` |
| 날짜 | 11/9–11/22 | 11/14(예비 11/15) | 11/14 |
| 주 산출 | 곡 구간 지표 | 단계 지표(동조율, 체공, Fr) | 흔들림 주기 P |

**가설과 사람별 판정 기준 [확정]** (연구계획 2.2·2.4). n=3이므로 사람마다 판정하고, 3명 중 2명 이상에서 같으면 '지지'다(가설 4만 3명 모두).

| 가설 | 내용 | 한 사람에서 '지지'의 기준 |
|---|---|---|
| H1 | 곡 BPM이 PC ±10% 안이면 지시 없이도 걸음이 박자 쪽으로 끌려간다 | 곡 구간 단위 Spearman ρ(T, ΔC%) > 0 이고 p < 0.05, 그리고 PC ±`sync.near_pc_pct`(10%) 안의 곡에서 동조율이 그 밖의 곡보다 높다 |
| H1-2 | 박자에 맞추라고 하면 +20%까지 맞춘다 | 실험 2의 100%와 120% 단계 각각에서 ±`sync.tol_pct`(3%) 안 걸음이 `exp2.h1_2_min_sync_frac`(80%) 이상 [초안 D-10] |
| H2 | 빠른 곡일수록 더 빨리·큰 보폭으로 걷고 충격이 크다. 억지로 맞추면 걸음 변동성이 더 크다 | ρ(T, 속도), ρ(T, 보폭), ρ(T, 충격)이 양수면 '증가 경향'. 변동성은 같은 템포의 실험 1과 실험 2를 비교 |
| H3 | 템포를 올리면 어느 지점에서 달리기로 바뀌고, 그 지점이 Fr ≈ 0.5 | '마지막으로 걸은 단계'와 '처음 체공이 생긴 단계' 사이에 Fr 0.5가 들어간다 |
| H4 | 곧게 편 다리 진자의 예측 케이던스는 실측 PC보다 느리다 | 3명 모두에서 C_pend < PC. 흔들림 주기 예측-실측 평균 오차 15% 이내면 모델 타당 |
| 탐색 | 같은 BPM 구간에서 좋아하는 곡이면 더 빨리 걷는가 | 판정하지 않고 구간 안 순위 상관만 보고 |

## 3. 입력 데이터

### 3.1 Sensor Logger Zipped CSV

Sensor Logger는 기록 하나를 zip으로 내보낸다. 앱 공식 문서(awesome-sensor-logger)에서 확인된 사실:

- 켠 센서마다 CSV 하나: `Accelerometer.csv`, `Gyroscope.csv`, `Gravity.csv`, `Location.csv`, `Metadata.csv`. 걸음 수는 `Pedometer.csv`일 것으로 추정한다 [확인 필요].
- 시간 열: `time` = UNIX epoch 나노초(UTC), `seconds_elapsed` = 기록 시작부터의 초.
- 가속도·자이로·중력: `x, y, z`.
- 위치: `latitude, longitude, altitude, speed, speedAccuracy, bearing, bearingAccuracy, horizontalAccuracy, verticalAccuracy`. GPS 속도에는 오차가 있고 `speedAccuracy`가 그 크기다. 속도 단위는 문서에 없다 [확인 필요].
- `Metadata.csv`: version, device name, recording time, platform, platform version, appVersion, recording timezone, recording epoch time, standardisation. 옛 기록에는 일부 열이 없다.
- 압축 파일 이름의 시각은 현지 시각이고 열의 `time`은 UTC다.
- 센서는 고르게 샘플링되지 않는다. 간격이 흔들리는 것이 정상이다.

### 3.2 Phase 0에서 확인할 것 [확인 필요]

1. 실제 압축 파일 목록과 센서별 열 이름.
2. Accelerometer가 중력을 포함하는가, 단위가 g인가 m/s²인가. 판별법은 §5.2.
3. Gravity의 단위와 부호(가속도와 같은 방향인가 반대인가).
4. Gyroscope 단위(rad/s로 가정).
5. Pedometer: 파일이 있는가, 열 이름, 누적 값인가 구간 값인가, 갱신 간격.
6. Location: 갱신 간격, `speed` 단위(m/s로 가정), `speedAccuracy`·`horizontalAccuracy` 분포.
7. 센서별 첫·마지막 `time`의 차이, 실제 샘플링 간격(중앙값, 5·95 백분위, 최대), 끊김.
8. `Metadata.csv` 내용. 'recording epoch time'을 기록 시작 시각으로 쓸 수 있는가.
9. iOS와 Android 모두 있으면 둘의 차이.

결과는 `DATA_FACTS.md`에 적고, 이 문서의 가정과 다르면 `DECISIONS.md`에 적은 뒤 사용자에게 알린다.

### 3.3 메타데이터 CSV

`data/README.md`에 열마다 설명이 있다. 요약:

| 파일 | 내용 | 누가 채우나 |
|---|---|---|
| `assignment.csv` | 회차 배정표(고정). `tools/assign.py`로 재현 | 생성 완료 |
| `manifest.csv` | 기록지 내보내기, 회차당 1줄 | 걷는 사람, A가 점검 |
| `participants.csv` | 나이·키·체중·다리 길이·폰 | 각자 |
| `music_bpm.csv` | 곡 12+2: BPM, **곡 길이(`duration_s`)** | C |
| `song_ratings.csv` | 곡별 좋아하는 정도·아는 정도(1–5) | 각자 |
| `exclusions.csv` | 수동 제외 구간(계단·인파·폰 만짐) | 걷는 사람 |
| `exp2_trials.csv` | 챌린지 기록지(통과 시간, 걸음 수, 걷기/뛰기) | 현장 기록 담당 |
| `exp3_swings.csv` | 진자 시행 목록 | 현장 |
| `private/sections.csv` | 측정 구간 웨이포인트(좌표). git 제외 | 각자 |

### 3.4 파일 이름과 manifest

- 코드는 파일 이름이 아니라 manifest를 기준으로 한다. 이름과 manifest가 어긋나면 QA 실패(Q10). `walk_id`는 zip 파일 이름에서 `.zip`을 뺀 것이다(예: `E1_B_07_P1_1113`).
- 실험 1: `E1_<사람>_<회차 2자리>_<조건>_<MMDD>.zip`, 무음은 `S`. 예: `E1_B_07_P1_1113.zip`, `E1_A_01_S_1109.zip`. 다시 한 회차는 16부터. 이름에 시작 곡(①②③)이 없으므로 `start_song`은 manifest에서 읽는다.
- 실험 2: `E2_<사람>_<비율>_<반복>` (예: `E2_A_150_2`), 무음 시행은 비율 자리에 `S`. 실험 3: `E3_<사람>_<반복>`.
- 시범 측정은 `TEST_A_1107`로 manifest에 등록한다.

## 4. 정의와 기호

**기호 규칙.** T는 템포 비율(%)에만 쓴다. P는 다리 흔들림 주기(s)에만 쓴다(플레이리스트 이름 P1–P4와 다르다). t는 시간이다. 코드에서는 `tempo_ratio_pct`, `swing_period_s`처럼 풀어 쓴다.

**표기 주의.** 계획서·프로토콜의 단위 '보/분'은 분당 걸음 수(steps per minute, spm)다. 이 저장소는 '걸음/분'으로 쓴다. 계획서의 '보폭'은 한 걸음의 길이(step length)이고, 같은 발이 다시 닿을 때까지(두 걸음)는 stride(한 보)라 부른다.

### 4.1 걸음과 케이던스 [확정]

| 이름 | 정의 | 식·단위 |
|---|---|---|
| 걸음(step) | 한쪽 발이 닿은 뒤 반대쪽 발이 닿을 때까지. 검출 단위는 발 디딤(heel strike) 1회. 한 보(stride) = 2걸음 | |
| 걸음 간격 Δt_i | i번째와 i+1번째 발 디딤 사이의 시간 | s |
| 순간 케이던스 c_i | | c_i = 60 ÷ Δt_i (걸음/분) |
| 케이던스 C | 구간 안 유효 걸음 간격으로 두 가지를 모두 낸다. `cadence_median_spm` = 유효 c_i의 중앙값(프로토콜 "곡마다 중앙값"), `cadence_rate_spm` = 유효 간격 수 ÷ 유효 간격 합 × 60(계획서 2.3 "걸음 수 ÷ 시간 × 60"). PC·T·ΔC%·R에는 `cadence.primary`가 가리키는 쪽만 쓴다 [초안 D-05: 기본 median. 걸음 하나를 놓쳐 생긴 긴 간격이 rate를 낮추기 때문] | 걸음/분 |
| 평소 케이던스 PC | 사람마다 무음 회차들의 C(회차 전체 유효 창에서 `cadence.primary` 기준으로 계산)의 평균. 무음이 3회 미만이면 임시 값(`pc_provisional=true`) | 걸음/분 |
| 걸음 변동성 CV | 100 × SD(Δt_i) ÷ mean(Δt_i), 구간 안 연속 유효 간격만. 표본 SD(ddof=1) | % |

### 4.2 템포와 동조 [확정]

| 이름 | 정의 | 식 |
|---|---|---|
| 템포 비율 T | 곡 BPM이 PC의 몇 %인가 | T = BPM ÷ PC × 100 (%) |
| 케이던스 변화율 ΔC% | | (C − PC) ÷ PC × 100 |
| 추종 비율 R | 템포 변화를 걸음이 얼마나 따라갔나. 1은 완전히 따라감, 0은 무반응 | R = ΔC% ÷ (T − 100). `sync.r_exclude_low` ≤ T ≤ `sync.r_exclude_high`(98–102%)이면 계산하지 않는다(NaN) |
| 동조율 S3 | 유효 걸음 중 c_i가 곡 BPM의 ±`sync.tol_pct`(3%) 안인 비율(%) | \|c_i − BPM\| ≤ 0.03 × BPM. 분모는 구간의 유효 걸음 수 |
| 동조율 S5 | 같은 방식, ±`sync.tol_alt_pct`(5%) (함께 보고) | |
| 반 박자 동조 S3_half | \|c_i − BPM/2\| ≤ 0.03 × BPM/2 인 비율. 따로 센다 | |
| 두 배 박자 동조 S3_double | \|c_i − 2·BPM\| ≤ 0.03 × 2·BPM 인 비율. 따로 센다 | |
| 하위·상위 동조 표시 | 구간 C ÷ BPM이 0.5의 ±`sync.tol_pct`(3%) 안이면 `sub`, 2의 ±3% 안이면 `super`, 아니면 `none` | 변수 대응표(G2)에 따라 "분석 코드에 판정 추가" |

### 4.3 역학 지표 (폰 허리 장착, 모두 **추정치**) [확정, 구현 세부는 초안]

| 이름 | 정의 | 식·단위 |
|---|---|---|
| 총 수직 가속도 a_v,total | 중력을 포함한 수직 방향 가속도. 서 있을 때 +1 g가 되도록 방향을 맞춘다 | g |
| 발 디딤 충격 F/BW | 발이 닿은 직후 수직 지면반력의 최댓값(체중 배수, 추정). 걸음마다 걸음 시각 ± `steps.impact_window_s` 안 a_v,total의 최댓값. 구간 값은 중앙값 [초안 D-07] | F/BW = a_v,total,max ÷ g |
| 충격 상대값 | 구간 충격이 그 사람 무음 회차 충격 중앙값에서 변한 정도 | (구간값 − 무음 중앙값) ÷ 무음 중앙값 × 100 (%) |
| 마찰 요구비 μ_req | 발 디딤 직후 수평력 ÷ 수직력(추정). 충격 피크 시각 근처 앞뒤 가속도 크기 ÷ 같은 시각 a_v,total | 무차원 |
| 속도 v | §5.6 (D-01) | m/s |
| 보폭 SL | v ÷ (C ÷ 60) | m |
| 속도 분해 | Δln v = Δln SL + Δln C (정확히 더해진다). 기여율 = Δln SL ÷ Δln v, Δln C ÷ Δln v. 계획서의 Δv/v ≈ ΔSL/SL + ΔC/C 와 1차 근사에서 같다 [초안 D-12] | |

### 4.4 실험 2·3 [확정]

| 이름 | 정의 | 식·단위 |
|---|---|---|
| 체공 | 두 발이 모두 땅에서 떨어진 구간. 총 가속도 크기 < `flight.a_thresh_g`(0.2 g)가 `flight.min_duration_s`(30 ms) 이상 이어진 구간. 영상으로 확인 | 체공 시간 t_f (s) |
| 몸 중심 상승 높이 h | | h = g · t_f² ÷ 8 (m) |
| Froude 수 Fr | 속도를 다리 길이로 표준화 | Fr = v² ÷ (g · L), L = 대전자~바닥 높이(m), g = `constants.g`(9.81) |
| 다리 흔들림 주기 P | 정강이 자이로 주축 각속도의 같은 방향 봉우리 간격의 중앙값 | s |
| 진자 예측 케이던스 C_pend | | C_pend = 60 ÷ (P ÷ 2) = 120 ÷ P (걸음/분) |
| 진자 모델 주기 P_model | 곧게 편 다리를 물리 진자로 본 이론값. 회전반경 k = `pendulum.k_over_L`(0.560) L, 질량중심 d = `pendulum.d_over_L`(0.447) L (Winter) [초안 D-06] | P_model = 2π √(k² ÷ (g · d)) |
| 주기 오차 | | (P − P_model) ÷ P_model × 100 (%) |

## 5. 처리 파이프라인

흐름: `zip → 불러오기(5.1) → 단위·부호 판별(5.2) → 자세 분해(5.3) → 걸음 검출(5.4) → 구간 나누기(5.5) → 지표(5.6–5.8) → 판정(§6) → 출력(§7) → 그림·표(§8)`.

### 5.1 불러오기와 시간축

- zip은 `data/raw/`에서 풀지 않고 읽거나, 풀 때는 `data/interim/<walk_id>/`에 푼다.
- `time`(ns, UTC)을 시각으로 바꾸고 `time.timezone`(Asia/Seoul, D-16)으로 보여 준다. 센서 사이의 공통 시간축 t_s = (time − 기록 시작) ÷ 1e9. 기록 시작은 `Metadata.csv`의 recording epoch time이 쓸 만하면 그 값, 아니면 모든 센서 파일의 첫 `time` 중 최솟값 [확인 필요, D-20].
- 샘플 간격은 불규칙하다. 간격 분포를 기록하고, 필터링 전에는 중앙 간격의 균일 격자로 선형 보간한다. 보간은 `qa.gap_warn_s`보다 긴 끊김을 가로지르지 않는다(끊김 앞뒤를 따로 처리).
- 파일 하나가 비거나 열이 다르면 조용히 넘어가지 말고 QA에 실패로 남긴다.

### 5.2 단위와 부호 판별

가정하지 않고 데이터로 판별한다. 판별에 실패하면 멈추고 알린다.

- 단위와 중력 포함 여부: 서 있는 앞 `qa.standing_check_s`(10 s)에서 ‖(x, y, z)‖의 중앙값으로 판단한다. 약 1이면 g 단위이고 중력 포함, 약 9.8이면 m/s²이고 중력 포함, 0 근처면 중력 제외 신호다(이때 단위는 같은 구간 Gravity 크기가 약 1인지 약 9.8인지로 정한다). 서 있는 구간이 없으면 걷는 동안의 중앙값으로 대신하되 확신이 낮다고 표시한다(중력 제외 신호도 g 단위로는 걷는 동안 1 근처가 될 수 있다). 내부 계산은 g로 통일한다.
- 총 가속도: 중력 포함 신호는 그대로 쓴다. 중력 제외 신호이면 Accelerometer와 Gravity를 더해 만든다. 부호 규칙은 Phase 0에서 확인해 DECISIONS.md에 적는다. 합친 뒤 걷는 동안 a_v,total이 1 g 아래보다 위로 더 크게 벗어나는지(발 디딤 충격이 위쪽 피크인지)를 상식 점검으로 확인한다.
- 방향: '위'는 서 있는 구간 평균 벡터의 방향으로 정의해 a_v,total이 서 있을 때 +1 g가 되게 한다. 플랫폼마다 부호 규칙이 달라도 같은 값이 된다.
- 판별 결과(`units`, `includes_gravity`, `gravity_combine_sign`)를 회차마다 QA 결과에 남기고, 사람·회차 사이에 달라지면 경고한다.

### 5.3 자세 분해

폰이 파우치에서 기울어도 쓸 수 있게 몸 기준 방향으로 나눈다.

- 위(수직) 단위벡터 û: 서 있는 구간의 평균 중력 방향, 걷는 동안에는 느린 저역 통과(`orientation.lowpass_hz`, 0.3 Hz)로 갱신한다 [초안 D-22].
- a_v,total = 총 가속도 · û (g). 서 있을 때 +1 g.
- 수평면에서 걷는 동안 가속도의 주성분(PCA 첫 축)을 앞뒤(AP)로, 그에 수직인 축을 좌우(ML)로 한다. 부호는 마찰 요구비가 크기를 쓰므로 중요하지 않다.
- 회차마다 û(폰 방향)를 기록하고, 사람의 회차 사이 방향 차이가 `qa.phone_tilt_warn_deg`보다 크면 경고한다(폰 위치가 바뀐 신호).

### 5.4 걸음 검출 [초안 D-02, 수용 기준은 확정]

- 신호: 기본은 총 가속도 **크기** ‖a_total‖(계획서 4.6). 크기는 폰 방향에 둔감하다. `steps.signal = "vertical"`로 a_v,total을 쓰는 대안을 두고, 시범 파일과 합성 신호에서 더 잘 맞는 쪽을 골라 근거를 `DATA_FACTS.md`에 적는다.
- 처리: 직류 성분 제거 후 영위상 대역 통과 `steps.detect_band_hz`로 걸음 박자를 살리고, 봉우리를 찾는다(최소 간격 `steps.min_interval_s`, 적응형 문턱). 걸음 시각은 봉우리 시각이다.
- 충격 값은 대역 통과한 신호가 아니라 `steps.impact_lowpass_hz`로만 저역 통과한 신호에서 걸음 시각 ± `steps.impact_window_s` 안의 최댓값을 쓴다(과한 평활은 피크를 깎는다).
- 이상 간격: Δt가 `steps.min_interval_s`–`steps.max_interval_s` 밖이면 '이상 간격'으로 표시하고 통계에서 뺀다(누락·중복 검출 신호). 이상 간격 비율이 `qa.max_bad_interval_frac`를 넘으면 QA 경고.
- 알고리즘은 구현이 정한다. 아래 **수용 기준**을 넘는 것이 요구사항이다.
  1. 합성 신호: 걸음 주파수 1.5–2.5 Hz, 잡음·진폭 변동을 넣은 100 Hz 신호에서 케이던스 오차 ≤ 1%.
  2. 직접 센 걸음 수가 있으면 ± `qa.hand_count_tol_steps`(2) 안.
  3. Pedometer가 있으면 걸음 수 차이 ≤ `qa.pedometer_tol_pct`(3%).
  4. 보조 검증: 좌우(ML) 축 스펙트럼의 주 피크가 걸음 주파수의 절반(두 걸음, 곧 한 보에 한 번 흔들림)에 있는지.
- 한 사람의 15회에 같은 매개변수를 쓴다. 회차마다 튜닝하지 않는다.

### 5.5 구간 나누기와 제외

**(a) 보행 묶음과 유효 창.** 걸음 간격이 `exclude.stop_gap_s`(2.0 s) 이하로 이어진 걸음들을 한 보행 묶음으로 본다. 걸음 `exclude.min_bout_steps`(10)개 이상인 묶음이 지속 보행이다 [초안 D-21]. t_depart = 첫 지속 보행의 첫 걸음, t_arrive = 마지막 지속 보행의 마지막 걸음. **유효 창 = [t_depart + 20 s, t_arrive − 20 s]** (`exclude.edge_s`).

**(b) 정지.** 간격이 2.0 s를 넘는 걸음 쌍은 이어진 구간이 아니므로 그 간격과 앞뒤 `exclude.stop_pad_s`를 제외한다 [초안 D-19].

**(c) 수동 제외.** `data/exclusions.csv`의 (walk_id, start_s, end_s) 구간(계단·인파 등)과, 폰을 만진 시각(`reason=phone_touch`)은 앞뒤 `exclude.phone_touch_pad_s`를 제외한다. manifest의 `notes`는 자유 서술이라 코드가 해석하지 않는다. `notes`가 있는데 `exclusions.csv`에 그 walk_id가 없으면 QA가 INFO로 알린다.

**(d) 곡 구간 (실험 1).**

- 첫 곡 재생 시각 = 기록 시작 + `music_offset_s`(manifest 값, 없으면 `music.default_offset_s`).
- 재생 순서: manifest `songs_played`가 있으면 그 순서를 쓴다(프로토콜: "분석은 실제로 들은 곡 기준"). 없으면 플레이리스트의 곡 번호 [1, 2, 3]을 `start_song`부터 순환한다(전체 반복). 곡 순서를 알 수 없는 회차(`status=no_song_segments`)는 곡 구간을 계산하지 않고 회차 단위 지표만 쓴다.
- 곡 k의 시작 = 첫 곡 재생 시각 + 앞 곡들의 `duration_s` 합. `duration_s`가 비어 있으면 **추측하지 말고 멈추고 알린다.**
- 유효 곡 구간 = [곡 시작 + 10 s, 곡 끝 − 10 s](`exclude.boundary_s`) ∩ 유효 창 − (b)·(c)의 제외.
- 유효 걸음이 `qa.min_valid_steps_per_segment`(30)보다 적은 구간은 지표를 내지 않는다(`flags=few_steps`) [초안 D-08].
- 무음 회차는 유효 창 전체가 구간 하나다.
- 민감도: `music_offset_s`를 ± `music.offset_sensitivity_s`만큼 옮겨 다시 계산한 결과를 `sensitivity.csv`에 남긴다.

**(e) 측정 구간 통과 (속도 검증용).** `data/private/sections.csv`의 웨이포인트(시작→끝)에 위치 점을 투영해 시작·끝 통과 시각을 선형 보간으로 구한다(`speed.section_radius_m` 안에서만 인정). 방향이 반대(오는 길)면 통과 순서로 시작·끝을 정한다. v_section = `participants.section_distance_m` ÷ (t_out − t_in). 좌표는 이 계산에만 쓰고 출력에는 시각·거리만 남긴다. GPS가 튀어 거리 차가 `qa.gps_distance_tol_pct`를 넘는 회차는 지도 거리 ÷ 통과 시간으로 속도를 구한다. 이때 통과 시각은 구간 시작·끝에서 걷는 사람이 멈춘 약 2초(걸음이 끊긴 구간)에서 찾고 `flags=section_by_stops`를 붙인다 [초안 D-26].

### 5.6 실험 1 지표

곡 구간마다(`segments.csv`), 회차마다(`walks.csv`), 사람마다(`participants.csv`) 계산한다.

- **구간:** n_valid_steps, valid_duration_s, C(중앙값), cadence_rate_spm, T, ΔC%, R, S3, S5, S3_half, S3_double, sub/super 표시, CV, 충격 F/BW(중앙값)와 상대값, μ_req(중앙값), 속도, 보폭.
- **속도·보폭 [초안 D-01].** 계획서 4.6은 측정 구간 통과 속도를, 4.7은 곡 구간(1인 30여 개) 단위 상관을 쓴다. 한 회차에 구간 통과는 한 번뿐이라 곡 구간 단위에는 쓸 수 없으므로 다음과 같이 둘을 함께 쓴다.
  - **기준값**: 곡 구간의 Doppler 속도(`Location.csv`의 `speed`, 속도 정확도 `speed.doppler_max_speed_accuracy_ms` 이하인 샘플)의 중앙값. 보폭 SL = v ÷ (C ÷ 60).
  - **검증값**: 회차마다 v_section(5.5e). 같은 회차의 Doppler 중앙값과 비교해 상대 차이를 `walks.csv`에 남긴다. 차이가 `speed.mismatch_tol_pct`(5%)를 넘는 회차는 `flags=speed_mismatch`.
- **PC:** 사람마다 무음 회차의 회차 단위 C를 평균한다. 무음이 3회 미만이면 `pc_provisional=true`, 무음 회차 수 n_silent를 함께 낸다. 사람마다 무음 C의 변동계수도 낸다(G2).
- T는 PC가 있어야 계산된다. PC가 임시 값이면 T·ΔC%·R도 `provisional`로 표시한다.
- **회차:** 유효 창 전체의 C, cadence_rate, CV, 속도, 걸음 수(검출/Pedometer/직접 센 값), QA 상태, 날씨·서두름·가방.

### 5.7 실험 2 (11/14 이후)

입력: `exp2_trials.csv`(기록지) + `E2_*` zip. 원칙: **기록지에서 오는 값(통과 시간 t30, 걸음 수 N, 걷기/뛰기)은 사람이 읽은 값이고, 센서에서 오는 값(체공, 충격, 센서 케이던스)은 코드가 낸다.** 둘을 한 표에 나란히 둔다.

- 분석 창: `t_in_sensor_s`, `t_out_sensor_s`(영상 동기에서 구한 센서 시각)가 있으면 그 창, 없으면 그 시행에서 검출한 걸음 열의 가운데 `exp2.central_step_frac`(75%) [초안 D-13].
- 코스 길이는 `exp2.course_m`(40 m)이고 분석 구간은 가운데 `exp2.analysis_m`(30 m)다. v = 30 ÷ t30_s. 기록지 케이던스 = N ÷ t30_s × 60.
- 현장 PC = 무음 2회의 (N ÷ t30_s × 60)의 평균. T = 실제 튼 BPM(`bpm_played`) ÷ 현장 PC × 100. 실험 1의 PC와의 차이를 표로 낸다 [초안 D-04]. 기록지의 `pc_field_spm`(현장에서 음원을 고르려고 사람이 계산해 적은 값)과 다시 계산한 값이 `exp2.pc_field_tol_spm`보다 많이 다르면 경고한다.
- 창 안 유효 걸음으로 S3, S5, S3_half, S3_double, CV, 충격 F/BW, 센서 C.
- 체공: 창 안에서 체공 이벤트(§4.4)를 찾고 `flight_step_frac`(체공이 있는 걸음 비율), 체공 시간 중앙값, 높이 h를 낸다. 필요한 최소 연속 샘플 수는 ceil(0.030 × fs − 1e-9)이고(부동소수점 오차로 3.0000000000000004가 4가 되지 않게 1e-9를 뺀다), 샘플링이 100 Hz면 3샘플, 50 Hz면 2샘플(40 ms)이다.
- 걷기/뛰기: 영상 판정(`gait_video`)이 기준이고 센서 체공은 검증용이다. 어긋나면 `flags=gait_mismatch`.
- Fr = v² ÷ (g · L). L은 `participants.leg_length_m`.
- 단계 요약: 같은 사람·비율의 2회를 평균한다(`exp2_stages.csv`는 시행 단위, `exp2_summary.csv`는 단계 단위).
- H3 판정: 사람마다 단계(`exp2.stage_ratios_pct`)를 100→165% 순서로 놓고, 마지막으로 걸은 단계의 Fr ≤ `stats.froude_walk_run`(0.5) ≤ 처음 뛴 단계의 Fr 이면 지지. 165%에서도 뛰지 않았으면 `flags=no_run` (G2의 'F6').
- 영상 동기: 점프 3회 + 박수가 센서에서 큰 수직 가속도 3연타와 체공으로 보인다. 코드는 점프 3개의 센서 시각을 찾아 `sync_jump_sensor_s`로 낸다(영상 쪽 시각은 사람이 읽어 `t_in_sensor_s`로 옮긴다).

### 5.8 실험 3

- 입력: `E3_*` zip의 `Gyroscope.csv`, `exp3_swings.csv`, `participants.leg_length_m`.
- 자이로 3축의 주성분(첫 축) 각속도 ω(t)를 만들고 저역 통과(`pendulum.gyro_lowpass_hz`, 6 Hz) [초안 D-24]. 같은 방향 봉우리 간격으로 P를 구한다. 처음과 마지막 한 주기는 뺀다. 시행마다 P 중앙값, 사람마다 3회의 중앙값.
- C_pend = 120 ÷ P. P_model(L)과 주기 오차를 계산한다.
- H4: 3명 모두 C_pend < PC 이면 지지. 세 사람 |주기 오차|의 평균이 `pendulum.valid_error_pct`(15%) 이하이면 모델 타당.
- 참고: L = 0.9 m이면 P_model ≈ 1.59 s, C_pend ≈ 75 걸음/분(§9).

### 5.9 시나리오 신호 (G2용)

실행 스케줄 탭의 '결과가 예상과 다를 때' 표를 코드로 옮긴 것이다. 계획서에 숫자가 있는 것만 `triggered`를 판정하고, 없는 것은 값만 내고 `triggered=NA`로 둔다(**임계값을 지어내지 않는다**). 결과는 `g2_flags.csv`.

| ID | 신호 | 계산 | 판정 |
|---|---|---|---|
| F1 | 일상에서 동조가 거의 없음 | 사람마다 ρ(T, ΔC%)·p, PC ±10% 곡의 S3 중앙값 | NA(사람이 판단) |
| F2 | 과동조 | 일상 보행 구간 중 S3 ≥ `sync.over_sync_frac`(80%)인 구간의 비율 | 그런 구간이 있으면 triggered |
| F3 | 반 박자·두 배 박자 | sub/super 표시가 붙은 구간 수 | 1개 이상이면 triggered |
| F4 | 곡마다 들쭉날쭉 | ΔC%의 같은 플레이리스트 안 곡 사이 분산 vs 플레이리스트 사이 분산 | 안 > 사이 이면 triggered |
| F5 | 날마다 편차 큼 | 사람마다 무음 C의 CV | > `g2.silent_cv_max_pct`(3%) 이면 triggered |
| F6 | 165%에서도 안 뜀 | 165% 단계에 체공 없음 + 영상 걷기 | triggered |
| F7 | 충격 잡음 큼 | 같은 조건 3회 구간 충격 중앙값의 CV | > `g2.impact_cv_max_pct`(15%) 이면 triggered |
| F8 | 진자 예측과 실측의 큰 차이 | C_pend, PC | NA. "예상된 결과"로 보고만 한다 |

## 6. 통계와 판정

- 단위: 실험 1은 곡 구간, 실험 2는 단계(시행 2회 평균), 모두 **사람 안에서** 분석한다.
- 기술통계: 사람×조건 평균 ± SD(`stats.sd_ddof`=1, D-14), CV.
- 상관: `scipy.stats.spearmanr`, 양측, α = `stats.alpha`(0.05). 구간 수 n을 함께 낸다. 구간 수가 `stats.min_n_for_corr`(8) 미만이면 '표본 부족'으로 표시하고 판정하지 않는다 [초안 D-23]. 곡 구간은 같은 회차 안에서 독립이 아니므로 p는 참고치라고 표에 주석을 단다.
- 효과 크기: 무음 대비 차이(절대, %)와 표준화 효과 크기(Cohen's d, 구간 값 기준 풀링 SD). 기술용이다.
- 변동성 비교(가설 2): 실험 2 단계의 T와 `stats.same_tempo_pct`(±5%p) 이내인 실험 1 곡 구간을 짝지어, 사람마다 CV의 평균을 비교한다. 짝이 없는 단계는 뺀다 [초안 D-11].
- 일치 개수: 가설마다 '지지'인 사람 수를 센다(`hypotheses.csv`). `stats.agree_min_persons`(3명 중 2명) 이상이면 집단 수준 '지지'(가설 4는 3명 모두).
- 탐색(곡 선호도): 플레이리스트 안에서 (좋아하는 정도, ΔC%)의 순위 상관을 구한 뒤 부호를 센다 [초안 D-15].
- **쓰지 않는다:** Wilcoxon·Friedman 같은 집단 검정, 사후에 문턱을 바꾸는 것.
- 민감도 분석(부록): ±5% 동조 기준, 오프셋 ±5 s, 서두른 회차 포함/제외, 비 오는 날 포함/제외, 임시 PC vs 최종 PC → `sensitivity.csv`.

## 7. 출력

`results/` 아래에 쓴다(합성 데이터는 `results_synthetic/`). 모든 CSV는 UTF-8, 열 이름은 영어 snake_case에 단위 접미사(`_spm`, `_ms`, `_s`, `_pct`, `_g`, `_m`)를 붙인다. **좌표(위도·경도) 열은 어디에도 두지 않는다.**

| 파일 | 한 줄 | 주요 열 |
|---|---|---|
| `qa_summary.csv` | 회차×검사 | walk_id, check_id, status(PASS/WARN/FAIL/NA/INFO), value, threshold, note |
| `qa/<walk_id>.json` | 회차 QA 상세 | 단위·부호 판별, 샘플링, 끊김, 방향 û |
| `steps/<walk_id>_steps.csv` | 걸음 | step_idx, t_s, interval_s, cadence_inst_spm, impact_g, friction_req, valid, exclude_reason, song_idx |
| `segments.csv` | 곡 구간 | walk_id, participant, condition, playlist, song_title, bpm, tempo_ratio_pct, n_valid_steps, valid_duration_s, cadence_median_spm, cadence_rate_spm, dC_pct, R, sync3_pct, sync5_pct, sync3_half_pct, sync3_double_pct, sub_super, cv_pct, impact_g, impact_rel_pct, friction_req, speed_ms, step_length_m, liking, familiarity, pc_provisional, flags |
| `walks.csv` | 회차 | walk_id, participant, walk_no, condition, date, duration_s, valid_duration_s, detected_steps, pedometer_steps, hand_count, cadence_median_spm, cadence_rate_spm, cv_pct, speed_doppler_ms, speed_section_ms, speed_diff_pct, qa_status, hurried, weather, flags |
| `participants.csv` | 사람 | participant, n_silent, pc_spm, pc_provisional, silent_cv_pct, age, height_cm, mass_kg, leg_length_m |
| `hypotheses.csv` | 가설×사람 | hypothesis, participant, metric, value, n, criterion, supported, note (집단 행 포함) |
| `g2_flags.csv` | 시나리오 신호 | flag_id, description, value, threshold, triggered, suggested_response |
| `exp2_stages.csv` / `exp2_summary.csv` | 시행 / 단계 | runner, ratio_pct, repeat, bpm_played, pc_field_spm, tempo_ratio_pct, v_ms, cadence_record_spm, cadence_median_spm, sync3_pct, sync5_pct, cv_pct, impact_g, flight_step_frac, flight_time_median_s, rise_height_m, gait_video, fr, flags |
| `exp3_swings.csv` | 진자 | runner, repeat, swing_period_s, n_cycles, cadence_pend_spm, period_model_s, period_error_pct, leg_length_m |
| `sensitivity.csv` | 민감도 | 변형 이름, 영향받은 지표 |
| `tables/table1_participants.csv`, `table2_speed_decomposition.csv`, `table3_summary.csv` | 논문 표 | §8 |
| `figures/*.png` | 그림 | §8 |
| `frozen/v1.0/` | 동결본 | 위 CSV 복사 + `SHA256SUMS` (G3에서만, 덮어쓰기 거부) |
| `run_info.json` | 실행 기록 | git 해시, params 해시, 입력 파일 sha256, 패키지 버전, 시각 |

## 8. 그림과 표

템포에 따른 그림(그림 2, 3b, 4, 5, 6)의 가로축은 템포 비율 T(%)로 통일한다. 사람 3명은 패널 하나씩(공유 축), 곡 구간 값은 점, 평균은 굵은 선이다. 그림 제목은 중립적으로 두고(결과 문장은 사람이 데이터를 본 뒤 쓴다), 그림마다 같은 이름의 `.json`에 그려진 값 요약과 params 해시를 남긴다. 해상도 300 dpi, 폭 6.5–8 inch, 색은 색각 이상에서도 구분되는 팔레트, 사람마다 같은 색.

| 번호 | 파일 | 내용 | x | y | 비고 |
|---|---|---|---|---|---|
| 표 1 | `table1_participants.csv` | 나이, 키, 체중, 다리 길이, PC | | | |
| 그림 2 | `fig2_cadence_vs_tempo.png` | 1인 1패널. 실험 1 곡 구간은 점, 실험 2 단계는 선. 대각선 y = x | T (%) | 케이던스 ÷ PC (%) | **핵심** |
| 그림 3a | `fig3a_sync_by_playlist.png` | 플레이리스트(P1–P4)별 동조율 | 플레이리스트 | S3 (%) | |
| 그림 3b | `fig3b_sync_exp1_vs_exp2.png` | 실험 1 구간과 실험 2 단계의 동조율을 T로 나란히 | T (%) | S3 (%) | **핵심** |
| 그림 4 | `fig4_speed_steplength.png` | 속도와 보폭(실험 1) | T (%) | v (m/s), SL (m) | |
| 표 2 | `table2_speed_decomposition.csv` | 조건별 보폭·케이던스 기여율 | | | 로그 분해 |
| 그림 5 | `fig5_impact_variability.png` | 충격과 걸음 변동성(실험 1·2) | T (%) | F/BW, CV (%) | |
| 그림 6 | `fig6_speed_flight_froude.png` | 단계별 속도(선), 체공 시간(막대), Fr(보조 표시)와 Fr = 0.5 선, 영상 걷기/뛰기 표시 | 단계(T) | v (m/s), 체공 (s), Fr | **핵심** |
| 그림 7 | `fig7_pendulum.png` | 사람마다 막대 3개: 모델 예측, 실측 흔들림 기반 예측, 실측 PC | 사람 | 케이던스 (걸음/분) | **핵심** |
| 그림 8 | `fig8_preference.png` | 좋아하는 정도 vs 케이던스 변화율(구간 안) | 좋아하는 정도 (1–5) | ΔC% | 탐색 |
| 표 3 | `table3_summary.csv` | 사람×조건 모든 종속변수의 평균 ± SD | | | |

- 한글 폰트 [D-18]: Pretendard, Noto Sans CJK KR, NanumGothic, Malgun Gothic, AppleGothic 순으로 찾고, 없으면 영어 라벨로 그린다. `axes.unicode_minus = False`.
- 합성 데이터 그림에는 대각선 워터마크 "SYNTHETIC"을 넣는다.
- 지도, 경로, 좌표는 그림에 넣지 않는다.

## 9. 예제 수치 (그대로 테스트로 만든다)

| # | 입력 | 기대값 |
|---|---|---|
| 1 | 200 m를 150 s에 걷고 275걸음 | 속도 1.3333 m/s, 케이던스 110 걸음/분(걸음 수 ÷ 시간 × 60), 보폭 0.7273 m |
| 2 | PC = 110, BPM = 120 | T = 109.09%, ±3% 띠 [116.4, 123.6], ±5% 띠 [114, 126] |
| 3 | PC = 110, C = 115, BPM = 120 | ΔC% = 4.545, T − 100 = 9.091, R = 0.5000 |
| 4 | 체중 60 kg, 수직 가속도 3 m/s² | F = 60 × (9.81 + 3) = 768.6 N, 체중 588.6 N, F/BW = 1.306 |
| 5 | L = 0.9 m | √(gL) = 2.971 m/s, Fr = 0.5가 되는 v = 2.101 m/s, v = 1.33이면 Fr = 0.2004 |
| 6 | 체공 t_f = 0.12 s | h = 0.01766 m |
| 7 | r = 0.9 m, ω = 4 rad/s | v = 3.6 m/s(1.33 m/s의 2.707배) |
| 8 | 1.5 km, 속도 1.33 → 1.40 m/s | 1127.8 s → 1071.4 s, 56.4 s 단축 |
| 9 | L = 0.9 m (k = 0.560 L, d = 0.447 L) | P_model = 1.5940 s, C_pend = 120 ÷ P = 75.28. P = 1.6 s이면 C_pend = 75.0 |
| 10 | v 1.30 → 1.45, C 108 → 116 | SL 0.7222 → 0.7500, Δln v = 0.10920, Δln C = 0.07146, Δln SL = 0.03774, 케이던스 기여율 0.6544, 보폭 기여율 0.3456 |
| 11 | BPM = 120, c = [118, 121, 124, 119, 100, 240, 60.5] | S3 = 3/7 = 42.86%, 반 박자 1개, 두 배 박자 1개 |
| 12 | Δt = [0.50, 0.52, 0.48, 0.50, 0.50] (ddof=1) | CV = 2.828% |
| 13 | 무음 C = [108, 110, 112] | 변동계수 1.818% |
| 14 | PC = 110, 비율 1.00 / 1.20 / 1.35 / 1.50 / 1.65, 5 BPM 단위 반올림(0.5는 올림) | 110, 130, 150, 165, 180 |
| 15 | 100 Hz 신호가 1 g인데 0.1 g가 연속 5샘플 / 3샘플 / 2샘플 | 5샘플(50 ms)은 체공 1개, 3샘플(30 ms)도 1개(경계 포함), 2샘플(20 ms)은 없음 |
| 16 | 100–210 BPM, 5 간격 | 파일 23개 |
| 17 | PC = 110 | PC ±10% = [99, 121] BPM |

`tools/assign.py`의 출력이 `data/assignment.csv`와 같은지 확인하는 테스트도 둔다(배정은 이미 걷기 전에 정해졌으므로 바뀌면 안 된다).

## 10. 코드 구조와 품질

```
src/walkmusic/
  cli.py              inspect, qa, process, stats, figures, freeze, all
  config.py           params.toml 읽기 (키 이름은 위 문서와 같게)
  io_sensorlogger.py  zip → DataFrame, 시간축
  units.py            단위·부호 판별
  orientation.py      수직·앞뒤·좌우 분해
  steps.py            걸음 검출, 충격
  segments.py         보행 묶음, 제외, 곡 구간, 측정 구간
  metrics.py          케이던스, 동조율, CV, 속도, 보폭, 분해
  exp1.py exp2.py exp3.py
  stats.py            상관, 판정, 시나리오 신호
  figures.py          그림·표
  synthetic.py        실제 형식을 흉내 낸 합성 zip 생성
tests/
```

- 환경: Python 3.10 이상. 의존성은 numpy, pandas, scipy, matplotlib, (개발) pytest, ruff. 더 필요하면 이유를 `DECISIONS.md`에 적고 추가한다.
- 모든 공개 함수에 타입 힌트와 단위를 적은 독스트링. 입출력(파일)과 계산(순수 함수)을 분리한다. 난수는 시드를 고정한다.
- 명령: `python -m walkmusic inspect|qa|process|stats|figures|freeze|all`. 공통 옵션 `--walk ID`, `--participant X`, `--synthetic`.
- `all`은 같은 입력이면 같은 출력을 낸다(멱등). 입력 파일 해시가 같으면 다시 계산하지 않는다.
- 합성 데이터(`synthetic.py`): 알려진 케이던스·BPM 추종·체공·진자 주기를 가진 가짜 zip을 만들어, 45회 + 실험 2·3 전체가 실제 데이터 없이 끝까지 돌아가게 한다. 결과는 `results_synthetic/`에만 쓴다. 실제 형식은 Phase 0의 `DATA_FACTS.md`를 따른다.
- 테스트: §9 예제 수치, 합성 신호 걸음 검출, 제외 규칙 경계, 곡 구간 계산(순환·`start_song`), 단위·부호 판별, 시범 파일 QA 실행, 좌표 열이 `results/`에 없는지, 배정표 재현.
- 로그에는 좌표와 기기 이름을 찍지 않는다.

## 11. 개인정보와 데이터 취급

- 저장소는 **비공개**로 둔다. `data/raw/`, `data/interim/`, `data/private/`는 git에서 제외한다.
- `Location.csv`에는 집·학교가 이어지는 평소 길이 그대로 들어 있다. 좌표는 속도·거리 계산에만 쓰고 결과·로그·그림·커밋에 남기지 않는다. 테스트가 이를 확인한다.
- 기기 이름 같은 식별 정보는 문서와 결과에 쓰지 않는다(기종 정도만).
- 보강 N 참가자(친구)의 데이터는 동의 범위 안에서 ID(N1–N4)로만 다룬다.
- 합성 데이터의 좌표는 0 근처 가짜 값으로 만든다.

## 12. 단계(Phase)와 완료 기준

| Phase | 기간 | 내용 | 완료 기준 |
|---|---|---|---|
| 0 | 11/7–11/8 | 시범 zip에서 데이터 사실 확인 | §3.2의 항목이 `DATA_FACTS.md`에 값 또는 '해당 없음'으로 채워짐. 가정이 틀린 곳은 `DECISIONS.md`에 |
| 1 | ~11/12 (G1) | 뼈대, 불러오기, QA, 걸음 검출 초안, 합성 데이터 생성기 | `pytest` 통과(§9 + 합성 신호), 시범 파일 QA 리포트, `qa --gate G1`이 합성 데이터에서 동작하고 11/12까지 들어온 실제 1–2회차 파일(6개)로도 표를 냄 |
| 2 | ~11/18 (G2) | 실험 1 곡 구간 지표, PC, 판정, 시나리오 신호, 그림 2·3 | 실제 회차(1인 7회 이상)에 `all`이 한 번에 돌고 `hypotheses.csv`·`g2_flags.csv`가 나옴 |
| 3 | 11/14 데이터 → ~11/18 | 실험 2·3 | `exp2_*`, `exp3_swings.csv`, 그림 6·7 |
| 4 | ~11/24 (G3) | 전체 표·그림, 데이터 표 v1.0 동결 | `freeze --version 1.0`, 핵심 그림 4장 |
| 5 | 11/24 이후, **사용자가 요청할 때만** | 웹 데모(같은 파이썬 코드를 재사용, 예: Streamlit) | 별도 계획 |

각 Phase 시작 전에 계획을 보여주고 승인을 받는다. 끝나면 CLAUDE.md의 보고 순서를 따른다.
