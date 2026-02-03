-- Continuous Claude Unified Schema
-- 4 tables: sessions, file_claims, archival_memory, handoffs

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- =============================================================================
-- COORDINATION LAYER
-- =============================================================================

-- Sessions: Cross-terminal awareness
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    project TEXT NOT NULL,
    working_on TEXT,
    started_at TIMESTAMP DEFAULT NOW(),
    last_heartbeat TIMESTAMP DEFAULT NOW()
);

-- File Claims: Cross-terminal file locking
CREATE TABLE IF NOT EXISTS file_claims (
    file_path TEXT NOT NULL,
    project TEXT NOT NULL,
    session_id TEXT,
    claimed_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (file_path, project)
);

-- =============================================================================
-- MEMORY LAYER
-- =============================================================================

-- Archival Memory: Long-term learnings with embeddings
-- Note: Using 1024 dimensions for BGE-large-en-v1.5 embeddings
-- project_id: Hash of project root path for project-scoped queries
-- scope: PROJECT (default) or GLOBAL (cross-project patterns like Windows issues)
CREATE TABLE IF NOT EXISTS archival_memory (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_id TEXT NOT NULL,
    agent_id TEXT,
    project_id TEXT,
    scope TEXT CHECK(scope IN ('PROJECT', 'GLOBAL')) DEFAULT 'PROJECT',
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    embedding vector(1024),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_archival_session ON archival_memory(session_id);
CREATE INDEX IF NOT EXISTS idx_archival_agent ON archival_memory(session_id, agent_id);
CREATE INDEX IF NOT EXISTS idx_archival_project ON archival_memory(project_id, scope);
CREATE INDEX IF NOT EXISTS idx_archival_scope ON archival_memory(scope);
CREATE INDEX IF NOT EXISTS idx_archival_created ON archival_memory(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_archival_content_fts ON archival_memory
    USING gin(to_tsvector('english', content));
CREATE INDEX IF NOT EXISTS idx_archival_embedding_hnsw ON archival_memory
    USING hnsw(embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- HANDOFFS LAYER
-- =============================================================================

-- Handoffs: Session handoffs/task completions with embeddings for semantic search
CREATE TABLE IF NOT EXISTS handoffs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    session_name TEXT NOT NULL,
    file_path TEXT UNIQUE NOT NULL,
    format TEXT DEFAULT 'yaml',
    session_id TEXT,
    agent_id TEXT,
    root_span_id TEXT,
    jsonl_path TEXT,
    goal TEXT,
    what_worked TEXT,
    what_failed TEXT,
    key_decisions TEXT,
    outcome TEXT CHECK(outcome IN ('SUCCEEDED','PARTIAL_PLUS','PARTIAL_MINUS','FAILED','UNKNOWN')),
    outcome_notes TEXT,
    content TEXT,
    embedding VECTOR(1024),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    indexed_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_handoffs_session ON handoffs(session_name);
CREATE INDEX IF NOT EXISTS idx_handoffs_session_id ON handoffs(session_id);
CREATE INDEX IF NOT EXISTS idx_handoffs_root_span ON handoffs(root_span_id);
CREATE INDEX IF NOT EXISTS idx_handoffs_created ON handoffs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_handoffs_outcome ON handoffs(outcome);
CREATE INDEX IF NOT EXISTS idx_handoffs_goal_fts ON handoffs
    USING gin(to_tsvector('english', COALESCE(goal, '')));
CREATE INDEX IF NOT EXISTS idx_handoffs_embedding_hnsw ON handoffs
    USING hnsw(embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);

-- =============================================================================
-- PAGEINDEX LAYER (Tree-based RAG)
-- =============================================================================

-- PageIndex Trees: Hierarchical tree indexes for markdown documents
-- Uses LLM reasoning for retrieval (98.7% accuracy vs ~50% for vector similarity)
CREATE TABLE IF NOT EXISTS pageindex_trees (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    project_id TEXT NOT NULL,
    doc_path TEXT NOT NULL,
    doc_type TEXT CHECK(doc_type IN ('ROADMAP', 'DOCUMENTATION', 'ARCHITECTURE', 'README', 'OTHER')),
    tree_structure JSONB NOT NULL,
    doc_hash TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(project_id, doc_path)
);

CREATE INDEX IF NOT EXISTS idx_pageindex_project ON pageindex_trees(project_id);
CREATE INDEX IF NOT EXISTS idx_pageindex_doctype ON pageindex_trees(doc_type);
CREATE INDEX IF NOT EXISTS idx_pageindex_updated ON pageindex_trees(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_pageindex_tree_gin ON pageindex_trees USING gin(tree_structure jsonb_path_ops);
