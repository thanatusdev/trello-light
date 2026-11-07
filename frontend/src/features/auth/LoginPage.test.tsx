import { screen, waitFor } from '@testing-library/react'
import { delay, http, HttpResponse } from 'msw'

import { useAuthStore } from '@/stores/auth-store'
import { API, demoUser } from '@/test/handlers'
import { renderApp } from '@/test/render'
import { server } from '@/test/server'

async function fillAndSubmit(
  user: ReturnType<typeof renderApp>['user'],
  email = demoUser.email,
  password = 'Demo1234!',
) {
  if (email) await user.type(screen.getByLabelText('Email'), email)
  if (password) await user.type(screen.getByLabelText('Password'), password)
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
}

describe('LoginPage', () => {
  it('validates the form before calling the API', async () => {
    const { user } = renderApp('/login')

    await user.click(await screen.findByRole('button', { name: 'Sign in' }))

    expect(await screen.findByText('Enter a valid email address.')).toBeInTheDocument()
    expect(screen.getByText('Enter your password.')).toBeInTheDocument()
    expect(screen.getByLabelText('Email')).toHaveAttribute('aria-invalid', 'true')
  })

  it('signs in and lands on the board shell', async () => {
    const { user, router } = renderApp('/login')

    await fillAndSubmit(user)

    expect(await screen.findByText(demoUser.full_name)).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/board')
    expect(useAuthStore.getState().refreshToken).toBe('refresh-1')
  })

  it('returns to the page the user was sent away from', async () => {
    const { user, router } = renderApp('/tasks')

    await screen.findByRole('heading', { name: 'Sign in' })
    expect(router.state.location.pathname).toBe('/login')
    await fillAndSubmit(user)

    await screen.findByText(demoUser.full_name)
    expect(router.state.location.pathname).toBe('/tasks')
  })

  it('shows an inline error for wrong credentials', async () => {
    const { user } = renderApp('/login')

    await fillAndSubmit(user, demoUser.email, 'wrong-password')

    expect(await screen.findByRole('alert')).toHaveTextContent('Incorrect email or password.')
    expect(useAuthStore.getState().refreshToken).toBeNull()
  })

  it('tells the user how long to wait when rate limited', async () => {
    server.use(
      http.post(`${API}/auth/login`, () =>
        HttpResponse.json(
          { detail: 'Rate limit exceeded, try again later' },
          { status: 429, headers: { 'Retry-After': '30' } },
        ),
      ),
    )
    const { user } = renderApp('/login')

    await fillAndSubmit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Too many sign-in attempts. Try again in 30 seconds.',
    )
  })

  it('reports network failures', async () => {
    server.use(http.post(`${API}/auth/login`, () => HttpResponse.error()))
    const { user } = renderApp('/login')

    await fillAndSubmit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent("Can't reach the server.")
  })

  it('reports unexpected server errors', async () => {
    server.use(
      http.post(`${API}/auth/login`, () => HttpResponse.json({ detail: 'boom' }, { status: 500 })),
    )
    const { user } = renderApp('/login')

    await fillAndSubmit(user)

    expect(await screen.findByRole('alert')).toHaveTextContent('Something went wrong.')
  })

  it('disables the submit button while signing in', async () => {
    server.use(
      http.post(`${API}/auth/login`, async () => {
        await delay(50)
        return HttpResponse.json({ detail: 'Incorrect email or password' }, { status: 401 })
      }),
    )
    const { user } = renderApp('/login')

    await fillAndSubmit(user)

    expect(screen.getByRole('button', { name: /Signing in/ })).toBeDisabled()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Sign in' })).toBeEnabled()
    })
  })
})
