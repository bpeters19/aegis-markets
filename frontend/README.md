# Aegis Markets Dashboard

Next.js and TypeScript frontend for the Aegis Markets backtest API. See the [main README](../README.md) for the full project.

## Run locally

Start the backend first (from `backend/`: `uvicorn app.main:app --reload`), then from `frontend/`:

- `npm install`
- `npm run dev` and open http://localhost:3000

## API types

Types in `src/lib/api-schema.ts` are generated from the backend's OpenAPI schema. With the backend running, regenerate them after any API change:

- `npm run gen:api`
