# FILE: utils.py
"""
Utility functions for text extraction and analysis.
"""
import re
import logging
import unicodedata
from typing import List, Set
from urllib.parse import urlparse
import tldextract

logger = logging.getLogger(__name__)


def extract_text_from_message(message) -> str:
    """
    Extract all text content from a Telegram message.
    Includes message text and caption.
    """
    parts = []
    if message.text:
        parts.append(message.text)
    if message.caption:
        parts.append(message.caption)
    return " ".join(parts)


def extract_urls(text: str) -> List[str]:
    """
    Extract all URLs from text using regex.
    Covers http(s), www patterns, and naked domains.
    """
    # Pattern to match URLs
    url_pattern = re.compile(
        r"(?:(?:https?://)|(?:www\.)|(?:[a-zA-Z0-9-]+\.[a-zA-Z]{2,}))"
        r"(?:[^\s<>\"'\)]+)?",
        re.IGNORECASE,
    )
    matches = url_pattern.findall(text)
    return [m for m in matches if m]


def extract_tld(url: str) -> str:
    """
    Extract top-level domain from URL.
    Returns empty string if parsing fails.
    """
    try:
        extracted = tldextract.extract(url)
        return extracted.suffix.lower()
    except Exception as e:
        logger.debug(f"Failed to extract TLD from {url}: {e}")
        return ""


def has_telegram_invite(text: str) -> bool:
    """Check if text contains Telegram invite links."""
    patterns = [
        r"t\.me/joinchat/",
        r"t\.me/\+",
        r"telegram\.me/joinchat/",
        r"telegram\.me/\+",
    ]
    for pattern in patterns:
        if re.search(pattern, text, re.IGNORECASE):
            return True
    return False


def count_links(text: str) -> int:
    """Count total number of URLs in text."""
    return len(extract_urls(text))


def has_url_shortener(urls: List[str]) -> bool:
    """Check if any URL uses a known shortener service."""
    shorteners = {
        "bit.ly",
        "t.co",
        "tinyurl.com",
        "goo.gl",
        "ow.ly",
        "is.gd",
        "buff.ly",
        "adf.ly",
    }
    for url in urls:
        try:
            parsed = urlparse(url if "://" in url else f"http://{url}")
            domain = parsed.netloc.lower().replace("www.", "")
            if domain in shorteners:
                return True
        except Exception:
            pass
    return False


def has_unicode_tricks(text: str) -> bool:
    """
    Detect unicode confusables, zero-width chars, and suspicious patterns.
    """
    # Zero-width and invisible characters
    zero_width_chars = {
        "\u200b",  # ZERO WIDTH SPACE
        "\u200c",  # ZERO WIDTH NON-JOINER
        "\u200d",  # ZERO WIDTH JOINER
        "\u2060",  # WORD JOINER
        "\ufeff",  # ZERO WIDTH NO-BREAK SPACE
    }

    for char in text:
        if char in zero_width_chars:
            return True

    # Check for excessive combining characters (can hide real text)
    combining_count = sum(1 for c in text if unicodedata.combining(c))
    if combining_count > len(text) * 0.1:  # More than 10% combining chars
        return True

    # Check for right-to-left override tricks
    rtl_chars = {"\u202e", "\u202d"}
    if any(char in text for char in rtl_chars):
        return True

    return False


def contains_spam_keywords(text: str) -> bool:
    """
    Check for common spam keywords.
    Case-insensitive matching.
    """
    spam_keywords = [
        # Crypto spam
        "free crypto",
        "airdrop",
        "giveaway",
        "claim now",
        "free btc",
        "free eth",
        "free tokens",
        # Phishing
        "verify your account",
        "verification team",
        "verify now",
        "urgent action required",
        # Adult content
        r"\b(xxx|18\+|onlyfans)\b",
        "hot singles",
        # Generic spam
        "dm me",
        "click here",
        "limited time",
        "act now",
        "congratulations you won",
        "prize winner",
        # Scams
        "double your",
        "investment opportunity",
        "make money fast",
        "work from home",
        "no experience needed",
    ]

    text_lower = text.lower()
    for keyword in spam_keywords:
        if re.search(keyword, text_lower):
            return True

    return False


def get_suspicious_tlds() -> Set[str]:
    """Return set of TLDs commonly associated with spam."""
    return {
        "ru",
        "icu",
        "xyz",
        "top",
        "monster",
        "tk",
        "ml",
        "ga",
        "cf",
        "gq",
        "work",
        "click",
        "link",
        "loan",
        "win",
        "bid",
    }


def normalize_text(text: str) -> str:
    """
    Normalize text for comparison.
    Strips whitespace, converts to lowercase, removes zero-width chars.
    """
    # Remove zero-width and invisible chars
    text = re.sub(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]", "", text)
    # Normalize unicode
    text = unicodedata.normalize("NFKC", text)
    # Strip and lowercase
    return text.strip().lower()
