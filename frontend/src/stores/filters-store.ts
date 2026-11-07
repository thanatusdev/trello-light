import { create } from 'zustand'

import type { TaskFilters } from '@/features/filters/filters'

interface FiltersState {
  filters: TaskFilters
  setFilter: <K extends keyof TaskFilters>(key: K, value: TaskFilters[K] | undefined) => void
  replace: (filters: TaskFilters) => void
  clear: () => void
}

/**
 * Task filters for the board and list. The URL is the source of truth;
 * `useFilterUrlSync` keeps this store and the query string in step.
 */
export const useFiltersStore = create<FiltersState>()((set) => ({
  filters: {},
  setFilter: (key, value) => {
    set((state) => {
      const filters: TaskFilters = { ...state.filters, [key]: value }
      // Unset filters are removed rather than kept as `undefined`.
      if (value === undefined) Reflect.deleteProperty(filters, key)
      return { filters }
    })
  },
  replace: (filters) => {
    set({ filters })
  },
  clear: () => {
    set({ filters: {} })
  },
}))
