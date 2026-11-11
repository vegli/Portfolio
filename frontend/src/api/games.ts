export interface Credentials { game_id: string; session_token: string }
export interface Effect { type: 'hp' | 'score' | 'time'; value: number; trigger: 'correct' | 'incorrect' }
export interface GameState {
  game_id: string
  status: 'created' | 'active' | 'finished'
  phase: 'awaiting_card' | 'awaiting_answer' | 'awaiting_next_card' | null
  player: { hp: number; score: number; correct_streak: number }
  remaining_time_ms: number
  card: {
    id: string
    rarity: 'common' | 'rare' | 'epic'
    question: { id: string; text: string; category: string; difficulty: number; options: { id: string; text: string }[] }
    effects: Effect[]
  } | null
  game_over_reason: 'hp_depleted' | 'time_expired' | 'no_questions_available' | null
  last_answer_result: {
    card_id: string; answer_option_id: string; is_correct: boolean; correct_answer_id: string
    score_delta: number; applied_effects: Effect[]
  } | null
}
export type StartedGame = GameState & { session_token: string }

export class GameApiError extends Error {
  constructor(public readonly status: number) {
    super(status === 404 ? 'This session is no longer available. Start a new game.'
      : status === 503 ? 'The game service is temporarily unavailable. Please try again.'
      : 'Unable to load the game. Check your connection and try again.')
  }
}

const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const object = (value: unknown): value is Record<string, unknown> => typeof value === 'object' && value !== null
export function isCredentials(value: unknown): value is Credentials {
  return object(value) && typeof value.game_id === 'string' && uuid.test(value.game_id)
    && typeof value.session_token === 'string' && /^[A-Za-z0-9_-]{43}$/.test(value.session_token)
}

const isUUID = (value: unknown): value is string => typeof value === 'string' && uuid.test(value)
const isInteger = (value: unknown): value is number => Number.isSafeInteger(value)
function isEffect(value: unknown): value is Effect {
  return object(value) && ['hp', 'score', 'time'].includes(String(value.type)) && isInteger(value.value)
    && ['correct', 'incorrect'].includes(String(value.trigger))
}
function isFeedback(value: unknown): value is GameState['last_answer_result'] {
  return value === null || (object(value) && isUUID(value.card_id) && isUUID(value.answer_option_id)
    && isUUID(value.correct_answer_id) && typeof value.is_correct === 'boolean' && isInteger(value.score_delta)
    && Array.isArray(value.applied_effects) && value.applied_effects.every(isEffect))
}
function isCard(value: unknown): value is GameState['card'] {
  if (value === null) return true
  if (!object(value) || !isUUID(value.id) || !['common', 'rare', 'epic'].includes(String(value.rarity))
    || !Array.isArray(value.effects) || !value.effects.every(isEffect) || !object(value.question)) return false
  const question = value.question
  return isUUID(question.id) && typeof question.text === 'string' && typeof question.category === 'string'
    && isInteger(question.difficulty) && question.difficulty >= 1 && question.difficulty <= 5
    && Array.isArray(question.options) && question.options.length === 4
    && question.options.every(option => object(option) && isUUID(option.id) && typeof option.text === 'string')
    && new Set(question.options.map(option => option.id)).size === 4
}
function isGame(value: unknown): value is GameState {
  if (!object(value) || !isUUID(value.game_id) || !object(value.player)) return false
  const player = value.player
  return ['created', 'active', 'finished'].includes(String(value.status))
    && (value.phase === null || ['awaiting_card', 'awaiting_answer', 'awaiting_next_card'].includes(String(value.phase)))
    && (value.game_over_reason === null || ['hp_depleted', 'time_expired', 'no_questions_available'].includes(String(value.game_over_reason)))
    && isInteger(value.remaining_time_ms) && value.remaining_time_ms >= 0
    && isInteger(player.hp) && isInteger(player.score) && isInteger(player.correct_streak) && player.correct_streak >= 0
    && isCard(value.card) && (value.status !== 'active' || value.card !== null)
    && isFeedback(value.last_answer_result)
}

async function request(path: string, init: RequestInit, signal: AbortSignal): Promise<unknown> {
  try {
    const response = await fetch(`/api/v1/games${path}`, {
      ...init, signal: AbortSignal.any([signal, AbortSignal.timeout(10000)]), cache: 'no-store', credentials: 'omit',
    })
    if (!response.ok) throw new GameApiError(response.status)
    return await response.json()
  } catch (error) {
    if (error instanceof GameApiError) throw error
    throw new GameApiError(0)
  }
}

export async function startGame(signal: AbortSignal): Promise<StartedGame> {
  const value = await request('', { method: 'POST' }, signal)
  if (!isGame(value) || !isCredentials(value)) throw new GameApiError(0)
  return value
}

export async function getGame(credentials: Credentials, signal: AbortSignal): Promise<GameState> {
  const value = await request(`/${credentials.game_id}`, { headers: { 'X-Game-Token': credentials.session_token } }, signal)
  if (!isGame(value) || value.game_id !== credentials.game_id) throw new GameApiError(0)
  return value
}
