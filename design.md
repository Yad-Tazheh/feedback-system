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

-------------------------------------------
## Sprint 03 — Conversation & Message Domain

### Schema Diagram

```
┌─────────────────────────────────┐
│          Conversation           │
├─────────────────────────────────┤
│ id: BigAutoField (PK)           │
│ type: CharField(20)             │
│ title: CharField(200)           │
│ created_at: DateTimeField       │
│ updated_at: DateTimeField       │
└────────────────┬────────────────┘
                 │ 1
                 │
                 │ *
┌────────────────▼────────────────┐
│             Message             │
├─────────────────────────────────┤
│ id: BigAutoField (PK)           │
│ conversation_id: FK(CASCADE)    │
│ role: CharField(20) [user/asst] │
│ content: TextField              │
│ created_at: DateTimeField       │
│ ai_model: CharField(100)        │
│ prompt_tokens: PosInt(null)     │
│ completion_tokens: PosInt(null) │
│ cached_tokens: PosInt(null)     │
│ total_tokens: PosInt(null)      │
│ ai_status: CharField(20, null)  │
│ ai_error: TextField             │
└─────────────────────────────────┘
Index: (conversation, created_at)
Ordering: ['created_at', 'id']
Constraint: user_message_token_fields_null
```

### Investigation Questions & Architectural Decisions

#### 1. What should be a model and what should be an attribute?
Entities representing independent domain lifecycles, identities, and one-to-many relationships are modeled as distinct database tables (`Conversation` and `Message`). Properties describing an instance (such as message `role`, token counts, `ai_status`, and timestamps) are scalar attributes on the respective model.

#### 2. Which data is duplicated and why is that a problem?
In the single-table `Feedback` schema, the thread title and feedback type were coupled directly to a single response field. Extending to multi-turn conversation would have required duplicating thread metadata or denormalizing message history into arbitrary text columns. Separating into `Conversation` (thread identity) and `Message` (individual turns) establishes 3NF normalization, ensures single-responsibility updates, and prevents data anomalies.

#### 3. Where should AI-specific metadata live?
AI metadata (`ai_model`, token consumption, status, error) belongs strictly to the individual assistant `Message` record generated by the AI turn. It does not belong on `Conversation` (which spans multiple interactions across models and turns) nor on user messages. A database `CheckConstraint` enforces that user messages have null token metrics.

#### 4. How should message order be guaranteed?
Message ordering is guaranteed at the model level via `Meta.ordering = ['created_at', 'id']`. Secondary sorting by primary key `id` guarantees deterministic ordering even when multiple messages share identical timestamps within the same clock tick. Furthermore, a composite index `(conversation, created_at)` optimizes this ordering query plan at the SQL storage engine level.

#### 5. Which queries require `select_related`, `prefetch_related`, aggregation, or explicit indexing?
- **Explicit Indexing:** The composite index on `(conversation, created_at)` accelerates history filtering and ordering for conversation detail views and prompt building.
- **Aggregation:** `AIUsageView` computes platform-wide token usage and counts via a single SQL `aggregate(Sum(...), Count(...))` across assistant messages without loading objects into memory.
- **Query Count Optimization:** `FeedbackListView` annotates message count via `.annotate(message_count=Count('messages'))`, avoiding N+1 queries across the list.

### History Query SQL
The conversation history query used by `Conversation.as_messages()` (`conversation.messages.exclude(ai_status='failed')`):

```sql
SELECT "feedbacks_message"."id",
       "feedbacks_message"."conversation_id",
       "feedbacks_message"."role",
       "feedbacks_message"."content",
       "feedbacks_message"."created_at",
       "feedbacks_message"."ai_model",
       "feedbacks_message"."prompt_tokens",
       "feedbacks_message"."completion_tokens",
       "feedbacks_message"."cached_tokens",
       "feedbacks_message"."total_tokens",
       "feedbacks_message"."ai_status",
       "feedbacks_message"."ai_error"
FROM "feedbacks_message"
WHERE ("feedbacks_message"."conversation_id" = 1
  AND NOT ("feedbacks_message"."ai_status" = 'failed' AND "feedbacks_message"."ai_status" IS NOT NULL))
ORDER BY "feedbacks_message"."created_at" ASC,
         "feedbacks_message"."id" ASC;
```

-------------------------------------------
## Sprint 04 — Authentication, Ownership & Admin

### Investigation Questions & Architectural Decisions

#### 1. What is the difference between authentication and authorization?
- **Authentication (AuthN):** The process of verifying *who* a user is (identity verification, e.g., verifying username and password credentials during login, establishing session cookies).
- **Authorization (AuthZ):** The process of verifying *what* an authenticated user is permitted to do or access (access control, e.g., ensuring User A cannot read, edit, delete, or append messages to User B's conversations).

#### 2. Where should ownership checks happen?
Ownership checks must happen at the backend database query boundary (`get_queryset()` in class-based views) rather than relying on template UI hiding or client-side checks. By scoping the query via `Conversation.objects.filter(owner=self.request.user)` inside a shared `OwnedConversationMixin`, the ORM naturally treats any unauthorized ID lookup as a 404 (Not Found), completely eliminating Insecure Direct Object Reference (IDOR) vulnerabilities across detail, update, delete, and message creation endpoints.

#### 3. How can an object-level authorization bug appear even when the UI looks correct?
An object-level authorization bug (IDOR) occurs when the UI only displays links to resources owned by the current user, but the view fetches records by primary key alone (`Conversation.objects.get(pk=pk)`) without filtering by the authenticated user. An attacker or curious user can simply change the PK in the browser URL bar (e.g. `/c/42/`, `/update/42/`, or `/delete/42/`) and access or manipulate another user's data, bypassing UI restrictions unless the backend view strictly enforces ownership at the query level.

#### 4. When is an abstract base model justified?
An abstract base model (such as `TimeStampedModel`) is justified when multiple distinct models share identical fields, indexing, and lifecycle behaviors. In our domain, `Conversation` is a mutable entity requiring both `created_at` and `updated_at`, while `Message` represents immutable turn records with only `created_at`. Creating an abstract base for a single model or forcing `updated_at` onto immutable messages would introduce unnecessary abstraction and database bloat without deduplication value. Therefore, explicit timestamp declarations were kept, and an abstract base was deliberately not forced.

#### 5. How should session lifecycle affect application behavior?
The session lifecycle governs authentication state. When a session expires or a user logs out (via Django 5+ POST-only logout), session data (`_auth_user_id`) is purged, and subsequent requests to protected endpoints immediately redirect to the login URL with `?next=...`. Upon login or signup, a session is initialized (`django.contrib.auth.login`), establishing the request user identity that scopes all downstream conversation ownership queries.

### Session Identity vs. Ownership Decision
Session identity is ephemeral and browser/device-specific (tied to session cookies with potential expiration or clearance), whereas resource ownership (`Conversation.owner`) represents persistent relational ownership tied to the permanent User identity in the database. Relying solely on session identity for ownership would lose data across device switches or cookie clearings. Therefore, conversations are strictly bound via foreign key to the permanent `AUTH_USER_MODEL`, while sessions authenticate the user making the request.

### Legacy Data Migration Decision
Migration `0006` introduces `owner` as a nullable foreign key (`null=True, blank=True`). This ensures that legacy conversations created prior to authentication can be preserved without requiring arbitrary placeholder users or data destruction. These legacy unowned conversations remain accessible in Django Admin for administrative auditing while remaining hidden from standard user views.


