export const PAGE_SIZES = [10, 20, 50, 100] as const
const DEFAULT_SIZE = 20

/** `page` and `size` from the URL, falling back to defaults for anything invalid. */
export function parsePaging(params: URLSearchParams) {
  const page = Number(params.get('page'))
  const size = Number(params.get('size'))
  return {
    page: Number.isInteger(page) && page >= 1 ? page : 1,
    size: (PAGE_SIZES as readonly number[]).includes(size) ? size : DEFAULT_SIZE,
  }
}
