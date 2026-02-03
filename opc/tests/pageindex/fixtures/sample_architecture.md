# Architecture

## Overview
System architecture document.

## Components

### Memory System
Handles persistent storage of learnings.

#### PostgreSQL Backend
Primary data store with pgvector.

#### Embedding Service
Generates embeddings for semantic search.

### Hook System
Intercepts Claude Code events.

#### PreToolUse Hooks
Run before tool execution.

#### PostToolUse Hooks
Run after tool execution.

## Data Flow
1. User input
2. Hook processing
3. Memory query
4. Response generation
