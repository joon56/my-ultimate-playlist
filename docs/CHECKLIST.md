# CHECKLIST — 할 일과 결정 대기

갱신 2026-11-08 밤(분석 규칙 사전 등록 D-43–D-52 반영). 열린 항목만 둔다. 한 줄 = 누구 · 할 일/질문 → 추천. 근거는 '근거'를 펼친다.

- 답은 번호로 준다(예: "K-60 안 넣음"). Claude Code는 답을 받거나 해결·변경되면 항목을 지운다. 결정은 `DECISIONS.md`(새 번호는 D-53부터), 사실은 `DATA_FACTS.md`로 옮긴 뒤 지운다. 지운 번호는 다시 쓰지 않는다.
- '점검 #n'은 2026-11-07 문서 점검의 번호다. A = 팀장, B = 데이터, C = 곡.

## 지금 (실험 1 시작 무렵)

- [ ] **K-12** (A) 프로토콜에 정한 곡 길이(분:초)·박 세기를 알려 준다(Cupid는 원곡으로 정함) → Claude Code가 `music_bpm.csv`에 넣는다(비어 있으면 곡 구간을 계산하지 않는다)
- [ ] **K-54** (B·C) 사전 점검 파일 두 개(리허설 10분, 100걸음)를 올린다 → 받으면 Claude Code가 OS·파일 형식·100걸음을 확인한다
  <details><summary>근거</summary>

  100걸음 파일이 걸음 검출을 검증하는 유일한 기준이다(G1의 100걸음 ±2, D-39). 걸음 수 앱은 직접 센 100걸음을 128로 세었다(D-37). Android면 단위·부호를 다시 판별해야 한다(DATA_FACTS는 iOS만).

  </details>
- [ ] **K-13** (각자) `participants.csv` → A는 나이·키·체중·폰 기종이 남았고, B·C는 전부(폰 기종은 기기 이름 말고)

## 실험 1 진행 중 (11/9–11/22)

- [ ] **K-33** (걷는 사람, 매회) PROTOCOL 2.5 순서로 걷고 그날 안에 zip을 이름 그대로 올린 뒤 앱에서 지운다 → 기록지에 날짜·기록 시작 시각(시:분)을 정확히, 폰을 만졌으면 그 시각을 특이사항에
- [ ] **K-61** (Claude Code, 11/12 G1 전) D-42 구현 → 기록지 CSV와 zip으로 manifest의 walk_id·zip_file 채우기(기록 시작 시각 대조), 특이사항의 폰 만진 시각을 `exclusions.csv`로, Q10을 '기록 시작 시각 ↔ 기록지'로 바꾸고 QA_CHECKLIST Q10 문구 고치기. A는 첫 기록지 CSV와 zip을 `data/raw/`에 넣어 준다
- [ ] **K-34** (셋, 11/12 G1) 1–2회차 파일 6개와 기록지 6줄

## 11/14(실험 2·3) 전

- [ ] **K-62** (A, 11/13까지) 팀 문서의 실험 2·3 절차에 D-44(시행마다 파일 하나)·D-45(범위 밖 음원)·D-47(진자 약 20초)을 넣는다 → START_PROMPT.md 6절 프롬프트
- [ ] **K-40** (각자) `participants.csv`의 `leg_length_m`(대전자~바닥)

## Phase 2·G2(11/18) 전

- [ ] **K-41** (B) DECISIONS D-28·D-29·D-32·D-33·D-34·D-37과 Phase 1에서 더한 초안 키를 검토한다 → 나머지 '열림'·'검증 후 확정'은 표대로
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

- [ ] **K-51** (A) GitHub 저장소를 비공개로 바꾼 뒤 push 요청 → 2026-11-07 확인 때 공개(public), README·SPEC §11은 비공개만 허용
- [ ] **K-60** (A) `results/qa_summary.csv`·`results/qa/`를 git에 넣을지 → 추천: `.gitignore`에 넣는다(다시 만들 수 있고, 남길 결과는 G3에서 `results/frozen/`으로 동결한다)
- [ ] **K-52** (A) `data/raw/`의 zip 4개를 읽기 전용으로 잠근다(README 2단계)
