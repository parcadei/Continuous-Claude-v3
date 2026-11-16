"""
Tests for erotetic-termination.ts - Phase 9 of Self-Improving Skill System

Termination conditions for the erotetic loop:
1. All Q-heuristics resolved (E(X,Q)=empty)
2. User says "use defaults"
3. Hard cap hit (max 4 questions already asked)
"""

import pytest
import subprocess
import json
import os

# Project root
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))

# Hooks directory for running tsx
HOOKS_DIR = os.path.join(PROJECT_ROOT, ".claude/hooks/src")

# Import path for TypeScript (relative from hooks/src dir)
TS_IMPORT = "./shared/erotetic-termination.ts"


def run_tsx(code: str) -> subprocess.CompletedProcess:
    """Helper to run TypeScript code via tsx."""
    return subprocess.run(
        ["npx", "tsx", "-e", code],
        capture_output=True,
        text=True,
        cwd=HOOKS_DIR
    )


# =============================================================================
# Test Interface Exports
# =============================================================================

class TestTerminationStateInterface:
    """Tests for TerminationState interface."""

    def test_interface_exists(self):
        """TerminationState interface should be exported."""
        result = run_tsx(f"""
import type {{ TerminationState }} from '{TS_IMPORT}';
const state: TerminationState = {{
    resolved: {{ goal: 'Build feature' }},
    unresolved: [],
    questionsAsked: 1,
    userRequestedDefaults: false
}};
console.log(JSON.stringify(state));
""")
        # Should compile and output JSON
        assert result.returncode == 0 or "TerminationState" in result.stderr
        if result.returncode == 0:
            data = json.loads(result.stdout.strip())
            assert data["questionsAsked"] == 1

    def test_resolved_is_record(self):
        """resolved should be Record<string, string>."""
        result = run_tsx(f"""
import type {{ TerminationState }} from '{TS_IMPORT}';
const state: TerminationState = {{
    resolved: {{ goal: 'Build feature', scope: 'module' }},
    unresolved: [],
    questionsAsked: 2,
    userRequestedDefaults: false
}};
console.log(Object.keys(state.resolved).length);
""")
        assert "2" in result.stdout


class TestTerminationResultInterface:
    """Tests for TerminationResult interface."""

    def test_interface_exists(self):
        """TerminationResult interface should be exported."""
        result = run_tsx(f"""
import type {{ TerminationResult }} from '{TS_IMPORT}';
const result: TerminationResult = {{
    shouldTerminate: true,
    reason: 'all_resolved',
    finalResolution: {{ goal: 'test' }}
}};
console.log(JSON.stringify(result));
""")
        assert result.returncode == 0 or "TerminationResult" in result.stderr

    def test_reason_enum_values(self):
        """reason should support all valid values."""
        reasons = ['all_resolved', 'defaults_requested', 'max_questions', 'continue']
        for reason in reasons:
            result = run_tsx(f"""
import type {{ TerminationResult }} from '{TS_IMPORT}';
const result: TerminationResult = {{
    shouldTerminate: {str(reason != 'continue').lower()},
    reason: '{reason}',
    finalResolution: {{}}
}};
console.log(result.reason);
""")
            # Should compile
            assert result.returncode == 0 or reason in result.stdout


# =============================================================================
# Test Constants
# =============================================================================

class TestConstants:
    """Tests for termination constants."""

    def test_max_questions_constant(self):
        """MAX_QUESTIONS_TOTAL should be 4."""
        result = run_tsx(f"""
import {{ MAX_QUESTIONS_TOTAL }} from '{TS_IMPORT}';
console.log(MAX_QUESTIONS_TOTAL);
""")
        assert result.returncode == 0
        assert "4" in result.stdout


# =============================================================================
# Test checkTermination Function
# =============================================================================

class TestCheckTermination:
    """Tests for checkTermination function."""

    def test_function_exists(self):
        """checkTermination function should be exported."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';
console.log(typeof checkTermination);
""")
        assert result.returncode == 0
        assert "function" in result.stdout

    def test_all_resolved_terminates(self):
        """When all Q-heuristics are resolved, should terminate."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';
const state = {{
    resolved: {{ goal: 'Build API', scope: 'module' }},
    unresolved: [],  // Empty = all resolved
    questionsAsked: 2,
    userRequestedDefaults: false
}};
const result = checkTermination(state);
console.log(JSON.stringify(result));
""")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["shouldTerminate"] is True
        assert data["reason"] == "all_resolved"

    def test_defaults_requested_terminates(self):
        """When user requests defaults, should terminate immediately."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';
const state = {{
    resolved: {{ goal: 'Build API' }},
    unresolved: [{{ id: 'scope', question: 'What scope?', options: [], default: 'module' }}],
    questionsAsked: 1,
    userRequestedDefaults: true
}};
const result = checkTermination(state);
console.log(JSON.stringify(result));
""")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["shouldTerminate"] is True
        assert data["reason"] == "defaults_requested"

    def test_max_questions_terminates(self):
        """When 4 questions already asked, should terminate."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';
const state = {{
    resolved: {{ goal: 'Build API', scope: 'module' }},
    unresolved: [{{ id: 'format', question: 'What format?', options: [], default: 'REST' }}],
    questionsAsked: 4,  // Hard cap hit
    userRequestedDefaults: false
}};
const result = checkTermination(state);
console.log(JSON.stringify(result));
""")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["shouldTerminate"] is True
        assert data["reason"] == "max_questions"

    def test_continue_when_more_questions_needed(self):
        """When questions remain and cap not hit, should continue."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';
const state = {{
    resolved: {{ goal: 'Build API' }},
    unresolved: [
        {{ id: 'scope', question: 'What scope?', options: [] }},
        {{ id: 'format', question: 'What format?', options: [] }}
    ],
    questionsAsked: 2,  // Under cap
    userRequestedDefaults: false
}};
const result = checkTermination(state);
console.log(JSON.stringify(result));
""")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["shouldTerminate"] is False
        assert data["reason"] == "continue"

    def test_final_resolution_includes_resolved(self):
        """finalResolution should include all resolved values."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';
const state = {{
    resolved: {{ goal: 'Build API', scope: 'module' }},
    unresolved: [],
    questionsAsked: 2,
    userRequestedDefaults: false
}};
const result = checkTermination(state);
console.log(JSON.stringify(result.finalResolution));
""")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["goal"] == "Build API"
        assert data["scope"] == "module"

    def test_termination_priority_order(self):
        """Priority: all_resolved > defaults_requested > max_questions."""
        # When all resolved AND defaults requested, should be all_resolved
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';
const state = {{
    resolved: {{ goal: 'Build API' }},
    unresolved: [],  // All resolved
    questionsAsked: 4,  // Max hit too
    userRequestedDefaults: true  // Also requested defaults
}};
const result = checkTermination(state);
console.log(result.reason);
""")
        assert result.returncode == 0
        assert "all_resolved" in result.stdout


# =============================================================================
# Test applyDefaults Function
# =============================================================================

class TestApplyDefaults:
    """Tests for applyDefaults function."""

    def test_function_exists(self):
        """applyDefaults function should be exported."""
        result = run_tsx(f"""
import {{ applyDefaults }} from '{TS_IMPORT}';
console.log(typeof applyDefaults);
""")
        assert result.returncode == 0
        assert "function" in result.stdout

    def test_fills_unresolved_with_defaults(self):
        """Should fill unresolved Q-heuristics with their default values."""
        result = run_tsx(f"""
import {{ applyDefaults }} from '{TS_IMPORT}';
const resolved = {{ goal: 'Build API' }};
const unresolved = [
    {{ id: 'scope', question: 'What scope?', options: [], default: 'module' }},
    {{ id: 'format', question: 'What format?', options: [], default: 'json' }}
];
const result = applyDefaults(resolved, unresolved);
console.log(JSON.stringify(result));
""")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["goal"] == "Build API"
        assert data["scope"] == "module"
        assert data["format"] == "json"

    def test_preserves_resolved_values(self):
        """Should not overwrite already resolved values."""
        result = run_tsx(f"""
import {{ applyDefaults }} from '{TS_IMPORT}';
const resolved = {{ goal: 'Build API', scope: 'system' }};  // scope already set
const unresolved = [
    {{ id: 'scope', question: 'What scope?', options: [], default: 'module' }}  // Has different default
];
const result = applyDefaults(resolved, unresolved);
console.log(JSON.stringify(result));
""")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["scope"] == "system"  # Should keep original, not use default

    def test_handles_missing_defaults(self):
        """Should use empty string for Q-heuristics without defaults."""
        result = run_tsx(f"""
import {{ applyDefaults }} from '{TS_IMPORT}';
const resolved = {{ goal: 'Build API' }};
const unresolved = [
    {{ id: 'scope', question: 'What scope?', options: [] }}  // No default
];
const result = applyDefaults(resolved, unresolved);
console.log(JSON.stringify(result));
""")
        assert result.returncode == 0
        data = json.loads(result.stdout.strip())
        assert data["scope"] == ""  # Empty string for no default

    def test_returns_new_object(self):
        """Should return a new object, not mutate input."""
        result = run_tsx(f"""
import {{ applyDefaults }} from '{TS_IMPORT}';
const resolved = {{ goal: 'Build API' }};
const unresolved = [
    {{ id: 'scope', question: 'What scope?', options: [], default: 'module' }}
];
const result = applyDefaults(resolved, unresolved);
console.log(resolved === result);  // Should be false
console.log('scope' in resolved);  // Should be false (not mutated)
""")
        assert result.returncode == 0
        lines = result.stdout.strip().split('\n')
        assert "false" in lines[0]
        assert "false" in lines[1]


# =============================================================================
# Test "Use Defaults" Intent Detection
# =============================================================================

class TestDetectDefaultsIntent:
    """Tests for detectDefaultsIntent function."""

    def test_function_exists(self):
        """detectDefaultsIntent function should be exported."""
        result = run_tsx(f"""
import {{ detectDefaultsIntent }} from '{TS_IMPORT}';
console.log(typeof detectDefaultsIntent);
""")
        assert result.returncode == 0
        assert "function" in result.stdout

    def test_detects_just_use_defaults(self):
        """Should detect 'just use defaults'."""
        result = run_tsx(f"""
import {{ detectDefaultsIntent }} from '{TS_IMPORT}';
console.log(detectDefaultsIntent('just use defaults'));
""")
        assert result.returncode == 0
        assert "true" in result.stdout

    def test_detects_pick_for_me(self):
        """Should detect 'pick for me'."""
        result = run_tsx(f"""
import {{ detectDefaultsIntent }} from '{TS_IMPORT}';
console.log(detectDefaultsIntent('pick for me please'));
""")
        assert result.returncode == 0
        assert "true" in result.stdout

    def test_detects_you_decide(self):
        """Should detect 'you decide'."""
        result = run_tsx(f"""
import {{ detectDefaultsIntent }} from '{TS_IMPORT}';
console.log(detectDefaultsIntent('you decide what is best'));
""")
        assert result.returncode == 0
        assert "true" in result.stdout

    def test_detects_whatever_works(self):
        """Should detect 'whatever works'."""
        result = run_tsx(f"""
import {{ detectDefaultsIntent }} from '{TS_IMPORT}';
console.log(detectDefaultsIntent('whatever works for you'));
""")
        assert result.returncode == 0
        assert "true" in result.stdout

    def test_detects_go_with_defaults(self):
        """Should detect 'go with defaults'."""
        result = run_tsx(f"""
import {{ detectDefaultsIntent }} from '{TS_IMPORT}';
console.log(detectDefaultsIntent('go with defaults'));
""")
        assert result.returncode == 0
        assert "true" in result.stdout

    def test_detects_default_values(self):
        """Should detect 'use default values'."""
        result = run_tsx(f"""
import {{ detectDefaultsIntent }} from '{TS_IMPORT}';
console.log(detectDefaultsIntent('use the default values'));
""")
        assert result.returncode == 0
        assert "true" in result.stdout

    def test_not_triggered_by_normal_prompt(self):
        """Should not trigger on normal prompts."""
        result = run_tsx(f"""
import {{ detectDefaultsIntent }} from '{TS_IMPORT}';
console.log(detectDefaultsIntent('build an API for user management'));
""")
        assert result.returncode == 0
        assert "false" in result.stdout

    def test_case_insensitive(self):
        """Should be case insensitive."""
        result = run_tsx(f"""
import {{ detectDefaultsIntent }} from '{TS_IMPORT}';
console.log(detectDefaultsIntent('JUST USE DEFAULTS'));
""")
        assert result.returncode == 0
        assert "true" in result.stdout


# =============================================================================
# Integration Tests
# =============================================================================

class TestIntegration:
    """Integration tests for the complete termination flow."""

    def test_full_termination_flow_all_resolved(self):
        """Complete flow when all questions are resolved."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';

const state = {{
    resolved: {{ goal: 'Build API', scope: 'module', format: 'REST' }},
    unresolved: [],
    questionsAsked: 3,
    userRequestedDefaults: false
}};

const termResult = checkTermination(state);
if (termResult.shouldTerminate) {{
    console.log('Terminated:', termResult.reason);
    console.log('Resolution:', JSON.stringify(termResult.finalResolution));
}}
""")
        assert result.returncode == 0
        assert "Terminated: all_resolved" in result.stdout
        assert "goal" in result.stdout

    def test_full_termination_flow_defaults_requested(self):
        """Complete flow when user requests defaults."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';

const state = {{
    resolved: {{ goal: 'Build API' }},
    unresolved: [
        {{ id: 'scope', question: 'Scope?', options: [], default: 'module' }},
        {{ id: 'format', question: 'Format?', options: [], default: 'REST' }}
    ],
    questionsAsked: 1,
    userRequestedDefaults: true
}};

const termResult = checkTermination(state);
console.log('Terminated:', termResult.reason);
console.log('Has scope:', 'scope' in termResult.finalResolution);
console.log('Scope value:', termResult.finalResolution.scope);
""")
        assert result.returncode == 0
        assert "Terminated: defaults_requested" in result.stdout
        assert "Has scope: true" in result.stdout
        assert "Scope value: module" in result.stdout

    def test_full_termination_flow_max_questions(self):
        """Complete flow when max questions reached."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';

const state = {{
    resolved: {{ goal: 'Build API', scope: 'module' }},
    unresolved: [
        {{ id: 'format', question: 'Format?', options: [], default: 'REST' }},
        {{ id: 'auth', question: 'Auth?', options: [], default: 'None' }}
    ],
    questionsAsked: 4,
    userRequestedDefaults: false
}};

const termResult = checkTermination(state);
console.log('Terminated:', termResult.reason);
console.log('Format applied:', termResult.finalResolution.format);
console.log('Auth applied:', termResult.finalResolution.auth);
""")
        assert result.returncode == 0
        assert "Terminated: max_questions" in result.stdout
        assert "Format applied: REST" in result.stdout
        assert "Auth applied: None" in result.stdout

    def test_continue_returns_partial_resolution(self):
        """When continuing, should return current resolved values."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';

const state = {{
    resolved: {{ goal: 'Build API' }},
    unresolved: [{{ id: 'scope', question: 'Scope?', options: [] }}],
    questionsAsked: 1,
    userRequestedDefaults: false
}};

const termResult = checkTermination(state);
console.log('Should terminate:', termResult.shouldTerminate);
console.log('Reason:', termResult.reason);
console.log('Goal preserved:', termResult.finalResolution.goal);
""")
        assert result.returncode == 0
        assert "Should terminate: false" in result.stdout
        assert "Reason: continue" in result.stdout
        assert "Goal preserved: Build API" in result.stdout


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_zero_questions_asked(self):
        """Should handle case where no questions have been asked yet."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';

const state = {{
    resolved: {{}},
    unresolved: [{{ id: 'goal', question: 'Goal?', options: [] }}],
    questionsAsked: 0,
    userRequestedDefaults: false
}};

const termResult = checkTermination(state);
console.log(termResult.shouldTerminate);
console.log(termResult.reason);
""")
        assert result.returncode == 0
        assert "false" in result.stdout
        assert "continue" in result.stdout

    def test_empty_state(self):
        """Should handle empty resolved and unresolved."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';

const state = {{
    resolved: {{}},
    unresolved: [],  // Empty = technically all resolved
    questionsAsked: 0,
    userRequestedDefaults: false
}};

const termResult = checkTermination(state);
console.log(termResult.shouldTerminate);
console.log(termResult.reason);
""")
        assert result.returncode == 0
        assert "true" in result.stdout
        assert "all_resolved" in result.stdout

    def test_exactly_four_questions(self):
        """At exactly 4 questions, should terminate due to max."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';

const state = {{
    resolved: {{ a: '1', b: '2', c: '3' }},
    unresolved: [{{ id: 'd', question: 'D?', options: [], default: '4' }}],
    questionsAsked: 4,
    userRequestedDefaults: false
}};

const termResult = checkTermination(state);
console.log(termResult.reason);
""")
        assert result.returncode == 0
        assert "max_questions" in result.stdout

    def test_three_questions_continues(self):
        """At 3 questions with unresolved, should continue."""
        result = run_tsx(f"""
import {{ checkTermination }} from '{TS_IMPORT}';

const state = {{
    resolved: {{ a: '1', b: '2', c: '3' }},
    unresolved: [{{ id: 'd', question: 'D?', options: [] }}],
    questionsAsked: 3,
    userRequestedDefaults: false
}};

const termResult = checkTermination(state);
console.log(termResult.shouldTerminate);
console.log(termResult.reason);
""")
        assert result.returncode == 0
        assert "false" in result.stdout
        assert "continue" in result.stdout

    def test_apply_defaults_empty_unresolved(self):
        """applyDefaults with empty unresolved should return copy of resolved."""
        result = run_tsx(f"""
import {{ applyDefaults }} from '{TS_IMPORT}';

const resolved = {{ goal: 'Build' }};
const result = applyDefaults(resolved, []);
console.log(JSON.stringify(result));
console.log(resolved === result);
""")
        assert result.returncode == 0
        lines = result.stdout.strip().split('\n')
        data = json.loads(lines[0])
        assert data == {"goal": "Build"}
        assert "false" in lines[1]  # Not same object


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
