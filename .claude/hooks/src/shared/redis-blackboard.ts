/**
 * Redis pub/sub client for inter-agent messaging (blackboard pattern)
 */

import { spawn } from 'child_process';
import { promisify } from 'util';
import { readFile, writeFile } from 'fs/promises';
import { tmpdir } from 'os';
import { join } from 'path';

const execSync = promisify(require('child_process').execSync);

interface BlackboardMessage {
  type: 'request' | 'response' | 'status' | 'directive' | 'checkpoint';
  senderAgent: string;
  payload: Record<string, unknown>;
  timestamp: string;
}

interface RedisConfig {
  host: string;
  port: number;
  password?: string;
}

export class RedisBlackboard {
  private config: RedisConfig;
  private subprocess: ReturnType<typeof spawn> | null = null;
  private messageBuffer: Map<string, BlackboardMessage[]> = new Map();

  constructor(config: RedisConfig = { host: 'localhost', port: 6379 }) {
    this.config = config;
  }

  /**
   * Publish message to channel
   */
  async publish(channel: string, message: BlackboardMessage): Promise<number> {
    const cmd = [
      'redis-cli', '-h', this.config.host,
      '-p', this.config.port.toString(),
      'PUBLISH', channel, JSON.stringify(message)
    ].join(' ');

    try {
      const result = execSync(cmd, { encoding: 'utf-8' });
      return parseInt(result.trim()) || 0;
    } catch {
      console.error(`Failed to publish to ${channel}`);
      return 0;
    }
  }

  /**
   * Subscribe to channel (blocking with timeout)
   */
  async subscribe(
    channel: string,
    timeoutMs: number = 5000
  ): Promise<BlackboardMessage | null> {
    const tempFile = join(tmpdir(), `redis-sub-${Date.now()}.txt`);
    const cmd = [
      'redis-cli', '-h', this.config.host,
      '-p', this.config.port.toString(),
      'SUBSCRIBE', channel, '--pipe-timeout', (timeoutMs / 1000).toString()
    ].join(' ');

    try {
      // Use redis-cli BLPOP for simple polling
      const result = execSync(
        `timeout ${timeoutMs}s redis-cli -h ${this.config.host} -p ${this.config.port} BLPOP ${channel} 2>/dev/null || echo "timeout"`,
        { encoding: 'utf-8', timeout: timeoutMs + 1000 }
      );

      if (result && !result.includes('timeout')) {
        return JSON.parse(result);
      }
    } catch {
      console.error(`Failed to subscribe to ${channel}`);
    }

    return null;
  }

  /**
   * Post to agent inbox
   */
  async postToAgent(agentId: string, message: Omit<BlackboardMessage, 'senderAgent' | 'timestamp'>): Promise<void> {
    const fullMessage: BlackboardMessage = {
      ...message,
      senderAgent: 'system',
      timestamp: new Date().toISOString(),
    };
    await this.publish(`agent:${agentId}:inbox`, fullMessage);
  }

  /**
   * Broadcast to swarm
   */
  async broadcastToSwarm(swarmId: string, message: Omit<BlackboardMessage, 'senderAgent' | 'timestamp'>): Promise<number> {
    const fullMessage: BlackboardMessage = {
      ...message,
      senderAgent: 'system',
      timestamp: new Date().toISOString(),
    };
    return await this.publish(`swarm:${swarmId}:events`, fullMessage);
  }

  /**
   * Get messages from buffer
   */
  getMessages(channel: string): BlackboardMessage[] {
    return this.messageBuffer.get(channel) || [];
  }
}

// Channel constants
export const CHANNELS = {
  AGENT_INBOX: (id: string) => `agent:${id}:inbox`,
  SWARM_EVENTS: (id: string) => `swarm:${id}:events`,
  SESSION_HEARTBEAT: (id: string) => `session:${id}:heartbeat`,
};

export const blackboard = new RedisBlackboard();
