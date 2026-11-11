import { computed, onMounted, onUnmounted, ref, shallowRef } from 'vue'
import { GameApiError, getGame, isCredentials, startGame, type Credentials, type GameState } from '../api/games'

const storageKey = 'playground.session.v1'

export function useGameSession() {
  const game = shallowRef<GameState | null>(null)
  const busy = ref(false)
  const error = ref('')
  const storageNotice = ref('')
  const remaining = ref(0)
  const canRestore = ref(false)
  const seconds = computed(() => Math.ceil(remaining.value / 1000))
  let credentials: Credentials | null = null
  let deadline = 0
  let confirmationAt = 0
  let confirmationAttempted = false
  let disposed = false
  const controller = new AbortController()
  let timer: ReturnType<typeof setInterval> | undefined

  function save(value: Credentials | null) {
    credentials = value
    canRestore.value = value !== null
    try {
      if (value) sessionStorage.setItem(storageKey, JSON.stringify(value))
      else sessionStorage.removeItem(storageKey)
    } catch {
      storageNotice.value = 'Browser storage is unavailable. Refresh may lose this session.'
    }
  }

  function apply(state: GameState, sentAt: number) {
    // Project only state fields: never keep the start-only credential in UI state.
    game.value = {
      game_id: state.game_id, status: state.status, phase: state.phase, player: state.player,
      remaining_time_ms: state.remaining_time_ms, card: state.card,
      game_over_reason: state.game_over_reason, last_answer_result: state.last_answer_result,
    }
    const now = performance.now()
    remaining.value = Math.max(0, state.remaining_time_ms - (now - sentAt))
    deadline = now + remaining.value
    confirmationAt = remaining.value > 0 ? deadline : now + state.remaining_time_ms
    confirmationAttempted = false
    if (state.status === 'finished') {
      remaining.value = 0
      save(null)
    }
  }

  async function load(start: boolean) {
    if (busy.value || disposed || (!start && !credentials)) return
    busy.value = true
    error.value = ''
    const sentAt = performance.now()
    try {
      const state = start ? await startGame(controller.signal) : await getGame(credentials!, controller.signal)
      if (disposed) return
      if (start && isCredentials(state)) save({ game_id: state.game_id, session_token: state.session_token })
      apply(state, sentAt)
    } catch (reason) {
      if (disposed) return
      error.value = reason instanceof GameApiError ? reason.message : 'Unable to load the game. Please try again.'
      if (reason instanceof GameApiError && reason.status === 404) {
        save(null)
        game.value = null
        remaining.value = 0
      }
    } finally {
      if (!disposed) busy.value = false
    }
  }

  onMounted(() => {
    try {
      const stored = sessionStorage.getItem(storageKey)
      if (stored) {
        const parsed: unknown = JSON.parse(stored)
        if (isCredentials(parsed)) {
          credentials = parsed
          canRestore.value = true
          void load(false)
        } else save(null)
      }
    } catch { save(null) }
    timer = setInterval(() => {
      if (game.value?.status !== 'active') return
      const now = performance.now()
      remaining.value = Math.max(0, deadline - now)
      if (now >= confirmationAt && !confirmationAttempted && !busy.value) {
        confirmationAttempted = true
        void load(false)
      }
    }, 200)
  })

  onUnmounted(() => {
    disposed = true
    controller.abort()
    clearInterval(timer)
  })

  return { game, busy, error, storageNotice, canRestore, seconds,
    start: () => load(true), restore: () => load(false) }
}
