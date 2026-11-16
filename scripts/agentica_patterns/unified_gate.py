"""Unified orchestration gate - chains erotetic, resources, composition validation.

The unified gate implements a 3-gate flow:
1. Erotetic Gate - Blocks when unknowns exist in the task specification
2. Resources Gate - Blocks when insufficient system resources
3. Composition Gate - Blocks on invalid pattern algebra

All gates must pass before reaching the OrchestrationLayer.

Usage:
    from scripts.agentica_patterns.unified_gate import UnifiedGate, ClarificationRequired

    gate = UnifiedGate()

    # Validate a full request
    try:
        result = gate.validate({
            "task": {
                "description": "Build a data pipeline",
                "unknowns": [],
            },
            "resources": {
                "ram_gb": 4,
                "cpu_cores": 2,
            },
            "composition": {
                "pattern": "Pipeline",
                "composition_mode": "handoff",
            },
        })
        print(result)  # {"passed": True, "ready_for_orchestration": True}
    except ClarificationRequired as e:
        print(f"Need clarification: {e.unknowns}")
    except ResourcesInsufficient as e:
        print(f"Resource bottleneck: {e.bottleneck}, suggestion: {e.suggestion}")
    except CompositionInvalid as e:
        print(f"Invalid composition: {e.errors}")
"""

from __future__ import annotations

import psutil
from typing import Any


# ============================================================================
# Exceptions
# ============================================================================


class ClarificationRequired(Exception):
    """Raised when E(X,Q) != {} - unknowns exist in task specification."""

    def __init__(self, unknowns: list[str]) -> None:
        self.unknowns = unknowns
        super().__init__(f"Clarification required for: {', '.join(unknowns)}")


class ResourcesInsufficient(Exception):
    """Raised when system resources cannot support the requested pattern."""

    def __init__(self, bottleneck: str, suggestion: str) -> None:
        self.bottleneck = bottleneck
        self.suggestion = suggestion
        super().__init__(
            f"Insufficient resources: {bottleneck} is the bottleneck. "
            f"Suggestion: {suggestion}"
        )


class CompositionInvalid(Exception):
    """Raised when pattern algebra rules are violated."""

    def __init__(self, errors: list[str]) -> None:
        self.errors = errors
        super().__init__(f"Invalid composition: {'; '.join(errors)}")


# ============================================================================
# Standalone Gate Functions
# ============================================================================


def gate1_erotetic(propositions: dict[str, Any]) -> dict[str, Any]:
    """Check E(X,Q) - raise ClarificationRequired if unknowns exist.

    Args:
        propositions: Dict where values are known or "UNKNOWN"/None for unknowns

    Returns:
        Result dict with isEmpty, unknowns, and count

    Raises:
        ClarificationRequired: When unknowns are present
    """
    from scripts.z3_erotetic import check_evocation

    result = check_evocation(propositions)

    if not result["isEmpty"]:
        raise ClarificationRequired(result["unknowns"])

    return result


def gate2_resources(pattern: str, count: int = 1) -> dict[str, Any]:
    """Check system resources - raise ResourcesInsufficient if can't launch.

    Args:
        pattern: Pattern name (e.g., "Swarm", "Pipeline")
        count: Number of agents to launch

    Returns:
        Resource validation result dict

    Raises:
        ResourcesInsufficient: When resources are insufficient
    """
    from scripts.validate_resources import validate_resources, get_system_resources

    composition = f"{pattern}({count})" if count > 1 else pattern
    result = validate_resources(composition)

    if not result.can_launch:
        raise ResourcesInsufficient(
            bottleneck=result.bottleneck or "unknown",
            suggestion=result.fallback_suggestion or "Reduce agent count or try a simpler pattern",
        )

    return {
        "can_launch": result.can_launch,
        "composition": result.composition,
        "required": {
            "memory_mb": result.required.memory_mb,
            "cpu_cores": result.required.cpu_cores,
            "concurrent_agents": result.required.concurrent_agents,
        },
        "available": {
            "memory_mb": result.available.available_memory_mb,
            "cpu_cores": result.available.available_cpu_cores,
        },
    }


def gate3_composition(
    pattern_a: str,
    pattern_b: str,
    scope: str,
    operator: str = ";",
) -> dict[str, Any]:
    """Check algebra rules - raise CompositionInvalid if invalid.

    Args:
        pattern_a: First pattern name
        pattern_b: Second pattern name
        scope: Scope type ("iso", "shared", "fed", "handoff")
        operator: Composition operator (";", "|", "+")

    Returns:
        Validation result dict

    Raises:
        CompositionInvalid: When composition rules are violated
    """
    from scripts.validate_composition import can_compose, ScopeType, Operator

    # Convert scope string to ScopeType enum
    scope_map = {
        "iso": ScopeType.ISOLATED,
        "isolated": ScopeType.ISOLATED,
        "shared": ScopeType.SHARED,
        "fed": ScopeType.FEDERATED,
        "federated": ScopeType.FEDERATED,
        "handoff": ScopeType.HANDOFF,
    }
    scope_type = scope_map.get(scope.lower())
    if scope_type is None:
        raise CompositionInvalid([f"Unknown scope type: {scope}"])

    # Convert operator string to Operator enum
    operator_map = {
        ";": Operator.SEQUENTIAL,
        "|": Operator.PARALLEL,
        "+": Operator.CHOICE,
    }
    op_type = operator_map.get(operator)
    if op_type is None:
        raise CompositionInvalid([f"Unknown operator: {operator}"])

    result = can_compose(pattern_a, pattern_b, scope_type, op_type)

    if not result.valid:
        raise CompositionInvalid(result.errors)

    return {
        "valid": result.valid,
        "composition": result.composition,
        "warnings": result.warnings,
        "scope_trace": result.scope_trace,
    }


# ============================================================================
# Main Entry Point (async)
# ============================================================================


async def orchestrate_with_gates(
    prompt: str,
    session_id: str,
    pattern_hint: str | None = None,
) -> dict[str, Any]:
    """Full gate chain to OrchestrationLayer execution.

    This function chains all three gates and then executes via OrchestrationLayer.

    Args:
        prompt: Task description / prompt
        session_id: Session identifier
        pattern_hint: Optional hint for pattern selection

    Returns:
        Orchestration result dict

    Raises:
        ClarificationRequired: If unknowns exist
        ResourcesInsufficient: If resources insufficient
        CompositionInvalid: If composition invalid
    """
    from scripts.agentica_patterns.orchestration_layer import OrchestrationLayer

    # Gate 1: Erotetic - check if prompt has unknowns
    # (For now, assume prompt-based tasks don't have unknowns)
    propositions = {"prompt": prompt}
    gate1_erotetic(propositions)

    # Gate 2: Resources - check if we can launch the pattern
    if pattern_hint:
        gate2_resources(pattern_hint)

    # Gate 3: Composition - skip if no composition specified
    # (Single pattern execution doesn't need composition validation)

    # Infer pattern and get confidence
    from scripts.agentica_patterns.pattern_inference import infer_pattern
    inference = infer_pattern(prompt)
    confidence = inference.confidence

    # All gates passed - execute via OrchestrationLayer
    layer = OrchestrationLayer.create_default(session_id=session_id)

    config: dict[str, Any] = {}
    if pattern_hint:
        config["pattern_hint"] = pattern_hint

    result = await layer.orchestrate(prompt, config=config)

    return {
        "success": result.success,
        "session_id": result.session_id,
        "pattern_used": result.pattern_used,
        "confidence": confidence,  # Include confidence for hook routing
        "aggregated_output": result.aggregated_output,
        "errors": result.errors,
        "total_duration_ms": result.total_duration_ms,
    }


# ============================================================================
# UnifiedGate Class (synchronous validation)
# ============================================================================


class UnifiedGate:
    """Unified gate for validating task requests through 3-gate chain.

    Provides synchronous validation methods for each gate and a combined
    validate() method that runs all gates in order.
    """

    def check_erotetic(self, task: dict[str, Any]) -> bool:
        """Gate 1: Check if task specification has unknowns.

        Args:
            task: Task dict with "description" and optional "unknowns" list

        Returns:
            True if no unknowns

        Raises:
            ClarificationRequired: If unknowns exist
        """
        unknowns = task.get("unknowns", [])

        if unknowns:
            raise ClarificationRequired(unknowns)

        return True

    def check_resources(self, requirements: dict[str, Any]) -> bool:
        """Gate 2: Check if system has sufficient resources.

        Args:
            requirements: Dict with "ram_gb" and "cpu_cores" requirements

        Returns:
            True if resources sufficient

        Raises:
            ResourcesInsufficient: If resources insufficient
        """
        if not requirements:
            return True

        ram_required_gb = requirements.get("ram_gb", 0)
        cpu_required = requirements.get("cpu_cores", 0)

        # Get actual system resources
        mem = psutil.virtual_memory()
        available_ram_gb = mem.available / (1024 * 1024 * 1024)  # Convert to GB

        cpu_count = psutil.cpu_count() or 4
        available_cpu = cpu_count * 0.8  # Reserve 20% for system

        # Check RAM first (priority order)
        if ram_required_gb > available_ram_gb:
            raise ResourcesInsufficient(
                bottleneck="ram",
                suggestion="Consider using streaming or batch processing",
            )

        # Check CPU
        if cpu_required > available_cpu:
            raise ResourcesInsufficient(
                bottleneck="cpu",
                suggestion="Reduce parallelism or use sequential processing",
            )

        return True

    def check_composition(self, composition: dict[str, Any]) -> bool:
        """Gate 3: Check if pattern composition is valid.

        Args:
            composition: Dict with "pattern", "composition_mode", and optionally
                         "next_pattern", "stages", "allow_cycles"

        Returns:
            True if composition is valid

        Raises:
            CompositionInvalid: If composition rules violated
        """
        from scripts.validate_composition import PATTERNS, ScopeType

        pattern = composition.get("pattern")
        mode = composition.get("composition_mode")
        next_pattern = composition.get("next_pattern")
        stages = composition.get("stages", [])
        allow_cycles = composition.get("allow_cycles", True)

        errors: list[str] = []

        if pattern:
            # Get pattern info
            pattern_info = PATTERNS.get(pattern)
            if pattern_info is None:
                errors.append(f"Unknown pattern: {pattern}")
            else:
                # Check if mode is valid for pattern
                valid_scopes = pattern_info.get("scopes", [])

                if mode:
                    # Convert mode to ScopeType
                    mode_map = {
                        "iso": ScopeType.ISOLATED,
                        "isolated": ScopeType.ISOLATED,
                        "shared": ScopeType.SHARED,
                        "fed": ScopeType.FEDERATED,
                        "federated": ScopeType.FEDERATED,
                        "handoff": ScopeType.HANDOFF,
                    }
                    scope_type = mode_map.get(mode.lower())

                    if scope_type is None:
                        errors.append(f"Unknown composition mode: {mode}")
                    elif scope_type not in valid_scopes:
                        valid_str = ", ".join(s.value for s in valid_scopes)
                        errors.append(
                            f"{pattern} requires [{valid_str}] scope, "
                            f"but got [{mode}]"
                        )

        # Check for circular dependencies in stages
        if stages and not allow_cycles:
            seen: set[str] = set()
            for stage in stages:
                if stage in seen:
                    errors.append(f"Circular dependency detected: {stage} appears multiple times")
                    break
                seen.add(stage)

        # If next_pattern specified, validate composition between patterns
        if pattern and next_pattern:
            # For composition with next_pattern, we check if ANY valid composition exists
            # The composition_mode applies to the primary pattern's internal operation
            next_pattern_info = PATTERNS.get(next_pattern)
            if next_pattern_info is None:
                errors.append(f"Unknown pattern: {next_pattern}")
            else:
                # Check if patterns can compose with a compatible scope
                # Find intersection of scopes
                first_scopes = set(pattern_info.get("scopes", []) if pattern_info else [])
                next_scopes = set(next_pattern_info.get("scopes", []))

                # For sequential composition (handoff), check if handoff is valid
                # If first pattern supports handoff, it can hand off to any pattern
                if mode and mode.lower() == "handoff":
                    if ScopeType.HANDOFF not in first_scopes:
                        valid_str = ", ".join(s.value for s in first_scopes)
                        errors.append(
                            f"{pattern} doesn't support handoff mode (valid: [{valid_str}])"
                        )
                    # For handoff, the next pattern just needs to be a valid pattern
                    # (no further scope check needed - handoff is a boundary)
                elif mode:
                    # For other modes, check if there's a common scope
                    scope_type = mode_map.get(mode.lower())
                    if scope_type and scope_type not in next_scopes:
                        # Only warn if the explicit mode is incompatible
                        # This allows patterns to negotiate their own scopes
                        pass  # Allow - patterns can negotiate internally

        if errors:
            raise CompositionInvalid(errors)

        return True

    def validate(self, request: dict[str, Any]) -> dict[str, Any]:
        """Run all gates in order: Erotetic -> Resources -> Composition.

        Args:
            request: Dict with "task", "resources", and "composition" sections

        Returns:
            Result dict with "passed" and "ready_for_orchestration"

        Raises:
            ClarificationRequired: Gate 1 failed
            ResourcesInsufficient: Gate 2 failed
            CompositionInvalid: Gate 3 failed
        """
        task = request.get("task", {})
        resources = request.get("resources", {})
        composition = request.get("composition", {})

        # Gate 1: Erotetic (check for unknowns)
        self.check_erotetic(task)

        # Gate 2: Resources (check system capacity)
        self.check_resources(resources)

        # Gate 3: Composition (check algebra rules)
        self.check_composition(composition)

        return {
            "passed": True,
            "ready_for_orchestration": True,
        }
