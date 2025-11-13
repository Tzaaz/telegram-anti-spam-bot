# FILE: rules.py
"""
Spam detection rules and scoring logic.
Fast heuristic-based scoring with configurable thresholds.
"""
import logging
from dataclasses import dataclass
from typing import List
import yaml
from pathlib import Path

from utils import (
    extract_urls,
    extract_tld,
    has_telegram_invite,
    has_url_shortener,
    has_unicode_tricks,
    contains_spam_keywords,
    get_suspicious_tlds,
    has_non_english_text,
)

logger = logging.getLogger(__name__)

# Default thresholds
WARN_THRESHOLD = 4
HARD_DELETE_THRESHOLD = 8


@dataclass
class SpamScore:
    """Container for spam scoring results."""

    total: int
    reasons: List[str]
    should_warn: bool
    should_delete: bool

    def __str__(self):
        return f"Score: {self.total} | {', '.join(self.reasons)}"


class RulesConfig:
    """Configuration for spam detection rules."""

    def __init__(self, config_path: str = "data/rules.yaml"):
        self.warn_threshold = WARN_THRESHOLD
        self.hard_delete_threshold = HARD_DELETE_THRESHOLD
        self.suspicious_tlds = get_suspicious_tlds()
        self.check_non_english = True  # Enable non-English detection by default
        self.non_english_threshold = 0.3  # 30% non-Latin characters
        self.load_config(config_path)

    def load_config(self, config_path: str):
        """Load rules from YAML file if it exists."""
        path = Path(config_path)
        if not path.exists():
            logger.info(f"Rules config not found at {config_path}, using defaults")
            return

        try:
            with open(path, "r") as f:
                config = yaml.safe_load(f)

            if config:
                self.warn_threshold = config.get("warn_threshold", WARN_THRESHOLD)
                self.hard_delete_threshold = config.get(
                    "hard_delete_threshold", HARD_DELETE_THRESHOLD
                )

                # Load additional suspicious TLDs if provided
                extra_tlds = config.get("suspicious_tlds", [])
                if extra_tlds:
                    self.suspicious_tlds.update(extra_tlds)

                # Load non-English detection settings
                self.check_non_english = config.get("check_non_english", True)
                self.non_english_threshold = config.get("non_english_threshold", 0.3)

                logger.info(
                    f"✅ Rules loaded: warn={self.warn_threshold}, "
                    f"delete={self.hard_delete_threshold}, "
                    f"non_english_check={self.check_non_english}"
                )
        except Exception as e:
            logger.warning(f"Failed to load rules config: {e}, using defaults")


def calculate_spam_score(
    text: str, strict_mode: bool = False, rules_config: RulesConfig = None
) -> SpamScore:
    """
    Calculate spam score for message text using heuristic rules.

    Args:
        text: Message text to analyze
        strict_mode: If True, adds +1 to any non-zero score
        rules_config: Optional rules configuration (uses defaults if None)

    Returns:
        SpamScore with total score, reasons, and action flags
    """
    if rules_config is None:
        rules_config = RulesConfig()

    score = 0
    reasons = []

    # Extract URLs for analysis
    urls = extract_urls(text)

    # Rule 1: Link count (≥2 links)
    link_count = len(urls)
    if link_count >= 2:
        points = min(link_count, 4)  # Cap at +4
        score += points
        reasons.append(f"{link_count} links (+{points})")

    # Rule 2: Suspicious TLDs
    suspicious_tld_count = 0
    for url in urls:
        tld = extract_tld(url)
        if tld in rules_config.suspicious_tlds:
            suspicious_tld_count += 1

    if suspicious_tld_count > 0:
        points = min(suspicious_tld_count * 2, 6)  # +2 per suspicious TLD, cap at +6
        score += points
        reasons.append(f"Suspicious TLD ({suspicious_tld_count}) (+{points})")

    # Rule 3: URL shorteners
    if has_url_shortener(urls):
        score += 3
        reasons.append("URL shortener (+3)")

    # Rule 4: Telegram invite links
    if has_telegram_invite(text):
        score += 4
        reasons.append("Telegram invite (+4)")

    # Rule 5: Spam keywords
    if contains_spam_keywords(text):
        score += 5
        reasons.append("Spam keywords (+5)")

    # Rule 6: Unicode tricks (zero-width, confusables, etc.)
    if has_unicode_tricks(text):
        score += 3
        reasons.append("Unicode tricks (+3)")

    # Rule 7: Non-English text (Cyrillic, Arabic, Chinese, etc.)
    if rules_config.check_non_english:
        if has_non_english_text(text, threshold=rules_config.non_english_threshold):
            score += 6
            reasons.append("Non-English text (+6)")

    # Strict mode penalty: add +1 to any non-zero score
    if strict_mode and score > 0:
        score += 1
        reasons.append("Strict mode (+1)")

    # Determine actions based on thresholds
    should_warn = score >= rules_config.warn_threshold
    should_delete = score >= rules_config.hard_delete_threshold

    return SpamScore(
        total=score,
        reasons=reasons,
        should_warn=should_warn,
        should_delete=should_delete,
    )


# Global rules config instance
_rules_config: RulesConfig = None


def get_rules_config() -> RulesConfig:
    """Get or initialize the global rules config."""
    global _rules_config
    if _rules_config is None:
        _rules_config = RulesConfig()
    return _rules_config
