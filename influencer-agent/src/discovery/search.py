#!/usr/bin/env python3
"""Instagram influencer discovery via Apify.

Usage:
    python -m src.discovery.search --niche "fitness" --hashtags "fitnessmotivation,gymlife" --limit 200
    python -m src.discovery.search --usernames "user1,user2,user3"
"""

import argparse
import json
import sys
from pathlib import Path

from apify_client import ApifyClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
from src.shared.config import get_env, load_config
from src.shared.db import init_db, upsert_influencer
from src.discovery.filter import filter_profiles
from src.discovery.extract import extract_email


INSTAGRAM_PROFILE_SCRAPER = "apify/instagram-profile-scraper"
INSTAGRAM_SEARCH_SCRAPER = "apify/instagram-search-scraper"


def search_by_hashtags(client: ApifyClient, hashtags: list[str], limit: int) -> list[dict]:
    """Search Instagram profiles by hashtags using search scraper."""
    results = []
    for tag in hashtags:
        run_input = {
            "search": tag,
            "resultsType": "user",
            "resultsLimit": limit,
        }
        print(f"Searching hashtag: #{tag} (limit: {limit})...")
        run = client.actor(INSTAGRAM_SEARCH_SCRAPER).call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        print(f"  Found {len(items)} results for #{tag}")
        results.extend(items)
    return results


def scrape_profiles(client: ApifyClient, usernames: list[str]) -> list[dict]:
    """Scrape full profile data for a list of usernames."""
    if not usernames:
        return []

    # Apify has limits per run; batch in groups of 50
    all_profiles = []
    for i in range(0, len(usernames), 50):
        batch = usernames[i : i + 50]
        run_input = {"usernames": batch}
        print(f"Scraping profiles batch {i // 50 + 1}: {len(batch)} usernames...")
        run = client.actor(INSTAGRAM_PROFILE_SCRAPER).call(run_input=run_input)
        items = list(client.dataset(run["defaultDatasetId"]).iterate_items())
        all_profiles.extend(items)
    return all_profiles


def process_profile(profile: dict, niche: str) -> dict:
    """Transform Apify profile data into our internal format."""
    username = profile.get("username", "")
    followers = profile.get("followersCount", 0)
    posts = profile.get("latestPosts", [])
    biography = profile.get("biography", "")

    # Calculate average views from recent posts
    view_counts = []
    like_counts = []
    for post in posts[:20]:
        views = post.get("videoViewCount") or post.get("viewCount") or 0
        likes = post.get("likesCount", 0)
        if views > 0:
            view_counts.append(views)
        if likes > 0:
            like_counts.append(likes)

    avg_views = int(sum(view_counts) / len(view_counts)) if view_counts else 0
    avg_likes = int(sum(like_counts) / len(like_counts)) if like_counts else 0
    engagement_rate = (avg_likes / followers * 100) if followers > 0 else 0

    # Extract email
    email, email_source = extract_email(profile)

    return {
        "instagram_username": username,
        "full_name": profile.get("fullName", ""),
        "biography": biography,
        "followers_count": followers,
        "avg_views": avg_views,
        "avg_engagement_rate": round(engagement_rate, 2),
        "email": email,
        "email_source": email_source,
        "website_url": profile.get("externalUrl", ""),
        "niche": niche,
        "is_verified": profile.get("isVerified", False),
        "is_business_account": profile.get("isBusinessAccount", False),
        "raw_data": json.dumps({"username": username, "followers": followers, "posts_count": profile.get("postsCount", 0)}),
    }


def run_discovery(niche: str = "", hashtags: list[str] | None = None, usernames: list[str] | None = None,
                  min_followers: int = 10000, max_followers: int = 50000, min_views: int = 10000,
                  limit: int = 200) -> dict:
    """Main discovery pipeline."""
    init_db()
    config = load_config()
    token = get_env("APIFY_API_TOKEN")
    client = ApifyClient(token)

    # Use config defaults if not provided
    disc_config = config.get("discovery", {})
    if not hashtags and not usernames:
        hashtags = disc_config.get("hashtags", [])
    if not niche:
        niche = ",".join(disc_config.get("niche_keywords", []))
    filters = disc_config.get("filters", {})
    min_followers = min_followers or filters.get("min_followers", 10000)
    max_followers = max_followers or filters.get("max_followers", 50000)
    min_views = min_views or filters.get("min_avg_views", 10000)

    profiles = []

    # Step 1: Search by hashtags or scrape specific usernames
    if usernames:
        profiles = scrape_profiles(client, usernames)
    elif hashtags:
        # Search returns user summaries; scrape full profiles
        search_results = search_by_hashtags(client, hashtags, limit)
        found_usernames = list({r.get("username", "") for r in search_results if r.get("username")})
        print(f"Found {len(found_usernames)} unique usernames from search")
        if found_usernames:
            profiles = scrape_profiles(client, found_usernames[:limit])

    # Step 2: Process and filter
    processed = [process_profile(p, niche) for p in profiles if p.get("username")]
    matched = filter_profiles(processed, min_followers, max_followers, min_views)

    # Step 3: Save to database
    new_count = 0
    for inf in matched:
        row_id = upsert_influencer(inf)
        if row_id:
            new_count += 1

    with_email = [m for m in matched if m.get("email")]
    top_matches = sorted(matched, key=lambda x: x.get("avg_engagement_rate", 0), reverse=True)[:5]

    result = {
        "total_searched": len(profiles),
        "total_matched": len(matched),
        "total_with_email": len(with_email),
        "total_new": new_count,
        "top_matches": [
            {"username": m["instagram_username"], "followers": m["followers_count"],
             "views": m["avg_views"], "engagement": m["avg_engagement_rate"], "email": m.get("email", "")}
            for m in top_matches
        ],
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="Instagram influencer discovery")
    parser.add_argument("--niche", default="", help="Target niche")
    parser.add_argument("--hashtags", default="", help="Comma-separated hashtags")
    parser.add_argument("--usernames", default="", help="Comma-separated usernames to scrape directly")
    parser.add_argument("--min-followers", type=int, default=10000)
    parser.add_argument("--max-followers", type=int, default=50000)
    parser.add_argument("--min-views", type=int, default=10000)
    parser.add_argument("--limit", type=int, default=200)
    args = parser.parse_args()

    hashtags = [h.strip() for h in args.hashtags.split(",") if h.strip()] if args.hashtags else None
    usernames = [u.strip() for u in args.usernames.split(",") if u.strip()] if args.usernames else None

    result = run_discovery(
        niche=args.niche, hashtags=hashtags, usernames=usernames,
        min_followers=args.min_followers, max_followers=args.max_followers,
        min_views=args.min_views, limit=args.limit,
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
