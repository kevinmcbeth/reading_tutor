# Changelog: F&P Guided Reading Level System

## Overview

Added a **Fountas & Pinnell (F&P) Guided Reading Level system** as a structured "Leveled Reading" mode alongside the existing free-play library. F&P levels A through Z2 (28 levels) provide an educationally grounded reading progression with auto-advancement based on accuracy.

---

## Database

- **New table `fp_levels`** — 28 level definitions (A-Z2) seeded on startup, each with:
  - Sentence count range (1-2 at Level A up to 30+ at Z2)
  - Image generation toggle (enabled A-N, disabled O+)
  - Image support tier (heavy/strong/moderate/light/minimal/sparse/rare/none)
  - Vocabulary constraints as JSONB (sight-words-only, CVC+sight, expanding, varied, grade-appropriate)
  - Grade range and description
- **New table `fp_progress`** — Tracks per-child, per-level reading accuracy history
- **New columns on `children`** — `fp_level` (current level), `fp_level_set_by` (auto/parent)
- **New column on `stories`** — `fp_level` (associates story with a reading level)
- **New indexes** — `idx_fp_progress_child_level`, `idx_stories_fp_level`

## Backend — Story Generation

- **New prompt templates** — `fp_story_system.txt` and `fp_image_prompt_system.txt` with level-specific placeholders
- **New function `generate_fp_story()`** in `ollama_client.py`:
  - Builds vocabulary rules and level instructions dynamically from JSONB constraints
  - Strict sight-word validation at levels A-B with one retry on violation
  - Level-appropriate writing instructions (pattern text at A-B, full narratives at O+)
- **New function `generate_fp_image_prompts()`** — Adjusts image detail by support level
- **New pipeline `run_fp_story_generation()`** in `story_pipeline.py`:
  - Loads level definition, generates text with level-aware prompts
  - Skips image generation entirely for levels O+ (saves GPU time)
  - F&P-specific challenge word logic (all words at A-D, non-common at E+)
  - Full audio generation for all levels
- **New worker task `generate_fp_story_task`** registered in arq worker

## Backend — API Endpoints

New router at `/api/fp` with 6 endpoints:

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/fp/levels` | GET | List all 28 F&P level definitions |
| `/api/fp/stories?level=A` | GET | Stories at a specific level |
| `/api/fp/generate` | POST | Generate story at a specific F&P level |
| `/api/fp/child/{id}/progress` | GET | Child's level progress, accuracy, advance/drop status |
| `/api/fp/child/{id}/level` | POST | Parent override of child's level |
| `/api/fp/child/{id}/start` | POST | Initialize child into leveled reading mode |

## Backend — Progression Logic

Session completion (`POST /api/sessions/{id}/complete`) now includes F&P tracking:

- Records accuracy in `fp_progress` for F&P stories
- **Auto-advancement**: If last 3 stories at current level all have >= 90% accuracy, child auto-advances to next level
- **Drop suggestion**: If last 3 stories all < 70% accuracy, `suggest_drop` flag is set (parent-visible, not auto-applied)

## Backend — API Models

- **New models**: `FPLevelResponse`, `FPProgressResponse`, `FPLevelSet`, `FPStartRequest`, `FPStoryPrompt`
- **Extended**: `StoryResponse` (+`fp_level`), `ChildResponse` (+`fp_level`)

## Generation Script

**New file: `scripts/generate_fp_content.py`**

Bulk content generation with topic pools organized by complexity:
- **Tier 1** (A-D): Concrete nouns — "a cat", "a dog", "a ball"
- **Tier 2** (E-H): Simple plots — "a lost kitten", "a trip to the park"
- **Tier 3** (I-N): Complex stories — "a brave mouse goes on an adventure"
- **Tier 4** (O-Z2): Sophisticated themes — "a child discovers a hidden library"

```bash
python scripts/generate_fp_content.py                    # All levels, 10 stories each
python scripts/generate_fp_content.py --levels A B C     # Specific levels
python scripts/generate_fp_content.py --count 20         # 20 per level
python scripts/generate_fp_content.py --skip-existing    # Idempotent reruns
```

## Frontend — New Routes

| Route | Component | Description |
|-------|-----------|-------------|
| `/leveled` | `LeveledHomePage` | Level map hub with onboarding |
| `/leveled/:level` | `LeveledStoryListPage` | Stories at a specific level |

## Frontend — New Components

- **`LevelBadge.tsx`** — Reusable styled circle badge with level letter (completed=gold, current=blue+pulse, locked=gray)
- **`LevelTrail.tsx`** — SVG winding trail visualization with animated nodes, shows completed/current/upcoming levels

## Frontend — New Pages

- **`LeveledHomePage.tsx`** — Leveled reading hub:
  - If no F&P level set: inline "Choose Your Starting Level" picker with all 28 levels and descriptions
  - If active: current level badge, progress bar (X/3 stories passed), winding trail map, "Start Reading" button
  - Shows advance/drop suggestions

- **`LeveledStoryListPage.tsx`** — Browse and select stories at current level with style icons and navigation

## Frontend — Modified Pages

- **`ChildLoginPage.tsx`** — After selecting a child, shows a mode selection modal with two cards: "Free Reading" (library) and "Leveled Reading" (level map)
- **`SessionResultPage.tsx`** — For F&P stories: shows level progress bar (X/3 passed), level-up celebration, and "Back to Level Map" button
- **`ParentDashboard.tsx`** — New F&P section per child showing current level, progress stats, and level override dropdown
- **`StoryManagementPage.tsx`** — New "Leveled (F&P)" tab for generating stories at specific levels with level picker and description

## Frontend — API Client

New functions in `services/api.ts`:
- `fetchFPLevels()`, `fetchFPStories(level)`, `fetchFPProgress(childId)`
- `setFPLevel(childId, level)`, `startFPMode(childId, startingLevel)`, `generateFPStory(topic, level, theme?)`
- New TypeScript interfaces: `FPLevelResponse`, `FPProgressResponse`

---

## Files Changed

### New Files (8)
- `backend/endpoints/fp.py`
- `backend/prompts/fp_story_system.txt`
- `backend/prompts/fp_image_prompt_system.txt`
- `frontend/src/components/LevelBadge.tsx`
- `frontend/src/components/LevelTrail.tsx`
- `frontend/src/pages/LeveledHomePage.tsx`
- `frontend/src/pages/LeveledStoryListPage.tsx`
- `scripts/generate_fp_content.py`

### Modified Files (15)
- `backend/database.py`
- `backend/endpoints/children.py`
- `backend/endpoints/sessions.py`
- `backend/endpoints/stories.py`
- `backend/main.py`
- `backend/models/api_models.py`
- `backend/services/ollama_client.py`
- `backend/services/story_pipeline.py`
- `backend/worker.py`
- `frontend/src/App.tsx`
- `frontend/src/pages/ChildLoginPage.tsx`
- `frontend/src/pages/ParentDashboard.tsx`
- `frontend/src/pages/SessionResultPage.tsx`
- `frontend/src/pages/StoryManagementPage.tsx`
- `frontend/src/services/api.ts`
