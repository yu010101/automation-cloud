"""Filter influencer profiles by criteria."""


def filter_profiles(profiles: list[dict], min_followers: int = 10000,
                    max_followers: int = 50000, min_views: int = 10000) -> list[dict]:
    """Filter profiles by follower count and average views."""
    matched = []
    for p in profiles:
        followers = p.get("followers_count", 0)
        views = p.get("avg_views", 0)

        if not (min_followers <= followers <= max_followers):
            continue
        if views < min_views:
            continue

        matched.append(p)

    return matched
