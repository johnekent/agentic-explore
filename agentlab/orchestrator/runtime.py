from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, Iterable, Set

from agentlab.orchestrator.registry import ToolRegistry, build_registry
from agentlab.tools.types import ToolResult


@dataclass
class Orchestrator:
    registry: ToolRegistry
    allowed_capabilities: Set[str]

    def tool_for_capability(self, capability: str) -> Callable[..., ToolResult]:
        if capability not in self.allowed_capabilities:
            raise PermissionError(f"Capability not allowed: {capability}")
        tool_name = self.registry.capability_to_tool.get(capability)
        if not tool_name:
            raise KeyError(f"No tool mapped for capability: {capability}")
        tool = self.registry.tools.get(tool_name)
        if not tool:
            raise KeyError(f"Tool not registered: {tool_name}")
        return tool

    def use(self, capability: str, **kwargs) -> ToolResult:
        tool = self.tool_for_capability(capability)
        return tool(**kwargs)


def default_orchestrator() -> Orchestrator:
    registry = build_registry()
    allowed = set(registry.capability_to_tool.keys())
    return Orchestrator(registry=registry, allowed_capabilities=allowed)
