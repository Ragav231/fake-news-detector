# Veritas — AI-Driven Fake News Detection Using Rule-Based Reasoning

An explainable expert system that examines news articles for indicators of
misinformation. It uses a **knowledge base** of documented patterns and an
**inference engine** of 12 weighted rules — no machine learning, no training
data, and no black box. Every number in every report traces back to a named
rule the user can read.

---

## Why rule-based

| | Machine learning approach | This system |
|---|---|---|
| Training data | Large labelled corpus required | None |
| Compute | GPU training, heavy inference | Runs on any laptop |
| Explainability | Weights are opaque | Every point traced to a named rule |
| Updating | Retrain the model | Edit a list in `knowledge_base.py` |
| Auditing | Not practical | Full rule book exposed at `/knowledge` |

---

## Architecture

```
NEWS INPUT
    ↓
TEXT PREPROCESSING          Analysis.build()  — normalise, tokenise, measure
    ↓
FEATURE & PATTERN ANALYSIS  caps ratio, punctuation, URLs, word count
    ↓
KNOWLEDGE BASE              knowledge_base.py — vocabulary & source lists
    ↓
INFERENCE ENGINE            rules_engine.py   — 12 registered rules
    ↓
SUSPICION SCORING           weighted sum → normalised 0–100 risk score
    ↓
CLASSIFICATION              REAL · SUSPICIOUS · FAKE  (+ written reasoning)
```

The knowledge base and the inference engine are deliberately in **separate
modules**. Domain knowledge can be extended without touching reasoning code —
the defining property of an expert system.

---

## The rule set

| ID | Rule | Category | Effect |
|----|------|----------|--------|
| R01 | Source credibility | Source | +18 unreliable · +12 unknown · +6 unrecognised · **−8 trusted** |
| R02 | Suspicious web address | Source | +7 |
| R03 | Sensational language | Language | +4 each, max +12 |
| R04 | Clickbait construction | Language | +6 |
| R05 | Excessive capitalisation | Language | +5 / +8 by ratio |
| R06 | Excessive punctuation | Language | +3 / +5 |
| R07 | Unverified claims | Evidence | +4 each, max +12 |
| R08 | Supporting evidence | Evidence | +8 if absent · **−6 if well-cited** |
| R09 | Named attribution | Evidence | **−5** |
| R10 | Urgency and virality pressure | Framing | +8 |
| R11 | Conspiratorial framing | Framing | +4 each, max +10 |
| R12 | Absolute claims | Framing | +3 each, max +9 |

**Mitigating rules (R01, R08, R09) subtract points.** This is what keeps the
system fair: a well-sourced article with named quotes and real citations can
score zero, rather than merely accumulating fewer penalties.

### Scoring

The weighted total is divided by a practical ceiling of 55 points and capped
at 100 to give a risk percentage:

- **0–24 %** → CLEARED (real)
- **25–59 %** → UNDER INVESTIGATION (suspicious)
- **60–100 %** → FALSIFIED (fake)

Each report also states a **confidence** level, since very short submissions
give the rules little to work with.

---

## Project structure

```
fake_news_detector/
├── app.py                 Flask routes, JSON API, error handling
├── knowledge_base.py      Domain data only — no logic
├── rules_engine.py        Inference engine, rule registry, scoring
├── requirements.txt
├── templates/
│   ├── base.html          Shared layout and navigation
│   ├── index.html         Case intake form
│   ├── report.html        Examination report
│   ├── knowledge.html     Browsable rule book
│   └── error.html         404 / 500
├── static/
│   └── style.css        Dark theme (prints as a light document)
└── tests/
    └── test_rules.py      38 unit tests
```

---

## Running it

```bash
pip install -r requirements.txt
python app.py
```

Open <http://localhost:5000>.

### Running the tests

```bash
python tests/test_rules.py          # or: python -m pytest tests/ -v
```

### JSON API

```bash
curl -X POST http://localhost:5000/api/analyze \
     -H "Content-Type: application/json" \
     -d '{"text": "SHOCKING claim!! Sources say...", "source": "Unknown"}'
```

Returns the full report — verdict, risk score, confidence and every finding.

---

## Pages

| Route | Purpose |
|-------|---------|
| `/` | Case intake form |
| `/analyze` | Runs the engine, redirects to the report (POST-redirect-GET) |
| `/report` | The examination report with findings ledger |
| `/knowledge` | Every active rule and the full vocabulary behind it |
| `/api/analyze` | JSON endpoint |

---

## Adding a new rule

Rules are registered by decorator, so no other file needs editing:

```python
@rule("R13", "Missing dateline", "Evidence",
      "Flags articles with no date or time reference.")
def r_dateline(a: Analysis):
    if re.search(r"\b(monday|tuesday|january|\d{4})\b", a.text):
        return None
    return _finding("R13", "Missing dateline", "Evidence", 4,
                    "No date reference found, so the claim cannot be "
                    "placed in time.")
```

Scoring, the report ledger and the public rule book all pick it up
automatically.

---

## Interface notes

The source field is a **dropdown** listing every recognised outlet, plus a
"No source provided" default for forwarded messages and an "Other" option that
reveals a text field for unrecognised or known-unreliable publishers. The
theme is dark; the report's print stylesheet converts it to a light document
so printed case files stay readable.

---

## Rule interactions worth knowing

Three rules deliberately coordinate rather than judging in isolation:

- A **suspicious link** (R02) is not counted as supporting evidence by R08.
  Without this, a fabricated article citing an imitation domain would be
  penalised and credited for the same link.
- **"do your own research"** is conspiratorial framing (R11), not a citation,
  even though it contains the evidence marker "research". Matching is
  span-aware so a short marker swallowed by a longer opposing phrase does
  not count.
- Phrase matching respects **word boundaries**, so "secret" does not fire
  inside "Secretary". Plurals are still matched.

Each of these is pinned by regression tests.

---

## Limitations

This is a transparent heuristic system, not a fact-checker. It assesses *how a
claim is presented*, not whether the underlying event occurred. Satire and
opinion writing may score high; a carefully written falsehood from a trusted
outlet will score low. The verdict is a prompt to verify, not a substitute
for verification.

---

## Future scope

- Expand the knowledge base with regional and multilingual vocabulary
- Integrate external fact-checking APIs for claim-level verification
- Add a dateline/temporal-consistency rule
- Weight tuning against a labelled evaluation set
- Hybrid approach: rules for explanation, a model for ranking
