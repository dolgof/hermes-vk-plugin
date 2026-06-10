"""
VK access control policies: dmPolicy, groupPolicy, pairing.

Implements four DM policies:
  - "open"       — accept all incoming DMs
  - "allowlist"  — only users in allowFrom list
  - "pairing"    — challenge-response code for new users
  - "disabled"   — ignore all DMs

And three group policies:
  - "open"       — accept messages from all group members
  - "allowlist"  — only users in groupAllowFrom list
  - "disabled"   — ignore group messages

Also supports:
  - requireMention — in group chats, require @bot mention
  - Pairing challenge with numeric code validation
"""

import asyncio
import logging
import random
from typing import Dict, Optional, Set, Tuple

logger = logging.getLogger(__name__)

# In-memory pairing state.  In production this should be backed by
# a persistent store, but for a single-gateway deployment this is fine.
# Key: user_id str, Value: (code: str, expire_ts: float)
_pairing_state: Dict[str, Tuple[str, float]] = {}

# Already-paired users (cleared on restart)
_paired_users: Set[str] = set()

# Pairing code TTL in seconds
PAIRING_CODE_TTL = 300  # 5 minutes

# Default pairing code length
PAIRING_CODE_LENGTH = 6


# ---------------------------------------------------------------------------
# Policy types
# ---------------------------------------------------------------------------

DmPolicy = str  # "pairing" | "allowlist" | "open" | "disabled"
GroupPolicy = str  # "open" | "disabled" | "allowlist"


def _normalize_allowlist(entries: Optional[list]) -> Set[str]:
    """Normalize allowlist entries to a set of string user IDs."""
    if not entries:
        return set()
    return {str(e).strip() for e in entries if str(e).strip()}


def _is_wildcard(allow_from: Set[str]) -> bool:
    """Check if allowlist contains '*' (allow all)."""
    return "*" in allow_from


# ---------------------------------------------------------------------------
# DM Policy
# ---------------------------------------------------------------------------

def check_dm_policy(
    user_id: str,
    dm_policy: DmPolicy = "open",
    allow_from: Optional[list] = None,
) -> Tuple[bool, Optional[str]]:
    """
    Check if a user is allowed to send a DM.

    Args:
        user_id: The VK user ID (as string)
        dm_policy: One of "open", "allowlist", "pairing", "disabled"
        allow_from: List of allowed user IDs (or ["*"] for all)

    Returns:
        (allowed: bool, reason: Optional[str])
    """
    if dm_policy == "disabled":
        return False, "DM policy is disabled"

    if dm_policy == "open":
        return True, None

    allow_set = _normalize_allowlist(allow_from)

    if dm_policy == "allowlist":
        if _is_wildcard(allow_set):
            return True, None
        if user_id in allow_set:
            return True, None
        return False, "User not in DM allowlist"

    if dm_policy == "pairing":
        # Already paired
        if user_id in _paired_users:
            return True, None
        # Also check allowlist for pairing mode
        if allow_set and user_id in allow_set:
            _paired_users.add(user_id)
            return True, None
        return False, "Pairing required"

    # Unknown policy — deny
    return False, f"Unknown DM policy: {dm_policy}"


# ---------------------------------------------------------------------------
# Group Policy
# ---------------------------------------------------------------------------

def check_group_policy(
    user_id: str,
    group_policy: GroupPolicy = "open",
    group_allow_from: Optional[list] = None,
    require_mention: bool = False,
    message_text: str = "",
    bot_name: str = "",
) -> Tuple[bool, Optional[str]]:
    """
    Check if a message in a group chat should be processed.

    Args:
        user_id: The VK user ID
        group_policy: One of "open", "disabled", "allowlist"
        group_allow_from: List of allowed user IDs
        require_mention: Whether @mention is required
        message_text: The message text
        bot_name: The bot's display name for mention detection

    Returns:
        (allowed: bool, reason: Optional[str])
    """
    if group_policy == "disabled":
        return False, "Group policy is disabled"

    # Check allowlist for group
    if group_policy == "allowlist":
        allow_set = _normalize_allowlist(group_allow_from)
        if not _is_wildcard(allow_set) and user_id not in allow_set:
            return False, "User not in group allowlist"

    # Check requireMention
    if require_mention and bot_name and message_text:
        # Look for @mention, [clubXXX|name], or just the bot name
        text_lower = message_text.lower()
        name_lower = bot_name.lower()
        if name_lower not in text_lower:
            return False, "Bot mention required in group messages"

    return True, None


# ---------------------------------------------------------------------------
# Pairing Challenge
# ---------------------------------------------------------------------------

def generate_pairing_code() -> str:
    """Generate a numeric pairing code."""
    return str(random.randint(10 ** (PAIRING_CODE_LENGTH - 1), 10 ** PAIRING_CODE_LENGTH - 1))


def issue_pairing_challenge(user_id: str) -> str:
    """
    Generate and store a pairing challenge for a user.

    Returns the code string to send to the user.
    """
    code = generate_pairing_code()
    _pairing_state[user_id] = (code, asyncio.get_event_loop().time() + PAIRING_CODE_TTL)
    logger.info("[VK] Pairing challenge issued for user %s: %s", user_id, code)
    return code


def validate_pairing_code(user_id: str, code: str) -> bool:
    """
    Validate a pairing code submitted by a user.

    Returns True if the code matches and hasn't expired.
    """
    now = asyncio.get_event_loop().time()
    entry = _pairing_state.get(user_id)

    if not entry:
        return False

    stored_code, expires = entry
    if now > expires:
        del _pairing_state[user_id]
        return False

    if code.strip() == stored_code:
        del _pairing_state[user_id]
        _paired_users.add(user_id)
        logger.info("[VK] Pairing successful for user %s", user_id)
        return True

    return False


def revoke_pairing(user_id: str) -> None:
    """Revoke a previously paired user."""
    _paired_users.discard(user_id)
    _pairing_state.pop(user_id, None)


def get_pairing_message(code: str) -> str:
    """Generate the pairing challenge message."""
    return (
        "🔐 Для доступа к боту необходимо подтверждение.\n"
        f"Отправьте код: {code}\n\n"
        "Код действителен 5 минут."
    )


def is_awaiting_pairing(user_id: str) -> bool:
    """Check if a user has a pending pairing challenge."""
    entry = _pairing_state.get(user_id)
    if entry:
        _, expires = entry
        if asyncio.get_event_loop().time() > expires:
            del _pairing_state[user_id]
            return False
        return True
    return False
