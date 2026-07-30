"""Check the flat projection of a submission. See data/flat_projection.md.

    python3 score.py --pred out/flat.json

Standard library only, no API keys. Because you define your own themes, nothing
here compares your names to ours. It reports:

  ROWS       well-formed rows, unknown review ids, duplicated rows
  TREE       whether your three tiers form a consistent hierarchy
  SHAPE      how many distinct themes at each tier, and how they are distributed
  EXTRAS     any additional fields your projection carries
  SPREAD     rows per review, and the distribution

These are measurements, not marks. What they imply for your design is yours to
work out and to defend in NOTES.html.
"""

import argparse
import json
from collections import Counter, defaultdict
from statistics import mean, median

# Broadest to finest. The keys are the field names in the flat projection; the
# labels are what gets printed.
TIERS = ("strategic_theme", "midlevel_theme", "specific_theme")
LABEL = {"strategic_theme": "strategic", "midlevel_theme": "midlevel",
         "specific_theme": "specific"}
STRATEGIC, MIDLEVEL, SPECIFIC = TIERS


def row_id(row: dict):
    """`review_id` is documented; `id` is accepted so nothing fails over a key
    name rather than its substance."""
    return row.get("review_id") or row.get("id")


def load_pred(path: str) -> dict:
    """Flat rows -> {review_id: [row, ...]}. Rows are grouped, never counted as
    reviews: a review with no rows simply does not appear as a key."""
    data = json.load(open(path, encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("rows") or data.get("themes") or next(
            (v for v in data.values() if isinstance(v, list)), [])
    grouped = defaultdict(list)
    for row in data:
        if isinstance(row, dict):
            grouped[row_id(row)].append(row)
    return dict(grouped)


def check_rows(pred: dict, reviews: dict) -> list:
    """Row-level faults only. How many reviews carry rows is reported under
    SPREAD as a number — it is not a fault, and this function does not judge it."""
    problems = []
    unknown = sorted(rid for rid in pred if rid is not None and rid not in reviews)
    if unknown:
        problems.append(f"{len(unknown)} review_id values are not in the dataset "
                        f"(e.g. {unknown[0]!r})")
    if None in pred:
        problems.append(f"{len(pred[None])} rows have no review_id")
    for rid, rows in pred.items():
        seen = set()
        for n, row in enumerate(rows):
            where = f"{rid} row {n}"
            for tier in TIERS:
                v = row.get(tier)
                if not isinstance(v, str) or not v.strip():
                    problems.append(f"{where}: missing or empty '{tier}'")
            triple = tuple(row.get(t) for t in TIERS)
            if triple in seen:
                problems.append(f"{where}: {' > '.join(str(t) for t in triple)} "
                                f"duplicated for this review")
            seen.add(triple)
    return problems


def check_tree(pred: dict) -> None:
    """A specific theme must always hang off the same midlevel, and a midlevel off
    the same strategic — otherwise the tiers are not a hierarchy and per-theme
    counts built on them do not mean what they appear to."""
    parents = {SPECIFIC: defaultdict(set), MIDLEVEL: defaultdict(set)}
    for rows in pred.values():
        for row in rows:
            s, m, sp = (row.get(t) for t in TIERS)
            if sp:
                parents[SPECIFIC][sp].add(m)
            if m:
                parents[MIDLEVEL][m].add(s)

    bad = {tier: {k: v for k, v in d.items() if len(v) > 1}
           for tier, d in parents.items()}
    print("TREE")
    if not bad[SPECIFIC] and not bad[MIDLEVEL]:
        print("  ok — every specific theme has one midlevel parent, every midlevel "
              "has one strategic")
        return
    for tier, parent_label in ((MIDLEVEL, "strategic"), (SPECIFIC, "midlevel")):
        for name, ps in list(bad[tier].items())[:6]:
            print(f"  FAIL  {LABEL[tier]} theme {name!r} appears under {len(ps)} "
                  f"{parent_label} parents: {sorted(str(p) for p in ps)}")
    hidden = sum(max(len(b) - 6, 0) for b in bad.values())
    if hidden:
        print(f"  ... and {hidden} more")


def report_shape(pred: dict) -> None:
    counts = {t: Counter() for t in TIERS}
    for rows in pred.values():
        for row in rows:
            for t in TIERS:
                counts[t][row.get(t)] += 1

    total = sum(counts[SPECIFIC].values())
    print("SHAPE")
    print(f"  total rows                   {total}")
    for t in TIERS:
        print(f"  distinct {LABEL[t] + ' themes':<20} {len(counts[t])}")
    if not total:
        return

    leaf = counts[SPECIFIC]
    print(f"  rows per specific theme      mean {total / len(leaf):.1f}  "
          f"median {median(leaf.values()):.0f}  max {max(leaf.values())}")
    once = sum(1 for c in leaf.values() if c == 1)
    twice = sum(1 for c in leaf.values() if c <= 2)
    print(f"  specific used once           {once} of {len(leaf)} "
          f"({once / len(leaf):.0%})")
    print(f"  specific used twice or less  {twice} of {len(leaf)} "
          f"({twice / len(leaf):.0%})")
    for t in (STRATEGIC, MIDLEVEL):
        top, n = counts[t].most_common(1)[0]
        print(f"  largest {LABEL[t]:<10}           {n} of {total} rows "
              f"({n / total:.0%}) — {top!r}")
    print("  most frequent specific       "
          f"{', '.join(f'{c} ({n})' for c, n in leaf.most_common(5))}")


def report_extras(pred: dict) -> None:
    fields = Counter()
    for rows in pred.values():
        for row in rows:
            for k in row:
                if k not in TIERS and k not in ("review_id", "id"):
                    fields[k] += 1
    print("EXTRAS")
    if not fields:
        print("  none — review_id plus the three tiers")
    else:
        for k, n in fields.most_common():
            print(f"  {k:<27}  on {n} rows")


def report_spread(pred: dict, reviews: dict) -> None:
    counts = [len(pred.get(rid) or []) for rid in reviews]
    dist = Counter(counts)
    print("SPREAD")
    print(f"  reviews with rows            {sum(1 for c in counts if c)} of "
          f"{len(reviews)}")
    print(f"  rows per review              mean {mean(counts):.2f}  "
          f"min {min(counts)}  max {max(counts)}")
    shown = dict(sorted(dist.items())[:9])
    print(f"  distribution                 {shown}{' ...' if len(dist) > 9 else ''}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pred", required=True)
    ap.add_argument("--reviews", default="data/reviews.json")
    args = ap.parse_args()

    reviews = {r["id"]: r for r in json.load(open(args.reviews, encoding="utf-8"))}
    pred = load_pred(args.pred)

    problems = check_rows(pred, reviews)
    print("ROWS")
    if problems:
        for p in problems[:20]:
            print(f"  FAIL  {p}")
        if len(problems) > 20:
            print(f"  ... and {len(problems) - 20} more")
    else:
        print(f"  ok — {sum(len(v) for v in pred.values())} rows, all well-formed")

    check_tree(pred)
    report_shape(pred)
    report_extras(pred)
    report_spread(pred, reviews)


if __name__ == "__main__":
    main()
