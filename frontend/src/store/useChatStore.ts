import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import { STORAGE_KEYS } from '../config'
import type { ChatMessage, ChatSession } from '../types/chat'

interface ChatStoreState {
  messages: ChatMessage[]
  sessions: ChatSession[]
  currentSession: ChatSession | null
  guestSessionId: string | null
  isSending: boolean
}

interface ChatStoreActions {
  setSessions: (sessions: ChatSession[]) => void
  setCurrentSession: (session: ChatSession | null) => void
  setGuestSessionId: (id: string | null) => void
  ensureGuestSessionId: () => string
  addMessage: (message: ChatMessage) => void
  clearMessages: () => void
  replaceMessage: (id: string, message: Partial<ChatMessage>) => void
  setIsSending: (state: boolean) => void
  reset: () => void
}

export type ChatStore = ChatStoreState & ChatStoreActions

function generateMessageId() {
  if (typeof crypto !== 'undefined' && crypto.randomUUID) {
    return crypto.randomUUID()
  }
  return Math.random().toString(36).slice(2)
}

function ensureGuestSessionPersistence(id: string) {
  if (typeof window === 'undefined') return
  window.localStorage.setItem(STORAGE_KEYS.guestSession, id)
}

function hydrateGuestSession(): string | null {
  if (typeof window === 'undefined') return null
  return window.localStorage.getItem(STORAGE_KEYS.guestSession)
}

function sessionsEqual(a: ChatSession[], b: ChatSession[]) {
  if (a.length !== b.length) return false
  for (let i = 0; i < a.length; i += 1) {
    if (a[i].id !== b[i].id || a[i].updated_at !== b[i].updated_at) {
      return false
    }
  }
  return true
}

export const useChatStore = create<ChatStore>()(
  persist(
    (set, get): ChatStore => ({
      messages: [],
      sessions: [],
      currentSession: null,
      guestSessionId: hydrateGuestSession(),
      isSending: false,
      setSessions: (sessions) => {
        const sortedSessions = Array.isArray(sessions)
          ? [...sessions].sort(
              (a, b) =>
                new Date(b.created_at).getTime() -
                new Date(a.created_at).getTime(),
            )
          : []
        set((state) => {
          if (sessionsEqual(state.sessions, sortedSessions)) {
            return state
          }
          return { sessions: sortedSessions }
        })
      },
      setCurrentSession: (session) => set({ currentSession: session }),
      setGuestSessionId: (id) => {
        if (typeof window !== 'undefined') {
          if (id) {
            window.localStorage.setItem(STORAGE_KEYS.guestSession, id)
          } else {
            window.localStorage.removeItem(STORAGE_KEYS.guestSession)
          }
        }
        set({ guestSessionId: id })
      },
      ensureGuestSessionId: () => {
        const existing = get().guestSessionId ?? hydrateGuestSession()
        if (existing) {
          ensureGuestSessionPersistence(existing)
          set({ guestSessionId: existing })
          return existing
        }
        const randomId =
          typeof crypto !== 'undefined' && crypto.randomUUID
            ? crypto.randomUUID()
            : Math.random().toString(36).slice(2)
        const newId = `guest-${randomId}`
        ensureGuestSessionPersistence(newId)
        set({ guestSessionId: newId })
        return newId
      },
      addMessage: (message) =>
        set((state) => ({
          messages: [
            ...state.messages,
            { ...message, id: message.id || generateMessageId() },
          ],
        })),
      replaceMessage: (id, patch) =>
        set((state) => ({
          messages: state.messages.map((message) =>
            message.id === id ? { ...message, ...patch } : message,
          ),
        })),
      clearMessages: () => set({ messages: [] }),
      setIsSending: (state) => set({ isSending: state }),
      reset: () => {
        if (typeof window !== 'undefined') {
          window.localStorage.removeItem(STORAGE_KEYS.guestSession)
        }
        set({
          messages: [],
          currentSession: null,
          guestSessionId: null,
        })
      },
    }),
    {
      name: 'healthnavi.chat',
      partialize: (state) => ({
        guestSessionId: state.guestSessionId,
        sessions: state.sessions,
      }),
    },
  ),
)

export function useChatMessages() {
  return useChatStore((state) => state.messages)
}

export function formatChatHistory(messages: ChatMessage[]): string {
  if (!messages.length) return ''
  const pairs: string[] = []
  let lastUserMessage: string | null = null

  messages.forEach((message) => {
    if (message.author === 'user') {
      lastUserMessage = message.content
      return
    }

    if (message.author === 'assistant' && lastUserMessage) {
      pairs.push(`Doctor: ${lastUserMessage}\nModel: ${message.content}`)
      lastUserMessage = null
    }
  })

  return pairs.join('\n\n')
}

