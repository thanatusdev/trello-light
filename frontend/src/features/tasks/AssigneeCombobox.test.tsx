import { QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { http, HttpResponse } from 'msw'

import { createQueryClient } from '@/app/query-client'
import { useAuthStore } from '@/stores/auth-store'
import { API, tokens } from '@/test/handlers'
import { server } from '@/test/server'

import { AssigneeCombobox } from './AssigneeCombobox'

function renderCombobox(onChange = vi.fn()) {
  useAuthStore.getState().setTokens(tokens.initial)
  const user = userEvent.setup()
  render(
    <QueryClientProvider client={createQueryClient({ retry: false })}>
      <AssigneeCombobox value={null} onChange={onChange} />
    </QueryClientProvider>,
  )
  return { user, onChange }
}

describe('AssigneeCombobox', () => {
  it('lists people and picks one', async () => {
    const { user, onChange } = renderCombobox()

    await user.click(screen.getByRole('combobox'))
    await user.click(await screen.findByRole('option', { name: 'Bob Jones' }))

    expect(onChange).toHaveBeenCalledWith('6f1c2a3e-0000-4000-8000-000000000002')
  })

  it('says nobody matches a search', async () => {
    const { user } = renderCombobox()

    await user.click(screen.getByRole('combobox'))
    await screen.findByRole('option', { name: 'Bob Jones' })
    await user.type(screen.getByPlaceholderText('Search people…'), 'zzz')

    expect(screen.getByText('No one matches.')).toBeInTheDocument()
  })

  it('shows a load failure distinctly and retries', async () => {
    let fail = true
    server.use(
      http.get(`${API}/users`, () =>
        fail ? HttpResponse.json({ detail: 'boom' }, { status: 500 }) : undefined,
      ),
    )
    const { user } = renderCombobox()

    await user.click(screen.getByRole('combobox'))

    expect(await screen.findByText("Couldn't load people.")).toBeInTheDocument()
    expect(screen.queryByText('No one matches.')).not.toBeInTheDocument()
    fail = false
    await user.click(screen.getByRole('button', { name: 'Try again' }))

    expect(await screen.findByRole('option', { name: 'Bob Jones' })).toBeInTheDocument()
  })
})
