# VK Plugin for Hermes Agent

![VK Logo](https://upload.wikimedia.org/wikipedia/commons/2/21/VK.com-logo.svg){width=162}

Плагин для [Hermes Agent](https://github.com/nousresearch/hermes), подключающий AI-агента к сообществам [VK](https://vk.com) через Bots Long Poll API.

Бот принимает и отвечает на сообщения в личных диалогах и групповых беседах, поддерживает нативное форматирование VK (format_data), inline-клавиатуры, загрузку вложений и гибкие политики доступа.

---

## Содержание

- [Возможности](#возможности)
- [Требования](#требования)
- [Установка](#установка)
- [Конфигурация](#конфигурация)
- [Публичный API](#публичный-api)
- [Inline-клавиатуры](#inline-клавиатуры)
- [Текстовое форматирование](#текстовое-форматирование)
- [Политики доступа](#политики-доступа)
- [Multi-account](#multi-account)
- [Разработка](#разработка)
- [Лицензия](#лицензия)

---

## Возможности

### 📨 Сообщения

- **Текст** с нативным форматированием VK (format_data): **жирный**, *курсив*, <u>подчёркнутый</u>, [ссылки](url), ***вложенные*** стили
- **Inline-клавиатура** — до 10 строк × 4 кнопки (callback / text / open_link / location / vkpay / open_app)
- **Reply** — ответы с цитированием
- **Typing indicator** — индикатор набора текста
- **Редактирование и удаление** отправленных сообщений через `messages.edit` / `messages.delete`

### 🖼️ Медиа

- **Фото** — загрузка через `photos.getMessagesUploadServer` + fallback на текст
- **Фото по URL** — скачивание → загрузка как вложение
- **Документы** — загрузка через `docs.getMessagesUploadServer`
- **Входящие вложения** — авто-скачивание в кэш для анализа AI (фото, документы, аудио, видео, стикеры, граффити)

### 🔐 Политики доступа

| dmPolicy    | Описание                                  |
| ----------- | ----------------------------------------- |
| `open`      | Все могут писать в ЛС                     |
| `allowlist` | Только пользователи из `allowFrom`        |
| `pairing`   | Код-подтверждение для новых пользователей |
| `disabled`  | ЛС отключены                              |

| groupPolicy | Описание                 |
| ----------- | ------------------------ |
| `open`      | Все участники чата       |
| `allowlist` | Только `groupAllowFrom`  |
| `disabled`  | Групповые чаты отключены |

`requireMention` — требовать @упоминание бота в беседах.

### 👥 Multi-account

- Несколько сообществ VK на одном экземпляре
- Каждый аккаунт со своими политиками и токеном

### 🛡️ Надёжность

- **Watchdog** — перезапуск Long Poll при падении
- **Экспоненциальный backoff** — при ошибках соединения
- **Long-recovery mode** — проверка каждые 5 минут при недоступности
- **Token bucket rate limiter** — троттлинг для send/api/upload/download
- **Уведомления** в Telegram + VK при проблемах

---

## Требования

- [Hermes Agent](https://github.com/nousresearch/hermes) v1.0+
- Python 3.11+
- `httpx` (устанавливается автоматически)
- Токен сообщества VK с правами: `messages`, `manage`, `photos`, `docs`

---

## Установка

### Вручную

```bash
# Клонировать репозиторий
git clone https://github.com/dolgof/hermes-vk-plugin
cd hermes-vk-plugin

# Скопировать в директорию плагинов
cp -r vk /opt/data/plugins/vk

# Зависимости
pip install httpx

# Перезапустить gateway
# docker compose restart <container_name>
```

### Через переменные окружения

```bash
export VK_GROUP_TOKEN="vk1.a.xxxxx..."
```

---

## Конфигурация

### Минимальная (один аккаунт)

```yaml
# plugin.yaml или config.extra
vk:
  token: "vk1.a.xxxxx..."
  dmPolicy: "open"
```

### Через переменные окружения (legacy)

```bash
VK_GROUP_TOKEN="vk1.a.xxxxx..."
VK_ALLOW_ALL_USERS=true
```

### Multi-account

```yaml
vk:
  accounts:
    default:
      token: "vk1.a.xxxxx..."
      dmPolicy: "open"
    sales:
      token: "vk1.a.yyyyy..."
      dmPolicy: "allowlist"
      allowFrom: ["12345", "67890"]
    support:
      tokenFile: "/run/secrets/vk-support.token"
      dmPolicy: "pairing"
      groupPolicy: "open"
```

### Полная конфигурация

```yaml
vk:
  token: "vk1.a.xxxxx..."
  api_version: "5.199"

  # Политики
  dmPolicy: "open"           # open | allowlist | pairing | disabled
  allowFrom: ["*"]           # список user_id или ["*"] для всех
  groupPolicy: "open"        # open | allowlist | disabled
  groupAllowFrom: ["*"]
  requireMention: false      # @упоминание в беседах
  botName: "My Bot"          # имя для @mention детекции

  # Токен из файла (Docker secrets)
  tokenFile: "/run/secrets/vk-token"
```

---

## Публичный API плагина

| Функция/Метод                                     | Описание                              |
| ------------------------------------------------- | ------------------------------------- |
| `VKAdapter`                                       | Основной адаптер платформы            |
| `format_vk_message(text)`                         | Markdown → VK текст (legacy)          |
| `parse_markdown(text)`                            | Markdown → Format tree                |
| `markdown_format_data(text)`                      | Markdown → (plain_text, format_data)  |
| `VKKeyboard(one_time, inline)`                    | Билдер клавиатуры                     |
| `check_dm_policy(user_id, dm_policy, allow_from)` | Проверка DM политики                  |
| `check_group_policy(user_id, ...)`                | Проверка групповой политики           |
| `issue_pairing_challenge(user_id)`                | Выпуск pairing-кода                   |
| `validate_pairing_code(user_id, code)`            | Проверка pairing-кода                 |
| `download_vk_attachments(client, attachments)`    | Скачивание вложений                   |

### Методы VKAdapter

| Метод                                        | Описание                   |
| -------------------------------------------- | -------------------------- |
| `send(chat_id, content, reply_to)`           | Отправить текст            |
| `send_keyboard(chat_id, content, keyboard)`  | Отправить с клавиатурой    |
| `remove_keyboard(chat_id, content)`          | Удалить клавиатуру         |
| `send_image(chat_id, image_url, caption)`    | Отправить изображение      |
| `send_image_file(chat_id, image_path)`       | Отправить файл изображения |
| `send_document(chat_id, file_path, caption)` | Отправить документ         |
| `edit_message(chat_id, msg_id, content)`     | Редактировать сообщение    |
| `delete_message(chat_id, msg_id)`            | Удалить сообщение          |
| `probe()`                                    | Health check               |
| `get_chat_info(chat_id)`                     | Информация о чате          |

---

## Inline-клавиатуры

VK поддерживает inline-клавиатуры — кнопки под сообщением. Поддерживается до **10 строк × 4 кнопки**, до **40 символов** на кнопку, до **255 байт** payload.

### Типы кнопок

| Тип           | action_type    | Описание                                                          |
|---------------|----------------|-------------------------------------------------------------------|
| **Текст**     | `text`         | Отправляет callback-текст боту. Требует payload.                  |
| **Callback**  | `callback`     | Аналог text, но кнопка скрывается после нажатия. Требует payload. |
| **Ссылка**    | `open_link`    | Открывает URL в браузере. Не требует payload. Требует `link`.     |
| **Приложение**| `open_app`     | Открывает VK Mini App. Требует `app_id`, `owner_id`, `hash`.     |
| **Локация**   | `location`     | Запрашивает геолокацию пользователя.                              |
| **VK Pay**    | `vkpay`        | Открывает платёж VK Pay.                                          |

### Цвета кнопок

| color       | Вид      | Назначение          |
|-------------|----------|---------------------|
| `primary`   | Синяя    | Основное действие   |
| `secondary` | Белая    | Нейтральное         |
| `positive`  | Зелёная  | Подтверждение       |
| `negative`  | Красная  | Отмена / Удаление   |

### Использование `Keyboard` из кода адаптера

```python
from vk.keyboard import Keyboard, Text, OpenLink, KeyboardButtonColor

# Создаём клавиатуру
kb = Keyboard(inline=True)
kb.add(Text("✅ Да", payload={"cmd": "yes"}), KeyboardButtonColor.POSITIVE)
kb.add(Text("❌ Нет", payload={"cmd": "no"}), KeyboardButtonColor.NEGATIVE)
kb.row()
kb.add(OpenLink("🔗 Сайт", link="https://example.com"))

# Отправить с клавиатурой
await adapter.send_keyboard(chat_id, "Выберите действие:", kb)

# Или через send() с метаданными
await adapter.send(chat_id, "Выберите:", metadata={"keyboard": kb})

# Удалить клавиатуру
await adapter.remove_keyboard(chat_id)
```

### Встраивание в текст сообщения

Агент может отправить клавиатуру через обычный `send_message`, вставив `[[keyboard:...]]` в текст. Плагин VK автоматически распознаёт маркер:

```python
"Выберите действие: [[keyboard:{\"buttons\":[[{\"action\":{\"type\":\"text\",\"label\":\"✅ Да\"},\"color\":\"positive\"},{\"action\":{\"type\":\"text\",\"label\":\"❌ Нет\"},\"color\":\"negative\"}]],\"inline\":true}]]"
```

### Callback-обработка

VK отправляет нажатие кнопки двумя способами:

| Тип кнопки | Событие VK          | Как обрабатывается                                             |
|------------|---------------------|---------------------------------------------------------------|
| `text`     | `message_new` + `payload` | Парсится в `_process_update`, текст заменяется на `/vk_<command>` |
| `callback` | `message_event`           | `_process_callback_event` → создаёт `/vk_callback:<command>`   |

```python
from vk.keyboard import make_callback_payload, parse_callback_payload

# Создание payload для кнопки
payload = make_callback_payload("confirm", item_id=42)

# Парсинг входящего payload (из message_new)
command = parse_callback_payload(incoming_message)
# → возвращает "confirm" или None
```

Для `callback`-кнопок (`message_event`) адаптер автоматически:
1. Отвечает на событие (acknowledge) — VK не показывает ошибку
2. Создаёт виртуальное сообщение `/vk_callback:confirm {"item_id":42, ...}`
3. Диспатчит через `handle_message()` — шлюз обрабатывает как команду

### Ограничения VK API

| Параметр               | Лимит                    |
|------------------------|--------------------------|
| Строк (рядов)          | ≤ **10**                 |
| Кнопок в строке        | ≤ **4**                  |
| Длина текста кнопки    | ≤ **40** символов        |
| Размер payload         | ≤ **255** байт (JSON)    |
| Всего кнопок           | ≤ **40**                 |

---

## Текстовое форматирование

VK API поддерживает нативное форматирование через параметр `format_data`. Плагин автоматически конвертирует Markdown в format_data:

| Markdown           | VK format_data              |
|--------------------|-----------------------------|
| `**жирный**`       | bold span                   |
| `*курсив*`         | italic span                 |
| `<u>подчёркнутый</u>` | underline span           |
| `***жирный курсив***` | bold + italic (вложенные) |
| `[текст](url)`     | clickable link              |
| `\\*экранировано\\*`  | literal asterisks        |

Плагин также включает **legacy-модуль** `format.py` для конвертации Markdown → plain text (использовался до обнаружения format_data). Он сохранён для обратной совместимости.

```python
from vk.markdown_vk import markdown_format_data

plain_text, format_data_json = markdown_format_data("**Привет**, *мир*!")
# plain_text = "Привет, мир!"
# format_data_json = '{"version":1,"items":[{"type":"bold","offset":0,"length":6}]}'
```

**Важно:** Все смещения (offset/length) в format_data считаются в UTF-16 code units. Для ASCII и кириллицы это совпадает с длиной строки, но для эмодзи (🔥 → 2 units) необходимо учитывать разницу.

---

## Политики доступа

### DM Policy

Плагин поддерживает четыре режима доступа к личным сообщениям:

- **`open`** — все могут писать
- **`allowlist`** — только пользователи из списка `allowFrom`
- **`pairing`** — код-подтверждение (challenge-response)
- **`disabled`** — ЛС отключены

### Group Policy

- **`open`** — все участники чата
- **`allowlist`** — только из `groupAllowFrom`
- **`disabled`** — групповые чаты отключены

### Pairing (код-подтверждение)

Режим `pairing` генерирует 6-значный код при первом сообщении от пользователя.
Код действителен 5 минут. После успешного подтверждения пользователь попадает в белый список до перезапуска.

```python
from vk.policy import (
    issue_pairing_challenge,
    validate_pairing_code,
    revoke_pairing,
)

code = issue_pairing_challenge("12345")
# → "483291"

if validate_pairing_code("12345", "483291"):
    print("Пользователь подтверждён")
```

---

## Multi-account

Плагин поддерживает несколько сообществ VK на одном экземпляре. Каждый аккаунт имеет собственный:
- Токен доступа (из конфига, переменной окружения или файла)
- Long Poll соединение (независимый цикл опроса)
- Политики доступа (dmPolicy, groupPolicy)
- Уровень троттлинга (разделяемые rate limiters)

```yaml
vk:
  accounts:
    default:
      token: "vk1.a.xxxxx..."
      dmPolicy: "open"
    support:
      tokenFile: "/run/secrets/vk-support-token"
      dmPolicy: "pairing"
```

В multi-account режиме токен из корневого `vk.token` игнорируется — используются только `accounts`.

---

## Структура проекта

```text
vk/
├── __init__.py          # Публичный API
├── adapter.py           # Основной адаптер VK (Long Poll, Messaging)
├── markdown_vk.py       # Markdown → format_data парсер (stack-based tokenizer)
├── format_data.py       # Format tree / VK format_data builder
├── format.py            # Markdown → VK текст (legary, DEPRECATED)
├── keyboard.py          # Inline-клавиатура (Keyboard / VKKeyboard)
├── callback_response.py # Модели ответов на callback (ShowSnackbar, OpenLink, OpenApp)
├── media.py             # Скачивание вложений
├── policy.py            # Политики доступа (dmPolicy, groupPolicy, pairing)
├── ratelimit.py         # Rate limiter (token bucket)
├── plugin.yaml          # Метаданные плагина
├── README.md
├── CHANGELOG.md
├── LICENSE
├── .gitignore
├── .env.example
└── config.example.yaml
```

---

## Благодарности

Этот плагин использует дизайн и архитектурные решения из следующих Open Source проектов:

### vkbottle

Фреймворк [vkbottle](https://github.com/vkbottle/vkbottle) (MIT License) послужил источником вдохновения для модулей:

- `markdown_vk.py` — stack-based Markdown → format_data парсер (на основе `markdown_parser.py`)
- `format_data.py` — Format tree для format_data (на основе `tools/formatting.py`)
- `keyboard.py` — иерархия действий и билдер клавиатуры (на основе `tools/keyboard/`)
- `callback_response.py` — модели ответов на callback (на основе `tools/event_data.py`)

```
MIT License

Copyright (c) 2019 timoniq
Copyright (c) 2022-2024 feeeek (Axd1x8a)
Copyright (c) 2024 luwqz1

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

---

## Разработка

```bash
# Клонировать
git clone https://github.com/dolgof/hermes-vk-plugin
cd hermes-vk-plugin

# Зависимости
pip install httpx

# Линтер
pip install ruff
ruff check .
```

### Тестирование

```bash
# Прямой вызов VK API для проверки
curl -s "https://api.vk.com/method/groups.getById" \
  -d "access_token=$VK_GROUP_TOKEN" \
  -d "v=5.199"
```

---

## Лицензия

MIT License. См. [LICENSE](LICENSE).

Copyright (c) 2026 Hermes Agent VK Plugin Contributors
