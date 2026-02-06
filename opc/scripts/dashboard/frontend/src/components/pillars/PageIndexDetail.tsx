import { useState, useEffect, useMemo } from 'react'
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from '@/components/ui/sheet'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { ScrollArea } from '@/components/ui/scroll-area'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/components/ui/tooltip'
import { cn } from '@/lib/utils'
import { fetchPageIndexDocuments } from '@/lib/api'
import type { IndexedDocument } from '@/types'

type IndexStatus = 'indexed' | 'pending' | 'failed'

interface PageIndexDetailProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

const STATUS_CONFIG: Record<IndexStatus, { label: string; variant: string; icon: string }> = {
  indexed: {
    label: 'Indexed',
    variant: 'bg-online/15 text-online border-online/30',
    icon: '●',
  },
  pending: {
    label: 'Pending',
    variant: 'bg-degraded/15 text-degraded border-degraded/30',
    icon: '◐',
  },
  failed: {
    label: 'Failed',
    variant: 'bg-offline/15 text-offline border-offline/30',
    icon: '○',
  },
}

function formatTimeAgo(dateStr: string | null): string {
  if (!dateStr) return 'Never'

  const date = new Date(dateStr)
  const now = new Date()
  const diffMs = now.getTime() - date.getTime()
  const diffMins = Math.floor(diffMs / 60000)
  const diffHours = Math.floor(diffMins / 60)
  const diffDays = Math.floor(diffHours / 24)

  if (diffMins < 1) return 'Just now'
  if (diffMins < 60) return `${diffMins}m ago`
  if (diffHours < 24) return `${diffHours}h ago`
  if (diffDays < 7) return `${diffDays}d ago`
  return date.toLocaleDateString()
}

function getLanguageColor(language: string): string {
  const colors: Record<string, string> = {
    typescript: 'text-blue-400',
    javascript: 'text-yellow-400',
    python: 'text-green-400',
    markdown: 'text-gray-400',
    yaml: 'text-purple-400',
    json: 'text-orange-400',
    text: 'text-muted-foreground',
  }
  return colors[language] || 'text-muted-foreground'
}

export function PageIndexDetail({ open, onOpenChange }: PageIndexDetailProps) {
  const [documents, setDocuments] = useState<IndexedDocument[]>([])
  const [total, setTotal] = useState(0)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<IndexStatus | 'all'>('all')

  useEffect(() => {
    if (!open) return

    let cancelled = false
    setLoading(true)
    setError(null)

    fetchPageIndexDocuments({ page: 1, page_size: 100, search: searchQuery || undefined })
      .then((data) => {
        if (cancelled) return
        setDocuments(data.documents)
        setTotal(data.total)
      })
      .catch((err) => {
        if (cancelled) return
        setError(err.message || 'Failed to load documents')
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })

    return () => { cancelled = true }
  }, [open, searchQuery])

  const filteredDocuments = useMemo(() => {
    return documents.filter((doc) => {
      const matchesStatus = statusFilter === 'all' || doc.status === statusFilter
      return matchesStatus
    })
  }, [documents, statusFilter])

  const stats = useMemo(() => {
    return {
      indexed: documents.filter((d) => d.status === 'indexed').length,
      pending: documents.filter((d) => d.status === 'pending').length,
      failed: documents.filter((d) => d.status === 'failed').length,
      total: total,
    }
  }, [documents, total])

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full sm:max-w-lg">
        <SheetHeader>
          <SheetTitle className="flex items-center gap-2">
            <svg className="h-5 w-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={1.5}
                d="M4 6h16M4 10h16M4 14h16M4 18h16"
              />
            </svg>
            PageIndex Documents
          </SheetTitle>
          <SheetDescription>View and manage indexed documents</SheetDescription>
        </SheetHeader>

        <div className="mt-4 space-y-4">
          <div className="grid grid-cols-3 gap-2">
            <div className="rounded-lg bg-online/10 p-2 text-center">
              <div className="text-lg font-bold text-online">{stats.indexed}</div>
              <div className="text-xs text-muted-foreground">Indexed</div>
            </div>
            <div className="rounded-lg bg-degraded/10 p-2 text-center">
              <div className="text-lg font-bold text-degraded">{stats.pending}</div>
              <div className="text-xs text-muted-foreground">Pending</div>
            </div>
            <div className="rounded-lg bg-offline/10 p-2 text-center">
              <div className="text-lg font-bold text-offline">{stats.failed}</div>
              <div className="text-xs text-muted-foreground">Failed</div>
            </div>
          </div>

          <div className="flex gap-2">
            <div className="relative flex-1">
              <svg
                className="absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                />
              </svg>
              <Input
                placeholder="Filter by path..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-8"
              />
            </div>
          </div>

          <div className="flex gap-1">
            <Button
              variant={statusFilter === 'all' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setStatusFilter('all')}
              className="text-xs"
            >
              All ({stats.total})
            </Button>
            <Button
              variant={statusFilter === 'indexed' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setStatusFilter('indexed')}
              className="text-xs"
            >
              Indexed
            </Button>
            <Button
              variant={statusFilter === 'pending' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setStatusFilter('pending')}
              className="text-xs"
            >
              Pending
            </Button>
            <Button
              variant={statusFilter === 'failed' ? 'default' : 'outline'}
              size="sm"
              onClick={() => setStatusFilter('failed')}
              className="text-xs"
            >
              Failed
            </Button>
          </div>
        </div>

        <ScrollArea className="mt-4 h-[calc(100vh-320px)]">
          <TooltipProvider>
            <div className="space-y-2 pr-4">
              {loading ? (
                <div className="py-8 text-center text-muted-foreground">
                  <p className="text-sm">Loading documents...</p>
                </div>
              ) : error ? (
                <div className="py-8 text-center text-muted-foreground">
                  <p className="text-sm text-offline">{error}</p>
                </div>
              ) : filteredDocuments.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground">
                  <svg
                    className="mx-auto h-12 w-12 text-muted-foreground/50"
                    fill="none"
                    stroke="currentColor"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={1}
                      d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                    />
                  </svg>
                  <p className="mt-2 text-sm">No documents found</p>
                  <p className="text-xs">Try adjusting your filters</p>
                </div>
              ) : (
                filteredDocuments.map((doc) => (
                  <DocumentRow key={doc.id} document={doc} />
                ))
              )}
            </div>
          </TooltipProvider>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  )
}

function DocumentRow({ document }: { document: IndexedDocument }) {
  const statusConfig = STATUS_CONFIG[document.status]

  return (
    <div
      className={cn(
        'rounded-lg border p-3 transition-colors',
        document.status === 'failed' && 'border-offline/30 bg-offline/5',
        document.status === 'pending' && 'border-degraded/30 bg-degraded/5',
        document.status === 'indexed' && 'hover:bg-muted/50'
      )}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <code className="truncate font-mono text-sm">{document.file_path}</code>
            {document.error && (
              <Tooltip>
                <TooltipTrigger asChild>
                  <button className="shrink-0 text-offline hover:text-offline/80">
                    <svg className="h-4 w-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        strokeWidth={2}
                        d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z"
                      />
                    </svg>
                  </button>
                </TooltipTrigger>
                <TooltipContent side="left" className="max-w-xs">
                  <p>{document.error}</p>
                </TooltipContent>
              </Tooltip>
            )}
          </div>
          <div className="mt-1 flex items-center gap-3 text-xs text-muted-foreground">
            <span className={getLanguageColor(document.language)}>{document.language}</span>
            <span>{formatTimeAgo(document.indexed_at)}</span>
          </div>
        </div>
        <Badge variant="outline" className={cn('shrink-0 text-xs', statusConfig.variant)}>
          <span className="mr-1">{statusConfig.icon}</span>
          {statusConfig.label}
        </Badge>
      </div>
    </div>
  )
}
