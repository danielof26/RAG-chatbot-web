import { afterEach, describe, expect, it, vi } from 'vitest'
import { createApi } from './apiClient'

const respond = (status) => vi.fn().mockResolvedValue({ status, ok: status < 400 })

afterEach(() => vi.unstubAllGlobals())

describe('createApi', () => {
  it('sends the bearer token on every verb', async () => {
    const fetch = respond(200)
    vi.stubGlobal('fetch', fetch)
    const api = createApi('tok')

    await api.get('/a')
    await api.post('/b', { x: 1 })
    await api.put('/c', { x: 1 })
    await api.delete('/d')
    await api.upload('/e', new FormData())

    for (const [, options] of fetch.mock.calls) {
      expect(options.headers.Authorization).toBe('Bearer tok')
    }
  })

  it('sends JSON bodies with a JSON content type, and leaves FormData for the browser to type', async () => {
    const fetch = respond(200)
    vi.stubGlobal('fetch', fetch)
    const api = createApi('tok')

    await api.post('/json', { a: 1 })
    expect(fetch.mock.calls[0][1].body).toBe('{"a":1}')
    expect(fetch.mock.calls[0][1].headers['Content-Type']).toBe('application/json')

    await api.upload('/file', new FormData())
    expect(fetch.mock.calls[1][1].headers['Content-Type']).toBeUndefined()
  })

  it('posts without a body when none is given', async () => {
    const fetch = respond(200)
    vi.stubGlobal('fetch', fetch)
    await createApi('tok').post('/x')
    expect(fetch.mock.calls[0][1].body).toBeUndefined()
  })

  it('calls onUnauthorized on a 401 and still returns the response', async () => {
    vi.stubGlobal('fetch', respond(401))
    const onUnauthorized = vi.fn()
    const res = await createApi('tok', onUnauthorized).get('/x')
    expect(onUnauthorized).toHaveBeenCalledOnce()
    expect(res.status).toBe(401)
  })

  it.each([200, 403, 404, 500])('does not log the user out on a %i', async (status) => {
    vi.stubGlobal('fetch', respond(status))
    const onUnauthorized = vi.fn()
    await createApi('tok', onUnauthorized).get('/x')
    expect(onUnauthorized).not.toHaveBeenCalled()
  })

  it('works without an onUnauthorized callback', async () => {
    vi.stubGlobal('fetch', respond(401))
    await expect(createApi('tok').get('/x')).resolves.toMatchObject({ status: 401 })
  })

  it('lets network errors reach the caller', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('offline')))
    await expect(createApi('tok').get('/x')).rejects.toThrow('offline')
  })
})
