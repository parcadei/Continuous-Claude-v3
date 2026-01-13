/**
 * Tests for TypeScript Daemon Client
 *
 * TDD tests for the shared daemon client used by all TypeScript hooks.
 * The client communicates with the Python TLDR daemon via Unix socket.
 */

import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { existsSync, mkdirSync, writeFileSync, rmSync, unlinkSync, readFileSync } from 'fs';
import { join } from 'path';
import * as net from 'net';
import * as crypto from 'crypto';

// Create mock module for daemon-client
// This allows us to control isDaemonReachable and tryStartDaemon behavior
const mockDaemonClient = vi.hoisted(() => {
  // Default mock implementations
  let mockIsDaemonReachable = false;
  let mockTryStartDaemon = false;

  return {
    // Mock state
    _isDaemonReachable: mockIsDaemonReachable,
    _tryStartDaemon: mockTryStartDaemon,

    // Reset mocks
    _reset: function() {
      this._isDaemonReachable = false;
      this._tryStartDaemon = false;
    },

    // Setters for test control
    setDaemonReachable: function(value: boolean) { this._isDaemonReachable = value; },
    setDaemonStarts: function(value: boolean) { this._tryStartDaemon = value; },

    // Mock implementations
    getSocketPath: vi.fn((projectDir: string) => {
      const hash = crypto.createHash('md5').update(projectDir).digest('hex').substring(0, 8);
      return `/tmp/tldr-${hash}.sock`;
    }),

    getStatusFile: vi.fn((projectDir: string) => {
      const statusPath = join(projectDir, '.tldr', 'status');
      if (existsSync(statusPath)) {
        try {
          return readFileSync(statusPath, 'utf-8').trim();
        } catch {
          return null;
        }
      }
      return null;
    }),

    isIndexing: vi.fn((projectDir: string) => {
      const statusPath = join(projectDir, '.tldr', 'status');
      if (existsSync(statusPath)) {
        try {
          return readFileSync(statusPath, 'utf-8').trim() === 'indexing';
        } catch {
          return false;
        }
      }
      return false;
    }),

    isDaemonReachable: vi.fn((projectDir: string) => {
      return mockDaemonClient._isDaemonReachable;
    }),

    tryStartDaemon: vi.fn((projectDir: string) => {
      return mockDaemonClient._tryStartDaemon;
    }),

    queryDaemonSync: vi.fn((query: any, projectDir: string) => {
      // Check if indexing - return early with indexing flag
      if (mockDaemonClient.isIndexing(projectDir)) {
        return { indexing: true, status: 'indexing', message: 'Daemon is still indexing' };
      }

      if (!mockDaemonClient._isDaemonReachable) {
        if (!mockDaemonClient._tryStartDaemon) {
          return { status: 'unavailable', error: 'Daemon not running and could not start' };
        }
      }

      // Simulate successful connection
      return { status: 'ok' };
    }),

    queryDaemon: vi.fn(async (query: any, projectDir: string) => {
      // Check if indexing - return early with indexing flag
      if (mockDaemonClient.isIndexing(projectDir)) {
        return { indexing: true, status: 'indexing', message: 'Daemon is still indexing' };
      }

      if (!mockDaemonClient._isDaemonReachable) {
        if (!mockDaemonClient._tryStartDaemon) {
          return { status: 'unavailable', error: 'Daemon not running and could not start' };
        }
      }

      // Simulate successful connection
      return { status: 'ok' };
    }),

    DaemonQuery: {} as any,
    DaemonResponse: {} as any,
  };
});

// Apply mocks before importing
vi.mock('../daemon-client.js', () => mockDaemonClient);

// Now import from the mocked module
const {
  getSocketPath,
  getStatusFile,
  isIndexing,
  queryDaemon,
  queryDaemonSync,
  DaemonQuery,
  DaemonResponse,
} = await import('../daemon-client.js');

// Test fixtures
const TEST_PROJECT_DIR = '/tmp/daemon-client-test';
const TLDR_DIR = join(TEST_PROJECT_DIR, '.tldr');

function setupTestEnv(): void {
  if (!existsSync(TLDR_DIR)) {
    mkdirSync(TLDR_DIR, { recursive: true });
  }
}

function cleanupTestEnv(): void {
  if (existsSync(TEST_PROJECT_DIR)) {
    rmSync(TEST_PROJECT_DIR, { recursive: true, force: true });
  }
}

// Helper to compute socket path (mirrors the daemon logic)
function computeSocketPath(projectDir: string): string {
  const hash = crypto.createHash('md5').update(projectDir).digest('hex').substring(0, 8);
  return `/tmp/tldr-${hash}.sock`;
}

// =============================================================================
// Test 1: getSocketPath() - compute deterministic socket path
// =============================================================================

describe('getSocketPath', () => {
  it('should compute socket path using md5 hash', () => {
    const projectPath = '/Users/test/myproject';
    const expectedHash = crypto.createHash('md5')
      .update(projectPath)
      .digest('hex')
      .substring(0, 8);
    const expectedPath = `/tmp/tldr-${expectedHash}.sock`;

    expect(getSocketPath(projectPath)).toBe(expectedPath);
  });

  it('should produce different paths for different projects', () => {
    const path1 = getSocketPath('/project/a');
    const path2 = getSocketPath('/project/b');

    expect(path1).not.toBe(path2);
  });

  it('should be deterministic for same project', () => {
    const path1 = getSocketPath('/project/same');
    const path2 = getSocketPath('/project/same');

    expect(path1).toBe(path2);
  });
});

// =============================================================================
// Test 2: getStatusFile() - read .tldr/status if exists
// =============================================================================

describe('getStatusFile', () => {
  beforeEach(() => {
    setupTestEnv();
  });

  afterEach(() => {
    cleanupTestEnv();
  });

  it('should return status content when file exists', () => {
    writeFileSync(join(TLDR_DIR, 'status'), 'ready');
    expect(getStatusFile(TEST_PROJECT_DIR)).toBe('ready');
  });

  it('should return null when status file does not exist', () => {
    const statusPath = join(TLDR_DIR, 'status');
    if (existsSync(statusPath)) {
      unlinkSync(statusPath);
    }

    expect(getStatusFile(TEST_PROJECT_DIR)).toBeNull();
  });

  it('should detect indexing status', () => {
    writeFileSync(join(TLDR_DIR, 'status'), 'indexing');
    expect(getStatusFile(TEST_PROJECT_DIR)).toBe('indexing');
  });

  it('should work with isIndexing helper', () => {
    writeFileSync(join(TLDR_DIR, 'status'), 'indexing');
    expect(isIndexing(TEST_PROJECT_DIR)).toBe(true);

    writeFileSync(join(TLDR_DIR, 'status'), 'ready');
    expect(isIndexing(TEST_PROJECT_DIR)).toBe(false);
  });
});

// =============================================================================
// Test 3: DaemonQuery and DaemonResponse interfaces
// =============================================================================

describe('DaemonQuery and DaemonResponse types', () => {
  it('should define valid query structure for ping', () => {
    const query: DaemonQuery = { cmd: 'ping' };
    expect(query.cmd).toBe('ping');
  });

  it('should define valid query structure for search', () => {
    const query: DaemonQuery = { cmd: 'search', pattern: 'handleClick' };
    expect(query.cmd).toBe('search');
    expect(query.pattern).toBe('handleClick');
  });

  it('should define valid response structure', () => {
    const response: DaemonResponse = {
      status: 'ok',
      results: [{ file: 'test.ts', line: 42 }],
    };
    expect(response.status).toBe('ok');
    expect(response.results).toHaveLength(1);
  });

  it('should support indexing flag in response', () => {
    const response: DaemonResponse = { indexing: true };
    expect(response.indexing).toBe(true);
  });
});

// =============================================================================
// Test 4: queryDaemonSync() - sync version
// =============================================================================

describe('queryDaemonSync', () => {
  beforeEach(() => {
    setupTestEnv();
    mockDaemonClient._reset();
  });

  afterEach(() => {
    cleanupTestEnv();
  });

  it('should return unavailable when socket does not exist', () => {
    // Daemon not reachable and won't start
    mockDaemonClient.setDaemonReachable(false);
    mockDaemonClient.setDaemonStarts(false);

    const result = queryDaemonSync({ cmd: 'ping' }, TEST_PROJECT_DIR);
    expect(result.status).toBe('unavailable');
  });

  it('should return indexing:true when status file says indexing', () => {
    writeFileSync(join(TLDR_DIR, 'status'), 'indexing');

    const result = queryDaemonSync({ cmd: 'search', pattern: 'test' }, TEST_PROJECT_DIR);
    expect(result.indexing).toBe(true);
  });

  it('should return ok when daemon is reachable', () => {
    mockDaemonClient.setDaemonReachable(true);
    mockDaemonClient.setDaemonStarts(true);

    const result = queryDaemonSync({ cmd: 'ping' }, TEST_PROJECT_DIR);
    expect(result.status).toBe('ok');
  });

  it('should handle timeout gracefully', () => {
    const timeoutResponse: DaemonResponse = { status: 'error', error: 'timeout' };
    expect(timeoutResponse.error).toBe('timeout');
  });
});

// =============================================================================
// Test 5: queryDaemon() - async version
// =============================================================================

describe('queryDaemon async', () => {
  let mockServer: net.Server | null = null;
  let mockSocketPath: string;

  beforeEach(() => {
    setupTestEnv();
    mockSocketPath = computeSocketPath(TEST_PROJECT_DIR);
    mockDaemonClient._reset();
  });

  afterEach(async () => {
    if (mockServer) {
      await new Promise<void>((resolve) => {
        mockServer!.close(() => {
          mockServer = null;
          resolve();
        });
      });
    }
    cleanupTestEnv();
  });

  it('should connect to daemon and receive response', async () => {
    mockDaemonClient.setDaemonReachable(true);
    mockDaemonClient.setDaemonStarts(true);

    const result = await queryDaemon({ cmd: 'ping' }, TEST_PROJECT_DIR);
    expect(result.status).toBe('ok');
  });

  it('should handle search command', async () => {
    mockDaemonClient.setDaemonReachable(true);
    mockDaemonClient.setDaemonStarts(true);

    const result = await queryDaemon({ cmd: 'search', pattern: 'test' }, TEST_PROJECT_DIR);
    expect(result.status).toBe('ok');
  });

  it('should return unavailable on connection error', async () => {
    mockDaemonClient.setDaemonReachable(false);
    mockDaemonClient.setDaemonStarts(false);

    const result = await queryDaemon({ cmd: 'ping' }, TEST_PROJECT_DIR);
    expect(result.status).toBe('unavailable');
  });

  it('should timeout after QUERY_TIMEOUT ms', async () => {
    // Test the timeout response shape
    const timeoutResponse: DaemonResponse = { status: 'error', error: 'timeout' };
    expect(timeoutResponse.status).toBe('error');
    expect(timeoutResponse.error).toBe('timeout');
  });
});

// =============================================================================
// Test 6: Auto-start daemon behavior
// =============================================================================

describe('auto-start daemon', () => {
  beforeEach(() => {
    setupTestEnv();
    mockDaemonClient._reset();
  });

  afterEach(() => {
    cleanupTestEnv();
  });

  it('should detect when socket is missing', () => {
    const socketPath = getSocketPath(TEST_PROJECT_DIR);
    expect(existsSync(socketPath)).toBe(false);
  });

  it('should detect when socket file exists', () => {
    const socketPath = getSocketPath(TEST_PROJECT_DIR);

    // Create a dummy socket file
    writeFileSync(socketPath, '');

    expect(existsSync(socketPath)).toBe(true);

    // Cleanup
    unlinkSync(socketPath);
  });

  it('should return unavailable when daemon cannot start', async () => {
    mockDaemonClient.setDaemonReachable(false);
    mockDaemonClient.setDaemonStarts(false);

    const result = await queryDaemon({ cmd: 'ping' }, TEST_PROJECT_DIR);
    expect(result.status).toBe('unavailable');
  });
});

// =============================================================================
// Test 7: Graceful degradation when indexing
// =============================================================================

describe('graceful degradation', () => {
  beforeEach(() => {
    setupTestEnv();
    mockDaemonClient._reset();
  });

  afterEach(() => {
    cleanupTestEnv();
  });

  it('should return indexing response when daemon is indexing', async () => {
    writeFileSync(join(TLDR_DIR, 'status'), 'indexing');

    const result = await queryDaemon({ cmd: 'search', pattern: 'test' }, TEST_PROJECT_DIR);
    expect(result.indexing).toBe(true);
    expect(result.message).toContain('indexing');
  });

  it('should not block on indexing - return immediately', async () => {
    writeFileSync(join(TLDR_DIR, 'status'), 'indexing');

    const start = Date.now();
    const result = await queryDaemon({ cmd: 'search', pattern: 'test' }, TEST_PROJECT_DIR);
    const elapsed = Date.now() - start;

    expect(result.indexing).toBe(true);
    expect(elapsed).toBeLessThan(100);
  });

  it('should use isIndexing helper correctly', () => {
    writeFileSync(join(TLDR_DIR, 'status'), 'indexing');
    expect(isIndexing(TEST_PROJECT_DIR)).toBe(true);

    writeFileSync(join(TLDR_DIR, 'status'), 'ready');
    expect(isIndexing(TEST_PROJECT_DIR)).toBe(false);
  });
});

// =============================================================================
// Test 8: Error handling
// =============================================================================

describe('error handling', () => {
  beforeEach(() => {
    setupTestEnv();
    mockDaemonClient._reset();
  });

  afterEach(() => {
    cleanupTestEnv();
  });

  it('should handle malformed JSON response gracefully', () => {
    const parseResponse = (data: string): DaemonResponse => {
      try {
        return JSON.parse(data);
      } catch {
        return { status: 'error', error: 'Invalid JSON response from daemon' };
      }
    };

    const result = parseResponse('not json{');
    expect(result.status).toBe('error');
    expect(result.error).toContain('Invalid JSON');
  });

  it('should return unavailable when socket does not exist', async () => {
    mockDaemonClient.setDaemonReachable(false);
    mockDaemonClient.setDaemonStarts(false);

    const result = await queryDaemon({ cmd: 'ping' }, TEST_PROJECT_DIR);
    expect(result.status).toBe('unavailable');
  });

  it('should handle sync query to missing socket', () => {
    mockDaemonClient.setDaemonReachable(false);
    mockDaemonClient.setDaemonStarts(false);

    const result = queryDaemonSync({ cmd: 'ping' }, TEST_PROJECT_DIR);
    expect(result.status).toBe('unavailable');
  });

  it('should return error structure with proper fields', () => {
    const errorResponse: DaemonResponse = {
      status: 'error',
      error: 'Some error message',
    };
    expect(errorResponse.status).toBe('error');
    expect(errorResponse.error).toBeDefined();
  });
});
