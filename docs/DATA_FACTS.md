# DATA_FACTS — 실제 파일에서 확인한 사실

Phase 0에서 시범 측정 zip을 열어 채운다. '문서로 아는 것'은 Sensor Logger 공식 문서에서 확인한 내용이고, '파일에서 확인한 값'이 비어 있으면 아직 확인하지 않은 것이다. 추측해서 채우지 않는다. SPEC과 다른 점은 DECISIONS.md에 적는다.

## 규칙

- 좌표 값, 기기 이름 등 개인을 알아볼 수 있는 값은 적지 않는다. 거리, 속도, 정확도, 시각만 적는다.
- 값마다 어떻게 확인했는지(어떤 계산인지)를 '메모'에 한 줄 적는다.
- 시범 파일 1개로 확인한 것은 '시범 1개 기준'이라고 적고, 실제 회차가 들어오면 다시 확인한다.
- 센서마다 파일이 따로이므로, 아래 표의 센서 이름은 파일 이름과 같게 쓴다.

**확인 범위.** 아래 값은 모두 **시범 1개 기준**이다: `TEST_A_1107`(iOS 26.2.1, Sensor Logger 1.68.1, standardisation=false, 바지 앞주머니). 실제 회차나 Android 기록이 들어오면 다시 확인한다. 계산은 저장소 밖 일회용 스크립트(numpy·pandas·scipy)로 했고, Phase 1의 `inspect`·`qa`가 같은 값을 다시 내야 한다. t_s는 Metadata `recording epoch time`부터 잰 초다.

## 0. 시범 측정 개요

| 항목 | 값 | 메모 |
|---|---|---|
| zip 파일 이름 | `_1271-10-2026-11-07_11-20-44.zip` (14,636,083 B, 안의 9개 파일 합 34,474,566 B) | sha256 `a5169b05fa85bec7d353aa1d236d5dd469f3639afbbf703042b170dbb53374a9`. 이름의 시각은 UTC다(§2). 앞부분 `_1271-10`은 Metadata 값과 겹치지 않는다(뜻은 확인하지 않음). `walk_id`(TEST_A_1107)와 이름이 다르다 → D-27 |
| 기록 시작 (Asia/Seoul) | 2026-11-07 20:20:44.444 | Metadata `recording epoch time`. IMU 첫 샘플은 20:20:44.502 |
| 기록 길이 | 718.9 s (11분 59초) | Accelerometer 첫~끝 샘플(20:20:44.502–20:32:43.377) |
| 걷기 내용 (사용자 설명) | 산책, 화면 끄고 기록, 조건 없음. 정지 없이 계속 걸었고 폰을 만지지 않았다. 끝에서 약 10초 서 있다가 기록을 끝냈다 | 사용자 답(2026-11-07). 데이터: 시작에는 서 있기 없음(첫 걸음 t_s 1.4 s), 마지막 걸음 t_s 700.3 s, 701–710 s 서 있기(Pedometer 증가 0), 710 s 무렵 폰 방향이 약 60–70° 바뀜(폰을 꺼낸 때로 보임) |
| 폰 OS 종류와 둔 위치 | iOS 26.2.1 · 바지 앞주머니 | OS는 Metadata, 위치는 사용자 답. 프로토콜 기본(허리 파우치)과 다르다. 기종은 participants.csv에 |
| 직접 센 걸음 수 | 없음 | 사용자 답: 세지 않음 |
| 확인한 날과 확인한 사람 | 2026-11-07 · Claude Code(A 요청) | 시범 1개 기준 |

## 1. 파일 목록

| 파일 | 문서로 아는 것 | 파일에서 확인한 값(있음/없음, 열 이름, 행 수) | 메모 |
|---|---|---|---|
| Accelerometer.csv | 켠 센서마다 CSV 하나. 열: time, seconds_elapsed, x, y, z | 있음. `time, seconds_elapsed, z, y, x` · 71,588행 | 열 순서가 z, y, x다. 열 이름으로 읽는다. 결측 0, `time` 순증가 |
| Gravity.csv | 같음 | 있음. 같은 열 · 71,588행 | 결측 0, 순증가 |
| Gyroscope.csv | 같음 | 있음. 같은 열 · 71,588행 | 결측 0, 순증가 |
| Location.csv | latitude, longitude, altitude, speed, speedAccuracy, bearing, bearingAccuracy, horizontalAccuracy, verticalAccuracy | 있음. `time, seconds_elapsed, altitude, speedAccuracy, bearingAccuracy, latitude, altitudeAboveMeanSeaLevel, bearing, horizontalAccuracy, verticalAccuracy, longitude, speed` · 723행 | 문서에 없는 `altitudeAboveMeanSeaLevel`이 있고 열 순서가 다르다. 값은 적지 않는다 |
| Metadata.csv | 버전, 플랫폼, 기록 시각, 시간대 등. 옛 기록에는 일부 열이 없다 | 있음. 항목 12개(§7) · 데이터 1행 | |
| Pedometer.csv | 있을 것으로 추정(미확인) | 있음. `time, seconds_elapsed, steps` · 275행 | §6 |
| 그 밖의 파일 | — | AccelerometerUncalibrated.csv(71,589행), GyroscopeUncalibrated.csv(71,590행): 열은 IMU와 같다. Annotation.csv: 0바이트(헤더도 없음) | Uncalibrated 가속도는 중력 포함·단위 g(§4). Annotation은 주석을 달지 않으면 비는 것으로 보인다(폰을 만지지 않음과 맞음). 빈 파일 처리 → D-32 |
| 형식 | — | UTF-8, BOM 없음, 줄바꿈 LF, 쉼표 구분, 첫 줄 헤더 | 9개 파일 모두 같다 |

## 2. 시간

| 항목 | 문서로 아는 것 | 파일에서 확인한 값 | 메모 |
|---|---|---|---|
| `time` | UNIX epoch 나노초, UTC | 19자리 정수(ns). 모든 파일에서 순증가, 중복 0 | KST로 바꾼 시각이 zip 안 파일 시각(20:20:44, 20:32:42)과 맞는다 |
| `seconds_elapsed` | 기록 시작부터 초 | = (`time` − `recording epoch time`) ÷ 1e9. 모든 센서에서 차이 0.001 ms 미만 | 0점이 Metadata의 기록 시작이다. Location은 음수(−14.219 s)부터 시작한다 |
| 파일 이름 안의 시각 | 현지 시각 | **UTC**. 이름의 `2026-11-07_11-20-44` = Metadata `recording time` = UTC 11:20:44 = KST 20:20:44 | SPEC §3.1과 다르다 → D-27 |
| 센서 사이 첫 `time` 차이 | — | IMU 5개는 서로 14 ms 안(t_s 0.044–0.058 s). Pedometer 첫 갱신 t_s 9.809 s. Location 첫 점 t_s −14.219 s | 가장 이른 첫 `time`은 Location의 기록 전 점이다 → D-28 |
| Metadata의 기록 시작 시각과 센서 첫 `time`의 차이 | — | `recording epoch time` = 1794050444444(ms, 13자리) = 20:20:44.444 KST. IMU 첫 샘플은 44–58 ms 뒤 | 센서 `time`은 ns, 이 값은 ms다. DECISIONS D-20, D-28 |

센서별 첫·끝 시각(2026-11-07, Asia/Seoul):

| 파일 | 첫 `time` | 끝 `time` | 길이 (s) | 첫 t_s (s) |
|---|---|---|---|---|
| Accelerometer | 20:20:44.502 | 20:32:43.377 | 718.876 | 0.058 |
| AccelerometerUncalibrated | 20:20:44.497 | 20:32:43.372 | 718.876 | 0.053 |
| Gravity | 20:20:44.502 | 20:32:43.377 | 718.876 | 0.058 |
| Gyroscope | 20:20:44.502 | 20:32:43.377 | 718.876 | 0.058 |
| GyroscopeUncalibrated | 20:20:44.488 | 20:32:43.372 | 718.884 | 0.044 |
| Location | 20:20:30.225 | 20:32:42.999 | 732.774 | −14.219 |
| Pedometer | 20:20:54.252 | 20:32:38.626 | 704.373 | 9.809 |

## 3. 샘플링

| 센서 | 행 수 | 중앙 간격 (ms) | fs (Hz) | 5·95 백분위 간격 (ms) | 최대 간격 (s) | 1 s 넘는 끊김 개수 |
|---|---|---|---|---|---|---|
| Accelerometer | 71,588 | 10.042 | 99.58 | 10.041 / 10.043 | 0.019 | 0 |
| Gravity | 71,588 | 10.042 | 99.58 | 10.041 / 10.043 | 0.019 | 0 |
| Gyroscope | 71,588 | 10.042 | 99.58 | 10.041 / 10.043 | 0.019 | 0 |
| Location | 723 | 999.989 | 1.00 | 999.981 / 1000.086 | 9.000 | 1 s 넘는 간격 102개 중 98개는 1.000–1.010 s(정상 주기). 나머지 4개는 기록 시작 전 2개(9.000 s: t_s −14.2→−5.2, 5.267 s: −5.2→0.05)와 시작 직후 2개(1.384 s: 0.06→1.45, 1.222 s: 2.32→3.54) |
| Pedometer | 275 | 2570.648 | 0.39 | 2570.429 / 2571.038 | 2.575 | 해당 없음(갱신 주기 2.57 s). 주기의 1.5배를 넘는 간격 0 |

- AccelerometerUncalibrated(71,589행)와 GyroscopeUncalibrated(71,590행)도 간격이 같고(중앙 10.042 ms, 최대 0.014 s) 끊김이 없다.
- IMU에는 0.05 s를 넘는 간격이 하나도 없다(`qa.gap_warn_s` 0.25 s 기준으로 Q03 PASS에 해당). Location에는 0.9 s 미만 간격도 3개(최소 0.01 s) 있다.
- Metadata `sampleRateMs`의 설정은 10 ms인데 실제 중앙 간격은 10.042 ms(99.58 Hz)다. Q02로는 PASS이고 '목표 100 Hz보다 낮음' INFO가 붙는다 → D-34.
- 문서로 아는 것: 센서 샘플링은 고르지 않다. 이 파일의 IMU 간격은 p5–p95 폭이 0.002 ms로 거의 고르다.

## 4. Accelerometer · Gravity · Gyroscope

| 항목 | 문서로 아는 것 | 파일에서 확인한 값 | 메모(근거 계산) |
|---|---|---|---|
| Accelerometer 단위 | 문서에 없음(g 또는 m/s²) | **m/s²** | 중력 제외 신호라 크기만으로는 못 정해서, SPEC §5.2대로 같은 구간 Gravity 크기(9.80665)로 정했다. 아래 Accelerometer + Gravity = 9.80665 × AccelerometerUncalibrated도 같은 결론이다 |
| Accelerometer가 중력을 포함하는가 | 문서에 없음 | **포함하지 않는다**(사용자 가속도) | 서 있을 때 ‖a‖ 중앙 0.101(0 근처). 걷는 동안 평균 벡터 크기 0.13 m/s², 그 Gravity 방향 성분 0.015 m/s²(중력을 포함하면 약 9.8) |
| 서 있을 때 ‖a‖ | — | Accelerometer 0.101 m/s² · Accelerometer+Gravity 9.798 m/s²(0.999 g) · AccelerometerUncalibrated 0.999 g | 1 s 창 움직임 지표(Accelerometer 세 축 분산 합의 제곱근)가 0.23 m/s² 미만인 창은 기록 끝 713–716 s(3 s, 폰을 꺼내 든 뒤)뿐이다. 시작에는 서 있는 구간이 없다. 끝 서 있기 701–710 s(주머니 안)의 지표는 0.25–2.3 m/s² → D-30 |
| 걷는 동안 ‖a‖ 중앙값 | — | Accelerometer 3.761 m/s² · Accelerometer+Gravity 9.668 m/s²(0.986 g) · AccelerometerUncalibrated 0.986 g | 움직임 지표 1.38 m/s² 초과인 1 s 창 701개(전체 715) 기준. 지표 중앙 4.28 m/s² |
| 폰 방향 | — | 걷는 동안 Gravity 평균 방향이 −y 축과 23.8°, +z 축과 67.5°, x 축과 약 83–97° | 분마다 평균 방향의 변화 1.8–13.2°, 순간 방향과 평균의 각도 중앙 8.3°·p95 21.4°. iOS 규약(Gravity가 땅 쪽)이면 폰 위쪽이 위를 향하고 약 24° 기울었다. 0–8 s와 710 s 뒤는 방향이 약 60–73° 다르다(폰을 넣고 꺼낸 때로 보임) |
| Gravity 단위 | 문서에 없음 | **m/s²** | 크기가 모든 샘플에서 9.80665(최소 = 최대) |
| Gravity와 Accelerometer의 부호 관계 | 문서에 없음 | **총 가속도 = Accelerometer + Gravity**(합성 부호 +1) | (1) ‖Accelerometer + Gravity − 9.80665 × Uncalibrated‖ 중앙 0.0000 m/s²(부호를 바꾸면 19.61). (2) Gravity 방향으로 투영한 총 가속도가 걷는 동안 위로 더 크게 벗어난다: p99 − 중앙 7.18 > 중앙 − p1 3.23 m/s², 왜도 +0.72(반대 부호는 −0.72). (3) 서 있을 때 Uncalibrated와 Gravity의 cos = +1.000 → D-29 |
| Gyroscope 단위 | rad/s로 가정 | **rad/s** | ‖ω‖ 걷는 동안 중앙 1.43, p95 3.20, p99 4.41, 최대 12.23, 서 있을 때 중앙 0.037. °/s라면 걷는 동안 중앙이 1.4 °/s라 너무 작다. GyroscopeUncalibrated와의 차이 중앙 0.0038 rad/s |

## 5. Location

| 항목 | 문서로 아는 것 | 파일에서 확인한 값 | 메모 |
|---|---|---|---|
| 갱신 간격 | — | 1.000 s(중앙 999.989 ms) | 기록 전 점 2개(t_s −14.2, −5.2 s). 시작 직후 1.38 s·1.22 s 간격 뒤로는 1 s(§3) |
| `speed` 단위와 범위 | 단위는 문서에 없음(m/s로 가정) | **m/s**. 유효값 최소 0, p5 0.455, 중앙 0.912, p95 1.238, 최대 1.476. 걷는 동안(t_s 1.36–700.32) 중앙 0.919, 평균 0.903 | `speed` = −1(무효)이 7개, 모두 t_s 2.3 s 이전(그 점은 `speedAccuracy`도 −1). 중앙 0.92는 이 칸 메모의 '1.2–1.5'보다 낮지만, km/h라면 0.26 m/s라 걸음 101 spm과 맞지 않는다. 경로 속도와의 차이는 아래 |
| `speedAccuracy` 중앙값 | 속도 오차의 크기 | 0.894 m/s (p5 0.589, p95 0.987) | 걷는 동안 0.5 이하 3.0%(21/697), 0.75 이하 14.5%, 1.0 이하 97.6%. `speed.doppler_max_speed_accuracy_ms`(0.5)를 넘는 점이 97% → D-31 |
| `horizontalAccuracy` 중앙값 | 위치 오차의 크기 | 4.75 m (p95 4.75, 최대 23.06) | `qa.gps_accuracy_warn_m`(20) 이하. `verticalAccuracy` 중앙 4.98 m, `bearingAccuracy` 중앙 68.3° |
| 총 이동 거리 | — | 걷는 동안 892.7 m(1 s 점을 모두 연결), 874.5 m(10점마다 연결) | 5–30점마다 연결하면 860–877 m라 위치 잡음으로 늘어난 길이는 2–4%다. 모든 점(기록 전 점 포함) 954.1 m, 수평 정확도 20 m 이하 점끼리 891.0 m. 거리는 위경도 사이 대원 거리의 합 |
| 지도 거리와의 차이 | — | 해당 없음 | 시범 경로의 지도 거리를 모른다 |
| Doppler 속도 중앙값 vs 이동 거리 ÷ 시간 | — | Doppler 중앙 0.919 m/s(적분 628 m) vs 경로 1.26–1.28 m/s(875–893 m ÷ 696 s) | Doppler가 27–30% 낮다. 이 파일만으로는 어느 쪽이 맞는지 모른다. 1179걸음으로 나눈 보폭은 0.53 m vs 0.74–0.76 m → DECISIONS D-01, D-31 |

## 6. Pedometer

| 항목 | 문서로 아는 것 | 파일에서 확인한 값 | 메모 |
|---|---|---|---|
| 파일 있음 | 추정 | 있음 | |
| 열 이름 | — | `time, seconds_elapsed, steps` | 거리·케이던스 열은 없다 |
| 누적 값인가 구간 값인가 | — | **누적**(기록 시작부터) | 감소 0번, 정수. 첫 갱신(t_s 9.81 s)의 값이 9로, 그 전에 걸은 걸음이 들어 있다 |
| 갱신 간격 | — | 2.571 s (p5 2.5704, p95 2.5710, 최대 2.575 s) | 갱신마다 증가 중앙 4, 최대 6. 증가 0인 갱신 5번은 모두 끝 서 있기(t_s 701.33 s 뒤)다 |
| 총 걸음 수 | — | 1174 | 마지막 갱신 t_s 714.18 s. 첫 갱신 뒤 증가량은 1165 |

## 7. Metadata

| 항목 | 값 | 메모 |
|---|---|---|
| 항목 이름 목록 | version, device name, recording epoch time, recording time, recording timezone, platform, appVersion, device id, sensors, sampleRateMs, standardisation, platform version (12개) | 값은 적지 않는다(기기 이름 포함). device name·device id는 값이 있고 둘 다 zip 이름에 들어 있지 않다. SPEC §3.1 목록에 없는 device id, sensors, sampleRateMs가 있다 → D-32 |
| 앱 버전 | 1.68.1 (version 3) | |
| 플랫폼과 버전 | ios 26.2.1 | |
| recording timezone | Asia/Seoul | |
| standardisation | false | true인 기록이 들어오면 단위·부호를 다시 판별한다 |
| recording epoch time | 1794050444444 (ms) = 2026-11-07 20:20:44.444 KST | §2 |
| recording time | `2026-11-07_11-20-44` | UTC 문자열이다(zip 이름의 시각과 같음) |
| sensors · sampleRateMs | Accelerometer 10 · Gravity 10 · Gyroscope 10 · Location 0 · Pedometer 10 · Annotation (빈칸) · GyroscopeUncalibrated 10 · AccelerometerUncalibrated 10 (ms) | 두 항목은 `\|`로 나뉜 같은 순서의 목록이다 |

## 8. 걸음 검출 예비 비교 (일회용 계산)

| 방법 | 검출 걸음 수 | 평균 케이던스 (걸음/분) | 간격 p5 / 중앙 / p95 (s) | 직접 센 값과 차이 | Pedometer와 차이 |
|---|---|---|---|---|---|
| 크기 ‖a‖ | 1190 = 걷기 1179 + 끝 서 있기 11 | 중앙 101.27 · rate 101.12 | 0.532 / 0.592 / 0.643 | 해당 없음(세지 않음) | 전체 +16 (+1.36%) · 걷기만 +5 (+0.43%) · Pedometer 갱신 창 +1 (+0.09%) |
| 수직 성분 | 1191 = 걷기 1179 + 끝 서 있기 12 | 중앙 101.27 · rate 101.12 | 0.542 / 0.592 / 0.643 | 해당 없음(세지 않음) | 전체 +17 (+1.45%) · 걷기만 +5 (+0.43%) · Pedometer 갱신 창 +1 (+0.09%) |

계산: 총 가속도 = (Accelerometer + Gravity) ÷ 9.80665(g, 원래 샘플 그대로). 크기는 ‖·‖, 수직 성분은 샘플마다 Gravity 방향으로 투영한 값이다. 평균을 빼고 2차 Butterworth 대역 통과 0.8–5 Hz(`steps.detect_band_hz`, 영위상)를 거친 뒤 봉우리를 찾았다(최소 간격 0.30 s = `steps.min_interval_s`, 높이 ≥ max(0.5 × 2 s 이동 RMS, 0.25 × 걷는 동안 RMS 중앙값)). '걷기'는 마지막 걸음(t_s 700.32 s)까지, 'Pedometer 갱신 창'은 첫 갱신부터 증가가 멈춘 갱신까지(t_s 9.81–701.33 s, Pedometer 1165걸음)다. 나머지 비교의 기준은 Pedometer 끝 값 1174다. Phase 1 검출기가 아니다.

- 두 신호의 걸음 수와 간격이 사실상 같다. 이 파일로는 D-02를 가를 수 없다(합성 신호와 직접 센 파일로 다시 본다).
- 걷는 동안 간격은 최소 0.35–0.38 s, 최대 1.08 s로 모두 D-09 범위(0.30–1.50 s) 안이다(이상 간격 0%). 101 spm 산책 한 번의 결과다.
- 분 단위 비교: 1–10분은 Pedometer 증가량과 ±1.2걸음 안이다. 0분은 +4(시작), 11분은 +11(끝 서 있기의 흔들림을 걸음으로 셈)이다.
- 끝 서 있기(701–711 s)의 봉우리 높이는 0.07–0.41 g로 걷는 동안 중앙 0.45 g보다 작지만, 간격이 2 s보다 짧아 지속 보행 묶음(D-21)에 붙는다. 그래서 t_arrive가 700.3 s가 아니라 711.0 s로 잡힌다 → D-33.
- 처음 10 s 안에 봉우리 13개(서 있기 없이 바로 걸었다. Pedometer는 t_s 9.81 s에 9), 마지막 10 s 안에 3개(오검출)가 있다. Q05 기준이면 둘 다 WARN이다.
- ML 축 스펙트럼 점검(SPEC §5.4 수용 기준 4)은 하지 않았다(Phase 1).

DECISIONS D-02, D-09의 근거 자료다.

## 9. SPEC에 필요한 변경

SPEC의 가정과 다른 점을 한 줄씩 적고 DECISIONS.md의 번호를 단다.

- 파일 이름과 Metadata `recording time`의 시각은 UTC다(SPEC §3.1은 현지 시각). 이름에서 날짜·시각을 읽지 않는다 — D-27
- 기록 시작의 대안 '모든 센서 첫 `time`의 최솟값'(SPEC §5.1)은 Location의 기록 전 점(t_s −14.2 s)을 고른다. 기준은 `recording epoch time`, 대안은 IMU 파일만 — D-28 (D-20)
- Accelerometer는 중력 제외·m/s², Gravity는 m/s², AccelerometerUncalibrated는 중력 포함·g다. 총 가속도 = Accelerometer + Gravity — D-29
- '서 있는 앞 10 s'(SPEC §5.2)와 Q05의 '처음·마지막 10 s'를 그대로 쓸 수 없다. 단위 판별은 기록 전체의 통계로 한다 — D-30
- `speedAccuracy` 0.5 m/s 이하인 점이 3%뿐이고, Doppler 속도가 경로 속도보다 27–30% 낮다 — D-31 (D-01)
- SPEC §3.1에 없는 파일·열(Uncalibrated 2개, 빈 Annotation.csv, `device id` 등)과 빈 파일 처리 — D-32
- 서 있는 동안의 흔들림이 걸음으로 잡혀 지속 보행의 끝이 밀린다 — D-33 (D-02, D-21)
- 100 Hz 설정의 실제 fs가 99.58 Hz라 Q02가 늘 INFO를 낸다 — D-34
