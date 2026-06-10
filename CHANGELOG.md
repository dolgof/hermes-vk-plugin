<!-- fullWidth: false tocVisible: false tableWrap: true -->
# CHANGELOG

## v1.2.0 (2026-06-03)

### Changed

- **Native Markdown formatting via `format_data`** — no more Unicode hacks!
  - `**bold**`, `*italic*`, `<u>underline</u>`, `[text](url)`, `***nested***`
  - `_format_content_raw()` returns `(plain_text, format_data_json)`
  - `format_data` JSON passed directly to `messages.send`, `messages.edit`
  - `send_keyboard()` and `_send_file_attachment()` captions also support format_data
  - `_apply_unicode_styling()` and Unicode maps marked as DEPRECATED (kept for compat)
  - `format_message()` now strips Markdown markers only — no character substitution
- Updated `platform_hint` to describe native formatting

### Added

- `_format_content_raw()` method returning `(plain_text, format_data)` tuple

## v1.1.0 (2026-06-03)

### Added

- **Markdown → VK formatting** (`format.py`): bold, italic, code, links, headers, lists, blockquotes, fenced code blocks, HTML sanitization
- **Inline Keyboard** (`keyboard.py`): VKKeyboard builder (10×4 buttons), `send_keyboard()`, `remove_keyboard()`, callback payload parsing
- **Access policies** (`policy.py`):
  - `dmPolicy`: open, allowlist, pairing (challenge code), disabled
  - `groupPolicy`: open, allowlist, disabled
  - `requireMention`: @mention requirement in group chats
- **Multi-account**: support for multiple community tokens with independent Long Poll loops
- **Media download** (`media.py`): inbound attachment download (photo, doc, audio, video, sticker, graffiti) to local cache
- **Image URL → attachment**: `send_image()` now downloads URLs and uploads as VK photos
- **Message editing/deletion**: `edit_message()`, `delete_message()` via VK API
- **Health probe**: `probe()` method returning `{ok, group_id, ts, ...}`
- **Rate limiter** (`ratelimit.py`): token-bucket throttling for send (5rps/20burst), api (3/5), upload (1/2), download (5/10)
- **tokenFile**: reading token from file (Docker secrets support)
- **Config schema**: `plugin.yaml` now documents all configuration parameters

### Changed

- `send()` now applies `format_vk_message()` automatically
- `VK_ALLOWED_USERS` / `VK_ALLOW_ALL_USERS` legacy env vars still supported
- `platform_hint` updated: messages support basic formatting
- Improved error resilience: fallback chains for image upload, scope-denied recovery

### Fixed

- `chat_type` duplicate determination in `_process_update` (was causing KeyError)
- `_send_semaphore` replaced with proper token-bucket rate limiter

## v1.0.0 (Initial)

- Basic VK Long Poll connection with watchdog
- Text sending/receiving
- Image file upload via `photos.getMessagesUploadServer`
- Document upload via `docs.getMessagesUploadServer`
- Forwarded message formatting
- Long Poll failure recovery (exponential backoff + long-recovery mode)
- Telegram + VK notifications for errors/recovery