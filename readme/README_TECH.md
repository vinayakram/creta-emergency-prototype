# Creta Emergency Assistant — Prototype v1 (Technical README)

## What’s inside
- `backend/` FastAPI API
- `frontend/` React + React Router UI
- `evals/` Braintrust eval script (optional)

## Backend endpoints
- `GET /health`
- `POST /query` → returns `{ steps, warnings, tools, sources }`

## Requirements
- Windows 11
- Python 3.13.x
- Node 18+

## Qdrant mode
This prototype uses **Qdrant local mode** by default (no Docker needed).
Vectors stored at `backend/data/qdrant/`.

If you want Qdrant server mode, set `QDRANT_URL` in `backend/.env` and unset `QDRANT_PATH`.

## Run (power users)
```powershell
cd backend
py -3.13 -m venv .venv
. .\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env

# Put PDF at backend\data\creta_manual.pdf
python -m app.rag.ingest --pdf data\creta_manual.pdf

uvicorn app.main:app --reload --port 8000
```

Frontend:
```powershell
cd ..\frontend
npm install
copy .env.example .env
npm run dev
```

Open http://localhost:5173
