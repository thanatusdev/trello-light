import { useEffect, useMemo, useRef } from 'react'
import { useSearchParams } from 'react-router'

import { applyFilters, filtersKey, parseFilters } from '@/features/filters/filters'
import { useFiltersStore } from '@/stores/filters-store'

/**
 * Keep the filters store and the URL query string in step. The URL wins on load and on
 * back/forward; store changes are written back with `replace` so typing doesn't flood
 * the history. Mount once, in the layout that hosts the filter bar.
 */
export function useFilterUrlSync() {
  const [searchParams, setSearchParams] = useSearchParams()
  const filters = useFiltersStore((state) => state.filters)
  const fromUrl = useMemo(() => parseFilters(searchParams), [searchParams])
  const urlKey = filtersKey(fromUrl)
  /** The filters both sides last agreed on. */
  const synced = useRef<string | null>(null)

  useEffect(() => {
    if (urlKey === synced.current) return
    synced.current = urlKey
    useFiltersStore.getState().replace(fromUrl)
    // `fromUrl` is fully described by `urlKey`.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [urlKey])

  useEffect(() => {
    // Read the store directly: on first load the effect above has just updated it.
    const current = useFiltersStore.getState().filters
    const key = filtersKey(current)
    if (synced.current === null || key === synced.current) return
    synced.current = key
    setSearchParams((previous) => applyFilters(previous, current), { replace: true })
  }, [filters, setSearchParams])
}
