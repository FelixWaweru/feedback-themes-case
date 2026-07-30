# Technical case: customer feedback themes

This is the take-home case for engineering roles at Compethic.

**Budget about five hours.** We would rather see a modest pipeline you
understand completely and can defend than a large one you generated and did not
read. If you run out of time, ship what works and tell us what you would have
done next.

---

## The task

`data/reviews.json` holds **223 reviews** for a fictional Norwegian bank, "Kvist
Bank", which provides invoice financing and business banking to small companies.

```json
{
  "id": "rev-9e874d7ed04d",
  "rating": 5,
  "title": "Rask og ryddig",
  "feedback_date": "2024-01-15 09:12:04+00:00",
  "content_no": "Rask kredittvurdering og utrolig hyggelige folk å ha med å gjøre.",
  "content_en": "Fast credit assessment and incredibly pleasant people to deal with."
}
```

Both languages are given. You do not need to read Norwegian — work from
`content_en` if you prefer. The reviews are synthetic and have not been cleaned
up for you.

**Build a pipeline that extracts, from each review, the themes it mentions —
at three tiers of specificity: a strategic theme, a midlevel theme, and a
specific theme.**

### What a theme is

A theme is **a subject customers give feedback about** — a label you can attach
to many reviews and then count. It is not a summary of one review, and not a
restatement of how the customer felt. If a label could only ever apply to a
single review in this dataset, it is a description, not a theme.

The three tiers are the same kind of thing at different resolutions, each nested
inside the one above:

- **strategic theme** — the broadest grouping
- **midlevel theme** — narrower, sitting inside a strategic theme
- **specific theme** — the finest, sitting inside a midlevel theme

The nesting works the way `Europe > Norway > Oslo` does: each tier narrows the
one above it, and anything at a lower tier belongs to exactly one parent above.
(That is an illustration of the *relationship* only — it has nothing to do with
this data.)

What the themes actually are, at every tier, is yours to work out from the
reviews. Themes recur: many reviews mention themes that other reviews also
mention, which is what makes them countable.

### The rest is yours

You define the themes, and you choose the JSON structure that represents the
categorisation best — the one that carries the meaning of what you built and that
you would defend as the right model for this problem. Both are design decisions we
assess, and we have deliberately not handed you a schema for either. Read
**`data/flat_projection.md`** before you start: it explains what to aim for, and
the one small derived file we need alongside it so that a script can check your
submission mechanically.

Everything else is yours too: any language, any framework, any model, any number
of LLM calls, any amount of ordinary code.

There is no answer key in this repo and no worked example. We hold our own
annotations for a subset of the reviews and do not publish them.

## How we assess it

Two gates, then judgement.

**Gate 1 — it checks out.** Your flat projection parses, its rows are
well-formed, and your three tiers form a consistent tree. `score.py` tells you
if they don't.

**Gate 2 — cost and speed.** Processing all 223 reviews must finish in **under
25 minutes wall clock** for **under $6.00** of API spend, including whatever you
spent arriving at your theme set. These are floors, not a leaderboard — clear
them and you are through. Report your actual numbers.

**Then judgement.** Everything that clears both gates is read by people. We form
a view on your theme set, on whether the extraction is faithful to what the
reviews say, on the architecture, on the code, and on how well you understand
your own pipeline's failures.

We are not checking whether your themes match ours. We have our own for this
domain and a good set that looks nothing like it is a strong submission.

## Deliverables

A repository or a zip containing:

1. **Your code.**
2. **Your three-tier theme set**, as a standalone readable file with a one-line
   definition for each theme at each tier.
3. **Your categorisation results as JSON**, in the structure you designed — this
   is the one we assess — plus `out/flat.json`, the derived projection for the
   checker. Both are described in `data/flat_projection.md`.
4. **`RUN.md`** — how to run it from a clean checkout. Assume we have API keys
   for the major providers and nothing else. If we cannot run it in five
   minutes, we assess what we can read.
5. **`NOTES.html`** — a single self-contained HTML file, no external assets, and
   about two pages' worth of reading. If a diagram or a rendering of your theme
   set explains something faster than prose, embed it. Covering:

   - **Your theme set** — how you arrived at it and the calls you found hard.
     What you changed along the way, and what you are still unsure about.
   - **Decisions the brief left open** — where you had to choose, what you chose,
     and why.
   - **Architecture** — how the pipeline works and why it is shaped that way,
     including how you chose to represent the output and what that buys you.
     What you tried that did not work is more interesting than a description of
     code we can read.
   - **Numbers** — wall clock for all 223, total input and output tokens, total
     cost in USD, and the model(s) used.
   - **Five outputs your pipeline got wrong, and why** — required. Pick five you
     believe are incorrect, say what the right answer was, and say what in your
     design caused the miss.
   - **What you would do with another week.**

## Self-checking

```
python3 score.py --pred out/flat.json
```

Standard library only, no API keys. It checks your rows are well-formed, checks
your three tiers form a consistent tree, and reports the shape of what you
built. It never compares your names to ours.

A clean report is the starting line, not a good score. Read the output as
measurements, not marks — what the numbers mean for your design, and what to do
about them, is your call to make and to defend.

We also compare your output against our own annotations for a subset of the
reviews, in ways that do not depend on your names matching ours.

## Ground rules

- **Use AI coding tools if you want to.** We do, daily. Say in `NOTES.html` which
  ones and roughly how. What we assess is the result and whether you can defend
  it.
- **Don't hand-write the answers.** Output you produced by reading all 223
  yourself, or a lookup table keyed by review id, defeats the exercise — we are
  hiring for the pipeline. Reading the data yourself to *design your theme set*
  is not only allowed, it is the job.
- **Ask if something blocks you.** But much of what looks underspecified is
  deliberately left to you: where we have not told you what to do, deciding is
  part of the task, and we would rather read your reasoning in `NOTES.html` than
  hand you ours.

## After you submit

We read your theme set and your `NOTES.html`, run your pipeline, then spend about
30 minutes with you on your design and a handful of specific reviews. That
conversation matters at least as much as the submission.
