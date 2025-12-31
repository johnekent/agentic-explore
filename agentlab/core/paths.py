from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from datetime import datetime, timezone

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

@dataclass(frozen=True)
class Workspace:
    root: Path
    @property
    def content(self) -> Path: return self.root / "content"
    @property
    def documents(self) -> Path: return self.content / "documents"
    @property
    def ideas(self) -> Path: return self.content / "ideas"
    @property
    def matches(self) -> Path: return self.content / "matches"
    @property
    def index(self) -> Path: return self.root / "index"
    @property
    def db_path(self) -> Path: return self.index / "agent.db"
    @property
    def runs(self) -> Path: return self.root / "runs"
    @property
    def exports(self) -> Path: return self.root / "exports"

def ensure_workspace(root: Path) -> Workspace:
    ws = Workspace(root=root)
    for p in [ws.documents, ws.ideas, ws.matches, ws.index, ws.runs, ws.exports]:
        p.mkdir(parents=True, exist_ok=True)
    return ws

def dated_dir(base: Path) -> Path:
    now = datetime.now().strftime("%Y/%m")
    d = base / now
    d.mkdir(parents=True, exist_ok=True)
    return d
