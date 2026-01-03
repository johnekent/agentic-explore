ALTER TABLE documents ADD COLUMN asset_type TEXT;
ALTER TABLE documents ADD COLUMN asset_ref TEXT;
ALTER TABLE documents ADD COLUMN asset_path TEXT;

CREATE TABLE IF NOT EXISTS item_processing (
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
  FOREIGN KEY(run_id) REFERENCES runs(run_id)
);

CREATE INDEX IF NOT EXISTS idx_item_processing_item ON item_processing(item_type, item_id);
CREATE INDEX IF NOT EXISTS idx_item_processing_run ON item_processing(run_id);
CREATE INDEX IF NOT EXISTS idx_item_processing_stage ON item_processing(stage);
CREATE INDEX IF NOT EXISTS idx_item_processing_status ON item_processing(status);
