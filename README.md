# 🤖 Feedback System

A Django-based feedback management system with AI-powered responses using **LM Studio** and local LLM models.

Users can submit:

- ✅ Requests
- ❌ Criticism
- 💡 Suggestions

The system automatically generates a response using a local AI model and stores the generated response with the feedback.

---

## ✨ Features

- Django web application
- Feedback management (Create, Read, Update, Delete)
- AI-generated responses using local LLM
- LM Studio API integration
- Environment-based configuration
- SQLite database (development)
- Ready for future PostgreSQL deployment

---

# 🚀 Installation

## 1. Clone Repository

```bash
git clone <repository-url>

cd 01-feedback-system
```

---

## 2. Install Dependencies

This project uses **uv** for package management.

Install dependencies:

```bash
uv sync
```

---

# 🔐 Environment Configuration

Copy the provided `.env.example` template to `.env` in the project root:

```bash
cp .env.example .env
```

All configurable environment variables are documented in `.env.example`:

- **AI Service:** `LM_STUDIO_URL`, `LM_MODEL`, `LM_TEMPERATURE`, `LM_MAX_TOKENS`, `LM_TIMEOUT`
- **Django Settings:** `DJANGO_SETTINGS_MODULE` (`feedback_system.settings.dev` for development, `feedback_system.settings.prod` for production)
- **Production Secrets:** `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`
- **Logging & Storage:** `DJANGO_LOG_LEVEL`, `DJANGO_DB_PATH`, `DJANGO_SECURE_SSL_REDIRECT`

---

# 🧠 AI Model Setup (LM Studio)

This project uses LM Studio as a local AI server.

## 1. Install LM Studio

Download and install:

https://lmstudio.ai/

---

## 2. Download a Model

Recommended models:

```
Qwen2.5-7B-Instruct-GGUF
```

or other compatible instruction models.

---

## 3. Load the Model

Open LM Studio:

```
Developer → Load Model
```

Load your downloaded model.

---

## 4. Start Local Server

Enable LM Studio API server:

```
http://localhost:1234
```

The API endpoint:

```
http://localhost:1234/v1/chat/completions
```

---

## 5. Set Model Name

Copy the model identifier shown by LM Studio.

Example:

```env
LM_MODEL=qwen2.5-7b-instruct
```

---

# 🗄 Database Setup

Run migrations:

```bash
uv run python manage.py migrate
```

Create admin account:

```bash
uv run python manage.py createsuperuser
```

---

# ▶️ Run Project

Start Django server:

```bash
uv run python manage.py runserver
```

Open:

```
http://127.0.0.1:8000/
```

Create an account at `/accounts/signup/` or log in at `/accounts/login/`.

---

# 🏗 Project Architecture

```
User
 |
 v
Django Views
 |
 v
Conversation & Message Models
 |
 v
Replies Service & AIService
 |
 v
LM Studio API
 |
 v
Local LLM Model
 |
 v
AI Assistant Message
```

---

# 📂 Project Structure

```
01-feedback-system/

├── feedback_system/
│   ├── settings/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── dev.py
│   │   └── prod.py
│   ├── urls.py
│   ├── wsgi.py
│   └── asgi.py
│
├── feedbacks/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   └── services/
│       ├── ai_service.py
│       └── replies.py
│
├── config/
│   └── prompts/
│       └── feedback_response.txt
│
├── templates/
│   ├── feedbacks/
│   └── registration/
│
├── .env.example
├── .env
├── manage.py
├── pyproject.toml
└── README.md
```

---

# ⚙️ AI Configuration

The AI prompt is stored separately from the code:

```
config/prompts/feedback_response.txt
```

The application loads:

- AI endpoint
- Model name
- Temperature
- Token limit
- System prompt

from configuration files.

---

# ⚠️ Important Notes

- Do not commit `.env` to GitHub.
- LM Studio must be running before creating feedback.
- The selected model must be loaded in LM Studio.
- Any OpenAI-compatible local model can be used.

---

# 🛠 Development

Check project:

```bash
uv run python manage.py check
```

Create migrations:

```bash
uv run python manage.py makemigrations
```

Apply migrations:

```bash
uv run python manage.py migrate
```

---

# 📌 Future Improvements

- Add authentication
- Add API endpoints
- Add PostgreSQL production setup
- Add automated tests
- Improve AI response management