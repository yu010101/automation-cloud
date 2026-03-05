"""Email extraction from Instagram profiles."""

import re

EMAIL_REGEX = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

# Common false-positive domains to exclude
EXCLUDED_DOMAINS = {"example.com", "email.com", "youremail.com", "mail.com"}


def extract_email_from_text(text: str) -> str | None:
    """Extract the first valid email from text."""
    if not text:
        return None
    matches = EMAIL_REGEX.findall(text)
    for email in matches:
        domain = email.split("@")[1].lower()
        if domain not in EXCLUDED_DOMAINS:
            return email.lower()
    return None


def extract_email(profile: dict) -> tuple[str, str]:
    """Extract email from an Instagram profile.

    Returns (email, source) tuple.
    Sources: 'business_contact', 'bio', 'website', ''
    """
    # Priority 1: Business contact email (official)
    biz_email = profile.get("businessEmail")
    if biz_email:
        return biz_email.lower(), "business_contact"

    # Priority 2: Email in biography
    bio = profile.get("biography", "")
    bio_email = extract_email_from_text(bio)
    if bio_email:
        return bio_email, "bio"

    # Priority 3: External URL (would need website scraping - deferred)
    # This is handled by a separate async process if needed

    return "", ""
