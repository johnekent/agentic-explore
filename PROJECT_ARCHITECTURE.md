# Agent Lab - Project and Architecture

Purpose: a single, shareable overview of the project intent, current architecture, and near-term migration plan.

If you need the original docs, this file consolidates:
- `PROJECT_OVERVIEW.md`
- `ARCHITECTURE_TARGET.md`
- `MIGRATION_PLAN.md`

---

## Purpose

AgentLab is a local-first, human-in-the-loop agent system for applied research teams. The goal is to
augment human sensemaking, not replace it. Humans remain the final judges on relevance, quality, and
decisions.

The system continuously:
- searches for external information,
- fetches and normalizes content,
- summarizes and indexes it,
- matches research findings to human ideas,
- supports human review, scoring, and correction,
- plans and tracks execution.

---

## Core Principles

1. Local-first: runs on a developer laptop, SQLite for state, Markdown as source of record.
2. Human-legible artifacts: docs, ideas, and matches are editable Markdown with YAML frontmatter.
3. Strong provenance: sources, URLs, and timestamps are preserved.
4. Separation of concerns: tools do side effects, skills orchestrate, services are shared across UI/CLI/MCP.
5. Human-in-the-loop scoring: agents propose; humans decide; feedback loops into learning.

See `GUIDING_PRINCIPLES.md` for the full constitution-level rules.

---

## System Model

### Artifacts
- Document: internet-sourced or synthesized content, stored as Markdown.
- Idea / Problem: one idea per record, stored as Markdown.
- Match: idea-to-document relationship with score (0-10) and reasons.
- Task: execution plan linked to a match (SQLite table).

### Storage
- Markdown + YAML frontmatter are the system of record.
- SQLite is the searchable index and relational glue.
- `item_processing` records per-document stages: fetch, summary, index, embed.

### Interfaces
- CLI: `agentlab ...`
- Streamlit UI: `ui.py`
- MCP server: `agentlab-mcp`

### Architecture Layers
- Interfaces call services.
- Services call skills (no direct side effects).
- Skills use the orchestrator to resolve capabilities to tools.
- Tools perform side effects and wrap pipeline logic.
- Markdown files and SQLite store artifacts and indexes.

---

## Current Core Loop

1. Search web sources (run stored in SQLite).
2. Fetch documents (write Markdown, log fetch status).
3. Summarize documents (title + summary, update Markdown/DB).
4. Index documents (SQLite searchable index).
5. Match ideas to documents, with human review and scoring.
6. Plan and track execution.

---

## Capabilities and Tools (current summary)

Core capabilities already in use:
- File I/O: `cap.file_read`, `cap.file_write`, `cap.file_list`
- Web: `cap.web_search`, `cap.http_fetch`
- Summarize: `cap.summarize_document`
- SQLite: `cap.query_rows`, `cap.persist_rows`, `cap.update_rows`, `cap.delete_rows`, `cap.db_migrate`
- Indexing: `cap.index_document`, `cap.index_idea`
- Ops: `cap.ops_logging`
- Planning: `cap.plan_match_execution`, `cap.plan_backlog`, `cap.plan_update_status`, `cap.plan_assign_agent`
- Matching: `cap.match_idea_to_docs`, `cap.match_doc_to_ideas`

See `capabilities.yaml` for the authoritative mapping.

---

## Skills (current summary)

Core skills currently active:
- search_web_sources
- fetch_documents_from_run
- fetch_urls
- summarize_documents
- index_documents_from_run
- create_idea
- match_all_ideas / match_all_docs
- plan_match_execution / plan_backlog / plan_update_status / plan_assign_agent
- build_dashboard
- match_learning

See `skills/*/SKILL.md` for skill definitions.

---

## Roadmap and Migration Plan

The system is already migrated to tool-driven side effects and skill-based orchestration. Remaining
gaps are mostly in UI/CLI cleanup and test coverage. The recommended sequence:

1) Tool and capability gaps (done)
2) Skills wrapping pipeline logic (done)
3) Services call skills only (done)
4) UI/CLI eliminate direct DB/file I/O (done)
5) Expand tool/skill tests (active)

### Planned Enhancements

Short-term priorities:
- Match explanations and match-quality analytics
- Entity resolution and canonicalization
- Lightweight research memory and cycles
- Taxonomy governance workflows
- Batch operations (fetch/summarize/classify)

These are tracked as phases in the original `ARCHITECTURE_TARGET.md` and can be expanded again if
needed.

---

## Success Metrics (to track)

Match quality:
- Precision/recall on human-scored matches
- Explanation quality ratings
- Human override rate

System performance:
- Documents processed per week
- Matches generated/reviewed per week
- End-to-end cycle time (search -> fetch -> match -> review)

Learning:
- Match rule coverage and updates
- Research memory usage rates
- Taxonomy stability

---

## Constraints (non-negotiable)

- Markdown + YAML stays as the source of truth.
- Explainable matching remains the default (no opaque embeddings-only system).
- Human review gates are required.
- Changes must be incremental and reversible.

---

## Notes for Contributors

- If you need detailed target-state architecture, expand this file or re-split it.
- Keep the quickstart and operational details in `README.md`.
- Keep architectural rules in `GUIDING_PRINCIPLES.md`.
