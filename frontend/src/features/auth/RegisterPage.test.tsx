import { screen, waitFor } from '@testing-library/react'
import { delay, http, HttpResponse } from 'msw'

import { useAuthStore } from '@/stores/auth-store'
import { API, demoUser } from '@/test/handlers'
import { renderApp } from '@/test/render'
import { recordRequests } from '@/test/requests'
import { server } from '@/test/server'

const newUser = {
  full_name: 'Dana Scully',
  email: 'dana@example.com',
  password: 'trustno1!',
}

async function fillAndSubmit(
  user: ReturnType<typeof renderApp>['user'],
  values: Partial<typeof newUser & { confirm: string }> = {},
) {
  const { full_name, email, password, confirm } = { ...newUser, confirm: undefined, ...values }
  if (full_name) await user.type(screen.getByLabelText('Full name'), full_name)
  if (email) await user.type(screen.getByLabelText('Email'), email)
  if (password) await user.type(screen.getByLabelText('Password'), password)
  const confirmation = confirm ?? password
  if (confirmation) await user.type(screen.getByLabelText('Confirm password'), confirmation)
  await user.click(screen.getByRole('button', { name: 'Create account' }))
}

function rejectRegister(status: number, detail: unknown, headers: Record<string, string> = {}) {
  server.use(
    http.post(`${API}/auth/register`, () => HttpResponse.json({ detail }, { status, headers })),
  )
}

describe('RegisterPage', () => {
  it('is reachable from the login page and links back to it', async () => {
    const { user, router } = renderApp('/login')

    await user.click(await screen.findByRole('link', { name: 'Create an account' }))
    expect(await screen.findByRole('heading', { name: 'Create an account' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/register')

    await user.click(screen.getByRole('link', { name: 'Sign in' }))
    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('validates the form before calling the API', async () => {
    const requests = recordRequests()
    const { user } = renderApp('/register')

    await user.click(await screen.findByRole('button', { name: 'Create account' }))

    expect(await screen.findByText('Enter your name.')).toBeInTheDocument()
    expect(screen.getByText('Enter a valid email address.')).toBeInTheDocument()
    expect(screen.getByText('Use at least 8 characters.')).toBeInTheDocument()
    expect(screen.getByLabelText('Full name')).toHaveAttribute('aria-invalid', 'true')
    expect(screen.getByLabelText('Password')).toHaveAccessibleDescription(
      /Use at least 8 characters\./,
    )
    expect(requests).toEqual([])
  })

  it('checks that the passwords match', async () => {
    const { user } = renderApp('/register')

    await screen.findByRole('heading', { name: 'Create an account' })
    await fillAndSubmit(user, { confirm: 'something-else' })

    expect(await screen.findByText("Passwords don't match.")).toBeInTheDocument()
    expect(screen.getByLabelText('Confirm password')).toHaveAttribute('aria-invalid', 'true')
  })

  it('creates the account, signs in and lands on the board', async () => {
    const requests = recordRequests()
    const { user, router } = renderApp('/register')

    await screen.findByRole('heading', { name: 'Create an account' })
    await fillAndSubmit(user)

    await waitFor(() => {
      expect(router.state.location.pathname).toBe('/board')
    })
    expect(useAuthStore.getState().refreshToken).not.toBeNull()
    expect(requests[0]).toEqual({
      method: 'POST',
      path: '/auth/register',
      body: newUser,
    })
    expect(requests[1]).toMatchObject({ method: 'POST', path: '/auth/login' })
  })

  it('says when the email is already registered', async () => {
    const { user } = renderApp('/register')

    await screen.findByRole('heading', { name: 'Create an account' })
    await fillAndSubmit(user, { email: demoUser.email })

    expect(
      await screen.findByText('An account with this email already exists.'),
    ).toBeInTheDocument()
    expect(useAuthStore.getState().refreshToken).toBeNull()
  })

  it('tells the user how long to wait when rate limited', async () => {
    rejectRegister(429, 'Rate limit exceeded', { 'Retry-After': '45' })
    const { user } = renderApp('/register')

    await screen.findByRole('heading', { name: 'Create an account' })
    await fillAndSubmit(user)

    expect(
      await screen.findByText('Too many sign-up attempts. Try again in 45 seconds.'),
    ).toBeInTheDocument()
  })

  it.each([
    ['a string detail', 'Invalid email address'],
    ['a list detail', [{ msg: 'Invalid email address', loc: ['body', 'email'] }]],
  ])('shows the server validation message from %s', async (_case, detail) => {
    rejectRegister(422, detail)
    const { user } = renderApp('/register')

    await screen.findByRole('heading', { name: 'Create an account' })
    await fillAndSubmit(user)

    expect(await screen.findByText('Invalid email address')).toBeInTheDocument()
  })

  it('reports network failures', async () => {
    server.use(http.post(`${API}/auth/register`, () => HttpResponse.error()))
    const { user } = renderApp('/register')

    await screen.findByRole('heading', { name: 'Create an account' })
    await fillAndSubmit(user)

    expect(await screen.findByText(/Can't reach the server/)).toBeInTheDocument()
  })

  it('sends the user to sign in if the account was created but signing in failed', async () => {
    server.use(
      http.post(`${API}/auth/login`, () => HttpResponse.json({ detail: 'boom' }, { status: 500 })),
    )
    const { user } = renderApp('/register')

    await screen.findByRole('heading', { name: 'Create an account' })
    await fillAndSubmit(user)

    expect(
      await screen.findByText(/Your account was created, but we couldn't sign you in/),
    ).toBeInTheDocument()
    expect(useAuthStore.getState().refreshToken).toBeNull()
  })

  it('disables the submit button while creating the account', async () => {
    server.use(
      http.post(`${API}/auth/register`, async () => {
        await delay(50)
        return HttpResponse.json({ detail: 'exists' }, { status: 409 })
      }),
    )
    const { user } = renderApp('/register')

    await screen.findByRole('heading', { name: 'Create an account' })
    await fillAndSubmit(user)

    expect(screen.getByRole('button', { name: /Creating account/ })).toBeDisabled()
    await waitFor(() => {
      expect(screen.getByRole('button', { name: 'Create account' })).toBeEnabled()
    })
  })
})
