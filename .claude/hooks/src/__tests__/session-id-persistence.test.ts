/**
 * Tests for session ID persistence across hooks.
 *
 * The coordination layer uses session IDs to track file claims and prevent
 * conflicts. Since each hook runs as a separate Node.js process, we persist
 * the session ID to a file so all hooks use the same ID.
 *
 * Flow:
 *   SessionStart: session-register.ts writes ID to ~/.claude/.coordination-session-id
 *   PreToolUse:   file-claims.ts reads ID from that file
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

// Import actual implementations from shared module
import {
  getSessionIdFile,
  generateSessionId,
  writeSessionId,
  readSessionId,
  getSessionId,
  getProject,
} from '../shared/session-id.js';

describe('getSessionIdFile', () => {
  it('returns path in .claude directory', () => {
    const result = getSessionIdFile();
    expect(result).toContain('.claude');
    expect(result).toContain('.coordination-session-id');
  });

  it('creates directory when createDir option is true', () => {
    // This test just verifies the function doesn't throw
    // Actual directory creation depends on HOME env
    expect(() => getSessionIdFile({ createDir: true })).not.toThrow();
  });
});

describe('generateSessionId', () => {
  it('returns a string starting with "s-" when no BRAINTRUST_SPAN_ID', () => {
    const originalSpanId = process.env.BRAINTRUST_SPAN_ID;
    delete process.env.BRAINTRUST_SPAN_ID;

    try {
      const result = generateSessionId();
      expect(result).toMatch(/^s-[a-z0-9]+$/);
    } finally {
      if (originalSpanId) {
        process.env.BRAINTRUST_SPAN_ID = originalSpanId;
      }
    }
  });

  it('uses BRAINTRUST_SPAN_ID when available', () => {
    const originalSpanId = process.env.BRAINTRUST_SPAN_ID;
    process.env.BRAINTRUST_SPAN_ID = 'test1234-5678-abcd-efgh';

    try {
      const result = generateSessionId();
      expect(result).toBe('test1234');
    } finally {
      if (originalSpanId) {
        process.env.BRAINTRUST_SPAN_ID = originalSpanId;
      } else {
        delete process.env.BRAINTRUST_SPAN_ID;
      }
    }
  });
});

describe('writeSessionId and readSessionId', () => {
  let tempDir: string;
  let originalHome: string | undefined;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'session-id-test-'));
    originalHome = process.env.HOME;
    process.env.HOME = tempDir;
  });

  afterEach(() => {
    if (originalHome) {
      process.env.HOME = originalHome;
    } else {
      delete process.env.HOME;
    }
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('writeSessionId creates file and readSessionId retrieves it', () => {
    const testId = 's-test123';

    const writeResult = writeSessionId(testId);
    expect(writeResult).toBe(true);

    const readResult = readSessionId();
    expect(readResult).toBe(testId);
  });

  it('readSessionId returns null when file does not exist', () => {
    const result = readSessionId();
    expect(result).toBeNull();
  });

  it('writeSessionId overwrites existing session ID', () => {
    writeSessionId('s-old');
    writeSessionId('s-new');

    const result = readSessionId();
    expect(result).toBe('s-new');
  });
});

describe('getSessionId', () => {
  let tempDir: string;
  let originalHome: string | undefined;
  let originalCoordId: string | undefined;
  let originalSpanId: string | undefined;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'session-id-test-'));
    originalHome = process.env.HOME;
    originalCoordId = process.env.COORDINATION_SESSION_ID;
    originalSpanId = process.env.BRAINTRUST_SPAN_ID;
    process.env.HOME = tempDir;
    delete process.env.COORDINATION_SESSION_ID;
    delete process.env.BRAINTRUST_SPAN_ID;
  });

  afterEach(() => {
    if (originalHome) {
      process.env.HOME = originalHome;
    } else {
      delete process.env.HOME;
    }
    if (originalCoordId) {
      process.env.COORDINATION_SESSION_ID = originalCoordId;
    } else {
      delete process.env.COORDINATION_SESSION_ID;
    }
    if (originalSpanId) {
      process.env.BRAINTRUST_SPAN_ID = originalSpanId;
    } else {
      delete process.env.BRAINTRUST_SPAN_ID;
    }
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('prefers COORDINATION_SESSION_ID env var', () => {
    writeSessionId('s-from-file');
    process.env.COORDINATION_SESSION_ID = 's-from-env';

    const result = getSessionId();
    expect(result).toBe('s-from-env');
  });

  it('reads from file when env not set', () => {
    writeSessionId('s-from-file');

    const result = getSessionId();
    expect(result).toBe('s-from-file');
  });

  it('generates new ID when no sources available', () => {
    const result = getSessionId();
    expect(result).toMatch(/^s-[a-z0-9]+$/);
  });

  it('uses BRAINTRUST_SPAN_ID as fallback', () => {
    process.env.BRAINTRUST_SPAN_ID = 'fb123456-7890-abcd';

    const result = getSessionId();
    expect(result).toBe('fb123456');
  });
});

describe('getProject', () => {
  let originalProjectDir: string | undefined;

  beforeEach(() => {
    originalProjectDir = process.env.CLAUDE_PROJECT_DIR;
  });

  afterEach(() => {
    if (originalProjectDir) {
      process.env.CLAUDE_PROJECT_DIR = originalProjectDir;
    } else {
      delete process.env.CLAUDE_PROJECT_DIR;
    }
  });

  it('returns CLAUDE_PROJECT_DIR when set', () => {
    process.env.CLAUDE_PROJECT_DIR = '/test/project';

    const result = getProject();
    expect(result).toBe('/test/project');
  });

  it('falls back to cwd when CLAUDE_PROJECT_DIR not set', () => {
    delete process.env.CLAUDE_PROJECT_DIR;

    const result = getProject();
    expect(result).toBe(process.cwd());
  });
});

describe('cross-process consistency', () => {
  let tempDir: string;
  let originalHome: string | undefined;
  let originalCoordId: string | undefined;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'session-id-test-'));
    originalHome = process.env.HOME;
    originalCoordId = process.env.COORDINATION_SESSION_ID;
    process.env.HOME = tempDir;
    delete process.env.COORDINATION_SESSION_ID;
  });

  afterEach(() => {
    if (originalHome) {
      process.env.HOME = originalHome;
    } else {
      delete process.env.HOME;
    }
    if (originalCoordId) {
      process.env.COORDINATION_SESSION_ID = originalCoordId;
    } else {
      delete process.env.COORDINATION_SESSION_ID;
    }
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  it('session-register and file-claims use same ID via file', () => {
    // Simulate session-register writing
    const generatedId = generateSessionId();
    writeSessionId(generatedId);

    // Simulate file-claims reading (different process, no env var)
    const readId = getSessionId();

    expect(readId).toBe(generatedId);
  });

  it('multiple getSessionId calls return same ID', () => {
    writeSessionId('s-consistent');

    const id1 = getSessionId();
    const id2 = getSessionId();
    const id3 = getSessionId();

    expect(id1).toBe('s-consistent');
    expect(id2).toBe('s-consistent');
    expect(id3).toBe('s-consistent');
  });
});
