import { create } from 'zustand'
import { createJSONStorage, persist } from 'zustand/middleware'

export const AUTH_STORAGE_KEY = 'trello-light-auth'

export interface TokenPair {
  access_token: string
  refresh_token: string
}

interface AuthState {
  /** Kept in memory only, so a page reload drops it and the session is restored via refresh. */
  accessToken: string | null
  /** Persisted to localStorage so the session survives reloads. */
  refreshToken: string | null
  setTokens: (tokens: TokenPair) => void
  clear: () => void
}

// Storage can be unavailable (private mode, blocked site data); fall back to memory-only.
const safeLocalStorage = createJSONStorage(() => ({
  getItem: (name: string) => {
    try {
      return localStorage.getItem(name)
    } catch {
      return null
    }
  },
  setItem: (name: string, value: string) => {
    try {
      localStorage.setItem(name, value)
    } catch {
      /* ignore */
    }
  },
  removeItem: (name: string) => {
    try {
      localStorage.removeItem(name)
    } catch {
      /* ignore */
    }
  },
}))

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      accessToken: null,
      refreshToken: null,
      setTokens: (tokens) => {
        set({ accessToken: tokens.access_token, refreshToken: tokens.refresh_token })
      },
      clear: () => {
        set({ accessToken: null, refreshToken: null })
      },
    }),
    {
      name: AUTH_STORAGE_KEY,
      storage: safeLocalStorage,
      partialize: (state) => ({ refreshToken: state.refreshToken }),
    },
  ),
)
