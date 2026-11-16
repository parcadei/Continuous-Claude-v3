"""Span processor for two-pass decision extraction.

Handles large span datasets with cross-reference resolution using:
- Reference-aware chunking
- Two-pass Map/Reduce (summaries then decisions)
- Blackboard-style shared state

Pipeline:
1. Pre-scan: Build reference graph
2. Chunking: Group by connected components
3. Pass 1: Extract summaries (no cross-refs)
4. Embed: Batch embed summaries
5. Pass 2: Extract decisions (with reference context)
6. Persist: Store to PostgreSQL

Usage:
    processor = SpanProcessor(
        session_id="abc123",
        num_mappers=4,
        max_chunk_size=50,
    )
    result = await processor.process(spans)
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

# Import for module-level availability (used by test mocks)
from scripts.agentica_patterns.embedding_service import EmbeddingService
from scripts.agentica_patterns.memory_service_pg import MemoryServicePG

# Import MapReduce from patterns
from scripts.agentica_patterns.patterns import MapReduce

# =============================================================================
# Helper Functions
# =============================================================================


def _extract_json_from_response(response: str) -> str:
    """Extract JSON from LLM response, stripping markdown fences.

    LLMs commonly wrap JSON responses in markdown code blocks like:
    ```json
    {"key": "value"}
    ```

    This function strips those fences to allow json.loads() to parse.

    Args:
        response: Raw LLM response string

    Returns:
        Cleaned string ready for json.loads()
    """
    response = response.strip()
    if response.startswith("```"):
        lines = response.split("\n")
        # Remove opening fence (```json or ```)
        if lines[0].startswith("```"):
            lines = lines[1:]
        # Remove closing fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        response = "\n".join(lines)
    return response


# =============================================================================
# Phase 1: Data Structures
# =============================================================================


@dataclass
class SpanSummary:
    """Summary extracted from a span in Pass 1.

    Attributes:
        span_id: Original Braintrust span ID
        turn_number: Position in session
        summary: 2-3 sentence summary (50-100 tokens)
        key_entities: Entities mentioned (names, files, concepts)
        references: Span IDs this span references
        span_type: Type of span (tool_call, llm_reasoning, user_input, agent_output)
        content_hash: Deterministic hash for deduplication
    """

    span_id: str
    turn_number: int
    summary: str
    key_entities: list[str]
    references: list[str]
    span_type: str
    content_hash: str


@dataclass
class SpanDecision:
    """Decision extracted from a span in Pass 2.

    Attributes:
        span_id: Original Braintrust span ID
        decision: The decision made
        rationale: Why the decision was made
        confidence: Confidence score (0.0-1.0)
        source_refs: Span IDs that informed this decision
    """

    span_id: str
    decision: str
    rationale: str
    confidence: float
    source_refs: list[str]


@dataclass
class SpanProcessingContext:
    """Async-safe shared context for span processing.

    Acts as a Blackboard for the two-pass pipeline, storing
    summaries from Pass 1 for use in Pass 2.

    Uses asyncio.Lock for safe concurrent access from async contexts.

    Attributes:
        span_summaries: Dict mapping span_id -> SpanSummary
        reference_graph: Dict mapping span_id -> list of referenced span_ids
        processing_log: List of processing events for debugging
    """

    span_summaries: dict[str, SpanSummary] = field(default_factory=dict)
    reference_graph: dict[str, list[str]] = field(default_factory=dict)
    processing_log: list[dict[str, Any]] = field(default_factory=list)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def add_summary(self, summary: SpanSummary) -> None:
        """Add a span summary (async-safe).

        Args:
            summary: SpanSummary to add
        """
        async with self._lock:
            self.span_summaries[summary.span_id] = summary
            self.reference_graph[summary.span_id] = summary.references
            self.processing_log.append({
                "action": "add_summary",
                "span_id": summary.span_id,
            })

    async def get_reference_context(self, span_id: str) -> str:
        """Get summary context for all spans this span references.

        Args:
            span_id: Span to get reference context for

        Returns:
            Formatted string with referenced span summaries
        """
        async with self._lock:
            refs = self.reference_graph.get(span_id, [])
            contexts = []
            for ref_id in refs:
                if ref_id in self.span_summaries:
                    summary = self.span_summaries[ref_id]
                    contexts.append(f"[{ref_id}]: {summary.summary}")
            return "\n".join(contexts)

    async def all_summaries(self) -> list[SpanSummary]:
        """Get all summaries (async-safe copy).

        Returns:
            List of all SpanSummary objects
        """
        async with self._lock:
            return list(self.span_summaries.values())


@dataclass
class SpanProcessingResult:
    """Result from SpanProcessor.process().

    Captures all pipeline metrics for reporting and debugging.
    """

    session_id: str
    spans_processed: int
    summaries_extracted: int
    decisions_extracted: int
    summaries_persisted: int
    decisions_persisted: int
    duration_seconds: float
    errors: list[str] = field(default_factory=list)


# =============================================================================
# Phase 2: Reference Graph Builder
# =============================================================================


def _extract_file_path(span: dict[str, Any]) -> str | None:
    """Extract file path from span input/metadata.

    Handles various input formats:
    - Dict with file_path key: {"file_path": "/path/to/file"}
    - Dict with path key: {"path": "/src"}
    - Nested file_path: {"params": {"file_path": "/path"}}
    - JSON string: '{"file_path": "/path/to/file"}'

    Args:
        span: Span dict from Braintrust

    Returns:
        File path string or None if not found
    """
    input_data = span.get("input", {})

    if isinstance(input_data, dict):
        # Direct file_path or path key
        path = input_data.get("file_path") or input_data.get("path")
        if path:
            return path
        # Check nested params
        params = input_data.get("params", {})
        if isinstance(params, dict):
            path = params.get("file_path") or params.get("path")
            if path:
                return path
    elif isinstance(input_data, str):
        # Try JSON parse for string inputs
        try:
            parsed = json.loads(input_data)
            if isinstance(parsed, dict):
                path = parsed.get("file_path") or parsed.get("path")
                if path:
                    return path
                # Check nested params
                params = parsed.get("params", {})
                if isinstance(params, dict):
                    return params.get("file_path") or params.get("path")
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def _normalize_path(path: str) -> str:
    """Normalize path for comparison (resolve ./ and //).

    Args:
        path: File path string

    Returns:
        Normalized path string
    """
    import os.path
    return os.path.normpath(path)


def _extract_file_paths_from_output(span: dict[str, Any]) -> list[str]:
    """Extract file paths from Glob/Grep output for linking.

    Handles:
    - Glob output: list of file paths
    - Grep output: "filepath:line:content" format

    Args:
        span: Span dict from Braintrust

    Returns:
        List of file paths found in output
    """
    output = span.get("output")
    tool_name = (span.get("metadata") or {}).get("tool_name", "")
    paths: list[str] = []

    if tool_name == "Glob":
        # Glob returns list of paths
        if isinstance(output, list):
            for item in output:
                if isinstance(item, str):
                    paths.append(item)
        elif isinstance(output, str):
            # Try parsing as JSON list
            try:
                parsed = json.loads(output)
                if isinstance(parsed, list):
                    paths.extend([p for p in parsed if isinstance(p, str)])
            except (json.JSONDecodeError, TypeError):
                pass

    elif tool_name == "Grep":
        # Grep returns "filepath:line:content" format
        if isinstance(output, str):
            for line in output.split("\n"):
                if ":" in line:
                    # Extract file path before first colon
                    file_path = line.split(":")[0]
                    if file_path.startswith("/"):
                        paths.append(file_path)

    return paths


def build_reference_graph(spans: list[dict[str, Any]]) -> dict[str, list[str]]:
    """Pre-scan spans to build reference graph.

    Detection tiers (in order of confidence):
    0. span_parents structural hierarchy (100% confidence)
    1. File path references - same file operations (90% confidence)
    2. Tool output IDs matching prior tool input IDs (high confidence)
    3. Explicit mentions ("As discussed in...", "Based on earlier...")
    4. Turn proximity (spans within N turns often reference each other)

    Args:
        spans: List of span dicts from Braintrust

    Returns:
        Dict mapping span_id -> list of referenced span_ids
    """
    graph: dict[str, list[str]] = {}

    if not spans:
        return graph

    # Build span index for fast lookup
    span_by_id = {s.get("span_id", ""): s for s in spans}
    span_order = [s.get("span_id", "") for s in spans]

    # Reference patterns
    explicit_patterns = [
        r"as discussed (?:in|earlier|above)",
        r"based on (?:the|earlier|prior)",
        r"referring to",
        r"see (?:span|turn|above)",
    ]

    # Pre-build file path index for P2 detection (Tier 2: 90% confidence)
    # Maps normalized path -> list of (span_id, position_index) tuples
    file_paths_index: dict[str, list[tuple[str, int]]] = {}
    # Also track Glob/Grep output paths for linking search -> read patterns
    search_output_paths: dict[str, list[tuple[str, int]]] = {}

    for idx, span in enumerate(spans):
        span_id = span.get("span_id", "")

        # Index file paths from input
        path = _extract_file_path(span)
        if path:
            norm_path = _normalize_path(path)
            if norm_path not in file_paths_index:
                file_paths_index[norm_path] = []
            file_paths_index[norm_path].append((span_id, idx))

        # Index file paths from Glob/Grep output
        output_paths = _extract_file_paths_from_output(span)
        for out_path in output_paths:
            norm_path = _normalize_path(out_path)
            if norm_path not in search_output_paths:
                search_output_paths[norm_path] = []
            search_output_paths[norm_path].append((span_id, idx))

    for span in spans:
        span_id = span.get("span_id", "")
        refs: list[str] = []

        # 0. Parent span structural reference (Tier 1: 100% confidence)
        # This is the most reliable reference detection - based on explicit
        # structural data from Braintrust span tree, not heuristics.
        # Note: Braintrust returns span_parents as an array (may have multiple parents)
        span_parents = span.get("span_parents") or []
        if isinstance(span_parents, str):
            span_parents = [span_parents]  # Handle legacy single-value format
        for parent_id in span_parents:
            if parent_id and parent_id != span_id and parent_id in span_by_id:
                refs.append(parent_id)

        # 1. File path reference detection (Tier 2: 90% confidence)
        # Spans operating on the same file should be linked
        current_path = _extract_file_path(span)
        if current_path:
            norm_path = _normalize_path(current_path)
            current_idx = span_order.index(span_id) if span_id in span_order else -1

            # Check for prior spans with same file path
            for prior_id, prior_idx in file_paths_index.get(norm_path, []):
                if prior_id != span_id and prior_idx < current_idx:
                    if prior_id not in refs:
                        refs.append(prior_id)

            # Check for prior Glob/Grep that found this file
            for prior_id, prior_idx in search_output_paths.get(norm_path, []):
                if prior_id != span_id and prior_idx < current_idx:
                    if prior_id not in refs:
                        refs.append(prior_id)

        # 2. Tool output -> input matching (Tier 3)
        output = span.get("output")
        if output:
            output_str = str(output)
            for prior_id in span_order:
                if prior_id == span_id:
                    break  # Only check prior spans
                prior_span = span_by_id.get(prior_id, {})
                prior_input = str(prior_span.get("input", ""))
                # Check if output references prior input content
                if len(prior_input) > 20 and prior_input[:50] in output_str:
                    if prior_id not in refs:
                        refs.append(prior_id)

        # 3. Explicit pattern matching - ONLY for LLM spans (Tier 4)
        span_type = (span.get("span_attributes") or {}).get("type", "llm")
        if span_type == "llm":
            content = str(span.get("input", "")) + str(span.get("output", ""))
            for pattern in explicit_patterns:
                if re.search(pattern, content, re.IGNORECASE):
                    # Reference likely to prior N spans
                    idx = span_order.index(span_id) if span_id in span_order else -1
                    if idx > 0:
                        # Add prior 3 spans as potential references
                        for i in range(max(0, idx - 3), idx):
                            if span_order[i] not in refs:
                                refs.append(span_order[i])

        graph[span_id] = refs

    return graph


def chunk_by_references(
    spans: list[dict[str, Any]],
    ref_graph: dict[str, list[str]],
    max_chunk_size: int = 50,
    overlap: int = 5,
) -> list[list[dict[str, Any]]]:
    """Chunk spans keeping referenced spans together.

    Algorithm:
    1. Build connected components from reference graph
    2. Components <= max_chunk_size become chunks
    3. Larger components are subdivided with overlap

    Args:
        spans: List of span dicts
        ref_graph: Reference graph from build_reference_graph
        max_chunk_size: Maximum spans per chunk
        overlap: Overlap between adjacent sub-chunks

    Returns:
        List of span chunks
    """
    if not spans:
        return []

    # Build undirected adjacency for connected components
    adj: dict[str, set[str]] = defaultdict(set)
    for span_id, refs in ref_graph.items():
        for ref_id in refs:
            adj[span_id].add(ref_id)
            adj[ref_id].add(span_id)

    # Find connected components via BFS
    visited: set[str] = set()
    components: list[list[str]] = []

    span_by_id = {s.get("span_id", ""): s for s in spans}

    for span in spans:
        span_id = span.get("span_id", "")
        if span_id in visited:
            continue

        # BFS from this span
        component: list[str] = []
        queue = [span_id]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            component.append(current)
            for neighbor in adj[current]:
                if neighbor not in visited:
                    queue.append(neighbor)

        components.append(component)

    # Convert components to chunks
    chunks: list[list[dict[str, Any]]] = []

    for component in components:
        component_spans = [span_by_id[sid] for sid in component if sid in span_by_id]

        if len(component_spans) <= max_chunk_size:
            if component_spans:
                chunks.append(component_spans)
        else:
            # Subdivide with overlap - ensure positive step
            step = max(1, max_chunk_size - overlap)
            for i in range(0, len(component_spans), step):
                chunk = component_spans[i:i + max_chunk_size]
                if chunk:
                    chunks.append(chunk)

    return chunks


# =============================================================================
# Phase 3: Pass 1 - Summary Extraction
# =============================================================================


SUMMARY_EXTRACTION_PREMISE = """You are a span summarizer.

For each span in your assigned chunk, extract:
1. A 2-3 sentence summary (50-100 tokens max)
2. Key entities mentioned (names, files, concepts)
3. The span type (tool_call, llm_reasoning, user_input, agent_output)

Return a JSON array with one object per span:
[
  {
    "span_id": "...",
    "summary": "...",
    "key_entities": ["entity1", "entity2"],
    "span_type": "..."
  }
]

Be concise. Focus on what was done or decided, not implementation details.
"""


def _content_hash(content: str, metadata: dict[str, Any] | None = None) -> str:
    """Generate deterministic hash for deduplication.

    Args:
        content: The content to hash
        metadata: Optional metadata dict

    Returns:
        16-character hex hash string
    """
    normalized = {
        "content": content.strip().lower(),
        "type": metadata.get("type") if metadata else None,
        "span_id": metadata.get("span_id") if metadata else None,
    }
    return hashlib.sha256(json.dumps(normalized, sort_keys=True).encode()).hexdigest()[:16]


async def extract_summaries(
    chunks: list[list[dict[str, Any]]],
    context: SpanProcessingContext,
    num_mappers: int = 4,
) -> None:
    """Pass 1: Extract summaries from spans without cross-reference context.

    Populates context.span_summaries for use in Pass 2.

    Args:
        chunks: Span chunks from chunk_by_references
        context: Shared processing context
        num_mappers: Number of parallel mappers
    """
    if not chunks:
        return

    mr = MapReduce(
        mapper_premise=SUMMARY_EXTRACTION_PREMISE,
        reducer_premise="Not used in Pass 1",
        num_mappers=num_mappers,
        fail_fast=False,  # Continue on mapper failure
    )

    async def process_chunk(chunk: list[dict[str, Any]]) -> None:
        """Process a single chunk and extract summaries."""
        # Format chunk for mapper
        chunk_text = json.dumps([
            {
                "span_id": s.get("span_id"),
                "turn": i,
                "input": str(s.get("input", ""))[:500],  # Truncate for context
                "output": str(s.get("output", ""))[:500],
            }
            for i, s in enumerate(chunk)
        ], indent=2)

        # Use MapReduce's internal map phase
        results = await mr._map_phase(
            query=f"Extract summaries from these spans:\n{chunk_text}",
            chunks=[chunk],
        )

        # Parse results and add to context
        for result in results:
            if not result:
                continue
            try:
                # Parse JSON array from result (strip markdown fences if present)
                if isinstance(result, str):
                    cleaned = _extract_json_from_response(result)
                    summaries = json.loads(cleaned)
                else:
                    summaries = result
                if not isinstance(summaries, list):
                    summaries = [summaries]

                for s in summaries:
                    span_id = s.get("span_id")
                    if not span_id:
                        continue

                    # Find original span for turn number
                    turn_number = next(
                        (i for i, sp in enumerate(chunk) if sp.get("span_id") == span_id),
                        0
                    )

                    summary = SpanSummary(
                        span_id=span_id,
                        turn_number=turn_number,
                        summary=s.get("summary", ""),
                        key_entities=s.get("key_entities", []),
                        references=[],  # Filled later from reference graph
                        span_type=s.get("span_type", "unknown"),
                        content_hash=_content_hash(s.get("summary", ""), {"span_id": span_id}),
                    )
                    await context.add_summary(summary)

            except (json.JSONDecodeError, TypeError) as e:
                context.processing_log.append({
                    "action": "parse_error",
                    "error": str(e),
                    "result_preview": str(result)[:200],
                })

    # Process all chunks in parallel
    await asyncio.gather(*[process_chunk(chunk) for chunk in chunks])


# =============================================================================
# Phase 4: Pass 2 - Decision Extraction
# =============================================================================


DECISION_EXTRACTION_PREMISE = """You are a decision extractor.

For each span, using the provided reference context, extract:
1. Any decisions made
2. The rationale for each decision
3. Your confidence (0.0-1.0) that this is a real decision
4. Which referenced spans informed this decision

**Reference Context** (summaries of spans this span references):
{reference_context}

Return a JSON array:
[
  {
    "span_id": "...",
    "decision": "...",
    "rationale": "...",
    "confidence": 0.8,
    "source_refs": ["span_id_1", "span_id_2"]
  }
]

Only include spans that contain actual decisions (confidence > 0.5).
Skip spans that are just information gathering or tool outputs.
"""


async def extract_decisions(
    chunks: list[list[dict[str, Any]]],
    context: SpanProcessingContext,
    num_mappers: int = 4,
) -> list[SpanDecision]:
    """Pass 2: Extract decisions using summary context from Pass 1.

    Args:
        chunks: Same chunks from Pass 1
        context: Context populated with summaries from Pass 1
        num_mappers: Number of parallel mappers

    Returns:
        List of extracted decisions
    """
    if not chunks:
        return []

    decisions: list[SpanDecision] = []
    decisions_lock = asyncio.Lock()

    async def process_chunk_with_context(chunk: list[dict[str, Any]]) -> None:
        """Process chunk with injected reference context."""
        # Enrich each span with reference context
        enriched = []
        for span in chunk:
            span_id = span.get("span_id", "")
            ref_context = await context.get_reference_context(span_id)

            enriched.append({
                "span_id": span_id,
                "input": str(span.get("input", ""))[:500],
                "output": str(span.get("output", ""))[:500],
                "reference_context": ref_context,
            })

        # Format for mapper
        chunk_text = json.dumps(enriched, indent=2)

        mr = MapReduce(
            mapper_premise=DECISION_EXTRACTION_PREMISE,
            reducer_premise="Synthesize all decisions into a coherent report.",
            num_mappers=1,  # Single mapper per chunk for Pass 2
            fail_fast=False,
        )

        results = await mr._map_phase(
            query=f"Extract decisions from these spans:\n{chunk_text}",
            chunks=[enriched],
        )

        # Parse and collect decisions (strip markdown fences if present)
        for result in results:
            if not result:
                continue
            try:
                if isinstance(result, str):
                    cleaned = _extract_json_from_response(result)
                    parsed = json.loads(cleaned)
                else:
                    parsed = result
                if not isinstance(parsed, list):
                    parsed = [parsed]

                for d in parsed:
                    # Use consistent default (0.5) for confidence
                    confidence = d.get("confidence", 0.5)
                    if confidence < 0.5:
                        continue

                    decision = SpanDecision(
                        span_id=d.get("span_id", ""),
                        decision=d.get("decision", ""),
                        rationale=d.get("rationale", ""),
                        confidence=confidence,
                        source_refs=d.get("source_refs", []),
                    )

                    async with decisions_lock:
                        decisions.append(decision)

            except (json.JSONDecodeError, TypeError) as e:
                context.processing_log.append({
                    "action": "decision_parse_error",
                    "error": str(e),
                })

    await asyncio.gather(*[process_chunk_with_context(chunk) for chunk in chunks])

    return decisions


# =============================================================================
# Phase 5: Batch Embedding and Persistence
# =============================================================================


async def embed_and_persist_summaries(
    context: SpanProcessingContext,
    session_id: str,
    embedding_provider: str = "openai",
) -> int:
    """Batch embed all summaries and persist to PostgreSQL.

    Called after Pass 1 completes, before Pass 2.

    Args:
        context: Context with span_summaries populated
        session_id: Braintrust session ID for isolation
        embedding_provider: "openai", "voyage", or "mock"

    Returns:
        Number of summaries persisted
    """
    summaries = await context.all_summaries()
    if not summaries:
        return 0

    # Batch embed
    embedder = EmbeddingService(provider=embedding_provider)
    texts = [s.summary for s in summaries]
    embeddings = await embedder.embed_batch(texts)

    # Persist to PostgreSQL
    memory = MemoryServicePG(session_id=session_id)
    await memory.connect()

    stored_count = 0
    for summary, embedding in zip(summaries, embeddings):
        try:
            await memory.store(
                content=summary.summary,
                metadata={
                    "span_id": summary.span_id,
                    "turn_number": summary.turn_number,
                    "key_entities": summary.key_entities,
                    "references": summary.references,
                    "span_type": summary.span_type,
                    "content_hash": summary.content_hash,
                    "type": "span_summary",
                },
                embedding=embedding,
            )
            stored_count += 1
        except Exception as e:
            context.processing_log.append({
                "action": "store_error",
                "span_id": summary.span_id,
                "error": str(e),
            })

    await memory.close()
    return stored_count


async def persist_decisions(
    decisions: list[SpanDecision],
    session_id: str,
) -> int:
    """Persist extracted decisions to PostgreSQL.

    Args:
        decisions: Decisions from Pass 2
        session_id: Braintrust session ID

    Returns:
        Number of decisions persisted
    """
    if not decisions:
        return 0

    memory = MemoryServicePG(session_id=session_id)
    await memory.connect()

    stored_count = 0
    for d in decisions:
        try:
            await memory.store(
                content=f"Decision: {d.decision}\nRationale: {d.rationale}",
                metadata={
                    "span_id": d.span_id,
                    "confidence": d.confidence,
                    "source_refs": d.source_refs,
                    "type": "span_decision",
                },
            )
            stored_count += 1
        except Exception:
            pass

    await memory.close()
    return stored_count


# =============================================================================
# Phase 6: SpanProcessor Orchestrator
# =============================================================================


class SpanProcessor:
    """Process large span datasets with two-pass Map/Reduce.

    Pipeline:
    1. Pre-scan: Build reference graph
    2. Chunking: Group by connected components
    3. Pass 1: Extract summaries (no cross-refs)
    4. Embed: Batch embed summaries
    5. Pass 2: Extract decisions (with reference context)
    6. Persist: Store to PostgreSQL

    Example:
        processor = SpanProcessor(
            session_id="abc123",
            num_mappers=4,
            max_chunk_size=50,
        )
        result = await processor.process(spans)
    """

    def __init__(
        self,
        session_id: str,
        num_mappers: int = 4,
        max_chunk_size: int = 50,
        overlap: int = 5,
        embedding_provider: str = "openai",
    ):
        """Initialize SpanProcessor.

        Args:
            session_id: Braintrust session ID
            num_mappers: Parallel mappers for each pass
            max_chunk_size: Max spans per chunk
            overlap: Overlap for subdivided chunks
            embedding_provider: "openai", "voyage", or "mock"
        """
        self.session_id = session_id
        self.num_mappers = num_mappers
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.embedding_provider = embedding_provider

        self.context = SpanProcessingContext()

    async def process(self, spans: list[dict[str, Any]]) -> SpanProcessingResult:
        """Process spans through two-pass pipeline.

        Args:
            spans: Raw spans from Braintrust BTQL

        Returns:
            SpanProcessingResult with counts and errors
        """
        start_time = time.time()

        result = SpanProcessingResult(
            session_id=self.session_id,
            spans_processed=len(spans),
            summaries_extracted=0,
            decisions_extracted=0,
            summaries_persisted=0,
            decisions_persisted=0,
            duration_seconds=0,
        )

        try:
            # Phase 1: Build reference graph
            ref_graph = build_reference_graph(spans)

            # Phase 2: Chunk by references
            chunks = chunk_by_references(
                spans, ref_graph, self.max_chunk_size, self.overlap
            )

            # Phase 3: Pass 1 - Extract summaries
            await extract_summaries(chunks, self.context, self.num_mappers)
            result.summaries_extracted = len(self.context.span_summaries)

            # Populate references in summaries from ref_graph
            for span_id, refs in ref_graph.items():
                if span_id in self.context.span_summaries:
                    self.context.span_summaries[span_id].references = refs

            # Phase 4: Batch embed and persist summaries
            result.summaries_persisted = await embed_and_persist_summaries(
                self.context, self.session_id, self.embedding_provider
            )

            # Phase 5: Pass 2 - Extract decisions
            decisions = await extract_decisions(chunks, self.context, self.num_mappers)
            result.decisions_extracted = len(decisions)

            # Phase 6: Persist decisions
            result.decisions_persisted = await persist_decisions(decisions, self.session_id)

        except Exception as e:
            result.errors.append(f"Pipeline error: {e}")

        result.duration_seconds = time.time() - start_time
        return result
