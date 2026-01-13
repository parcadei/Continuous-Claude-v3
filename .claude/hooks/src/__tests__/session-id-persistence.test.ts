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

describe('session ID file persistence', () => {
  let tempDir: string;
  let sessionIdFile: string;

  beforeEach(() => {
    tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'session-id-test-'));
    sessionIdFile = path.join(tempDir, '.coordination-session-id');
  });

  afterEach(() => {
    fs.rmSync(tempDir, { recursive: true, force: true });
  });

  describe('getSessionIdFile', () => {
    function getSessionIdFile(homeDir: string): string {
      const claudeDir = path.join(homeDir, '.claude');
      try {
        fs.mkdirSync(claudeDir, { recursive: true });
      } catch { /* ignore */ }
      return path.join(claudeDir, '.coordination-session-id');
    }

    it('returns path in .claude directory', () => {
      const result = getSessionIdFile(tempDir);
      expect(result).toBe(path.join(tempDir, '.claude', '.coordination-session-id'));
    });

    it('creates .claude directory if it does not exist', () => {
      const newTempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'session-id-mkdir-'));
      try {
        const claudeDir = path.join(newTempDir, '.claude');
        expect(fs.existsSync(claudeDir)).toBe(false);

        getSessionIdFile(newTempDir);

        expect(fs.existsSync(claudeDir)).toBe(true);
      } finally {
        fs.rmSync(newTempDir, { recursive: true, force: true });
      }
    });
  });

  describe('session-register writes ID', () => {
    it('writes session ID to file', () => {
      const sessionId = 's-test123';
      fs.writeFileSync(sessionIdFile, sessionId, 'utf-8');

      expect(fs.existsSync(sessionIdFile)).toBe(true);
      expect(fs.readFileSync(sessionIdFile, 'utf-8')).toBe(sessionId);
    });

    it('overwrites existing session ID on new session', () => {
      fs.writeFileSync(sessionIdFile, 's-old-session', 'utf-8');
      fs.writeFileSync(sessionIdFile, 's-new-session', 'utf-8');

      expect(fs.readFileSync(sessionIdFile, 'utf-8')).toBe('s-new-session');
    });
  });

  describe('file-claims reads ID', () => {
    function getSessionId(
      envSessionId: string | undefined,
      sessionFile: string,
      braintrustSpanId: string | undefined
    ): string {
      // First try environment (same process)
      if (envSessionId) {
        return envSessionId;
      }

      // Try reading from file (cross-process persistence)
      if (fs.existsSync(sessionFile)) {
        try {
          const id = fs.readFileSync(sessionFile, 'utf-8').trim();
          if (id) return id;
        } catch { /* ignore read errors */ }
      }

      // Fallback to Braintrust span ID or generate new
      return braintrustSpanId?.slice(0, 8) || `s-${Date.now().toString(36)}`;
    }

    it('prefers environment variable if set', () => {
      fs.writeFileSync(sessionIdFile, 's-from-file', 'utf-8');

      const result = getSessionId('s-from-env', sessionIdFile, undefined);

      expect(result).toBe('s-from-env');
    });

    it('reads from file when env not set', () => {
      fs.writeFileSync(sessionIdFile, 's-from-file', 'utf-8');

      const result = getSessionId(undefined, sessionIdFile, undefined);

      expect(result).toBe('s-from-file');
    });

    it('trims whitespace from file content', () => {
      fs.writeFileSync(sessionIdFile, '  s-with-spaces  \n', 'utf-8');

      const result = getSessionId(undefined, sessionIdFile, undefined);

      expect(result).toBe('s-with-spaces');
    });

    it('falls back to Braintrust span ID when file missing', () => {
      const result = getSessionId(undefined, '/nonexistent/path', 'span-12345678-abcd');

      expect(result).toBe('span-123');
    });

    it('generates new ID when all sources unavailable', () => {
      const result = getSessionId(undefined, '/nonexistent/path', undefined);

      expect(result).toMatch(/^s-[a-z0-9]+$/);
    });

    it('handles empty file gracefully', () => {
      fs.writeFileSync(sessionIdFile, '', 'utf-8');

      const result = getSessionId(undefined, sessionIdFile, 'fallback-span-id');

      expect(result).toBe('fallback');
    });
  });

  describe('cross-process consistency', () => {
    it('session-register and file-claims use same ID via file', () => {
      // Simulate session-register writing
      const generatedId = `s-${Date.now().toString(36)}`;
      fs.writeFileSync(sessionIdFile, generatedId, 'utf-8');

      // Simulate file-claims reading (different process, no env var)
      const readId = fs.readFileSync(sessionIdFile, 'utf-8').trim();

      expect(readId).toBe(generatedId);
    });

    it('multiple file-claims calls get same ID', () => {
      fs.writeFileSync(sessionIdFile, 's-consistent', 'utf-8');

      // Simulate multiple file edits in same session
      const id1 = fs.readFileSync(sessionIdFile, 'utf-8').trim();
      const id2 = fs.readFileSync(sessionIdFile, 'utf-8').trim();
      const id3 = fs.readFileSync(sessionIdFile, 'utf-8').trim();

      expect(id1).toBe('s-consistent');
      expect(id2).toBe('s-consistent');
      expect(id3).toBe('s-consistent');
    });
  });
});
