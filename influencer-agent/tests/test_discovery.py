"""Tests for discovery module."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.discovery.extract import extract_email_from_text, extract_email
from src.discovery.filter import filter_profiles
from src.shared.db import init_db, upsert_influencer, get_uncontacted_with_email, get_pipeline_counts


def test_email_extraction():
    """Test email regex extraction from bio text."""
    assert extract_email_from_text("DM for collabs or email me at john@gmail.com") == "john@gmail.com"
    assert extract_email_from_text("contact: hello@mybrand.io for business") == "hello@mybrand.io"
    assert extract_email_from_text("No email here") is None
    assert extract_email_from_text("") is None
    assert extract_email_from_text("test@example.com") is None  # excluded domain
    print("  email extraction: PASS")


def test_extract_email_from_profile():
    """Test email extraction priority from profile dict."""
    # Business email takes priority
    profile = {"businessEmail": "biz@brand.com", "biography": "contact@other.com"}
    email, source = extract_email(profile)
    assert email == "biz@brand.com"
    assert source == "business_contact"

    # Falls back to bio
    profile = {"biography": "DM or email me contact@creator.com"}
    email, source = extract_email(profile)
    assert email == "contact@creator.com"
    assert source == "bio"

    # No email found
    profile = {"biography": "Just vibes"}
    email, source = extract_email(profile)
    assert email == ""
    assert source == ""
    print("  profile extraction: PASS")


def test_filter_profiles():
    """Test profile filtering logic."""
    profiles = [
        {"instagram_username": "a", "followers_count": 5000, "avg_views": 15000},   # too few followers
        {"instagram_username": "b", "followers_count": 25000, "avg_views": 15000},  # match
        {"instagram_username": "c", "followers_count": 25000, "avg_views": 5000},   # too few views
        {"instagram_username": "d", "followers_count": 60000, "avg_views": 20000},  # too many followers
        {"instagram_username": "e", "followers_count": 10000, "avg_views": 10000},  # match (edge)
    ]
    matched = filter_profiles(profiles, 10000, 50000, 10000)
    usernames = [m["instagram_username"] for m in matched]
    assert "b" in usernames
    assert "e" in usernames
    assert "a" not in usernames
    assert "c" not in usernames
    assert "d" not in usernames
    assert len(matched) == 2
    print("  filter profiles: PASS")


def test_database_operations():
    """Test SQLite CRUD operations."""
    init_db()

    # Upsert
    data = {
        "instagram_username": "test_user_123",
        "full_name": "Test User",
        "biography": "test bio",
        "followers_count": 20000,
        "avg_views": 15000,
        "avg_engagement_rate": 3.5,
        "email": "test@creator.com",
        "email_source": "bio",
        "website_url": "https://test.com",
        "niche": "test",
        "is_verified": False,
        "is_business_account": True,
        "raw_data": "{}",
    }
    row_id = upsert_influencer(data)
    assert row_id is not None

    # Query
    uncontacted = get_uncontacted_with_email(limit=10)
    found = [u for u in uncontacted if u["instagram_username"] == "test_user_123"]
    assert len(found) == 1
    assert found[0]["email"] == "test@creator.com"

    # Pipeline counts
    counts = get_pipeline_counts()
    assert "discovered" in counts
    assert counts["discovered"] >= 1

    # Cleanup: remove test data
    from src.shared.db import get_connection
    with get_connection() as conn:
        conn.execute("DELETE FROM influencers WHERE instagram_username = 'test_user_123'")
    print("  database operations: PASS")


def test_classify_import():
    """Test that classify module imports correctly."""
    from src.followup.classify import CATEGORIES
    assert "interested" in CATEGORIES
    assert "not_interested" in CATEGORIES
    assert len(CATEGORIES) == 6
    print("  classify import: PASS")


if __name__ == "__main__":
    print("Running tests...")
    test_email_extraction()
    test_extract_email_from_profile()
    test_filter_profiles()
    test_database_operations()
    test_classify_import()
    print("\nAll tests passed!")
