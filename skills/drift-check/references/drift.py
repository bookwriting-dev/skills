#!/usr/bin/env python3
"""Book-level drift audit: what per-chapter gates cannot see.

The average chapter is fine; the trend is not. This script measures five
proxies across a list of chapter files, in order, and flags trends:

  pet words      content words hot in one chapter or concentrating in the back half
  negation pivot negation constructions per 1k words, first vs second half
  opener formula first-word clusters across chapters (serialized-recap habit)
  closer dies    pairwise similarity of chapter-final sentences (stamped closers)
  specifics      proper-noun-ish tokens per 1k words, as a trend (texture thinning)

These are proxies that correlate with the reader-experience problem, not
measurements of it. The skill that calls this owns interpretation; the script
only reports numbers and candidate clusters.

    python3 drift.py Chapter-001.md Chapter-002.md ...
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from collections import Counter

STOP = set("""a an and the this that these those there here it its he she they them his
her their him of to in on at by for with from as is are was were be been being am do does
did have has had will would could should can may might must not no nor so if but or and
then than when while where what which who whom whose how why all any both each few more
most other some such only own same too very just now one two three i you we us our your
my me up out off over under again further once about into through during before after
above below between because until against itself himself herself themselves myself
yourself""".split())

WORD = re.compile(r"[A-Za-z][A-Za-z']+")


def split_words(text: str) -> list[str]:
    return WORD.findall(text)


def body_lines(path: Path) -> tuple[str, list[str]]:
    """Title (first # heading or filename) and prose lines with headings/fences stripped."""
    title = path.stem
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if title == path.stem:
                title = line.lstrip("#").strip()
            continue
        if line in ("---", "```", "***"):
            continue
        if re.match(r"^[-*] \[", line):  # checkbox apparatus
            continue
        lines.append(line)
    return title, lines


def first_words(lines: list[str], n: int = 6) -> str:
    for line in lines:
        words = split_words(line)
        if len(words) >= 3:
            return " ".join(words[:n])
    return "(none)"


def last_sentence(lines: list[str]) -> str:
    for line in reversed(lines):
        sentences = re.split(r"(?<=[.!?])\s+", line)
        for sentence in reversed(sentences):
            if len(split_words(sentence)) >= 4:
                return sentence
    return "(none)"


def jaccard(a: str, b: str) -> float:
    aw = {w for w in split_words(a.lower()) if w not in STOP}
    bw = {w for w in split_words(b.lower()) if w not in STOP}
    if not aw or not bw:
        return 0.0
    return len(aw & bw) / len(aw | bw)


def skeleton(a: str) -> tuple[str, ...]:
    """The stop-word frame of a sentence: same frame + fresh nouns = a die."""
    return tuple(w for w in split_words(a.lower()) if w in STOP)


def skeleton_match(a: str, b: str) -> float:
    sa, sb = skeleton(a), skeleton(b)
    if len(sa) < 4 or len(sb) < 4 or set(sa) != set(sb):
        return 0.0
    return 1.0


def cluster_pairs(pairs: list[tuple[int, int, float, str]]) -> list[list[int]]:
    """Union-find the flagged pairs into clusters."""
    parent: dict[int, int] = {}

    def find(x: int) -> int:
        while parent.setdefault(x, x) != x:
            x = parent[x] = parent[parent[x]]
        return x

    for i, j, _, _ in pairs:
        parent[find(i)] = find(j)
    groups: dict[int, list[int]] = {}
    for node in sorted(parent):
        groups.setdefault(find(node), []).append(node)
    return sorted(groups.values(), key=lambda g: (-len(g), g[0]))


def main() -> None:
    paths = [Path(p) for p in sys.argv[1:]]
    if len(paths) < 2:
        print("need at least 2 chapter files, in order")
        raise SystemExit(2)

    chapters = []
    for path in paths:
        title, lines = body_lines(path)
        text = " ".join(lines)
        words = split_words(text)
        low = [w.lower() for w in words]
        n = max(len(low), 1)
        neg = len(re.findall(r"\b(?:is|are|was|were|does|do|did)\s+not\b|\bn't\b|\bnever\b|\bno one\b|\bnobody\b", text, re.I))
        caps = sum(
            1
            for i, w in enumerate(words)
            if w[0].isupper()
            and w.lower() not in STOP
            and (i == 0 or words[i - 1] not in (".", "!", "?") and not re.search(r'[.!?]"?$', ""))
        )
        chapters.append({
            "title": title,
            "k": n / 1000.0,
            "neg": neg / (n / 1000.0),
            "spec": caps / (n / 1000.0),
            "open": first_words(lines),
            "close": last_sentence(lines),
            "words": Counter(w for w in low if w not in STOP and len(w) > 3),
        })

    total_words = sum(len(split_words(" ".join(body_lines(p)[1]))) for p in paths)
    book_freq = Counter()
    for c in chapters:
        book_freq.update(c["words"])

    print(f"Drift audit — {len(chapters)} chapters, ~{total_words:,} words\n")
    print(f"{'ch':>4} {'words':>6} {'neg/1k':>7} {'spec/1k':>8}  opener")
    for i, c in enumerate(chapters, 1):
        print(f"{i:>4} {int(c['k']*1000):>6} {c['neg']:>7.1f} {c['spec']:>8.1f}  {c['open'][:48]}")

    half = len(chapters) // 2
    front_neg = sum(c["neg"] for c in chapters[:half]) / max(half, 1)
    back_neg = sum(c["neg"] for c in chapters[half:]) / max(len(chapters) - half, 1)
    front_spec = sum(c["spec"] for c in chapters[:half]) / max(half, 1)
    back_spec = sum(c["spec"] for c in chapters[half:]) / max(len(chapters) - half, 1)
    print(f"\nNegation-pivot density: front half avg {front_neg:.1f}/1k vs back half {back_neg:.1f}/1k"
          f"  {'— RISING (house style calcifying)' if back_neg > front_neg * 1.3 else ''}")
    print(f"Specifics density:      front half avg {front_spec:.1f}/1k vs back half {back_spec:.1f}/1k"
          f"  {'— FALLING (texture thinning)' if back_spec < front_spec * 0.7 else ''}")

    print("\nPet-word candidates (hot in one chapter ≥3× book rate, or ≥70% back-half):")
    found = False
    for word, total in book_freq.most_common(400):
        if total < 8:
            continue
        per_ch = [(i + 1, c["words"].get(word, 0)) for i, c in enumerate(chapters)]
        hot = [(i, cnt) for i, cnt in per_ch if cnt >= 3 and cnt >= 3 * total / len(chapters)]
        back_share = sum(cnt for i, cnt in per_ch if i > half) / total
        if hot or back_share >= 0.7:
            found = True
            detail = (f"hot in ch{hot[0][0]} ({hot[0][1]}×)" if hot
                      else f"{back_share:.0%} of uses in back half")
            print(f"  {word!r}: {total}× — {detail}")
    if not found:
        print("  none")

    print("\nOpener clusters (shared first 2 words, ≥3 chapters):")
    found = False
    opener_pairs = Counter(" ".join(c["open"].split()[:2]).lower() for c in chapters)
    for prefix, cnt in opener_pairs.most_common(5):
        if cnt >= 3:
            found = True
            members = [i + 1 for i, c in enumerate(chapters)
                       if " ".join(c["open"].split()[:2]).lower() == prefix]
            print(f"  {prefix!r}: chapters {members}")
    if not found:
        print("  none — openers vary")

    print("\nCloser die candidates:")
    found = False
    pairs = []
    for i in range(len(chapters)):
        for j in range(i + 1, len(chapters)):
            a, b = chapters[i]["close"], chapters[j]["close"]
            sim = jaccard(a, b)
            if sim >= 0.45:
                pairs.append((i, j, sim, "verbatim"))
            elif skeleton_match(a, b):
                pairs.append((i, j, 1.0, "same frame, fresh nouns"))
    for cluster in cluster_pairs(pairs):
        found = True
        members = ", ".join(f"ch{m+1}" for m in cluster)
        kind = next(kind for i, j, _, kind in pairs if i in cluster and j in cluster)
        print(f"  {members}  ({kind})")
        for n in cluster[:3]:
            print(f"    {chapters[n]['close'][:90]}")
    if not found:
        print("  none — closers vary")


if __name__ == "__main__":
    main()
