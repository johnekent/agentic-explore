PRAGMA foreign_keys = OFF;

CREATE TABLE IF NOT EXISTS item_processing_new (
  id TEXT PRIMARY KEY,
  item_type TEXT NOT NULL,
  item_id TEXT NOT NULL,
  run_id TEXT,
  stage TEXT NOT NULL,
  status TEXT NOT NULL,
  error TEXT,
  metadata_json TEXT,
  started_at TEXT NOT NULL,
  ended_at TEXT NOT NULL,
  FOREIGN KEY(run_id) REFERENCES agent_runs(id)
);

INSERT INTO item_processing_new (
  id,
  item_type,
  item_id,
  run_id,
  stage,
  status,
  error,
  metadata_json,
  started_at,
  ended_at
)
SELECT
  id,
  item_type,
  item_id,
  run_id,
  stage,
  status,
  error,
  metadata_json,
  started_at,
  ended_at
FROM item_processing;

DROP TABLE item_processing;
ALTER TABLE item_processing_new RENAME TO item_processing;

CREATE INDEX IF NOT EXISTS idx_item_processing_item ON item_processing(item_type, item_id);
CREATE INDEX IF NOT EXISTS idx_item_processing_run ON item_processing(run_id);
CREATE INDEX IF NOT EXISTS idx_item_processing_stage ON item_processing(stage);
CREATE INDEX IF NOT EXISTS idx_item_processing_status ON item_processing(status);

PRAGMA foreign_keys = ON;
