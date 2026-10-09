"""Owner's known software (data/skills.md), compared locally: never sent to Claude."""

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def normalize(name: str) -> str:
    """'Apache HTTP-Server ' -> 'apache http server'."""
    return " ".join(re.sub(r"[^a-z0-9]+", " ", name.lower()).split())


def product_key(vendor: str | None, product: str) -> str:
    return normalize(f"{vendor or ''} {product}")


def load_skills(path: Path) -> set[str] | None:
    """Normalized skill names, or None if the file does not exist."""
    if not path.is_file():
        logger.warning("skills file not found: %s (no product sheets generated)", path)
        return None
    skills = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(("-", "*")):
            name = normalize(line[1:])
            if name:
                skills.add(name)
    return skills


def is_known(skills: set[str], vendor: str | None, product: str) -> bool:
    """Known if the skill list names the product, with or without its vendor."""
    product_name = normalize(product)
    return product_name in skills or product_key(vendor, product) in skills
