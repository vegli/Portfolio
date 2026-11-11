import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createApp, nextTick, type App } from 'vue'
import PlaygroundView from '../src/views/PlaygroundView.vue'
import type { GameState } from '../src/api/games'

const id = '12345678-1234-4234-8234-123456789abc'
const token = 'a'.repeat(43)
const credentials = { game_id: id, session_token: token }
const storageKey = 'playground.session.v1'
const state: GameState = {
  game_id: id, status: 'active', phase: 'awaiting_answer', remaining_time_ms: 60000,
  player: { hp: 100, score: 0, correct_streak: 0 }, game_over_reason: null, last_answer_result: null,
  card: { id, rarity: 'common', effects: [], question: { id, text: 'What is atomicity?', category: 'databases', difficulty: 2,
    options: ['All or nothing', 'Isolation', 'Durability', 'Availability'].map((text, i) => ({ id: `00000000-0000-4000-8000-00000000000${i}`, text })) } },
}
let app: App | undefined
let root: HTMLDivElement
const fetchMock = vi.fn<typeof fetch>()
const response = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status, headers: { 'Content-Type': 'application/json' } })

async function settle() {
  await vi.advanceTimersByTimeAsync(0)
  await nextTick()
}
async function mount() {
  root = document.createElement('div')
  document.body.append(root)
  app = createApp(PlaygroundView)
  app.component('RouterLink', { template: '<a><slot /></a>' })
  app.mount(root)
  await settle()
}
function click(label: string) {
  const button = [...root.querySelectorAll('button')].find(button => button.textContent === label)
  expect(button).toBeDefined()
  button!.click()
}

beforeEach(() => {
  vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval', 'performance'] })
  sessionStorage.clear()
  fetchMock.mockReset()
  vi.stubGlobal('fetch', fetchMock)
})
afterEach(() => {
  app?.unmount()
  app = undefined
  root?.remove()
  vi.unstubAllGlobals()
  vi.useRealTimers()
})

describe('Playground start and restore', () => {
  it('starts once, shows loading, persists credentials and displays read-only options', async () => {
    let resolve!: (value: Response) => void
    fetchMock.mockReturnValueOnce(new Promise(done => { resolve = done }))
    await mount()
    expect(fetchMock).not.toHaveBeenCalled()
    click('Start Game')
    await settle()
    expect(root.textContent).toContain('Starting game…')
    expect(root.querySelector('button')!.disabled).toBe(true)
    resolve(response({ ...state, session_token: token }, 201))
    await settle()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]![0]).toBe('/api/v1/games')
    expect(fetchMock.mock.calls[0]![1]!.method).toBe('POST')
    expect(root.textContent).toContain('What is atomicity?')
    expect(root.querySelectorAll('.game-options li')).toHaveLength(4)
    expect(root.querySelectorAll('.game-options button')).toHaveLength(0)
    expect(root.querySelector('[role="timer"]')!.textContent).toBe('60s')
    expect(JSON.parse(sessionStorage.getItem(storageKey)!)).toEqual(credentials)
    expect(root.textContent).not.toContain(token)
  })

  it('restores on mount using the header without starting another game', async () => {
    sessionStorage.setItem(storageKey, JSON.stringify(credentials))
    fetchMock.mockResolvedValueOnce(response({ ...state, remaining_time_ms: 42000 }))
    await mount()
    expect(fetchMock.mock.calls[0]![0]).toBe(`/api/v1/games/${id}`)
    expect(fetchMock.mock.calls[0]![1]!.headers).toEqual({ 'X-Game-Token': token })
    expect(root.querySelector('[role="timer"]')!.textContent).toBe('42s')
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('counts down locally and confirms expiration without periodic polling', async () => {
    sessionStorage.setItem(storageKey, JSON.stringify(credentials))
    fetchMock.mockResolvedValueOnce(response({ ...state, remaining_time_ms: 2000 }))
    fetchMock.mockResolvedValueOnce(response({ ...state, status: 'finished', phase: null, remaining_time_ms: 0, game_over_reason: 'time_expired' }))
    await mount()
    await vi.advanceTimersByTimeAsync(1000)
    expect(root.querySelector('[role="timer"]')!.textContent).toBe('1s')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1000)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(root.textContent).toContain('This session has ended')
    expect(sessionStorage.getItem(storageKey)).toBeNull()
    await vi.advanceTimersByTimeAsync(10000)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('clears unavailable credentials and allows starting again', async () => {
    sessionStorage.setItem(storageKey, JSON.stringify(credentials))
    fetchMock.mockResolvedValueOnce(response({}, 404))
    await mount()
    expect(root.querySelector('[role="alert"]')!.textContent).toContain('no longer available')
    expect(sessionStorage.getItem(storageKey)).toBeNull()
    expect(root.querySelector('button')!.disabled).toBe(false)
  })

  it('keeps credentials on service failure and permits restore retry', async () => {
    sessionStorage.setItem(storageKey, JSON.stringify(credentials))
    fetchMock.mockResolvedValueOnce(response({ detail: 'private internals' }, 503))
    await mount()
    expect(root.textContent).toContain('temporarily unavailable')
    expect(root.textContent).not.toContain('private internals')
    expect(sessionStorage.getItem(storageKey)).not.toBeNull()
    fetchMock.mockResolvedValueOnce(response(state))
    click('Retry session')
    await settle()
    expect(root.textContent).toContain('What is atomicity?')
    expect(root.querySelector('[role="alert"]')).toBeNull()
  })

  it('handles failed start and does not persist a credential', async () => {
    fetchMock.mockRejectedValueOnce(new TypeError('Failed to fetch'))
    await mount()
    click('Start Game')
    await settle()
    expect(root.textContent).toContain('Check your connection')
    expect(sessionStorage.getItem(storageKey)).toBeNull()
    expect(root.querySelector('button')!.disabled).toBe(false)
  })

  it('discards malformed stored credentials without making a request', async () => {
    sessionStorage.setItem(storageKey, JSON.stringify({ game_id: '../../secret', session_token: token }))
    await mount()
    expect(fetchMock).not.toHaveBeenCalled()
    expect(sessionStorage.getItem(storageKey)).toBeNull()
  })

  it('deducts request duration conservatively from the visual countdown', async () => {
    let resolve!: (value: Response) => void
    fetchMock.mockReturnValueOnce(new Promise(done => { resolve = done }))
    await mount()
    click('Start Game')
    await vi.advanceTimersByTimeAsync(1200)
    resolve(response({ ...state, session_token: token }))
    await settle()
    expect(root.querySelector('[role="timer"]')!.textContent).toBe('59s')
  })

  it('continues in memory when sessionStorage is blocked', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new DOMException('Blocked') })
    fetchMock.mockResolvedValueOnce(response({ ...state, session_token: token }))
    await mount()
    click('Start Game')
    await settle()
    expect(root.textContent).toContain('Browser storage is unavailable')
    expect(root.textContent).toContain('What is atomicity?')
  })

  it('does not persist a late response after leaving the page', async () => {
    let resolve!: (value: Response) => void
    fetchMock.mockReturnValueOnce(new Promise(done => { resolve = done }))
    await mount()
    click('Start Game')
    app!.unmount()
    app = undefined
    resolve(response({ ...state, session_token: token }))
    await settle()
    expect(sessionStorage.getItem(storageKey)).toBeNull()
  })

  it('does not repeatedly retry a failed expiry confirmation', async () => {
    sessionStorage.setItem(storageKey, JSON.stringify(credentials))
    fetchMock.mockResolvedValueOnce(response({ ...state, remaining_time_ms: 1000 }))
    fetchMock.mockResolvedValueOnce(response({}, 503))
    await mount()
    await vi.advanceTimersByTimeAsync(10000)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(root.textContent).toContain('Retry session')
  })

  it('rejects malformed API state without saving credentials', async () => {
    fetchMock.mockResolvedValueOnce(response({ ...state, remaining_time_ms: '60000', session_token: token }))
    await mount()
    click('Start Game')
    await settle()
    expect(root.querySelector('[role="alert"]')).not.toBeNull()
    expect(sessionStorage.getItem(storageKey)).toBeNull()
  })

})
