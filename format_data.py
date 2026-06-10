"""
VK native text formatting via format_data parameter.

VK API messages.send accepts format_data — a JSON structure describing
formatted spans (bold, italic, underline, url) within the plain message text.
This is the NATIVE VK formatting mechanism, used by vkbottle framework.

IMPORTANT: All offsets are in UTF-16 code units, not Python characters!
For emoji (🔥) and some special chars, UTF-16 units ≠ len(text).

Reference: https://dev.vk.ru/en/reference/objects/message#format_data
Inspired by: https://github.com/vkbottle/vkbottle (tools/formatting.py)

vkbottle is MIT-licensed:
  Copyright (c) 2019 timoniq
  Copyright (c) 2022-2024 feeeek (Axd1x8a)
  Copyright (c) 2024 luwqz1
  https://github.com/vkbottle/vkbottle/blob/master/LICENSE
"""

from __future__ import annotations

import dataclasses
import json
from typing import Any


FormatType = str  # "bold" | "italic" | "underline" | "url"


def _utf16_offset(text: str) -> int:
    """Count UTF-16 code units in a string.

    VK format_data uses UTF-16 code units for offset/length, NOT Python
    character count.  For ASCII and Cyrillic these are the same, but for
    emoji (🔥), some special chars, and surrogate pairs they differ.

    Examples:
        _utf16_offset("Hello") == 5       # ASCII: 1 unit per char
        _utf16_offset("Привет") == 6      # Cyrillic: 1 unit per char
        _utf16_offset("🔥") == 2          # Emoji: 2 units (surrogate pair)
    """
    return len(text.encode("utf-16-le")) // 2


def _format(
    string: str | Format,
    fmt_type: FormatType,
    data: dict[str, Any] | None = None,
    /,
) -> Format:
    """Create a Format object, preserving nested formatting."""
    data = data or {}
    if isinstance(string, Format):
        return Format(string.string, type=fmt_type, data=data, other_formats=[string])
    return Format(string, type=fmt_type, data=data)


def bold(string: str | Format, /) -> Format:
    """Wrap text in bold formatting."""
    return _format(string, "bold")


def italic(string: str | Format, /) -> Format:
    """Wrap text in italic formatting."""
    return _format(string, "italic")


def underline(string: str | Format, /) -> Format:
    """Wrap text in underline formatting."""
    return _format(string, "underline")


def url(string: str | Format, /, *, href: str) -> Format:
    """Wrap text in a clickable link."""
    return _format(string, "url", {"url": href})


@dataclasses.dataclass
class Format:
    """A formatted span within a VK message.

    Supports nesting: other_formats contains inner Format objects that
    apply to substrings of this span.

    When type is None, this is a container — it has no formatting of its own
    and acts purely as a holder for sibling other_formats.

    Attributes:
        string: The plain text content.
        type: "bold", "italic", "underline", "url", or None for containers.
        offset: Position in the full message (UTF-16 code units).
        length: Length of this span (UTF-16 code units).
        data: Extra data (e.g. {"url": "https://..."} for links).
        other_formats: Nested inner formats (e.g. *italic* inside **bold**)
                       or sibling formats for a container.
    """

    string: str
    type: FormatType | None
    offset: int = 0
    length: int = 0
    data: dict[str, Any] = dataclasses.field(default_factory=dict)
    other_formats: list[Format] = dataclasses.field(default_factory=list)

    def __post_init__(self) -> None:
        self.offset = 0
        self.length = _utf16_offset(self.string)

    def __str__(self) -> str:
        return self.string

    def __add__(self, other: object, /) -> Format:
        if not isinstance(other, (str, Format)):
            return NotImplemented
        if isinstance(other, str):
            # Append plain text — mutates this span's string
            self.string += other
            self.length = _utf16_offset(self.string)
            return self
        return self._concat(other)

    def __radd__(self, other: object, /) -> Format:
        if not isinstance(other, str):
            return NotImplemented
        rhs_offset = _utf16_offset(other)
        self.offset += rhs_offset
        self._add_offset_recursive(self.other_formats, rhs_offset)
        self.string = other + self.string
        self.length = _utf16_offset(self.string)
        return self

    def _add_offset_recursive(self, formats: list[Format], delta: int) -> None:
        for fmt in formats:
            fmt.offset += delta
            self._add_offset_recursive(fmt.other_formats, delta)

    def _concat(self, other: Format) -> Format:
        """Concatenate another Format after this one.

        Both formats become siblings inside a new container, preserving
        their independent formatting ranges. This avoids overlapping
        format_data items that VK API rejects.
        """
        parts: list[str | Format] = [self, other]
        return Format.container(parts)

    def as_data(self, *, offset: int = 0) -> dict[str, Any]:
        """Serialize this Format (and nested formats) to format_data JSON.

        Returns a dict suitable for json.dumps() and passing as the
        format_data parameter to messages.send.
        """
        items: list[dict[str, Any]] = []

        # Container (type=None) has no own item — flatten children only
        if self.type is not None:
            items.append({
                "type": self.type,
                "offset": self.offset + offset,
                "length": self.length,
                **self.data,
            })

        # Nested formats inherit parent offset — they are relative to parent
        parent_offset = self.offset + offset
        for fmt in self.other_formats:
            nested = fmt.as_data(offset=parent_offset)
            items.extend(nested["items"])

        return {"version": 1, "items": items}

    def as_raw_data(self, *, offset: int = 0) -> str:
        """Serialize to JSON string for messages.send."""
        return json.dumps(self.as_data(offset=offset), ensure_ascii=False)

    @staticmethod
    def container(parts: list[str | Format]) -> Format:
        """Build a container Format that holds sibling formatted spans.

        Takes a list of mixed str/Format pieces and produces a single Format
        whose other_formats contain all independent Format objects at the
        same level (no wrapping span). The resulting type is None (container).

        Example:
            Format.container(["text ", bold("bold"), " ", italic("italic")])
            → Format(string="text bold italic", type=None,
                      other_formats=[bold(0-5), italic(7-13)])
        """
        if not parts:
            return Format("", type=None)

        # Build the full string and collect Format objects with their offsets
        full = ""
        formats: list[Format] = []
        for p in parts:
            if isinstance(p, str):
                full += p
            else:
                # Adjust Format offset to its position in the full string
                p.offset = _utf16_offset(full)
                p.string = p.string  # keep original string
                formats.append(p)
                full += p.string

        container = Format(full, type=None, other_formats=formats)
        return container
