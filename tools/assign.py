"""실험 1 회차 배정표 생성기 (재현용).

2026-11-07에 만든 스크립트를 그대로 옮기고, CSV 출력만 더했다.
같은 시드(A 20261107, B 20261108, C 20261109)면 data/assignment.csv와 똑같이 나와야 한다.
조건 로직은 바꾸지 말 것: 바꾸면 이미 걷기 시작한 배정과 달라진다.

사용: python tools/assign.py            # 표를 화면에 출력
      python tools/assign.py --csv PATH # long 형식 CSV로 저장
"""
import argparse
import csv
import random

conds = ['무음', 'P1', 'P2', 'P3', 'P4']


def valid(seq):
    # 같은 조건이 연달아 나오지 않는다
    for a, b in zip(seq, seq[1:]):
        if a == b:
            return False
    # 각 조건이 홀수·짝수 회차(1부터 셈)에 모두 나온다
    for c in conds:
        pos = [i + 1 for i, x in enumerate(seq) if x == c]
        if not (any(p % 2 == 1 for p in pos) and any(p % 2 == 0 for p in pos)):
            return False
    return True


def make(seed):
    rng = random.Random(seed)
    while True:
        # 1블록: 무음을 맨 앞에 고정(파일럿), 나머지는 섞기
        rest = conds[1:]
        rng.shuffle(rest)
        b1 = ['무음'] + rest
        b2 = conds[:]
        rng.shuffle(b2)
        b3 = conds[:]
        rng.shuffle(b3)
        seq = b1 + b2 + b3
        if valid(seq):
            return seq


def label(seq):
    count = {c: 0 for c in conds}
    out = []
    for c in seq:
        count[c] += 1
        if c == '무음':
            out.append('무음')
        else:
            out.append(f"{c} {'①②③'[count[c]-1]}")
    return out


PEOPLE = {'A': 20261107, 'B': 20261108, 'C': 20261109}


def rows():
    """(participant, walk_no, condition, start_song) 목록. 조건은 S/P1..P4, 무음은 S, start_song은 1–3."""
    out = []
    for p, seed in PEOPLE.items():
        for i, lab in enumerate(label(make(seed)), start=1):
            if lab == '무음':
                out.append((p, i, 'S', ''))
            else:
                c, s = lab.split()
                out.append((p, i, c, '①②③'.index(s) + 1))
    return out


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv')
    a = ap.parse_args()
    seqs = {p: label(make(s)) for p, s in PEOPLE.items()}
    for i in range(15):
        print(i + 1, ' | '.join(seqs[p][i] for p in 'ABC'))
    for p, s in seqs.items():
        raw = [x.split()[0] for x in s]
        print(p, {c: raw.count(c) for c in conds})
    if a.csv:
        with open(a.csv, 'w', newline='', encoding='utf-8') as f:
            w = csv.writer(f)
            w.writerow(['participant', 'walk_no', 'condition', 'start_song'])
            w.writerows(rows())
        print('saved', a.csv)
