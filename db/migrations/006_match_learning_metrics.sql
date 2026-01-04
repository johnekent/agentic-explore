CREATE TABLE IF NOT EXISTS match_learning_metrics (
  id TEXT PRIMARY KEY,
  ruleset_version INTEGER NOT NULL,
  precision REAL,
  recall REAL,
  high_threshold INTEGER NOT NULL,
  low_threshold INTEGER NOT NULL,
  samples_high INTEGER NOT NULL,
  samples_low INTEGER NOT NULL,
  created_at TEXT NOT NULL,
  notes TEXT
);

CREATE INDEX IF NOT EXISTS idx_match_learning_metrics_created_at
  ON match_learning_metrics(created_at DESC);
