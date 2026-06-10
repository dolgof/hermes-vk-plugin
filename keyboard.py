"""
VK Inline Keyboard builder — expanded with all VK action types.

Based on vkbottle tools/keyboard/ design (ABCAction hierarchy)
and VK Bot API keyboard documentation.

vkbottle is MIT-licensed:
  Copyright (c) 2019 timoniq
  Copyright (c) 2022-2024 feeeek (Axd1x8a)
  Copyright (c) 2024 luwqz1
  https://github.com/vkbottle/vkbottle/blob/master/LICENSE

Supported actions:
  Text      — sends message text with payload
  Callback  — sends message_event (button hides after click)
  OpenLink  — opens URL in browser
  Location  — requests user geolocation (max 2 per row)
  VKPay     — opens VK Pay (must be alone in row)
  VKApps    — opens VK Mini App

Keyboard types:
  Inline (inline=True)  — shown inside the message (max 10 buttons, 6 rows, 5/row)
  Reply  (inline=False) — shown below input field  (max 40 buttons, 10 rows, 5/row)

Usage:
    from vk.keyboard import Keyboard, Text, KeyboardButtonColor

    kb = Keyboard(inline=True)
    kb.add(Text("Yes", payload={"cmd": "yes"}), KeyboardButtonColor.POSITIVE)
    kb.add(Text("No", payload={"cmd": "no"}), KeyboardButtonColor.NEGATIVE)
    kb.row()
    kb.add(OpenLink("Website", link="https://vk.com"))
    print(kb.get_json())
"""

from __future__ import annotations

import dataclasses
import json
from enum import Enum
from typing import Any


# ---- Constants -------------------------------------------------------------

MAX_INLINE_ROWS = 6
MAX_INLINE_BUTTONS_PER_ROW = 5
MAX_INLINE_BUTTONS_TOTAL = 10

MAX_REPLY_ROWS = 10
MAX_REPLY_BUTTONS_PER_ROW = 5
MAX_REPLY_BUTTONS_TOTAL = 40

MAX_BUTTON_LABEL = 40
MAX_PAYLOAD_BYTES = 255


class KeyboardButtonColor(Enum):
    """VK keyboard button colors."""
    PRIMARY = "primary"        # Blue — default, main action
    SECONDARY = "secondary"    # White — neutral
    NEGATIVE = "negative"      # Red — destructive/cancel
    POSITIVE = "positive"      # Green — confirm/agree


# ---- Action types ----------------------------------------------------------

class ABCAction:
    """Base class for button actions.

    Subclasses define `type` and additional fields.
    Call `get_data()` to serialize for VK API.
    """
    type: str

    def get_data(self) -> dict[str, Any]:
        data = {k: v for k, v in vars(self).items() if v is not None}
        data["type"] = self.type
        return data


class Text(ABCAction):
    """Text button — sends message to chat with optional payload."""
    type = "text"

    def __init__(self, label: str, payload: str | dict | None = None):
        self.label = str(label)[:MAX_BUTTON_LABEL]
        if payload is not None:
            self.payload = _normalize_payload(payload)


class Callback(ABCAction):
    """Callback button — sends message_event, hides after click."""
    type = "callback"

    def __init__(self, label: str, payload: str | dict | None = None):
        self.label = str(label)[:MAX_BUTTON_LABEL]
        if payload is not None:
            self.payload = _normalize_payload(payload)


class OpenLink(ABCAction):
    """Opens a URL in the browser."""
    type = "open_link"

    def __init__(self, label: str, link: str, payload: str | dict | None = None):
        self.label = str(label)[:MAX_BUTTON_LABEL]
        self.link = link
        if payload is not None:
            self.payload = _normalize_payload(payload)


class Location(ABCAction):
    """Requests user geolocation. Max 2 per row."""
    type = "location"

    def __init__(self, payload: str | dict | None = None):
        if payload is not None:
            self.payload = _normalize_payload(payload)


class VKPay(ABCAction):
    """Opens VK Pay. Must be alone in its row."""
    type = "vkpay"

    def __init__(self, hash_: str, payload: str | dict | None = None):
        self.hash = hash_
        if payload is not None:
            self.payload = _normalize_payload(payload)


class VKApps(ABCAction):
    """Opens a VK Mini App."""
    type = "open_app"

    def __init__(
        self,
        label: str,
        app_id: int,
        owner_id: int,
        hash_: str = "",
        payload: str | dict | None = None,
    ):
        self.label = str(label)[:MAX_BUTTON_LABEL]
        self.app_id = app_id
        self.owner_id = owner_id
        if hash_:
            self.hash = hash_
        if payload is not None:
            self.payload = _normalize_payload(payload)


# ---- Button ----------------------------------------------------------------

@dataclasses.dataclass
class KeyboardButton:
    """A single button: action + color."""
    action: ABCAction
    color: KeyboardButtonColor

    def get_data(self) -> dict[str, Any]:
        return {"action": self.action.get_data(), "color": self.color.value}


# ---- Keyboard builder -----------------------------------------------------

class Keyboard:
    """VK keyboard builder.

    Attributes:
        inline: True = inline (in message), False = reply (below input).
        one_time: If True, keyboard hides after first button press.
    """

    def __init__(self, one_time: bool = False, inline: bool = True):
        self.one_time = one_time
        self.inline = inline
        self.rows: list[list[KeyboardButton]] = [[]]

    @property
    def total_buttons(self) -> int:
        return sum(len(row) for row in self.rows)

    def add(
        self,
        action: ABCAction,
        color: KeyboardButtonColor = KeyboardButtonColor.PRIMARY,
    ) -> Keyboard:
        """Add a button to the current row."""
        self.rows[-1].append(KeyboardButton(action, color))
        return self

    def row(self) -> Keyboard:
        """Start a new row."""
        self.rows.append([])
        return self

    def validate(self) -> list[str]:
        """Validate against VK API limits. Returns list of errors."""
        errors: list[str] = []

        max_rows = MAX_INLINE_ROWS if self.inline else MAX_REPLY_ROWS
        max_per_row = MAX_INLINE_BUTTONS_PER_ROW if self.inline else MAX_REPLY_BUTTONS_PER_ROW
        max_total = MAX_INLINE_BUTTONS_TOTAL if self.inline else MAX_REPLY_BUTTONS_TOTAL

        n_rows = len(self.rows)
        n_total = self.total_buttons

        if n_rows > max_rows:
            errors.append(f"{n_rows} rows exceeds max {max_rows}")
        if n_total > max_total:
            errors.append(f"{n_total} buttons exceeds max {max_total}")

        for i, row in enumerate(self.rows, 1):
            n = len(row)
            if n > max_per_row:
                errors.append(f"Row {i}: {n} buttons exceeds max {max_per_row}")

            # Location constraint: max 2 per row
            n_loc = sum(1 for btn in row if isinstance(btn.action, Location))
            if n_loc > 2:
                errors.append(f"Row {i}: {n_loc} location buttons exceeds max 2")

            # VKPay constraint: must be alone in row
            has_vkpay = any(isinstance(btn.action, VKPay) for btn in row)
            if has_vkpay and n > 1:
                errors.append(f"Row {i}: VKPay must be alone in row (has {n} buttons)")

        return errors

    def get_json(self) -> str:
        """Build the VK keyboard JSON string.

        Returns:
            JSON string for the 'keyboard' parameter of messages.send.
            Empty rows are skipped. Returns empty keyboard JSON if no buttons.
        """
        buttons = []
        for row in self.rows:
            btn_data = [btn.get_data() for btn in row]
            if btn_data:
                buttons.append(btn_data)

        keyboard = {
            "one_time": self.one_time,
            "inline": self.inline,
            "buttons": buttons,
        }

        return json.dumps(keyboard, ensure_ascii=False)

    # Backward-compatible API (old adapter.py uses these)
    def build(self) -> str:
        """Alias for get_json() — backward compat with old VKKeyboard."""
        return self.get_json()

    def add_button(
        self,
        label: str,
        payload: str | dict | None = None,
        color: str = "primary",
        action_type: str = "text",
        link: str | None = None,
        app_id: int | None = None,
        owner_id: int | None = None,
        hash_val: str | None = None,
    ) -> Keyboard:
        """Add a button using old-style flat parameters. Backward compat."""
        color_enum = KeyboardButtonColor(color)

        match action_type:
            case "open_link":
                action = OpenLink(label, link or "", payload=payload)
            case "location":
                action = Location(payload=payload)
            case "vkpay":
                action = VKPay(hash_val or "", payload=payload)
            case "open_app":
                action = VKApps(label, app_id or 0, owner_id or 0, hash_val or "", payload=payload)
            case "callback":
                action = Callback(label, payload=payload)
            case _:
                action = Text(label, payload=payload)

        return self.add(action, color_enum)

    def add_row(self) -> Keyboard:
        """Alias for row() — backward compat with old VKKeyboard."""
        return self.row()

    remove_keyboard = None  # handled by remove_keyboard adapter method


# ---- Helpers ---------------------------------------------------------------

def _normalize_payload(payload: str | dict) -> str:
    """Normalize payload to a VK-compatible JSON string (≤255 bytes)."""
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except (json.JSONDecodeError, TypeError):
            payload = {"command": payload}

    payload_str = json.dumps(payload, ensure_ascii=False)

    if len(payload_str.encode("utf-8")) > MAX_PAYLOAD_BYTES:
        payload_str = json.dumps(str(payload), ensure_ascii=False)[:250]

    return payload_str


def build_empty_keyboard() -> str:
    """Build a keyboard JSON that removes the current keyboard."""
    return json.dumps({"one_time": True, "buttons": []}, ensure_ascii=False)


# ---- Backward compatibility ------------------------------------------------

# Legacy API from old keyboard.py (kept for existing code)
VKKeyboard = Keyboard  # alias
VKKeyboardRow = list  # stub

# Legacy constants
COLOR_PRIMARY = KeyboardButtonColor.PRIMARY.value
COLOR_SECONDARY = KeyboardButtonColor.SECONDARY.value
COLOR_NEGATIVE = KeyboardButtonColor.NEGATIVE.value
COLOR_POSITIVE = KeyboardButtonColor.POSITIVE.value

ACTION_TEXT = "text"
ACTION_CALLBACK = "callback"
ACTION_LOCATION = "location"
ACTION_VKPAY = "vkpay"
ACTION_OPEN_APP = "open_app"
ACTION_OPEN_LINK = "open_link"

# Old build_remove_keyboard (used by adapter.py)
build_remove_keyboard = build_empty_keyboard

# Legacy make/parse helpers
def make_callback_payload(command: str, **extra) -> str:
    """Build a callback payload JSON string."""
    payload = {"command": command, **extra}
    return json.dumps(payload, ensure_ascii=False)


def parse_callback_payload(message: dict) -> str | None:
    """Extract callback payload from a VK message payload."""
    payload_raw = message.get("payload", "")
    if not payload_raw:
        return None
    try:
        payload = json.loads(payload_raw)
        if isinstance(payload, dict):
            return payload.get("command") or payload.get("button") or payload.get("payload") or json.dumps(payload)
        return str(payload)
    except (json.JSONDecodeError, TypeError):
        return str(payload_raw)
