# FILE: storage.py
"""
Redis wrapper for state management.
Handles strikes, dedup cache, strict mode, whitelists/blacklists.
"""
import logging
import hashlib
from typing import Optional, Set
import redis.asyncio as redis
from redis.asyncio import Redis

logger = logging.getLogger(__name__)

# TTLs
STRIKE_TTL_SECONDS = 7 * 24 * 60 * 60  # 7 days
DEDUP_TTL_SECONDS = 60 * 60  # 1 hour


class Store:
    """Redis-backed storage for bot state."""

    def __init__(self, redis_url: str):
        """
        Initialize Redis client.
        Handles both redis:// (no TLS) and rediss:// (TLS).
        """
        self.redis_url = redis_url
        self.client: Optional[Redis] = None

    async def connect(self):
        """Establish Redis connection."""
        try:
            # Parse URL and determine TLS
            ssl_enabled = self.redis_url.startswith("rediss://")
            self.client = redis.from_url(
                self.redis_url,
                encoding="utf-8",
                decode_responses=True,
                ssl_cert_reqs=None if ssl_enabled else None,
            )
            # Test connection
            await self.client.ping()
            logger.info(f"✅ Redis connected (TLS={ssl_enabled})")
        except Exception as e:
            logger.error(f"❌ Redis connection failed: {e}")
            self.client = None

    async def close(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            logger.info("Redis connection closed")

    async def healthy(self) -> bool:
        """Check if Redis is reachable."""
        if not self.client:
            return False
        try:
            await self.client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis health check failed: {e}")
            return False

    # --- Strikes ---

    def _strike_key(self, chat_id: int, user_id: int) -> str:
        """Generate Redis key for user strikes in a chat."""
        return f"strikes:{chat_id}:{user_id}"

    async def get_strikes(self, chat_id: int, user_id: int) -> int:
        """Get current strike count for a user in a chat."""
        if not self.client:
            return 0
        try:
            key = self._strike_key(chat_id, user_id)
            val = await self.client.get(key)
            return int(val) if val else 0
        except Exception as e:
            logger.error(f"Error getting strikes: {e}")
            return 0

    async def increment_strikes(self, chat_id: int, user_id: int) -> int:
        """Increment strike count and return new total."""
        if not self.client:
            return 0
        try:
            key = self._strike_key(chat_id, user_id)
            new_count = await self.client.incr(key)
            await self.client.expire(key, STRIKE_TTL_SECONDS)
            logger.info(f"User {user_id} in chat {chat_id} now has {new_count} strike(s)")
            return new_count
        except Exception as e:
            logger.error(f"Error incrementing strikes: {e}")
            return 0

    async def reset_strikes(self, chat_id: int, user_id: int):
        """Clear strikes for a user in a chat."""
        if not self.client:
            return
        try:
            key = self._strike_key(chat_id, user_id)
            await self.client.delete(key)
            logger.info(f"Strikes reset for user {user_id} in chat {chat_id}")
        except Exception as e:
            logger.error(f"Error resetting strikes: {e}")

    # --- Dedup Cache ---

    def _dedup_key(self, chat_id: int, content_hash: str) -> str:
        """Generate Redis key for dedup cache."""
        return f"dedup:{chat_id}:{content_hash}"

    def _hash_content(self, text: str) -> str:
        """Create a short hash of message content."""
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]

    async def is_duplicate(self, chat_id: int, text: str) -> bool:
        """Check if this content was recently processed."""
        if not self.client:
            return False
        try:
            content_hash = self._hash_content(text)
            key = self._dedup_key(chat_id, content_hash)
            exists = await self.client.exists(key)
            return bool(exists)
        except Exception as e:
            logger.error(f"Error checking dedup: {e}")
            return False

    async def mark_as_processed(self, chat_id: int, text: str):
        """Mark content as processed to avoid duplicate actions."""
        if not self.client:
            return
        try:
            content_hash = self._hash_content(text)
            key = self._dedup_key(chat_id, content_hash)
            await self.client.setex(key, DEDUP_TTL_SECONDS, "1")
        except Exception as e:
            logger.error(f"Error marking as processed: {e}")

    # --- Strict Mode (per chat) ---

    def _strict_key(self, chat_id: int) -> str:
        """Generate Redis key for chat strict mode."""
        return f"strict:{chat_id}"

    async def is_strict_mode(self, chat_id: int) -> bool:
        """Check if strict mode is enabled for a chat."""
        if not self.client:
            return False
        try:
            key = self._strict_key(chat_id)
            val = await self.client.get(key)
            return val == "1"
        except Exception as e:
            logger.error(f"Error checking strict mode: {e}")
            return False

    async def toggle_strict_mode(self, chat_id: int) -> bool:
        """Toggle strict mode for a chat and return new state."""
        if not self.client:
            return False
        try:
            key = self._strict_key(chat_id)
            current = await self.is_strict_mode(chat_id)
            new_state = not current
            await self.client.set(key, "1" if new_state else "0")
            logger.info(f"Strict mode {'enabled' if new_state else 'disabled'} for chat {chat_id}")
            return new_state
        except Exception as e:
            logger.error(f"Error toggling strict mode: {e}")
            return False

    # --- Whitelist (per chat) ---

    def _whitelist_key(self, chat_id: int) -> str:
        """Generate Redis key for chat whitelist."""
        return f"whitelist:{chat_id}"

    async def is_whitelisted(self, chat_id: int, user_id: int) -> bool:
        """Check if user is whitelisted in a chat."""
        if not self.client:
            return False
        try:
            key = self._whitelist_key(chat_id)
            return await self.client.sismember(key, str(user_id))
        except Exception as e:
            logger.error(f"Error checking whitelist: {e}")
            return False

    async def add_to_whitelist(self, chat_id: int, user_id: int):
        """Add user to chat whitelist."""
        if not self.client:
            return
        try:
            key = self._whitelist_key(chat_id)
            await self.client.sadd(key, str(user_id))
            logger.info(f"User {user_id} added to whitelist in chat {chat_id}")
        except Exception as e:
            logger.error(f"Error adding to whitelist: {e}")

    async def remove_from_whitelist(self, chat_id: int, user_id: int):
        """Remove user from chat whitelist."""
        if not self.client:
            return
        try:
            key = self._whitelist_key(chat_id)
            await self.client.srem(key, str(user_id))
            logger.info(f"User {user_id} removed from whitelist in chat {chat_id}")
        except Exception as e:
            logger.error(f"Error removing from whitelist: {e}")

    async def get_whitelist(self, chat_id: int) -> Set[int]:
        """Get all whitelisted users in a chat."""
        if not self.client:
            return set()
        try:
            key = self._whitelist_key(chat_id)
            members = await self.client.smembers(key)
            return {int(uid) for uid in members}
        except Exception as e:
            logger.error(f"Error getting whitelist: {e}")
            return set()

    # --- Blacklist (per chat) ---

    def _blacklist_key(self, chat_id: int) -> str:
        """Generate Redis key for chat blacklist."""
        return f"blacklist:{chat_id}"

    async def is_blacklisted(self, chat_id: int, user_id: int) -> bool:
        """Check if user is blacklisted in a chat."""
        if not self.client:
            return False
        try:
            key = self._blacklist_key(chat_id)
            return await self.client.sismember(key, str(user_id))
        except Exception as e:
            logger.error(f"Error checking blacklist: {e}")
            return False

    async def add_to_blacklist(self, chat_id: int, user_id: int):
        """Add user to chat blacklist."""
        if not self.client:
            return
        try:
            key = self._blacklist_key(chat_id)
            await self.client.sadd(key, str(user_id))
            logger.info(f"User {user_id} added to blacklist in chat {chat_id}")
        except Exception as e:
            logger.error(f"Error adding to blacklist: {e}")

    async def remove_from_blacklist(self, chat_id: int, user_id: int):
        """Remove user from chat blacklist."""
        if not self.client:
            return
        try:
            key = self._blacklist_key(chat_id)
            await self.client.srem(key, str(user_id))
            logger.info(f"User {user_id} removed from blacklist in chat {chat_id}")
        except Exception as e:
            logger.error(f"Error removing from blacklist: {e}")

    async def get_blacklist(self, chat_id: int) -> Set[int]:
        """Get all blacklisted users in a chat."""
        if not self.client:
            return set()
        try:
            key = self._blacklist_key(chat_id)
            members = await self.client.smembers(key)
            return {int(uid) for uid in members}
        except Exception as e:
            logger.error(f"Error getting blacklist: {e}")
            return set()
