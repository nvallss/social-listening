import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import { createClient } from '@supabase/supabase-js';
import fetch from 'node-fetch';
import path from 'path';
import { fileURLToPath } from 'url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const app = express();
const PORT = process.env.PORT || 3000;

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, 'public')));

const supabase = createClient(
  process.env.SUPABASE_URL,
  process.env.SUPABASE_ANON_KEY
);

// ── GET /api/stats ────────────────────────────────────────────────────────────
// Returns: total, by_source, by_week, top_engagement
app.get('/api/stats', async (req, res) => {
  try {
    const { data, error } = await supabase
      .from('menciones')
      .select('fuente, fecha, likes, comentarios, plays, score, titulo, url, snippet')
      .order('fecha', { ascending: false });

    if (error) return res.status(500).json({ error: error.message });

    // By source
    const by_source = {};
    for (const m of data) {
      by_source[m.fuente] = (by_source[m.fuente] || 0) + 1;
    }

    // By week (last 8 weeks)
    const weeks = {};
    const now = new Date();
    for (const m of data) {
      const d = new Date(m.fecha);
      const diff = Math.floor((now - d) / (7 * 24 * 3600 * 1000));
      if (diff > 7) continue;
      const label = `S-${diff}`;
      if (!weeks[label]) weeks[label] = { label, total: 0 };
      weeks[label].total++;
    }
    const by_week = Object.values(weeks)
      .sort((a, b) => parseInt(b.label.slice(2)) - parseInt(a.label.slice(2)))
      .reverse()
      .map((w, i, arr) => ({ ...w, label: i === arr.length - 1 ? 'Esta semana' : `Hace ${parseInt(w.label.slice(2))}s` }));

    // Top engagement (Instagram + TikTok by likes/plays)
    const top_engagement = data
      .filter(m => m.likes !== null || m.plays !== null)
      .map(m => ({
        fuente: m.fuente,
        titulo: m.titulo,
        url: m.url,
        engagement: (m.likes || 0) + (m.plays || 0) * 0.1 + (m.comentarios || 0) * 2,
        likes: m.likes,
        plays: m.plays,
        comentarios: m.comentarios,
      }))
      .sort((a, b) => b.engagement - a.engagement)
      .slice(0, 5);

    // Recent mentions
    const recent = data.slice(0, 20);

    res.json({
      total: data.length,
      by_source,
      by_week,
      top_engagement,
      recent,
    });
  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── POST /api/chat ────────────────────────────────────────────────────────────
// Body: { message: string, history: [{role, content}] }
app.post('/api/chat', async (req, res) => {
  const { message, history = [] } = req.body;
  if (!message) return res.status(400).json({ error: 'message required' });

  try {
    // Fetch last 200 mentions as context
    const { data: menciones, error } = await supabase
      .from('menciones')
      .select('fuente, titulo, url, snippet, fecha, likes, comentarios, plays, score')
      .order('fecha', { ascending: false })
      .limit(200);

    if (error) return res.status(500).json({ error: error.message });

    const context = menciones.map(m =>
      `[${m.fuente} | ${m.fecha?.slice(0, 10)}] ${m.titulo}${m.snippet ? ' – ' + m.snippet : ''}${m.likes ? ' | ❤️' + m.likes : ''}${m.plays ? ' | ▶️' + m.plays : ''}`
    ).join('\n');

    const systemPrompt = `Eres el Asistente de Inteligencia de Marca para Natura Bissé.
Tienes acceso a las menciones recientes de la marca en redes sociales, medios y blogs.
Responde siempre en español, de forma concisa y útil.
Si te preguntan por datos específicos, basate SOLO en las menciones proporcionadas.
No inventes datos ni URLs.

MENCIONES RECIENTES (${menciones.length} entradas):
${context}`;

    const messages = [
      ...history.slice(-10),
      { role: 'user', content: message }
    ];

    // Use Ollama (local via tunnel) if OPENAI_BASE_URL is set, otherwise fallback to OpenRouter
    const useOllama = !!process.env.OPENAI_BASE_URL;
    const apiUrl = useOllama
      ? `${process.env.OPENAI_BASE_URL}/chat/completions`
      : 'https://openrouter.ai/api/v1/chat/completions';

    const model = useOllama ? 'llama3' : 'anthropic/claude-3.5-haiku';

    const bodyPayload = useOllama
      ? {
          model,
          messages: [
            { role: 'system', content: systemPrompt },
            ...messages
          ],
          stream: false,
        }
      : {
          model,
          messages,
          system: systemPrompt,
          max_tokens: 1000,
        };

    const headers = useOllama
      ? { 'Content-Type': 'application/json' }
      : {
          'Authorization': `Bearer ${process.env.OPENROUTER_API_KEY}`,
          'Content-Type': 'application/json',
          'HTTP-Referer': 'https://natura-bisse-dashboard.onrender.com',
          'X-Title': 'Natura Bissé Brand Intelligence',
        };

    const response = await fetch(apiUrl, {
      method: 'POST',
      headers,
      body: JSON.stringify(bodyPayload),
    });

    const result = await response.json();
    const reply = result.choices?.[0]?.message?.content || 'Sin respuesta';
    res.json({ reply });

  } catch (err) {
    res.status(500).json({ error: err.message });
  }
});

// ── SPA fallback ──────────────────────────────────────────────────────────────
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

app.listen(PORT, () => console.log(`🌿 Natura Bissé Dashboard → http://localhost:${PORT}`));
