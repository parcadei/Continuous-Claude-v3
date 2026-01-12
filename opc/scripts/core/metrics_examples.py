"""
Example Metrics Integrations for Continuous-Claude-v3

This file demonstrates how to integrate metrics into the core scripts.
Copy these patterns into the actual scripts.

1. memory_daemon.py integration
2. recall_learnings.py integration
3. store_learning.py integration
4. stream_monitor.py integration
5. mcp_client.py integration
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
import time

# Import metrics module
from scripts.core.metrics import (
    # Module-level metrics
    memory_daemon_cycles,
    memory_daemon_extractions,
    memory_daemon_extraction_duration,
    memory_daemon_queue_depth,
    memory_daemon_active_extractions,
    memory_daemon_restarts,
    memory_daemon_stale_sessions,
    recall_queries_total,
    recall_query_latency,
    recall_cache_hits,
    recall_cache_misses,
    recall_embedding_latency,
    store_operations_total,
    store_latency,
    store_deduplication_skipped,
    store_embedding_time,
    store_learning_types,
    store_confidence_levels,
    stream_events_processed,
    stream_stuck_detections,
    stream_turn_count,
    stream_redis_publishes,
    stream_active_monitors,
    mcp_connection_state,
    mcp_tool_calls,
    mcp_tool_latency,
    mcp_connection_latency,
    mcp_cache_hits,
    mcp_cache_misses,
    mcp_servers_connected,
    postgres_pool_size,
    postgres_pool_acquire_time,
    redis_memory_bytes,
    process_memory_bytes,
    process_cpu_percent,
    process_open_fds,

    # Context managers
    MemoryDaemonMetrics,
    RecallMetrics,
    StoreMetrics,
    StreamMonitorMetrics,
    MCPMetrics,
    SystemMetrics,

    # Decorators
    track_latency,
    track_counter,
    timed_operation,
)


# =============================================================================
# 1. INTEGRATION: memory_daemon.py
# =============================================================================

"""
Changes to make in memory_daemon.py:

1. Add imports at the top:
   from scripts.core.metrics import (
       MemoryDaemonMetrics, memory_daemon_cycles, memory_daemon_stale_sessions,
       memory_daemon_queue_depth, memory_daemon_active_extractions,
       memory_daemon_extraction_duration, memory_daemon_restarts,
   )

2. Add module-level metric context:
   memory_daemon_metrics = MemoryDaemonMetrics()

3. In daemon_loop(), wrap the main operations:

   def daemon_loop():
       db_type = "PostgreSQL" if use_postgres() else "SQLite"
       log(f"Memory daemon started (using {db_type}, max_concurrent={MAX_CONCURRENT_EXTRACTIONS})")
       ensure_schema()

       while True:
           try:
               # Reap completed processes and process pending queue
               completed = reap_completed_extractions()
               memory_daemon_metrics.update_queue_state(
                   queue_depth=len(pending_queue),
                   active=len(active_extractions)
               )
               spawned = process_pending_queue()

               # Find new stale sessions
               stale = get_stale_sessions()
               memory_daemon_metrics.record_cycle(stale_count=len(stale))

               if stale:
                   log(f"Found {len(stale)} stale sessions")
                   for session_id, project in stale:
                       with memory_daemon_metrics.extraction(session_id, project or ""):
                           queue_or_extract(session_id, project or "")
                       mark_extracted(session_id)
           except Exception as e:
               log(f"Error in daemon loop: {e}")
               memory_daemon_restarts.labels(reason="error").inc()

           time.sleep(POLL_INTERVAL)

4. In extract_memories(), wrap subprocess call:

   def extract_memories(session_id: str, project_dir: str):
       start = time.perf_counter()
       try:
           # ... existing extraction logic ...
       finally:
           duration = time.perf_counter() - start
           memory_daemon_extraction_duration.labels(status="success").observe(duration)
"""


# =============================================================================
# 2. INTEGRATION: recall_learnings.py
# =============================================================================

"""
Changes to make in recall_learnings.py:

1. Add imports:
   from scripts.core.metrics import (
       RecallMetrics, recall_queries_total, recall_query_latency,
       recall_cache_hits, recall_cache_misses, recall_embedding_latency,
   )

2. Add module-level metric context:
   recall_metrics = RecallMetrics()

3. Wrap search functions:

   async def search_learnings_postgres(...) -> list[dict[str, Any]]:
       with recall_metrics.query(backend="postgres", search_type="vector"):
           # ... existing logic ...

       # Track embedding time
       recall_metrics.record_embedding_time(provider=provider, duration=embed_time)

       return results

   async def search_learnings_hybrid_rrf(...) -> list[dict[str, Any]]:
       with recall_metrics.query(backend="postgres", search_type="hybrid_rrf"):
           # ... existing logic ...

4. In main(), track cache hits/misses based on results:

   results = await search_learnings_hybrid_rrf(...)

   if len(results) > 0:
       recall_metrics.record_cache_hit("results")
   else:
       recall_metrics.record_cache_miss("results")
"""


# =============================================================================
# 3. INTEGRATION: store_learning.py
# =============================================================================

"""
Changes to make in store_learning.py:

1. Add imports:
   from scripts.core.metrics import (
       StoreMetrics, store_operations_total, store_latency,
       store_deduplication_skipped, store_embedding_time,
       store_learning_types, store_confidence_levels,
   )

2. Add module-level metric context:
   store_metrics = StoreMetrics()

3. Wrap store_learning_v2():

   async def store_learning_v2(...) -> dict:
       with store_metrics.store(backend=backend):
           # ... embedding logic ...
           store_metrics.record_embedding_time(provider="local", duration=embed_time)

           # ... dedup logic ...
           if existing and similarity >= DEDUP_THRESHOLD:
               store_metrics.record_deduplication(
                   backend=backend,
                   skipped=True,
                   reason="similarity_threshold"
               )
               return {"success": True, "skipped": True, ...}

           # ... store logic ...

       store_metrics.record_learning_type(learning_type or "unknown")
       if confidence:
           store_metrics.record_confidence(confidence)

       return {"success": True, "memory_id": memory_id, ...}
"""


# =============================================================================
# 4. INTEGRATION: stream_monitor.py
# =============================================================================

"""
Changes to make in stream_monitor.py:

1. Add imports:
   from scripts.core.metrics import (
       StreamMonitorMetrics, stream_events_processed,
       stream_stuck_detections, stream_turn_count,
       stream_redis_publishes, stream_active_monitors,
   )

2. Add module-level metric context:
   stream_metrics = StreamMonitorMetrics()

3. In StreamMonitor class __init__:
   class StreamMonitor:
       def __init__(self, ...):
           stream_active_monitors.inc()  # Track new monitor

           self._redis_errors = 0
           self._redis_success = 0

4. In _process_event(), add metrics:
   def _process_event(self, event: StreamEvent) -> None:
       stream_metrics.record_event(self.agent_id, event.event_type)

       if event.event_type == "tool_result":
           stream_metrics.update_turn_count(self.agent_id, self._state.turn_count)

       # ... existing stuck detection ...
       if self._state.is_stuck:
           stream_metrics.record_stuck_detection(
               self.agent_id,
               self._state.stuck_reason or "unknown"
           )

       # Redis metrics
       if self.redis_client:
           try:
               # ... existing redis push ...
               stream_metrics.record_redis_publish(self.agent_id, success=True)
           except Exception:
               stream_metrics.record_redis_publish(self.agent_id, success=False)

5. In stop(), add cleanup:
   def stop(self, timeout: float = 5.0) -> None:
       stream_active_monitors.dec()
       # ... existing logic ...
"""


# =============================================================================
# 5. INTEGRATION: mcp_client.py (in .claude/runtime/)
# =============================================================================

"""
Changes to make in .claude/runtime/mcp_client.py:

1. Add imports at the top:
   import time
   from scripts.core.metrics import (
       MCPMetrics, mcp_connection_state, mcp_tool_calls,
       mcp_tool_latency, mcp_connection_latency,
       mcp_cache_hits, mcp_cache_misses, mcp_servers_connected,
   )

2. Add module-level metric context:
   mcp_metrics = MCPMetrics()

3. In _connect_stdio(), _connect_sse(), _connect_http():

   async def _connect_stdio(self, server_name: str, config: ServerConfig) -> None:
       start = time.perf_counter()
       try:
           # ... existing connection logic ...
           mcp_metrics.record_connection(server_name, "stdio", time.perf_counter() - start, True)
       except Exception as e:
           mcp_metrics.record_connection(server_name, "stdio", time.perf_counter() - start, False)
           raise

4. In _get_server_tools(), track cache hits/misses:

   async def _get_server_tools(self, server_name: str) -> list[Tool]:
       if server_name in self._tool_cache:
           mcp_metrics.record_cache_hit(server_name)
           return self._tool_cache[server_name]
       # ... existing logic ...
       self._tool_cache[server_name] = tools
       mcp_metrics.record_cache_miss(server_name)
       return tools

5. In call_tool(), track latency and success:

   async def call_tool(self, tool_identifier: str, params: dict[str, Any], max_retries: int = 1) -> Any:
       # ... existing setup ...

       for attempt in range(max_retries + 1):
           start = time.perf_counter()
           try:
               # ... existing tool call ...
               mcp_metrics.record_tool_call(
                   server_name=server_name,
                   tool_name=tool_name,
                   duration=time.perf_counter() - start,
                   success=True,
                   retries=attempt,
               )
               return result
           except Exception as e:
               if attempt < max_retries:
                   mcp_retries.labels(server_name=server_name, tool_name=tool_name).inc()

       mcp_metrics.record_tool_call(
           server_name=server_name,
           tool_name=tool_name,
           duration=time.perf_counter() - start,
           success=False,
           retries=max_retries,
       )
       raise ToolExecutionError(...)

6. In cleanup(), update connection state:

   async def cleanup(self) -> None:
       for server_name in list(self._session_contexts.keys()):
           # ... existing cleanup ...
           mcp_metrics.record_disconnection(server_name, transport="stdio")

       mcp_metrics.update_connection_count(0)
"""


# =============================================================================
# 6. SYSTEM METRICS INTEGRATION
# =============================================================================

"""
For system metrics (PostgreSQL, Redis, Process), integrate with your server:

from scripts.core.metrics import SystemMetrics, PostgresPoolCollector, RedisStatsCollector
from scripts.core.db.postgres_pool import get_pool

system_metrics = SystemMetrics()

# Collect system metrics periodically
async def collect_system_metrics():
    while True:
        system_metrics.collect()
        await asyncio.sleep(15)
        asyncio.create_task(collect_system_metrics())

# For PostgreSQL pool metrics (in postgres_pool.py or your main server):
pool_collector = PostgresPoolCollector(get_pool)
REGISTRY.register(pool_collector)

# For Redis metrics:
redis_collector = RedisStatsCollector(redis_client)
REGISTRY.register(redis_collector)
"""


# =============================================================================
# COMPLETE EXAMPLE: metrics_server.py integration
# =============================================================================

"""
Complete example for running metrics server alongside your main application:

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from scripts.core.metrics_server import create_metrics_app
from scripts.core.metrics import system

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# Mount metrics endpoint
metrics_app = create_metrics_app()
app.mount("/metrics", metrics_app)

@app.on_event("startup")
async def startup():
    import asyncio
    asyncio.create_task(_collect_loop())

async def _collect_loop():
    while True:
        try:
            system.collect()
        except Exception:
            pass
        await asyncio.sleep(15)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
"""
