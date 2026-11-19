# Backend Engineering Roadmap

A practical, GitHub-driven Django backend apprenticeship project.

The project is designed to evolve from a simple feedback system into a real-world, production-oriented backend covering AI integration, conversations, authentication, authorization, expert workflows, documents, testing, APIs, and deployment.

---

## Engineering Rules

1. Backend implementation must be developed from official documentation, technical documentation, source code, and targeted web research rather than by handing the backend code to ChatGPT, coding agents, or other LLMs.
2. Frontend work may use LLM assistance.
3. Every sprint must be developed through GitHub using branches, commits, pull requests, review, requested changes, and merge.
4. `ROADMAP.md` is part of the repository and must be updated as each sprint progresses.
5. Every sprint must contain a concise implementation/review log in this file or in a linked project document.
6. Backend decisions must be explainable: a developer must be able to explain why an implementation, abstraction, query, pattern, or best practice was chosen.
7. No secrets, credentials, private infrastructure details, private business information, or confidential project information belongs in the public repository.
8. Every sprint must leave a clearly identifiable part of the system in a state that could be integrated into a real backend product.
9. Bugs discovered during review should be fixed through a normal GitHub iteration, not by silently rewriting history.
10. A new abstraction is valuable only when its purpose and trade-offs can be justified.

---

# Sprint 01 — Feedback Core

## Goal

Build the first reusable core of the application around feedback collection.

The system must support creating, reading, updating, and deleting user feedback such as suggestions, criticisms, and general comments.

## Tasks

- [x] Create the Django project/app structure.
- [x] Design and implement the feedback data model.
- [x] Create and apply migrations.
- [x] Implement complete CRUD functionality.
- [x] Use minimal Django templates for the initial UI.
- [x] Add URL routing and request handling.
- [x] Register the model in Django Admin.
- [x] Implement basic validation.
- [x] Add meaningful Git commits.
- ~~[ ] Open a pull request for review~~
- [x] Resolve review feedback in follow-up commits.

## Engineering Focus

- Django fundamentals
- Models and migrations
- Django ORM basics
- Views and URLs
- Templates
- Request/response lifecycle
- CRUD design
- Git/GitHub workflow

## Review Gate

- [x] Reviewer identifies design, style, correctness, security, and maintainability issues.
- [ ] Issues discovered in this sprint are documented as an improvement backlog.
- [x] The implementation is not considered final merely because the CRUD works.

## Real-World Readiness

**Ready component:** a basic feedback-management backend component suitable as the foundation for a larger application after review and hardening.

## Sprint Completion Notes

- Status: `Done`
- Review: `Done`
- Main lessons:
  1. Implemented the first Django feature from end to end.
  2. Practiced the complete model → migration → view → URL → template → database flow.
  3. Established the first working backend core for the application.
- Follow-up issues:
  1. Adding The dev branch. and move it trough this system.

---

# Sprint 02 — AI Response Pipeline

## Goal

Add AI-generated responses to feedback using an OpenAI-compatible endpoint exposed by LM Studio.

The implementation must use Django class-based views and must treat AI interaction as a potentially slow and failure-prone external operation.

## Tasks

- [x] Integrate LM Studio through its OpenAI-compatible API.
- [x] Keep endpoint/model configuration outside source code.
- [x] Implement the AI integration using an explicit service boundary rather than coupling the HTTP client directly to templates.
- [x] Use a class-based view for the feature.
- [x] Investigate synchronous versus asynchronous execution and choose an appropriate approach for the Django deployment model.
- [x] Handle long AI response times appropriately.
- [x] Add timeouts.
- [x] Handle connection failures, malformed responses, and other expected exceptions.
- [x] Persist the AI response in the database.
- [x] Persist the model identifier and other relevant response metadata.
- [x] Persist token usage when the provider supplies it.
- [x] Distinguish input, output, cached, and total usage where the API actually exposes those values.
- [x] Preserve enough metadata to understand how a response was generated.
- [x] Build a basic AI-usage page.
- [x] Aggregate total input/output/cached/total token usage with Django ORM queries.
- [x] Investigate how prior messages can be sent to the model as OpenAI-style `messages` context.
- [x] Avoid inventing token counts when the provider does not report them.
- [x] Add tests for successful responses and failure paths.
- [ ] Open a pull request and resolve review feedback.

## Engineering Focus

- Class-based views
- External API integration
- Python async/concurrency concepts
- Timeouts and failure handling
- Service-layer boundaries
- Persistence of external API metadata
- ORM aggregation and reporting
- `@property` and calculated model attributes where justified
- Structured metadata
- Integration testing and mocking

## Investigation Questions

- [x] What exactly does async improve in this deployment architecture?
- [x] When does async fail to provide the expected benefit?
- [x] What should happen when LM Studio is unavailable?
- [x] Which token metrics are authoritative and which are derived?
- [x] Where should AI-client logic live and why?
- [x] Which data belongs in a database field versus computed properties or metadata?

## Real-World Readiness

**Ready component:** an AI-backed feedback processing pipeline with persistent AI response metadata, failure handling, and usage reporting.

## Sprint Completion Notes

- Status: Done (pending PR review)
- Review: Pending PR creation and review
- Main lessons: Synchronous execution with strict timeouts under WSGI avoids complex event loop overhead while maintaining reliability; decoupling the AI client via an explicit service layer with custom exception handling guarantees the view never returns 500 errors; single-query ORM aggregation efficiently calculates multi-metric token usage without unnecessary database round-trips.
- Architecture decisions: Retained synchronous views with timeout protection for WSGI; adopted PRG pattern with django.contrib.messages for AI responses; persisted authoritative token metrics directly in database fields with NULL support.
- Follow-up issues: PR not opened yet.

---

# Sprint 03 — Conversation & Message Domain

## Goal

Evolve the one-shot feedback/response flow into a reusable conversation system.

The domain model must avoid duplicating the same information across `Request`, `Response`, and `Conversation` concepts.

## Tasks

- [x] Design the conversation domain before implementation.
- [x] Introduce a `Conversation` model.
- [x] Introduce a `Message` model representing conversation messages.
- [x] Define message roles clearly.
- [x] Model the relationships between conversations and messages with relational integrity.
- [x] Migrate the previous feedback/AI flow toward the conversation architecture where appropriate.
- [x] Avoid redundant storage of message content or shared conversation data.
- [x] Define ordering semantics for messages.
- [x] Add database constraints and indexes where justified.
- [x] Query conversation history efficiently.
- [x] Build a minimal conversation UI.
- [x] Allow a user message to trigger an AI response.
- [x] Persist the resulting message(s) correctly.
- [x] Test ordering and relational behavior.
- [x] Review generated SQL for important queries.
- [ ] Open a pull request and resolve review feedback.

## Engineering Focus

- Relational database design
- Normalization
- Foreign keys
- One-to-many relationships
- Query planning
- Constraints and indexes
- Transaction boundaries
- Domain modeling
- ORM query quality

## Investigation Questions

- [x] What should be a model and what should be an attribute?
- [x] Which data is duplicated and why is that a problem?
- [x] Where should AI-specific metadata live?
- [x] How should message order be guaranteed?
- [x] Which queries require `select_related`, `prefetch_related`, aggregation, or explicit indexing?

## Real-World Readiness

**Ready component:** a normalized conversation/message backend that can serve as the core messaging domain of a real application.

## Sprint Completion Notes

- Status: Done (pending PR review)
- Review: Pending PR creation and review
- Main lessons: Separating conversations from messages achieves 3NF normalization and enables clean multi-turn history tracking without data duplication; isolating external AI calls outside database transactions prevents transaction timeouts and connection holding while preserving data integrity; compound ordering with fallback to primary key guarantees deterministic message ordering.
- Schema decisions: Split the legacy monolithic Feedback table into Conversation (type, title, timestamps) and Message (conversation FK CASCADE, role, content, AI metadata); added composite index on (conversation, created_at) and CheckConstraint enforcing NULL token metrics on user messages; linear data migration (0003 -> 0004 -> 0005) cleanly transitioned existing data and dropped the legacy model.
- Follow-up issues: PR not opened yet.

---

# Sprint 04 — Authentication, Ownership & Admin

## Goal

Turn the application into a multi-user system using Django's built-in authentication/session mechanisms.

Each user must be isolated from other users' conversations and resources.

## Tasks

- [x] Implement registration.
- [x] Implement login and logout using Django authentication.
- [x] Handle authenticated sessions correctly.
- [x] Introduce ownership for user-owned resources.
- [x] Ensure a user can only access their own conversations.
- [x] Add appropriate authorization checks at the backend boundary.
- [x] Connect the important models to Django Admin.
- [x] Configure admin list/search/filter behavior where useful.
- [x] Investigate class-based authentication-related views and patterns.
- [x] Design reusable abstract model foundations such as timestamp/ownership/full-model bases when justified.
- [x] Evaluate whether session identity and conversation ownership need separate concepts.
- [x] Add authorization-focused tests.
- [x] Verify that direct URL access cannot bypass ownership rules.
- [ ] Open a pull request and resolve review feedback.

## Engineering Focus

- Django authentication
- Sessions
- Ownership
- Authorization boundaries
- Django Admin
- Abstract base models
- Reusable model architecture
- Security-oriented testing

## Investigation Questions

- [x] What is the difference between authentication and authorization?
- [x] Where should ownership checks happen?
- [x] How can an object-level authorization bug appear even when the UI looks correct?
- [x] When is an abstract base model justified?
- [x] How should session lifecycle affect application behavior?

## Real-World Readiness

**Ready component:** a multi-user conversation backend with authentication, ownership isolation, and administrative visibility.

## Sprint Completion Notes

- Status: Done (pending PR review)
- PR: Pending PR creation and review
- Review: Pending PR creation and review
- Main lessons: Authorization checks must be strictly enforced at the database query boundary via `get_queryset()` rather than UI visibility; Insecure Direct Object References (IDOR) are prevented when the ORM automatically filters object queries by the authenticated user; POST-only logout in modern Django protects against CSRF-based forced logout attacks.
- Security findings: Direct URL manipulation (`/c/<pk>/`, `/update/<pk>/`, `/delete/<pk>/`) is completely blocked at the backend query level, returning 404 for unauthorized resources; anonymous users are systematically redirected to login on all views; AI usage totals are strictly isolated per-user.
- Follow-up issues: PR not opened yet.

---

# Sprint 05 — Best Practices & Development/Production Architecture

## Goal

Harden the existing project instead of merely adding another feature.

The focus shifts from feature delivery toward maintainability, correctness, security, configuration, and production discipline.

## Tasks

- [x] Audit the existing project for maintainability and architectural problems.
- [x] Research relevant Django and Python best practices using primary or high-quality technical sources.
- [x] Separate development and production configuration appropriately.
- [x] Establish a clean settings/configuration structure.
- [x] Remove hard-coded secrets and environment-specific values.
- [x] Review logging configuration.
- [x] Review error handling and failure visibility.
- [x] Review database configuration and production readiness.
- [x] Review static/media handling.
- [x] Review security-related Django settings.
- [x] Review model architecture and abstraction boundaries.
- [x] Introduce model methods, properties, custom querysets/managers, metadata, validators, constraints, or other Python/Django mechanisms only where justified.
- [x] Inspect and improve inefficient ORM queries.
- [x] Add indexes or constraints where evidence supports them.
- [x] Add or improve tests around behavior changed during hardening.
- [x] Document important architectural decisions.
- [x] For every significant best-practice change, explain the problem, evidence, chosen solution, and trade-off.
- [ ] Open a pull request and resolve review feedback.

## Engineering Focus

- Django project architecture
- Configuration management
- Production readiness
- Python object model
- Decorators and descriptors where relevant
- Properties and metadata
- Custom model behavior
- Custom QuerySets/managers
- ORM performance
- Security hardening
- Engineering reasoning

## Rule for Best Practices

A best practice is not accepted merely because it is commonly recommended.

For every meaningful change:

1. Identify the problem.
2. Investigate reliable sources.
3. Understand the mechanism.
4. Apply it where appropriate.
5. Explain the trade-off.

## Real-World Readiness

**Ready component:** a substantially hardened Django backend with explicit development/production separation and documented engineering decisions.

## Sprint Completion Notes

- Status: Done (pending PR review)
- PR: Pending PR creation and review
- Review: Pending PR creation and review
- Main lessons: Splitting settings into base/dev/prod isolates deployment security checks from developer ergonomics; burning exposed secrets and strictly validating them via `ImproperlyConfigured` prevents production misconfiguration; structured logging with sanitized parameters (`logger.exception`) gives full failure visibility without leaking sensitive prompt or conversation PII.
- Best-practice findings: Ensuring single leading system message aligns with modern LLM chat templates that reject multiple mid-history system prompts; encapsulating domain filters in `ConversationQuerySet` (`for_user`, `with_message_count`) cleans view code; `prefetch_related('messages')` eliminates N+1 queries on conversation detail.
- Architectural decisions: Modular settings package (`base.py`, `dev.py`, `prod.py`); `manage.py` defaults to `.dev`, `wsgi`/`asgi` default to `.prod`; composite index `(owner, -created_at)` for optimal list sorting; strict deploy check compliance (`check --deploy --fail-level WARNING`).
- Follow-up issues: PR not opened yet.

---

# Sprint 06 — Expert Role, Permissions & Intervention Workflow

## Goal

Introduce the third major actor in the system: the expert.

The application must distinguish ordinary users, experts, and administrators while supporting expert intervention in conversations with explicit authorization and business rules.

## Tasks

- [x] Define the role model for user, expert, and administrator capabilities.
- [x] Separate authentication from authorization explicitly.
- [x] Implement backend-enforced permissions.
- [x] Prevent unauthorized access even when an endpoint is called directly.
- [x] Introduce expert assignment/intervention concepts where needed.
- [x] Model expert participation in conversations relationally.
- [x] Define when an expert can join a conversation.
- [x] Define when the AI should respond automatically.
- [x] Define when the AI should remain silent because an expert is handling the interaction.
- [x] Define how explicit user requests can address an expert.
- [x] Define the state transitions around expert intervention.
- [x] Update the message/conversation models only as required by the new domain rules.
- [x] Add authorization tests for user, expert, and administrator actions.
- [x] Add workflow tests for AI/expert interaction.
- [x] Update Django Admin for expert-related management.
- [ ] Open a pull request and resolve review feedback.

## Engineering Focus

- Role-based access control
- Object-level authorization
- Permission design
- Domain state
- Expert workflow
- Business rules
- Message routing
- Multi-actor conversations

## Investigation Questions

- [x] Should roles be represented as a fixed field, groups, permissions, or a combination?
- [x] Which permissions are global and which are object-level?
- [x] How should expert participation be represented in the database?
- [x] What precisely causes the AI to answer or stay silent?
- [x] Which state transitions are valid and which must be rejected?

## Real-World Readiness

**Ready component:** a multi-actor conversation subsystem with explicit roles, backend-enforced permissions, and expert intervention rules suitable for integration into a real application.

## Sprint Completion Notes

- Status: Done (pending PR review)
- PR: Pending PR creation and review
- Review: Pending PR creation and review
- Main lessons: State transitions and intervention logic must be modeled directly as explicit domain methods (`transition_to`) with backend validation; permission logic is most maintainable when consolidated in a dedicated module (`feedbacks/permissions.py`); human expert answers must be seamlessly mapped to `assistant` in multi-turn AI context.
- Authorization findings: Unifying authorization checks and returning HTTP 404 (instead of 403) protects conversation existence and state against discovery and direct manipulation across all endpoints (`/expert/`, `/c/<pk>/claim/`, `/c/<pk>/release/`, `/c/<pk>/close/`, `/c/<pk>/request-expert/`).
- Workflow decisions: Standard Django `experts` Group defines expert capability; conversation status machine transitions strictly from `ai` to `waiting_expert` on user request/@expert trigger, to `expert_active` upon claim, to `ai` upon release, and to `closed` as terminal state; AI remains strictly silent whenever an expert is requested or active.
- Follow-up issues: PR not opened yet.

---

# Sprint Review Template

Copy this structure into the relevant sprint section when the sprint begins/completes.

```markdown
## Implementation Log

### What was built?
- [ ] ...

### What was researched?
- [ ] ...

### Important design decisions
- ...

### Problems discovered
- ...

### How were they solved?
- ...

### Tests added
- [ ] ...

### PR
- Link: ...

### Review outcome
- [ ] Approved
- [ ] Changes requested
- [ ] Merged

### What is now production-ready?
- ...

### What remains?
- ...
- Adding the feature through Git/GitHub branch workflow. (Actualy is on Sprint 01, but moved to future for making a complexity.)

---

# Final Engineering Standard

By the end of this roadmap, the project should demonstrate that its developer can:

- [x] Understand and extend an existing Django codebase.
- [x] Design relational models without unnecessary duplication.
- [x] Write effective Django ORM queries.
- [x] Integrate and operate external AI services safely.
- [x] Reason about async/concurrency and latency rather than using async blindly.
- [x] Handle failure paths and external-service uncertainty.
- [x] Build authentication and authorization correctly.
- [x] Design domain workflows with explicit states and rules.
- [x] Write maintainable Python/Django abstractions.
- [x] Research best practices independently and explain trade-offs.
- [x] Write automated tests and regression tests.
- [ ] Build a documented API. (Deferred: REST/GraphQL API specification and endpoints scheduled for a dedicated API phase)
- [ ] Work professionally through GitHub pull requests and code review. (Deferred: GitHub PR/branch review workflow deferred by project owner)
- [x] Prepare a backend for real integration and deployment.

The final standard is not simply “the code works.”

The standard is:

> **The developer can explain the system, defend the design, test the important behavior, respond to review, and safely evolve the backend.**
