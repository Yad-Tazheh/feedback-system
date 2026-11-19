# Feedback System

A Django 6.1 web app where users open conversations (requests, criticisms or suggestions) and get AI replies from a local model served by [LM Studio](https://lmstudio.ai/). When a user asks for a human, an expert can take over the chat, and the AI stays silent until the expert releases it.

The UI is in Persian. The code, settings and this README are in English.

## Features

- **Conversations and messages**: each conversation has a type (request, criticism, suggestion), a title and an ordered list of messages.
- **AI replies**: the app sends the conversation history to an OpenAI-compatible `chat/completions` endpoint (LM Studio). Failed calls are stored as failed messages, not lost.
- **Token usage tracking**: prompt, completion, cached and total tokens are stored on each assistant message when the provider reports them. They are never invented.
- **AI usage page**: per-user totals and OK/failed counts.
- **Accounts**: sign up, log in, log out (POST only). Each user sees only their own conversations; other IDs return 404.
- **Expert role**: members of the `experts` group get a queue of waiting chats, can claim one, answer it, release it back to the AI, or close it.
- **Staff**: staff users can see all conversations, close any open one, and use the Django admin.
- **Settings split**: `dev` and `prod` settings modules.

## Quick start

Requirements: [uv](https://docs.astral.sh/uv/). The Python version (3.14) is pinned in `.python-version`.

```bash
uv sync
cp .env.example .env            # on Windows: copy .env.example .env
uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Open http://127.0.0.1:8000/ and sign up, or log in with the superuser.

## LM Studio setup

1. Load a chat model in LM Studio (the example config uses `qwen2.5-7b-instruct`).
2. Start the local server (default port 1234).
3. Set `LM_STUDIO_URL` to the full chat endpoint, for example `http://localhost:1234/v1/chat/completions`, and `LM_MODEL` to the model id.

If LM Studio is down, the conversation is still saved and the failure is recorded on the message.

## Environment variables

Values come from `.env.example`, `feedback_system/settings/*.py` and `feedbacks/services/ai_service.py`.

| Variable | Default | Purpose |
|---|---|---|
| `LM_STUDIO_URL` | none (required) | Full chat completions URL |
| `LM_MODEL` | none (required) | Model id sent to LM Studio |
| `LM_TEMPERATURE` | `0.4` | Sampling temperature |
| `LM_MAX_TOKENS` | `150` | Max tokens per reply |
| `LM_TIMEOUT` | `60` | Request timeout in seconds |
| `DJANGO_SETTINGS_MODULE` | `feedback_system.settings.dev` (set in `manage.py`) | Settings module to use |
| `DJANGO_SECRET_KEY` | dev fallback in `dev`; required in `prod` | Django secret key |
| `DJANGO_ALLOWED_HOSTS` | empty (prod only; `dev` always uses `localhost,127.0.0.1`) | Comma-separated host names (prod) |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | empty (prod only) | Comma-separated origins (prod) |
| `DJANGO_SECURE_SSL_REDIRECT` | `True` (prod only) | Redirect HTTP to HTTPS (prod) |
| `DJANGO_SECURE_HSTS_SECONDS` | `31536000` (prod only) | HSTS max-age (prod) |
| `DJANGO_EMAIL_BACKEND` | `django.core.mail.backends.smtp.EmailBackend` (prod only) | Email backend read by `prod.py` |
| `DJANGO_LOG_LEVEL` | `INFO` | Log level for the `feedbacks` logger |
| `DJANGO_DB_PATH` | `db.sqlite3` in the project root | SQLite file path |

Note: only the AI service loads `.env` (through python-dotenv). Django settings read real environment variables, so export the `DJANGO_*` values in your shell or process manager instead of relying on `.env`.

## Roles and conversation states

| Role | Who | Can |
|---|---|---|
| Visitor | not logged in | sign up, log in |
| Owner | any logged-in user, for their own chats | create, edit, delete own chats; post; request an expert while the chat is `ai` |
| Expert | member of the `experts` group | see the queue; claim unassigned waiting chats (not their own); post in chats they hold; release; close their chats |
| Staff | `is_staff` | see all chats; close any open chat; admin site |

| State | Meaning | AI replies? |
|---|---|---|
| `ai` | AI answers user messages | yes |
| `waiting_expert` | in the expert queue | no |
| `expert_active` | an expert holds the chat | no |
| `closed` | terminal, no new messages | no |

Transitions: `ai` to `waiting_expert` (owner asks, or a message starts with `@expert`); `waiting_expert` to `expert_active` (expert claims); `expert_active` to `ai` (assigned expert releases); any open state to `closed` (staff or assigned expert). Invalid transitions raise a `ValidationError`.

To make a user an expert, add them to the `experts` group in the Django admin (`/admin/`). The group is created by a migration.

## URLs

Project (`feedback_system/urls.py`):

| Path | Name / target |
|---|---|
| `admin/` | Django admin |
| `accounts/signup/` | `signup` (sign-up view) |
| `accounts/` | Django auth URLs (`login/`, `logout/`, password views) |
| `` | app URLs below |

App (`feedbacks/urls.py`):

| Path | Name | Purpose |
|---|---|---|
| `` | `feedback_list` | Own conversations |
| `create/` | `feedback_create` | New conversation with first message |
| `update/<pk>/` | `feedback_update` | Edit type and title (owner) |
| `delete/<pk>/` | `feedback_delete` | Delete conversation (owner) |
| `c/<pk>/` | `conversation_detail` | View and post messages |
| `c/<pk>/request-expert/` | `conversation_request_expert` | POST: ask for an expert |
| `c/<pk>/claim/` | `conversation_claim` | POST: expert claims |
| `c/<pk>/release/` | `conversation_release` | POST: expert releases to AI |
| `c/<pk>/close/` | `conversation_close` | POST: close |
| `expert/` | `expert_queue` | Expert queue (experts and staff) |
| `usage/` | `ai_usage` | Own AI token usage |

## Running tests

```bash
uv run python manage.py test
```

Tests mock the AI calls, so LM Studio does not need to run.

## Production notes

- Set `DJANGO_SETTINGS_MODULE=feedback_system.settings.prod`. `wsgi.py` and `asgi.py` already default to it.
- Required: `DJANGO_SECRET_KEY` (the app refuses to start without it). Also set `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` for your domain.
- Prod enables `DEBUG=False`, HTTPS redirect, secure cookies, HSTS, and trusts `X-Forwarded-Proto`. Run the app behind a reverse proxy that terminates TLS and overwrites that header. For local HTTP testing set `DJANGO_SECURE_SSL_REDIRECT=False`.
- Run `uv run python manage.py check --deploy` before going live.
- Run `uv run python manage.py collectstatic`. Static files go to `staticfiles/`; the proxy must serve `/static/` (no WhiteNoise is installed).
- The database is SQLite (`DJANGO_DB_PATH`). Keep it on a persistent volume.

## Project structure

```
.env.example
.python-version
README.md
ROADMAP.md
design.md
manage.py
pyproject.toml
uv.lock
config/prompts/feedback_response.txt     # system prompt for AI replies
feedback_system/                         # project package
    settings/base.py, dev.py, prod.py
    urls.py, wsgi.py, asgi.py
feedbacks/                               # main app
    models.py          # Conversation, Message
    views.py           # class-based views
    urls.py
    permissions.py     # object-level rules (can_view, can_claim, ...)
    forms.py, admin.py
    services/ai_service.py   # HTTP client for LM Studio
    services/replies.py      # create_ai_reply: persists ok/failed replies
    migrations/        # 0001 to 0009
    tests.py
src/01_feedback_system/__init__.py       # package entry point from pyproject
templates/feedbacks/                     # app pages
templates/registration/                  # login, signup, logout pages
```

## Docs

- [ROADMAP.md](ROADMAP.md): sprint goals and review notes.
- [design.md](design.md): design decisions for each sprint.

## Built with

Built in co-op with Fable 5.2: AI pair-programming, with every change reviewed and tested in CI.
