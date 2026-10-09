"""Gravatar: is a public profile attached to an email? Only a SHA-256 hash is sent."""

import hashlib

import httpx2

from modules.osint.sources import RawFinding

PROFILE_URL = "https://api.gravatar.com/v3/profiles/{hash}"


def email_hash(email: str) -> str:
    return hashlib.sha256(email.strip().lower().encode()).hexdigest()


def check_profile(http: httpx2.Client, email: str, subject: str) -> RawFinding | None:
    response = http.get(PROFILE_URL.format(hash=email_hash(email)))
    if response.status_code == 404:
        return None
    response.raise_for_status()
    profile = response.json()
    return RawFinding(
        kind="gravatar",
        subject=subject,
        source="gravatar",
        key="profile",
        title="Profil Gravatar public",
        details={
            "url": profile.get("profile_url"),
            "display_name": profile.get("display_name"),
            "location": profile.get("location"),
        },
    )
