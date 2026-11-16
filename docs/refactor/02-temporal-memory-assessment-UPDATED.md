# Temporal Memory Assessment

**Reference:** See [00-architecture-decisions.md](./00-architecture-decisions.md) for authoritative Round 3 decisions (113+ total decisions).

## Overview

Evaluation of the temporal memory system for session history, learnings, and cross-session continuity.

## Current State (As-Is)

### Implementation

```python
# scripts/temporal_memory/store.py
class TemporalStore:
    """PostgreSQL-backed session history"""

    def store_fact(self, session_id: str, fact: dict):
        """Store temporal fact"""
        self.db.execute("""
            INSERT INTO temporal_facts (session_id, fact_type, content, timestamp)
            VALUES (?, ?, ?, ?)
        """, (session_id, fact['type'], fact['content'], now()))

    def recall_facts(self, query: str, session_id: str = None):
        """Recall facts via vector search"""
        embedding = self.embed(query)
        results = self.db.vector_search(embedding, limit=10)

        if session_id:
            results = [r for r in results if r.session_id == session_id]

        return results
```

### Storage Schema

```sql
CREATE TABLE temporal_facts (
    id UUID PRIMARY KEY,
    session_id TEXT NOT NULL,
    fact_type TEXT NOT NULL,  -- 'decision', 'learning', 'pattern'
    content TEXT NOT NULL,
    embedding VECTOR(1536),   -- OpenAI embeddings
    timestamp TIMESTAMPTZ NOT NULL,
    metadata JSONB
);

CREATE INDEX idx_temporal_session ON temporal_facts(session_id);
CREATE INDEX idx_temporal_embedding ON temporal_facts USING ivfflat(embedding vector_cosine_ops);
```

### Current Usage

1. **Session Start Hook**: Load recent facts for context
2. **Post-Tool-Use Hook**: Store decisions/learnings
3. **Session End Hook**: Summarize session, store key facts

## Problems Identified

### 1. Recall Granularity

**Issue**: Vector search returns too many or too few results

```python
# Current (fixed top-k)
results = recall_facts("authentication pattern", limit=10)
# Sometimes 10 is too few, sometimes too many
```

**Impact**: Context pollution or missing critical facts

### 2. Session Isolation

**Issue**: Cross-session recall pollutes context with irrelevant facts

```python
# Current (no session filtering)
results = recall_facts("API design")
# Returns facts from unrelated sessions
```

**Impact**: Confusing historical decisions with current context

### 3. Fact Staleness

**Issue**: No expiration or relevance decay

```python
# Current (no staleness)
results = recall_facts("deployment strategy")
# Returns facts from 6 months ago (potentially obsolete)
```

**Impact**: Outdated advice treated as current truth

### 4. Embedding Cost

**Issue**: Every fact stored requires embedding generation

```python
# Current (embed everything)
for fact in session_facts:
    embedding = openai.embed(fact.content)  # $0.0001 per fact
    store_fact(fact, embedding)
```

**Impact**: Accumulates cost over time ($10-50/month for active use)

## Future State (To-Be)

### 1. Adaptive Recall

```python
class AdaptiveRecall:
    """Adjust recall depth based on query specificity"""

    def recall(self, query: str) -> list[Fact]:
        # Specific query → fewer results
        if self.is_specific(query):
            return self.vector_search(query, limit=3)

        # Broad query → more results
        return self.vector_search(query, limit=20)

    def is_specific(self, query: str) -> bool:
        """Check if query is specific (e.g., mentions file paths, function names)"""
        return any([
            '/' in query,           # File path
            '()' in query,          # Function call
            query.startswith('How') # Specific question
        ])
```

### 2. Session-Scoped Recall

```python
class SessionScopedRecall:
    """Separate current-session facts from historical facts"""

    def recall(self, query: str, session_id: str) -> RecallResults:
        # Current session facts (high priority)
        current = self.search(query, session_id=session_id, limit=5)

        # Historical facts (lower priority)
        historical = self.search(query, exclude_session=session_id, limit=10)

        return RecallResults(
            current=current,
            historical=historical,
            merge_strategy='current_first'
        )
```

### 3. Staleness Decay

```python
class StalenessDecay:
    """Reduce relevance of old facts"""

    def score_fact(self, fact: Fact, query_embedding: vector) -> float:
        # Cosine similarity
        similarity = cosine(fact.embedding, query_embedding)

        # Age penalty (decay over 90 days)
        age_days = (now() - fact.timestamp).days
        age_penalty = max(0, 1 - (age_days / 90))

        # Combined score
        return similarity * age_penalty
```

### 4. Embedding Optimization

```python
class EmbeddingOptimization:
    """Reduce embedding costs"""

    def should_embed(self, fact: Fact) -> bool:
        """Only embed important facts"""
        return fact.type in ['decision', 'pattern', 'learning']
        # Skip ephemeral facts (e.g., "ran test", "fixed typo")

    def batch_embed(self, facts: list[Fact]):
        """Batch embedding requests (cheaper)"""
        contents = [f.content for f in facts]
        embeddings = openai.embed_batch(contents)  # Single API call
        for fact, emb in zip(facts, embeddings):
            fact.embedding = emb
```

## Migration Strategy

### Phase 1: Session Scoping (Immediate)

**Goal**: Separate current-session from historical facts

**Changes**:
```python
# Add session_id parameter to recall
def recall_facts(query: str, session_id: str = None) -> RecallResults
```

**Testing**:
```python
# Test session isolation
facts = recall_facts("API design", session_id="current")
assert all(f.session_id == "current" for f in facts.current)
```

### Phase 2: Staleness Decay (Week 2)

**Goal**: Downweight old facts

**Changes**:
```python
# Add age penalty to scoring
def score_fact(fact, query_embedding):
    similarity = cosine(fact.embedding, query_embedding)
    age_penalty = calculate_age_penalty(fact.timestamp)
    return similarity * age_penalty
```

**Testing**:
```python
# Test age penalty
old_fact = create_fact(timestamp=now() - timedelta(days=100))
new_fact = create_fact(timestamp=now())
assert score_fact(new_fact, query) > score_fact(old_fact, query)
```

### Phase 3: Embedding Optimization (Week 3)

**Goal**: Reduce embedding costs

**Changes**:
```python
# Filter ephemeral facts
if fact.type in ['decision', 'pattern', 'learning']:
    embed_and_store(fact)
else:
    store_without_embedding(fact)  # Still searchable via SQL
```

**Testing**:
```python
# Test selective embedding
ephemeral = Fact(type='status_update', content='ran tests')
assert not should_embed(ephemeral)

important = Fact(type='decision', content='chose PostgreSQL')
assert should_embed(important)
```

### Phase 4: Adaptive Recall (Week 4)

**Goal**: Adjust recall depth dynamically

**Changes**:
```python
# Adaptive limit
limit = 3 if is_specific(query) else 20
results = vector_search(query, limit=limit)
```

**Testing**:
```python
# Test adaptive limits
specific_query = "How does authenticate() work?"
broad_query = "How does authentication work?"

assert len(recall(specific_query)) < len(recall(broad_query))
```

## SpawnQueue Integration (Round 3 Update)

**Previous (Deprecated)**: Temporal memory was accessed via "Agentica Scope" abstraction

**Current (Round 3)**: Temporal memory is accessed directly via scripts

### Migration from Agentica Scope

```python
# OLD (deprecated - Agentica Scope pattern)
from agentica import Scope

scope = Scope()
facts = scope.recall("authentication pattern")  # Abstraction layer

# NEW (current - Direct access)
from scripts.temporal_memory.store import TemporalStore

store = TemporalStore()
facts = store.recall_facts("authentication pattern", session_id=current_session_id)
```

**Why Changed**:
- Agentica Scope was an unnecessary abstraction layer
- Direct access to TemporalStore is clearer and more explicit
- SpawnQueue replaced Oracle agent, eliminating the Scope pattern

### SpawnQueue Coordination Pattern

```python
# SpawnQueue uses temporal memory for spawn decisions
from scripts.agentica_patterns.spawn_queue import SpawnQueue
from scripts.temporal_memory.store import TemporalStore

class SpawnQueue:
    def __init__(self):
        self.temporal = TemporalStore()

    async def should_spawn(self, agent_type: str, task: str) -> bool:
        """Check if similar task recently completed"""
        recent_facts = self.temporal.recall_facts(
            query=f"{agent_type} {task}",
            session_id=self.current_session_id,
            max_age_hours=1  # Only last hour
        )

        # Don't re-spawn if just completed
        if any(f.fact_type == 'task_completed' for f in recent_facts):
            return False

        return True
```

## Performance Metrics

### Current Performance

```
Operation             | Latency | Cost/op
----------------------|---------|--------
Store fact            | 50ms    | $0.0001 (embedding)
Recall facts (top-10) | 200ms   | $0 (cached embeddings)
Session load          | 500ms   | $0 (bulk load)
```

### Target Performance (Post-Migration)

```
Operation             | Latency | Cost/op
----------------------|---------|--------
Store fact (filtered) | 50ms    | $0.00005 (50% reduction via filtering)
Recall facts (adaptive) | 150ms | $0 (25% faster via better indexing)
Session load          | 300ms   | $0 (40% faster via session scoping)
```

## Monitoring

### Metrics to Track

```python
# Temporal memory health
temporal_metrics = {
    'facts_stored_per_session': 15,      # Average
    'recall_latency_p95': 250,           # ms
    'embedding_cost_per_day': 0.50,      # USD
    'stale_facts_returned': 0.05,        # 5% of results
    'session_isolation_accuracy': 0.98   # 98% correct scoping
}
```

### Alerts

```python
# Alert if recall performance degrades
if temporal_metrics['recall_latency_p95'] > 500:
    alert("Temporal recall latency high - check index performance")

# Alert if embedding costs spike
if temporal_metrics['embedding_cost_per_day'] > 2.00:
    alert("Embedding costs high - check filtering logic")
```

## Testing Strategy

### Unit Tests

```python
# Test session scoping
def test_session_scoped_recall():
    store = TemporalStore()

    # Store facts in different sessions
    store.store_fact('session-1', {'type': 'decision', 'content': 'Use PostgreSQL'})
    store.store_fact('session-2', {'type': 'decision', 'content': 'Use MongoDB'})

    # Recall should only return current session
    results = store.recall_facts('database choice', session_id='session-1')
    assert len(results.current) == 1
    assert results.current[0].content == 'Use PostgreSQL'

# Test staleness decay
def test_staleness_decay():
    store = TemporalStore()

    old_fact = Fact(timestamp=now() - timedelta(days=100))
    new_fact = Fact(timestamp=now())

    old_score = store.score_fact(old_fact, query_embedding)
    new_score = store.score_fact(new_fact, query_embedding)

    assert new_score > old_score
```

### Integration Tests

```python
# Test end-to-end flow
def test_temporal_memory_e2e():
    # Session 1: Store decision
    session1 = TemporalStore(session_id='test-1')
    session1.store_fact({'type': 'decision', 'content': 'Use REST API'})

    # Session 2: Recall decision
    session2 = TemporalStore(session_id='test-2')
    results = session2.recall_facts('API design')

    # Should find historical fact
    assert len(results.historical) > 0
    assert 'REST API' in results.historical[0].content
```

## Related Decisions

From [00-architecture-decisions.md](./00-architecture-decisions.md):

- **SpawnQueue > Oracle**: Spawn coordination moved from Oracle agent to SpawnQueue
- **Direct Access > Agentica Scope**: Temporal memory accessed directly, not via Scope abstraction
- **Session Isolation**: Current-session facts separated from historical facts
- **Archive Strategy**: Old temporal sessions → `docs/archive/temporal/`
- **PostgreSQL**: Temporal facts stored in PostgreSQL (not SQLite)

## Future Enhancements

1. **Fact Relationships**: Link related facts (e.g., decision → implementation → outcome)
2. **Automatic Summarization**: LLM summarizes session facts at end
3. **Fact Validation**: Mark facts as confirmed/unconfirmed, update as validated
4. **Cross-Project Recall**: Query temporal memory across multiple projects

## References

- [Agent Orchestration](./05-agent-orchestration.md) - SpawnQueue coordination patterns
- [Temporal Archival](./20-temporal-archival.md) - Archiving old temporal sessions
- [Concurrency Coordination](./06-concurrency-coordination.md) - SpawnQueue implementation
- [Architecture Map](./01-architecture-map.md) - Overall system architecture
