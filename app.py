"""
app.py
======
Web interface for the rule-based fake news detection system.

Routes
------
GET  /              Case intake form
POST /analyze       Runs the inference engine, redirects to the report
GET  /report        Renders the generated case report
GET  /knowledge     Browsable view of the knowledge base and active rules
POST /api/analyze   JSON endpoint (for scripts, tests, or a future frontend)
"""

import os

from flask import (Flask, jsonify, redirect, render_template, request,
                   session, url_for)

import knowledge_base as kb
from rules_engine import RULES, evaluate

app = Flask(__name__)

# In a real deployment this comes from the environment. The fallback keeps
# the project runnable out of the box for demonstration purposes.
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-change-in-production")

MAX_INPUT_CHARS = 20000


# --------------------------------------------------------------------------
# Web interface
# --------------------------------------------------------------------------

@app.route("/")
def index():
    """Case intake form."""
    return render_template(
        "index.html",
        trusted_sources=sorted(kb.TRUSTED_SOURCES),
        rule_count=len(RULES),
    )


@app.route("/analyze", methods=["POST"])
def analyze():
    """Run the engine, store the report, then redirect to its own page."""
    news_text = request.form.get("news_text", "").strip()
    source = request.form.get("source", "").strip()

    # The dropdown's "Other" option defers to a free-text field, so an
    # unrecognised or known-unreliable publisher can still be examined.
    if source == "__other__":
        source = request.form.get("source_other", "").strip()

    if not news_text:
        return redirect(url_for("index", error="empty"))

    news_text = news_text[:MAX_INPUT_CHARS]
    report = evaluate(news_text, source)

    session["report"] = report
    session["submitted"] = {
        "text": news_text,
        "source": source or "Not provided",
    }
    # Redirect after POST so the report has its own URL and a refresh
    # does not resubmit the form.
    return redirect(url_for("report"))


@app.route("/report")
def report():
    """Render the case report produced by the most recent analysis."""
    data = session.get("report")
    submitted = session.get("submitted")
    if not data or not submitted:
        return redirect(url_for("index"))

    return render_template(
        "report.html",
        r=data,
        submitted=submitted,
        threshold_suspicious=kb.THRESHOLD_SUSPICIOUS,
        threshold_fake=kb.THRESHOLD_FAKE,
    )


@app.route("/knowledge")
def knowledge():
    """
    Transparency page: shows every active rule and the knowledge base
    behind it. This is what makes the system auditable -- a trained
    model has no equivalent view.
    """
    grouped: dict = {}
    for entry in RULES:
        grouped.setdefault(entry["category"], []).append(entry)

    vocab = [
        ("Trusted sources", sorted(kb.TRUSTED_SOURCES)),
        ("Known unreliable publishers", sorted(kb.KNOWN_UNRELIABLE_SOURCES)),
        ("Sensational vocabulary", sorted(kb.SENSATIONAL_WORDS)),
        ("Vague attribution phrases", sorted(kb.CLAIM_INDICATOR_PHRASES)),
        ("Evidence markers", sorted(kb.EVIDENCE_MARKERS)),
        ("Urgency and virality phrases", sorted(kb.URGENCY_PHRASES)),
        ("Conspiratorial framing", sorted(kb.CONSPIRACY_PHRASES)),
        ("Absolute claim phrases", sorted(kb.ABSOLUTE_CLAIM_PHRASES)),
        ("Clickbait constructions", sorted(kb.CLICKBAIT_PHRASES)),
    ]

    return render_template(
        "knowledge.html",
        grouped=grouped,
        vocab=vocab,
        rule_count=len(RULES),
        threshold_suspicious=kb.THRESHOLD_SUSPICIOUS,
        threshold_fake=kb.THRESHOLD_FAKE,
        ceiling=kb.NORMALISATION_CEILING,
    )


# --------------------------------------------------------------------------
# JSON API
# --------------------------------------------------------------------------

@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    """
    Machine-readable endpoint.

        curl -X POST http://localhost:5000/api/analyze \
             -H "Content-Type: application/json" \
             -d '{"text": "SHOCKING claim!!", "source": "Unknown"}'
    """
    payload = request.get_json(silent=True) or {}
    text = (payload.get("text") or "").strip()
    source = (payload.get("source") or "").strip()

    if not text:
        return jsonify({"error": "Field 'text' is required."}), 400

    return jsonify(evaluate(text[:MAX_INPUT_CHARS], source))


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

@app.errorhandler(404)
def not_found(_):
    return render_template("error.html",
                           code="404",
                           message="That page isn't in the archive."), 404


@app.errorhandler(500)
def server_error(_):
    return render_template("error.html",
                           code="500",
                           message="The analysis could not be completed."), 500


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
