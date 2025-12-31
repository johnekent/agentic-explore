---
name: plan-match-execution
description: Create and manage tasks for executing reviewed matches, including prioritization, assignment, and progress tracking.
---

# plan-match-execution

Implemented by `agentlab` CLI and `agentlab-mcp` server.

This skill transitions reviewed matches into executable tasks stored in the local SQLite DB. It creates tasks with links to match IDs, assigns agents/humans, sets priorities, and tracks status.

Inputs:
- Match ID (from agent-lab DB)
- Human review score and notes

Outputs:
- Task ID in tasks table
- Updated task status via CLI commands

Uses SQLite for task storage and management, integrated with agent-lab's DB.
