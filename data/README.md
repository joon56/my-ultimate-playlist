# data/ — 폴더와 CSV 설명

CSV는 UTF-8(BOM 없음)이다. 구글 시트에서 내려받았을 때 BOM이 붙어 있으면 읽을 때 `encoding="utf-8-sig"`를 쓴다. 날짜는 `YYYY-MM-DD`, 시각은 24시간제 `HH:MM`(Asia/Seoul)이다. 빈 칸은 '모름 또는 해당 없음'이고, 0으로 채우지 않는다.

## 폴더

| 위치 | 내용 | git |
|---|---|---|
| `raw/` | 내보낸 zip 원본(이름을 바꾸지 않는다). 사람별 하위 폴더 `raw/<사람>/`에 두고(시범 zip은 `raw/` 바로 아래도 된다) 읽기 전용으로 둔다 | 제외 |
| `interim/` | zip을 푼 파일, 중간 계산 | 제외 |
| `private/` | 좌표가 든 파일(`sections.csv`) | 제외 |
| 나머지 CSV | 아래 표 | 포함 |

## 파일 한눈에

| 파일 | 한 줄 | 채우는 사람 | 언제까지 |
|---|---|---|---|
| `assignment.csv` | 회차 배정표(고정). `tools/assign.py`로 재현된다 | 만들어 둠 | — |
| `manifest.csv` | 실험 1 기록지(회차당 1줄)와 시범·사전 점검 기록 | 걷는 사람, A가 점검 | 걸은 날 안에 |
| `participants.csv` | 사람 정보 | 각자 | 나이·키·체중·폰·측정 구간 거리는 11/9 전, 다리·허벅지·정강이 길이는 11/14 |
| `music_bpm.csv` | 곡 12+2: BPM, **곡 길이** | C | `duration_s`는 11/9 전 |
| `song_ratings.csv` | 곡별 좋아하는 정도·아는 정도 | 각자 | 처음 듣고 바로 |
| `exclusions.csv` | 수동 제외 구간(계단·인파·폰 만짐) | 걷는 사람 | 걸은 뒤 |
| `exp2_trials.csv` | 챌린지 기록지(180·195% 단계, 점프 기록 포함) | 현장 기록 담당 | 11/14 |
| `exp3_swings.csv` | 진자 시행 목록(곧은·굽힌 다리) | 현장 | 11/14 |
| `video_checks.csv` | 영상에서 읽은 시간 값(점프 체공 프레임, 진자 10번 흔들림 시간) | 카메라 담당의 메모를 B가 옮김 | 11/18 |
| `video_markers.csv` | 영상 프레임의 테이프 마커 좌표(착지 순간, 굽힌 다리 진자) | B 또는 C | 11/22 |
| `debrief.csv` | 종료 설문(15회를 마친 뒤 한 번) | 각자 | 15회를 마친 날 |
| `sections.example.csv` | 측정 구간 좌표 예시(가짜 값) | — | — |
| `private/sections.csv` | 측정 구간 좌표(실제) | 각자 | 11/9 전 |

## 열 설명

### assignment.csv

`participant`(A·B·C), `walk_no`(1–15), `condition`(S=무음, P1–P4), `start_song`(1–3, 무음은 비움). 바꾸지 않는다.

### manifest.csv

| 열 | 설명 |
|---|---|
| `walk_id` | 분석용 이름. 코드가 만든다: 실험 1은 `E1_<사람>_<회차2자리>_<조건>_<MMDD>`(예: `E1_B_07_P1_1113`). 비워 두거나 같은 값이어야 한다. 사전 점검은 `TEST_<사람>_<MMDD>_<종류>`(예: `TEST_B_1108_steps100`), 11/7 시범은 `TEST_A_1107`. A의 11/8 사전 점검은 이미 등록한 `TEST_A_1108_1`–`_3`(리허설·100걸음·메트로놈)을 그대로 쓴다. zip은 이름을 바꾸지 않고 올리므로 `zip_file`로 연결한다 (SPEC §3.4, DECISIONS D-27) |
| `experiment` | `E1` 또는 `TEST` (실험 2·3은 각자의 CSV를 쓴다) |
| `participant` | A·B·C (보강 참가자는 N1–N4) |
| `walk_no` | 1–15. 다시 걸은 회차는 16부터. 시범·사전 점검(`TEST`)은 비운다 |
| `redo_of` | 다시 걸은 회차가 대신하는 원래 회차 번호. 아니면 비움 |
| `date` | 걸은 날 |
| `start_time` | 기록을 시작한 시각(시:분). zip의 기록 시작 시각과 맞추는 데 쓰므로 정확히 적는다. 파일 이름의 시각은 UTC라 베끼지 않는다 |
| `condition` | S, P1–P4. 사전 점검(`TEST`)은 `rehearsal`(10분 리허설) 또는 `steps100`(100걸음). A의 11/8 메트로놈 점검은 `metronome` |
| `start_song` | 처음 튼 곡 1–3. 무음은 비움 |
| `direction` | 가는 길 / 오는 길 |
| `weather` | 맑음 / 흐림 / 비 |
| `temp_c` | 대략의 기온(숫자) |
| `bag` | 없음 / 가벼움 / 무거움 |
| `hurried` | 예 / 아니오 |
| `music_offset_s` | 기록 시작부터 음악이 시작될 때까지 대략 몇 초. 모르면 비움(기본 3초를 쓴다) |
| `songs_played` | 실제로 들은 곡 순서를 세미콜론으로. 예: `P3-2;P3-3;P3-1`. 목록 밖의 곡은 `X:제목`. 끝나면 마지막 곡의 다음 곡부터 플레이리스트 순서로 이어진다고 본다. 비우면 `start_song`부터 순환 |
| `hand_step_count` | 직접 센 걸음 수(사전 점검용 기록). `steps100`은 100 |
| `hand_step_note` | 센 구간 설명. 센 구간을 기계가 읽게 하려면 `start=MM:SS end=MM:SS`(기록 시작 후 시각)를 넣는다 |
| `zip_file` | Sensor Logger가 내보낸 원본 zip 이름(`.zip` 포함, 바꾸지 않은 이름). 분석 쪽이 `results/zip_links.csv`로 연결을 확인한 뒤 적는다 |
| `status` | 비우면 정상. `redo`(끊겨서 다시 걸음, 분석 제외) · `excluded`(분석 제외, 이유는 `notes`) · `no_song_segments`(곡 순서를 몰라 회차 단위로만 씀) · `test` |
| `notes` | 기록지 '특이사항' 그대로. 코드는 해석하지 않는다. 뺄 구간은 `exclusions.csv`에 옮겨 적는다 |

### participants.csv

`participant`, `role`, `age`, `height_cm`, `mass_kg`, `leg_length_m`(대전자~바닥 높이, 미터), `phone_model`(기종만. 기기 이름이 아니다), `phone_os`(iOS/Android와 버전), `carry_position`(예: 허리 파우치, 등 쪽·가로), `earphones`, `section_distance_m`(측정 구간 거리, 지도앱 거리재기), `notes`, `thigh_length_m`(대전자~무릎 바깥 관절선, 미터), `shank_length_m`(무릎 관절선~바깥 복사뼈, 미터). 뒤의 두 열은 11/9에 맨 끝에 더했고 11/14에 잰다.

### music_bpm.csv

`playlist`(P1–P4), `order`(1–3, 예비 곡은 비움), `title`, `artist`, `bpm_public`(공개된 값), `duration_s`(**곡 길이 초. C가 채운다**), `bpm_count_1`, `bpm_count_2`(C가 30초 박 세기 × 2 한 값), `is_spare`(1이면 예비 곡), `source_url`, `note`.
목록 밖의 곡이 나온 회차가 있으면 `playlist=X`로 행을 추가하고 BPM과 길이를 채운다. 채우지 못하면 그 구간은 쓰지 않는다.

### song_ratings.csv

`participant`, `title`, `liking_1to5`, `familiarity_1to5`.

### exclusions.csv

`walk_id`, `start_s`, `end_s`(기록 시작 후 초, 센서 시간축), `reason`(`stairs` · `crowd` · `phone_touch` · `stop` · `other`), `note`.

### exp2_trials.csv

| 열 | 설명 |
|---|---|
| `trial_id` | 파일 이름 규칙대로. 예: `E2_A_150_2`, 무음은 `E2_A_S_1`, 현장에서 더 한 단계는 `E2_A_180_1`, 점프 기록은 `E2_A_J_1` |
| `runner` | A·B·C |
| `ratio_pct` | 100·120·135·150·165(현장에서 더 하면 180·195), 무음은 `S`, 점프 기록은 `J` |
| `repeat` | 1–2(180·195%와 점프 기록은 1) |
| `bpm_played` | 실제로 틀어 준 BPM(무음은 비움) |
| `direction` | `→` 또는 `←` |
| `pc_field_spm` | 현장에서 음원을 고르려고 사람이 계산해 적은 PC(걸음/분). 코드는 무음 시행에서 다시 계산해 비교한다 |
| `t30_s` | 30 m 통과 시간(영상에서 읽은 초). 점프 기록은 비운다 |
| `steps_N` | 30 m 동안의 걸음 수(영상에서 센 값) |
| `gait_video` | 영상 판정 `walk` / `run` / `mixed` |
| `zip_file` | 이 시행의 센서 zip(내보낸 이름 그대로). 비우면 분석 쪽에서 기록 시작 순서로 채운다(D-55) |
| `t_in_sensor_s`, `t_out_sensor_s` | 5 m 표시와 35 m 표시를 지난 시각을 센서 시간축(기록 시작 후 초)으로 옮긴 값. 한 기록에 시행이 하나뿐이고 모르면 비운다 |
| `notes` | 메모 |
| `video_file` | 이 시행을 찍은 영상 파일 이름(카메라 담당이 적는다) |
| `video_fps` | 그 영상의 fps(점프는 120 이상의 슬로모션) |

### exp3_swings.csv

`trial_id`(예: `E3_A_1`, 무릎 굽힌 다리는 `E3_A_K_1`), `runner`, `repeat`, `zip_file`, `valid`(1/0), `notes`, `knee`(`straight` 또는 `bent`), `video_file`(촬영한 시행만), `video_fps`. 뒤의 세 열은 11/9에 더했다.

### video_checks.csv

영상에서 사람이 읽은 시간 값이다. 한 줄에 값 하나.

| 열 | 설명 |
|---|---|
| `trial_id` | `E2_A_J_1`, `E3_A_K_1`, `E2_A_150_1`처럼 기록지의 시행 |
| `kind` | `jump_flight`(이륙~착지) · `swing_10`(10번 흔들리는 시간) · `run_contact`, `run_flight`(선택, 달리기 한 걸음의 접촉·체공) |
| `event_no` | 몇 번째 점프·걸음인가(1부터). `swing_10`은 1 |
| `video_file` | 영상 파일 이름 |
| `fps` | 영상 fps(슬로모션이면 실제 촬영 fps, 예: 240) |
| `frames` | 센 프레임 수. 시간을 초로 쟀으면 비운다 |
| `value_s` | 초. `frames`가 있으면 비워도 된다(코드가 frames ÷ fps로 계산한다) |
| `measurer` | 읽은 사람 |
| `notes` | 메모 |

### video_markers.csv

영상 한 프레임에서 읽은 테이프 마커의 픽셀 좌표다(x는 오른쪽, y는 아래쪽이 +). 각도는 코드가 계산한다(SPEC §5.7).

| 열 | 설명 |
|---|---|
| `trial_id` | 시행 |
| `event` | `contact`(챌린지 착지 순간) · `pendulum_bent`(굽힌 다리 진자의 무릎 각) |
| `event_no` | 몇 번째 착지인가(1부터) |
| `video_file`, `frame_no` | 영상과 프레임 번호 |
| `hip_x`, `hip_y` | 대전자 마커 |
| `knee_x`, `knee_y` | 무릎 바깥(관절선) 마커 |
| `ankle_x`, `ankle_y` | 바깥 복사뼈 마커 |
| `measurer`, `notes` | 읽은 사람, 메모 |

### debrief.csv

종료 설문이다. 15회를 마친 뒤 한 번만 적고 매 회차에는 묻지 않는다(DECISIONS D-42).

`participant`, `date`, `tried_to_sync`(`yes`/`no`), `sync_walks`(맞추려 한 회차 번호. 여러 개면 `;`로 구분), `sync_songs`(곡 이름, `;`로 구분), `guessed_bpm_order`(`yes`/`no`/`partly`), `notes`.

### private/sections.csv

`participant`, `seq`(1부터, 걷는 순서), `lat`, `lon`, `label`. 첫 점이 측정 구간 시작, 마지막 점이 끝이다. 파일 형식은 `sections.example.csv`와 같다. **이 파일은 git에 올리지 않는다.** 출력과 로그에 값을 쓰지 않는다.
