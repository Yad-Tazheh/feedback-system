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

- [ ] Create the Django project/app structure.
- [ ] Design and implement the feedback data model.
- [ ] Create and apply migrations.
- [ ] Implement complete CRUD functionality.
- [ ] Use minimal Django templates for the initial UI.
- [ ] Add URL routing and request handling.
- [ ] Register the model in Django Admin.
- [ ] Implement basic validation.
- [ ] Add meaningful Git commits.
- [ ] Open a pull request for review.
- [ ] Resolve review feedback in follow-up commits.

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

- [ ] Reviewer identifies design, style, correctness, security, and maintainability issues.
- [ ] Issues discovered in this sprint are documented as an improvement backlog.
- [ ] The implementation is not considered final merely because the CRUD works.

## Real-World Readiness

**Ready component:** a basic feedback-management backend component suitable as the foundation for a larger application after review and hardening.

## Sprint Completion Notes

- Status: `Not Started`
- PR: TBD
- Review: TBD
- Main lessons: TBD
- Follow-up issues: TBD

---

# Sprint 02 — AI Response Pipeline

## Goal

Add AI-generated responses to feedback using an OpenAI-compatible endpoint exposed by LM Studio.

The implementation must use Django class-based views and must treat AI interaction as a potentially slow and failure-prone external operation.

## Tasks

- [ ] Integrate LM Studio through its OpenAI-compatible API.
- [ ] Keep endpoint/model configuration outside source code.
- [ ] Implement the AI integration using an explicit service boundary rather than coupling the HTTP client directly to templates.
- [ ] Use a class-based view for the feature.
- [ ] Investigate synchronous versus asynchronous execution and choose an appropriate approach for the Django deployment model.
- [ ] Handle long AI response times appropriately.
- [ ] Add timeouts.
- [ ] Handle connection failures, malformed responses, and other expected exceptions.
- [ ] Persist the AI response in the database.
- [ ] Persist the model identifier and other relevant response metadata.
- [ ] Persist token usage when the provider supplies it.
- [ ] Distinguish input, output, cached, and total usage where the API actually exposes those values.
- [ ] Preserve enough metadata to understand how a response was generated.
- [ ] Build a basic AI-usage page.
- [ ] Aggregate total input/output/cached/total token usage with Django ORM queries.
- [ ] Investigate how prior messages can be sent to the model as OpenAI-style `messages` context.
- [ ] Avoid inventing token counts when the provider does not report them.
- [ ] Add tests for successful responses and failure paths.
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

- [ ] What exactly does async improve in this deployment architecture?
- [ ] When does async fail to provide the expected benefit?
- [ ] What should happen when LM Studio is unavailable?
- [ ] Which token metrics are authoritative and which are derived?
- [ ] Where should AI-client logic live and why?
- [ ] Which data belongs in a database field versus computed properties or metadata?

## Real-World Readiness

**Ready component:** an AI-backed feedback processing pipeline with persistent AI response metadata, failure handling, and usage reporting.

## Sprint Completion Notes

- Status: `Not Started`
- PR: TBD
- Review: TBD
- Main lessons: TBD
- Architecture decisions: TBD
- Follow-up issues: TBD

---

# Sprint 03 — Conversation & Message Domain

## Goal

Evolve the one-shot feedback/response flow into a reusable conversation system.

The domain model must avoid duplicating the same information across `Request`, `Response`, and `Conversation` concepts.

## Tasks

- [ ] Design the conversation domain before implementation.
- [ ] Introduce a `Conversation` model.
- [ ] Introduce a `Message` model representing conversation messages.
- [ ] Define message roles clearly.
- [ ] Model the relationships between conversations and messages with relational integrity.
- [ ] Migrate the previous feedback/AI flow toward the conversation architecture where appropriate.
- [ ] Avoid redundant storage of message content or shared conversation data.
- [ ] Define ordering semantics for messages.
- [ ] Add database constraints and indexes where justified.
- [ ] Query conversation history efficiently.
- [ ] Build a minimal conversation UI.
- [ ] Allow a user message to trigger an AI response.
- [ ] Persist the resulting message(s) correctly.
- [ ] Test ordering and relational behavior.
- [ ] Review generated SQL for important queries.
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

- [ ] What should be a model and what should be an attribute?
- [ ] Which data is duplicated and why is that a problem?
- [ ] Where should AI-specific metadata live?
- [ ] How should message order be guaranteed?
- [ ] Which queries require `select_related`, `prefetch_related`, aggregation, or explicit indexing?

## Real-World Readiness

**Ready component:** a normalized conversation/message backend that can serve as the core messaging domain of a real application.

## Sprint Completion Notes

- Status: `Not Started`
- PR: TBD
- Review: TBD
- Main lessons: TBD
- Schema decisions: TBD
- Follow-up issues: TBD

---

# Sprint 04 — Authentication, Ownership & Admin

## Goal

Turn the application into a multi-user system using Django's built-in authentication/session mechanisms.

Each user must be isolated from other users' conversations and resources.

## Tasks

- [ ] Implement registration.
- [ ] Implement login and logout using Django authentication.
- [ ] Handle authenticated sessions correctly.
- [ ] Introduce ownership for user-owned resources.
- [ ] Ensure a user can only access their own conversations.
- [ ] Add appropriate authorization checks at the backend boundary.
- [ ] Connect the important models to Django Admin.
- [ ] Configure admin list/search/filter behavior where useful.
- [ ] Investigate class-based authentication-related views and patterns.
- [ ] Design reusable abstract model foundations such as timestamp/ownership/full-model bases when justified.
- [ ] Evaluate whether session identity and conversation ownership need separate concepts.
- [ ] Add authorization-focused tests.
- [ ] Verify that direct URL access cannot bypass ownership rules.
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

- [ ] What is the difference between authentication and authorization?
- [ ] Where should ownership checks happen?
- [ ] How can an object-level authorization bug appear even when the UI looks correct?
- [ ] When is an abstract base model justified?
- [ ] How should session lifecycle affect application behavior?

## Real-World Readiness

**Ready component:** a multi-user conversation backend with authentication, ownership isolation, and administrative visibility.

## Sprint Completion Notes

- Status: `Not Started`
- PR: TBD
- Review: TBD
- Main lessons: TBD
- Security findings: TBD
- Follow-up issues: TBD

---

# Sprint 05 — Best Practices & Development/Production Architecture

## Goal

Harden the existing project instead of merely adding another feature.

The focus shifts from feature delivery toward maintainability, correctness, security, configuration, and production discipline.

## Tasks

- [ ] Audit the existing project for maintainability and architectural problems.
- [ ] Research relevant Django and Python best practices using primary or high-quality technical sources.
- [ ] Separate development and production configuration appropriately.
- [ ] Establish a clean settings/configuration structure.
- [ ] Remove hard-coded secrets and environment-specific values.
- [ ] Review logging configuration.
- [ ] Review error handling and failure visibility.
- [ ] Review database configuration and production readiness.
- [ ] Review static/media handling.
- [ ] Review security-related Django settings.
- [ ] Review model architecture and abstraction boundaries.
- [ ] Introduce model methods, properties, custom querysets/managers, metadata, validators, constraints, or other Python/Django mechanisms only where justified.
- [ ] Inspect and improve inefficient ORM queries.
- [ ] Add indexes or constraints where evidence supports them.
- [ ] Add or improve tests around behavior changed during hardening.
- [ ] Document important architectural decisions.
- [ ] For every significant best-practice change, explain the problem, evidence, chosen solution, and trade-off.
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

- Status: `Not Started`
- PR: TBD
- Review: TBD
- Main lessons: TBD
- Best-practice findings: TBD
- Architectural decisions: TBD
- Follow-up issues: TBD

---

# Sprint 06 — Expert Role, Permissions & Intervention Workflow

## Goal

Introduce the third major actor in the system: the expert.

The application must distinguish ordinary users, experts, and administrators while supporting expert intervention in conversations with explicit authorization and business rules.

## Tasks

- [ ] Define the role model for user, expert, and administrator capabilities.
- [ ] Separate authentication from authorization explicitly.
- [ ] Implement backend-enforced permissions.
- [ ] Prevent unauthorized access even when an endpoint is called directly.
- [ ] Introduce expert assignment/intervention concepts where needed.
- [ ] Model expert participation in conversations relationally.
- [ ] Define when an expert can join a conversation.
- [ ] Define when the AI should respond automatically.
- [ ] Define when the AI should remain silent because an expert is handling the interaction.
- [ ] Define how explicit user requests can address an expert.
- [ ] Define the state transitions around expert intervention.
- [ ] Update the message/conversation models only as required by the new domain rules.
- [ ] Add authorization tests for user, expert, and administrator actions.
- [ ] Add workflow tests for AI/expert interaction.
- [ ] Update Django Admin for expert-related management.
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

- [ ] Should roles be represented as a fixed field, groups, permissions, or a combination?
- [ ] Which permissions are global and which are object-level?
- [ ] How should expert participation be represented in the database?
- [ ] What precisely causes the AI to answer or stay silent?
- [ ] Which state transitions are valid and which must be rejected?

## Real-World Readiness

**Ready component:** a multi-actor conversation subsystem with explicit roles, backend-enforced permissions, and expert intervention rules suitable for integration into a real application.

## Sprint Completion Notes

- Status: `Not Started`
- PR: TBD
- Review: TBD
- Main lessons: TBD
- Authorization findings: TBD
- Workflow decisions: TBD
- Follow-up issues: TBD

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
```

---

# Final Engineering Standard

By the end of this roadmap, the project should demonstrate that its developer can:

- [ ] Understand and extend an existing Django codebase.
- [ ] Design relational models without unnecessary duplication.
- [ ] Write effective Django ORM queries.
- [ ] Integrate and operate external AI services safely.
- [ ] Reason about async/concurrency and latency rather than using async blindly.
- [ ] Handle failure paths and external-service uncertainty.
- [ ] Build authentication and authorization correctly.
- [ ] Design domain workflows with explicit states and rules.
- [ ] Write maintainable Python/Django abstractions.
- [ ] Research best practices independently and explain trade-offs.
- [ ] Write automated tests and regression tests.
- [ ] Build a documented API.
- [ ] Work professionally through GitHub pull requests and code review.
- [ ] Prepare a backend for real integration and deployment.

The final standard is not simply “the code works.”

The standard is:

> **The developer can explain the system, defend the design, test the important behavior, respond to review, and safely evolve the backend.**
