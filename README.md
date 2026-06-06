# Natura Bissé · Brand Intelligence Dashboard

Stack: Node.js + Express + HTML vanilla · Supabase · OpenRouter

## Estructura

```
natura-bisse-dashboard/
├── server.js          ← API Express (stats + chat)
├── package.json
├── .env.example
└── public/
    └── index.html     ← Dashboard completo (HTML/CSS/JS)
```

## Setup local

```bash
cp .env.example .env
# Edita .env con tus credenciales
npm install
npm run dev
# → http://localhost:3000
```

## Variables de entorno

| Variable | Dónde encontrarla |
|---|---|
| `SUPABASE_URL` | Supabase → Settings → API → Project URL |
| `SUPABASE_ANON_KEY` | Supabase → Settings → API → anon/public |
| `OPENROUTER_API_KEY` | openrouter.ai → Keys |

## Deploy en Render

1. Sube este repo a GitHub
2. Render → **New Web Service** → conecta el repo
3. Configuración:
   - **Build command:** `npm install`
   - **Start command:** `node server.js`
   - **Node version:** 20
4. Render → Environment → añade las 3 variables del `.env`
5. Deploy

## SQL Supabase (una vez)

```sql
CREATE TABLE menciones (
  id          BIGSERIAL PRIMARY KEY,
  fuente      TEXT,
  titulo      TEXT,
  url         TEXT UNIQUE,
  snippet     TEXT,
  fecha       TIMESTAMPTZ,
  likes       INT,
  comentarios INT,
  plays       INT,
  score       INT,
  created_at  TIMESTAMPTZ DEFAULT NOW()
);
```

## Flujo completo

```
n8n (07:00 diario)
  └── recolecta menciones
        └── upsert → Supabase

Render (siempre activo)
  └── GET /api/stats  ← lee Supabase → dashboard
  └── POST /api/chat  ← lee Supabase + OpenRouter → respuesta IA
```
