# SPEC — 분석 명세 v0.3

작성 2026-11-07, 2026-11-08 수정(프로토콜 11/8 수정판 반영: §2, §3, §5.2–5.5, §7, §12, DECISIONS D-27–D-32), 2026-11-09 수정(실험 2·3 추가 측정과 결과 전 기준 반영: §2–§9, §11, §12, DECISIONS D-33–D-42, 손계산 노트 `docs/HANDCALC.md`) · 읽는 사람: Claude Code(구현), B(데이터 담당), A(팀장)

이 문서는 팀 문서 「내 플레이리스트가 걸음을 바꾼다 — 프로젝트 통합본」의 연구계획·실험 1 프로토콜·실행 스케줄 탭에서 분석 코드에 필요한 부분만 뽑아, 코드가 바로 쓸 수 있게 고쳐 쓴 것이다. [확정] 표시가 붙은 값은 원문 그대로다. 원문 사이(예: 연구계획과 프로토콜)나 원문과 이 문서가 어긋나는 곳은 `DECISIONS.md`에 적고, 사용자가 정하기 전까지는 이 문서의 [초안] 값을 쓴다.

## 0. 읽는 법

- **[확정]** 연구계획서·프로토콜에 있는 정의와 기준. 결과를 보기 전에 정해 둔 것이라 코드가 바꾸지 않는다. 바꿔야 하면 멈추고 사용자에게 묻는다.
- **[초안]** 계획서에 없거나 모호해서 이 문서가 정한 기본값. `DECISIONS.md`에 번호(D-xx)가 있고 B가 DECISIONS의 '먼저 정할 것'에 적힌 날짜 전에 확인한다. 실제 데이터를 본 뒤에는 바꾸지 않는다.
- **[확인 필요]** 실제 파일을 열어 봐야 아는 사실. Phase 0에서 확인해 `DATA_FACTS.md`에 적는다.
- 임계값과 파라미터는 `config/params.toml`의 키 이름으로 가리킨다(예: `exclude.edge_s`).
- §9의 예제 수치는 그대로 테스트가 된다. 손계산 노트(`docs/HANDCALC.md`)의 숫자도 §9에 들어 있어서, 발표·부록의 손계산과 코드 결과가 같은지를 테스트가 확인한다.
- 단계는 Phase 0–5(§12), 판단 관문은 G1 11/12 · G2 11/18 · G3 11/24 · G4 11/28이다.

## 1. 목표와 범위

**목표.** Sensor Logger zip → 품질 점검(QA) → 걸음 검출 → 지표 → 가설 판정·그림·표. 전체를 명령 한 줄로 다시 만들 수 있어야 한다.

**성공 기준**

1. G1(11/12): 셋 다 1–2회차 파일(6개)을 QA로 자동 판정한다.
2. G2(11/18): 분석 고정 태그(§6 '분석 고정')를 붙인 뒤 실험 1 지표(1인 7회 이상), 무음 케이던스 변동계수와 실질적 변화 기준(§4.5), 시나리오 신호(§5.9)를 낸다.
3. G3(11/24): 데이터 표 v1.0(동결)과 핵심 그림 4장(그림 2, 3b, 6, 7), 측정 검증표(§5.10), 처방 범위(§4.5).
4. 그 뒤: 논문의 표·그림 전부를 다시 만든다.

**범위 밖.** 웹/앱(Phase 5, 사용자가 요청할 때만), phyphox 백업 파일 읽기(Sensor Logger가 실패해 실제로 쓰게 될 때만 추가), 실시간 처리, 영상 자동 분석(영상에서 사람이 읽은 값은 CSV로 받는다), 집단 검정, 의학적 해석, 데이터를 외부로 보내는 모든 것.

## 2. 연구 설계 요약 (분석 관점)

| | 실험 1 · 일상 보행 | 실험 2 · 템포 챌린지 | 실험 3 · 다리 진자 |
|---|---|---|---|
| 사람 | A·B·C (+ 보강 N1–N4는 별도 표, D-17) | A·B·C | A·B·C |
| 조건 | 무음 3 + 플레이리스트 P1–P4 각 3 = 1인 15회 | PC의 100·120·135·150·165% 음원, 단계마다 2회, 방향 번갈아. 165%에서도 걸으면 그 자리에서 180·195% 1회씩. 끝에 수직 점프 3회 | 정강이 폰, 다리 힘 빼고 곧은 다리 3회 + 무릎 90° 굽힌 다리 3회 |
| 한 번 | 평소 길 8분 이상 | 40 m 코스(가운데 30 m 분석) | 흔들기 |
| 지시 | 없음 | 박자 하나에 한 발씩, 걷든 뛰든 | 힘 빼고 흔들기 |
| 폰 | 허리 파우치, 등 쪽·가로·셋 다 같게 | 허리 파우치 | 정강이 밴드 |
| 파일 이름 | 내보낸 이름 그대로 올림. `walk_id` `E1_<사람>_<회차2자리>_<조건>_<MMDD>`는 분석 쪽이 붙임(§3.4) | `E2_<사람>_<비율>_<반복>`, 점프 `E2_<사람>_J_1` | `E3_<사람>_<반복>`, 굽힌 다리 `E3_<사람>_K_<반복>` |
| 날짜 | 11/9–11/22 | 11/14(예비 11/15) | 11/14 |
| 주 산출 | 곡 구간 지표, 처방 범위 하한(§4.5) | 단계 지표(동조율, 체공, Fr, 달리기 접촉 시간·다리 강성), 점프(높이·이륙 속도·충격량), 처방 범위 상한 | 흔들림 주기 P(곧은 다리)와 P_K(굽힌 다리), 진자 에너지 |

**가설과 사람별 판정 기준 [확정]** (연구계획 2.2·2.4). n=3이므로 사람마다 판정하고, 3명 중 2명 이상에서 같으면 '지지'다(가설 4만 3명 모두).

| 가설 | 내용 | 한 사람에서 '지지'의 기준 |
|---|---|---|
| H1 | 곡 BPM이 PC ±10% 안이면 지시 없이도 걸음이 박자 쪽으로 끌려간다 | 곡 구간 단위 Spearman ρ(T, ΔC%) > 0 이고 p < 0.05, 그리고 PC ±`sync.near_pc_pct`(10%) 안의 곡에서 동조율이 그 밖의 곡보다 높다 |
| H1-2 | 박자에 맞추라고 하면 +20%까지 맞춘다 | 실험 2의 100%와 120% 단계 각각에서 ±`sync.tol_pct`(3%) 안 걸음이 `exp2.h1_2_min_sync_frac`(80%) 이상 [초안 D-10] |
| H2 | 빠른 곡일수록 더 빨리·큰 보폭으로 걷고 충격이 크다. 억지로 맞추면 걸음 변동성이 더 크다 | ρ(T, 속도), ρ(T, 보폭), ρ(T, 충격)이 양수면 '증가 경향'. 변동성은 같은 템포의 실험 1과 실험 2를 비교 |
| H3 | 템포를 올리면 어느 지점에서 달리기로 바뀌고, 그 지점이 Fr ≈ 0.5 | '마지막으로 걸은 단계'와 '처음 체공이 생긴 단계' 사이에 Fr 0.5가 들어간다 |
| H4 | 곧게 편 다리 진자의 예측 케이던스는 실측 PC보다 느리다 | 3명 모두에서 C_pend < PC. 흔들림 주기 예측-실측 평균 오차 15% 이내면 모델 타당 |
| 보조 | 무릎을 굽히면 다리 진자의 주기가 짧아진다(관성모멘트 감소) | 판정하지 않는다(`hypotheses.csv`에 넣지 않음). 사람마다 P_K < P인지와 실측 비율 P_K ÷ P를 분절 모델 비율 P_seg(φ) ÷ P_seg(0)(§4.4)과 나란히 보고 [초안 D-41] |
| 탐색 | 같은 BPM 구간에서 좋아하는 곡이면 더 빨리 걷는가 | 판정하지 않고 구간 안 순위 상관만 보고 |

## 3. 입력 데이터

### 3.1 Sensor Logger Zipped CSV

Sensor Logger는 기록 하나를 zip으로 내보낸다. 앱 공식 문서(awesome-sensor-logger)에서 확인된 사실:

- 켠 센서마다 CSV 하나: `Accelerometer.csv`, `Gyroscope.csv`, `Gravity.csv`, `Location.csv`, `Metadata.csv`. 걸음 수는 `Pedometer.csv`일 것으로 추정한다 [확인 필요]. 11/8부터 보정 안 한 가속도계·자이로스코프(Uncalibrated)도 켜므로 파일이 더 있다. 파일 이름과 열 이름은 [확인 필요]이고, 지금은 기록만 하며 파이프라인은 읽지 않는다(쓰려면 DECISIONS.md D-32에 먼저 적는다).
- 시간 열: `time` = UNIX epoch 나노초(UTC), `seconds_elapsed` = 기록 시작부터의 초.
- 가속도·자이로·중력: `x, y, z`.
- 위치: `latitude, longitude, altitude, speed, speedAccuracy, bearing, bearingAccuracy, horizontalAccuracy, verticalAccuracy`. GPS 속도에는 오차가 있고 `speedAccuracy`가 그 크기다. 속도 단위는 문서에 없다 [확인 필요].
- `Metadata.csv`: version, device name, recording time, platform, platform version, appVersion, recording timezone, recording epoch time, standardisation. 옛 기록에는 일부 열이 없다.
- 압축 파일 이름의 시각도 UTC다(A가 11/8에 확인한 내용이며 실제 파일로 다시 확인한다 [확인 필요]). 그래서 날짜·시각을 파일 이름에서 읽지 않는다. 기록 시작 시각은 `Metadata.csv`와 센서 `time`에서 구해 Asia/Seoul로 바꾼다(§5.1).
- 센서는 고르게 샘플링되지 않는다. 간격이 흔들리는 것이 정상이다.

### 3.2 Phase 0에서 확인할 것 [확인 필요]

1. 실제 압축 파일 목록과 센서별 열 이름(Uncalibrated 파일이 있으면 그 이름과 열 이름도).
2. Accelerometer가 중력을 포함하는가, 단위가 g인가 m/s²인가. 판별법은 §5.2.
3. Gravity의 단위와 부호(가속도와 같은 방향인가 반대인가).
4. Gyroscope 단위(rad/s로 가정).
5. Pedometer: 파일이 있는가, 열 이름, 누적 값인가 구간 값인가, 갱신 간격.
6. Location: 갱신 간격, `speed` 단위(m/s로 가정), `speedAccuracy`·`horizontalAccuracy` 분포.
7. 센서별 첫·마지막 `time`의 차이, 실제 샘플링 간격(중앙값, 5·95 백분위, 최대), 끊김.
8. `Metadata.csv` 내용. 'recording epoch time'을 기록 시작 시각으로 쓸 수 있는가.
9. iOS와 Android 모두 있으면 둘의 차이.
10. 압축 파일 이름의 시각이 UTC인지: 이름의 시각을 Metadata의 recording epoch time, 센서 첫 `time`과 비교한다.

결과는 `DATA_FACTS.md`에 적고, 이 문서의 가정과 다르면 `DECISIONS.md`에 적은 뒤 사용자에게 알린다.

### 3.3 메타데이터 CSV

`data/README.md`에 열마다 설명이 있다. 요약:

| 파일 | 내용 | 누가 채우나 |
|---|---|---|
| `assignment.csv` | 회차 배정표(고정). `tools/assign.py`로 재현 | 생성 완료 |
| `manifest.csv` | 기록지 내보내기, 회차당 1줄. 날짜·시작 시각으로 zip과 연결(§3.4) | 걷는 사람, A가 점검 |
| `participants.csv` | 나이·키·체중·다리 길이·허벅지·정강이 길이·폰 | 각자 |
| `music_bpm.csv` | 곡 12+2: BPM, **곡 길이(`duration_s`)** | C |
| `song_ratings.csv` | 곡별 좋아하는 정도·아는 정도(1–5) | 각자 |
| `exclusions.csv` | 수동 제외 구간(계단·인파·폰 만짐) | 걷는 사람 |
| `exp2_trials.csv` | 챌린지 기록지(통과 시간, 걸음 수, 걷기/뛰기). 180·195% 단계와 점프 기록(`ratio_pct=J`)도 한 줄씩 | 현장 기록 담당 |
| `exp3_swings.csv` | 진자 시행 목록(곧은·굽힌 다리) | 현장 |
| `video_checks.csv` | 영상에서 사람이 읽은 시간 값: 점프 체공 프레임 수, 진자 10번 흔들림 시간, (선택) 달리기 접촉·체공 프레임 수 | 카메라 담당의 메모를 B가 옮김 |
| `video_markers.csv` | 영상 프레임의 테이프 마커 픽셀 좌표(대전자·무릎·바깥 복사뼈): 착지 순간, 굽힌 다리 진자 | B 또는 C |
| `debrief.csv` | 종료 설문(15회를 마친 뒤 한 번) | 각자 |
| `private/sections.csv` | 측정 구간 웨이포인트(좌표). git 제외 | 각자 |

### 3.4 파일 이름과 manifest

- 코드는 파일 이름이 아니라 manifest를 기준으로 한다. 걷는 사람은 파일 이름을 바꾸지 않는다. Sensor Logger가 내보낸 이름 그대로 올린 zip을 `data/raw/<사람>/`에 둔다(드라이브의 '실험1/사람' 폴더를 내려받은 것). 원본 이름의 시각이 UTC라서 사람이 날짜를 베끼면 틀리기 때문이고, 사람은 기록지에 날짜와 기록 시작 시각(시:분)만 정확히 적는다 [확정, 11/8].
- **zip 연결 [초안 D-27].** 분석 쪽이 zip의 기록 시작 시각(UTC → Asia/Seoul)을 같은 사람의 manifest 줄 `date`·`start_time`과 맞춘다. 차이가 `manifest.start_time_tol_s` 이내이고 일대일이어야 한다. 코드는 manifest를 고치지 않고 연결 제안을 `results/zip_links.csv`로 낸다. 확인한 사람이 manifest `zip_file`에 원본 이름을 적는다. 맞는 줄이 없거나 둘 이상이면 연결하지 않고 보고한다. 연결이 틀리면 QA 실패(Q10).
- **`walk_id`는 코드가 만든다 [초안 D-27].** 실험 1: `E1_<사람>_<회차 2자리>_<조건>_<MMDD>`(MMDD는 manifest `date`), 무음은 `S`. 예: `E1_B_07_P1_1113`, `E1_A_01_S_1109`. 다시 한 회차는 16부터. 이름에 시작 곡(①②③)이 없으므로 `start_song`은 manifest에서 읽는다. manifest의 `walk_id` 열은 비워 두거나 같은 값이어야 한다.
- 사전 점검(11/8) 기록은 `experiment=TEST`다. `walk_id` = `TEST_<사람>_<MMDD>_<종류>`, 종류는 `rehearsal`(10분 리허설) 또는 `steps100`(100걸음)이고 같은 날 같은 종류가 또 있으면 `_2`를 붙인다. 11/7 시범은 `TEST_A_1107` 그대로 둔다.
- 실험 2: `E2_<사람>_<비율>_<반복>` (예: `E2_A_150_2`), 무음 시행은 비율 자리에 `S`. 165%에서도 걸은 사람이 현장에서 더 한 단계는 `E2_A_180_1`, `E2_A_195_1`이다. 수직 점프 3회는 기록 하나로 `E2_<사람>_J_1`이다. 실험 3: 곧은 다리 `E3_<사람>_<반복>`, 무릎 굽힌 다리 `E3_<사람>_K_<반복>`(예: `E3_A_K_2`). 이 둘은 이름에 날짜가 없고 `exp2_trials.csv`·`exp3_swings.csv`의 `zip_file`이 파일을 가리킨다. 영상에서 읽은 값(`video_checks.csv`, `video_markers.csv`)은 같은 `trial_id`로 잇는다.

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
| 몸 중심 수직 변위 h_com | 걸음마다(발 디딤 i ~ i+1) (a_v,total − 1) × g에서 그 걸음 안의 평균을 빼고 적분해 속도, 속도에서 다시 평균을 빼고 적분해 위치를 구한 뒤 위치의 최고 − 최저. 구간 값은 중앙값 [초안 D-40] | m |
| 역진자 보폭 SL_ZH | 몸 중심이 다리 길이 l의 원호를 그린다고 보고 h_com에서 한 걸음의 길이를 구한다(Zijlstra & Hof, 2003). l = `participants.leg_length_m`, K = `com.zh_correction`(1.0, 보정하지 않음). GPS 보폭 SL과의 비를 측정 검증(§5.10)에 낸다 [초안 D-40] | SL_ZH = K · 2√(2 l h_com − h_com²) (m) |
| 평균 수직 가속도 ā_v | 유효 창 안 a_v,total의 평균. 등속으로 걸으면 한 걸음 동안 (지면반력 − 체중)의 충격량이 0이므로 1 g가 되어야 한다. 단위·방향 판별의 점검값 [초안 D-38] | g |

### 4.4 실험 2·3 [확정]

| 이름 | 정의 | 식·단위 |
|---|---|---|
| 체공 | 두 발이 모두 땅에서 떨어진 구간. 총 가속도 크기 < `flight.a_thresh_g`(0.2 g)가 `flight.min_duration_s`(30 ms) 이상 이어진 구간. 영상으로 확인 | 체공 시간 t_f (s) |
| 몸 중심 상승 높이 h | | h = g · t_f² ÷ 8 (m) |
| Froude 수 Fr | 속도를 다리 길이로 표준화 | Fr = v² ÷ (g · L), L = 대전자~바닥 높이(m), g = `constants.g`(9.81) |
| 다리 흔들림 주기 P, P_K | 정강이 자이로 주축 각속도의 같은 방향 봉우리 간격의 중앙값. 곧은 다리는 P, 무릎 굽힌 다리는 P_K | s |
| 진자 예측 케이던스 C_pend | | C_pend = 60 ÷ (P ÷ 2) = 120 ÷ P (걸음/분) |
| 진자 모델 주기 P_model | 곧게 편 다리를 물리 진자로 본 이론값. 회전반경 k = `pendulum.k_over_L`(0.560) L, 질량중심 d = `pendulum.d_over_L`(0.447) L (Winter) [초안 D-06] | P_model = 2π √(k² ÷ (g · d)) |
| 주기 오차 | | (P − P_model) ÷ P_model × 100 (%) |
| 분절 진자 모델 P_seg(φ) | 허벅지와 '정강이+발' 두 분절로 본 물리 진자. φ는 무릎 굽힘 각(곧은 다리 0°). 허벅지: 질량 0.100 M, 엉덩관절에서 질량중심까지 0.433 l_t, 질량중심 기준 회전반경 0.323 l_t. 정강이+발: 질량 0.061 M, 무릎에서 질량중심까지 0.606 l_s, 회전반경 0.416 l_s(Dempster·Winter, `pendulum.seg_*`). l_t = 허벅지 길이(대전자 → 무릎 관절선), l_s = 정강이 길이(무릎 관절선 → 바깥 복사뼈), M = 체중. 엉덩관절을 원점, 허벅지를 x축으로 두면 정강이+발 질량중심은 (l_t + 0.606 l_s cos φ, 0.606 l_s sin φ) [초안 D-41] | I_hip = Σ m_i (k_i² + r_i²)(평행축 정리), d = 엉덩관절 → 두 분절 전체 질량중심, P_seg = 2π √(I_hip ÷ (m g d)), m = 두 분절 질량의 합 |
| 주기 비율 | 무릎을 굽히면 얼마나 빨라지나 | 실측 P_K ÷ P, 모델 P_seg(φ) ÷ P_seg(0) |
| 진자 에너지 | 흔들림 꼭대기의 위치에너지가 바닥에서 회전 운동에너지가 된다. 진폭 θ_amp는 자이로 각속도를 적분한 각도에서 반 주기마다 (최고 − 최저) ÷ 2 [초안 D-41] | ω_pred = √(2 m g d (1 − cos θ_amp) ÷ I_hip), 실측은 자이로 봉우리 ω_peak (rad/s) |

### 4.5 실질적 변화 기준과 처방 범위 [초안 D-33, D-36. G1 전에 확정하고, 결과를 본 뒤에는 바꾸지 않는다]

| 이름 | 정의 | 식·단위 |
|---|---|---|
| 실질적 변화 기준 SESOI | 사람마다 '날마다 흔들리는 폭'. 무음 회차 C(회차 단위)의 변동계수. `stats.sesoi_floor_pct`(1%)보다 작으면 1%를 쓴다. 무음이 3회 미만이면 임시 값 | SESOI = max(100 × SD ÷ 평균, 1) (%), SD는 ddof=1 |
| 실질적 변화 | 케이던스 변화율이 SESOI 밖인가. 곡 구간, 플레이리스트 평균, 실험 2 단계마다 붙인다 | \|ΔC%\| > SESOI이면 `meaningful_up`(빨라짐) 또는 `meaningful_down`(느려짐), 아니면 `within_band` |
| 처방 범위 하한 T_low | 실험 1에서 플레이리스트 평균 ΔC%가 +SESOI를 넘은(빨라진) 플레이리스트 가운데 플레이리스트 평균 T가 가장 낮은 것의 평균 T. 평균 T가 100% 이하인 플레이리스트는 보지 않는다 | % (PC 대비) |
| 처방 범위 상한 T_high | 실험 2 단계를 T 순서로 놓고(180·195%를 했으면 포함), 처음으로 S3 < `exp2.h1_2_min_sync_frac`(80%)가 된 단계 바로 앞 단계의 T. 단계 S3는 그 단계 시행들의 평균. 100% 단계부터 80% 미만이면 없음 | % (현장 PC 대비, D-04) |
| 처방 범위 | 사람마다 'PC의 T_low–T_high%'와 그 사람 PC로 바꾼 BPM 범위. T_low가 없으면 범위 대신 "듣기만으로는 걸음이 바뀌지 않고, 박자에 맞춰 걷겠다는 의도가 필요하다"를 적는다. T_low > T_high이면 둘 다 적고 `flags=inconsistent` | `prescription.csv` |

### 4.6 점프와 달리기 스프링 [식은 확정(연구계획 3.4–3.7, 11/9), 검출 세부는 초안 D-37, D-39]

| 이름 | 정의 | 식·단위 |
|---|---|---|
| 점프 체공 t_f | 이륙 ~ 착지. 총 가속도 크기 < `flight.a_thresh_g`(0.2 g)가 `jump.min_flight_s`(0.20 s) 이상 이어진 구간 | s |
| 점프 높이 h | 이륙 때와 착지 때 몸 중심 높이가 같다고 본다 | h = g t_f² ÷ 8 (m) |
| 이륙 속도 v_flight | 체공 시간에서 | v = g t_f ÷ 2 (m/s) |
| 이륙 속도 v_int | 점프 전 가만히 선 구간(`jump.quiet_s` 이상, \|a_v,total − 1\| ≤ `jump.quiet_tol_g`)의 끝부터 이륙까지 (a_v,total − 1) × g를 적분한다. 1 g는 그 가만히 선 구간의 평균으로 다시 맞춘다 | m/s |
| 순충격량 J | 이륙 전 (지면반력 − 체중)의 충격량 = 운동량 변화 | J = m v (N·s) |
| 운동에너지 | 이륙 순간 | ½ m v² = m g h (J) |
| 밀기 구간 t_push | 적분 속도가 마지막으로 0을 아래에서 위로 지난 시각(가장 낮은 자세) ~ 이륙 | s |
| 밀기 평균·최대 지면반력 | 밀기 구간 a_v,total의 평균과 최댓값. 평균은 1 + v_int ÷ (g t_push)와 같다 | BW |
| 달리기 접촉·체공 | 실험 2 달리기 단계에서 걸음마다 체공 이벤트(§4.4)의 길이 t_f와 접촉 t_c = 걸음 간격 − t_f. 단계 값은 중앙값 | s |
| 최대 지면반력 F_max | 접촉 중 지면반력을 반 사인파로 본 근사(Morin et al., 2005) | F_max = m g (π ÷ 2)(t_f ÷ t_c + 1) (N, BW) |
| 몸 중심 하강 Δy | | Δy = F_max t_c² ÷ (m π²) − g t_c² ÷ 8 (m) |
| 다리 압축 ΔL | L = `participants.leg_length_m`, v = 30 ÷ t30 | ΔL = L − √(L² − (v t_c ÷ 2)²) + Δy (m) |
| 수직 강성 k_vert, 다리 강성 k_leg | | k_vert = F_max ÷ Δy, k_leg = F_max ÷ ΔL (kN/m) |
| 탄성에너지 | 다리 스프링에 저장되는 에너지 | ½ k_vert Δy² (J) |
| 접촉 중 평균 지면반력 | 한 걸음(t_c + t_f) 동안의 충격량이 체중의 충격량과 같다 | BW × (t_c + t_f) ÷ t_c |
| 달리기 이륙 각 | 한 걸음의 체공을 포물선으로 본다 | v_y = g t_f ÷ 2, θ = arctan(v_y ÷ v), 공중 거리 = v t_f |

## 5. 처리 파이프라인

흐름: `zip → 불러오기(5.1) → 단위·부호 판별(5.2) → 자세 분해(5.3) → 걸음 검출(5.4) → 구간 나누기(5.5) → 지표(5.6–5.8) → 판정(§6) → 출력(§7) → 그림·표(§8)`.

### 5.1 불러오기와 시간축

- zip은 `data/raw/`에서 풀지 않고 읽거나, 풀 때는 `data/interim/<walk_id>/`에 푼다.
- `time`(ns, UTC)을 시각으로 바꾸고 `time.timezone`(Asia/Seoul, D-16)으로 보여 준다. zip 이름의 시각은 읽지 않는다(§3.4). 센서 사이의 공통 시간축 t_s = (time − 기록 시작) ÷ 1e9. 기록 시작은 `Metadata.csv`의 recording epoch time이 쓸 만하면 그 값, 아니면 모든 센서 파일의 첫 `time` 중 최솟값 [확인 필요, D-20].
- 샘플 간격은 불규칙하다. 간격 분포를 기록하고, 필터링 전에는 중앙 간격의 균일 격자로 선형 보간한다. 보간은 `qa.gap_warn_s`보다 긴 끊김을 가로지르지 않는다(끊김 앞뒤를 따로 처리).
- 파일 하나가 비거나 열이 다르면 조용히 넘어가지 말고 QA에 실패로 남긴다.

### 5.2 단위와 부호 판별

가정하지 않고 데이터로 판별한다. 판별에 실패하면 멈추고 알린다.

- 단위와 중력 포함 여부: **서 있는 구간**에서 ‖(x, y, z)‖의 중앙값으로 판단한다. 서 있는 구간은 기록의 맨 앞이 아니다. 11/8 절차는 출발점에서 기록을 시작하고 음악을 틀고 폰을 파우치에 넣은 다음 그 자리에서 `qa.standing_check_s`(10 s) 가만히 서는 순서라서, 기록 처음 수 초는 폰을 만지는 움직임이다. 그래서 첫 지속 보행(§5.5a) 바로 앞의 가만한 창을 쓴다. 도착 쪽은 마지막 지속 보행 바로 뒤의 창이다. 이 창은 단위를 모르는 상태에서도 찾을 수 있게 자이로 크기와 가속도 벡터의 변화가 작은 창으로 정한다. 구체적인 방법은 구현이 정하고 근거를 `DATA_FACTS.md`에 적는다 [초안 D-29]. 약 1이면 g 단위이고 중력 포함, 약 9.8이면 m/s²이고 중력 포함, 0 근처면 중력 제외 신호다(이때 단위는 같은 구간 Gravity 크기가 약 1인지 약 9.8인지로 정한다). 서 있는 구간이 없으면 걷는 동안의 중앙값으로 대신하되 확신이 낮다고 표시한다(중력 제외 신호도 g 단위로는 걷는 동안 1 근처가 될 수 있다). 내부 계산은 g로 통일한다.
- 총 가속도: 중력 포함 신호는 그대로 쓴다. 중력 제외 신호이면 Accelerometer와 Gravity를 더해 만든다. 부호 규칙은 Phase 0에서 확인해 DECISIONS.md에 적는다. 합친 뒤 걷는 동안 a_v,total이 1 g 아래보다 위로 더 크게 벗어나는지(발 디딤 충격이 위쪽 피크인지)를 상식 점검으로 확인한다.
- 방향: '위'는 서 있는 구간 평균 벡터의 방향으로 정의해 a_v,total이 서 있을 때 +1 g가 되게 한다. 플랫폼마다 부호 규칙이 달라도 같은 값이 된다.
- 판별 결과(`units`, `includes_gravity`, `gravity_combine_sign`)를 회차마다 QA 결과에 남기고, 사람·회차 사이에 달라지면 경고한다.

### 5.3 자세 분해

폰이 파우치에서 기울어도 쓸 수 있게 몸 기준 방향으로 나눈다. 폰 위치·방향은 11/8부터 규칙으로 정해졌지만(등 쪽, 가로, 셋 다 같게) 코드는 특정 축 배치를 가정하지 않고 서 있는 구간의 중력 방향으로 û를 구한다.

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
  2. 직접 센 걸음 수가 있으면 ± `qa.hand_count_tol_steps`(2) 안. 기준 사례는 사전 점검의 100걸음 기록(`condition=steps100`)이다. 기록 시작 → 폰 넣기 → 10초 서기 → 100걸음 → 10초 서기 순서라서 지속 보행 하나가 곧 100걸음이다.
  3. (참고) Pedometer가 있으면 걸음 수 차이를 함께 보고한다. 11/8 사전 점검에서 앱의 걸음 수가 직접 센 100걸음을 128로 세었으므로 수용 기준이 아니라 참고값이다 [초안 D-30].
  4. 보조 검증: 좌우(ML) 축 스펙트럼의 주 피크가 걸음 주파수의 절반(두 걸음, 곧 한 보에 한 번 흔들림)에 있는지.
- 한 사람의 15회에 같은 매개변수를 쓴다. 회차마다 튜닝하지 않는다.

### 5.5 구간 나누기와 제외

**(a) 보행 묶음과 유효 창.** 걸음 간격이 `exclude.stop_gap_s`(2.0 s) 이하로 이어진 걸음들을 한 보행 묶음으로 본다. 걸음 `exclude.min_bout_steps`(10)개 이상인 묶음이 지속 보행이다 [초안 D-21]. t_depart = 첫 지속 보행의 첫 걸음, t_arrive = 마지막 지속 보행의 마지막 걸음. **유효 창 = [t_depart + 20 s, t_arrive − 20 s]** (`exclude.edge_s`). 폰을 넣거나 꺼내는 움직임이 걸음으로 잡혀도 10걸음 이상 이어지지 않는 한 t_depart·t_arrive에 들어가지 않는다.

**(b) 정지.** 간격이 2.0 s를 넘는 걸음 쌍은 이어진 구간이 아니므로 그 간격과 앞뒤 `exclude.stop_pad_s`를 제외한다 [초안 D-19]. 측정 구간 시작·끝에서 일부러 멈추는 2초(11/8부터 매 회차)는 걸음 간격이 2.0 s 안팎이 되어 이 규칙의 정지로 제외되는 경우가 많다. 경계에 걸리는 경우의 처리는 D-28에서 정한다.

**(c) 수동 제외.** `data/exclusions.csv`의 (walk_id, start_s, end_s) 구간(계단·인파 등)과, 폰을 만진 시각(`reason=phone_touch`)은 앞뒤 `exclude.phone_touch_pad_s`를 제외한다. manifest의 `notes`는 자유 서술이라 코드가 해석하지 않는다. `notes`가 있는데 `exclusions.csv`에 그 walk_id가 없으면 QA가 INFO로 알린다.

**(d) 곡 구간 (실험 1).**

- 첫 곡 재생 시각 = 기록 시작 + `music_offset_s`(manifest 값, 없으면 `music.default_offset_s`). 11/8 절차는 기록을 시작한 직후 폰 화면에서 음악을 튼다. 재생 직전의 화면 조작 움직임이 센서에 남는지, 오프셋 추정에 쓸 수 있는지는 사전 점검·1–2회차 파일을 보고 G1 전에 B가 정한다 [열림, D-31].
- 재생 순서: manifest `songs_played`가 있으면 그 순서를 쓴다(프로토콜: "분석은 실제로 들은 곡 기준"). 없으면 플레이리스트의 곡 번호 [1, 2, 3]을 `start_song`부터 순환한다(전체 반복). 곡 순서를 알 수 없는 회차(`status=no_song_segments`)는 곡 구간을 계산하지 않고 회차 단위 지표만 쓴다.
- 곡 k의 시작 = 첫 곡 재생 시각 + 앞 곡들의 `duration_s` 합. `duration_s`가 비어 있으면 **추측하지 말고 멈추고 알린다.**
- 유효 곡 구간 = [곡 시작 + 10 s, 곡 끝 − 10 s](`exclude.boundary_s`) ∩ 유효 창 − (b)·(c)의 제외.
- 유효 걸음이 `qa.min_valid_steps_per_segment`(30)보다 적은 구간은 지표를 내지 않는다(`flags=few_steps`) [초안 D-08].
- 무음 회차는 유효 창 전체가 구간 하나다.
- 민감도: `music_offset_s`를 ± `music.offset_sensitivity_s`만큼 옮겨 다시 계산한 결과를 `sensitivity.csv`에 남긴다.

**(e) 측정 구간 통과 (속도 검증용).** `data/private/sections.csv`의 웨이포인트(시작→끝)에 위치 점을 투영해 시작·끝 통과 시각을 선형 보간으로 구한다(`speed.section_radius_m` 안에서만 인정). 방향이 반대(오는 길)면 통과 순서로 시작·끝을 정한다. v_section = `participants.section_distance_m` ÷ (t_out − t_in). 좌표는 이 계산에만 쓰고 출력에는 시각·거리만 남긴다. GPS가 튀어 거리 차가 `qa.gps_distance_tol_pct`를 넘는 회차는 지도 거리 ÷ 통과 시간으로 속도를 구한다. 이때 통과 시각은 구간 시작·끝에서 걷는 사람이 멈춘 약 2초(걸음이 끊긴 구간)에서 찾고 `flags=section_by_stops`를 붙인다 [초안 D-26]. 11/8부터는 모든 회차가 측정 구간 시작·끝에서 2초씩 멈추므로 이 표식을 어느 회차에서나 찾을 수 있다. 기본은 계속 GPS 통과 시각이고, 멈춤 표식은 GPS가 튄 회차의 대안이자 모든 회차의 교차 확인값이다. 둘의 차이는 `qa/<walk_id>.json`에 남기고, 어느 쪽을 기본으로 삼을지는 사전 점검·1–2회차 파일을 보고 G1 전에 B가 정한다 [열림, D-28].

### 5.6 실험 1 지표

곡 구간마다(`segments.csv`), 회차마다(`walks.csv`), 사람마다(`participants.csv`) 계산한다.

- **구간:** n_valid_steps, valid_duration_s, C(중앙값), cadence_rate_spm, T, ΔC%, R, S3, S5, S3_half, S3_double, sub/super 표시, CV, 충격 F/BW(중앙값)와 상대값, μ_req(중앙값), 속도, 보폭.
- **속도·보폭 [초안 D-01].** 계획서 4.6은 측정 구간 통과 속도를, 4.7은 곡 구간(1인 30여 개) 단위 상관을 쓴다. 한 회차에 구간 통과는 한 번뿐이라 곡 구간 단위에는 쓸 수 없으므로 다음과 같이 둘을 함께 쓴다.
  - **기준값**: 곡 구간의 Doppler 속도(`Location.csv`의 `speed`, 속도 정확도 `speed.doppler_max_speed_accuracy_ms` 이하인 샘플)의 중앙값. 보폭 SL = v ÷ (C ÷ 60).
  - **검증값**: 회차마다 v_section(5.5e). 같은 회차의 Doppler 중앙값과 비교해 상대 차이를 `walks.csv`에 남긴다. 차이가 `speed.mismatch_tol_pct`(5%)를 넘는 회차는 `flags=speed_mismatch`.
- **PC:** 사람마다 무음 회차의 회차 단위 C를 평균한다. 무음이 3회 미만이면 `pc_provisional=true`, 무음 회차 수 n_silent를 함께 낸다. 사람마다 무음 C의 변동계수도 낸다(G2).
- T는 PC가 있어야 계산된다. PC가 임시 값이면 T·ΔC%·R도 `provisional`로 표시한다.
- **회차:** 유효 창 전체의 C, cadence_rate, CV, 속도, 걸음 수(검출/Pedometer/직접 센 값), QA 상태, 날씨·서두름·가방.
- **몸 중심과 역진자 보폭 [초안 D-40]:** 곡 구간과 회차마다 h_com(중앙값)과 SL_ZH, 회차마다 ā_v(§4.3)를 낸다. 판정에는 쓰지 않고 측정 검증(§5.10)에 쓴다.
- **실질적 변화 [초안 D-33]:** 사람마다 SESOI(§4.5)를 `participants.csv`에 내고, 곡 구간과 플레이리스트 평균의 ΔC%에 `change_class`를 붙인다. 플레이리스트 평균 T·ΔC%와 처방 범위 하한은 `prescription.csv`에 낸다. 속도의 무음 대비 변화(m/s)도 함께 내서 노인 보행 속도의 '작지만 의미 있는 변화'(약 0.05 m/s, Perera et al., 2006)와 나란히 볼 수 있게 한다. 이 값은 기준으로 쓰지 않는다.

### 5.7 실험 2 (11/14 이후)

입력: `exp2_trials.csv`(기록지) + `E2_*` zip. 원칙: **기록지에서 오는 값(통과 시간 t30, 걸음 수 N, 걷기/뛰기)은 사람이 읽은 값이고, 센서에서 오는 값(체공, 충격, 센서 케이던스)은 코드가 낸다.** 둘을 한 표에 나란히 둔다.

- 분석 창: `t_in_sensor_s`, `t_out_sensor_s`(영상 동기에서 구한 센서 시각)가 있으면 그 창, 없으면 그 시행에서 검출한 걸음 열의 가운데 `exp2.central_step_frac`(75%) [초안 D-13].
- 코스 길이는 `exp2.course_m`(40 m)이고 분석 구간은 가운데 `exp2.analysis_m`(30 m)다. v = 30 ÷ t30_s. 기록지 케이던스 = N ÷ t30_s × 60.
- 현장 PC = 무음 2회의 (N ÷ t30_s × 60)의 평균. T = 실제 튼 BPM(`bpm_played`) ÷ 현장 PC × 100. 실험 1의 PC와의 차이를 표로 낸다 [초안 D-04]. 기록지의 `pc_field_spm`(현장에서 음원을 고르려고 사람이 계산해 적은 값)과 다시 계산한 값이 `exp2.pc_field_tol_spm`보다 많이 다르면 경고한다.
- 창 안 유효 걸음으로 S3, S5, S3_half, S3_double, CV, 충격 F/BW, 센서 C.
- 체공: 창 안에서 체공 이벤트(§4.4)를 찾고 `flight_step_frac`(체공이 있는 걸음 비율), 체공 시간 중앙값, 높이 h를 낸다. 필요한 최소 연속 샘플 수는 ceil(0.030 × fs − 1e-9)이고(부동소수점 오차로 3.0000000000000004가 4가 되지 않게 1e-9를 뺀다), 샘플링이 100 Hz면 3샘플, 50 Hz면 2샘플(40 ms)이다.
- 걷기/뛰기: 영상 판정(`gait_video`)이 기준이고 센서 체공은 검증용이다. 어긋나면 `flags=gait_mismatch`.
- Fr = v² ÷ (g · L). L은 `participants.leg_length_m`.
- **180·195% 단계 [확정 11/9]:** 165%에서도 영상 판정이 `walk`인 사람만 현장에서 `exp2.stage_ratios_extra_pct`(180, 195)를 `exp2.extra_stage_repeats`(1)회씩 더 한다. 다른 단계와 같은 방법으로 처리하고 단계 목록에 넣는다(H3, 처방 범위 상한, 그림 2·6).
- 단계 요약: 같은 사람·비율의 2회를 평균한다(`exp2_stages.csv`는 시행 단위, `exp2_summary.csv`는 단계 단위).
- H3 판정: 사람마다 실시한 단계(`exp2.stage_ratios_pct`, 했으면 180·195% 포함)를 낮은 쪽부터 놓고, 마지막으로 걸은 단계의 Fr ≤ `stats.froude_walk_run`(0.5) ≤ 처음 뛴 단계의 Fr 이면 지지. 실시한 가장 높은 단계에서도 뛰지 않았으면 `flags=no_run` (G2의 'F6').
- 영상 동기: 점프 3회 + 박수가 센서에서 큰 수직 가속도 3연타와 체공으로 보인다. 코드는 점프 3개의 센서 시각을 찾아 `sync_jump_sensor_s`로 낸다(영상 쪽 시각은 사람이 읽어 `t_in_sensor_s`로 옮긴다).
- **수직 점프 [초안 D-37]:** `E2_<사람>_J_1` 기록에서 체공 이벤트(§4.6)를 찾아 시각 순서로 번호를 매긴다(`jump.n_jumps`개가 아니면 QA Q17). 점프마다 t_f, h, v_flight, v_int, J, 운동에너지, t_push, 밀기 평균·최대 지면반력을 `jumps.csv`에 내고, 영상 값(`video_checks.csv`의 `jump_flight`)이 있으면 나란히 둔다. 사람 값은 3회의 중앙값이다. 챌린지 시작의 싱크 점프는 이 계산에 쓰지 않는다.
- **달리기 스프링 [초안 D-39]:** 영상 판정이 `run.gait_for_spring`(`run`)인 단계에서 걸음마다 t_c, t_f를 구하고, 단계 중앙값으로 F_max, Δy, ΔL, k_vert, k_leg, 탄성에너지, 접촉 중 평균 지면반력, 달리기 이륙 각(§4.6)을 낸다. `mixed` 단계는 계산하되 `flags=mixed_gait`를 붙이고 표 4에는 넣지 않는다. 영상 값(`run_contact`, `run_flight`)이 있으면 측정 검증에 쓴다.
- **착지 무릎 각 [초안 D-38]:** `video_markers.csv`의 `contact` 행(대전자·무릎·바깥 복사뼈 픽셀 좌표)에서 무릎 안쪽 각(코사인 법칙), 굽힘 각(180° − 안쪽 각), 다리 각 θ = arctan(Δx ÷ Δy)(대전자 → 바깥 복사뼈 선과 수직선 사이)를 `knee_angles.csv`에 낸다. 100%와 150% 단계를 비교하는 기술용이다.
- **(선택) 데모 기록:** 사용자가 요청하면 데모 촬영 때의 기록(템포 램프 등)에서 걸음 시각과 순간 케이던스만 `results/demo/<이름>_steps.csv`로 낸다(영상 편집용). 분석과 판정에는 쓰지 않는다.

### 5.8 실험 3

- 입력: `E3_*` zip의 `Gyroscope.csv`, `exp3_swings.csv`, `participants`의 `leg_length_m`·`thigh_length_m`·`shank_length_m`·`mass_kg`·`height_cm`, (있으면) `video_checks.csv`의 `swing_10`과 `video_markers.csv`의 `pendulum_bent`.
- 자이로 3축의 주성분(첫 축) 각속도 ω(t)를 만들고 저역 통과(`pendulum.gyro_lowpass_hz`, 6 Hz) [초안 D-24]. 같은 방향 봉우리 간격으로 P를 구한다. 처음과 마지막 한 주기는 뺀다. 시행마다 P 중앙값, 사람마다 3회의 중앙값.
- C_pend = 120 ÷ P. P_model(L)과 주기 오차를 계산한다.
- H4: 3명 모두 C_pend < PC 이면 지지. 세 사람 |주기 오차|의 평균이 `pendulum.valid_error_pct`(15%) 이하이면 모델 타당.
- 참고: L = 0.9 m이면 P_model ≈ 1.59 s, C_pend ≈ 75 걸음/분(§9).
- **무릎 굽힌 진자 [초안 D-41]:** `E3_<사람>_K_*`(`exp3_swings.knee=bent`)도 같은 방법으로 P_K를 구한다. 분절 모델 P_seg(0)과 P_seg(φ)(§4.4)를 계산해 실측 비율 P_K ÷ P와 나란히 낸다. φ는 `video_markers.csv`의 `pendulum_bent` 행이 있으면 그 굽힘 각, 없으면 `pendulum.bent_knee_deg`(90°)이고 `flags=knee_nominal`을 붙인다. 허벅지·정강이 길이가 비면 키에 `pendulum.fallback_thigh_over_H`·`pendulum.fallback_shank_over_H`를 곱하고 `flags=seg_len_from_height`를 붙인다.
- **진자 에너지 [초안 D-41]:** 시행마다 자이로 각속도를 적분한 각도에서 반 주기별 진폭 θ_amp와 각속도 봉우리 ω_peak를 구하고(첫·마지막 주기는 뺀다) ω_pred(§4.4)와의 비를 낸다. 판정에는 쓰지 않는다.
- **영상 검증:** `video_checks.csv`의 `swing_10`(10번 흔들리는 시간)이 있으면 영상 주기 = 값 ÷ 10을 같은 시행의 P(또는 P_K)와 비교한다(§5.10).

### 5.9 시나리오 신호 (G2용)

실행 스케줄 탭의 '결과가 예상과 다를 때' 표를 코드로 옮긴 것이다. 계획서에 숫자가 있는 것만 `triggered`를 판정하고, 없는 것은 값만 내고 `triggered=NA`로 둔다(**임계값을 지어내지 않는다**). 결과는 `g2_flags.csv`.

| ID | 신호 | 계산 | 판정 |
|---|---|---|---|
| F1 | 일상에서 동조가 거의 없음 | 사람마다 ρ(T, ΔC%)·p와 95% 신뢰구간, PC ±10% 곡의 S3 중앙값, 플레이리스트 평균 ΔC%가 모두 SESOI(§4.5) 안인지 | NA(사람이 판단) |
| F2 | 과동조 | 일상 보행 구간 중 S3 ≥ `sync.over_sync_frac`(80%)인 구간의 비율 | 그런 구간이 있으면 triggered |
| F3 | 반 박자·두 배 박자 | sub/super 표시가 붙은 구간 수 | 1개 이상이면 triggered |
| F4 | 곡마다 들쭉날쭉 | ΔC%의 같은 플레이리스트 안 곡 사이 분산 vs 플레이리스트 사이 분산 | 안 > 사이 이면 triggered |
| F5 | 날마다 편차 큼 | 사람마다 무음 C의 CV | > `g2.silent_cv_max_pct`(3%) 이면 triggered |
| F6 | 가장 높은 단계에서도 안 뜀 | 실시한 가장 높은 단계(165%, 현장에서 더 했으면 195%)에 체공 없음 + 영상 걷기 | triggered |
| F7 | 충격 잡음 큼 | 같은 조건 3회 구간 충격 중앙값의 CV | > `g2.impact_cv_max_pct`(15%) 이면 triggered |
| F8 | 진자 예측과 실측의 큰 차이 | C_pend, PC | NA. "예상된 결과"로 보고만 한다 |

### 5.10 측정 검증 [초안 D-38]

폰으로 잰 값이 믿을 만한지를 다른 방법과 비교해 표 하나(`validation.csv`)와 그림 9로 낸다. **통과 기준을 두지 않고 그대로 보고한다**(기준을 결과를 본 뒤에 정하지 않기 위해서다). 짝이 있는 비교는 Bland–Altman으로 차이의 평균(bias)과 95% 일치 한계(bias ± 1.96 SD, ddof=1)를 낸다.

| 비교 | 방법 A | 방법 B | 단위 |
|---|---|---|---|
| 실험 2 케이던스 | 기록지 N ÷ t30 × 60 | 센서 C(분석 창 안 중앙값) | 걸음/분 |
| 점프 체공 | 폰 t_f | 영상 프레임 수 ÷ fps | s |
| 진자 주기 | 폰 P(또는 P_K) | 영상 10번 흔들림 시간 ÷ 10 | s |
| 점프 이륙 속도 | v_flight = g t_f ÷ 2 | v_int(가속도 적분) | m/s |
| 보폭 | SL_ZH(역진자) | SL(속도 ÷ 케이던스) | m |
| (선택) 달리기 접촉·체공 | 폰 t_c, t_f | 영상 프레임 수 ÷ fps | s |
| 걷기 평균 수직 가속도 | ā_v(회차마다) | 이론값 1 g | g(평균, SD, 범위만) |

- 이미 있는 검증(100걸음 ±2, GPS 거리 5%, Doppler 대 구간 통과 속도)도 같은 표에 한 줄씩 옮겨 적는다.
- 영상 값의 분해능(1 프레임 = 1 ÷ fps 초)을 표에 함께 적는다.
- 힘판을 빌릴 수 있으면(보강 V, 11/21) 폰으로 추정한 F/BW와 점프 t_f를 힘판 값과 같은 방식으로 비교해 줄을 더한다. 형식은 그때 정한다.

## 6. 통계와 판정

- 단위: 실험 1은 곡 구간, 실험 2는 단계(시행 2회 평균), 모두 **사람 안에서** 분석한다.
- 기술통계: 사람×조건 평균 ± SD(`stats.sd_ddof`=1, D-14), CV.
- 상관: `scipy.stats.spearmanr`, 양측, α = `stats.alpha`(0.05). 구간 수 n을 함께 낸다. 구간 수가 `stats.min_n_for_corr`(8) 미만이면 '표본 부족'으로 표시하고 판정하지 않는다 [초안 D-23]. 곡 구간은 같은 회차 안에서 독립이 아니므로 p는 참고치라고 표에 주석을 단다.
- **신뢰구간 [초안 D-34]:** 가설 1의 ρ(T, ΔC%)와 평균 추종 비율 R에 회차 단위 재표집(cluster bootstrap) 95% 신뢰구간을 붙인다. 사람마다 그 사람의 음악 회차를 복원 추출하고(뽑힌 회차의 곡 구간을 모두 가져온다) `stats.bootstrap_n`(2000)번 다시 계산해 2.5·97.5 백분위를 쓴다. 시드는 `stats.bootstrap_seed`, PC는 고정한다. 신뢰구간은 기술용이고 '지지' 판정(§2)을 바꾸지 않는다.
- 효과 크기: 무음 대비 차이(절대, %)와 표준화 효과 크기(Cohen's d, 구간 값 기준 풀링 SD). 기술용이다. 케이던스 변화는 실질적 변화 기준(SESOI, §4.5)과 비교한 `change_class`를 함께 적는다.
- 변동성 비교(가설 2): 실험 2 단계의 T와 `stats.same_tempo_pct`(±5%p) 이내인 실험 1 곡 구간을 짝지어, 사람마다 CV의 평균을 비교한다. 짝이 없는 단계는 뺀다 [초안 D-11].
- 일치 개수: 가설마다 '지지'인 사람 수를 센다(`hypotheses.csv`). `stats.agree_min_persons`(3명 중 2명) 이상이면 집단 수준 '지지'(가설 4는 3명 모두).
- 탐색(곡 선호도): 플레이리스트 안에서 (좋아하는 정도, ΔC%)의 순위 상관을 구한 뒤 부호를 센다 [초안 D-15].
- **쓰지 않는다:** Wilcoxon·Friedman 같은 집단 검정, 사후에 문턱을 바꾸는 것.
- 민감도 분석(부록): ±5% 동조 기준, 오프셋 ±5 s, 서두른 회차 포함/제외, 비 오는 날 포함/제외, 임시 PC vs 최종 PC → `sensitivity.csv`.
- **처방 범위 [초안 D-36]:** §4.5대로 사람마다 `prescription.csv`에 낸다.
- **종료 설문 [확정 11/9, D-42]:** `debrief.csv`에 '박자에 맞추려 한 적이 있다'고 적은 회차가 있으면 그 회차를 뺀 결과를 민감도 분석에 더한다. 설문은 기술로만 보고한다.
- **분석 고정 [초안 D-35]:** 걸음 검출·QA·구간 규칙은 무음 회차, 사전 점검(TEST), 합성 데이터만 보고 조정한다. 가설 결과(음악 구간의 T·ΔC%·R·S3 요약, 상관, `hypotheses.csv`, 그림 2·3)를 실제 데이터로 처음 계산하기 전에, 그리고 G2(11/18) 전에 코드·`config/params.toml`·`docs/DECISIONS.md`를 커밋하고 git 태그 `freeze.tag`(`analysis-freeze-g2`)를 붙인다. 태그는 사용자가 승인한 뒤 붙인다. 태그가 없으면 `stats`·`figures`는 실제 데이터에서 멈추고 알린다(사용자가 `--allow-unfrozen`을 주면 돌리되 `run_info.json`에 `unfrozen=true`를 남긴다). 태그 뒤에 정의·문턱·제외 규칙을 바꾸면 DECISIONS의 변경 기록에 적고 바꾸기 전후 결과를 모두 보고한다(버그 수정도 적는다). 실험 2·3 코드는 태그 뒤에 완성해도 되지만 정의와 문턱은 태그 시점의 SPEC·params를 따른다. G3의 데이터 동결(`freeze --version 1.0`)과는 다른 것이다.

## 7. 출력

`results/` 아래에 쓴다(합성 데이터는 `results_synthetic/`). 모든 CSV는 UTF-8, 열 이름은 영어 snake_case에 단위 접미사(`_spm`, `_ms`, `_s`, `_pct`, `_g`, `_m`)를 붙인다. **좌표(위도·경도) 열은 어디에도 두지 않는다.**

| 파일 | 한 줄 | 주요 열 |
|---|---|---|
| `qa_summary.csv` | 회차×검사 | walk_id, check_id, status(PASS/WARN/FAIL/NA/INFO), value, threshold, note |
| `qa/<walk_id>.json` | 회차 QA 상세 | 단위·부호 판별, 샘플링, 끊김, 방향 û, 서 있는 구간(D-29), 멈춤 표식과 GPS 통과 시각의 차이(D-28) |
| `zip_links.csv` | zip ↔ manifest 연결 제안 | zip_name, participant, start_kst, walk_id, diff_s, status(matched/none/ambiguous) |
| `steps/<walk_id>_steps.csv` | 걸음 | step_idx, t_s, interval_s, cadence_inst_spm, impact_g, friction_req, valid, exclude_reason, song_idx |
| `segments.csv` | 곡 구간 | walk_id, participant, condition, playlist, song_title, bpm, tempo_ratio_pct, n_valid_steps, valid_duration_s, cadence_median_spm, cadence_rate_spm, dC_pct, R, sync3_pct, sync5_pct, sync3_half_pct, sync3_double_pct, sub_super, cv_pct, impact_g, impact_rel_pct, friction_req, speed_ms, step_length_m, liking, familiarity, com_vertical_m, step_length_zh_m, change_class, pc_provisional, flags |
| `walks.csv` | 회차 | walk_id, participant, walk_no, condition, date, duration_s, valid_duration_s, detected_steps, pedometer_steps, hand_count, cadence_median_spm, cadence_rate_spm, cv_pct, speed_doppler_ms, speed_section_ms, speed_diff_pct, com_vertical_m, step_length_zh_m, mean_av_g, qa_status, hurried, weather, flags |
| `participants.csv` | 사람 | participant, n_silent, pc_spm, pc_provisional, silent_cv_pct, sesoi_pct, age, height_cm, mass_kg, leg_length_m, thigh_length_m, shank_length_m |
| `hypotheses.csv` | 가설×사람 | hypothesis, participant, metric, value, ci_low, ci_high, n, criterion, supported, note (집단 행 포함) |
| `g2_flags.csv` | 시나리오 신호 | flag_id, description, value, threshold, triggered, suggested_response |
| `exp2_stages.csv` / `exp2_summary.csv` | 시행 / 단계 | runner, ratio_pct, repeat, bpm_played, pc_field_spm, tempo_ratio_pct, v_ms, cadence_record_spm, cadence_median_spm, sync3_pct, sync5_pct, cv_pct, impact_g, flight_step_frac, flight_time_median_s, rise_height_m, contact_time_s, fmax_bw, delta_y_m, delta_l_m, kvert_kn_m, kleg_kn_m, elastic_energy_j, takeoff_angle_deg, change_class, gait_video, fr, flags |
| `exp3_swings.csv` | 진자 | runner, repeat, knee, knee_deg, swing_period_s, n_cycles, cadence_pend_spm, period_model_s, period_error_pct, period_model_seg_s, period_ratio_bent, amp_deg, omega_peak_rad_s, omega_pred_rad_s, video_period_s, leg_length_m, flags |
| `jumps.csv` | 점프 | runner, trial_id, jump_no, flight_time_s, flight_time_video_s, height_m, takeoff_v_flight_ms, takeoff_v_int_ms, impulse_ns, kinetic_energy_j, pushoff_time_s, mean_grf_push_bw, peak_grf_push_bw, flags |
| `knee_angles.csv` | 영상 마커 각도 | trial_id, event, event_no, frame_no, knee_inner_deg, knee_flexion_deg, leg_angle_deg |
| `validation.csv` | 측정 검증(§5.10) | measure, participant, n, mean_a, mean_b, bias, loa_low, loa_high, mean_abs_diff, unit, resolution, method_a, method_b, note |
| `prescription.csv` | 처방 범위(§4.5) | participant, row_type(playlist/summary), playlist, pc_spm, sesoi_pct, playlist_t_pct, playlist_dc_pct, change_class, t_low_pct, t_high_pct, bpm_low, bpm_high, statement, flags |
| `demo/<이름>_steps.csv` | (선택) 데모 기록의 걸음 | t_s, cadence_inst_spm |
| `sensitivity.csv` | 민감도 | 변형 이름, 영향받은 지표 |
| `tables/table1_participants.csv`, `table2_speed_decomposition.csv`, `table3_summary.csv`, `table4_jump_spring.csv` | 논문 표 | §8 |
| `figures/*.png` | 그림 | §8 |
| `frozen/v1.0/` | 동결본 | 위 CSV 복사 + `SHA256SUMS` (G3에서만, 덮어쓰기 거부) |
| `run_info.json` | 실행 기록 | git 해시, 분석 고정 태그와 HEAD가 태그 뒤 몇 커밋인지, `unfrozen`, params 해시, 입력 파일 sha256, 패키지 버전, 시각 |

## 8. 그림과 표

템포에 따른 그림(그림 2, 3b, 4, 5, 6)의 가로축은 템포 비율 T(%)로 통일한다. 사람 3명은 패널 하나씩(공유 축), 곡 구간 값은 점, 평균은 굵은 선이다. 그림 제목은 중립적으로 두고(결과 문장은 사람이 데이터를 본 뒤 쓴다), 그림마다 같은 이름의 `.json`에 그려진 값 요약과 params 해시를 남긴다. 해상도 300 dpi, 폭 6.5–8 inch, 색은 색각 이상에서도 구분되는 팔레트, 사람마다 같은 색.

| 번호 | 파일 | 내용 | x | y | 비고 |
|---|---|---|---|---|---|
| 표 1 | `table1_participants.csv` | 나이, 키, 체중, 다리 길이, PC | | | |
| 그림 2 | `fig2_cadence_vs_tempo.png` | '템포 지도'. 1인 1패널. 실험 1 곡 구간은 점, 실험 2 단계는 선. 대각선 y = x, 날마다 흔들리는 폭(100 ± SESOI %, 회색 띠), 진자 예측 케이던스(곧은·굽힌 다리, 가로 점선), 처음 체공이 생긴 단계(세로선), 처방 범위(가로축 음영) | T (%) | 케이던스 ÷ PC (%) | **핵심** |
| 그림 3a | `fig3a_sync_by_playlist.png` | 플레이리스트(P1–P4)별 동조율 | 플레이리스트 | S3 (%) | |
| 그림 3b | `fig3b_sync_exp1_vs_exp2.png` | 실험 1 구간과 실험 2 단계의 동조율을 T로 나란히 | T (%) | S3 (%) | **핵심** |
| 그림 4 | `fig4_speed_steplength.png` | 속도와 보폭(실험 1) | T (%) | v (m/s), SL (m) | |
| 표 2 | `table2_speed_decomposition.csv` | 조건별 보폭·케이던스 기여율 | | | 로그 분해 |
| 그림 5 | `fig5_impact_variability.png` | 충격과 걸음 변동성(실험 1·2) | T (%) | F/BW, CV (%) | |
| 그림 6 | `fig6_speed_flight_froude.png` | 단계별 속도(선), 체공 시간(막대), Fr(보조 표시)와 Fr = 0.5 선, 영상 걷기/뛰기 표시 | 단계(T) | v (m/s), 체공 (s), Fr | **핵심** |
| 그림 7 | `fig7_pendulum.png` | 사람마다 곧은 다리 막대 2개(모델 예측, 실측 흔들림 기반 예측)와 굽힌 다리 막대 2개(분절 모델 예측, 실측 흔들림 기반 예측), 실측 PC는 가로선 | 사람 | 케이던스 (걸음/분) | **핵심** |
| 그림 8 | `fig8_preference.png` | 좋아하는 정도 vs 케이던스 변화율(구간 안) | 좋아하는 정도 (1–5) | ΔC% | 탐색 |
| 표 3 | `table3_summary.csv` | 사람×조건 모든 종속변수의 평균 ± SD | | | |
| 표 4 | `table4_jump_spring.csv` | 사람마다 점프 높이·이륙 속도(두 방법)·충격량, 달리기 단계의 F_max·Δy·다리 강성 | | | 가설 3 보조 |
| 그림 9 | `fig9_validation.png` | 측정 검증(§5.10). 비교마다 패널 하나의 Bland–Altman | 두 방법의 평균 | 두 방법의 차이 | 방법 |

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
| 16 | 100–245 BPM, 5 간격 | 파일 30개 |
| 17 | PC = 110 | PC ±10% = [99, 121] BPM |
| 18 | 무음 C = [108, 110, 112] / [110.0, 110.5, 110.2] | SESOI = 1.818% / 변동계수 0.228%가 1%보다 작아 SESOI = 1.0% |
| 19 | SESOI 1.818%, 플레이리스트 평균 (T, ΔC%) = P1 (92.7, 0.4), P2 (100.9, 1.1), P3 (108.2, 2.5), P4 (119.1, 4.2). 실험 2 단계 S3 = 100%: 95, 120%: 88, 135%: 82, 150%: 64, 165%: 31 | T_low = 108.2%, T_high = 135%. PC 110이면 119.0–148.5 BPM |
| 20 | 18과 같은데 P3, P4의 ΔC%가 1.5, 1.7 | T_low 없음 → "듣기만으로는 걸음이 바뀌지 않고, 박자에 맞춰 걷겠다는 의도가 필요하다" |
| 21 | 점프 t_f = 0.50 s, m = 60 kg | h = 0.30656 m, v = 2.4525 m/s, J = 147.15 N·s, ½mv² = mgh = 180.44 J |
| 22 | v = 2.4525 m/s, t_push = 0.30 s | 밀기 평균 지면반력 1.8333 BW (1079.1 N) |
| 23 | 영상 120프레임, 240 fps | t_f = 0.5000 s, h = 30.66 cm. 1프레임(4.17 ms) 차이는 높이 약 0.51 cm(120 fps면 1.02 cm) |
| 24 | 달리기 v = 2.5 m/s, t_f = 0.10 s | v_y = 0.4905 m/s, θ = 11.10°, 공중 거리 0.250 m, h = 1.226 cm |
| 25 | m = 60 kg, t_c = 0.25 s, t_f = 0.10 s, v = 3.0 m/s, L = 0.90 m | F_max = 1294.4 N (2.199 BW), Δy = 0.05997 m, ΔL = 0.14182 m, k_vert = 21.58 kN/m, k_leg = 9.13 kN/m, 탄성에너지 38.8 J, 접촉 중 평균 1.40 BW |
| 26 | M = 60 kg, l_t = 0.4165 m, l_s = 0.4182 m(키 1.70 m의 0.245, 0.246) | φ = 0°: I_hip = 2.057 kg·m², d = 0.366 m, P_seg = 1.531 s(78.4 걸음/분). φ = 90°: I_hip = 1.284 kg·m²(−37.6%), d = 0.286 m, P_seg = 1.367 s(−10.7%, 87.8 걸음/분), 비율 0.893 |
| 27 | 26의 곧은 다리(m = 9.66 kg), θ_amp = 30° | 위치에너지 4.645 J, ω_pred = 2.125 rad/s, 발목 속도 v = (l_t + l_s) ω = 1.774 m/s, 중력 토크 17.33 N·m, α = τ ÷ I = 8.43 rad/s² |
| 28 | 마커 픽셀 좌표 대전자 (0, 0), 무릎 (50, 420), 바깥 복사뼈 (−100, 800) | 무릎 안쪽 각 151.67°, 굽힘 각 28.33°, 다리 각 −7.13° |
| 29 | l = 0.90 m, h_com = 0.040 m | SL_ZH = 0.5307 m. 예제 1의 보폭 0.7273 m와의 비 0.7297 |
| 30 | A = [110, 112, 115, 120], B = [111, 112, 113, 121] | A − B = [−1, 0, 2, −1], bias = 0.000, SD = 1.414, 95% 일치 한계 [−2.772, 2.772] |
| 31 | PC = 110, 비율 1.80 / 1.95(5 BPM 단위, 0.5는 올림) | 200, 215 BPM. PC = 112이면 200, 220 |
| 32 | a_v,total = 1 + 0.3 sin(2π · 1.8 t), 100 Hz, 10 s | ā_v = 1.000 g |
| 33 | 같은 입력과 같은 `stats.bootstrap_seed` | 같은 신뢰구간(재현성). 음악 회차가 1개뿐인 사람은 NA |

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
  jumps.py            수직 점프(체공, 가속도 적분, 충격량), 달리기 스프링(Morin)
  validation.py       측정 검증(Bland–Altman), 처방 범위
  stats.py            상관, 신뢰구간(회차 단위 재표집), 판정, 시나리오 신호, 분석 고정 확인
  figures.py          그림·표
  synthetic.py        실제 형식을 흉내 낸 합성 zip 생성
tests/
```

- 환경: Python 3.10 이상. 의존성은 numpy, pandas, scipy, matplotlib, (개발) pytest, ruff. 더 필요하면 이유를 `DECISIONS.md`에 적고 추가한다.
- 모든 공개 함수에 타입 힌트와 단위를 적은 독스트링. 입출력(파일)과 계산(순수 함수)을 분리한다. 난수는 시드를 고정한다.
- 명령: `python -m walkmusic inspect|qa|process|stats|figures|freeze|all`. 공통 옵션 `--walk ID`, `--participant X`, `--synthetic`.
- `all`은 같은 입력이면 같은 출력을 낸다(멱등). 입력 파일 해시가 같으면 다시 계산하지 않는다.
- 합성 데이터(`synthetic.py`): 알려진 케이던스·BPM 추종·체공·점프·진자 주기(곧은·굽힌 다리)를 가진 가짜 zip을 만들어, 45회 + 실험 2·3 전체가 실제 데이터 없이 끝까지 돌아가게 한다. 결과는 `results_synthetic/`에만 쓴다. 실제 형식은 Phase 0의 `DATA_FACTS.md`를 따른다.
- 테스트: §9 예제 수치(손계산 노트 포함), 합성 신호 걸음 검출, 제외 규칙 경계, 곡 구간 계산(순환·`start_song`), 단위·부호 판별, 시범 파일 QA 실행, 좌표 열이 `results/`에 없는지, 배정표 재현, 재표집 재현성(같은 시드 → 같은 신뢰구간), 분석 고정 태그가 없을 때 `stats`가 멈추는지, 합성 점프·진자 신호에서 체공 시간·이륙 속도·주기를 되찾는지.
- 로그에는 좌표와 기기 이름을 찍지 않는다.

## 11. 개인정보와 데이터 취급

- 저장소는 **비공개**로 둔다. `data/raw/`, `data/interim/`, `data/private/`는 git에서 제외한다.
- `Location.csv`에는 집·학교가 이어지는 평소 길이 그대로 들어 있다. 좌표는 속도·거리 계산에만 쓰고 결과·로그·그림·커밋에 남기지 않는다. 테스트가 이를 확인한다.
- 기기 이름 같은 식별 정보는 문서와 결과에 쓰지 않는다(기종 정도만).
- 보강 N 참가자(친구)의 데이터는 동의 범위 안에서 ID(N1–N4)로만 다룬다.
- 합성 데이터의 좌표는 0 근처 가짜 값으로 만든다.
- 영상 파일(얼굴이 나온다)은 저장소에 넣지 않는다. 영상에서 읽은 값만 CSV(`video_checks.csv`, `video_markers.csv`)로 둔다.

## 12. 단계(Phase)와 완료 기준

| Phase | 기간 | 내용 | 완료 기준 |
|---|---|---|---|
| 0 | 11/7–11/8 | 시범 zip에서 데이터 사실 확인. 11/8 사전 점검 기록(리허설, 100걸음)이 있으면 같이 확인 | §3.2의 항목이 `DATA_FACTS.md`에 값 또는 '해당 없음'으로 채워짐. 가정이 틀린 곳은 `DECISIONS.md`에 |
| 1 | ~11/12 (G1) | 뼈대, 불러오기, QA, 걸음 검출 초안, 합성 데이터 생성기 | `pytest` 통과(§9 + 합성 신호), 시범 파일 QA 리포트, `qa --gate G1`이 합성 데이터에서 동작하고 11/12까지 들어온 실제 1–2회차 파일(6개)로도 표를 냄. 결과 전 기준(D-33–D-36)이 DECISIONS에 '확정'으로 적힘(사람) |
| 2 | ~11/18 (G2) | 실험 1 곡 구간 지표, PC, SESOI, 판정과 신뢰구간, 시나리오 신호, 그림 2·3. 결과 계산 전 분석 고정 태그 | 태그 `analysis-freeze-g2`를 붙인 뒤 실제 회차(1인 7회 이상)에 `all`이 한 번에 돌고 `hypotheses.csv`·`g2_flags.csv`가 나옴 |
| 3 | 11/14 데이터 → ~11/22 | 실험 2·3: 단계 지표와 180·195%, 점프, 달리기 스프링, 곧은·굽힌 진자와 진자 에너지, 측정 검증, 처방 범위 | `exp2_*`, `exp3_swings.csv`, `jumps.csv`, `validation.csv`, `prescription.csv`, 그림 6·7·9, 표 4 |
| 4 | ~11/24 (G3) | 전체 표·그림, 데이터 표 v1.0 동결 | `freeze --version 1.0`, 핵심 그림 4장 |
| 5 | 11/24 이후, **사용자가 요청할 때만** | 웹 데모(같은 파이썬 코드를 재사용, 예: Streamlit) | 별도 계획 |

각 Phase 시작 전에 계획을 보여주고 승인을 받는다. 끝나면 CLAUDE.md의 보고 순서를 따른다.
