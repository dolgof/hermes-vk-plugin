"""VK Messenger platform adapter for Hermes Agent."""
from .adapter import VKAdapter, check_requirements, validate_config, register

# Stage 1 improvements — submodule API
from .markdown_vk import parse_markdown, markdown_to_plain, markdown_format_data, extract_keyboard_marker
from .format_data import Format, bold, italic, underline, url
from .keyboard import (
    VKKeyboard,
    VKKeyboardRow,
    build_remove_keyboard,
    make_callback_payload,
    parse_callback_payload,
)
from .policy import (
    check_dm_policy,
    check_group_policy,
    issue_pairing_challenge,
    validate_pairing_code,
    get_pairing_message,
    is_awaiting_pairing,
    revoke_pairing,
)
from .media import download_vk_attachments, download_vk_image_by_url
from .callback_response import ShowSnackbar, OpenLink, OpenApp
