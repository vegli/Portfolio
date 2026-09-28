# Architecture

## 1. System Overview

The application consists of two main product areas:

1. Portfolio
   - Public presentation of experience, skills and projects.
   - Primarily frontend-driven.
   - Does not require backend functionality unless a concrete need appears.

2. Playground
   - Interactive card-based technical interview game.
   - Vue frontend provides the game UI.
   - FastAPI owns game-related business logic and exposes it through an HTTP API.
   - PostgreSQL stores persistent game data.
   - Redis may be introduced later if a concrete caching or temporary-state use case appears.

## High-Level Architecture

```text
Browser
    |
    v
Vue 3 + TypeScript
    |
    | HTTP / JSON
    v
FastAPI
    |
    v
PostgreSQL
```

Redis is optional and should only be introduced when needed.

## Portfolio

The portfolio is a frontend-only part of the application.

Its content is static and does not require persistence or backend processing.
Portfolio data such as experience, skills, projects, and personal information
is maintained directly within the frontend application.

No backend API or database will be introduced for portfolio content unless a
concrete future requirement justifies it.

## Playground

The Playground is an interactive, card-based technical interview preparation game.

The goal is to provide a short and engaging way to practice technical concepts while also serving as the main interactive part of the portfolio.

### Core Concept

- The player is presented with question cards from different technical categories.
- Categories may include Computer Science, Databases, Networking, System Design, Security, DDD, Backend Engineering, and Performance.
- Questions may use different formats, such as multiple choice or short technical scenarios.
- Correct answers increase the player's score.
- Consecutive correct answers may build a streak or score multiplier.
- The game may include limited-use mechanics such as hints, skips, question swaps, or second chances.

### Presentation

The game should have a polished card-based interface with lightweight animations and transitions.

Visual effects should improve feedback and game feel without making the interface distracting or overly game-like.

The Playground should feel naturally integrated into the portfolio rather than like a separate application.

### Game Flow

A game session starts with:

- 120 seconds of available time.
- 100 initial HP.
- A shuffled deck of question cards.

During the session, the player repeatedly draws a card from the deck and answers its question.

Cards may differ by:

- Technical category.
- Difficulty.
- Answer type.
- Zero or more gameplay effects.

Supported answer types may include multiple-choice and free-text answers. Voice-based answers may be explored later.

Each answer affects the current game state. Depending on the answer, card difficulty, active effects, and the player's current streak, the game may update:

- Score
- HP
- Current streak
- Other temporary game state

HP may exceed the initial 100 HP when granted by gameplay effects.

The session ends when either:

- The 120-second timer expires.
- The player's HP reaches zero.

### Game Results

At the end of a session, the player receives a summary including:

- Total score
- Longest correct-answer streak
- Fastest answer time
- Slowest answer time
- Best-performing categories
- Worst-performing categories

### Card Model

A `Card` is an independent game entity that defines the challenge itself.

A card contains:

- Question content
- Technical category
- Difficulty
- Answer type
- Possible answers or answer-evaluation rules
- Number of effect slots available on the card

The card itself does not contain active game-session state such as HP, score, streak, or currently assigned effects.

Effects are assigned when the card is used within a `GameSession`.

### Effect Assignment

When a card is drawn during a game session, zero or more effects may be assigned to it up to the card's available effect-slot limit.

Effect assignment may be randomized, but must respect balancing rules based on factors such as:

- Card difficulty
- Effect strength
- Potential reward
- Potential HP damage
- Current game state

The goal is to allow variation between sessions while preventing unreasonable combinations, such as an easy question producing an excessively large reward or a difficult question causing disproportionate punishment.

### Effect Model

An `Effect` represents a gameplay modifier that changes the outcome or rules of a drawn card.

Effects are not permanently stored as part of the card itself. A card only defines how many effect slots it has available.

When a card is drawn during a `GameSession`, effects may be assigned to those slots according to the game's balancing rules.

Each effect contains:

- `trigger` - determines when the effect is activated.
- `type` - defines what the effect changes.
- `value` - optional numeric value used by the effect.
- `duration` - optional duration when the effect persists beyond the current card.

Possible triggers:

- `ON_CORRECT`
- `ON_WRONG`
- `ALWAYS`

Possible effect types may include:

- `HP_CHANGE`
- `TIME_CHANGE`
- `SCORE_MULTIPLIER`
- `DAMAGE_MULTIPLIER`
- `STREAK_PROTECTION`
- `STREAK_RESET`
- `NEXT_WRONG_PROTECTION`

Examples:

- `ON_CORRECT + HP_CHANGE +10`
- `ON_CORRECT + SCORE_MULTIPLIER x2`
- `ON_CORRECT + TIME_CHANGE +10s`
- `ON_WRONG + HP_CHANGE -20`
- `ON_WRONG + DAMAGE_MULTIPLIER x2`
- `ON_CORRECT + NEXT_WRONG_PROTECTION`

Some effects may persist beyond the current card and therefore become temporary state within the `GameSession`.

Effect combinations should respect balancing rules based on card difficulty and effect strength.

### Game Session Model

A `GameSession` represents one active or completed game run.

A session contains the current gameplay state and is responsible for tracking progress throughout the run.

A game session contains:

- Start time
- Session duration
- Current HP
- Current score
- Current streak
- Longest streak
- Answer history
- Active temporary effects
- Current session status

Possible session statuses:

- `ACTIVE`
- `COMPLETED`
- `FAILED`

A session starts with:

- 120 seconds
- 100 HP
- 0 score
- 0 streak

The session ends when:

- The timer expires.
- HP reaches zero or below.

The session may also track per-answer data required for the final result summary, such as:

- Answer duration
- Whether the answer was correct
- Question category
- Question difficulty
- Score gained
- HP change
- Effects applied

### Answer Attempt Model

An `AnswerAttempt` represents one player interaction with a drawn card.

It records what happened during that specific question and provides the data needed for scoring, statistics, and the final session summary.

An answer attempt contains:

- Card identifier
- Question category
- Question difficulty
- Answer type
- Player answer
- Whether the answer was correct
- Answer duration
- Score gained
- HP change
- Time change
- Streak before the answer
- Streak after the answer
- Effects applied
- Timestamp

The attempt should capture the final resolved outcome of the card after all relevant effects and game rules are applied.

Answer attempts are stored as part of the `GameSession` history and are later used to calculate:

- Fastest answer
- Slowest answer
- Best-performing categories
- Worst-performing categories
- Longest streak
- Total score

So conceptually : 

```
GameSession
    |
    +--> AnswerAttempt
    +--> AnswerAttempt
    +--> AnswerAttempt
    +--> ...
```

### Scoring and Damage Model

The outcome of an `AnswerAttempt` is calculated from several factors:

- Card difficulty
- Whether the answer was correct
- Current streak
- Active card effects
- Active session effects

Each difficulty level defines a base reward and base penalty.

Example:

- `EASY`
- `MEDIUM`
- `HARD`
- `VERY_HARD`

For a correct answer:

1. Determine the base score from card difficulty.
2. Apply streak-related modifiers.
3. Apply card effects.
4. Apply active session effects.
5. Calculate the final score gain.
6. Apply HP or time rewards if present.

For a wrong answer:

1. Determine the base HP penalty from card difficulty.
2. Apply streak-related consequences.
3. Apply card effects.
4. Apply active session effects.
5. Calculate the final HP and time changes.

Effects may modify the normal result, but balancing rules should prevent extreme outcomes that are disproportionate to card difficulty.

### Balancing Rules

Random effect assignment must operate within predefined boundaries.

Examples:

- Easy cards should not provide disproportionately large rewards.
- Very hard cards should not cause unreasonable instant HP loss.
- Multiple stacked effects should have a combined strength limit.
- Positive and negative effects should be weighted according to card difficulty.
- Certain effect combinations may be explicitly disallowed.

### Difficulty Model

Each card has one of the following difficulty levels:

- `EASY`
- `MEDIUM`
- `HARD`
- `VERY_HARD`

Difficulty influences:

- Base score reward
- Base HP penalty
- Allowed effect strength
- Maximum combined strength of stacked effects
- Probability of receiving stronger positive or negative effects

The frontend maps difficulty levels to visual styling:

- `EASY` → green
- `MEDIUM` → blue
- `HARD` → red
- `VERY_HARD` → purple or dark blue

Visual representation belongs to the frontend and is not part of the domain model.

Difficulty should provide predictable balancing boundaries while still allowing randomness through effect assignment.

### Deck and Card Selection Model

A `Deck` represents the pool of cards available during a `GameSession`.

Cards should not be selected completely randomly without constraints, because that could produce poor gameplay balance.

Card selection should consider:

- Card difficulty
- Technical category
- Previously drawn cards
- Current game progress
- Remaining session time
- Existing difficulty distribution within the session

The same card should not normally appear more than once in the same session.

Selection may use weighted randomness rather than uniform randomness.

Example behavior:

- Easier cards are slightly more common at the beginning of a session.
- Harder cards may become more likely as the session progresses.
- Categories should be distributed so that a session does not become dominated by a single topic.
- Extremely difficult cards should remain relatively rare.

The deck should still feel unpredictable, but randomness should operate within balancing constraints.

Esentially 

```
Card Pool
   ↓
Filter eligible cards
   ↓
Apply weights
   ↓
Random selection
   ↓
Drawn Card
```

### Answer Evaluation

For the initial version of the game, cards use only predefined answer choices.

Each card contains:
- A list of possible answers.
- Exactly one correct answer.

When the player submits an answer:

1. The backend checks whether the selected answer matches the card's correct answer.
2. The answer is marked as correct or wrong.
3. Scoring, HP changes, streak changes, and effects are applied.
4. The resolved result is stored as an `AnswerAttempt`.

Free-text and voice-based answers are intentionally excluded from the initial version and may be explored later.

### Session Lifecycle

A game session follows this lifecycle:

1. Start a new session.
2. Initialize timer, HP, score, and streak.
3. Draw the next eligible card.
4. Submit an answer.
5. Evaluate the answer.
6. Apply score, HP, streak, time, and effects.
7. Store the resulting `AnswerAttempt`.
8. Continue until the timer expires or HP reaches zero.
9. Finalize the session.
10. Return the session result summary.

## Backend Architecture

The backend is responsible only for Playground functionality. Portfolio content remains frontend-only.

The backend should be organized around clear responsibilities rather than around framework-specific code.

```text
FastAPI Routes
    ↓
Application / Game Services
    ↓
Domain Logic
    ↓
Repositories
    ↓
PostgreSQL
```

### API Layer

The API layer exposes HTTP endpoints used by the frontend.

Responsibilities include:

- Receiving and validating incoming requests.
- Calling the appropriate application service.
- Returning HTTP responses.
- Mapping domain or application errors to appropriate HTTP status codes.

Route handlers should remain thin and should not contain significant game logic.

### Application / Game Services

Application services coordinate use cases such as:

- Starting a game session.
- Drawing the next card.
- Submitting an answer.
- Resolving scoring, HP, streaks, and effects.
- Finalizing a game session.
- Building the final result summary.

These services orchestrate domain objects and repositories but should not contain persistence-specific logic.

### Domain Logic

Domain logic contains the core gameplay rules.

This includes:

- Card selection rules.
- Difficulty handling.
- Effect assignment.
- Effect resolution.
- Scoring rules.
- HP changes.
- Streak handling.
- Session lifecycle rules.
- Balancing constraints.

The domain layer should remain independent from FastAPI and database-specific details where practical.

### Repository Layer

Repositories handle persistent data access.

Their responsibility is to load and store domain-related data such as:

- Cards.
- Game sessions.
- Answer attempts.

Repositories should hide database-specific details from the application and domain layers.

### Persistence

PostgreSQL is the primary persistent data store.

It may store:

- Card definitions.
- Possible answers.
- Game sessions.
- Answer attempts.
- Persisted session results, if needed.

Redis is not part of the initial backend flow and should only be introduced if a concrete caching or temporary-state requirement appears.



