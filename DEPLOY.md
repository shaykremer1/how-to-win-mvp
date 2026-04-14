# Deploy

## Minimal final actions (you only do this)

1. **Render — Web Service**  
   Connect repo. Use **Build:** `pip install -r backend/requirements.txt` and **Start:** `python -m uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT`  
   **Health check path:** `/health/live`  
   Set env: `PYTHON_VERSION=3.11.8`, all `DB_*`, `CORS_ORIGINS` (your Vercel production URL, no trailing `/`).  
   Optional: `CORS_ORIGIN_REGEX=https://.*\\.vercel\\.app` so preview deployments work without extra clicks.  
   Deploy → copy the **HTTPS API URL**.

2. **Vercel — New Project**  
   **Root Directory:** `frontend`  
   Env: `VITE_API_BASE` = that API URL (no `/api` suffix).  
   Deploy.

3. If you did **not** set `CORS_ORIGIN_REGEX`, go back to **Render** → add the exact Vercel URL to `CORS_ORIGINS` → **Manual Deploy** once.

---

## Optional: Blueprint

**Render → New + → Blueprint** → pick repo → uses `render.yaml`. You still add `DB_*`, `CORS_ORIGINS`, and optionally `CORS_ORIGIN_REGEX` in the dashboard (not stored in git).

---

## Reference

| Where | Variable | Example |
|-------|----------|---------|
| Render | `CORS_ORIGINS` | `https://myapp.vercel.app` |
| Render | `CORS_ORIGIN_REGEX` (optional) | `https://.*\.vercel\.app` |
| Vercel | `VITE_API_BASE` | `https://my-api.onrender.com` |

**Local dev:** repo root `python -m uvicorn backend.app.main:app --reload --port 8000` · `frontend` with `VITE_API_BASE=/api` and `npm run dev`.

**CI:** `.github/workflows/ci.yml` runs `npm ci && npm run build` and a Python import check on every push/PR.
