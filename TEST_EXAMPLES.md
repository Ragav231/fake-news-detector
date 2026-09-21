# Veritas — Test Examples

Verified sample inputs for demonstrating the system. Every example below was
run against the live engine; the stated rule fires and the stated verdict is
what the application returns.

**Using the source dropdown:** recognised outlets (Hindustan Times, Reuters,
The Hindu, BBC and the rest) are listed directly. For any source not in the
list — `YourNewsWire`, `Daily Feed`, `Truth Feed`, `Viral Point`, `Metro Desk`,
`Wellness Daily`, `WhatsApp` — choose **"Other — enter the name manually"** and
type it in. Leave the default **"No source provided"** for forwarded messages.

---

## Part 1 — One example per rule

Each example is written to isolate one rule. Note that R01 (source
credibility) fires on almost everything, since every article has some source
status — that is expected and is noted in each case.

---

### R01 · Source credibility (Source)

**Source:** `YourNewsWire`

**Text:**
> A city council meeting was held on Tuesday to discuss the new drainage project, according to the report states published minutes.

**Fires:** R01 at **+18** — the publisher is on the known-unreliable list.
**Verdict:** SUSPICIOUS, 33 %

*Variation worth showing:* run the same text with source `Reuters` → R01
becomes **−8** (mitigating) and the verdict drops to CLEARED. This single
swap demonstrates the mitigating-rule concept better than anything else.

---

### R02 · Suspicious web address (Source)

**Source:** `Daily Feed`

**Text:**
> The full story about the district budget was carried on www.breaking-news-24.xyz according to the published record.

**Fires:** R02 at **+7** — host pattern matches imitation news sites
(`news`+`24` construction, `.xyz` domain).
**Verdict:** CLEARED, 24 % — just under the threshold, which shows a single
weak signal is not treated as proof.

---

### R03 · Sensational language (Language)

**Source:** `Metro Desk`

**Text:**
> In a shocking and explosive development, the minister was slammed after a bombshell report was exposed to the public, according to the statement.

**Fires:** R03 at **+12** (capped) — four instances: bombshell, explosive,
exposed, shocking.
**Verdict:** SUSPICIOUS, 33 %

---

### R04 · Clickbait construction (Language)

**Source:** `Viral Point`

**Text:**
> She opened the old cupboard in her grandmother's house and you won't believe what happened next, according to the neighbours present.

**Fires:** R04 at **+6** — curiosity-gap patterns "you won't believe" and
"what happened next".
**Verdict:** SUSPICIOUS, 29 %

---

### R05 · Excessive capitalisation (Language)

**Source:** `Metro Desk`

**Text:**
> THIS ENTIRE REPORT WAS RELEASED TODAY AND EVERY RESIDENT MUST READ IT CAREFULLY according to the notice.

**Fires:** R05 at **+8** — 71 % of words fully capitalised (≥35 % tier).
**Verdict:** SUSPICIOUS, 25 %

*Contrast case:* "The US and UK agreed on new terms" does **not** fire — two
letter acronyms are excluded so legitimate reporting is not penalised.

---

### R06 · Excessive punctuation (Language)

**Source:** `Metro Desk`

**Text:**
> The water supply was restored today?!?! Residents were informed by the board!! The notice was issued according to the office!!

**Fires:** R06 at **+5** — six exclamation and two question marks, including
repeated runs.
**Verdict:** CLEARED, 20 %

---

### R07 · Unverified claims (Evidence)

**Source:** `Metro Desk`

**Text:**
> Sources say the merger has been finalised. Insiders say the announcement is imminent, and it is believed the board has already agreed.

**Fires:** R07 at **+12** (capped) — three untraceable attributions.
Also fires R08, since nothing here is citable.
**Verdict:** SUSPICIOUS, 47 %

---

### R08 · Supporting evidence — absent (Evidence)

**Source:** `Metro Desk`

**Text:**
> The transport department changed the bus timings for the northern route starting next week and passengers were informed at the terminal.

**Fires:** R08 at **+8** — no citations, data, studies or official statements.
**Verdict:** SUSPICIOUS, 25 %

Note this text is not sensational or false-sounding at all. It scores purely
for being unsupported, which is the point: the system measures *how a claim
is presented*, not whether it happened.

---

### R09 · Named attribution — mitigating (Evidence)

**Source:** `The Hindu`

**Text:**
> Transport Secretary Rajesh Kumar said the revised timetable would take effect on Monday, according to the official statement issued by his office.

**Fires:** R09 at **−5** (credit) and R01 at **−8** (trusted source).
**Verdict:** CLEARED, **0 %**

This is the clearest demonstration that the score can go *down*. A purely
additive system would still have assigned this article penalty points.

---

### R10 · Urgency and virality pressure (Framing)

**Source:** `WhatsApp`

**Text:**
> The bank is closing all accounts that are not updated. Forward this to everyone and share this before it's deleted from the system.

**Fires:** R10 at **+8** — three pressure phrases.
**Verdict:** SUSPICIOUS, 51 %

A realistic forwarded-message scenario, which tends to land well in a demo.

---

### R11 · Conspiratorial framing (Framing)

**Source:** `Truth Feed`

**Text:**
> The mainstream media won't report this because big pharma controls the coverage. Wake up and do your own research before the cover-up continues.

**Fires:** R11 at **+10** (capped) — big pharma, cover-up, do your own
research, mainstream media, wake up. R08 also fires, because "do your own
research" is not counted as a citation.
**Verdict:** SUSPICIOUS, 44 %

---

### R12 · Absolute claims (Framing)

**Source:** `Wellness Daily`

**Text:**
> The herbal mixture is 100% guaranteed and completely safe, with no side effects, and is proven to cure the condition permanently.

**Fires:** R12 at **+9** (capped) — 100 %, completely safe, guaranteed, no
side effects.
**Verdict:** SUSPICIOUS, 42 %

Worth mentioning: the "100 %" here is correctly treated as a promotional
absolute, **not** as statistical evidence. That distinction is enforced in
code and covered by a regression test.

---

## Part 2 — Full articles for the live demo

Use these three in sequence. They show the full range of the scale and all
produce **High** confidence, so nothing looks hedged.

---

### Demo A — Clearly fabricated → FALSIFIED, 100 %

**Source:** `Unknown`

**Text:**
> SHOCKING!! You won't believe what they found!! Sources say a MIRACLE remedy has been BANNED because big pharma controls the mainstream media. It is 100% guaranteed with no side effects and is proven to cure the illness permanently. Wake up and do your own research!! Read the full report at www.health-truth-247.xyz before it is deleted. Share this before they remove it!!

**Result:** FAKE · risk 100 % · confidence High · **10 of 12 rules fired**
(R01, R02, R03, R04, R06, R07, R08, R10, R11, R12)

The findings table fills with ten traceable rows — the strongest visual
moment in the demo.

R08 firing here is the result of two deliberate fixes: the article's link
(`www.health-truth-247.xyz`) is not credited as evidence because R02 flags it
as an imitation domain, and "do your own research" is not credited either,
despite containing the word "research". Both are covered by regression tests
and are good answers if you are asked how the rules interact.

---

### Demo B — Plausible but unsupported → UNDER INVESTIGATION, 40 %

**Source:** `Local Herald`

**Text:**
> The municipal corporation reportedly plans to revise property tax rates from next quarter. Sources say the proposal has been circulated internally, and it is believed the revision could affect several thousand households in the northern zone. No official notification has been issued so far.

**Result:** SUSPICIOUS · risk 40 % · confidence High · 3 rules (R01, R07, R08)

This is the most useful example to discuss. Nothing here is sensational or
obviously false — it reads like ordinary local reporting. It is flagged only
because every claim traces to an unnamed source and nothing is citable. The
verdict is "verify this", not "this is a lie".

---

### Demo C — Well-sourced reporting → CLEARED, 0 %

**Source:** `The Hindu`

**Text:**
> Cases of seasonal influenza declined by 18 percent in the district between June and August, according to data published in the state health bulletin. Health Secretary Meera Nair said the fall followed an expanded vaccination drive that reached 240 primary health centres. Researchers at the state medical college confirmed the trend in a survey released on Tuesday, though they cautioned that reporting gaps in rural areas may affect the figures.

**Result:** REAL · risk 0 % · confidence High · 3 rules, **all mitigating**
(R01 −8, R08 −6, R09 −5)

Note "Health **Secretary** Meera Nair" — this used to be flagged as
sensational language because "secret" matched inside "secretary". Matching is
now word-boundary aware, and two regression tests pin the behaviour. This is
a good bug to mention if you are asked how you tested the system.

---

## Part 3 — Suggested demo order

1. **Demo C** first (clean article, 0 %) — establishes the system is not just
   flagging everything.
2. **Demo A** (100 %) — the contrast, nine rules firing at once.
3. **Demo B** (40 %) — the interesting middle case; explain that the verdict
   is a prompt to verify.
4. **R01 source swap** — same text, `YourNewsWire` vs `Reuters`, showing
   +18 flip to −8.
5. **Rule Book page** (`/knowledge`) — close by showing every rule and the
   full vocabulary, then make the point that a trained model has no
   equivalent view.
6. **`python tests/test_rules.py`** — 38 tests passing, live.

---

## Part 4 — Edge cases, if you are asked

| Input | Result | Why it matters |
|---|---|---|
| `The US and UK signed the treaty.` (source: BBC) | CLEARED | Two-letter acronyms are not treated as shouting |
| `Big news today.` (source: blank) | Confidence **Low** | Too short to judge; the system says so instead of guessing |
| `This cure is 100% guaranteed.` | R08 fires | Promotional "100 %" is not counted as statistical evidence |
| `Cases fell by 20 percent according to the survey.` | R08 **−6** | A genuine reported figure does count |
| A satirical article | May score high | Stated limitation: the system reads presentation, not truth |
| `Read more at www.health-truth-247.xyz` | R02 **and** R08 fire | A suspicious link is not counted as a citation |
| `Wake up and do your own research.` | R11 **and** R08 fire | "research" inside a conspiracy phrase is not evidence |
| `Details at https://www.bbc.co.uk/news/story` | Counts as evidence | A legitimate link still earns credit |
