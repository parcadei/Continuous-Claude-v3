# Erotetic Prompt Resolver Hook

## Overview

A `UserPromptSubmit` hook that intercepts ambiguous prompts, asks clarifying questions until erotetic completion, then passes enriched context to skill generation.

## Hook Type

- **Event**: `UserPromptSubmit`
- **Behavior**: Block until questions resolved, then continue with enriched prompt
- **Integration**: Uses `AskUserQuestion` tool for clarification loop

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    UserPromptSubmit Hook                         │
├─────────────────────────────────────────────────────────────────┤
│  Input: user_prompt                                              │
│         ↓                                                        │
│  Stage 1: Erotetic Analysis                                      │
│    - Parse prompt as declaratives X                              │
│    - Compute E(X, Q) → evoked questions                          │
│    - Check: any unresolved questions?                            │
│         ↓                                                        │
│  ┌─ YES: questions remain ──────────────────────────────────┐   │
│  │  return {                                                 │   │
│  │    result: 'block',                                       │   │
│  │    questions: [{ question, options }]  // AskUserQuestion │   │
│  │  }                                                        │   │
│  │  → User answers → Hook fires again with answers           │   │
│  └───────────────────────────────────────────────────────────┘   │
│         ↓                                                        │
│  ┌─ NO: erotetic complete ──────────────────────────────────┐   │
│  │  Stages 2-4: Generate skill                               │   │
│  │  return {                                                 │   │
│  │    result: 'continue',                                    │   │
│  │    message: enrichedPrompt + skillYAML                    │   │
│  │  }                                                        │   │
│  └───────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

## Input Schema

```typescript
interface UserPromptSubmitInput {
  prompt: string;           // User's original prompt
  context?: {
    answers?: Record<string, string>;  // Previous clarification answers
    iteration?: number;                 // Clarification loop count
  };
}
```

## Output Schema

```typescript
// When questions remain
interface BlockOutput {
  result: 'block';
  questions: Array<{
    question: string;
    header: string;
    options: Array<{ label: string; description: string }>;
    multiSelect: boolean;
  }>;
}

// When erotetic complete
interface ContinueOutput {
  result: 'continue';
  message: string;  // Enriched prompt + generated skill context
}
```

## Erotetic Stage 1 Implementation

```typescript
function eroteticallyAnalyze(prompt: string, answers: Record<string, string>): EvokedQuestion[] {
  // 1. Parse prompt as declaratives X
  const X = parseDeclaratives(prompt);

  // 2. Apply answered questions to narrow X
  for (const [key, value] of Object.entries(answers)) {
    X.add(resolvedFact(key, value));
  }

  // 3. Compute E(X, Q) - what questions does X evoke?
  const evokedQuestions = computeEvocation(X);

  // 4. Filter already-answered
  return evokedQuestions.filter(q => !answers[q.id]);
}
```

## Example Flow

**Prompt**: "Implement security authorization protocol"

**Iteration 1**:
```
E(X, Q) evokes:
  - "What auth type?" → [OAuth2, JWT, Session, API Key]
  - "What resources?" → [API endpoints, Files, Database, All]
Hook returns: { result: 'block', questions: [...] }
```

**User answers**: OAuth2, API endpoints

**Iteration 2**:
```
E(X ∪ {auth=OAuth2, resources=API}, Q) evokes:
  - "Refresh tokens?" → [Yes, No]
  - "Scopes required?" → [Read, Write, Admin, Custom]
Hook returns: { result: 'block', questions: [...] }
```

**User answers**: Yes, Read+Write

**Iteration 3**:
```
E(X ∪ {...}, Q) = ∅  // No more questions
Hook returns: { result: 'continue', message: <enriched prompt + skill YAML> }
```

## Stages 2-4 (on erotetic completion)

Once no questions remain:

```typescript
// Stage 2: Decision Theory
const mdp = extractMDP(resolvedX);  // States, Actions, Transitions

// Stage 3: Logic Constraints
const logic = extractLogic(resolvedX);  // O/F/P, G/F/U operators

// Stage 4: Synthesize
const skillYAML = synthesize(mdp, logic);  // v5.1 Hybrid format
```

## Registration

```json
// .claude/settings.json
{
  "hooks": {
    "UserPromptSubmit": [{
      "hooks": [{
        "type": "command",
        "command": "$CLAUDE_PROJECT_DIR/.claude/hooks/erotetic-prompt-resolver.sh"
      }]
    }]
  }
}
```

## Files to Create

1. `.claude/hooks/erotetic-prompt-resolver.sh` - Shell wrapper
2. `.claude/hooks/src/erotetic-prompt-resolver.ts` - TypeScript handler
3. `scripts/prompt_to_dtml/stages/erotetic.py` - Core evocation logic
4. `scripts/prompt_to_dtml/stages/decision_theory.py` - MDP extraction
5. `scripts/prompt_to_dtml/stages/logic_constraints.py` - Modal/deontic
6. `scripts/prompt_to_dtml/stages/synthesizer.py` - v5.1 output

## Theoretical Backing

- **E(X, Q)**: Wiśniewski Inferential Erotetic Logic (Ragie: 0db9802d)
- **Complete answer**: CSP fully constrained, no more evoked questions
- **Functor synthesis**: DisCoPy pattern (Ragie: b6104c17)

## Testing

```bash
# Manual test
echo '{"prompt": "Implement auth"}' | .claude/hooks/erotetic-prompt-resolver.sh

# Expected: questions array until resolved
```
