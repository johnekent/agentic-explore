from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re
import yaml

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)\Z", re.DOTALL)

@dataclass
class MdDoc:
    frontmatter: dict[str, Any]
    body: str

def parse_md_with_frontmatter(text: str) -> MdDoc:
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return MdDoc(frontmatter={}, body=text)
    fm_text, body = m.group(1), m.group(2)
    fm = yaml.safe_load(fm_text) or {}
    if not isinstance(fm, dict):
        fm = {}
    return MdDoc(frontmatter=fm, body=body)

def dump_md_with_frontmatter(frontmatter: dict[str, Any], body: str) -> str:
    fm_text = yaml.safe_dump(frontmatter, sort_keys=False).strip()
    return f"---\n{fm_text}\n---\n\n{body.lstrip()}"
