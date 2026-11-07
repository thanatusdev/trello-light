/** Columns and tasks share one DnD context; column ids get a prefix to tell them apart. */
export const columnDndId = (id: string) => `column:${id}`

export const isColumnDndId = (id: string | number) => String(id).startsWith('column:')

/** The status/task id behind a DnD id. */
export const fromDndId = (id: string | number) => String(id).replace(/^column:/, '')
