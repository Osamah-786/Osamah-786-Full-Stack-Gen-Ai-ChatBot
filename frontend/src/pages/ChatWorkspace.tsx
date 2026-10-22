import { useEffect, useRef, useState, type FormEvent, type KeyboardEvent } from 'react'
import { NavLink, useNavigate, useParams } from 'react-router-dom'

import { api, parseCitations, type ChatMessage, type ChatThread, type Citation } from '@/lib/api'
import { ApiError } from '@/lib/http'
import { supabase } from '@/lib/supabase'
import applicationIcon from '@/assets/icons/application.png'
import messageIcon from '@/assets/icons/message.png'
import searchIcon from '@/assets/icons/search.png'
import textAnalyticsIcon from '@/assets/icons/text-analytics.png'
import userIcon from '@/assets/icons/user.png'
import verifiedIcon from '@/assets/icons/verified.png'
import linkIcon from '@/assets/icons/link.png'
import fileIcon from '@/assets/icons/file.png'

function chatErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) return 'Your session expired. Sign in again to continue.'
    if (error.status === 502) return 'The answer could not be verified against the filings. Please try again.'
    if (error.status === 503) return 'Document search is temporarily unavailable. Please try again.'
    if (error.status === 500) return 'The response could not be saved to chat history. Please try again.'
    if (error.isNetworkError) return 'Unable to reach the chat service. Check your connection or API CORS settings.'
  }
  return error instanceof Error ? error.message : 'The chat request failed. Please try again.'
}

function messageText(message: ChatMessage): string {
  return message.parts.filter((part) => part.type === 'text').map((part) => part.text).join('')
}

function messageCitations(message: ChatMessage): Citation[] {
  return message.parts.flatMap((part) => part.type === 'data-citations' ? parseCitations(part.data) : [])
}

function safeSourceUrl(value: string): string | null {
  try {
    const url = new URL(value)
    return url.protocol === 'https:' && (url.hostname === 'sec.gov' || url.hostname.endsWith('.sec.gov'))
      ? url.href
      : null
  } catch {
    return null
  }
}

function citationLabel(citation: Citation): string {
  const filing = `${citation.company_name || citation.ticker} · ${citation.filing_type} · ${citation.filing_date}`
  const location = citation.page_number !== null
    ? `p. ${citation.page_number}`
    : citation.section
  return `[${citation.citation_index}] ${filing}${location ? ` · ${location}` : ''}`
}

function renderAnswer(
  text: string,
  citations: Map<number, Citation>,
  onSelect: (citation: Citation, button: HTMLButtonElement) => void,
  selectedId: string | null,
) {
  return text.split(/(\[\d+\])/g).map((segment, index) => {
    const marker = /^\[(\d+)\]$/.exec(segment)
    if (!marker) return <span key={index}>{segment}</span>
    const citation = citations.get(Number(marker[1]))
    if (!citation) return <span key={index} className="citation-unavailable" title="Source details are unavailable">{segment}</span>
    return (
      <button
        key={index}
        type="button"
        className="inline-citation"
        aria-label={`Open source: ${citationLabel(citation)}`}
        aria-expanded={selectedId === citation.document_chunk_id}
        title={citationLabel(citation)}
        onClick={(event) => onSelect(citation, event.currentTarget)}
      >
        {segment}
      </button>
    )
  })
}

function MessageItem({
  message,
  isStreaming,
  selectedCitationId,
  onSelectCitation,
}: {
  message: ChatMessage
  isStreaming: boolean
  selectedCitationId: string | null
  onSelectCitation: (citation: Citation, button: HTMLButtonElement) => void
}) {
  const text = messageText(message)
  const citations = message.role === 'assistant' ? messageCitations(message) : []
  const citationsByIndex = new Map(citations.map((citation) => [citation.citation_index, citation]))
  const noEvidence = message.role === 'assistant'
    && citations.length === 0
    && /not enough evidence|insufficient evidence/i.test(text)

  return (
    <article className={`message-row ${message.role}`}>
      <div className="message-bubble">
        {text && <p className="chat-answer">{renderAnswer(text, citationsByIndex, onSelectCitation, selectedCitationId)}</p>}
        {citations.length > 0 && (
          <div className="citation-list" aria-label="Answer sources">
            {citations.map((citation) => (
              <button
                key={`${message.id}-${citation.citation_index}`}
                type="button"
                className="citation-chip"
                aria-expanded={selectedCitationId === citation.document_chunk_id}
                onClick={(event) => onSelectCitation(citation, event.currentTarget)}
              >
                {citationLabel(citation)}
              </button>
            ))}
          </div>
        )}
        {noEvidence && <p className="evidence-note">No supporting filing passage was found for this question.</p>}
        {message.role === 'assistant' && isStreaming && !text && (
          <span className="typing-indicator" aria-label="Assistant is responding"><i /><i /><i /></span>
        )}
      </div>
    </article>
  )
}

function ChatWorkspace() {
  const { threadId } = useParams()
  const navigate = useNavigate()
  const [threads, setThreads] = useState<ChatThread[]>([])
  const [threadsError, setThreadsError] = useState('')
  const [isLoadingThreads, setIsLoadingThreads] = useState(true)
  const [email, setEmail] = useState('')
  const [isSidebarOpen, setIsSidebarOpen] = useState(false)
  const menuButtonRef = useRef<HTMLButtonElement>(null)
  const drawerCloseRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    if (!isSidebarOpen) return
    drawerCloseRef.current?.focus()
    function closeOnEscape(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') {
        closeSidebar()
      }
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [isSidebarOpen])

  function closeSidebar() {
    setIsSidebarOpen(false)
    requestAnimationFrame(() => menuButtonRef.current?.focus())
  }

  function keepSidebarFocus(event: KeyboardEvent<HTMLElement>) {
    if (!isSidebarOpen || event.key !== 'Tab') return
    const focusable = event.currentTarget.querySelectorAll<HTMLElement>(
      'a[href], button:not(:disabled)',
    )
    const first = focusable[0]
    const last = focusable[focusable.length - 1]
    if (!first || !last) return
    if (event.shiftKey && document.activeElement === first) {
      event.preventDefault()
      last.focus()
    } else if (!event.shiftKey && document.activeElement === last) {
      event.preventDefault()
      first.focus()
    }
  }

  async function loadThreads() {
    setThreadsError('')
    setIsLoadingThreads(true)
    try {
      setThreads(await api.get<ChatThread[]>('/chat/threads'))
    } catch (cause) {
      setThreadsError(chatErrorMessage(cause))
    } finally {
      setIsLoadingThreads(false)
    }
  }

  useEffect(() => {
    let cancelled = false
    void api.get<ChatThread[]>('/chat/threads')
      .then((items) => { if (!cancelled) setThreads(items) })
      .catch((cause: unknown) => {
        if (!cancelled) setThreadsError(chatErrorMessage(cause))
      })
      .finally(() => { if (!cancelled) setIsLoadingThreads(false) })
    void supabase.auth.getUser().then(({ data }) => setEmail(data.user?.email ?? ''))
    return () => { cancelled = true }
  }, [])

  async function createThread() {
    try {
      const thread = await api.post<ChatThread>('/chat/threads')
      await loadThreads()
      navigate(`/chat/${thread.id}`)
      closeSidebar()
    } catch (cause) {
      setThreadsError(chatErrorMessage(cause))
    }
  }

  async function signOut() {
    await supabase.auth.signOut()
    navigate('/signin', { replace: true })
  }

  return (
    <main className="chat-shell">
      {isSidebarOpen && (
        <button className="sidebar-backdrop" type="button" aria-label="Close conversations" onClick={closeSidebar} />
      )}
      <aside
        id="chat-sidebar"
        className={`chat-sidebar${isSidebarOpen ? ' is-open' : ''}`}
        aria-label="Conversations"
        role={isSidebarOpen ? 'dialog' : undefined}
        aria-modal={isSidebarOpen || undefined}
        onKeyDown={keepSidebarFocus}
      >
        <div className="sidebar-heading">
          <div className="sidebar-brand-row">
            <span className="workspace-brand"><img src={applicationIcon} alt="" />Document Copilot</span>
            <button ref={drawerCloseRef} className="drawer-close-button" type="button" aria-label="Close conversations" onClick={closeSidebar}>×</button>
          </div>
          <span className="workspace-caption">SEC filing assistant</span>
        </div>
        <button className="new-chat-button" onClick={() => void createThread()}>
          <span aria-hidden="true">＋</span> New chat
        </button>
        <div className="conversation-heading">Conversations</div>
        <nav className="thread-list" aria-label="Past conversations">
          {isLoadingThreads && <p className="sidebar-message">Loading conversations…</p>}
          {!isLoadingThreads && threads.length === 0 && (
            <p className="sidebar-message">No conversations yet.</p>
          )}
          {threads.map((thread) => (
            <NavLink
              key={thread.id}
              to={`/chat/${thread.id}`}
              className={({ isActive }) => `thread-link${isActive ? ' active' : ''}`}
              title={thread.title ?? 'New conversation'}
              onClick={closeSidebar}
            >
              <span className="thread-icon"><img src={messageIcon} alt="" /></span>
              <span>{thread.title || 'New conversation'}</span>
            </NavLink>
          ))}
          {threadsError && (
            <div className="sidebar-error" role="alert">
              <p>{threadsError}</p>
              {threadsError.startsWith('Your session expired')
                ? <button type="button" onClick={() => navigate('/signin', { replace: true })}>Sign in again</button>
                : <button type="button" onClick={() => void loadThreads()}>Retry</button>}
            </div>
          )}
        </nav>
        <div className="sidebar-account">
          <span className="account-avatar" aria-hidden="true"><img src={userIcon} alt="" /></span>
          <span className="account-email" title={email}>{email || 'Signed in'}</span>
          <button className="signout-button" onClick={() => void signOut()}>Sign out</button>
        </div>
      </aside>

      <section className="chat-main" aria-label="Chat">
        <header className="workspace-topbar">
          <button
            ref={menuButtonRef}
            className="mobile-menu-button"
            type="button"
            aria-label="Open conversations"
            aria-controls="chat-sidebar"
            aria-expanded={isSidebarOpen}
            onClick={() => setIsSidebarOpen(true)}
          >
            <span aria-hidden="true">☰</span>
          </button>
          <span className="topbar-label">SEC filing research</span>
        </header>
        {threadId ? (
          <ThreadChat key={threadId} threadId={threadId} onThreadUpdate={loadThreads} />
        ) : (
          <div className="empty-chat">
            <img className="empty-illustration" src={textAnalyticsIcon} alt="" />
            <p className="eyebrow">Research workspace</p>
            <h1>Start with the filing</h1>
            <p>Ask a question about SEC filings, then inspect the cited passage behind the answer.</p>
            <div className="empty-proof-points">
              <span><img src={fileIcon} alt="" />SEC filing corpus</span>
              <span><img src={verifiedIcon} alt="" />Review source evidence</span>
            </div>
          </div>
        )}
      </section>
    </main>
  )
}

function ThreadChat({ threadId, onThreadUpdate }: { threadId: string; onThreadUpdate: () => Promise<void> }) {
  const navigate = useNavigate()
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [isLoading, setIsLoading] = useState(true)
  const [isStreaming, setIsStreaming] = useState(false)
  const [error, setError] = useState('')
  const [historyAttempt, setHistoryAttempt] = useState(0)
  const [selectedCitation, setSelectedCitation] = useState<Citation | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)
  const citationTriggerRef = useRef<HTMLButtonElement | null>(null)
  const panelCloseRef = useRef<HTMLButtonElement>(null)

  useEffect(() => {
    let cancelled = false
    void api.get<ChatMessage[]>(`/chat/threads/${threadId}/messages`)
      .then((history) => { if (!cancelled) setMessages(history) })
      .catch((cause: unknown) => {
        if (!cancelled) setError(chatErrorMessage(cause))
      })
      .finally(() => { if (!cancelled) setIsLoading(false) })
    return () => { cancelled = true }
  }, [threadId, historyAttempt])

  useEffect(() => {
    if (!selectedCitation) return
    panelCloseRef.current?.focus()
    function closeOnEscape(event: globalThis.KeyboardEvent) {
      if (event.key === 'Escape') {
        setSelectedCitation(null)
        requestAnimationFrame(() => citationTriggerRef.current?.focus())
      }
    }
    window.addEventListener('keydown', closeOnEscape)
    return () => window.removeEventListener('keydown', closeOnEscape)
  }, [selectedCitation])

  useEffect(() => bottomRef.current?.scrollIntoView({ behavior: 'smooth' }), [messages])

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const text = input.trim()
    if (!text || isStreaming) return

    const userMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      parts: [{ type: 'text', text }],
    }
    const assistantMessage: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'assistant',
      parts: [{ type: 'text', text: '' }],
    }
    const nextMessages = [...messages, userMessage]
    setMessages([...nextMessages, assistantMessage])
    setInput('')
    setError('')
    setSelectedCitation(null)
    setIsStreaming(true)

    try {
      await api.streamChat(threadId, nextMessages, (delta) => {
        setMessages((current) => current.map((message) =>
          message.id === assistantMessage.id
            ? {
                ...message,
                parts: [
                  { type: 'text', text: `${messageText(message)}${delta}` },
                  ...message.parts.filter((part) => part.type === 'data-citations'),
                ],
              }
            : message,
        ))
      }, (citations) => {
        setMessages((current) => current.map((message) => message.id === assistantMessage.id
          ? {
              ...message,
              parts: [
                { type: 'text', text: messageText(message) },
                { type: 'data-citations', data: citations },
              ],
            }
          : message,
        ))
      })
      const history = await api.get<ChatMessage[]>(`/chat/threads/${threadId}/messages`)
      setMessages(history)
      await onThreadUpdate()
    } catch (cause) {
      setError(chatErrorMessage(cause))
    } finally {
      setIsStreaming(false)
    }
  }

  function handleInputKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === 'Enter' && !event.shiftKey) {
      event.preventDefault()
      event.currentTarget.form?.requestSubmit()
    }
  }

  function openCitation(citation: Citation, button: HTMLButtonElement) {
    citationTriggerRef.current = button
    setSelectedCitation(citation)
  }

  function closeCitationPanel() {
    setSelectedCitation(null)
    requestAnimationFrame(() => citationTriggerRef.current?.focus())
  }

  function retryHistory() {
    setError('')
    setIsLoading(true)
    setHistoryAttempt((attempt) => attempt + 1)
  }

  return (
    <div className={`thread-layout${selectedCitation ? ' has-source' : ''}`}>
      <div className="thread-chat">
        <div className="message-list" aria-live="polite">
          {isLoading && <p className="chat-status" role="status">Loading conversation…</p>}
          {!isLoading && messages.length === 0 && !error && (
            <div className="thread-empty">
              <img className="thread-empty-icon" src={searchIcon} alt="" />
              <p className="eyebrow">New research thread</p>
              <h1>What should we examine?</h1>
              <p>Ask about a company, filing, or financial trend. Answers include source passages when evidence is available.</p>
            </div>
          )}
          {messages.map((message) => (
            <MessageItem
              key={message.id}
              message={message}
              isStreaming={isStreaming}
              selectedCitationId={selectedCitation?.document_chunk_id ?? null}
              onSelectCitation={openCitation}
            />
          ))}
          {isStreaming && messages.at(-1)?.role === 'assistant' && messageText(messages.at(-1)!) && (
            <p className="streaming-label">Writing response…</p>
          )}
          {error && (
            <div className="chat-error" role="alert">
              <p>{error}</p>
              {error.startsWith('Your session expired') && (
                <button type="button" onClick={() => navigate('/signin', { replace: true })}>Sign in again</button>
              )}
              {!isLoading && messages.length === 0 && (
                <button type="button" onClick={retryHistory}>Retry loading conversation</button>
              )}
            </div>
          )}
          <div ref={bottomRef} />
        </div>
        <form className="composer" onSubmit={(event) => void sendMessage(event)}>
          <textarea
            aria-label="Message"
            placeholder="Ask a question about SEC filings…"
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleInputKeyDown}
            rows={1}
            disabled={isLoading || isStreaming}
          />
          <button type="submit" disabled={!input.trim() || isLoading || isStreaming} aria-label="Send message">
            {isStreaming ? <span className="send-spinner" /> : '↑'}
          </button>
          <p>Document Copilot can make mistakes. Verify important information against the filing.</p>
        </form>
      </div>
      {selectedCitation && (
        <>
        <button className="source-backdrop" type="button" aria-label="Close source passage" onClick={closeCitationPanel} />
        <aside className="source-panel" aria-labelledby="source-panel-title">
          <div className="source-panel-heading">
            <h2 id="source-panel-title" tabIndex={-1}><img src={verifiedIcon} alt="" />Source passage</h2>
            <button ref={panelCloseRef} type="button" onClick={closeCitationPanel} aria-label="Close source passage">×</button>
          </div>
          <p className="source-company">{selectedCitation.company_name || selectedCitation.ticker} ({selectedCitation.ticker})</p>
          <dl className="source-metadata">
            <div><dt>Filing</dt><dd>{selectedCitation.filing_type}</dd></div>
            <div><dt>Date</dt><dd>{selectedCitation.filing_date}</dd></div>
            {selectedCitation.page_number !== null && <div><dt>Page</dt><dd>{selectedCitation.page_number}</dd></div>}
            {selectedCitation.section && <div><dt>Section</dt><dd>{selectedCitation.section}</dd></div>}
          </dl>
          <blockquote className="source-excerpt">“{selectedCitation.excerpt}”</blockquote>
          {safeSourceUrl(selectedCitation.source_url) ? (
            <a href={safeSourceUrl(selectedCitation.source_url)!} target="_blank" rel="noopener noreferrer">
              <img src={linkIcon} alt="" />Open SEC filing
            </a>
          ) : <p className="source-unavailable">Source link is unavailable.</p>}
        </aside>
        </>
      )}
    </div>
  )
}

export default ChatWorkspace
