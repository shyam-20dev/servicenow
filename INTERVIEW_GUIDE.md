# Interview Guide – HCLTech USM & Generative AI

Use these as *ideas to say in your own words*, not scripts to memorise. Interviewers prefer a short honest answer with
an example over a textbook paragraph.

---
# Part 1 – Concepts in simple language

## ITSM, USM and ServiceNow

* **ITSM (IT Service Management):** the way an IT team delivers and supports IT as a *service*: receiving problems and
  requests, tracking them, fixing them, and improving. Think: a well-organised help desk with defined processes
  (incident, problem, change, request) instead of random emails.
* **USM (Universal Service Management):** applying the same service-management approach beyond IT – HR, Finance,
  Facilities, Legal – so every department handles employee requests in one platform with shared workflows, catalog,
  knowledge and reporting. In my project, an HR "employment letter" and an IT "software install" use the same request
  workflow. *(I only demonstrate the principle; I don't claim it's the official product.)*
* **ServiceNow:** a cloud platform (Platform-as-a-Service) for digital workflows. Everything is stored in **tables**,
  shown in **forms** and **lists**, and automated with **workflows/flows**, business rules and a **REST API**.
* **Table / record / field:** a table (e.g. `incident`) is like a spreadsheet; a record is one row; a field is a column.
* **Form / list:** a form shows one record; a list shows many records with filters.
* **Workflow / Flow Designer:** a sequence of steps/approvals that runs automatically, e.g. "when a P1 incident is created,
  notify the on-call group and start an SLA".
* **Assignment group:** the team responsible for a ticket (e.g. Network Support).

## Incident, problem, change, request

* **Incident:** something is *broken or degraded* – restore service quickly ("VPN is down").
* **Problem:** the *root cause* behind one or many incidents ("Every Monday the VPN gateway runs out of licences").
* **Change request:** a *planned modification* to the environment, approved and scheduled to reduce risk ("upgrade the VPN gateway on Saturday").
* **Service request:** a *standard, expected ask* – nothing is broken ("install VS Code", "new joiner laptop", "HR letter").
* **Quick test:** Is something broken → incident. Do you want something → request. Why does it keep breaking → problem. Are we altering the system → change.

## SLA, priority, impact, urgency

* **Impact:** how many people/how much business is affected. **Urgency:** how quickly it must be fixed.
* **Priority** = f(impact, urgency). A single user's cosmetic issue (low/low) is low; a company-wide outage (high/high) is critical.
* **SLA (Service Level Agreement):** a time commitment, e.g. "respond to P1 in 15 minutes, resolve in 4 hours". Breach → escalation.
* In my app: `priority = matrix(impact, urgency)` computed in code, deterministic, not decided by the AI.

## REST API

A way for programs to talk over HTTP using URLs and verbs: **GET** read, **POST** create, **PUT/PATCH** update, **DELETE** remove,
usually exchanging **JSON**. ServiceNow's **Table API** exposes every table: `POST /api/now/table/incident` creates an incident,
`GET /api/now/table/incident?sysparm_limit=1` reads. Status codes: 200/201 success, 401 bad credentials, 403 no permission, 404 not found, 429 too many requests.

## Generative AI concepts

* **Generative AI:** models that *create* new content (text, code, images) rather than only classify or predict labels.
* **LLM (Large Language Model):** a neural network trained on huge text data to predict the next token; that ability lets it
  summarise, classify, translate and answer questions.
* **Tokens:** pieces of text (≈ ¾ of a word). Models read/produce tokens; cost and the **context window** (max tokens per request) are measured in them.
* **Prompt engineering:** writing instructions so the model behaves reliably – role, task, constraints, output format (e.g. "reply with JSON with these keys"), examples.
* **Embeddings:** a list of numbers (a vector) representing the *meaning* of text; similar meanings → vectors close together.
* **Vector search:** embed the question, then find the stored vectors nearest to it (cosine similarity). It finds meaning, not just matching words.
* **RAG (Retrieval-Augmented Generation):** *retrieve* relevant documents first, then give them to the LLM as context so it *generates* an answer grounded in them, with citations.
* **Why RAG for internal knowledge:** an LLM was never trained on your private, up-to-date documents; it will guess. RAG supplies the facts at question time, is
  easy to update (upload a file, no retraining), allows citations and permission control, and lets you say "I don't know".
* **Hallucination:** a confident but wrong/invented answer.
* **Reducing hallucinations:** ground with RAG; instruct "use only the context, otherwise say you don't know"; low temperature; require citations; validate structured output;
  threshold on retrieval relevance; human review for high-impact actions; evaluate with test questions.
* **AI agent:** an LLM-driven system that can *decide and take actions* with tools (call APIs, update tickets) in a loop towards a goal. My app is **not** an agent –
  it suggests; it doesn't act autonomously.
* **Automation vs AI:** automation follows fixed rules ("if category=Network then assign Network Support"). AI handles fuzzy, unstructured input (understanding free text,
  summarising). Best systems combine both – I use AI to understand text and rules to compute priority and routing.

## How GenAI improves ITSM

Summarising long tickets and chats, suggesting categories/priority/assignment group, proposing resolutions from knowledge,
drafting replies, deflecting simple questions via self-service chat (fewer tickets), writing knowledge articles from resolved tickets,
and summarising incident handovers. Risks: wrong suggestions, data privacy, cost – hence human review and logging.

---
# Part 2 – How SmartDesk works

1. Employee submits an incident (FastAPI validates it with Pydantic).
2. `incident_service` asks the LLM (if configured) for a JSON analysis: summary, category, impact, urgency, steps, resolution – optionally with 2 retrieved KB excerpts as context.
3. The JSON is parsed and validated; if invalid or the LLM fails, a **labelled rule-based fallback** is used.
4. Priority is computed by a fixed matrix; the group/technician come from the category.
5. The ticket is stored in SQLite. An agent updates status in the UI. Optionally it is pushed to ServiceNow via the Table API; `sys_id` and number are stored.
6. The assistant: knowledge documents are chunked and embedded; a question is embedded; cosine similarity picks the top chunks; if none pass the threshold we say "not enough information", otherwise the LLM answers from those chunks and the UI shows sources.

**Why these technologies?** FastAPI: fast to build, automatic validation + Swagger docs, async-ready. SQLite: zero setup, single file, perfect for a demo (I'd use PostgreSQL in production).
Vanilla JS: no build tooling, easy to explain. OpenAI-compatible API: provider can be swapped by changing `.env`. SQLite for vectors instead of Chroma/FAISS: fewer dependencies, no Windows install issues,
tiny KB. pytest with mocks: tests run without paying for or needing external services.

**Limitations & future work:** no real authentication/roles; SLA timers and approvals are not implemented; priority matrix is simplified; vector search is brute force (fine for hundreds of chunks, not millions);
no evaluation set for answer quality; no PII redaction before sending text to an LLM; single-process in-memory rate limiter; ServiceNow sync is one-way (no status back-sync / webhook).

---
# Part 3 – Likely questions and answers

### ServiceNow / ITSM
**1. What is ITSM?** The processes and tools an IT team uses to deliver and support IT services – logging issues, fixing them, handling requests and changes – in an organised, measurable way.

**2. Difference between incident, problem and service request?** Incident = something broken, restore it fast. Problem = the underlying cause of repeated incidents. Service request = a standard ask like software installation. Example: VPN down (incident), recurring gateway licence limit (problem), "give me VPN access" (request).

**3. What is a change request and why do we need it?** A controlled way to modify systems. Approval, risk assessment and scheduling prevent changes from causing new incidents.

**4. What is an SLA?** A promised response/resolution time depending on priority. Missing it triggers escalation; ServiceNow tracks it with SLA timers.

**5. How is priority decided?** From impact and urgency. In ServiceNow there is a priority lookup (data lookup rule); in my app it's a matrix in code: impact+urgency 2 → Critical, 3 → High, 4 → Moderate, else Low.

**6. What is USM and how does your project show it?** Using one service-management approach for all departments, not just IT. My request page has IT, HR, Finance and Facilities using the same catalog/workflow/statuses and routing to different fulfilment groups. It demonstrates the principle, not the official product.

**7. What are ServiceNow tables and records?** Data is stored in tables (incident, sc_request, sys_user); each row is a record. Many tables extend the `task` table and inherit fields like number, state, assignment group.

**8. What is a ServiceNow workflow/flow?** An automated sequence of steps/conditions/approvals, built in Flow Designer (or older Workflow Editor), triggered by events such as record creation.

**9. What is the Table API and how did you use it?** A REST API for CRUD on any table. I POST JSON (`short_description`, `description`, `urgency`, `impact`, `category`) to `/api/now/table/incident` with Basic auth, then read `result.sys_id` and `result.number` and store them. Success only if HTTP 201 and those fields exist.

**10. What permissions does the API user need?** Create/read on the incident table – practically the `itil` role. I'd use a dedicated "web service access only" user, not admin (least privilege).

**11. What would you do if ServiceNow returns 403?** The user is authenticated but lacks permission: check roles (`itil`), table ACLs and whether the account is restricted. 401 is credentials; 404 is URL/hibernating instance.

**12. How do you avoid duplicate incidents in ServiceNow?** I store `sn_sys_id` locally and refuse a second push; with a retry after a timeout I warn the user to check first. A production design would use a correlation ID.

### Generative AI / RAG
**13. What is Generative AI?** AI that produces new content such as text. In my project it summarises and classifies tickets and drafts grounded answers.

**14. What is an LLM and what are tokens?** A large model that predicts the next token; tokens are word-pieces. Limits and costs are per token, and the context window limits how much text I can send.

**15. What is prompt engineering? Show an example.** Designing instructions and format. Mine: "You are an ITSM triage assistant. Reply with ONE JSON object with keys summary, category (one of …), impact 1–3, urgency 1–3, steps, resolution." Clear role + strict output format makes parsing reliable.

**16. What is RAG and why use it?** Retrieve relevant internal documents and give them to the LLM so the answer is grounded. Because LLMs don't know private/current company info and may invent it.

**17. Explain your RAG pipeline step by step.** Chunk documents → embed each chunk → store vectors in SQLite. At question time: embed question → cosine similarity against chunks → keep those above a threshold → send top 3 as numbered context with an instruction to answer only from it → return answer plus sources.

**18. What are embeddings and how does similarity work?** Embeddings turn text into vectors capturing meaning. Cosine similarity measures the angle between two vectors: 1 = same direction (similar meaning), 0 = unrelated.

**19. Why chunk documents?** A whole document is too big/unspecific. Small chunks give precise matches, fit the context window and cut cost. Overlap avoids cutting an instruction in half.

**20. How does your app handle "I don't know"?** If no chunk passes the relevance threshold, it returns "knowledge base does not contain enough information" without calling the LLM. The prompt also tells the LLM to answer `INSUFFICIENT_CONTEXT` if the context lacks the answer.

**21. What is a hallucination and how do you reduce it?** An invented answer. I ground answers in retrieved text, forbid outside knowledge in the prompt, use low temperature, show sources, validate JSON, and keep a human in the loop.

**22. RAG vs fine-tuning?** Fine-tuning changes the model's behaviour/style and is costly to update; RAG supplies fresh facts at query time, is cheaper, and cites sources. For changing company documents RAG is the usual first choice.

**23. What happens without an embedding or LLM key?** Without embeddings it falls back to TF-IDF keyword retrieval, labelled "keyword fallback (not semantic)". Without an LLM it returns the retrieved passage labelled "not a generated answer". I never pass fallback output off as AI.

**24. Why didn't you use ChromaDB or FAISS?** For a few hundred chunks a Python loop is enough, it removes dependencies and Windows installation problems, and it is easy to explain. For big data I'd switch to pgvector/FAISS/managed vector DB; only `retrieve()` changes.

**25. How do you make LLM output reliable?** JSON mode where supported, a strict prompt, robust JSON extraction (strip code fences), Pydantic schema validation (types, ranges, allowed categories), and a fallback if anything fails. Critical values like priority are computed by code.

**26. What is an AI agent? Is your app one?** An agent plans and takes actions with tools autonomously. Mine is not – it suggests and a human decides. It could evolve into an agent that, with approval, assigns tickets or resets passwords.

**27. Automation vs AI?** Automation = fixed rules, predictable (routing by category). AI = interprets unstructured text (understanding "my screen is black and the fan is loud"). I combine them.

**28. What risks come with GenAI in ITSM?** Wrong or hallucinated advice, leaking sensitive data to external providers, bias, cost, over-trust. Mitigation: human review, grounding, data masking, audit logs, provider contracts.

**29. How would you evaluate answer quality?** Build a set of questions with expected source documents; measure retrieval hit-rate (is the right doc in the top-k), check faithfulness (answer supported by context), and collect agent thumbs-up/down feedback.

**30. How does ServiceNow itself use GenAI?** ServiceNow offers Now Assist (licensed) for incident/case summarisation, resolution notes, knowledge generation, and virtual agent. My project is an independent prototype of similar ideas, not a copy of those products.

### Project / engineering
**31. Walk me through your architecture.** Browser (HTML/JS) → FastAPI routes → services (incident, RAG, requests, ServiceNow, LLM client) → SQLite; LLM and ServiceNow are external HTTPS calls. Routes are thin; services hold logic; each external dependency is isolated and optional.

**32. How do you handle errors?** Pydantic returns 422 for invalid input; LLM/embedding/ServiceNow failures are converted to safe messages and fallbacks; SQLite errors return a generic 500 and are logged; timeouts are set on every external call.

**33. How do you protect secrets?** They are in `.env` (git-ignored), read via environment variables, sent only in headers, never logged or returned by API (a test checks this), and error messages are sanitised.

**34. What security features are missing?** Real authentication/authorisation, HTTPS, CSRF protection if cookies were used, persistent audit log, distributed rate limiting, PII redaction. I label the demo user clearly.

**35. How do you test it?** 39 pytest tests: priority matrix, fallback behaviour, API validation, RAG retrieval, upload handling, ServiceNow success/401/timeout with mocked HTTP, missing credentials, and that secrets never appear in responses. External services are mocked so tests run offline.

**36. What was the hardest part?** Making AI output trustworthy: parsing/validating LLM JSON, deciding when to say "I don't know", and being honest about fallbacks. (Use your real experience here.)

**37. How would you scale it?** PostgreSQL + pgvector, background workers for embedding, authentication (SSO), caching, queue for ServiceNow sync, observability, containerisation, and CI.

**38. How would you integrate with ServiceNow more deeply?** Two-way sync (webhook/Business Rule → REST Message back), use ServiceNow's Knowledge Base API as the RAG source, OAuth instead of basic auth, and use `correlation_id` for idempotency.

**39. Why does priority not come from the LLM?** Priority drives SLAs and escalations, so it must be predictable and explainable. The LLM suggests impact/urgency; code applies the matrix. Use AI for understanding, rules for policy.

**40. What would you do on your first day in a USM & GenAI team?** Learn the client's ServiceNow instance (tables, catalog, SLAs, workflows), read the knowledge base and typical ticket types, shadow incident handling, and look for high-volume low-complexity tickets where summarisation or knowledge suggestions could help.

---
# Part 4 – Honest positioning (read before the interview)

* Say "prototype", "demo" and "ServiceNow-inspired". Never say "production" or "official USM".
* Say you integrated with ServiceNow **only if you ran a successful call** against your PDI. Otherwise: "I implemented and unit-tested the integration; I could not verify it against a live instance yet."
* Say whether you ran with a real LLM key or in fallback mode.
* Know every file in `app/services/`; be ready to open `rag_service.py` and explain `chunk_text`, `cosine`, and `retrieve`.
* If you don't know something, say what you'd do to find out – that is a good answer.
