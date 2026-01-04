# Agent Lab (v0) — Local-first Agent Skills + SQLite Index + MCP Server

Starter kit for:
**search -> fetch/extract -> normalize/summarize -> classify (multi-taxonomy) -> index (SQLite) -> idea backlog -> match -> judge -> plan -> track -> dashboard**

- **Content of record:** Markdown files with YAML frontmatter
- **Index:** SQLite database with pointers to those files + searchable fields
- **Skills:** `skills/*/SKILL.md` (Agent Skills format)
- **MCP server:** `agentlab-mcp` exposes tools to any MCP-compatible client

## Adding Skills

Skills live under `skills/<skill-name>/SKILL.md`. The YAML frontmatter must include `name` and `description`, and the description is used for triggering.

**Option A: UI**
- Open the **Skills** tab in the Streamlit UI and use the “Create Skill” form.
- The skill becomes immediately discoverable via MCP (`list_skills` tool).

**Option B: Manual**
1) Create `skills/<skill-name>/SKILL.md`
2) Add frontmatter:
```yaml
---
name: my-skill
description: What this skill does and when to use it.
---
```
3) Add concise instructions in the body.

**Discoverability via MCP**
- Use the MCP tool `list_skills` to enumerate installed skills and their descriptions.

## Quick start

### 1) Install
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
```

## Local Run
Single command to initialize the agentic runtime:
```bash
agentlab run
```

Run tests:
```bash
python -m unittest discover -s tests -p "test_*.py"
```

### 2) Initialize workspace + DB
```bash
agentlab init
```

### 3) Create example ideas + docs (offline demo)
```bash
agentlab demo seed
agentlab dashboard build
```

Open: `workspace/exports/dashboard.md`

### 4) Run a real web search + fetch
```bash
agentlab search "asset tokenization market infrastructure" --top-n 8
agentlab fetch <RUN_ID_FROM_SEARCH_OUTPUT>
agentlab summarize docs <RUN_ID>
agentlab index docs <RUN_ID>
agentlab match ideas
agentlab dashboard build
```

### 5) Plan and track execution
```bash
agentlab plan match <MATCH_ID>  # Create task from reviewed match
agentlab plan backlog           # View active tasks
agentlab plan update-status <TASK_ID> in_progress
agentlab plan assign <TASK_ID> "human_researcher"
# Or use UI: streamlit run ui.py
```

### 6) Maintenance (cleanup or full wipe)
```bash
agentlab cleanup-db --dry-run
agentlab cleanup-db --apply
agentlab delete-all-data --yes          # deletes DB rows + document/idea files
agentlab delete-all-data --yes --keep-files
```

## Optional: LLM provider
### Ollama (local)
```bash
export AGENTLAB_LLM=ollama
export OLLAMA_MODEL=llama3.1
```

### Ollama (Docker)
```bash
docker run -d --name ollama -p 11434:11434 ollama/ollama
docker exec -it ollama ollama pull llama3.1
docker exec -it ollama ollama pull phi3:mini  # depending on what model(s) are used
docker exec -it ollama ollama run phi3:mini "Summarize: This is a short test."
```
Windows note: Docker Desktop must be running for these commands to work.

Or set defaults in `config.yaml` (env vars still override):
```yaml
llm_provider: ollama
db_path: workspace/index/agent.db
ollama:
  model: llama3.1
  base_url: http://localhost:11434
```

## MCP server
Start (stdio transport):
```bash
agentlab-mcp
```

Start (HTTP Streamable):
```bash
agentlab-mcp --transport streamable-http --host 127.0.0.1 --port 8000
```
Use `http://127.0.0.1:8000/mcp` as the MCP server URL.

Start (WebSocket):
```bash
agentlab-mcp --transport websocket --host 127.0.0.1 --port 8001 --ws-path /ws
```
Use `ws://127.0.0.1:8001/ws` as the MCP server URL.

Restart:
- Stop the existing server process (Ctrl+C) and re-run `agentlab-mcp` in a fresh terminal.

Call from an MCP client (stdio):
- Configure a server entry that runs the command `agentlab-mcp`.
- Use your client to list tools and call them (e.g., `list_skills`, `search_web`, `create_idea`).

Claude Desktop (Windows):
- Settings -> Developer -> Edit Config -> add an MCP server entry for `agentlab-mcp`, then restart Claude.

VS Code (MCP Client by christian237):
- Open the MCP Client panel and set `mcpClient.serverUrl` to `http://127.0.0.1:8000/mcp` (HTTP) or `ws://127.0.0.1:8001/ws` (WS).
- Connect, then reload the window if prompted.

The server exposes tools like `search_web`, `create_idea`, `match_idea_to_docs`, `build_dashboard`, `query_rows`.


## Architecture Alignment
This project follows `GUIDING_PRINCIPLES.md`:
- Agents decide, tools act (side effects are in `agentlab/tools/*`)
- Skills declare capabilities and use orchestrator routing
- Capability mapping lives in `capabilities.yaml`
 - Interfaces (CLI/UI/MCP) call services; services call skills; skills call tools

See:
- `ARCHITECTURE_TARGET.md` for the target tool/skill/agent set
- `MIGRATION_PLAN.md` for the refactor status and next steps

## Planning & Execution Tracking
After reviewing matches, create and manage tasks for execution:

- **Create tasks**: `agentlab plan match <match_id>` links a reviewed match to a new task.
- **View backlog**: `agentlab plan backlog` lists active tasks with status/priority/assignment.
- **Update tasks**: `agentlab plan update-status <task_id> <status>` and `agentlab plan assign <task_id> <agent>`.
- **UI Visualization**: Run `streamlit run ui.py` for interactive planning, including Gantt charts.
- **Data**: Tasks are stored in SQLite `tasks` table, linked to matches for traceability.
