import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Loader2, Plus, Send } from 'lucide-react'
import { Alert, Button, Card, CardBody, EmptyState, ErrorState, LoadingRegion, Skeleton, Textarea } from '@/components/ui'
import { useSession } from '@/features/auth/session'
import { ApiError } from '@/lib/api'
import { createConversation, getConversation, listConversations, sendMessage } from './api'

const SUGGESTIONS = [
  'How much money did I receive this week?',
  'Show my recent transactions.',
  'Which payments are pending?',
  'Show my available invoice information.',
  'Summarise my payment activity this month.',
  'Which records need further investigation?',
]

export function AssistantPage() {
  const { me } = useSession()
  const qc = useQueryClient()
  const [activeId, setActiveId] = useState<string | null>(null)
  const [draft, setDraft] = useState('')
  const list = useQuery({ queryKey: ['assistant', 'list'], queryFn: listConversations })
  const convo = useQuery({
    queryKey: ['assistant', 'convo', activeId],
    queryFn: () => getConversation(activeId!),
    enabled: Boolean(activeId),
  })

  const start = useMutation({
    mutationFn: () => createConversation(),
    onSuccess: (c) => {
      setActiveId(c.id)
      void qc.invalidateQueries({ queryKey: ['assistant', 'list'] })
    },
  })

  const send = useMutation({
    mutationFn: async (content: string) => {
      let id = activeId
      if (!id) {
        const created = await createConversation(content.slice(0, 80))
        id = created.id
        setActiveId(id)
      }
      return sendMessage(id, content)
    },
    onSuccess: () => {
      setDraft('')
      void qc.invalidateQueries({ queryKey: ['assistant'] })
    },
  })

  const ask = (text: string) => {
    if (!text.trim() || send.isPending) return
    send.mutate(text.trim())
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[16rem_1fr]">
      <aside className="space-y-3">
        <div className="flex items-center justify-between gap-2">
          <h1 className="type-page-title lg:sr-only">Assistant</h1>
          <p className="hidden font-semibold text-ink lg:block">Conversations</p>
          <Button size="sm" variant="secondary" onClick={() => start.mutate()} loading={start.isPending} aria-label="New conversation">
            <Plus className="size-4" aria-hidden /> New
          </Button>
        </div>
        {list.isPending && <Skeleton className="h-24 w-full" />}
        {list.data?.results.length === 0 && <p className="type-helper">No conversations yet.</p>}
        <ul className="space-y-1">
          {list.data?.results.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => setActiveId(c.id)}
                className={`flex min-h-11 w-full items-center rounded-md px-3 text-left text-sm ${activeId === c.id ? 'bg-teal-soft font-semibold text-navy' : 'hover:bg-page'}`}
              >
                <span className="truncate">{c.title || 'Untitled'}</span>
              </button>
            </li>
          ))}
        </ul>
      </aside>

      <div className="space-y-4">
        <div className="hidden lg:block">
          <h1 className="type-page-title">Assistant</h1>
          <p className="type-body mt-1 text-muted">Read-only. Totals come from backend tools over your imported PayPal records.</p>
        </div>
        {me?.paypal?.state !== 'connected' && me?.paypal?.state !== 'limited' && (
          <Alert tone="warning" title="No verified PayPal records yet">
            Connect and synchronise PayPal first. The assistant will not invent activity.
          </Alert>
        )}

        <Card className="flex min-h-[28rem] flex-col">
          <CardBody className="flex flex-1 flex-col gap-4">
            {convo.isError && <ErrorState error={convo.error} onRetry={() => void convo.refetch()} />}
            {convo.isPending && activeId && (
              <LoadingRegion label="Loading conversation">
                <Skeleton className="h-24 w-full" />
              </LoadingRegion>
            )}
            {!activeId && !send.isPending && (
              <EmptyState
                title="Ask about your own records"
                description="Suggested questions stay within what the imported data can answer."
                action={
                  <div className="flex max-w-lg flex-wrap justify-center gap-2">
                    {SUGGESTIONS.map((s) => (
                      <button
                        key={s}
                        type="button"
                        onClick={() => ask(s)}
                        className="rounded-full border border-line bg-surface px-3 py-2 text-left text-sm hover:bg-page"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                }
              />
            )}
            {convo.data && (
              <ol className="flex-1 space-y-3 overflow-y-auto">
                {convo.data.messages.map((m) => (
                  <li
                    key={m.id}
                    className={`max-w-[92%] rounded-lg px-3.5 py-2.5 text-sm ${m.role === 'user' ? 'ml-auto bg-brand text-white' : 'border border-line bg-page text-ink'}`}
                  >
                    {m.role === 'assistant' && (
                      <p className="mb-1 text-xs font-semibold tracking-wide text-teal uppercase">From your synced records</p>
                    )}
                    <p className="whitespace-pre-wrap">{m.content}</p>
                    {m.role === 'assistant' && m.citations?.length > 0 && (
                      <p className="type-helper mt-2">
                        Sources: {m.citations.map((c) => c.source_id || c.id).filter(Boolean).join(', ')}
                      </p>
                    )}
                  </li>
                ))}
              </ol>
            )}
            {send.isPending && (
              <p className="flex items-center gap-2 text-sm text-muted">
                <Loader2 className="size-4 animate-spin" aria-hidden /> Retrieving records and computing totals…
              </p>
            )}
            {send.isError && <Alert tone="danger" title={send.error instanceof ApiError ? send.error.message : 'The assistant could not answer.'} />}

            <form
              className="mt-auto flex flex-col gap-2 sm:flex-row sm:items-end"
              onSubmit={(e) => {
                e.preventDefault()
                ask(draft)
              }}
            >
              <Textarea
                label="Your question"
                rows={2}
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                className="sm:flex-1"
              />
              <Button type="submit" loading={send.isPending} disabled={!draft.trim()}>
                <Send className="size-4" aria-hidden /> Send
              </Button>
            </form>
            <p className="type-helper">The assistant cannot send reminders, create invoices, move money or issue refunds.</p>
          </CardBody>
        </Card>
      </div>
    </div>
  )
}
