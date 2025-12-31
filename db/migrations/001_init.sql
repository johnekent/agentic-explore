PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY,
  topic TEXT,
  started_at TEXT NOT NULL,
  ended_at TEXT,
  params_json TEXT,
  outputs_json TEXT
);

CREATE TABLE IF NOT EXISTS documents (
  id TEXT PRIMARY KEY,
  title TEXT,
  url TEXT,
  retrieved_at TEXT,
  summary TEXT,
  content_path TEXT NOT NULL,
  source_text TEXT,
  run_id TEXT,
  review_score REAL,
  review_notes TEXT,
  FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_documents_url ON documents(url);
CREATE INDEX IF NOT EXISTS idx_documents_retrieved_at ON documents(retrieved_at);

CREATE TABLE IF NOT EXISTS document_taxonomy (
  document_id TEXT NOT NULL,
  taxonomy_name TEXT NOT NULL,
  label TEXT NOT NULL,
  PRIMARY KEY (document_id, taxonomy_name, label),
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS ideas (
  id TEXT PRIMARY KEY,
  title TEXT,
  summary TEXT,
  proposed_by TEXT,
  created_at TEXT,
  status TEXT,
  content_path TEXT NOT NULL,
  source_text TEXT,
  review_score REAL,
  review_notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_ideas_created_at ON ideas(created_at);

CREATE TABLE IF NOT EXISTS idea_taxonomy (
  idea_id TEXT NOT NULL,
  taxonomy_name TEXT NOT NULL,
  label TEXT NOT NULL,
  PRIMARY KEY (idea_id, taxonomy_name, label),
  FOREIGN KEY(idea_id) REFERENCES ideas(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS matches (
  id TEXT PRIMARY KEY,
  idea_id TEXT NOT NULL,
  document_id TEXT NOT NULL,
  match_score REAL NOT NULL,
  reasons_json TEXT,
  scores_json TEXT,
  run_id TEXT,
  validity_pass INTEGER,
  validity_notes TEXT,
  judge_notes TEXT,
  review_score REAL,
  review_notes TEXT,
  FOREIGN KEY(idea_id) REFERENCES ideas(id) ON DELETE CASCADE,
  FOREIGN KEY(document_id) REFERENCES documents(id) ON DELETE CASCADE,
  FOREIGN KEY(run_id) REFERENCES runs(run_id),
  UNIQUE(idea_id, document_id)
);

CREATE INDEX IF NOT EXISTS idx_matches_score ON matches(match_score DESC);

CREATE TABLE IF NOT EXISTS tasks (
  id TEXT PRIMARY KEY,
  description TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'pending',  -- pending, in_progress, completed
  priority TEXT NOT NULL DEFAULT 'medium',  -- low, medium, high
  assigned_agent TEXT,
  match_id TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT,
  due_date TEXT,
  FOREIGN KEY(match_id) REFERENCES matches(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
CREATE INDEX IF NOT EXISTS idx_tasks_match_id ON tasks(match_id);

CREATE TABLE IF NOT EXISTS usage_logs (
  id TEXT PRIMARY KEY,
  timestamp TEXT NOT NULL,
  skill_name TEXT NOT NULL,
  agent_type TEXT NOT NULL,  -- e.g., 'cli', 'mcp', 'ui'
  workflow_context TEXT,     -- e.g., 'search', 'match', 'plan'
  parameters_json TEXT,      -- input params as JSON
  result_summary TEXT,       -- brief outcome
  duration_ms INTEGER        -- execution time in ms
);

CREATE INDEX IF NOT EXISTS idx_usage_logs_timestamp ON usage_logs(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_usage_logs_skill ON usage_logs(skill_name);
