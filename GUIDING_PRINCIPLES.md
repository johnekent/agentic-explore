# Guiding Principles for a Capability‑First Agentic System

> **Purpose**: This document defines the architectural rules of the system. It is written to be
> - **Human‑readable** (for architects, reviewers, and operators)
> - **Model‑usable** (for Codex / LLMs generating or modifying code)
>
> Treat this file as a *constitution*: code, prompts, and agents should conform to it unless there is an explicit, documented exception.

---

## 1. Core Separation of Responsibilities

### 1.1 Agents decide, tools act
- **Agents** perform reasoning, planning, evaluation, and choice.
- **Tools** perform actions with side effects (I/O, APIs, persistence, execution).

> If it touches the outside world, it is a **tool**.
> If it decides *whether* or *how* to do something, it is an **agent or skill**.

### 1.2 Skills are reusable decision procedures
- A **skill** is a reusable, composable unit of reasoning or workflow.
- Skills may orchestrate multiple steps and tool calls.
- Skills should not directly embed infrastructure assumptions.

---

## 2. Capability‑First Design

### 2.1 Capabilities are the contract
- Skills declare **capabilities**, not tool names.
- Capabilities represent *what must be possible*, not *how it is done*.

Examples:
- `cap.web_search`
- `cap.read_documents`
- `cap.persist_rows`
- `cap.code_execution`

### 2.2 Orchestrator maps capabilities → tools
- A central **orchestrator (or planner agent)** resolves capabilities to concrete tools.
- Mapping is based on:
  - MCP metadata
  - environment policy
  - cost / latency / trust tier

> Tool selection is an implementation detail, not skill logic.

### 2.3 Capabilities are stable; tools are swappable
- Capabilities should change rarely.
- Tools may change frequently (vendor, API, performance).

This enables portability across environments without rewriting skills.

---

## 3. Least Privilege and Safety

### 3.1 Least privilege by default
- Skills declare **only the capabilities they require**.
- Orchestrator grants access to tools strictly through those capabilities.

### 3.2 Tools enforce safety
- Tools are responsible for:
  - permission checks
  - rate limits
  - audit logs
  - idempotency (where possible)
  - optional human‑in‑the‑loop approval

> Skills and agents should assume tools may refuse execution.

---

## 4. Tool Design Rules

Tools MUST:
- Be deterministic where possible
- Have explicit input/output schemas
- Perform a single, well‑defined action
- Return structured errors (not prose)

Tools SHOULD:
- Be small and composable
- Be independently testable
- Avoid hidden side effects

Tools MUST NOT:
- Contain business logic or decision trees
- Perform multi‑step workflows

---

## 5. Skill Design Rules

Skills SHOULD:
- Be reusable across agents
- Produce structured outputs
- Validate tool outputs before proceeding
- Handle branching, retries, and fallback logic

Skills MAY:
- Call multiple tools
- Call other skills
- Perform pure reasoning with no tools

Skills MUST:
- Declare required and optional capabilities
- Avoid hard‑coding tool names unless explicitly justified

---

## 6. Orchestrator Responsibilities

The orchestrator is responsible for:
- Decomposing goals into tasks
- Assigning tasks to agents or skills
- Mapping capabilities → tools
- Managing state, retries, and timeouts
- Enforcing policies (cost, safety, environment)

Agents SHOULD NOT:
- Select tools based on vendor or implementation
- Manage global execution state

---

## 7. Agent Roles and Specialization

Prefer **many simple, specialized agents** over one complex agent.

Common roles:
- **Planner / Orchestrator** – decomposes goals, routes work
- **Researcher** – gathers and summarizes information
- **Analyst** – performs structured reasoning or calculations
- **Writer** – drafts artifacts
- **Reviewer / Critic** – validates correctness and quality
- **Executor** – performs approved high‑impact actions

Each agent:
- Has a clear role
- Uses a limited set of skills
- Operates under explicit capability constraints

---

## 8. Naming Conventions (Mandatory)

### 8.1 Tools
- Verb‑first, concrete action
- Examples:
  - `search_web`
  - `query_sql`
  - `write_file`
  - `send_email`

### 8.2 Skills
- Verb + domain intent
- Examples:
  - `rank_internships`
  - `draft_report`
  - `deduplicate_records`

### 8.3 Capabilities
- Stable nouns, namespaced
- Examples:
  - `cap.web_search`
  - `cap.persistence`
  - `cap.messaging`

---

## 9. Observability and Evaluation

Every run SHOULD be observable and replayable:
- Log prompts or prompt hashes
- Log tool calls with inputs/outputs
- Log decisions and branching
- Store final artifacts

Testing guidance:
- **Tools** → unit tests
- **Skills** → evals with mocked tools
- **Agents** → scenario‑based tests

---

## 10. Cost, Latency, and Risk as First‑Class Constraints

The system MUST:
- Track and budget LLM and tool usage
- Prefer read‑only actions first
- Gate high‑impact tools behind review or approval

Failure modes must be explicit and recoverable.

---

## 11. Evolution Rules

When changing the system:
- Prefer swapping tool implementations behind a capability
- Prefer refining skills over creating new agents
- Document any violation of these principles explicitly

> Architectural consistency is more valuable than short‑term convenience.

---

## 12. Summary (For Models)

- Agents decide, tools act
- Skills are reusable decision workflows
- Capabilities are the stable contract
- Orchestrator maps capabilities to tools
- Least privilege always
- Names must reveal intent

This document defines the expected structure of all agentic code and prompts in this repository.

