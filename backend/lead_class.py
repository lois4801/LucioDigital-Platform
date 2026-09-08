"""Automatic lead classification: separates test/dummy submissions from real people.

Pure regex/heuristics — no LLM call, so it runs on every lead at write time and on backfill.
A manual override (lane_manual) always wins and is never recomputed.
"""
import re

TEST_NAME_WORDS = ("qa", "test", "testing", "tester", "e2e", "dummy", "demo", "lorem",
                   "ipsum", "placeholder", "foobar", "asdf", "qwerty", "automation",
                   "playwright", "selenium", "cypress", "smoke", "fixture", "mock")
VERSION_RE = re.compile(r"\b[vV]\d{1,2}(\.\d+)?\b")
CAPS_TEST_RE = re.compile(r"\b(TEST|QA|E2E|DUMMY|DEMO)\b")
HEX_RE = re.compile(r"^[0-9a-f]{8,}$", re.I)
NO_VOWEL_RE = re.compile(r"^[^aeiouyAEIOUY\s]{5,}$")

DISPOSABLE_DOMAINS = {
    "resend.dev", "mailinator.com", "test.com", "test.dev", "testing.com", "example.com",
    "example.org", "example.net", "example.co", "localhost", "yopmail.com", "guerrillamail.com",
    "guerrillamail.info", "sharklasers.com", "10minutemail.com", "tempmail.com", "temp-mail.org",
    "tempmailo.com", "throwawaymail.com", "trashmail.com", "trashmail.de", "dispostable.com",
    "maildrop.cc", "getnada.com", "nada.email", "mailnesia.com", "fakeinbox.com", "fakemail.net",
    "mytemp.email", "moakt.com", "inboxkitten.com", "emailondeck.com", "spam4.me", "grr.la",
    "mail7.io", "harakirimail.com", "mohmal.com", "burnermail.io", "mailcatch.com", "mail.tm",
    "discard.email", "anonaddy.me", "spamgourmet.com", "wegwerfmail.de", "einrot.com",
    "mailsac.com", "email.tst", "qa.com", "demo.com", "dummy.com", "noreply.com", "no-reply.com",
}
FREE_DOMAINS = {"gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "hotmail.com", "hotmail.co.uk",
                "outlook.com", "live.com", "msn.com", "aol.com", "icloud.com", "me.com", "mail.com",
                "gmx.com", "gmx.de", "proton.me", "protonmail.com", "yandex.com", "zoho.com"}


def _domain(email: str) -> str:
    return (email or "").strip().lower().rsplit("@", 1)[-1] if "@" in (email or "") else ""


def _name_looks_fake(name: str) -> bool:
    n = (name or "").strip()
    if not n:
        return False
    low = n.lower()
    tokens = re.split(r"[^a-z0-9]+", low)
    if any(t in TEST_NAME_WORDS for t in tokens if t):
        return True
    if VERSION_RE.search(n):
        return True
    if HEX_RE.match(low.replace(" ", "")) or NO_VOWEL_RE.match(n.replace(" ", "")):
        return True
    if len(low.replace(" ", "")) < 2:
        return True
    if re.match(r"^(user|client|customer|person|lead)[\s_-]*\d+$", low):
        return True
    return False


def _natural_language(text: str) -> bool:
    t = (text or "").strip()
    if len(t) < 20:
        return False
    words = re.findall(r"[A-Za-z']{2,}", t)
    if len(words) < 5:
        return False
    common = {"the", "a", "an", "and", "or", "is", "are", "we", "i", "you", "my", "our", "for", "to",
              "of", "in", "on", "with", "would", "can", "could", "need", "want", "looking", "please",
              "hi", "hello", "thanks", "have", "do", "about", "quote", "help"}
    return any(w.lower() in common for w in words)


def classify(name: str = "", email: str = "", body: str = "", subject: str = "",
             source: str = "", meta: dict = None) -> dict:
    """Returns {lane, reasons, review}. lane is 'test' or 'real'."""
    meta = meta or {}
    reasons = []
    dom = _domain(email)
    text = f"{subject or ''} {body or ''}"

    if meta.get("automated") or meta.get("seeded") or str(meta.get("user_agent") or "").lower().find("playwright") >= 0:
        reasons.append("created by an automated test run")
    if _name_looks_fake(name):
        reasons.append(f"name looks like a test entry ({(name or '').strip()[:40]})")
    if dom and dom in DISPOSABLE_DOMAINS:
        reasons.append(f"disposable/test email domain ({dom})")
    if dom and (dom.startswith("test.") or dom.startswith("qa.") or dom.startswith("demo.")
                or dom.endswith(".test") or dom.endswith(".local") or dom.endswith(".invalid")):
        reasons.append(f"non-production email domain ({dom})")
    local = (email or "").split("@")[0].lower()
    if local and any(local.startswith(w) or local == w for w in ("test", "qa", "e2e", "dummy", "demo", "noreply", "no-reply")):
        reasons.append(f"test mailbox name ({local[:30]})")
    if CAPS_TEST_RE.search(text):
        reasons.append("message contains TEST/QA in capitals")

    if reasons:
        return {"lane": "test", "reasons": reasons[:4], "review": False}

    review = []
    if not _natural_language(body):
        review.append("message does not read like natural language")
    if not email:
        review.append("no email address supplied")
    elif dom in FREE_DOMAINS:
        review.append(f"free email domain ({dom})")
    if not (name or "").strip():
        review.append("no name supplied")
    return {"lane": "real", "reasons": [], "review": bool(review), "review_reasons": review[:3]}
