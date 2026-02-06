export type PillarStatus = 'online' | 'offline' | 'degraded' | 'unknown'

export interface PillarHealth {
  name: string
  status: PillarStatus
  count: number
  last_activity: string | null
  error: string | null
  details?: Record<string, unknown>
}

export interface HealthResponse {
  pillars: Record<string, PillarHealth>
  timestamp?: string
}

export interface Learning {
  id: string
  session_id: string
  type: string
  content: string
  context: string | null
  tags: string[] | null
  confidence: string
  created_at: string
  metadata: Record<string, unknown>
}

export interface LearningsResponse {
  learnings: Learning[]
  total: number
  page: number
  page_size: number
}

export interface MemoryDetails {
  total_count: number
  by_type: Record<string, number>
  by_scope: Record<string, number>
  recent: Learning[]
}

export interface KnowledgeTree {
  project?: {
    name: string
    description: string
    type: string
  }
  structure?: {
    root: string
    directories: Record<string, string>
  }
  stack?: Record<string, unknown>
  goals?: unknown[]
  [key: string]: unknown
}

export interface RoadmapGoal {
  id: string
  text: string
  completed: boolean
  section: string
}

export interface RoadmapResponse {
  goals: RoadmapGoal[]
  completed: number
  total: number
  completion_rate: number
}

export interface HandoffSummary {
  id: string
  title: string
  source: 'db' | 'file'
  status: string | null
  created_at: string | null
}

export interface HandoffDetail extends HandoffSummary {
  content: string
  metadata?: Record<string, unknown>
}

export interface HandoffsResponse {
  handoffs: HandoffSummary[]
  total: number
  page: number
  page_size: number
}

export interface IndexedDocument {
  id: string
  file_path: string
  status: 'indexed' | 'pending' | 'failed'
  indexed_at: string | null
  language: string
  error?: string
}

export interface PageIndexResponse {
  documents: IndexedDocument[]
  total: number
  page: number
  page_size: number
}

export type WebSocketEventType = 'health_update' | 'activity' | 'notification'

export interface HealthUpdateEvent {
  type: 'health_update'
  pillars: Record<string, PillarHealth>
  changed: string[]
  timestamp: string
}

export interface ActivityEvent {
  type: 'activity'
  pillar: string
  action: string
  details: Record<string, unknown>
  timestamp: string
}

export interface NotificationEvent {
  type: 'notification'
  level: 'info' | 'warning' | 'error'
  message: string
  timestamp: string
}

export type WebSocketEvent = HealthUpdateEvent | ActivityEvent | NotificationEvent

export interface WebSocketMessage {
  action: 'subscribe' | 'unsubscribe'
  project: string
}
