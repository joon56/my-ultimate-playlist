# walk-music — 내 플레이리스트가 걸음을 바꾼다 (분석 저장소)

연세대 Healthcare Biomechanics 팀 프로젝트(A·B·C)의 데이터 분석 저장소다. 폰의 Sensor Logger 기록에서 케이던스, 음악 동조율, 속도·보폭, 발 디딤 충격, 체공, 점프·다리 강성, 다리 진자 주기(곧은·굽힌 다리)를 계산하고, 가설 1–4를 사람별로 판정하고, 논문과 발표용 표·그림을 만든다. 팀 문서 「내 플레이리스트가 걸음을 바꾼다 — 프로젝트 통합본」의 연구계획, 실험 1 프로토콜, 실행 스케줄 탭에서 분석에 필요한 부분을 옮긴 것이 `docs/`다.

## 시작하기

1. 이 폴더를 풀어 Claude Code의 작업 폴더로 쓴다. `.claude`와 `.gitignore`는 점으로 시작해 탐색기에서 숨겨져 있을 수 있으니 지우지 않는다. `git init`을 한 뒤 올린다면 **비공개 저장소**로만 올린다(데이터에 평소 걷는 길이 들어 있다).
2. 시범 측정 zip을 `data/raw/`에 넣고 읽기 전용으로 잠근다. macOS·Linux는 `chmod -R a-w data/raw`, Windows는 폴더 속성에서 읽기 전용으로 바꾼다.
3. 이 폴더에서 Claude Code를 열고 `START_PROMPT.md`의 프롬프트를 붙여 넣는다.
4. Claude Code가 계획을 보여주면 읽고 승인한다. 이후 순서는 아래 로드맵과 같다.

## 폴더

```
walk-music/
├─ CLAUDE.md            Claude Code가 매 세션 읽는 규칙
├─ START_PROMPT.md      처음 붙여 넣을 프롬프트
├─ docs/
│  ├─ SPEC.md           분석 명세: 정의, 처리 순서, 출력, 테스트 수치
│  ├─ PROTOCOL.md       실험 절차 요약
│  ├─ QA_CHECKLIST.md   품질 검사 Q01–Q17, 관문 G1–G3 기준
│  ├─ DECISIONS.md      열린 결정과 변경 기록
│  ├─ DATA_FACTS.md     실제 파일에서 확인한 사실(Phase 0에서 채움)
│  ├─ HANDCALC.md       손계산 노트(교안 예제 ↔ 우리 데이터, SPEC §9와 같은 숫자)
│  ├─ CHANGES_1108.md   11/8 프로토콜 수정판에 따라 바뀐 문서 목록과 적용 방법
│  └─ CHANGES_1109.md   11/9 추가(점프·180·195%·굽힌 진자·측정 검증·결과 전 기준)와 적용 방법
├─ config/params.toml   모든 문턱과 파라미터
├─ data/                CSV 템플릿과 설명(data/README.md). raw/, interim/, private/는 git 제외
├─ tools/assign.py      회차 배정표 재현 스크립트
├─ results/             결과(Phase 1부터)
└─ .claude/settings.json  권한 설정
```

Phase 1에서 `pyproject.toml`, `src/walkmusic/`, `tests/`가 생긴다.

## 사람이 채울 것

| 누가 | 무엇을 | 언제까지 |
|---|---|---|
| C | `data/music_bpm.csv`의 곡 길이(`duration_s`)와 박 세기(`bpm_count_1`, `bpm_count_2`) | 11/9 전 |
| 각자 | `data/participants.csv`: 나이, 키, 체중, 폰 기종, 폰 위치, 측정 구간 거리 | 11/9 전 |
| 각자 | `data/private/sections.csv`: 측정 구간 시작·끝 좌표(`sections.example.csv` 형식) | 11/9 전 |
| 각자 | `participants.csv`의 다리 길이(대전자~바닥), 허벅지 길이(대전자~무릎 관절선), 정강이 길이(무릎 관절선~바깥 복사뼈) | 11/14 |
| B | `docs/DECISIONS.md`의 결과 전 기준 D-33–D-36(실질적 변화·신뢰구간·분석 고정·처방 범위) 확인 | G1(11/12) 전 |
| B(카메라 담당 메모로) | `data/video_checks.csv`(점프 체공 프레임, 진자 10번 흔들림 시간), `data/video_markers.csv`(착지·굽힌 무릎 마커 좌표) | 11/18, 11/22 |
| 각자 | `data/debrief.csv` 종료 설문 한 줄 | 15회를 마친 날 |
| B | `docs/DECISIONS.md`의 11/9 전 항목(D-01, D-03, D-04, D-05, D-10, D-13) 확인 | 11/9 전 |
| 걷는 사람 | 걸을 때마다 `manifest.csv` 한 줄(구글 시트 기록지를 내려받아 맞춰 둔다). 기록 시작 날짜·시각(시:분)을 정확히 적고, zip은 내보낸 이름 그대로 `data/raw/<사람>/`에 둔다 | 걸은 날 안에 |

## 로드맵

| Phase | 기간 | 내용 |
|---|---|---|
| 0 | 11/7–11/8 | 시범 측정 파일에서 데이터 사실 확인 |
| 1 | ~11/12 (G1) | 뼈대, 불러오기, 품질 검사, 걸음 검출 초안, 합성 데이터 생성기 |
| 2 | ~11/18 (G2) | 실험 1 지표, 평소 케이던스, 가설 판정, 시나리오 신호, 그림 2·3 |
| 3 | 11/14 데이터 ~11/18 | 실험 2·3 |
| 4 | ~11/24 (G3) | 전체 표·그림, 데이터 표 v1.0 동결 |
| 5 | 11/24 이후, 요청할 때만 | 웹 데모 |

자세한 완료 기준은 `docs/SPEC.md` §12.

## 개인정보

위치 기록에는 집과 학교를 잇는 평소 길이 그대로 들어 있다. 좌표는 속도·거리 계산에만 쓰고 결과, 로그, 그림, 커밋에 남기지 않는다. `data/raw`, `data/interim`, `data/private`는 `.gitignore`로 제외했다. 기기 이름 같은 식별 정보는 문서에 쓰지 않는다. 보강 참가자(친구)의 데이터는 동의 범위 안에서 ID(N1–N4)로만 다룬다.
