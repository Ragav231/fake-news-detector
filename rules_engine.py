"""
rules_engine.py
===============
The INFERENCE ENGINE component of the system.

Design notes
------------
Rules are *registered*, not hard-coded into a long if/else block. Each rule
is a small, independently testable function that receives a prepared
``Analysis`` object and returns either ``None`` (rule did not fire) or a
``Finding`` describing what it saw and how much suspicion it contributes.

Adding a new rule is therefore a three-line change: write a function,
decorate it with ``@rule(...)``, done. The scoring, ordering, reporting and
web interface all pick it up automatically.

Pipeline
--------
    NEWS INPUT
      -> TEXT PREPROCESSING      (Analysis.build)
      -> FEATURE & PATTERN ANALYSIS (Analysis fields)
      -> KNOWLEDGE BASE          (knowledge_base.py)
      -> INFERENCE ENGINE        (registered rules below)
      -> SUSPICION SCORING       (normalise_score)
      -> CLASSIFICATION          (classify)
"""

from __future__ import annotations

import random
import re
import string
from dataclasses import dataclass, field
from datetime import datetime
from typing import Callable, List, Optional

import knowledge_base as kb

# ==========================================================================
# DATA STRUCTURES
# ==========================================================================


@dataclass
class Finding:
    """A single piece of evidence produced by one rule."""
    rule_id: str
    name: str
    category: str
    points: int
    detail: str
    #: "aggravating" raises suspicion, "mitigating" lowers it.
    nature: str = "aggravating"

    @property
    def is_mitigating(self) -> bool:
        return self.points < 0


@dataclass
class Analysis:
    """
    Preprocessed view of the submitted article.

    Building these features once, up front, keeps every rule cheap and
    means the preprocessing logic lives in exactly one place.
    """
    raw_text: str
    raw_source: str
    text: str = ""              # lowercased, whitespace-normalised
    source: str = ""            # lowercased, trimmed
    words: List[str] = field(default_factory=list)
    word_count: int = 0
    caps_words: List[str] = field(default_factory=list)
    exclamation_count: int = 0
    question_count: int = 0
    urls: List[str] = field(default_factory=list)

    @classmethod
    def build(cls, news_text: str, source: str) -> "Analysis":
        """TEXT PREPROCESSING + FEATURE EXTRACTION."""
        normalised = re.sub(r"\s+", " ", news_text.strip())
        lowered = normalised.lower()
        raw_words = normalised.split()

        # A "shouting" word: 3+ letters, all uppercase. Ignores acronyms
        # of 2 letters (US, UK) which are legitimate in news writing.
        caps = [
            w for w in raw_words
            if len(re.sub(r"[^A-Za-z]", "", w)) >= 3 and w.isupper()
        ]

        return cls(
            raw_text=news_text,
            raw_source=source,
            text=lowered,
            source=re.sub(r"\s+", " ", source.strip().lower()),
            words=raw_words,
            word_count=len(raw_words),
            caps_words=caps,
            exclamation_count=normalised.count("!"),
            question_count=normalised.count("?"),
            urls=re.findall(r"https?://\S+|www\.\S+", lowered),
        )

    def matches(self, phrases) -> List[str]:
        """
        Return every knowledge-base phrase present in the article text.

        Matching respects word boundaries, so "secret" does not match
        inside "secretary" and "ap" does not match inside "apparently".
        A trailing plural "s" is tolerated ("survey" matches "surveys").

        Phrases ending in punctuation ("www.", "100%") skip the trailing
        boundary check, since the characters that follow them are
        ordinary word characters.
        """
        return sorted(p for p, _ in self._spans(phrases))

    def _spans(self, phrases):
        """Every (phrase, span) pair found in the text."""
        out = []
        for phrase in phrases:
            pattern = r"(?<!\w)" + re.escape(phrase)
            if phrase[-1].isalnum():
                pattern += r"s?(?!\w)"
            for m in re.finditer(pattern, self.text):
                out.append((phrase, m.span()))
        return out

    def matches_outside(self, phrases, excluded_phrases) -> List[str]:
        """
        Matches from ``phrases`` that do not sit inside a match of
        ``excluded_phrases``.

        Needed because short markers can be swallowed by longer phrases
        with the opposite meaning -- "do your own research" contains the
        evidence marker "research", but is conspiratorial framing, not a
        citation.
        """
        blocked = [span for _, span in self._spans(excluded_phrases)]
        found = set()
        for phrase, (start, end) in self._spans(phrases):
            if not any(b0 <= start and end <= b1 for b0, b1 in blocked):
                found.add(phrase)
        return sorted(found)


# ==========================================================================
# RULE REGISTRY
# ==========================================================================

RULES: List[dict] = []


def rule(rule_id: str, name: str, category: str, description: str):
    """Decorator that registers a rule function with the inference engine."""
    def wrapper(func: Callable[[Analysis], Optional[Finding]]):
        RULES.append({
            "id": rule_id,
            "name": name,
            "category": category,
            "description": description,
            "func": func,
        })
        return func
    return wrapper


def _finding(meta_id, name, category, points, detail, nature="aggravating"):
    return Finding(rule_id=meta_id, name=name, category=category,
                   points=points, detail=detail, nature=nature)


# --------------------------------------------------------------------------
# CATEGORY: SOURCE
# --------------------------------------------------------------------------

@rule("R01", "Source credibility", "Source",
      "Checks the named source against known-reliable and known-unreliable lists.")
def r_source_credibility(a: Analysis) -> Optional[Finding]:
    # IF source is on the unreliable list THEN suspicion += 18
    if any(bad in a.source for bad in kb.KNOWN_UNRELIABLE_SOURCES):
        return _finding("R01", "Source credibility", "Source", 18,
                        f'"{a.raw_source}" appears on the known-unreliable '
                        f"publisher list.")

    # IF no source given THEN suspicion += 12
    if a.source in kb.UNKNOWN_SOURCE_LABELS:
        return _finding("R01", "Source credibility", "Source", 12,
                        "No identifiable publisher was provided, so the claim "
                        "cannot be traced to an accountable outlet.")

    # IF source is trusted THEN suspicion -= 8 (mitigating)
    if a.source in kb.TRUSTED_SOURCES:
        return _finding("R01", "Source credibility", "Source", -8,
                        f'"{a.raw_source}" is an outlet with published '
                        f"editorial standards and a corrections policy.",
                        nature="mitigating")

    # Unrecognised but named source: mild suspicion.
    return _finding("R01", "Source credibility", "Source", 6,
                    f'"{a.raw_source}" is not a recognised outlet in the '
                    f"knowledge base; it could not be verified either way.")


def suspicious_hosts(a: Analysis) -> List[str]:
    """
    Hosts matching imitation-news patterns.

    Shared by R02 (which penalises them) and R08 (which must not count
    them as supporting evidence -- a scam link is not a citation).
    """
    found = []
    for url in a.urls:
        host = re.sub(r"^https?://", "", url).split("/")[0]
        # Imitation patterns: digits in brand position, long hyphen chains,
        # or news-like words stacked onto a free domain.
        if (host.count("-") >= 2
                or re.search(r"\d{2,}", host)
                or re.search(r"(news|daily|times|post)[-.]?(24|7|365|live|now)", host)
                or host.endswith((".xyz", ".top", ".click", ".info"))):
            found.append(host)
    return found


@rule("R02", "Suspicious web address", "Source",
      "Flags URLs that imitate news brands or use throwaway domain patterns.")
def r_suspicious_url(a: Analysis) -> Optional[Finding]:
    suspicious = suspicious_hosts(a)
    if suspicious:
        return _finding("R02", "Suspicious web address", "Source", 7,
                        "Link host patterns typical of imitation news sites: "
                        + ", ".join(sorted(set(suspicious))) + ".")
    return None


# --------------------------------------------------------------------------
# CATEGORY: LANGUAGE
# --------------------------------------------------------------------------

@rule("R03", "Sensational language", "Language",
      "Detects emotionally loaded tabloid vocabulary.")
def r_sensational(a: Analysis) -> Optional[Finding]:
    hits = a.matches(kb.SENSATIONAL_WORDS)
    if not hits:
        return None
    points = min(4 * len(hits), 12)
    return _finding("R03", "Sensational language", "Language", points,
                    f"Emotionally loaded wording ({len(hits)} instance"
                    f"{'s' if len(hits) > 1 else ''}): {', '.join(hits)}.")


@rule("R04", "Clickbait construction", "Language",
      "Detects headline formulas engineered for curiosity clicks.")
def r_clickbait(a: Analysis) -> Optional[Finding]:
    hits = a.matches(kb.CLICKBAIT_PHRASES)
    if not hits:
        return None
    return _finding("R04", "Clickbait construction", "Language", 6,
                    f"Curiosity-gap headline patterns found: "
                    f"{', '.join(hits)}.")


@rule("R05", "Excessive capitalisation", "Language",
      "Flags shouting -- a high proportion of fully capitalised words.")
def r_shouting(a: Analysis) -> Optional[Finding]:
    if a.word_count < 5 or len(a.caps_words) < 2:
        return None
    ratio = len(a.caps_words) / a.word_count
    if ratio < 0.15:
        return None
    points = 8 if ratio >= 0.35 else 5
    pct = round(ratio * 100)
    return _finding("R05", "Excessive capitalisation", "Language", points,
                    f"{pct}% of words are fully capitalised "
                    f"({', '.join(a.caps_words[:4])}"
                    f"{'...' if len(a.caps_words) > 4 else ''}), a common "
                    f"attention-grabbing device.")


@rule("R06", "Excessive punctuation", "Language",
      "Flags repeated exclamation or question marks used for emphasis.")
def r_punctuation(a: Analysis) -> Optional[Finding]:
    repeated = re.search(r"([!?])\1{1,}", a.raw_text)
    total = a.exclamation_count + a.question_count
    if not repeated and total < 3:
        return None
    points = 5 if repeated else 3
    return _finding("R06", "Excessive punctuation", "Language", points,
                    f"{a.exclamation_count} exclamation and "
                    f"{a.question_count} question marks used"
                    f"{', including repeated runs' if repeated else ''}. "
                    f"Standard reporting rarely needs them.")


# --------------------------------------------------------------------------
# CATEGORY: EVIDENCE
# --------------------------------------------------------------------------

@rule("R07", "Unverified claims", "Evidence",
      "Detects assertions attributed to vague, untraceable sources.")
def r_unverified(a: Analysis) -> Optional[Finding]:
    hits = a.matches(kb.CLAIM_INDICATOR_PHRASES)
    if not hits:
        return None
    points = min(4 * len(hits), 12)
    return _finding("R07", "Unverified claims", "Evidence", points,
                    f"Claims attributed to untraceable sources: "
                    f"{', '.join(hits)}.")


@rule("R08", "Supporting evidence", "Evidence",
      "Checks whether the article cites data, studies, links or named officials.")
def r_evidence(a: Analysis) -> Optional[Finding]:
    # Evidence markers swallowed by conspiratorial phrasing do not count:
    # "do your own research" is not a citation.
    hits = a.matches_outside(kb.EVIDENCE_MARKERS, kb.CONSPIRACY_PHRASES)

    # A link only counts as evidence if it is not itself suspect. Without
    # this, a fabricated article citing an imitation news domain would be
    # credited for "linking to a source" while R02 flags the same link.
    if a.urls and len(suspicious_hosts(a)) == len(a.urls):
        hits = [h for h in hits if h not in ("www.", "http://", "https://")]

    # A genuine reported statistic counts as evidence, but a round
    # promotional figure ("100% guaranteed") does not.
    for figure in re.findall(kb.STATISTIC_PATTERN, a.text):
        if figure.rstrip(".0") not in kb.NON_EVIDENTIAL_FIGURES and figure not in kb.NON_EVIDENTIAL_FIGURES:
            hits.append(f"a reported figure ({figure}%)")
            break

    # IF no evidence markers at all THEN suspicion += 8
    if not hits:
        return _finding("R08", "Supporting evidence", "Evidence", 8,
                        "No citations, data, studies or official statements "
                        "were found to support the claims.")

    # IF well-evidenced THEN suspicion -= 6 (mitigating)
    if len(hits) >= 3:
        return _finding("R08", "Supporting evidence", "Evidence", -6,
                        f"Claims are backed by multiple verifiable references: "
                        f"{', '.join(hits[:4])}.",
                        nature="mitigating")
    return None


@rule("R09", "Named attribution", "Evidence",
      "Rewards direct quotes attributed to a specific named person.")
def r_named_attribution(a: Analysis) -> Optional[Finding]:
    # A quotation followed/preceded by "<Capitalised Name> said" is a strong
    # signal of accountable reporting.
    pattern = re.compile(
        r'["\u201c][^"\u201d]{10,}["\u201d]'          # a real quotation
        r'[^.]{0,40}?\b[A-Z][a-z]+\s[A-Z][a-z]+\b'    # near a proper name
        r'|'
        r'\b[A-Z][a-z]+\s[A-Z][a-z]+\b[^.]{0,30}?\b(said|stated|told|announced)\b'
    )
    if pattern.search(a.raw_text):
        return _finding("R09", "Named attribution", "Evidence", -5,
                        "Statements are attributed to a specific named person, "
                        "which makes the reporting checkable.",
                        nature="mitigating")
    return None


# --------------------------------------------------------------------------
# CATEGORY: FRAMING
# --------------------------------------------------------------------------

@rule("R10", "Urgency and virality pressure", "Framing",
      "Detects instructions to share immediately -- a hallmark of chain messages.")
def r_urgency(a: Analysis) -> Optional[Finding]:
    hits = a.matches(kb.URGENCY_PHRASES)
    if not hits:
        return None
    return _finding("R10", "Urgency and virality pressure", "Framing", 8,
                    f"Pressure to spread the message before verifying it: "
                    f"{', '.join(hits)}.")


@rule("R11", "Conspiratorial framing", "Framing",
      "Detects framing that positions the reader against institutions.")
def r_conspiracy(a: Analysis) -> Optional[Finding]:
    hits = a.matches(kb.CONSPIRACY_PHRASES)
    if not hits:
        return None
    points = min(4 * len(hits), 10)
    return _finding("R11", "Conspiratorial framing", "Framing", points,
                    f"Anti-institutional framing used to pre-empt fact-checking: "
                    f"{', '.join(hits)}.")


@rule("R12", "Absolute claims", "Framing",
      "Detects overgeneralised guarantees that evidence rarely supports.")
def r_absolutes(a: Analysis) -> Optional[Finding]:
    hits = a.matches(kb.ABSOLUTE_CLAIM_PHRASES)
    if not hits:
        return None
    points = min(3 * len(hits), 9)
    return _finding("R12", "Absolute claims", "Framing", points,
                    f"Absolute or guaranteed outcomes asserted without "
                    f"qualification: {', '.join(hits)}.")


# ==========================================================================
# SCORING & CLASSIFICATION
# ==========================================================================

def normalise_score(raw_score: int) -> int:
    """Convert a raw weighted score into a 0-100 risk percentage."""
    if raw_score <= 0:
        return 0
    pct = (raw_score / kb.NORMALISATION_CEILING) * 100
    return int(min(round(pct), 100))


def classify(risk: int) -> str:
    """CLASSIFICATION step -- map risk percentage to a verdict."""
    if risk >= kb.THRESHOLD_FAKE:
        return "FAKE"
    if risk >= kb.THRESHOLD_SUSPICIOUS:
        return "SUSPICIOUS"
    return "REAL"


def assess_confidence(a: Analysis, findings: List[Finding]) -> str:
    """
    How much weight the verdict deserves.

    Very short submissions give the rules little to work with, so the
    system says so rather than projecting false certainty.
    """
    if a.word_count < 12:
        return "Low"
    if a.word_count < 40 or len(findings) < 2:
        return "Moderate"
    return "High"


def generate_case_id() -> str:
    """Unique reference number for the report."""
    stamp = datetime.now().strftime("%Y%m%d-%H%M")
    tail = "".join(random.choices(string.digits, k=3))
    return f"CF-{stamp}-{tail}"


def generate_summary(verdict: str, findings: List[Finding]) -> str:
    """Plain-language explanation of the verdict, built from what fired."""
    aggravating = [f for f in findings if f.points > 0]
    mitigating = [f for f in findings if f.points < 0]
    names = [f.name.lower() for f in aggravating]

    if verdict == "FAKE":
        if len(names) >= 3:
            lead = (f"Several independent checks failed at once — "
                    f"{', '.join(names[:-1])} and {names[-1]}.")
        elif names:
            lead = f"The decisive issue is {names[0]}."
        else:
            lead = "The overall pattern points to fabricated content."
        return (f"{lead} Taken together these indicators are strong enough to "
                f"treat the article as unreliable. Do not share it until a "
                f"recognised outlet reports the same facts independently.")

    if verdict == "SUSPICIOUS":
        if names:
            lead = f"Some checks did not pass — {', '.join(names)}."
        else:
            lead = "A few weaker indicators were triggered."
        tail = ""
        if mitigating:
            tail = (f" On the other side, {mitigating[0].name.lower()} counts "
                    f"in the article's favour.")
        return (f"{lead}{tail} That is not enough to call it either way. "
                f"Verify the central claim against a second source before "
                f"relying on it.")

    if mitigating:
        strengths = ", ".join(f.name.lower() for f in mitigating)
        return (f"Nothing significant was flagged, and the article is helped by "
                f"{strengths}. It shows the ordinary markers of accountable "
                f"reporting. Independent verification is still good practice "
                f"for any single article.")
    return ("No rules were triggered. The article avoids the linguistic and "
            "sourcing patterns associated with misinformation, though a clean "
            "result reflects the absence of red flags rather than proof of "
            "accuracy.")


# ==========================================================================
# PUBLIC ENTRY POINT
# ==========================================================================

def evaluate(news_text: str, source: str = "") -> dict:
    """
    Run the full pipeline and return a complete, explainable report.

    Every number in the result can be traced back to a named rule, which
    is the entire point of a rule-based approach over a trained model.
    """
    analysis = Analysis.build(news_text, source)

    findings: List[Finding] = []
    for entry in RULES:
        outcome = entry["func"](analysis)
        if outcome is not None:
            findings.append(outcome)

    # Strongest evidence first; mitigating factors last.
    findings.sort(key=lambda f: -f.points)

    raw_score = sum(f.points for f in findings)
    risk = normalise_score(raw_score)
    verdict = classify(risk)

    # Category breakdown, for the report's summary panel.
    categories: dict = {}
    for f in findings:
        categories.setdefault(f.category, 0)
        categories[f.category] += f.points

    return {
        "case_id": generate_case_id(),
        "timestamp": datetime.now().strftime("%d %b %Y, %I:%M %p"),
        "verdict": verdict,
        "stamp": kb.VERDICT_META[verdict]["stamp"],
        "headline": kb.VERDICT_META[verdict]["headline"],
        "risk": risk,
        "raw_score": raw_score,
        "confidence": assess_confidence(analysis, findings),
        "word_count": analysis.word_count,
        "rules_checked": len(RULES),
        "rules_fired": len(findings),
        "findings": [f.__dict__ | {"is_mitigating": f.points < 0} for f in findings],
        "categories": categories,
        "summary": generate_summary(verdict, findings),
    }
