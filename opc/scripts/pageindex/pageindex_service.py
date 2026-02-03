"""
PageIndex Service - CRUD operations for tree indexes in PostgreSQL.

Stores and retrieves hierarchical tree structures for markdown documents.
"""
import os
import json
import hashlib
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    import asyncpg
except ImportError:
    asyncpg = None

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor, Json
except ImportError:
    psycopg2 = None


class DocType(Enum):
    ROADMAP = "ROADMAP"
    DOCUMENTATION = "DOCUMENTATION"
    ARCHITECTURE = "ARCHITECTURE"
    README = "README"
    OTHER = "OTHER"


@dataclass
class TreeIndex:
    id: Optional[str] = None
    project_id: str = ""
    doc_path: str = ""
    doc_type: DocType = DocType.OTHER
    tree_structure: Dict[str, Any] = field(default_factory=dict)
    doc_hash: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def get_database_url() -> str:
    """Get database URL from environment."""
    return os.getenv(
        "DATABASE_URL",
        "postgresql://claude:claude_dev@localhost:5432/continuous_claude"
    )


def compute_doc_hash(content: str) -> str:
    """Compute SHA256 hash of document content."""
    return hashlib.sha256(content.encode()).hexdigest()


def detect_doc_type(doc_path: str) -> DocType:
    """Detect document type from filename."""
    name = Path(doc_path).name.upper()
    if "ROADMAP" in name:
        return DocType.ROADMAP
    elif "ARCHITECTURE" in name:
        return DocType.ARCHITECTURE
    elif "README" in name:
        return DocType.README
    elif any(x in name for x in ["DOC", "GUIDE", "MANUAL", "REFERENCE"]):
        return DocType.DOCUMENTATION
    return DocType.OTHER


def compute_project_id(project_path: str) -> str:
    """Compute project ID from project path (hash)."""
    return hashlib.sha256(project_path.encode()).hexdigest()[:16]


class PageIndexService:
    """Service for managing PageIndex tree structures in PostgreSQL."""

    def __init__(self, database_url: Optional[str] = None):
        self.database_url = database_url or get_database_url()
        self._conn = None

    def _get_sync_connection(self):
        """Get synchronous psycopg2 connection."""
        if psycopg2 is None:
            raise ImportError("psycopg2 not installed. Run: pip install psycopg2-binary")
        if self._conn is None or self._conn.closed:
            self._conn = psycopg2.connect(self.database_url)
        return self._conn

    def close(self):
        """Close database connection."""
        if self._conn and not self._conn.closed:
            self._conn.close()
            self._conn = None

    def store_tree(
        self,
        project_path: str,
        doc_path: str,
        tree_structure: Dict[str, Any],
        doc_content: Optional[str] = None
    ) -> TreeIndex:
        """
        Store or update a tree index.

        Args:
            project_path: Absolute path to project root
            doc_path: Relative path to document within project
            tree_structure: The tree index structure (from PageIndex)
            doc_content: Optional document content for hash computation

        Returns:
            TreeIndex with the stored data
        """
        conn = self._get_sync_connection()
        project_id = compute_project_id(project_path)
        doc_type = detect_doc_type(doc_path)
        doc_hash = compute_doc_hash(doc_content) if doc_content else None

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                INSERT INTO pageindex_trees (project_id, doc_path, doc_type, tree_structure, doc_hash, updated_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
                ON CONFLICT (project_id, doc_path)
                DO UPDATE SET
                    tree_structure = EXCLUDED.tree_structure,
                    doc_hash = EXCLUDED.doc_hash,
                    doc_type = EXCLUDED.doc_type,
                    updated_at = NOW()
                RETURNING id, project_id, doc_path, doc_type, tree_structure, doc_hash, created_at, updated_at
            """, (project_id, doc_path, doc_type.value, Json(tree_structure), doc_hash))

            row = cur.fetchone()
            conn.commit()

        return TreeIndex(
            id=str(row['id']),
            project_id=row['project_id'],
            doc_path=row['doc_path'],
            doc_type=DocType(row['doc_type']),
            tree_structure=row['tree_structure'],
            doc_hash=row['doc_hash'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def get_tree(self, project_path: str, doc_path: str) -> Optional[TreeIndex]:
        """
        Get a tree index by project and document path.

        Args:
            project_path: Absolute path to project root
            doc_path: Relative path to document

        Returns:
            TreeIndex if found, None otherwise
        """
        conn = self._get_sync_connection()
        project_id = compute_project_id(project_path)

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute("""
                SELECT id, project_id, doc_path, doc_type, tree_structure, doc_hash, created_at, updated_at
                FROM pageindex_trees
                WHERE project_id = %s AND doc_path = %s
            """, (project_id, doc_path))

            row = cur.fetchone()

        if not row:
            return None

        return TreeIndex(
            id=str(row['id']),
            project_id=row['project_id'],
            doc_path=row['doc_path'],
            doc_type=DocType(row['doc_type']),
            tree_structure=row['tree_structure'],
            doc_hash=row['doc_hash'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    def list_trees(
        self,
        project_path: Optional[str] = None,
        doc_type: Optional[DocType] = None
    ) -> List[TreeIndex]:
        """
        List tree indexes, optionally filtered by project or doc type.

        Args:
            project_path: Optional project path to filter by
            doc_type: Optional document type to filter by

        Returns:
            List of TreeIndex objects (without full tree_structure for efficiency)
        """
        conn = self._get_sync_connection()

        conditions = []
        params = []

        if project_path:
            project_id = compute_project_id(project_path)
            conditions.append("project_id = %s")
            params.append(project_id)

        if doc_type:
            conditions.append("doc_type = %s")
            params.append(doc_type.value)

        where_clause = " AND ".join(conditions) if conditions else "TRUE"

        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(f"""
                SELECT id, project_id, doc_path, doc_type, doc_hash, created_at, updated_at,
                       jsonb_array_length(COALESCE(tree_structure->'structure', '[]'::jsonb)) as node_count
                FROM pageindex_trees
                WHERE {where_clause}
                ORDER BY updated_at DESC
            """, params)

            rows = cur.fetchall()

        return [
            TreeIndex(
                id=str(row['id']),
                project_id=row['project_id'],
                doc_path=row['doc_path'],
                doc_type=DocType(row['doc_type']),
                tree_structure={"node_count": row.get('node_count', 0)},
                doc_hash=row['doc_hash'],
                created_at=row['created_at'],
                updated_at=row['updated_at']
            )
            for row in rows
        ]

    def delete_tree(self, project_path: str, doc_path: str) -> bool:
        """
        Delete a tree index.

        Args:
            project_path: Absolute path to project root
            doc_path: Relative path to document

        Returns:
            True if deleted, False if not found
        """
        conn = self._get_sync_connection()
        project_id = compute_project_id(project_path)

        with conn.cursor() as cur:
            cur.execute("""
                DELETE FROM pageindex_trees
                WHERE project_id = %s AND doc_path = %s
                RETURNING id
            """, (project_id, doc_path))

            deleted = cur.fetchone() is not None
            conn.commit()

        return deleted

    def needs_reindex(self, project_path: str, doc_path: str, current_content: str) -> bool:
        """
        Check if document needs reindexing (content changed).

        Args:
            project_path: Project root path
            doc_path: Document path
            current_content: Current document content

        Returns:
            True if document has changed and needs reindexing
        """
        tree = self.get_tree(project_path, doc_path)
        if not tree:
            return True

        current_hash = compute_doc_hash(current_content)
        return tree.doc_hash != current_hash

    def get_all_project_trees(self, project_path: str) -> Dict[str, TreeIndex]:
        """
        Get all tree indexes for a project.

        Args:
            project_path: Project root path

        Returns:
            Dict mapping doc_path to TreeIndex
        """
        trees = self.list_trees(project_path=project_path)
        return {t.doc_path: t for t in trees}


class AsyncPageIndexService:
    """Async version of PageIndexService using asyncpg."""

    def __init__(self, database_url: Optional[str] = None):
        if asyncpg is None:
            raise ImportError("asyncpg not installed. Run: pip install asyncpg")
        self.database_url = database_url or get_database_url()
        self._pool = None

    async def _get_pool(self):
        """Get or create connection pool."""
        if self._pool is None:
            self._pool = await asyncpg.create_pool(self.database_url)
        return self._pool

    async def close(self):
        """Close connection pool."""
        if self._pool:
            await self._pool.close()
            self._pool = None

    async def store_tree(
        self,
        project_path: str,
        doc_path: str,
        tree_structure: Dict[str, Any],
        doc_content: Optional[str] = None
    ) -> TreeIndex:
        """Store or update a tree index (async)."""
        pool = await self._get_pool()
        project_id = compute_project_id(project_path)
        doc_type = detect_doc_type(doc_path)
        doc_hash = compute_doc_hash(doc_content) if doc_content else None

        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                INSERT INTO pageindex_trees (project_id, doc_path, doc_type, tree_structure, doc_hash, updated_at)
                VALUES ($1, $2, $3, $4, $5, NOW())
                ON CONFLICT (project_id, doc_path)
                DO UPDATE SET
                    tree_structure = EXCLUDED.tree_structure,
                    doc_hash = EXCLUDED.doc_hash,
                    doc_type = EXCLUDED.doc_type,
                    updated_at = NOW()
                RETURNING id, project_id, doc_path, doc_type, tree_structure, doc_hash, created_at, updated_at
            """, project_id, doc_path, doc_type.value, json.dumps(tree_structure), doc_hash)

        return TreeIndex(
            id=str(row['id']),
            project_id=row['project_id'],
            doc_path=row['doc_path'],
            doc_type=DocType(row['doc_type']),
            tree_structure=json.loads(row['tree_structure']) if isinstance(row['tree_structure'], str) else row['tree_structure'],
            doc_hash=row['doc_hash'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )

    async def get_tree(self, project_path: str, doc_path: str) -> Optional[TreeIndex]:
        """Get a tree index (async)."""
        pool = await self._get_pool()
        project_id = compute_project_id(project_path)

        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT id, project_id, doc_path, doc_type, tree_structure, doc_hash, created_at, updated_at
                FROM pageindex_trees
                WHERE project_id = $1 AND doc_path = $2
            """, project_id, doc_path)

        if not row:
            return None

        return TreeIndex(
            id=str(row['id']),
            project_id=row['project_id'],
            doc_path=row['doc_path'],
            doc_type=DocType(row['doc_type']),
            tree_structure=json.loads(row['tree_structure']) if isinstance(row['tree_structure'], str) else row['tree_structure'],
            doc_hash=row['doc_hash'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
