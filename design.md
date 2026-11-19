we will explain each engineering decisions in this file 
my decisions are in normal font
reviewer decisions and comments are in italic format
----------------

we have an overview of the project as such:
Browser
                       │
                       ▼
              feedback_system/urls.py
                       │
                       ▼
                 feedbacks/urls.py
                       │
                       ▼
                 feedbacks/views.py
                       │
              ┌────────┴────────┐
              ▼                 ▼
        Feedback Model       AIService
              │                 │
              ▼                 ▼
           SQLite          LM Studio API
                                │
                                ▼
                         Qwen2.5-7B
-------------------------------------------
feedback_system = Project / settings.py entire django project settings
feedbacks        = Application



model layer:
Django provides an abstraction layer (the “models”) for structuring and manipulating the data of your web application

view layer:
Django has the concept of “views” to encapsulate the logic responsible for processing a user’s request and for returning the response.

template layer:
The template layer provides a designer-friendly syntax for rendering the information to be presented to the user.

form layer:
Django provides a rich framework to facilitate the creation of forms and the manipulation of form data.

-------------------------------------------
## Sprint 02 — Investigation Questions & Architectural Decisions

### 1. What exactly does async improve in this deployment architecture?
In an asynchronous ASGI architecture, async views allow the worker thread or event loop to yield while awaiting network I/O from an external API (like LM Studio), freeing up concurrency to serve other inbound requests.

### 2. When does async fail to provide the expected benefit?
Async fails to provide benefits when deployed under standard WSGI (such as Gunicorn with default sync workers), where the underlying OS worker process is synchronously blocked regardless of async view syntax. It also fails when operations are CPU-bound or database access is synchronous, causing context-switching overhead without genuine concurrency. Furthermore, if LM Studio / local LLM inference is serialized on a single GPU, the bottleneck is downstream inference capacity, not Django request concurrency. Therefore, synchronous execution with a strict timeout (`LM_TIMEOUT`) is the most robust and predictable approach under the current WSGI deployment.

### 3. What should happen when LM Studio is unavailable?
When LM Studio is unreachable, connection times out, or returns errors:
- The user's feedback submission must always be safely saved in the database first.
- The failure must be recorded directly on the record (`ai_status='failed'`, `ai_error` storing the exception message).
- The view must never raise an unhandled 500 error; it gracefully redirects (PRG pattern) and informs the user via `django.contrib.messages`.
- Failed requests can later be reprocessed manually or through background tasks.

### 4. Which token metrics are authoritative and which are derived?
- **Authoritative:** Metrics reported directly in the provider's API response payload (`prompt_tokens`, `completion_tokens`, `total_tokens`, and `cached_tokens` from `prompt_tokens_details.cached_tokens`). If omitted by the provider, they remain `None` (NULL) and must never be fabricated.
- **Derived:** Aggregate metrics across all records (e.g., total tokens consumed across the platform, counts of successful vs. failed requests) computed dynamically via Django ORM aggregations (`Sum`, `Count`).

### 5. Where should AI-client logic live and why?
AI-client logic lives in a dedicated service layer (`feedbacks/services/ai_service.py`), strictly separate from views, forms, and models. This encapsulates external HTTP transport details, environment configuration, prompt injection, and error normalization (`AIServiceError`), keeping views simple, declarative, and easy to unit test using mocks.

### 6. Which data belongs in a database field versus computed properties or metadata?
- **Database fields:** Persisted attributes required for relational queries, filtering, reporting, and SQL aggregation (`ai_status`, `ai_model`, `prompt_tokens`, `completion_tokens`, `cached_tokens`, `total_tokens`, `ai_responded_at`, `ai_error`).
- **Computed properties / helper methods:** Ephemeral logic, presentation formatting, and prompt payload construction (`Feedback.as_messages()`) that can be computed on demand without database indexing overhead.
