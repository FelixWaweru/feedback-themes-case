# Your output, and the flat projection

## Choose the representation that best expresses the categorisation

This is the file you are actually assessed on, so design it deliberately.

Pick the JSON structure that represents your categorisation *best* — the one that
carries the meaning of what you built, that another engineer could pick up, and
that you would be willing to defend as the right model for this problem. Nest it,
normalise it, denormalise it, keep a separate theme registry and reference into
it, attach whatever additional information your design produces. If a flat list of
rows genuinely is the best model, use it — but decide that, do not default to it.

We are not scoring you against a schema of ours, and we have not given you one.
How you choose to model a review-to-theme mapping tells us something we cannot
learn any other way, so treat it as part of the work rather than plumbing. Explain
the choice in `NOTES.html`.

## Also emit a flat projection, for the checker

We need something we can check mechanically without writing a parser per
submission. So *in addition* to your own file, write `out/flat.json`:

```json
[
  {
    "review_id": "rev-9e874d7ed04d",
    "strategic_theme": "...",
    "midlevel_theme": "...",
    "specific_theme": "..."
  }
]
```

One row per theme assignment you made. Rules, and there are only three:

- `review_id` is copied unchanged from `data/reviews.json`.
- All three tiers are non-empty, and come from your theme set.
- The same `(review_id, strategic_theme, midlevel_theme, specific_theme)` row
  must not appear twice.

Extra fields are ignored by the checker but harmless if your design carries them.

This file is **derived output for a script**. It is expected to be lossy — if your
real representation holds more than four strings per assignment, that richness
belongs in your own file, and this one is just the projection of it that a checker
can read. Generating it should be a few lines at the end of your pipeline. It is
not a hint about how to model the problem, and a submission whose only output is
this file has skipped the part we are most interested in.

Check it with:

```
python3 score.py --pred out/flat.json
```
