# Migration Plan

Purpose: refactor `agentlab/services/operations.py` so all side effects are performed through tools and orchestrated by skills.

If memory is lost: read `ARCHITECTURE_TARGET.md` first, then execute the Next Steps in this file.

## Summary of What Remains

`agentlab/services/operations.py` now delegates to skills for side effects. Remaining gaps are mostly in the UI/CLI (direct DB/file I/O) and test coverage for the new tools/skills.

## Target Mapping (operations.py -> skills/tools)

- `init_db` -> skill `init_workspace` -> tool `migrate_db`
- `list_runs` -> skill `list_runs` -> tool `query_rows`
- `load_run` -> skill `load_run` -> tool `query_rows`
- `list_skills` -> skill `list_skills` -> tool `list_files` + `read_file`
- `create_skill` -> skill `create_skill` -> tool `write_file`
- `list_document_duplicates` -> skill `list_document_duplicates` -> tool `list_document_duplicates`
- `delete_duplicate_documents` -> skill `delete_duplicate_documents` -> tool `delete_duplicate_documents`
- `search_local` -> skill `search_local` -> tools `query_rows` (local ranking in skill)
- `build_embeddings` -> skill `embeddings_build` -> tool `vector_index` (new)
- `search_semantic` -> skill `search_semantic` -> tool `vector_query` (new)
- `embeddings_status` -> skill `embeddings_status` -> tool `vector_stats` (new)
- `fetch_urls` -> skill `fetch_urls` -> tools `fetch_url`, `write_file`
- `summarize_documents` -> skill `summarize_documents` -> tools `read_file`, `write_file`, `summarize_document`, `update_rows`
- `resummarize_documents` -> skill `resummarize_documents` -> tools `read_file`, `llm_generate`, `update_rows`
- `index_docs` -> skill `index_documents_from_run` -> tool `index_document`
- `create_idea` -> skill `create_idea` -> tools `write_file`, `index_idea`
- `match_all_ideas` -> skill `match_all_ideas` -> tool `match_idea_to_docs`
- `match_all_docs` -> skill `match_all_docs` -> tool `match_doc_to_ideas`
- `match_single_idea` -> skill `match_single_idea` -> tool `match_idea_to_docs`
- `match_single_doc` -> skill `match_single_doc` -> tool `match_doc_to_ideas`
- `match_learning` -> skill `match_learning` -> tools `query_rows`, `read_file`, `write_file`, `persist_rows`
- `judge_validity_report` -> skill `judge_validity` -> tool `judge_validity` + `write_file`
- `build_dashboard` -> skill `build_dashboard` -> tool `build_dashboard`
- `plan_match` -> skill `plan_match_execution` -> tool `plan_match_execution`
- `plan_backlog` -> skill `plan_backlog` -> tool `plan_backlog`
- `plan_update` -> skill `plan_update_status` -> tool `plan_update_status`
- `plan_assign` -> skill `plan_assign_agent` -> tool `plan_assign_agent`
- `cleanup_db` -> skill `cleanup_db` -> tool `cleanup_db`
- `delete_all_data` -> skill `delete_all_data` -> tool `delete_all_data`
- `demo_seed` -> skill `demo_seed` -> tools `write_file`, `persist_rows`, `index_document`, `index_idea`

## Capabilities to Add (gap list)

Add these to `capabilities.yaml`, with tools in `agentlab/tools/*`:
- `cap.file_list` -> `list_files` (done)
- `cap.db_migrate` -> `migrate_db` (done)
- `cap.update_rows` -> `update_rows` (done)
- `cap.delete_rows` -> `delete_rows` (done)
- `cap.index_idea` -> `index_idea` (done)
- `cap.vector_index` -> `vector_index` (done)
- `cap.vector_query` -> `vector_query` (done)
- `cap.vector_stats` -> `vector_stats` (done)
- `cap.delete_all_data` -> `delete_all_data` (done)

## Next Steps (recommended order)

1) Add the missing tools and capabilities listed above. (done)
2) Build skills in `agentlab/skills_runtime/` that wrap existing pipeline logic but only call tools. (done)
3) Refactor `agentlab/services/operations.py` to call skills only (no direct side effects). (done)
4) Update `agentlab/cli.py` and `ui.py` to call services or skills; remove direct DB and file I/O. (done)
5) Add tests for tools (unit) and skills (mocked tools) to preserve behavior. (next)

## Notes

- Keep tools small and deterministic; do not embed workflow logic in tools.
- Prefer skills for branching, retries, and fallbacks.
- Any remaining direct I/O in UI or CLI should be treated as a migration gap.
- Design choice: matching, planning, dedup, and cleanup now go through tools that wrap existing pipeline functions. This avoids reimplementing DB logic in skills while keeping side effects in tools.
- Design choice: UI table rendering now uses a read-only `query_rows` skill to avoid direct SQLite access.
- Open gap: the UI Gantt chart still writes `gantt.svg` directly; consider routing through a file-write tool or alternate rendering path.
- New addition: environment validation tools/skill (`env_check_db`, `env_check_llm`, `validate_environment`) to gate LLM-dependent workflows.
- Environment validation can auto-start Ollama if it is configured but not running.
- Environment validation will attempt Docker-based Ollama startup if the Ollama binary is missing and Docker is available.
- Windows note: Docker Desktop must be running for Docker-based startup to succeed.
- Status logging: long-running skills now emit `agent_interactions` entries via ops logging, and UI/CLI can attach live log callbacks for progress visibility.
- Summarization fallback: adaptive chunking based on `OLLAMA_TIMEOUT_S` to reduce timeouts (map-reduce style).
- Runs now persist in SQLite (`runs` table). `workspace/runs` is deprecated for new data.
- Document actions now record per-document stages in `item_processing` (fetch, summary, index, embed).
