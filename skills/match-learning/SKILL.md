---
name: match-learning
description: Analyze high- vs low-scored matches, propose versioned match rules in YAML, and track precision/recall over time in SQLite. Use when adding or updating the match-learning workflow or reviewing match scoring patterns.
---

# match-learning

## Purpose
Analyze match review outcomes, propose rules for improving matches, and track metrics.

## Workflow

1) Load reviewed matches from SQLite (`matches` table), including:
   - `match_score` (1-10 human score)
   - `review_notes` (human comment; field name may vary)
   - `reasons_json` and any taxonomy fields needed
2) Split into high vs low score cohorts (default: high >= 8, low <= 4). If score distribution is narrow, log and adjust thresholds.
3) Identify recurring patterns by:
   - Common terms in titles/summaries
   - Repeated reasons or taxonomy overlaps
   - Consistent false positives/negatives noted in comments
4) Propose rule updates in `references/rules.yaml`:
   - Add or adjust rule entries, incrementing `version` and `last_updated`.
   - Keep rules human-readable and reversible.
5) Compute precision/recall metrics per ruleset version:
   - Store in SQLite table `match_learning_metrics` (create if missing)
   - Record `ruleset_version`, counts, precision, recall, and notes
6) Summarize changes and open questions for human review.

## Rules File
Use `references/rules.yaml` as the source of truth. Update it directly and keep a changelog in the `notes` field of each rule.

## Metrics Storage
If `match_learning_metrics` does not exist, create it with columns:
- `id` (uuid)
- `ruleset_version` (int)
- `precision` (float)
- `recall` (float)
- `high_threshold` (int)
- `low_threshold` (int)
- `samples_high` (int)
- `samples_low` (int)
- `created_at` (iso8601)
- `notes` (text)

## Outputs
- Updated `references/rules.yaml`
- Metrics row in SQLite
- Short summary for review
