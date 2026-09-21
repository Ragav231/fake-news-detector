"""
knowledge_base.py
=================
The KNOWLEDGE BASE component of the system.

This module holds *only data* -- the facts and linguistic patterns the
system reasons over. It contains no logic. Keeping the knowledge base
separate from the inference engine means the system can be extended by
domain experts (adding sources, phrases, patterns) without touching a
single line of reasoning code.

This mirrors the classic expert-system architecture:
    KNOWLEDGE BASE  (this file)  -> what the system knows
    INFERENCE ENGINE (rules_engine.py) -> how the system reasons
"""

# --------------------------------------------------------------------------
# 1. SOURCE KNOWLEDGE
# --------------------------------------------------------------------------

#: Outlets with established editorial standards and correction policies.
TRUSTED_SOURCES = {
    "bbc", "bbc news", "reuters", "associated press", "ap", "ap news",
    "the hindu", "ndtv", "times of india", "the guardian", "cnn",
    "al jazeera", "pib", "press information bureau", "who",
    "world health organization", "nature", "science", "indian express",
    "the indian express", "hindustan times", "the new york times",
    "the washington post", "npr", "bloomberg", "the economist",
    "financial times", "doordarshan", "ani", "pti",
}

#: Domains/outlets widely documented as publishing fabricated content.
#: (Illustrative list for an academic project -- extend as needed.)
KNOWN_UNRELIABLE_SOURCES = {
    "yournewswire", "newspunch", "worldnewsdailyreport", "empirenews",
    "nationalreport", "theonion", "thepeoplesvoice", "infowars",
    "beforeitsnews", "clickhole", "realnewsrightnow",
}

#: Values a user may type that mean "no source was provided".
UNKNOWN_SOURCE_LABELS = {
    "", "unknown", "anonymous", "not specified", "n/a", "na",
    "none", "-", "unspecified", "forwarded", "whatsapp", "social media",
}

# --------------------------------------------------------------------------
# 2. LINGUISTIC KNOWLEDGE
# --------------------------------------------------------------------------

#: Emotionally loaded / tabloid vocabulary.
SENSATIONAL_WORDS = {
    "shocking", "shocked", "you won't believe", "miracle", "secret",
    "exposed", "destroyed", "unbelievable", "outrage", "slams",
    "instantly", "banned", "conspiracy", "they don't want you to know",
    "goes viral", "panic", "chaos", "explosive", "bombshell", "insane",
    "horrifying", "terrifying", "jaw-dropping", "mind-blowing",
    "disaster", "catastrophe", "scandal", "stunned", "furious",
}

#: Vague attribution -- a claim with no traceable origin.
CLAIM_INDICATOR_PHRASES = {
    "sources say", "sources said", "experts claim", "it is believed",
    "some people say", "many believe", "rumors suggest", "rumours suggest",
    "insiders say", "according to unnamed", "anonymous source",
    "unconfirmed reports", "word on the street", "people are saying",
    "allegedly", "it is rumored", "it is rumoured", "a friend of mine",
}

#: Markers that the text is grounded in checkable evidence.
#: Note: bare "%" is deliberately excluded -- it matches promotional
#: absolutes such as "100% guaranteed", which are the opposite of
#: evidence. Genuine statistics are detected by STATISTIC_PATTERN below.
EVIDENCE_MARKERS = {
    "according to", "study shows", "study found", "data shows",
    "reported by", "published in", "official statement", "confirmed by",
    "http://", "https://", "www.", "research", "researchers",
    "statistics", "survey", "press release",
    "court documents", "the report states", "spokesperson said",
}

#: A real reported figure, e.g. "20 percent", "3.5%". Round promotional
#: numbers (100%, 0%) are excluded by the rule that uses this pattern.
STATISTIC_PATTERN = r"\b(\d{1,3}(?:\.\d+)?)\s?(?:%|percent)\b"

#: Figures that read as marketing rather than measurement.
NON_EVIDENTIAL_FIGURES = {"100", "0"}

#: Language pushing the reader to act or spread the message immediately.
URGENCY_PHRASES = {
    "share before", "share this before", "forward this", "forward to everyone",
    "before it's deleted", "before its deleted", "before they delete",
    "spread the word", "act now", "urgent", "must share", "share immediately",
    "delete soon", "going to be removed", "don't ignore", "read before",
    "send to 10", "forward to all",
}

#: Framing that positions the reader against institutions.
CONSPIRACY_PHRASES = {
    "mainstream media", "wake up", "they don't want you", "cover up",
    "cover-up", "the truth they hide", "hidden agenda", "deep state",
    "big pharma", "what they aren't telling you", "what they arent telling you",
    "censored", "silenced", "puppet", "controlled by", "sheeple",
    "do your own research", "open your eyes",
}

#: Overgeneralised / absolute statements that evidence rarely supports.
ABSOLUTE_CLAIM_PHRASES = {
    "100%", "completely safe", "completely cured", "guaranteed",
    "always works", "never fails", "everyone knows", "nobody knows",
    "all doctors", "every single", "proven to cure", "totally eliminates",
    "the only way", "no side effects", "instant cure", "permanent cure",
}

#: Clickbait headline constructions (checked as substrings).
CLICKBAIT_PHRASES = {
    "you won't believe", "you wont believe", "this one trick",
    "doctors hate", "what happened next", "will shock you",
    "number 7 will", "the reason why will", "find out why",
    "this is why", "here's what happened", "gone wrong",
}

# --------------------------------------------------------------------------
# 3. SCORING CONFIGURATION
# --------------------------------------------------------------------------

#: Raw score treated as "maximum practical suspicion" when normalising to
#: a 0-100 risk percentage. Set below the theoretical maximum so that a
#: clearly fabricated article reliably reaches 100.
NORMALISATION_CEILING = 55

#: Risk-percentage boundaries for the final verdict.
THRESHOLD_SUSPICIOUS = 25   # >= this  -> SUSPICIOUS
THRESHOLD_FAKE = 60         # >= this  -> FAKE

#: Verdict presentation metadata, used by the web interface.
VERDICT_META = {
    "REAL": {
        "stamp": "CLEARED",
        "headline": "No significant red flags found",
    },
    "SUSPICIOUS": {
        "stamp": "UNDER INVESTIGATION",
        "headline": "Several indicators need verification",
    },
    "FAKE": {
        "stamp": "FALSIFIED",
        "headline": "Strong indicators of unreliable content",
    },
}
