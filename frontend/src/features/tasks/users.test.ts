import { http, HttpResponse } from 'msw'

import { useAuthStore } from '@/stores/auth-store'
import { API, tokens } from '@/test/handlers'
import { server } from '@/test/server'

import { fetchUsers } from './users'

const person = (n: number) => ({
  id: `6f1c2a3e-0000-4000-8000-${String(n).padStart(12, '0')}`,
  email: `user${n}@example.com`,
  full_name: `User ${String(n).padStart(3, '0')}`,
})

describe('fetchUsers', () => {
  beforeEach(() => {
    useAuthStore.getState().setTokens(tokens.initial)
  })

  it('reads every page at the largest page size', async () => {
    const everyone = Array.from({ length: 230 }, (_, i) => person(i + 1))
    const requested: string[] = []
    server.use(
      http.get(`${API}/users`, ({ request }) => {
        const query = new URL(request.url).searchParams
        requested.push(query.toString())
        const page = Number(query.get('page'))
        const size = Number(query.get('size'))
        return HttpResponse.json({
          items: everyone.slice((page - 1) * size, page * size),
          total: everyone.length,
          page,
          size,
          pages: Math.ceil(everyone.length / size),
        })
      }),
    )

    const users = await fetchUsers()

    expect(users).toHaveLength(230)
    expect(users.at(-1)).toEqual(person(230))
    expect(requested.sort()).toEqual(['page=1&size=100', 'page=2&size=100', 'page=3&size=100'])
  })

  it('makes a single request when everyone fits on one page', async () => {
    const requested: string[] = []
    server.events.on('request:start', ({ request }) => {
      if (request.url.includes('/users')) requested.push(request.url)
    })

    expect(await fetchUsers()).toHaveLength(2)
    expect(requested).toHaveLength(1)
  })

  it('handles an empty list', async () => {
    server.use(
      http.get(`${API}/users`, () =>
        HttpResponse.json({ items: [], total: 0, page: 1, size: 100, pages: 0 }),
      ),
    )

    expect(await fetchUsers()).toEqual([])
  })

  it('fails if any page fails', async () => {
    server.use(
      http.get(`${API}/users`, ({ request }) =>
        new URL(request.url).searchParams.get('page') === '2'
          ? HttpResponse.json({ detail: 'boom' }, { status: 500 })
          : HttpResponse.json({ items: [person(1)], total: 101, page: 1, size: 100, pages: 2 }),
      ),
    )

    await expect(fetchUsers()).rejects.toMatchObject({ status: 500 })
  })
})
