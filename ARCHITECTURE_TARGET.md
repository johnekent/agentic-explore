# Architecture Target

Purpose: recommended tools, skills, and agents for refactoring Agent Lab toward the capability-first architecture.

If memory is lost: start here, then read `MIGRATION_PLAN.md` for the next actions.

## Capabilities and Tools (current)

Notes:
- Tools perform side effects only.
- Skills orchestrate tools and apply decision logic.
- Capabilities map to tools via `capabilities.yaml` and `agentlab/orchestrator/registry.py`.

### Core I/O and Ops
- `cap.ops_logging` -> `ops_log`
- `cap.file_read` -> `read_file`
- `cap.file_write` -> `write_file`
- `cap.file_list` -> `list_files`
- `cap.http_fetch` -> `fetch_url`
- `cap.web_search` -> `search_web`
- `cap.llm_generate` -> `llm_generate`

### SQLite and Indexing
- `cap.query_rows` -> `query_rows`
- `cap.persist_rows` -> `persist_rows`
- `cap.update_rows` -> `update_rows` (UPDATE only)
- `cap.delete_rows` -> `delete_rows` (DELETE only, guarded)
- `cap.index_document` -> `index_document` (legacy `cap.indexing` still exists)
- `cap.index_idea` -> `index_idea`
- `cap.db_migrate` -> `migrate_db`
Notes:
- `documents` include asset references (`asset_type`, `asset_ref`, `asset_path`) plus `content_path` to MD.
- `item_processing` captures per-document action history (fetch, summary, index, embed).

### Matching, Planning, and Review
- `cap.match_idea_to_docs` -> `match_idea_to_docs`
- `cap.match_doc_to_ideas` -> `match_doc_to_ideas`
- `cap.plan_match_execution` -> `plan_match_execution`
- `cap.plan_backlog` -> `plan_backlog`
- `cap.plan_update_status` -> `plan_update_status`
- `cap.plan_assign_agent` -> `plan_assign_agent`
- `cap.judge_validity` -> `judge_validity`
- `cap.build_dashboard` -> `build_dashboard`
- `cap.cleanup_db` -> `cleanup_db`
- `cap.delete_all_data` -> `delete_all_data`
- `cap.list_document_duplicates` -> `list_document_duplicates`
- `cap.delete_duplicate_documents` -> `delete_duplicate_documents`

### Vector Search
- `cap.vector_index` -> `vector_index`
- `cap.vector_query` -> `vector_query`
- `cap.vector_stats` -> `vector_stats`

### Environment Validation
- `cap.env_check_db` -> `env_check_db`
- `cap.env_check_llm` -> `env_check_llm`

### Optional (if kept)
- `cap.local_exec` -> `local_exec` (guarded, for controlled scripts)

## Skills (current)

Each skill should declare required/optional capabilities in its frontmatter.

### Workspace / Runs
- `init_workspace` -> ensure workspace + migrate DB
  - caps: `cap.file_write`, `cap.db_migrate`, `cap.ops_logging`
- `list_runs` -> list runs from SQLite
  - caps: `cap.query_rows`, `cap.ops_logging`
- `load_run` -> load a run from SQLite
  - caps: `cap.query_rows`, `cap.ops_logging`

### Skills Lifecycle
- `list_skills` -> enumerate `skills/*/SKILL.md`
  - caps: `cap.file_list`, `cap.file_read`, `cap.ops_logging`
- `create_skill` -> create new `skills/<name>/SKILL.md`
  - caps: `cap.file_write`, `cap.ops_logging`

### Search, Fetch, Index
- `search_web_sources` -> perform web search and write run metadata
  - caps: `cap.web_search`, `cap.persist_rows`, `cap.ops_logging`
- `fetch_documents_from_run` -> fetch URLs for a run
  - caps: `cap.file_write`, `cap.http_fetch`, `cap.query_rows`, `cap.update_rows`, `cap.llm_generate`, `cap.ops_logging`
- `fetch_urls` -> fetch URLs and write documents
  - caps: `cap.query_rows`, `cap.http_fetch`, `cap.file_write`, `cap.llm_generate`, `cap.ops_logging`
- `index_documents_from_run` -> index fetched docs
  - caps: `cap.query_rows`, `cap.indexing`, `cap.update_rows`, `cap.ops_logging`

### Ideas
- `create_idea` -> write idea file and index
  - caps: `cap.file_write`, `cap.index_idea`, `cap.ops_logging`

### Matching and Judging
- `match_all_ideas` -> compute matches per idea
  - caps: `cap.query_rows`, `cap.match_idea_to_docs`, `cap.ops_logging`
- `match_all_docs` -> compute matches per doc
  - caps: `cap.query_rows`, `cap.match_doc_to_ideas`, `cap.ops_logging`
- `match_single_idea` -> compute matches for one idea
  - caps: `cap.match_idea_to_docs`, `cap.ops_logging`
- `match_single_doc` -> compute matches for one doc
  - caps: `cap.match_doc_to_ideas`, `cap.ops_logging`
- `judge_validity` -> compute validity failures
  - caps: `cap.judge_validity`, `cap.file_write`, `cap.ops_logging`
- `build_dashboard` -> generate `dashboard.md`
  - caps: `cap.build_dashboard`, `cap.ops_logging`

### Planning
- `plan_match_execution` -> create task from match
  - caps: `cap.plan_match_execution`, `cap.ops_logging`
- `plan_backlog` -> list tasks
  - caps: `cap.plan_backlog`, `cap.ops_logging`
- `plan_update_status` -> update task status
  - caps: `cap.plan_update_status`, `cap.ops_logging`
- `plan_assign_agent` -> update assignment
  - caps: `cap.plan_assign_agent`, `cap.ops_logging`

### Maintenance
- `list_document_duplicates` -> list duplicates
  - caps: `cap.list_document_duplicates`, `cap.ops_logging`
- `delete_duplicate_documents` -> delete duplicates
  - caps: `cap.delete_duplicate_documents`, `cap.ops_logging`
- `delete_all_data` -> delete all DB rows (optionally delete content files)
  - caps: `cap.delete_all_data`, `cap.ops_logging`
- `resummarize_documents` -> update title/summary
  - caps: `cap.query_rows`, `cap.file_read`, `cap.llm_generate`, `cap.update_rows`, `cap.ops_logging`
- `embeddings_build` -> build vector index
  - caps: `cap.vector_index`, `cap.ops_logging`
- `search_semantic` -> semantic search
  - caps: `cap.vector_query`, `cap.query_rows`, `cap.ops_logging`
- `embeddings_status` -> embedding counts
  - caps: `cap.vector_stats`, `cap.ops_logging`

### Utility
- `read_file` -> read file content
  - caps: `cap.file_read`, `cap.ops_logging`
- `query_rows` -> read-only SQL query
  - caps: `cap.query_rows`, `cap.ops_logging`
- `validate_environment` -> validate DB + LLM readiness
  - caps: `cap.env_check_db`, `cap.env_check_llm`, `cap.ops_logging`
- `summarize_with_fallback` -> centralized summarize + retry + heuristic fallback
  - uses: `cap.llm_generate`, `cap.ops_logging`

## Agents (recommended)

### Planner / Orchestrator
- Role: decompose goals, select skills, enforce policy.
- Allowed caps: all read-only + `cap.ops_logging` + a minimal write set.

### Researcher
- Role: search + fetch + summarize.
- Allowed caps: `cap.web_search`, `cap.http_fetch`, `cap.llm_generate`, `cap.file_write`, `cap.ops_logging`.

### Indexer
- Role: indexing documents and ideas, embeddings.
- Allowed caps: `cap.index_document`, `cap.index_idea`, `cap.persist_rows`, `cap.ops_logging`.

### Matcher
- Role: compute matches.
- Allowed caps: `cap.query_rows`, `cap.persist_rows`, `cap.ops_logging`.

### Planner Executor
- Role: create/update tasks.
- Allowed caps: `cap.query_rows`, `cap.persist_rows`, `cap.update_rows`, `cap.ops_logging`.

### Reviewer
- Role: judge validity, build dashboards.
- Allowed caps: `cap.query_rows`, `cap.file_write`, `cap.ops_logging`.

### Maintenance Operator (guarded)
- Role: delete duplicates, cleanup.
- Allowed caps: `cap.delete_rows`, `cap.file_write`, `cap.ops_logging`.
