"""
Callback response models for VK message_event answers.

When a user clicks a callback button, the bot must answer the
message_event via messages.sendMessageEventAnswer.  The answer can
include event_data to trigger client-side actions without sending
a new message:

  - ShowSnackbar   — disappearing toast notification (10 sec, ≤90 chars)
  - OpenLink       — open a URL in the browser
  - OpenApp        — open a VK Mini App

Reference: vkbottle tools/event_data.py

vkbottle is MIT-licensed:
  Copyright (c) 2019 timoniq
  Copyright (c) 2022-2024 feeeek (Axd1x8a)
  Copyright (c) 2024 luwqz1
  https://github.com/vkbottle/vkbottle/blob/master/LICENSE
"""

from __future__ import annotations

import dataclasses
import json


@dataclasses.dataclass
class ShowSnackbar:
    """Show a disappearing notification (toast).

    Appears for 10 seconds, user can swipe to dismiss.
    Max text length: 90 characters.
    """
    text: str
    type: str = "show_snackbar"

    def __post_init__(self) -> None:
        if len(self.text) > 90:
            self.text = self.text[:87] + "..."

    def as_data(self) -> dict:
        return {"type": self.type, "text": self.text}

    def as_json(self) -> str:
        return json.dumps(self.as_data(), ensure_ascii=False)


@dataclasses.dataclass
class OpenLink:
    """Open a URL in the user's browser."""
    link: str
    type: str = "open_link"

    def as_data(self) -> dict:
        return {"type": self.type, "link": self.link}

    def as_json(self) -> str:
        return json.dumps(self.as_data(), ensure_ascii=False)


@dataclasses.dataclass
class OpenApp:
    """Open a VK Mini App."""
    app_id: int
    owner_id: int
    hash: str = ""
    type: str = "open_app"

    def as_data(self) -> dict:
        data = {"type": self.type, "app_id": self.app_id, "owner_id": self.owner_id}
        if self.hash:
            data["hash"] = self.hash
        return data

    def as_json(self) -> str:
        return json.dumps(self.as_data(), ensure_ascii=False)
