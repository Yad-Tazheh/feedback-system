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

Create a `.env` file in the project root:

```
.env
```

Add the following variables:

```env
LM_STUDIO_URL=http://localhost:1234/v1/chat/completions

LM_MODEL=your-model-name

LM_TEMPERATURE=0.4

LM_MAX_TOKENS=150
```

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

---

# 🏗 Project Architecture

```
User
 |
 v
Django Views
 |
 v
Feedback Model
 |
 v
AIService
 |
 v
LM Studio API
 |
 v
Local LLM Model
 |
 v
AI Response
```

---

# 📂 Project Structure

```
01-feedback-system/

├── feedbacks/
│   ├── models.py
│   ├── views.py
│   ├── urls.py
│   ├── forms.py
│   └── services/
│       └── ai_service.py
│
├── config/
│   └── prompts/
│       └── feedback_response.txt
│
├── templates/
│   └── feedbacks/
│
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