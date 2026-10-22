import { ApiError, request } from '@/lib/http'
import { env } from '@/lib/env'
import { supabase } from '@/lib/supabase'

export type Citation = {
  citation_index: number
  document_chunk_id: string
  excerpt: string
  ticker: string
  company_name: string
  filing_type: string
  filing_date: string
  page_number: number | null
  section: string | null
  source_url: string
}

export type MessagePart =
  | { type: 'text'; text: string }
  | { type: 'data-citations'; data: Citation[] }

export type ChatMessage = {
  id: string
  role: 'user' | 'assistant'
  parts: MessagePart[]
  createdAt?: string
}

export function parseCitations(value: unknown): Citation[] {
  if (!Array.isArray(value)) return []
  return value.filter((item): item is Citation => {
    if (typeof item !== 'object' || item === null) return false
    const citation = item as Record<string, unknown>
    return Number.isInteger(citation.citation_index) && (citation.citation_index as number) > 0
      && typeof citation.document_chunk_id === 'string'
      && typeof citation.excerpt === 'string' && citation.excerpt.trim().length > 0
      && typeof citation.ticker === 'string'
      && typeof citation.company_name === 'string'
      && typeof citation.filing_type === 'string'
      && typeof citation.filing_date === 'string'
      && (typeof citation.page_number === 'number' || citation.page_number === null)
      && (typeof citation.section === 'string' || citation.section === null)
      && typeof citation.source_url === 'string'
  })
}

export type ChatThread = {
  id: string
  title: string | null
  created_at: string
  updated_at: string
}

export const api = {
  get: <T>(path: string) => request<T>('GET', path),
  post: <T>(path: string, body?: unknown) => request<T>('POST', path, body),
  put: <T>(path: string, body?: unknown) => request<T>('PUT', path, body),
  patch: <T>(path: string, body?: unknown) => request<T>('PATCH', path, body),
  delete: <T>(path: string) => request<T>('DELETE', path),
  streamChat: async (
    threadId: string,
    messages: ChatMessage[],
    onText: (text: string) => void,
    onCitations: (citations: Citation[]) => void,
  ) => {
    const { data, error } = await supabase.auth.getSession()
    if (error || !data.session?.access_token) {
      throw new ApiError('Your session has expired. Please sign in again.', 401, false)
    }

    let response: Response
    try {
      response = await fetch(`${env.apiBaseUrl}/chat/stream`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${data.session.access_token}`,
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({ threadId, messages }),
      })
    } catch {
      throw new ApiError('Unable to reach the chat service. Check your connection and try again.', null, true)
    }
    if (!response.ok || !response.body) {
      const result: unknown = await response.json().catch(() => undefined)
      const detail = typeof result === 'object' && result !== null && 'detail' in result
        ? result.detail
        : undefined
      throw new ApiError(
        typeof detail === 'string' ? detail : `Chat request failed (${response.status})`,
        response.status,
        false,
      )
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    let receivedDone = false
    try {
      while (true) {
        const { done, value } = await reader.read()
        buffer += decoder.decode(value, { stream: !done })
        const events = buffer.split('\n\n')
        buffer = events.pop() ?? ''
        for (const event of events) {
          const line = event.split('\n').find((part) => part.startsWith('data: '))
          if (!line) continue
          if (line === 'data: [DONE]') {
            receivedDone = true
            continue
          }
          let payload: { type?: string; delta?: unknown; errorText?: unknown; data?: unknown }
          try {
            payload = JSON.parse(line.slice(6)) as typeof payload
          } catch {
            throw new ApiError('The chat service returned an unreadable response.', null, false)
          }
          if (payload.type === 'text-delta' && typeof payload.delta === 'string') onText(payload.delta)
          if (payload.type === 'data-citations') onCitations(parseCitations(payload.data))
          if (payload.type === 'error') {
            throw new ApiError(
              typeof payload.errorText === 'string' ? payload.errorText : 'Unable to save this response.',
              500,
              false,
            )
          }
        }
        if (done) break
      }
    } catch (error) {
      if (error instanceof ApiError) throw error
      throw new ApiError('The chat connection was interrupted. Please try again.', null, true)
    }
    if (!receivedDone) {
      throw new ApiError('The chat connection ended before the response was complete.', null, true)
    }
  },
}
