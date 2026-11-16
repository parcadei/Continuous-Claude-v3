"""
MapReduce Pattern for Agentica.

Fan out work to N mapper agents in parallel, then combine with reducer.
"""

import asyncio
from uuid import uuid4
from typing import TYPE_CHECKING, Any, Optional

# Import spawn from agentica if available, otherwise use a stub for testing
try:
    from agentica import spawn
except ImportError:
    # Stub for testing - tests will mock this
    async def spawn(**kwargs):  # type: ignore
        """Stub spawn function for testing."""
        raise NotImplementedError("agentica not installed - use mocking in tests")

if TYPE_CHECKING:
    from scripts.agentica_patterns.coordination import CoordinationDB


class MapReduce:
    """
    MapReduce pattern: Fan out work to N mapper agents, then combine with reducer.

    Distributes independent subtasks across mapper agents in parallel (map phase),
    then aggregates all results with a reducer agent (reduce phase). Good for
    parallel processing of independent subtasks.

    Flow:
    1. Map phase: Spawn N mappers, assign chunks to each, execute in parallel
    2. Reduce phase: Spawn reducer, pass all mapper outputs, synthesize result

    Example:
        mr = MapReduce(
            mapper_premise="You analyze one section of code.",
            reducer_premise="You synthesize analysis from multiple reviewers.",
            num_mappers=4
        )
        result = await mr.execute("Review this codebase", chunks=["file1.py", "file2.py", "file3.py", "file4.py"])
    """

    def __init__(
        self,
        mapper_premise: str,
        reducer_premise: str,
        num_mappers: int = 3,
        mapper_model: str | None = None,
        reducer_model: str | None = None,
        mapper_scope: dict[str, Any] | None = None,
        reducer_scope: dict[str, Any] | None = None,
        fail_fast: bool = True,
        return_type: type = str,
        db: Optional["CoordinationDB"] = None
    ):
        """
        Initialize MapReduce pattern.

        Args:
            mapper_premise: Premise for mapper agents
            reducer_premise: Premise for reducer agent
            num_mappers: Number of mapper agents to spawn
            mapper_model: Model for mapper agents
            reducer_model: Model for reducer agent
            mapper_scope: Tools for mapper agents
            reducer_scope: Tools for reducer agent
            fail_fast: If True, stop on first mapper error. If False, continue with partial results
            return_type: Expected return type for the final result
            db: Optional coordination database for tracking agents

        Raises:
            ValueError: If num_mappers < 1
        """
        if num_mappers < 1:
            raise ValueError("num_mappers must be at least 1")

        self.mapper_premise = mapper_premise
        self.reducer_premise = reducer_premise
        self.num_mappers = num_mappers
        self.mapper_model = mapper_model
        self.reducer_model = reducer_model
        self.mapper_scope = mapper_scope or {}
        self.reducer_scope = reducer_scope or {}
        self.fail_fast = fail_fast
        self.return_type = return_type
        self.db = db

        # Generate unique ID for this MapReduce execution
        self.mr_id = str(uuid4())

        # Reducer spawned lazily
        self.reducer_agent = None

    async def _spawn_mapper(self, mapper_index: int) -> Any:
        """Spawn a single mapper agent with environment variables."""
        spawn_kwargs = {"premise": self.mapper_premise}
        if self.mapper_scope:
            spawn_kwargs["scope"] = self.mapper_scope
        if self.mapper_model:
            spawn_kwargs["model"] = self.mapper_model

        # Set environment variables for hook detection
        spawn_kwargs["env"] = {
            "PATTERN_TYPE": "map_reduce",
            "PATTERN_ID": self.mr_id,
            "MR_ID": self.mr_id,
            "AGENT_ROLE": "mapper",
            "MAPPER_INDEX": str(mapper_index),
            "TOTAL_MAPPERS": str(self.num_mappers),
        }

        if self.db:
            from scripts.agentica_patterns.tracked_agent import tracked_spawn
            return await tracked_spawn(db=self.db, pattern="map_reduce", **spawn_kwargs)
        else:
            return await spawn(**spawn_kwargs)

    async def _ensure_reducer(self):
        """Lazy spawn reducer agent with environment variables."""
        if self.reducer_agent is None:
            spawn_kwargs = {"premise": self.reducer_premise}
            if self.reducer_scope:
                spawn_kwargs["scope"] = self.reducer_scope
            if self.reducer_model:
                spawn_kwargs["model"] = self.reducer_model

            # Set environment variables for hook detection
            spawn_kwargs["env"] = {
                "PATTERN_TYPE": "map_reduce",
                "PATTERN_ID": self.mr_id,
                "MR_ID": self.mr_id,
                "AGENT_ROLE": "reducer",
                "TOTAL_MAPPERS": str(self.num_mappers),
            }

            if self.db:
                from scripts.agentica_patterns.tracked_agent import tracked_spawn
                self.reducer_agent = await tracked_spawn(
                    db=self.db, pattern="map_reduce", **spawn_kwargs
                )
            else:
                self.reducer_agent = await spawn(**spawn_kwargs)

    def _distribute_chunks(self, chunks: list[Any]) -> list[list[Any]]:
        """
        Distribute chunks across mappers.

        If there are more chunks than mappers, chunks are distributed round-robin.
        If fewer chunks than mappers, some mappers get empty lists.

        Returns:
            List of chunk lists, one per mapper
        """
        distributed: list[list[Any]] = [[] for _ in range(self.num_mappers)]
        for i, chunk in enumerate(chunks):
            mapper_idx = i % self.num_mappers
            distributed[mapper_idx].append(chunk)
        return distributed

    async def _map_phase(
        self, query: str, chunks: list[Any]
    ) -> list[Any]:
        """
        Execute map phase: spawn mappers and process chunks in parallel.

        Args:
            query: Base query/task for mappers
            chunks: List of chunks to distribute

        Returns:
            List of mapper results
        """
        distributed = self._distribute_chunks(chunks)

        async def process_chunk_set(mapper_index: int, mapper_chunks: list[Any]) -> Any:
            if not mapper_chunks:
                return None

            mapper = await self._spawn_mapper(mapper_index)
            chunk_description = "\n".join(str(c) for c in mapper_chunks)
            prompt = f"""
            {query}

            Your assigned chunks:
            {chunk_description}

            Process these chunks and return your analysis.
            """

            return await mapper.call(str, prompt)

        # Execute all mappers in parallel
        from .primitives import gather_fail_fast

        coros = [process_chunk_set(i, chunk_set) for i, chunk_set in enumerate(distributed)]

        if self.fail_fast:
            try:
                results = await gather_fail_fast(coros, fail_fast=True)
            except ExceptionGroup as eg:
                # Re-raise first exception for backward compatibility
                raise eg.exceptions[0] from eg
        else:
            results = await gather_fail_fast(coros, fail_fast=False)

        # Filter None results and exceptions (failed mappers in non-fail-fast mode)
        filtered = []
        for r in results:
            if r is not None and not isinstance(r, Exception):
                filtered.append(r)

        return filtered

    async def _reduce_phase(
        self, query: str, mapper_outputs: list[Any]
    ) -> Any:
        """
        Execute reduce phase: combine mapper outputs.

        Args:
            query: Original query for context
            mapper_outputs: Results from all mappers

        Returns:
            Synthesized result from reducer
        """
        await self._ensure_reducer()

        outputs_text = "\n\n---\n\n".join(str(o) for o in mapper_outputs)
        prompt = f"""
        Original task: {query}

        Results from {len(mapper_outputs)} mappers:

        {outputs_text}

        Synthesize these results into a comprehensive final answer.
        """

        return await self.reducer_agent.call(self.return_type, prompt)

    async def execute(
        self, query: str, chunks: list[Any]
    ) -> Any:
        """
        Execute MapReduce pattern.

        Args:
            query: Task/question for the mappers
            chunks: List of data chunks to distribute across mappers

        Returns:
            Final synthesized result from reducer
        """
        # Map phase
        mapper_outputs = await self._map_phase(query=query, chunks=chunks)

        # Reduce phase
        result = await self._reduce_phase(query=query, mapper_outputs=mapper_outputs)

        return result
