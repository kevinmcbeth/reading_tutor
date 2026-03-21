# Reading Tutor — Usage Guide

An AI-powered reading tutor that generates illustrated stories with audio for children ages 4–7.

## Prerequisites

- **Python 3** (with venv)
- **Node.js 18+**
- **PostgreSQL**
- **Redis**
- **Ollama** with `qwen3:30b` model
- **ComfyUI** (image generation)
- **GPU with CUDA** recommended (for TTS and speech recognition)

## Quick Start

```bash
# 1. One-time setup (creates venv, installs dependencies)
./scripts/setup.sh

# 2. Copy and edit environment config
cp backend/.env.example backend/.env
# Edit backend/.env with your settings

# 3. Ollama and Redis run as systemd services (enabled on boot)
#    Verify they're running:
sudo systemctl status ollama
sudo systemctl status redis-server
# Start ComfyUI
# Ensure PostgreSQL is running

# 4. Start the app (backend + frontend)
./scripts/dev.sh
```

- **Frontend**: http://localhost:3000
- **API docs**: http://localhost:8000/docs

## Environment Variables

Edit `backend/.env` (see `backend/.env.example` for template):

| Variable | Default | Description |
|---|---|---|
| `BACKEND_PORT` | `8000` | API server port |
| `FRONTEND_URL` | `http://localhost:3000` | Frontend origin |
| `DATABASE_URL` | — | PostgreSQL connection string |
| `REDIS_URL` | `redis://localhost:6379` | Redis server address |
| `OLLAMA_URL` | `http://localhost:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `qwen3:30b` | LLM model for story generation |
| `COMFYUI_URL` | `http://localhost:8188` | ComfyUI API endpoint |
| `PARENT_PIN` | `1111` | Default parent PIN |
| `JWT_SECRET` | auto-generated | Secret for auth tokens |
| `WHISPER_MODEL` | `base.en` | Speech recognition model |
| `WHISPER_DEVICE` | `auto` | GPU/CPU for whisper |
| `REFERENCE_VOICE` | `assets/reference_voice.wav` | TTS reference voice file |

## How It Works

### For Parents

1. **Log in** at `/parent` with your family credentials
2. **Add children** with name, age, and avatar from the parent dashboard
3. **Generate stories** — pick a topic, difficulty (easy/medium/hard), and art style (cartoon, watercolor, realistic, etc.). Stories are generated in the background via the job queue.
4. **Monitor progress** — the dashboard shows reading analytics per child
5. **Manage the queue** at `/parent/queue` to see generation job status and logs

### For Children

1. **Log in** at `/` by selecting their profile and entering their PIN
2. **Pick a story** from the library at `/library`
3. **Read** — tap words to hear them, speak to read aloud, get scored on pronunciation
4. **See results** — celebration screen with score and stats after each session

## Project Structure

```
reading_tutor/
├── frontend/          # React + TypeScript + Vite + Tailwind
│   └── src/
│       ├── pages/     # Route pages
│       ├── components/# UI components
│       ├── hooks/     # useStorySession, useSpeechRecognition, useAudioPlayer
│       ├── services/  # API client, auth
│       └── context/   # Auth context
├── backend/           # FastAPI + Python
│   ├── main.py        # App entry point
│   ├── config.py      # Settings
│   ├── database.py    # PostgreSQL schema (auto-created on startup)
│   ├── worker.py      # arq background job runner
│   ├── endpoints/     # API routes (parent, children, stories, sessions, generation, speech, assets)
│   └── services/      # AI integrations (ollama, comfyui, tts, whisper, story_pipeline)
├── deploy/            # Production deployment (nginx, systemd, SSL)
├── scripts/           # setup.sh, dev.sh, utilities
└── assets/            # Reference voice, etc.
```

## NPM Scripts (Frontend)

```bash
cd frontend
npm run dev       # Vite dev server on :3000
npm run build     # Production build to dist/
npm run lint      # ESLint
npm run preview   # Preview production build
```

## Production Deployment

```bash
sudo ./deploy/deploy.sh --domain reading-tutor.duckdns.org --duckdns-token YOUR_TOKEN
```

This handles everything: PostgreSQL, Redis, nginx, SSL (Let's Encrypt), systemd services, and DuckDNS dynamic DNS.

To update an existing deployment:

```bash
./deploy/update.sh
```

## Story Generation Pipeline

When a parent requests a story:

1. **Text generation** — Ollama generates the story text with sentence-level image prompts
2. **Image generation** — ComfyUI creates illustrations for each sentence
3. **Audio generation** — F5-TTS generates per-word audio clips
4. Jobs run in the background via Redis + arq. Monitor at `/parent/queue`.

## Utility Scripts

```bash
python3 scripts/generate_100_stories.py      # Bulk generate test stories
python3 scripts/migrate_sqlite_to_pg.py      # Migrate from old SQLite DB
```
