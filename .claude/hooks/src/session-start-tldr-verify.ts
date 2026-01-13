#!/usr/bin/env node
/**
 * SessionStart Hook: Verify tldr-code is working
 *
 * Checks if /usr/local/bin/tldr exists and is the llm-tldr binary.
 * Silent on success, verbose warning on failure.
 */

import { execSync } from 'child_process';
import * as fs from 'fs';
import * as path from 'path';

interface VerificationResult {
  available: boolean;
  path: string | null;
  verified: boolean;
  error: string | null;
}

function verifyTldr(): VerificationResult {
  const tldrPath = '/usr/local/bin/tldr';

  // Check if tldr exists
  if (!fs.existsSync(tldrPath)) {
    return {
      available: false,
      path: null,
      verified: false,
      error: null // Silent if not installed
    };
  }

  // Check if it's a symlink or file
  try {
    const stats = fs.lstatSync(tldrPath);
    const realPath = fs.existsSync(tldrPath) ? fs.realpathSync(tldrPath) : tldrPath;

    // Verify it's the llm-tldr binary by checking --help output
    try {
      const helpOutput = execSync(`"${tldrPath}" --help 2>&1`, { encoding: 'utf-8', timeout: 5000 });

      if (helpOutput.includes('Token-efficient code analysis')) {
        return {
          available: true,
          path: realPath,
          verified: true,
          error: null
        };
      } else {
        return {
          available: true,
          path: realPath,
          verified: false,
          error: '/usr/local/bin/tldr is not llm-tldr (missing "Token-efficient code analysis" in --help)'
        };
      }
    } catch (execError: unknown) {
      // --help might exit with non-zero, but we can still check output
      const error = execError instanceof Error ? execError.message : String(execError);
      return {
        available: true,
        path: realPath,
        verified: false,
        error: `Failed to run tldr --help: ${error}`
      };
    }
  } catch (fsError) {
    return {
      available: true,
      path: tldrPath,
      verified: false,
      error: `Failed to access ${tldrPath}: ${fsError instanceof Error ? fsError.message : String(fsError)}`
    };
  }
}

function main() {
  const result = verifyTldr();

  // Silent on success
  if (result.available && result.verified && !result.error) {
    process.exit(0);
  }

  // Output warnings for failures (verbose mode)
  const verbose = process.env.VERBOSE === '1' || process.argv.includes('--verbose');

  if (!result.available) {
    if (verbose) {
      console.error('[tldr-code] Not installed (no /usr/local/bin/tldr)');
    }
    process.exit(0); // Don't fail session
  }

  if (!result.verified) {
    console.error(`[tldr-code] Warning: ${result.error}`);
    process.exit(0); // Don't fail session, just warn
  }

  process.exit(0);
}

main();
