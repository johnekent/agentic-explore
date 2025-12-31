---
name: document-title-summary
description: Extract a clean document title and a short summary from raw document text or HTML. Use when a document's title/summary is missing or needs to be generated for frontmatter indexing.
---

# Document Title + Summary Extraction

## Goal
Generate a concise, human-readable title and a short summary for a document so it can be indexed and shown in dashboards/matches.

## Inputs
- Raw document text (preferred) or HTML.
- Optional URL or source context.

## Output (strict JSON)
Return JSON with:
```json
{
  "title": "string",
  "summary": "string"
}
```

## Guidelines
- Title: 4-12 words, no quotes, no trailing punctuation.
- Summary: 1-3 sentences, ~50-120 words, factual tone.
- Avoid marketing fluff; prefer concrete claims and scope.
- If content is very short, keep the summary short.

## Workflow
1. Preflight LLM:
   - Read config (`config.yaml`) and/or environment:
     - `AGENTLAB_LLM`, `OLLAMA_BASE_URL`, `OLLAMA_MODEL`
   - Verify the LLM server is reachable (e.g., HTTP to `/api/chat` on Ollama).
   - If not running, start it (or instruct the user to start it) and report status clearly.
2. If HTML is provided, extract readable text first (remove script/style/nav).
3. If a page `<title>` or H1 exists, prefer it as a starting point for the title.
4. Use the document body to produce the summary.
5. Return JSON only, and include a short status message in logs/console if preflight failed.
