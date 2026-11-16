/**
 * tiny-dawn-75f1 — AI tutor + taplist proxy for brooksgroves.com
 * Locked-down version, Nov 16 2026 (after someone used the old open Worker
 * to send ~1M-token requests to Fable/Opus on Brooks's key).
 *
 * What changed from the old Worker:
 *  - The MODEL is fixed here. Whatever model a caller asks for is ignored.
 *  - max_tokens is capped (MAX_OUT). Size limits on the system prompt and the
 *    questions, so nobody can send a book's worth of text.
 *  - Only brooksgroves.com (and localhost for testing) get CORS access.
 *  - Optional daily limits per visitor and in total, if a KV namespace is
 *    bound as LIMITS (Settings → Bindings → KV namespace → name it LIMITS;
 *    the existing "hoplove-limits" namespace works). Without it, the size
 *    caps above still apply.
 *  - /proxy only fetches peaksandpints.com (the Outside page taplist).
 *
 * Secret needed (Settings → Variables and secrets): ANTHROPIC_API_KEY
 *
 * Request formats it accepts (same as before, so no page changes needed):
 *   { system, messages }      → returns Anthropic's response (data.content[0].text)
 *   { question, lesson }      → returns { answer } (quantum physics page)
 */

const MODEL = 'claude-sonnet-4-5';
const MAX_OUT = 1000;              // longest answer, in tokens
const MAX_SYSTEM_CHARS = 6000;     // the page's tutor instructions
const MAX_MESSAGES = 12;           // volcanology keeps a short chat history
const MAX_MESSAGE_CHARS = 4000;    // one question
const MAX_TOTAL_CHARS = 16000;     // everything in one request
const PER_VISITOR_PER_DAY = 40;
const TOTAL_PER_DAY = 300;

const ALLOWED_ORIGINS = [
  'https://brooksgroves.com',
  'https://www.brooksgroves.com',
  'https://bdgroves.github.io',
  'http://localhost:8000',
  'http://127.0.0.1:8000',
];
const PROXY_HOSTS = ['www.peaksandpints.com', 'peaksandpints.com'];

function cors(origin) {
  const ok = ALLOWED_ORIGINS.includes(origin);
  return {
    'Access-Control-Allow-Origin': ok ? origin : ALLOWED_ORIGINS[0],
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Vary': 'Origin',
  };
}
function json(obj, status, headers) {
  return new Response(JSON.stringify(obj), {
    status: status || 200,
    headers: Object.assign({ 'Content-Type': 'application/json' }, headers),
  });
}

async function overLimit(env, request) {
  if (!env.LIMITS) return false;
  const day = new Date().toISOString().slice(0, 10);
  const ip = request.headers.get('CF-Connecting-IP') || 'unknown';
  const kTotal = 'tutor:' + day + ':total';
  const kIp = 'tutor:' + day + ':ip:' + ip;
  const [t, v] = await Promise.all([env.LIMITS.get(kTotal), env.LIMITS.get(kIp)]);
  const total = Number(t || 0), mine = Number(v || 0);
  if (total >= TOTAL_PER_DAY || mine >= PER_VISITOR_PER_DAY) return true;
  const ttl = { expirationTtl: 60 * 60 * 26 };
  await Promise.all([env.LIMITS.put(kTotal, String(total + 1), ttl), env.LIMITS.put(kIp, String(mine + 1), ttl)]);
  return false;
}

function textOf(content) {
  if (typeof content === 'string') return content;
  if (Array.isArray(content)) {
    // text only — no images or documents through this Worker
    return content.filter(b => b && b.type === 'text').map(b => String(b.text || '')).join('\n');
  }
  return '';
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get('Origin') || '';
    const h = cors(origin);

    if (request.method === 'OPTIONS') return new Response(null, { status: 204, headers: h });

    // ---- Taplist proxy (Outside page) — Peaks and Pints only ----
    if (request.method === 'GET' && url.pathname === '/proxy') {
      let target;
      try { target = new URL(url.searchParams.get('url') || ''); } catch (e) { return json({ error: 'Bad url' }, 400, h); }
      if (target.protocol !== 'https:' || !PROXY_HOSTS.includes(target.hostname)) {
        return json({ error: 'That site is not allowed.' }, 403, h);
      }
      const r = await fetch(target.toString(), { headers: { 'User-Agent': 'brooksgroves.com taplist' } });
      return new Response(await r.text(), { status: r.status, headers: Object.assign({ 'Content-Type': 'text/html; charset=utf-8' }, h) });
    }

    if (request.method !== 'POST' || url.pathname !== '/') return json({ error: 'Not found' }, 404, h);

    // Browsers always send Origin on these requests; refuse other sites.
    if (origin && !ALLOWED_ORIGINS.includes(origin)) return json({ error: 'Not allowed.' }, 403, h);
    if (!env.ANTHROPIC_API_KEY) return json({ error: 'Tutor is not set up.' }, 500, h);

    const raw = await request.text();
    if (raw.length > MAX_TOTAL_CHARS + MAX_SYSTEM_CHARS + 2000) return json({ error: 'That question is too long.' }, 413, h);
    let body;
    try { body = JSON.parse(raw); } catch (e) { return json({ error: 'Bad request' }, 400, h); }

    // Build the request ourselves — never forward the caller's body as-is.
    let system, messages, legacy = false;
    if (typeof body.question === 'string') {
      legacy = true;
      const lesson = String(body.lesson || '').slice(0, 200);
      system = 'You are a friendly, clear tutor for a self-directed curriculum on quantum physics for a curious adult with a science background. ' +
        (lesson ? 'The learner is on the lesson "' + lesson + '". ' : '') +
        'Answer in a few short paragraphs, plain language first, then the key equation or idea if it helps. Stay on physics.';
      messages = [{ role: 'user', content: body.question }];
    } else {
      system = String(body.system || 'You are a helpful tutor.');
      messages = Array.isArray(body.messages) ? body.messages : [];
    }

    if (system.length > MAX_SYSTEM_CHARS) return json({ error: 'Too long.' }, 413, h);
    messages = messages.slice(-MAX_MESSAGES)
      .map(m => ({ role: m && m.role === 'assistant' ? 'assistant' : 'user', content: textOf(m && m.content).slice(0, MAX_MESSAGE_CHARS) }))
      .filter(m => m.content.trim());
    while (messages.length && messages[0].role !== 'user') messages.shift();
    if (!messages.length) return json({ error: 'Please type a question.' }, 400, h);
    const totalChars = system.length + messages.reduce((n, m) => n + m.content.length, 0);
    if (totalChars > MAX_TOTAL_CHARS + MAX_SYSTEM_CHARS) return json({ error: 'That question is too long.' }, 413, h);

    if (await overLimit(env, request)) {
      return json({ error: 'The tutor has answered a lot of questions today. Please try again tomorrow.' }, 429, h);
    }

    const upstream = await fetch('https://api.anthropic.com/v1/messages', {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-api-key': env.ANTHROPIC_API_KEY,
        'anthropic-version': '2023-06-01',
      },
      body: JSON.stringify({ model: MODEL, max_tokens: MAX_OUT, system, messages }),
    });
    const data = await upstream.json().catch(() => ({}));
    if (!upstream.ok) {
      return json({ error: 'The tutor is unavailable right now.', detail: (data.error && data.error.message) || '' }, 502, h);
    }
    if (legacy) return json({ answer: (data.content && data.content[0] && data.content[0].text) || '' }, 200, h);
    return json({ content: data.content || [] }, 200, h);
  },
};
