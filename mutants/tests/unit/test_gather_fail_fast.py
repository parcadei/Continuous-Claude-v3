"""Tests for gather_fail_fast helper (TDD - tests written first).

Tests async coordination primitive that uses TaskGroup for fail-fast mode
and asyncio.gather() with return_exceptions=True for partial results mode.
"""

import asyncio

import pytest


class TestGatherFailFastMode:
    """Test fail_fast=True (TaskGroup) behavior."""

    @pytest.mark.asyncio
    async def test_all_succeed(self):
        """All coroutines succeed - returns all results."""
        from scripts.agentica.patterns.primitives import gather_fail_fast

        async def succeed(x):
            return x * 2

        results = await gather_fail_fast(
            [succeed(1), succeed(2), succeed(3)],
            fail_fast=True
        )
        assert results == [2, 4, 6]

    @pytest.mark.asyncio
    async def test_first_exception_cancels_all(self):
        """First exception should cancel remaining tasks."""
        from scripts.agentica.patterns.primitives import gather_fail_fast

        executed = []

        async def slow_success():
            await asyncio.sleep(1)
            executed.append("slow")
            return "slow"

        async def fast_failure():
            executed.append("fast")
            raise ValueError("Fast failure")

        with pytest.raises(ExceptionGroup) as exc_info:
            await gather_fail_fast(
                [slow_success(), fast_failure()],
                fail_fast=True
            )

        # Fast failure should be in the exception group
        assert any(isinstance(e, ValueError) for e in exc_info.value.exceptions)
        # Slow success should have been cancelled (not in executed)
        assert "slow" not in executed

    @pytest.mark.asyncio
    async def test_exception_group_contains_all_failures(self):
        """ExceptionGroup should contain all exceptions that occurred."""
        from scripts.agentica.patterns.primitives import gather_fail_fast

        async def fail_with(msg: str):
            raise ValueError(msg)

        async def succeed():
            return "ok"

        with pytest.raises(ExceptionGroup) as exc_info:
            await gather_fail_fast(
                [fail_with("A"), succeed(), fail_with("B")],
                fail_fast=True
            )

        # At least one ValueError should be in the group
        errors = [e for e in exc_info.value.exceptions if isinstance(e, ValueError)]
        assert len(errors) >= 1


class TestGatherPartialMode:
    """Test fail_fast=False (gather) behavior."""

    @pytest.mark.asyncio
    async def test_collects_exceptions(self):
        """Exceptions are returned as values, not raised."""
        from scripts.agentica.patterns.primitives import gather_fail_fast

        async def succeed():
            return "ok"

        async def fail():
            raise ValueError("Failed")

        results = await gather_fail_fast(
            [succeed(), fail(), succeed()],
            fail_fast=False
        )

        assert results[0] == "ok"
        assert isinstance(results[1], ValueError)
        assert results[2] == "ok"

    @pytest.mark.asyncio
    async def test_all_continue_on_failure(self):
        """All coroutines complete even when some fail."""
        from scripts.agentica.patterns.primitives import gather_fail_fast

        executed = []

        async def track_and_succeed(name):
            executed.append(name)
            return name

        async def track_and_fail(name):
            executed.append(name)
            raise ValueError(name)

        await gather_fail_fast(
            [track_and_succeed("a"), track_and_fail("b"), track_and_succeed("c")],
            fail_fast=False
        )

        # All three should have executed
        assert set(executed) == {"a", "b", "c"}

    @pytest.mark.asyncio
    async def test_all_succeed_no_exceptions(self):
        """When all succeed in partial mode, returns all results."""
        from scripts.agentica.patterns.primitives import gather_fail_fast

        async def succeed(x):
            return x

        results = await gather_fail_fast(
            [succeed(1), succeed(2), succeed(3)],
            fail_fast=False
        )

        assert results == [1, 2, 3]


class TestGatherFailFastExport:
    """Test that gather_fail_fast is properly exported."""

    def test_gather_fail_fast_exported(self):
        """Helper should be importable from patterns package."""
        from scripts.agentica.patterns import gather_fail_fast
        assert callable(gather_fail_fast)
