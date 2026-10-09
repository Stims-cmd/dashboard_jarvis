"""Print an argon2 hash for JARVIS_PASSWORD_HASH.

Usage: python -m app.hash_password
"""

from getpass import getpass

from app.auth.security import hash_password


def main() -> None:
    password = getpass("New dashboard password: ")
    if len(password) < 12:
        raise SystemExit("Use at least 12 characters.")
    if getpass("Repeat: ") != password:
        raise SystemExit("Passwords do not match.")
    # Single quotes keep the "$" characters literal for Docker Compose and dotenv.
    print(f"JARVIS_PASSWORD_HASH='{hash_password(password)}'")


if __name__ == "__main__":
    main()
