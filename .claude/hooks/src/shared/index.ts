/**
 * Shared Module Barrel Exports
 *
 * Central export point for all shared utilities.
 */

// Workflow erotetic gate utilities
export {
  extractPropositions,
  generateClarificationQuestions,
  formatGateStatus,
  evaluateEroteticGate,
  generateBlockFeedback,
  isImplementationTask,
  CRITICAL_PROPOSITIONS,
  PROPOSITION_PATTERNS,
  Q_VALUE_ORDER,
} from './workflow-erotetic.js';

export type {
  Propositions,
  ClarificationQuestion,
  GateFeedback,
  GateResult,
  GateStatus,
} from './workflow-erotetic.js';

// Erotetic questions
export {
  getQHeuristicsForTask,
  resolveFromContext,
  formatAskUserQuestions,
  MAX_QUESTIONS,
} from './erotetic-questions.js';

export type {
  QHeuristic,
  QHeuristicOption,
  TaskQHeuristics,
  ContextResolutionResult,
  FormattedQuestion,
  AskUserQuestionFormat,
} from './erotetic-questions.js';

// Erotetic termination
export {
  checkTermination,
  detectDefaultsIntent,
  applyDefaults,
  MAX_QUESTIONS_TOTAL,
} from './erotetic-termination.js';

export type {
  TerminationState,
  TerminationResult,
} from './erotetic-termination.js';

// Pattern router
export {
  detectPattern,
  isValidId,
  SAFE_ID_PATTERN,
  SUPPORTED_PATTERNS,
} from './pattern-router.js';

export type { PatternType } from './pattern-router.js';

// Pattern selector
export {
  selectPattern,
  validateComposition,
  SUPPORTED_PATTERNS as PATTERN_LIST,
} from './pattern-selector.js';

export type {
  ScopeType,
  OperatorType,
  ValidationResult,
  PatternInferenceResult,
  PatternSelection,
  Task,
} from './pattern-selector.js';

// Composition gate (Gate 3)
export {
  gate3Composition,
  gate3CompositionChain,
  CompositionInvalidError,
} from './composition-gate.js';

// Python bridge (internal use)
export {
  callValidateComposition,
  callPatternInference,
} from './python-bridge.js';

// Resource utilities
export {
  readResourceState,
  getResourceFilePath,
  getSessionId,
  DEFAULT_RESOURCE_STATE,
} from './resource-reader.js';

export type { ResourceState } from './resource-reader.js';

export { getSystemResources } from './resource-utils.js';

export type { SystemResources } from './resource-utils.js';

// Skill router types
export type {
  SkillRouterInput,
  SkillRouterOutput,
  SkillLookupResult,
  SkillTrigger,
  SkillRule,
  SkillRulesConfig,
} from './skill-router-types.js';

export { CircularDependencyError } from './skill-router-types.js';

// Task detector
export { detectTask } from './task-detector.js';

export type { TaskDetectionResult } from './task-detector.js';

// Common types
export type {
  SubagentStartInput,
  SubagentStopInput,
  PreToolUseInput,
  PostToolUseInput,
  StopInput,
  HookOutput,
  QueryResult,
} from './types.js';

// DB utilities
export {
  getDbPath,
  queryDb,
  runPythonQuery,
  registerAgent,
  completeAgent,
  getActiveAgentCount,
} from './db-utils.js';

// Memory client
export {
  MemoryClient,
  searchMemory,
  storeMemory,
  isMemoryAvailable,
  trackUsage,
  recordSkillUsage,
} from './memory-client.js';

export type {
  MemorySearchResult,
  MemoryClientOptions,
  UsageRecord,
} from './memory-client.js';

// Output helpers
export {
  outputContinue,
  outputWithMessage,
  outputBlock,
} from './output.js';
