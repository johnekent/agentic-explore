CREATE TABLE IF NOT EXISTS agent_runs (
  id TEXT PRIMARY KEY,
  agent_name TEXT NOT NULL,
  agent_type TEXT NOT NULL, -- cli, mcp, ui, or custom
  purpose TEXT,
  status TEXT NOT NULL DEFAULT 'started',
  started_at TEXT NOT NULL,
  ended_at TEXT,
  parent_run_id TEXT,
  metadata_json TEXT
);

CREATE INDEX IF NOT EXISTS idx_agent_runs_started_at ON agent_runs(started_at DESC);

CREATE TABLE IF NOT EXISTS tool_calls (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  tool_name TEXT NOT NULL,
  skill_name TEXT,
  parameters_json TEXT,
  result_summary TEXT,
  duration_ms INTEGER,
  timestamp TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tool_calls_timestamp ON tool_calls(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_tool_calls_run_id ON tool_calls(run_id);

CREATE TABLE IF NOT EXISTS agent_interactions (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  with_agent TEXT NOT NULL,
  interaction_type TEXT NOT NULL, -- message, request, response, handoff
  details_json TEXT,
  timestamp TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_agent_interactions_timestamp ON agent_interactions(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_agent_interactions_run_id ON agent_interactions(run_id);
