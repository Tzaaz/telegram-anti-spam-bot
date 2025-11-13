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


def has_non_english_text(text: str, threshold: float = 0.3) -> bool:
    """
    Detect if text contains significant non-English characters.

    Args:
        text: Text to analyze
        threshold: Minimum ratio of non-Latin characters to flag (default 0.3 = 30%)

    Returns:
        True if text contains significant non-Latin script (Cyrillic, Arabic, Chinese, etc.)
    """
    # Remove whitespace, punctuation, numbers, and common symbols
    cleaned = re.sub(r'[\s\d\.\,\!\?\;\:\-\(\)\[\]\{\}\"\'\/\\@#$%^&*+=~`|<>_]', '', text)

    if len(cleaned) == 0:
        return False

    # Count non-Latin characters
    non_latin_count = 0

    for char in cleaned:
        # Get unicode block/script
        try:
            char_name = unicodedata.name(char, '')

            # Check for non-Latin scripts
            if any(script in char_name for script in [
                'CYRILLIC',      # Russian, Ukrainian, etc.
                'ARABIC',        # Arabic
                'HEBREW',        # Hebrew
                'CJK',           # Chinese, Japanese, Korean
                'HIRAGANA',      # Japanese
                'KATAKANA',      # Japanese
                'HANGUL',        # Korean
                'DEVANAGARI',    # Hindi, Sanskrit
                'THAI',          # Thai
                'GREEK',         # Greek (often used in spam)
            ]):
                non_latin_count += 1
        except (ValueError, TypeError):
            # If we can't get the name, check code point ranges
            code_point = ord(char)

            # Common non-Latin ranges
            if any([
                0x0400 <= code_point <= 0x04FF,  # Cyrillic
                0x0500 <= code_point <= 0x052F,  # Cyrillic Supplement
                0x0600 <= code_point <= 0x06FF,  # Arabic
                0x0750 <= code_point <= 0x077F,  # Arabic Supplement
                0x0590 <= code_point <= 0x05FF,  # Hebrew
                0x4E00 <= code_point <= 0x9FFF,  # CJK Unified Ideographs
                0x3040 <= code_point <= 0x309F,  # Hiragana
                0x30A0 <= code_point <= 0x30FF,  # Katakana
                0xAC00 <= code_point <= 0xD7AF,  # Hangul
                0x0900 <= code_point <= 0x097F,  # Devanagari
                0x0E00 <= code_point <= 0x0E7F,  # Thai
                0x0370 <= code_point <= 0x03FF,  # Greek
            ]):
                non_latin_count += 1

    # Calculate ratio
    ratio = non_latin_count / len(cleaned)

    if ratio >= threshold:
        logger.debug(f"Non-English text detected: {ratio:.1%} non-Latin characters")
        return True

    return False
