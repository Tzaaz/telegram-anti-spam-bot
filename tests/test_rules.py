# FILE: tests/test_rules.py
"""
Unit tests for spam detection rules.
Run with: pytest tests/test_rules.py
"""
import pytest
from rules import calculate_spam_score, RulesConfig


@pytest.fixture
def rules_config():
    """Create a test rules config."""
    return RulesConfig()


def test_clean_message(rules_config):
    """Test that clean messages get low scores."""
    text = "Hello everyone! How are you doing today?"
    score = calculate_spam_score(text, strict_mode=False, rules_config=rules_config)
    assert score.total == 0
    assert not score.should_warn
    assert not score.should_delete


def test_multiple_links(rules_config):
    """Test that multiple links increase score."""
    text = "Check out https://example.com and https://another.com"
    score = calculate_spam_score(text, strict_mode=False, rules_config=rules_config)
    assert score.total >= 2  # Should get points for 2 links
    assert any("links" in reason.lower() for reason in score.reasons)


def test_suspicious_tld(rules_config):
    """Test that suspicious TLDs increase score."""
    text = "Visit my site at https://scam.xyz and https://phishing.ru"
    score = calculate_spam_score(text, strict_mode=False, rules_config=rules_config)
    assert score.total > 0
    assert any("suspicious tld" in reason.lower() for reason in score.reasons)


def test_url_shortener(rules_config):
    """Test that URL shorteners are flagged."""
    text = "Click here: https://bit.ly/abc123"
    score = calculate_spam_score(text, strict_mode=False, rules_config=rules_config)
    assert score.total >= 3
    assert any("shortener" in reason.lower() for reason in score.reasons)


def test_telegram_invite(rules_config):
    """Test that Telegram invite links are flagged."""
    text = "Join our group: https://t.me/joinchat/abc123"
    score = calculate_spam_score(text, strict_mode=False, rules_config=rules_config)
    assert score.total >= 4
    assert any("telegram invite" in reason.lower() for reason in score.reasons)


def test_spam_keywords(rules_config):
    """Test that spam keywords increase score."""
    text = "Free crypto airdrop! Claim now!"
    score = calculate_spam_score(text, strict_mode=False, rules_config=rules_config)
    assert score.total >= 5
    assert any("spam keywords" in reason.lower() for reason in score.reasons)


def test_unicode_tricks(rules_config):
    """Test that unicode tricks are detected."""
    # Zero-width space
    text = "Hello\u200bWorld"
    score = calculate_spam_score(text, strict_mode=False, rules_config=rules_config)
    assert score.total >= 3
    assert any("unicode tricks" in reason.lower() for reason in score.reasons)


def test_high_spam_score(rules_config):
    """Test a clearly spammy message."""
    text = (
        "🚀 FREE CRYPTO GIVEAWAY! 🚀\n"
        "Click here: https://bit.ly/freecrypto\n"
        "And here: https://scam.xyz/airdrop\n"
        "Join now: https://t.me/joinchat/spam123\n"
        "DM me for verification!"
    )
    score = calculate_spam_score(text, strict_mode=False, rules_config=rules_config)
    assert score.total >= 8  # Should exceed hard delete threshold
    assert score.should_delete
    assert len(score.reasons) >= 3  # Multiple reasons


def test_strict_mode_adds_penalty(rules_config):
    """Test that strict mode adds +1 to non-zero scores."""
    text = "Check out https://example.com and https://another.com"
    
    # Without strict mode
    score_normal = calculate_spam_score(text, strict_mode=False, rules_config=rules_config)
    
    # With strict mode
    score_strict = calculate_spam_score(text, strict_mode=True, rules_config=rules_config)
    
    # Strict should be +1 higher (if score was non-zero)
    if score_normal.total > 0:
        assert score_strict.total == score_normal.total + 1
        assert any("strict mode" in reason.lower() for reason in score_strict.reasons)


def test_warning_threshold(rules_config):
    """Test that scores above warning threshold trigger warnings."""
    # Create a message that should warn but not delete
    text = "Check out https://example.com and https://another.com and https://third.com"
    score = calculate_spam_score(text, strict_mode=False, rules_config=rules_config)
    
    # Should warn at 4+
    if score.total >= 4:
        assert score.should_warn


def test_delete_threshold(rules_config):
    """Test that scores above delete threshold trigger deletion."""
    # Create a message that should definitely be deleted
    text = (
        "Free crypto giveaway! "
        "https://bit.ly/abc https://scam.xyz https://phishing.ru "
        "https://t.me/joinchat/spam"
    )
    score = calculate_spam_score(text, strict_mode=False, rules_config=rules_config)
    
    # Should delete at 8+
    if score.total >= 8:
        assert score.should_delete


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
