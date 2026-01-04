# Architecture Target (v2)

Purpose: recommended tools, skills, and agents for refactoring Agent Lab toward the capability-first architecture with enhanced learning, memory, and match quality.

If memory is lost: start here, then read `MIGRATION_PLAN.md` for the next actions.

---

## Design Philosophy Updates

This version adds:
- **Match learning and explanation** to improve relevance over time
- **Entity resolution and canonicalization** to reduce duplication and track concepts
- **Research memory** for institutional knowledge and avoiding repeated work
- **Taxonomy governance** to prevent label chaos
- **Batch operations** for performance at scale
- **Prototype scaffolding** (plans first, code later) for safer agent-generated implementations

---

## Capabilities and Tools (current + planned)

Notes:
- Tools perform side effects only.
- Skills orchestrate tools and apply decision logic.
- Capabilities map to tools via `capabilities.yaml` and `agentlab/orchestrator/registry.py`.

### Core I/O and Ops (current)
- `cap.ops_logging` -> `ops_log`
- `cap.file_read` -> `read_file`
- `cap.file_write` -> `write_file`
- `cap.file_list` -> `list_files`
- `cap.http_fetch` -> `fetch_url`
- `cap.web_search` -> `search_web`
- `cap.llm_generate` -> `llm_generate`
- `cap.summarize_document` -> `summarize_document`

### SQLite and Indexing (current)
- `cap.query_rows` -> `query_rows`
- `cap.persist_rows` -> `persist_rows`
- `cap.update_rows` -> `update_rows` (UPDATE only)
- `cap.delete_rows` -> `delete_rows` (DELETE only, guarded)
- `cap.index_document` -> `index_document`
- `cap.index_idea` -> `index_idea`
- `cap.db_migrate` -> `migrate_db`

Notes:
- `documents` include asset references (`asset_type`, `asset_ref`, `asset_path`) plus `content_path` to MD.
- **NEW**: `documents.canonical_entity_id` links related docs about the same entity.
- **NEW**: `documents.fetch_version` tracks updates to the same source over time.
- `item_processing` captures per-document action history (fetch, summary, index, embed).

### Matching, Planning, and Review (current + planned)
- `cap.match_idea_to_docs` -> `match_idea_to_docs`
- `cap.match_doc_to_ideas` -> `match_doc_to_ideas`
- **PLANNED**: `cap.match_explain` -> `match_explain` (generate detailed match reasoning)
- **PLANNED**: `cap.match_learn` -> `match_learn` (analyze patterns in human-scored matches)
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

Notes (planned):
- `matches.explanation_text` stores detailed reasoning for match score.
- `matches.human_override` flag tracks when humans change agent scores.
- `matches.feedback_incorporated` tracks if human feedback was used for learning.

### Entity Resolution and Canonicalization (planned)
- `cap.entity_resolve` -> `entity_resolve` (canonicalize company names, tech terms, people)
- `cap.entity_link` -> `entity_link` (link documents to canonical entities)
- `cap.entity_query` -> `entity_query` (retrieve all docs about an entity)

Notes (planned):
- New `entities` table: `id`, `canonical_name`, `entity_type` (company/technology/person/concept), `aliases`, `first_seen`, `last_updated`
- New `document_entities` table: links documents to entities (many-to-many)

### Research Memory and Learning (planned)
- `cap.memory_store` -> `memory_store` (store research insight, pattern, or dead end)
- `cap.memory_query` -> `memory_query` (retrieve relevant memories for current task)
- `cap.memory_update` -> `memory_update` (update memory with new evidence)

Notes (planned):
- New `research_memory` table: `id`, `memory_type` (insight/pattern/dead_end/decision), `content`, `evidence_refs` (JSON), `confidence`, `created_at`, `last_validated`
- New `research_cycles` table: tracks complete research ? match ? review cycles with outcomes

### Taxonomy Governance (planned)
- `cap.taxonomy_propose` -> `taxonomy_propose` (agent proposes new term with rationale)
- `cap.taxonomy_approve` -> `taxonomy_approve` (human approves proposed term)
- `cap.taxonomy_merge` -> `taxonomy_merge` (merge similar terms)
- `cap.taxonomy_deprecate` -> `taxonomy_deprecate` (mark term as deprecated)
- `cap.taxonomy_validate` -> `taxonomy_validate` (check for drift, overlaps, unused terms)

Notes (planned):
- New `taxonomy_proposals` table: `id`, `taxonomy_type`, `proposed_term`, `rationale`, `example_usage`, `status` (pending/approved/rejected), `proposer` (agent/human)
- Taxonomy YAML files now include `version`, `changelog`, `deprecated_terms`

### Batch Operations (planned)
- `cap.batch_summarize` -> `batch_summarize` (summarize multiple docs in one LLM call)
- `cap.batch_classify` -> `batch_classify` (classify multiple docs in one LLM call)
- `cap.batch_fetch` -> `batch_fetch` (parallel HTTP fetches with rate limiting)

### Prototype Scaffolding (planned)
- `cap.prototype_plan` -> `prototype_plan` (generate implementation plan, not code)
- `cap.prototype_scaffold` -> `prototype_scaffold` (create basic project structure)
- `cap.prototype_validate` -> `prototype_validate` (check plan feasibility)

Notes (planned):
- New `prototypes` table: `id`, `match_id`, `plan_content`, `status` (planned/scaffolded/implemented/deployed), `tech_stack`, `effort_estimate`, `security_reviewed`

### Vector Search
- `cap.vector_index` -> `vector_index`
- `cap.vector_query` -> `vector_query`
- `cap.vector_stats` -> `vector_stats`

### Analytics and Reporting (planned)
- `cap.analytics_match_quality` -> `analytics_match_quality` (analyze match score distributions, patterns)
- `cap.analytics_source_quality` -> `analytics_source_quality` (which sources produce good matches?)
- `cap.analytics_taxonomy_usage` -> `analytics_taxonomy_usage` (label usage stats, drift detection)

### Environment Validation
- `cap.env_check_db` -> `env_check_db`
- `cap.env_check_llm` -> `env_check_llm`

### Optional (if kept)
- `cap.local_exec` -> `local_exec` (guarded, for controlled scripts)

---

## Skills (current + planned)

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

### Search, Fetch, Index (current + planned)
- `search_web_sources` -> perform web search and write run metadata
  - caps: `cap.web_search`, `cap.persist_rows`, `cap.ops_logging`
- `fetch_documents_from_run` -> fetch URLs for a run
  - caps: `cap.file_write`, `cap.http_fetch`, `cap.query_rows`, `cap.update_rows`, `cap.ops_logging`
  - **PLANNED**: Use `cap.batch_fetch` for parallel fetching when batch size > 5
- `fetch_urls` -> fetch URLs and write documents
  - caps: `cap.query_rows`, `cap.http_fetch`, `cap.file_write`, `cap.ops_logging`
  - **PLANNED**: Use `cap.batch_summarize` for efficient summarization
- `summarize_documents` -> summarize fetched docs into title + summary
  - caps: `cap.file_read`, `cap.file_write`, `cap.summarize_document`, `cap.update_rows`, `cap.ops_logging`
- `index_documents_from_run` -> index fetched docs
  - caps: `cap.query_rows`, `cap.indexing`, `cap.update_rows`, `cap.ops_logging`
  - **PLANNED**: Call `entity_resolve_documents` after indexing

### Entity Resolution (planned)
- `entity_resolve_documents` -> extract and canonicalize entities from documents
  - caps: `cap.query_rows`, `cap.entity_resolve`, `cap.entity_link`, `cap.llm_generate`, `cap.persist_rows`, `cap.ops_logging`
- `entity_link_document` -> manually link document to entity
  - caps: `cap.entity_link`, `cap.ops_logging`
- `entity_list_documents` -> list all docs about an entity
  - caps: `cap.entity_query`, `cap.ops_logging`
- `entity_merge` -> merge duplicate entities
  - caps: `cap.query_rows`, `cap.update_rows`, `cap.entity_link`, `cap.ops_logging`

### Ideas (current + planned)
- `create_idea` -> write idea file and index
  - caps: `cap.file_write`, `cap.index_idea`, `cap.ops_logging`
  - **PLANNED**: Include `priority`, `strategic_alignment`, `effort_estimate` in frontmatter

### Matching and Judging (current + planned)
- `match_all_ideas` -> compute matches per idea
  - caps: `cap.query_rows`, `cap.match_idea_to_docs`, `cap.persist_rows`, `cap.ops_logging`
  - **PLANNED**: Use `cap.match_explain` to generate and store match explanations
- `match_all_docs` -> compute matches per doc
  - caps: `cap.query_rows`, `cap.match_doc_to_ideas`, `cap.persist_rows`, `cap.ops_logging`
  - **PLANNED**: Use `cap.match_explain` to generate and store match explanations
- `match_single_idea` -> compute matches for one idea
  - caps: `cap.match_idea_to_docs`, `cap.ops_logging`
  - **PLANNED**: Use `cap.match_explain`
- `match_single_doc` -> compute matches for one doc
  - caps: `cap.match_doc_to_ideas`, `cap.ops_logging`
  - **PLANNED**: Use `cap.match_explain`
- `match_learning` -> analyze human-scored matches and extract patterns
  - caps: `cap.query_rows`, `cap.persist_rows`, `cap.file_read`, `cap.file_write`, `cap.ops_logging`
  - Run this after batch of human reviews to improve future matching
- **PLANNED**: `match_explain_detail` -> generate detailed explanation for a specific match
  - caps: `cap.match_explain`, `cap.query_rows`, `cap.ops_logging`
- **PLANNED**: `match_quality_report` -> generate report on match quality trends
  - caps: `cap.analytics_match_quality`, `cap.query_rows`, `cap.file_write`, `cap.ops_logging`
- `judge_validity` -> compute validity failures
  - caps: `cap.judge_validity`, `cap.file_write`, `cap.ops_logging`
- `build_dashboard` -> generate `dashboard.md`
  - caps: `cap.build_dashboard`, `cap.ops_logging`

### Research Memory (planned)
- `memory_store_insight` -> store research insight or dead end
  - caps: `cap.memory_store`, `cap.ops_logging`
- `memory_query_relevant` -> retrieve memories relevant to current research
  - caps: `cap.memory_query`, `cap.query_rows`, `cap.ops_logging`
- `memory_update_evidence` -> update memory with new supporting/contradicting evidence
  - caps: `cap.memory_update`, `cap.query_rows`, `cap.ops_logging`
- `research_cycle_complete` -> mark research cycle as complete and extract learnings
  - caps: `cap.persist_rows`, `cap.memory_store`, `cap.query_rows`, `cap.ops_logging`

### Taxonomy Governance (planned)
- `taxonomy_propose_term` -> agent proposes new taxonomy term
  - caps: `cap.taxonomy_propose`, `cap.persist_rows`, `cap.ops_logging`
- `taxonomy_review_proposals` -> list pending taxonomy proposals for human review
  - caps: `cap.query_rows`, `cap.ops_logging`
- `taxonomy_approve_term` -> human approves proposed term
  - caps: `cap.taxonomy_approve`, `cap.update_rows`, `cap.file_write`, `cap.ops_logging`
- `taxonomy_validate_health` -> check taxonomy for drift, overlaps, unused terms
  - caps: `cap.taxonomy_validate`, `cap.query_rows`, `cap.analytics_taxonomy_usage`, `cap.file_write`, `cap.ops_logging`
- `taxonomy_merge_terms` -> merge similar or duplicate terms
  - caps: `cap.taxonomy_merge`, `cap.update_rows`, `cap.file_write`, `cap.ops_logging`

### Prototype Generation (planned)
- `prototype_plan_create` -> generate implementation plan (NOT code) for a match
  - caps: `cap.prototype_plan`, `cap.query_rows`, `cap.persist_rows`, `cap.llm_generate`, `cap.ops_logging`
  - Output: detailed plan with tech stack, architecture, milestones, risks
- `prototype_plan_review` -> human reviews and approves/rejects plan
  - caps: `cap.query_rows`, `cap.update_rows`, `cap.ops_logging`
- `prototype_scaffold_create` -> create basic project structure from approved plan
  - caps: `cap.prototype_scaffold`, `cap.query_rows`, `cap.file_write`, `cap.ops_logging`
  - Creates: directory structure, config files, README, basic scaffolding (NO complex logic)
- `prototype_validate_security` -> check prototype for security concerns
  - caps: `cap.prototype_validate`, `cap.query_rows`, `cap.file_read`, `cap.ops_logging`

### Planning
- `plan_match_execution` -> create task from match
  - caps: `cap.plan_match_execution`, `cap.ops_logging`
- `plan_backlog` -> list tasks
  - caps: `cap.plan_backlog`, `cap.ops_logging`
- `plan_update_status` -> update task status
  - caps: `cap.plan_update_status`, `cap.ops_logging`
- `plan_assign_agent` -> update assignment
  - caps: `cap.plan_assign_agent`, `cap.ops_logging`

### Analytics and Reporting (planned)
- `analytics_source_performance` -> which sources/domains produce high-quality matches?
  - caps: `cap.analytics_source_quality`, `cap.query_rows`, `cap.file_write`, `cap.ops_logging`
- `analytics_match_patterns` -> what patterns correlate with high human scores?
  - caps: `cap.analytics_match_quality`, `cap.query_rows`, `cap.file_write`, `cap.ops_logging`
- `analytics_research_velocity` -> how fast are we processing ideas ? prototypes?
  - caps: `cap.query_rows`, `cap.file_write`, `cap.ops_logging`

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

---

## Agents (recommended + new)

### Planner / Orchestrator
- **Role**: decompose goals, select skills, enforce policy.
- **Allowed caps**: all read-only + `cap.ops_logging` + minimal write set.
- **NEW responsibilities**:
  - Query research memory before starting new research
  - Decide when to trigger match learning
  - Coordinate taxonomy governance workflow

### Researcher
- **Role**: search + fetch + summarize + entity extraction.
- **Allowed caps**: `cap.web_search`, `cap.http_fetch`, `cap.llm_generate`, `cap.file_write`, `cap.batch_fetch`, `cap.batch_summarize`, `cap.ops_logging`.
- **NEW responsibilities**:
  - Check for duplicate/stale content before fetching
  - Extract entities during summarization

### Indexer
- **Role**: indexing documents and ideas, embeddings, entity linking.
- **Allowed caps**: `cap.index_document`, `cap.index_idea`, `cap.entity_resolve`, `cap.entity_link`, `cap.persist_rows`, `cap.ops_logging`.
- **NEW responsibilities**:
  - Resolve and link entities after indexing
  - Detect version updates to existing documents

### Matcher
- **Role**: compute matches with explanations.
- **Allowed caps**: `cap.query_rows`, `cap.persist_rows`, `cap.match_explain`, `cap.memory_query`, `cap.ops_logging`.
- **NEW responsibilities**:
  - Generate detailed match explanations
  - Query research memory for relevant patterns
  - Factor in entity relationships when matching

### Match Learning Agent (NEW)
- **Role**: analyze human feedback, extract patterns, update match rules.
- **Allowed caps**: `cap.match_learn`, `cap.query_rows`, `cap.memory_store`, `cap.analytics_match_quality`, `cap.ops_logging`.
- **Responsibilities**:
  - Run after batch of human reviews
  - Identify patterns in high/low scores
  - Generate match rules for future use
  - Store insights in research memory

### Taxonomy Curator (NEW)
- **Role**: propose new terms, validate taxonomy health, manage governance.
- **Allowed caps**: `cap.taxonomy_propose`, `cap.taxonomy_validate`, `cap.query_rows`, `cap.persist_rows`, `cap.analytics_taxonomy_usage`, `cap.ops_logging`.
- **Responsibilities**:
  - Monitor for missing or ambiguous terms
  - Detect taxonomy drift and overlaps
  - Propose merges for similar terms
  - Track human approval/rejection patterns

### Planner Executor
- **Role**: create/update tasks, manage backlog.
- **Allowed caps**: `cap.query_rows`, `cap.persist_rows`, `cap.update_rows`, `cap.ops_logging`.

### Prototype Planner (NEW)
- **Role**: generate implementation plans (NOT code).
- **Allowed caps**: `cap.prototype_plan`, `cap.query_rows`, `cap.persist_rows`, `cap.llm_generate`, `cap.memory_query`, `cap.ops_logging`.
- **Responsibilities**:
  - Generate detailed, realistic implementation plans
  - Assess technical feasibility and risks
  - Query memory for similar past prototypes
  - Wait for human approval before scaffolding

### Reviewer
- **Role**: judge validity, build dashboards, quality reports.
- **Allowed caps**: `cap.query_rows`, `cap.file_write`, `cap.analytics_match_quality`, `cap.analytics_source_quality`, `cap.ops_logging`.
- **NEW responsibilities**:
  - Generate match quality reports
  - Identify low-performing sources
  - Track research velocity metrics

### Memory Manager (NEW)
- **Role**: maintain research memory, prune stale insights.
- **Allowed caps**: `cap.memory_query`, `cap.memory_store`, `cap.memory_update`, `cap.query_rows`, `cap.ops_logging`.
- **Responsibilities**:
  - Surface relevant memories during research
  - Update memory confidence based on new evidence
  - Prune low-confidence or outdated memories
  - Track memory usage patterns

### Maintenance Operator (guarded)
- **Role**: delete duplicates, cleanup.
- **Allowed caps**: `cap.delete_rows`, `cap.file_write`, `cap.ops_logging`.

---

## Database Schema Changes

### New Tables

#### `entities`
- `id` (primary key)
- `canonical_name` (unique)
- `entity_type` (company/technology/person/concept/event)
- `aliases` (JSON array)
- `description` (text)
- `first_seen` (timestamp)
- `last_updated` (timestamp)
- `confidence` (0.0-1.0)

#### `document_entities` (many-to-many)
- `document_id` (foreign key -> documents.id)
- `entity_id` (foreign key -> entities.id)
- `relevance` (0.0-1.0, how central is this entity to the doc)
- `mentioned_count` (how many times mentioned)

#### `research_memory`
- `id` (primary key)
- `memory_type` (insight/pattern/dead_end/decision/rule)
- `content` (text)
- `evidence_refs` (JSON array of document/match IDs)
- `tags` (JSON array)
- `confidence` (0.0-1.0)
- `created_at` (timestamp)
- `last_validated` (timestamp)
- `validation_count` (integer)
- `impact_score` (0.0-1.0, how useful has this been)

#### `research_cycles`
- `id` (primary key)
- `cycle_name` (text)
- `start_date` (timestamp)
- `end_date` (timestamp)
- `search_runs` (JSON array of run IDs)
- `documents_fetched` (integer)
- `matches_created` (integer)
- `matches_reviewed` (integer)
- `prototypes_planned` (integer)
- `outcome_summary` (text)
- `learnings` (JSON array of memory IDs)

#### `taxonomy_proposals`
- `id` (primary key)
- `taxonomy_type` (domain/use_case/risk/maturity)
- `proposed_term` (text)
- `rationale` (text)
- `example_usage` (text, example documents where this would apply)
- `proposer` (agent_name or "human")
- `status` (pending/approved/rejected)
- `reviewed_by` (text, human name)
- `reviewed_at` (timestamp)
- `created_at` (timestamp)

#### `prototypes`
- `id` (primary key)
- `match_id` (foreign key -> matches.id)
- `name` (text)
- `plan_content` (text, markdown)
- `status` (planned/approved/scaffolded/in_progress/implemented/deployed/archived)
- `tech_stack` (JSON array)
- `effort_estimate_hours` (integer)
- `security_reviewed` (boolean)
- `security_notes` (text)
- `workspace_path` (text, where prototype files live)
- `created_at` (timestamp)
- `approved_at` (timestamp)
- `completed_at` (timestamp)

### Modified Tables

#### `documents` (add columns)
- `canonical_entity_id` (nullable foreign key -> entities.id, for docs ABOUT a single entity)
- `fetch_version` (integer, default 1, increments on re-fetch)
- `previous_version_id` (nullable foreign key -> documents.id)

#### `matches` (add columns)
- `explanation_text` (text, detailed reasoning for match score)
- `human_override` (boolean, true if human changed the score)
- `original_score` (float, agent's original score before human edit)
- `feedback_incorporated` (boolean, true if this feedback was used for learning)
- `entity_overlap_count` (integer, how many entities in common)

#### `ideas` (add columns)
- `priority` (integer, 1-5, human-assigned)
- `strategic_alignment` (text, how this aligns with strategy)
- `effort_estimate_hours` (integer)
- `status` (proposed/active/on_hold/completed/archived)

---

## Migration Priority

### Phase 1 (Weeks 1-2): Core Loop Solidification
1. Add `explanation_text` to matches table
2. Implement `match_explain` capability and tool
3. Add `human_override` tracking to matches
4. Update `match_all_ideas` and `match_all_docs` to generate explanations
5. Add basic analytics: match score distributions

### Phase 2 (Weeks 3-4): Entity Resolution
1. Create `entities` and `document_entities` tables
2. Implement `entity_resolve` and `entity_link` tools
3. Build `entity_resolve_documents` skill
4. Add entity extraction to fetch/index pipeline
5. Factor entity overlap into match scoring

### Phase 3 (Weeks 5-6): Research Memory
1. Create `research_memory` and `research_cycles` tables
2. Implement memory storage and query tools
3. Build `memory_store_insight` and `memory_query_relevant` skills
4. Add memory querying to matcher and researcher agents
5. Create `research_cycle_complete` skill for learning extraction

### Phase 4 (Weeks 7-8): Match Learning
1. Implement `match_learn` capability and tool
2. Build `match_learn_from_feedback` skill
3. Create Match Learning Agent
4. Add pattern detection for high/low scoring matches
5. Generate and version match rules

### Phase 5 (Weeks 9-10): Taxonomy Governance
1. Create `taxonomy_proposals` table
2. Implement taxonomy proposal and approval tools
3. Build taxonomy validation skill
4. Add taxonomy curator agent
5. Version taxonomy YAML files with changelog

### Phase 6 (Weeks 11-12): Prototype Planning
1. Create `prototypes` table
2. Implement `prototype_plan` tool (plans only, NO code generation yet)
3. Build `prototype_plan_create` skill
4. Add human review workflow for plans
5. Implement basic `prototype_scaffold` for approved plans

### Phase 7 (Ongoing): Performance & Analytics
1. Implement batch operations (`batch_fetch`, `batch_summarize`)
2. Add analytics skills (source quality, match patterns, velocity)
3. Build performance dashboards
4. Add memory manager agent for maintenance

---

## Success Metrics (to track)

### Match Quality Metrics
- Precision: % of high-scored agent matches that humans also score high
- Recall: % of human high-scores that agent identified
- Inter-annotator agreement: consistency between agent and human scores
- Explanation quality: human rating of match reasoning (1-5 scale)

### System Performance Metrics
- Documents processed per week
- Matches generated per week
- Matches reviewed per week (human throughput)
- Average time: search ? fetch ? match ? review
- Prototype plans created per month

### Learning Metrics
- Match rule coverage: % of matches explained by learned rules
- Memory usage: how often do agents query research memory
- Taxonomy stability: rate of new term proposals vs approvals
- Entity resolution accuracy: % of correctly canonicalized entities

### Business Impact Metrics
- Prototypes delivered per quarter
- Time saved vs manual research (estimated)
- Ideas advanced to execution (conversion rate)
- Team satisfaction score (monthly survey)

---

## Notes for Implementation

1. **Start small**: Implement Phase 1 completely before moving to Phase 2
2. **Measure everything**: Add telemetry for all new capabilities
3. **Human review gates**: All new agent behaviors need human approval initially
4. **Gradual autonomy**: Start with propose-and-wait, evolve to autonomous with alerts
5. **Version everything**: Taxonomy, match rules, memory schemas should be versioned
6. **Fail safely**: All new tools should have dry-run modes and rollback capability
7. **Document learnings**: Use research memory to track what works and what doesn't

---

## Red Flags and Safeguards

### Matching
- Alert if agent match scores diverge >3 points from human scores consistently
- Alert if explanation quality ratings drop below 3/5
- Weekly review of match patterns and rules

### Entity Resolution
- Human review for entity merges (prevent incorrect canonicalization)
- Confidence threshold: only auto-link entities with >0.8 confidence
- Weekly audit of new entities and aliases

### Memory
- Prune memories with confidence <0.3 and no recent validation
- Limit memory query results to top 10 most relevant
- Monthly review of high-impact memories

### Taxonomy
- Require 3 example documents for any new term proposal
- Auto-reject terms that overlap >80% with existing terms
- Quarterly taxonomy health check

### Prototypes
- NEVER generate complex code without explicit human request
- All prototype plans require security review before scaffolding
- Sandbox any agent-generated code execution
- Track prototype success/failure rates

