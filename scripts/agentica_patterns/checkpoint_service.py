#!/usr/bin/env python3
"""Checkpoint service for crash recovery and state persistence."""

import asyncio
import hashlib
import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional, AsyncIterator
from uuid import uuid4

@dataclass
class Checkpoint:
    """A checkpoint containing agent state."""
    id: str
    agent_id: str
    session_id: str
    state: Dict[str, Any]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    checksum: str = ""

@dataclass
class CheckpointMetadata:
    """Metadata about a checkpoint."""
    id: str
    agent_id: str
    session_id: str
    created_at: str
    state_size: int
    state_hash: str
    parent_checkpoint_id: Optional[str] = None

class CheckpointService:
    """Service for creating, listing, and restoring checkpoints."""

    def __init__(self, checkpoint_dir: str = "~/.claude/checkpoints"):
        self.checkpoint_dir = Path(checkpoint_dir).expanduser()
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._checkpoints: Dict[str, Checkpoint] = {}

    def _checkpoint_path(self, checkpoint_id: str) -> Path:
        return self.checkpoint_dir / f"{checkpoint_id}.json"

    def _compute_checksum(self, state: Dict[str, Any]) -> str:
        """Compute SHA-256 checksum of state."""
        state_str = json.dumps(state, sort_keys=True)
        return hashlib.sha256(state_str.encode()).hexdigest()

    async def create(
        self,
        agent_id: str,
        session_id: str,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        parent_id: Optional[str] = None,
    ) -> Checkpoint:
        """Create a new checkpoint."""
        checkpoint_id = str(uuid4())[:8]
        checksum = self._compute_checksum(state)

        checkpoint = Checkpoint(
            id=checkpoint_id,
            agent_id=agent_id,
            session_id=session_id,
            state=state,
            metadata=metadata or {},
            checksum=checksum,
        )

        # Persist to disk
        path = self._checkpoint_path(checkpoint_id)
        with open(path, 'w') as f:
            json.dump({
                'id': checkpoint.id,
                'agent_id': checkpoint.agent_id,
                'session_id': checkpoint.session_id,
                'state': checkpoint.state,
                'metadata': checkpoint.metadata,
                'created_at': checkpoint.created_at,
                'checksum': checkpoint.checksum,
            }, f, indent=2)

        self._checkpoints[checkpoint_id] = checkpoint
        return checkpoint

    async def get(self, checkpoint_id: str) -> Optional[Checkpoint]:
        """Get a checkpoint by ID."""
        if checkpoint_id in self._checkpoints:
            return self._checkpoints[checkpoint_id]

        path = self._checkpoint_path(checkpoint_id)
        if not path.exists():
            return None

        with open(path) as f:
            data = json.load(f)
            return Checkpoint(**data)

    async def restore(self, checkpoint_id: str) -> Optional[Dict[str, Any]]:
        """Restore state from a checkpoint."""
        checkpoint = await self.get(checkpoint_id)
        if checkpoint is None:
            return None

        # Verify checksum
        if self._compute_checksum(checkpoint.state) != checkpoint.checksum:
            raise ValueError(f"Checkpoint {checkpoint_id} checksum mismatch")

        return checkpoint.state

    async def list_by_session(self, session_id: str) -> list[CheckpointMetadata]:
        """List all checkpoints for a session."""
        checkpoints = []
        for path in self.checkpoint_dir.glob("*.json"):
            with open(path) as f:
                data = json.load(f)
                if data['session_id'] == session_id:
                    checkpoints.append(CheckpointMetadata(
                        id=data['id'],
                        agent_id=data['agent_id'],
                        session_id=data['session_id'],
                        created_at=data['created_at'],
                        state_size=len(json.dumps(data['state'])),
                        state_hash=data['checksum'],
                    ))
        return sorted(checkpoints, key=lambda c: c.created_at, reverse=True)

    async def delete(self, checkpoint_id: str) -> bool:
        """Delete a checkpoint."""
        path = self._checkpoint_path(checkpoint_id)
        if path.exists():
            path.unlink()
            self._checkpoints.pop(checkpoint_id, None)
            return True
        return False

    async def gc(self, max_age_hours: int = 24) -> int:
        """Garbage collect old checkpoints."""
        cutoff = datetime.now(timezone.utc).timestamp() - (max_age_hours * 3600)
        deleted = 0
        for path in self.checkpoint_dir.glob("*.json"):
            if path.stat().st_mtime < cutoff:
                checkpoint_id = path.stem
                await self.delete(checkpoint_id)
                deleted += 1
        return deleted

# Singleton
checkpoint_service = CheckpointService()
