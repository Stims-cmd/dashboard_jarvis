"""Does a username exist on public platforms? Official public APIs only."""

from collections.abc import Callable
from dataclasses import dataclass

import httpx2

from modules.osint.sources import RawFinding


@dataclass(frozen=True)
class Platform:
    name: str
    api_url: str  # {u} is replaced by the username
    profile_url: str
    # Some APIs answer 200 with an empty result instead of 404.
    exists: Callable[[httpx2.Response], bool] = lambda r: r.status_code == 200


PLATFORMS = (
    Platform("GitHub", "https://api.github.com/users/{u}", "https://github.com/{u}"),
    Platform(
        "GitLab",
        "https://gitlab.com/api/v4/users?username={u}",
        "https://gitlab.com/{u}",
        lambda r: r.status_code == 200 and r.json() != [],
    ),
    Platform("Codeberg", "https://codeberg.org/api/v1/users/{u}", "https://codeberg.org/{u}"),
    Platform(
        "Keybase",
        "https://keybase.io/_/api/1.0/user/lookup.json?usernames={u}",
        "https://keybase.io/{u}",
        lambda r: r.status_code == 200 and any(r.json().get("them") or []),
    ),
    Platform(
        "Hacker News",
        "https://hacker-news.firebaseio.com/v0/user/{u}.json",
        "https://news.ycombinator.com/user?id={u}",
        lambda r: r.status_code == 200 and r.json() is not None,
    ),
    Platform(
        "Chess.com", "https://api.chess.com/pub/player/{u}", "https://www.chess.com/member/{u}"
    ),
)


def check_username(http: httpx2.Client, platform: Platform, username: str) -> RawFinding | None:
    response = http.get(platform.api_url.format(u=username))
    if response.status_code not in (200, 404):
        response.raise_for_status()
    if not platform.exists(response):
        return None
    url = platform.profile_url.format(u=username)
    return RawFinding(
        kind="account",
        subject=username,
        source="platforms",
        key=platform.name,
        title=f"{platform.name} : {username}",
        details={"url": url},
    )
