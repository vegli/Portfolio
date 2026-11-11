<script setup lang="ts">
import { useGameSession } from '../composables/useGameSession'

const { game, busy, error, storageNotice, canRestore, seconds, start, restore } = useGameSession()
</script>

<template>
  <section class="container playground game-screen" aria-labelledby="playground-title" :aria-busy="busy">
    <p class="eyebrow">A space to explore</p>
    <h1 id="playground-title">Playground<span class="accent">.</span></h1>
    <p class="hero-description">Explore a technical interview question. Answering and drawing your next card are coming soon.</p>

    <p v-if="busy" role="status" class="game-message">{{ game ? 'Checking session…' : canRestore ? 'Restoring your session…' : 'Starting game…' }}</p>
    <p v-if="error" role="alert" class="game-message game-error">{{ error }}</p>
    <p v-if="storageNotice" role="status" class="game-message">{{ storageNotice }}</p>

    <div v-if="game" class="game-content">
      <dl class="game-stats" aria-label="Game statistics">
        <div><dt>HP</dt><dd>{{ game.player.hp }}</dd></div>
        <div><dt>Score</dt><dd>{{ game.player.score }}</dd></div>
        <div><dt>Time remaining</dt><dd role="timer" aria-live="off">{{ seconds }}<span class="stat-unit">s</span></dd></div>
      </dl>
      <p v-if="game.status === 'finished'" role="status" class="game-message">This session has ended. Start a new game to explore another question.</p>
      <p v-else-if="seconds === 0 && !error" role="status" class="game-message">Confirming remaining time…</p>
      <article v-if="game.card" class="game-card" aria-labelledby="question-title">
        <p class="eyebrow">{{ game.card.question.category.replaceAll('_', ' ') }} · Difficulty {{ game.card.question.difficulty }} · {{ game.card.rarity }}</p>
        <h2 id="question-title">{{ game.card.question.text }}</h2>
        <ol class="game-options" aria-label="Answer options" aria-describedby="options-notice">
          <li v-for="option in game.card.question.options" :key="option.id">{{ option.text }}</li>
        </ol>
        <p id="options-notice" class="game-note">Answer options are read-only in this preview.</p>
      </article>
    </div>

    <div class="game-actions">
      <button v-if="!game || game.status === 'finished'" class="button button-primary" :disabled="busy || canRestore" @click="start">Start Game</button>
      <button v-if="error && canRestore" class="button button-secondary" :disabled="busy" @click="restore">Retry session</button>
      <RouterLink class="text-link" to="/">Back to portfolio</RouterLink>
    </div>
  </section>
</template>
