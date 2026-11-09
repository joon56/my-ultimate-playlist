# CHECKLIST — 할 일과 결정 대기

갱신 2026-11-09(키트 v0.3 반영, D-29·D-30·D-32–D-36 확정, D-64 공개 저장소). 열린 항목만 둔다. 한 줄 = 누구 · 할 일/질문 → 추천. 근거는 '근거'를 펼친다.

- 답은 번호로 준다(예: "K-60 안 넣음"). Claude Code는 답을 받거나 해결·변경되면 항목을 지운다. 결정은 `DECISIONS.md`(새 번호는 D-65부터), 사실은 `DATA_FACTS.md`로 옮긴 뒤 지운다. 지운 번호는 다시 쓰지 않는다.
- '점검 #n'은 2026-11-07 문서 점검의 번호다. A = 팀장, B = 데이터, C = 곡.

## 지금 (실험 1 시작 무렵)

- [ ] **K-12** (A) 프로토콜에 정한 곡 길이(분:초)·박 세기를 알려 준다(Cupid는 원곡으로 정함) → Claude Code가 `music_bpm.csv`에 넣는다(비어 있으면 곡 구간을 계산하지 않는다)
- [ ] **K-54** (B·C) 사전 점검 파일 두 개(리허설 10분, 100걸음)를 올린다 → 받으면 Claude Code가 OS·파일 형식·100걸음을 확인한다
  <details><summary>근거</summary>

  100걸음 파일이 걸음 검출을 검증하는 유일한 기준이다(G1의 100걸음 ±2, D-27). 걸음 수 앱은 직접 센 100걸음을 128로 세었다(D-30). Android면 단위·부호를 다시 판별해야 한다(DATA_FACTS는 iOS만).

  </details>
- [ ] **K-13** (각자) `participants.csv` → A는 나이·키·체중·폰 기종이 남았고, B·C는 전부(폰 기종은 기기 이름 말고)

## 실험 1 진행 중 (11/9–11/22)

- [ ] **K-33** (걷는 사람, 매회) PROTOCOL 2.5 순서로 걷고 그날 안에 zip을 이름 그대로 올린 뒤 앱에서 지운다 → 기록지에 날짜·기록 시작 시각(시:분)을 정확히, 폰을 만졌으면 그 시각을 특이사항에
- [ ] **K-61** (A → Claude Code, 기록지가 올 때마다) zip은 이름 그대로 `data/raw/<사람>/`에, 기록지 CSV는 `data/raw/`에 넣는다 → Claude Code가 manifest 줄을 옮기고 `qa --links` 제안(기록 시작 시각 ±90 s, D-27)으로 `zip_file`을 채운 뒤 A에게 확인받는다. 특이사항의 폰 만진 시각은 `exclusions.csv`로 옮긴다(연결 기능과 Q10은 2026-11-09 구현)
- [ ] **K-34** (셋, 11/12 G1) 1–2회차 파일 6개와 기록지 6줄
- [ ] **K-66** (B·C → A, 11/12 G1 전) 측정 구간 시작·끝 좌표와 지도 거리 → A가 좌표는 `data/private/sections.csv`(git 제외), 거리는 `participants.csv`의 `section_distance_m`에 넣는다. 좌표는 채팅·커밋에 올리지 않는다(G1의 GPS 기준 Q08a에 필요. A는 있음)

## 11/14(실험 2·3) 전

- [ ] **K-62** (A, 11/13까지) 팀 문서의 실험 2·3 절차에 D-55(시행마다 파일 하나)·D-56(범위 밖 음원)·D-58(진자 약 20초)을 넣는다 → START_PROMPT.md 6절 프롬프트
- [ ] **K-40** (각자, 11/14 현장) `participants.csv`의 `leg_length_m`(대전자~바닥), `thigh_length_m`(대전자 → 무릎 바깥 관절선), `shank_length_m`(무릎 관절선 → 바깥 복사뼈)
- [ ] **K-64** (A, 11/13까지) 집에서 점프 기록 1개(손 허리, 점프 전 2초 가만히, 3회)와 무릎 굽힌 진자 기록 1개를 미리 찍어 올린다 → Claude Code가 점프·진자 계산이 되는지 확인한다(D-37, D-41)
- [ ] **K-65** (B, 11/14 전) D-37 점프·D-39 달리기 스프링·D-41 무릎 굽힌 진자의 기본값을 확인한다 → 추천: 표대로

## Phase 2·G2(11/18) 전

- [ ] **K-41** (B) DECISIONS D-43·D-44·D-47·D-48·D-49와 Phase 1에서 더한 초안 키를 검토한다 → 나머지 '열림'·'검증 후 확정'은 표대로
- [ ] **K-49** (C) 곡 사이 전환 시간을 집에서 잰다 → 짧은 곡 3개를 이어 틀고 1번 곡 시작~3번 곡 시작 스톱워치 시간에서 앱의 1·2번 곡 길이 합을 빼고 2로 나눔(점검 #24)
- [ ] **K-50** (A, 낮음) 입력·출력 이름 겹침(`participants.csv`, `exp3_swings.csv`), `hand_count` ↔ `hand_step_count`(점검 #12)

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

## 기타

- [ ] **K-52** (A) `data/raw/`의 zip 4개를 읽기 전용으로 잠근다(README 2단계)
- [ ] **K-63** (A, B·C 값을 넣기 전) 저장소가 공개라 `participants.csv`의 나이·키·체중과 manifest의 기록 날짜·시각(통학 시간대)도 공개된다 → 추천: B·C 값을 넣기 전에 비공개로 바꾸거나 B·C 동의를 받는다(D-64)
