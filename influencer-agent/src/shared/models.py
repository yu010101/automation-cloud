"""Data models for influencer-agent."""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Influencer:
    instagram_username: str
    full_name: str = ""
    biography: str = ""
    followers_count: int = 0
    avg_views: int = 0
    avg_engagement_rate: float = 0.0
    email: str = ""
    email_source: str = ""
    website_url: str = ""
    niche: str = ""
    is_verified: bool = False
    is_business_account: bool = False
    status: str = "discovered"
    raw_data: str = ""

    def matches_criteria(self, min_followers: int, max_followers: int, min_views: int) -> bool:
        if not (min_followers <= self.followers_count <= max_followers):
            return False
        if self.avg_views < min_views:
            return False
        return True


@dataclass
class DiscoveryResult:
    total_searched: int = 0
    total_matched: int = 0
    total_with_email: int = 0
    total_new: int = 0
    top_matches: list = field(default_factory=list)

    def summary(self) -> str:
        lines = [
            "Discovery Results:",
            f"  Searched: {self.total_searched} profiles",
            f"  Matched criteria: {self.total_matched} profiles",
            f"  With email: {self.total_with_email} profiles",
            f"  New (not in DB): {self.total_new} profiles",
        ]
        if self.top_matches:
            lines.append("  Top matches:")
            for m in self.top_matches[:5]:
                lines.append(f"    @{m['username']} - {m['followers']} followers, {m['views']} avg views")
        return "\n".join(lines)


@dataclass
class OutreachEmail:
    to_email: str
    to_name: str
    subject: str
    body: str
    influencer_id: int = 0
    sequence_number: int = 1
