CREATE TABLE IF NOT EXISTS perf_spans (
  id TEXT PRIMARY KEY,
  run_id TEXT NOT NULL,
  span_name TEXT NOT NULL,
  span_category TEXT,
  skill_name TEXT,
  status TEXT NOT NULL DEFAULT 'ok',
  started_at TEXT NOT NULL,
  ended_at TEXT NOT NULL,
  duration_ms INTEGER NOT NULL,
  metadata_json TEXT,
  parent_span_id TEXT,
  FOREIGN KEY(run_id) REFERENCES agent_runs(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_perf_spans_run_id ON perf_spans(run_id);
CREATE INDEX IF NOT EXISTS idx_perf_spans_started_at ON perf_spans(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_perf_spans_duration ON perf_spans(duration_ms DESC);
