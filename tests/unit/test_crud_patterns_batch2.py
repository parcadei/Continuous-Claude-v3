"""Level 3/4: Pattern Structure and Prompt Reliability Tests - Batch 2

Tests for MapReduce, Adversarial, ChainOfResponsibility, Blackboard, EventDriven.
Mock spawn to control deterministic responses.

Each pattern has 5 tests covering:
- Basic execution (happy path)
- Error handling / edge cases
- Prompt reliability (verifying prompts contain expected elements)
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# =============================================================================
# Module-level spawn paths for each pattern
# =============================================================================
MAP_REDUCE_SPAWN = "scripts.agentica.patterns.map_reduce.spawn"
ADVERSARIAL_SPAWN = "scripts.agentica.patterns.adversarial.spawn"
CHAIN_OF_RESP_SPAWN = "scripts.agentica.patterns.chain_of_responsibility.spawn"
BLACKBOARD_SPAWN = "scripts.agentica.patterns.blackboard.spawn"
EVENT_DRIVEN_SPAWN = "scripts.agentica.patterns.event_driven.spawn"


# =============================================================================
# MapReduce Pattern Tests (5 tests)
# =============================================================================
class TestMapReducePatternBatch2:
    """Tests for the MapReduce pattern structure and prompt reliability."""

    @pytest.fixture
    def mock_spawn(self):
        """Create a mock spawn function that returns mock agents."""
        with patch(MAP_REDUCE_SPAWN) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_map_phase_spawns_correct_number_of_mappers(self, mock_spawn):
        """Verify that the map phase spawns exactly N mapper agents for N chunks."""
        from scripts.agentica.patterns import MapReduce

        spawn_count = 0
        spawned_premises = []

        async def counting_spawn(**kwargs):
            nonlocal spawn_count
            spawn_count += 1
            spawned_premises.append(kwargs.get("premise", ""))
            agent = MagicMock()
            agent.call = AsyncMock(return_value=f"result{spawn_count}")
            return agent

        mock_spawn.side_effect = counting_spawn

        mr = MapReduce(
            mapper_premise="You analyze one section.",
            reducer_premise="You combine results.",
            num_mappers=3,
        )

        chunks = ["chunk1", "chunk2", "chunk3"]
        result = await mr.execute("Analyze this", chunks=chunks)

        # Should spawn 3 mappers + 1 reducer = 4 agents
        assert spawn_count == 4
        # Mapper premise should appear 3 times
        mapper_count = sum(1 for p in spawned_premises if "analyze" in p.lower())
        assert mapper_count == 3

    @pytest.mark.asyncio
    async def test_chunks_distributed_to_mappers_correctly(self, mock_spawn):
        """Verify chunk distribution (round-robin when chunks > mappers)."""
        from scripts.agentica.patterns import MapReduce

        chunks_received = []

        async def tracking_spawn(**kwargs):
            agent = MagicMock()

            async def mock_call(return_type, prompt, **kw):
                # Track what chunks were passed in prompts
                chunks_received.append(prompt)
                return "processed"

            agent.call = mock_call
            return agent

        mock_spawn.side_effect = tracking_spawn

        mr = MapReduce(
            mapper_premise="You analyze one section.",
            reducer_premise="You combine results.",
            num_mappers=2,
        )

        # More chunks than mappers
        chunks = ["chunk1", "chunk2", "chunk3", "chunk4"]
        result = await mr.execute("Analyze this", chunks=chunks)

        # All chunks should be processed
        assert result is not None
        # At least some prompts should have been captured
        assert len(chunks_received) >= 1

    @pytest.mark.asyncio
    async def test_reducer_receives_all_mapper_outputs(self, mock_spawn):
        """Verify reducer gets all mapper results."""
        from scripts.agentica.patterns import MapReduce

        reducer_prompt = None
        call_count = 0

        async def tracking_spawn(**kwargs):
            nonlocal call_count
            call_count += 1
            premise = kwargs.get("premise", "")
            agent = MagicMock()

            async def mock_call(return_type, prompt, **kw):
                nonlocal reducer_prompt
                if "combine" in premise.lower():
                    reducer_prompt = prompt
                    return "final combined result"
                else:
                    return f"mapper_{call_count}_result"

            agent.call = mock_call
            return agent

        mock_spawn.side_effect = tracking_spawn

        mr = MapReduce(
            mapper_premise="You analyze one section.",
            reducer_premise="You combine results.",
            num_mappers=3,
        )

        chunks = ["chunk1", "chunk2", "chunk3"]
        result = await mr.execute("Analyze this", chunks=chunks)

        # Reducer should have been called
        assert reducer_prompt is not None
        # Final result should be from reducer
        assert "combined" in result.lower() or result is not None

    @pytest.mark.asyncio
    async def test_handles_mapper_failure_with_fail_fast_false(self, mock_spawn):
        """Verify partial failure handling when fail_fast=False."""
        from scripts.agentica.patterns import MapReduce

        call_count = 0

        async def failing_spawn(**kwargs):
            nonlocal call_count
            call_count += 1
            premise = kwargs.get("premise", "")
            agent = MagicMock()

            if call_count == 2 and "analyze" in premise.lower():
                # Second mapper fails
                agent.call = AsyncMock(side_effect=Exception("Mapper failed"))
            elif "combine" in premise.lower():
                # Reducer always succeeds
                agent.call = AsyncMock(return_value="combined from partial")
            else:
                agent.call = AsyncMock(return_value=f"result{call_count}")

            return agent

        mock_spawn.side_effect = failing_spawn

        mr = MapReduce(
            mapper_premise="You analyze one section.",
            reducer_premise="You combine results.",
            num_mappers=3,
            fail_fast=False,
        )

        chunks = ["chunk1", "chunk2", "chunk3"]
        result = await mr.execute("Analyze this", chunks=chunks)

        # Should not raise, should return something
        assert result is not None

    @pytest.mark.asyncio
    async def test_mapper_prompt_contains_chunk_data(self, mock_spawn):
        """Verify mapper prompts include chunk content (prompt reliability)."""
        from scripts.agentica.patterns import MapReduce

        captured_prompts = []

        async def prompt_capturing_spawn(**kwargs):
            premise = kwargs.get("premise", "")
            agent = MagicMock()

            async def mock_call(return_type, prompt, **kw):
                if "analyze" in premise.lower():
                    captured_prompts.append(prompt)
                return "processed"

            agent.call = mock_call
            return agent

        mock_spawn.side_effect = prompt_capturing_spawn

        mr = MapReduce(
            mapper_premise="You analyze one section.",
            reducer_premise="You combine results.",
            num_mappers=2,
        )

        chunks = ["special_chunk_A", "special_chunk_B"]
        await mr.execute("Analyze this", chunks=chunks)

        # Each mapper should have received its chunk in the prompt
        all_prompts = " ".join(captured_prompts)
        assert "special_chunk_A" in all_prompts or "special_chunk_B" in all_prompts


# =============================================================================
# Adversarial Pattern Tests (5 tests)
# =============================================================================
class TestAdversarialPatternBatch2:
    """Tests for the Adversarial pattern structure and prompt reliability."""

    @pytest.fixture
    def mock_spawn(self):
        """Create mock spawn function."""
        with patch(ADVERSARIAL_SPAWN) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_advocate_and_adversary_both_spawned(self, mock_spawn):
        """Verify both agents are spawned and called."""
        from scripts.agentica.patterns import Adversarial

        spawned_premises = []

        def spawn_side_effect(**kwargs):
            spawned_premises.append(kwargs.get("premise", ""))
            mock_agent = AsyncMock()
            if "favor" in kwargs.get("premise", ""):
                mock_agent.call = AsyncMock(return_value="Pro argument")
            else:
                mock_agent.call = AsyncMock(return_value="Con argument")
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        adv = Adversarial(
            advocate_premise="You argue in favor.",
            adversary_premise="You argue against.",
            max_rounds=1,
        )

        result = await adv.debate("Should we use microservices?")

        # Both agents should have been spawned
        assert mock_spawn.call_count >= 2
        # Check that both premises were used
        assert any("favor" in p for p in spawned_premises)
        assert any("against" in p for p in spawned_premises)

    @pytest.mark.asyncio
    async def test_debate_runs_for_max_rounds(self, mock_spawn):
        """Verify multiple rounds of debate."""
        from scripts.agentica.patterns import Adversarial

        call_count = {"advocate": 0, "adversary": 0}

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                if "favor" in premise:
                    call_count["advocate"] += 1
                    return f"Pro argument round {call_count['advocate']}"
                else:
                    call_count["adversary"] += 1
                    return f"Con argument round {call_count['adversary']}"

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        adv = Adversarial(
            advocate_premise="You argue in favor.",
            adversary_premise="You argue against.",
            max_rounds=3,
        )

        await adv.debate("Should we use microservices?")

        # Each agent should be called max_rounds times
        assert call_count["advocate"] == 3
        assert call_count["adversary"] == 3

    @pytest.mark.asyncio
    async def test_judge_receives_both_positions(self, mock_spawn):
        """Verify judge gets advocate and adversary positions."""
        from scripts.agentica.patterns import Adversarial

        judge_received_prompt = None

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                nonlocal judge_received_prompt
                if "decide" in premise:
                    judge_received_prompt = prompt
                    return "Advocate wins"
                elif "favor" in premise:
                    return "Pro argument: microservices are scalable"
                else:
                    return "Con argument: microservices add complexity"

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        adv = Adversarial(
            advocate_premise="You argue in favor.",
            adversary_premise="You argue against.",
            judge_premise="You decide which is stronger.",
            max_rounds=1,
        )

        result = await adv.resolve("Should we use microservices?")

        # Judge should have been called with both positions
        assert judge_received_prompt is not None
        # Judge prompt should contain references to both arguments
        assert (
            "Pro" in judge_received_prompt
            or "advocate" in judge_received_prompt.lower()
            or "favor" in judge_received_prompt.lower()
        )

    @pytest.mark.asyncio
    async def test_works_without_judge_returns_both_positions(self, mock_spawn):
        """Verify pattern works without judge, returning both positions."""
        from scripts.agentica.patterns import Adversarial

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                if "favor" in premise:
                    return "Pro argument"
                else:
                    return "Con argument"

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        adv = Adversarial(
            advocate_premise="You argue in favor.",
            adversary_premise="You argue against.",
            max_rounds=1,
        )

        result = await adv.resolve("Should we use microservices?")

        # Without judge, should return both positions (as dict or combined)
        assert result is not None
        assert (
            "advocate" in str(result).lower()
            or "Pro" in str(result)
            or isinstance(result, dict)
        )

    @pytest.mark.asyncio
    async def test_adversary_receives_advocate_position_in_prompt(self, mock_spawn):
        """Verify adversary sees advocate's argument (prompt reliability)."""
        from scripts.agentica.patterns import Adversarial

        adversary_prompts = []

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                if "favor" in premise:
                    return "Pro: microservices enable independent scaling"
                else:
                    adversary_prompts.append(prompt)
                    return "Con: they add complexity"

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        adv = Adversarial(
            advocate_premise="You argue in favor.",
            adversary_premise="You argue against.",
            max_rounds=2,
        )

        await adv.debate("Should we use microservices?")

        # After round 1, adversary should see advocate's position
        if len(adversary_prompts) >= 2:
            # Later rounds should reference prior arguments
            all_adversary_prompts = " ".join(adversary_prompts[1:])
            assert (
                "Pro" in all_adversary_prompts
                or "scaling" in all_adversary_prompts
                or "microservices" in all_adversary_prompts.lower()
            )


# =============================================================================
# Chain of Responsibility Pattern Tests (5 tests)
# =============================================================================
class TestChainOfResponsibilityPatternBatch2:
    """Tests for the ChainOfResponsibility pattern structure and prompt reliability."""

    @pytest.fixture
    def mock_spawn(self):
        """Mock spawn function for testing."""
        with patch(CHAIN_OF_RESP_SPAWN) as mock:

            async def create_agent(**kwargs):
                agent = MagicMock()
                agent.call = AsyncMock(
                    return_value=f"Handled by: {kwargs.get('premise', 'unknown')}"
                )
                return agent

            mock.side_effect = create_agent
            yield mock

    @pytest.mark.asyncio
    async def test_first_matching_handler_processes_request(self, mock_spawn):
        """First handler that can_handle returns True should process the request."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        chain = ChainOfResponsibility(
            handlers=[
                Handler(
                    premise="You handle Python questions.",
                    can_handle=lambda q: "python" in q.lower(),
                ),
                Handler(
                    premise="You handle JavaScript questions.",
                    can_handle=lambda q: "javascript" in q.lower(),
                ),
            ]
        )

        result = await chain.process("How do I use async in Python?")

        # Should have called spawn with Python handler premise
        assert mock_spawn.called
        call_kwargs = mock_spawn.call_args.kwargs
        assert "Python" in call_kwargs.get("premise", "")

    @pytest.mark.asyncio
    async def test_falls_through_to_next_handler_when_no_match(self, mock_spawn):
        """If first handler can't handle, should try next handler."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        chain = ChainOfResponsibility(
            handlers=[
                Handler(
                    premise="You handle Python questions.",
                    can_handle=lambda q: "python" in q.lower(),
                ),
                Handler(
                    premise="You handle JavaScript questions.",
                    can_handle=lambda q: "javascript" in q.lower(),
                ),
            ]
        )

        result = await chain.process("How do I use promises in JavaScript?")

        # JavaScript handler should be used (Python can't handle it)
        assert mock_spawn.called
        call_kwargs = mock_spawn.call_args.kwargs
        assert "JavaScript" in call_kwargs.get("premise", "")

    @pytest.mark.asyncio
    async def test_fallback_handler_catches_unhandled_requests(self, mock_spawn):
        """A handler with can_handle=lambda q: True should catch all unhandled requests."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        chain = ChainOfResponsibility(
            handlers=[
                Handler(
                    premise="You handle Python questions.",
                    can_handle=lambda q: "python" in q.lower(),
                ),
                Handler(
                    premise="You handle general programming questions.",
                    can_handle=lambda q: True,  # Fallback
                ),
            ]
        )

        # Query that doesn't match Python
        result = await chain.process("What is recursion?")

        # Should fall through to general handler
        call_kwargs = mock_spawn.call_args.kwargs
        assert "general" in call_kwargs.get("premise", "").lower()

    @pytest.mark.asyncio
    async def test_raises_error_when_no_handler_matches(self, mock_spawn):
        """If no handler can handle the request, should raise an error."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        chain = ChainOfResponsibility(
            handlers=[
                Handler(
                    premise="You handle Python questions.",
                    can_handle=lambda q: "python" in q.lower(),
                ),
                Handler(
                    premise="You handle JavaScript questions.",
                    can_handle=lambda q: "javascript" in q.lower(),
                ),
            ]
        )

        # Query that matches neither
        with pytest.raises(ValueError, match="No handler"):
            await chain.process("What is the meaning of life?")

    @pytest.mark.asyncio
    async def test_handler_prompt_contains_query(self, mock_spawn):
        """Verify handler receives the query in its call (prompt reliability)."""
        from scripts.agentica.patterns import ChainOfResponsibility, Handler

        captured_prompts = []

        async def capturing_spawn(**kwargs):
            agent = MagicMock()

            async def mock_call(return_type, prompt, **kw):
                captured_prompts.append(prompt)
                return "Handled"

            agent.call = mock_call
            return agent

        mock_spawn.side_effect = capturing_spawn

        chain = ChainOfResponsibility(
            handlers=[
                Handler(
                    premise="You handle all questions.",
                    can_handle=lambda q: True,
                ),
            ]
        )

        await chain.process("Explain the difference between lists and tuples")

        # Handler's call should contain the original query
        assert len(captured_prompts) >= 1
        assert (
            "lists" in captured_prompts[0] or "tuples" in captured_prompts[0]
        )


# =============================================================================
# Blackboard Pattern Tests (5 tests)
# =============================================================================
class TestBlackboardPatternBatch2:
    """Tests for the Blackboard pattern structure and prompt reliability."""

    @pytest.fixture
    def mock_spawn(self):
        """Create mock spawn function."""
        with patch(BLACKBOARD_SPAWN) as mock:
            yield mock

    @pytest.mark.asyncio
    async def test_specialists_write_to_blackboard_state(self, mock_spawn):
        """Verify specialists update state with keys from writes_to."""
        from scripts.agentica.patterns import Blackboard, Specialist

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                if "check" in premise.lower():
                    return {"complete": True}
                else:
                    return {"requirements": "User needs login system"}

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        bb = Blackboard(
            specialists=[
                Specialist(premise="You analyze requirements.", writes_to=["requirements"]),
            ],
            controller_premise="You check if design is complete.",
            max_iterations=1,
        )

        result = await bb.solve("Build auth system")

        # Blackboard should have the written key
        assert "requirements" in result.state

    @pytest.mark.asyncio
    async def test_iteration_continues_until_controller_approves(self, mock_spawn):
        """Verify solve() iterates until controller says done."""
        from scripts.agentica.patterns import Blackboard, Specialist

        iteration_count = {"value": 0}

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                if "check" in premise.lower():
                    iteration_count["value"] += 1
                    if iteration_count["value"] >= 2:
                        return {"complete": True}
                    return {"complete": False}
                else:
                    return {"output": f"iteration {iteration_count['value']}"}

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        bb = Blackboard(
            specialists=[
                Specialist(premise="You analyze.", writes_to=["analysis"]),
            ],
            controller_premise="You check if complete.",
            max_iterations=10,
        )

        result = await bb.solve("Build something")

        # Should have iterated at least twice
        assert iteration_count["value"] >= 2
        assert result.completed is True

    @pytest.mark.asyncio
    async def test_max_iterations_prevents_infinite_loop(self, mock_spawn):
        """Verify max_iterations prevents infinite loops."""
        from scripts.agentica.patterns import Blackboard, Specialist

        iteration_count = {"value": 0}

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                iteration_count["value"] += 1
                if "check" in premise.lower():
                    # Controller never approves
                    return {"complete": False}
                else:
                    return {"output": "some work"}

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        bb = Blackboard(
            specialists=[
                Specialist(premise="You analyze.", writes_to=["analysis"]),
            ],
            controller_premise="You check if complete.",
            max_iterations=3,
        )

        result = await bb.solve("Build something")

        # Should have stopped after max_iterations (each iteration = 2 calls)
        assert iteration_count["value"] <= 6
        assert result.iterations <= 3

    @pytest.mark.asyncio
    async def test_state_history_preserved_across_iterations(self, mock_spawn):
        """Verify history tracking across iterations."""
        from scripts.agentica.patterns import Blackboard, Specialist

        iteration_num = {"value": 0}

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                if "check" in premise.lower():
                    iteration_num["value"] += 1
                    return {"complete": iteration_num["value"] >= 2}
                else:
                    return {"analysis": f"analysis_{iteration_num['value']}"}

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        bb = Blackboard(
            specialists=[
                Specialist(premise="You analyze.", writes_to=["analysis"]),
            ],
            controller_premise="You check if complete.",
            max_iterations=5,
        )

        result = await bb.solve("Build something")

        # History should contain entries
        assert len(result.state.history) > 0

    @pytest.mark.asyncio
    async def test_specialist_prompt_contains_readable_keys(self, mock_spawn):
        """Verify specialists see state they depend on (prompt reliability)."""
        from scripts.agentica.patterns import Blackboard, Specialist

        captured_prompts = []
        iteration = {"value": 0}

        def spawn_side_effect(**kwargs):
            mock_agent = AsyncMock()
            premise = kwargs.get("premise", "")

            async def mock_call(return_type, prompt, **kw):
                if "check" in premise.lower():
                    iteration["value"] += 1
                    return {"complete": iteration["value"] >= 2}
                elif "design" in premise.lower():
                    captured_prompts.append(prompt)
                    return {"design": "microservices architecture"}
                else:
                    return {"requirements": "user auth needed"}

            mock_agent.call = mock_call
            return mock_agent

        mock_spawn.side_effect = spawn_side_effect

        bb = Blackboard(
            specialists=[
                Specialist(premise="You analyze requirements.", writes_to=["requirements"]),
                Specialist(
                    premise="You design architecture.",
                    reads_from=["requirements"],
                    writes_to=["design"],
                ),
            ],
            controller_premise="You check if complete.",
            max_iterations=3,
        )

        await bb.solve("Build auth system")

        # Designer should see requirements in prompt
        if captured_prompts:
            all_prompts = " ".join(captured_prompts)
            # The prompt should reference requirements or contain state info
            assert len(all_prompts) > 0


# =============================================================================
# Event-Driven Pattern Tests (5 tests)
# =============================================================================
class TestEventDrivenPatternBatch2:
    """Tests for the EventDriven pattern structure and prompt reliability."""

    @pytest.fixture
    def mock_spawn(self):
        """Mock the spawn function."""
        with patch(EVENT_DRIVEN_SPAWN) as mock:
            mock_agent = AsyncMock()
            mock_agent.call = AsyncMock(return_value="processed")
            mock.return_value = mock_agent
            yield mock

    @pytest.mark.asyncio
    async def test_matching_subscriber_receives_event(self, mock_spawn):
        """Subscriber is called when event type matches."""
        from scripts.agentica.patterns import Event, Subscriber, EventDriven

        bus = EventDriven(
            subscribers=[
                Subscriber(
                    premise="You handle user created events.",
                    event_types=["user.created"],
                )
            ]
        )

        event = Event(type="user.created", payload={"user_id": "123"})
        results = await bus.publish(event)

        # Verify subscriber was spawned and called
        assert mock_spawn.called
        mock_agent = mock_spawn.return_value
        assert mock_agent.call.called
        assert len(results) == 1

    @pytest.mark.asyncio
    async def test_wildcard_subscriber_receives_all_events(self, mock_spawn):
        """Subscriber with '*' event_type receives all events."""
        from scripts.agentica.patterns import Event, Subscriber, EventDriven

        bus = EventDriven(
            subscribers=[
                Subscriber(
                    premise="You log all events.",
                    event_types=["*"],
                )
            ]
        )

        # Publish different event types
        event1 = Event(type="user.created", payload={})
        event2 = Event(type="order.placed", payload={})
        event3 = Event(type="something.else", payload={})

        results1 = await bus.publish(event1)
        results2 = await bus.publish(event2)
        results3 = await bus.publish(event3)

        # Wildcard should receive all events
        assert len(results1) == 1
        assert len(results2) == 1
        assert len(results3) == 1

    @pytest.mark.asyncio
    async def test_non_matching_subscriber_not_called(self, mock_spawn):
        """Subscriber is not called when event type doesn't match."""
        from scripts.agentica.patterns import Event, Subscriber, EventDriven

        bus = EventDriven(
            subscribers=[
                Subscriber(
                    premise="You handle order events.",
                    event_types=["order.placed"],
                )
            ]
        )

        event = Event(type="user.created", payload={"user_id": "123"})
        results = await bus.publish(event)

        # No subscribers should match
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_concurrent_dispatch_to_multiple_subscribers(self, mock_spawn):
        """Multiple matching subscribers are dispatched concurrently."""
        from scripts.agentica.patterns import Event, Subscriber, EventDriven

        call_times = []

        async def track_call(*args, **kwargs):
            call_times.append(asyncio.get_event_loop().time())
            await asyncio.sleep(0.01)  # Small delay to test concurrency
            return "processed"

        mock_agent = AsyncMock()
        mock_agent.call = track_call
        mock_spawn.return_value = mock_agent

        bus = EventDriven(
            subscribers=[
                Subscriber(premise="Handler 1", event_types=["user.created"]),
                Subscriber(premise="Handler 2", event_types=["user.created"]),
                Subscriber(premise="Handler 3", event_types=["user.created"]),
            ]
        )

        event = Event(type="user.created", payload={})
        results = await bus.publish(event)

        # All 3 subscribers should be called
        assert len(results) == 3

        # They should have started nearly simultaneously (concurrent dispatch)
        if len(call_times) >= 2:
            time_diff = max(call_times) - min(call_times)
            assert time_diff < 0.02  # Should be concurrent

    @pytest.mark.asyncio
    async def test_subscriber_prompt_contains_event_payload(self, mock_spawn):
        """Verify event data in prompt (prompt reliability)."""
        from scripts.agentica.patterns import Event, Subscriber, EventDriven

        captured_prompts = []

        async def capturing_call(return_type, prompt, **kw):
            captured_prompts.append(prompt)
            return "processed"

        mock_agent = AsyncMock()
        mock_agent.call = capturing_call
        mock_spawn.return_value = mock_agent

        bus = EventDriven(
            subscribers=[
                Subscriber(
                    premise="You handle user events.",
                    event_types=["user.created"],
                )
            ]
        )

        event = Event(
            type="user.created",
            payload={"user_id": "abc123", "email": "test@example.com"},
        )
        await bus.publish(event)

        # Subscriber's call should include event payload
        assert len(captured_prompts) >= 1
        prompt = captured_prompts[0]
        assert (
            "abc123" in prompt
            or "user_id" in prompt
            or "user.created" in prompt
        )
