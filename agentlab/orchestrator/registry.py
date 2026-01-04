from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Dict

from agentlab.capabilities.registry import load_capabilities
from agentlab.tools.cleanup_tools import cleanup_content, cleanup_db, delete_all_data
from agentlab.tools.dedup_tools import delete_duplicate_documents, list_document_duplicates
from agentlab.tools.env_tools import env_check_db, env_check_llm
from agentlab.tools.file_tools import list_files, read_file, write_file
from agentlab.tools.index_tools import index_document, index_idea
from agentlab.tools.judge_tools import build_dashboard_tool, judge_validity_tool
from agentlab.tools.llm_generate import llm_generate
from agentlab.tools.local_exec import local_exec
from agentlab.tools.match_tools import match_doc_to_ideas, match_idea_to_docs
from agentlab.tools.ops_tools import ops_log
from agentlab.tools.plan_tools import (
    plan_assign_agent_tool,
    plan_backlog_tool,
    plan_match_execution_tool,
    plan_update_status_tool,
)
from agentlab.tools.sqlite_tools import delete_rows, migrate_db, persist_rows, query_rows, update_rows
from agentlab.tools.summarize_tools import summarize_document
from agentlab.tools.vector_tools import vector_index, vector_query, vector_stats
from agentlab.tools.web_tools import fetch_url, search_web


ToolFn = Callable[..., object]


@dataclass(frozen=True)
class ToolRegistry:
    tools: Dict[str, ToolFn]
    capability_to_tool: Dict[str, str]


def build_registry() -> ToolRegistry:
    caps = load_capabilities()
    tools = {
        "persist_rows": persist_rows,
        "query_rows": query_rows,
        "update_rows": update_rows,
        "delete_rows": delete_rows,
        "migrate_db": migrate_db,
        "read_file": read_file,
        "write_file": write_file,
        "list_files": list_files,
        "index_document": index_document,
        "index_idea": index_idea,
        "local_exec": local_exec,
        "llm_generate": llm_generate,
        "summarize_document": summarize_document,
        "ops_log": ops_log,
        "search_web": search_web,
        "fetch_url": fetch_url,
        "match_idea_to_docs": match_idea_to_docs,
        "match_doc_to_ideas": match_doc_to_ideas,
        "plan_match_execution": plan_match_execution_tool,
        "plan_backlog": plan_backlog_tool,
        "plan_update_status": plan_update_status_tool,
        "plan_assign_agent": plan_assign_agent_tool,
        "judge_validity": judge_validity_tool,
        "build_dashboard": build_dashboard_tool,
        "cleanup_db": cleanup_db,
        "cleanup_content": cleanup_content,
        "delete_all_data": delete_all_data,
        "list_document_duplicates": list_document_duplicates,
        "delete_duplicate_documents": delete_duplicate_documents,
        "vector_index": vector_index,
        "vector_query": vector_query,
        "vector_stats": vector_stats,
        "env_check_db": env_check_db,
        "env_check_llm": env_check_llm,
    }
    capability_to_tool = {
        cap.id: cap.default_tool for cap in caps.values() if cap.default_tool
    }
    return ToolRegistry(tools=tools, capability_to_tool=capability_to_tool)
