import type {
  HealthResponse,
  LearningsResponse,
  MemoryDetails,
  KnowledgeTree,
  RoadmapResponse,
  HandoffsResponse,
  HandoffDetail,
  Learning,
  PageIndexResponse,
} from '@/types'

const API_BASE = '/api'

class ApiError extends Error {
  status: number

  constructor(status: number, message: string) {
    super(message)
    this.status = status
    this.name = 'ApiError'
  }
}

async function fetchJson<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      'Content-Type': 'application/json',
      ...options?.headers,
    },
    ...options,
  })

  if (!response.ok) {
    throw new ApiError(response.status, `API error: ${response.statusText}`)
  }

  return response.json()
}

export async function fetchHealth(): Promise<HealthResponse> {
  return fetchJson<HealthResponse>('/health')
}

export async function fetchPillarHealth(pillar: string): Promise<HealthResponse> {
  return fetchJson<HealthResponse>(`/health/${pillar}`)
}

export async function fetchLearnings(params?: {
  page?: number
  page_size?: number
  search?: string
  type_filter?: string
}): Promise<LearningsResponse> {
  const searchParams = new URLSearchParams()
  if (params?.page) searchParams.set('page', String(params.page))
  if (params?.page_size) searchParams.set('page_size', String(params.page_size))
  if (params?.search) searchParams.set('search', params.search)
  if (params?.type_filter) searchParams.set('type_filter', params.type_filter)

  const query = searchParams.toString()
  return fetchJson<LearningsResponse>(`/pillars/memory/learnings${query ? `?${query}` : ''}`)
}

export async function fetchLearning(id: string): Promise<Learning> {
  return fetchJson<Learning>(`/pillars/memory/learnings/${encodeURIComponent(id)}`)
}

export async function fetchMemoryDetails(): Promise<MemoryDetails> {
  return fetchJson<MemoryDetails>('/pillars/memory/details')
}

export async function fetchKnowledgeTree(): Promise<KnowledgeTree> {
  return fetchJson<KnowledgeTree>('/pillars/knowledge/tree')
}

export async function fetchRoadmapGoals(): Promise<RoadmapResponse> {
  return fetchJson<RoadmapResponse>('/pillars/roadmap/goals')
}

export async function fetchHandoffs(params?: {
  page?: number
  page_size?: number
  status_filter?: string
}): Promise<HandoffsResponse> {
  const searchParams = new URLSearchParams()
  if (params?.page) searchParams.set('page', String(params.page))
  if (params?.page_size) searchParams.set('page_size', String(params.page_size))
  if (params?.status_filter) searchParams.set('status_filter', params.status_filter)

  const query = searchParams.toString()
  return fetchJson<HandoffsResponse>(`/pillars/handoffs${query ? `?${query}` : ''}`)
}

export async function fetchHandoff(id: string): Promise<HandoffDetail> {
  return fetchJson<HandoffDetail>(`/pillars/handoffs/${encodeURIComponent(id)}`)
}

export async function fetchPageIndexDocuments(params?: {
  page?: number
  page_size?: number
  search?: string
}): Promise<PageIndexResponse> {
  const searchParams = new URLSearchParams()
  if (params?.page) searchParams.set('page', String(params.page))
  if (params?.page_size) searchParams.set('page_size', String(params.page_size))
  if (params?.search) searchParams.set('search', params.search)

  const query = searchParams.toString()
  return fetchJson<PageIndexResponse>(`/pillars/pageindex/documents${query ? `?${query}` : ''}`)
}

export { ApiError }
