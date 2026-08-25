/**
 * DFT E2E Platform — Anthropic API Proxy Server
 * 
 * This server sits between your browser and the Anthropic API.
 * It injects your ANTHROPIC_API_KEY from the environment so the
 * key never appears in client-side code.
 *
 * Usage:
 *   ANTHROPIC_API_KEY=sk-ant-... node server.js
 *
 * Then in a separate terminal:
 *   npm start
 */

const http = require('http');
const https = require('https');

const PORT = 3001;
const ANTHROPIC_HOST = 'api.anthropic.com';
const API_KEY = process.env.ANTHROPIC_API_KEY;

if (!API_KEY) {
  console.error('\n❌  ANTHROPIC_API_KEY environment variable not set.');
  console.error('    Run: ANTHROPIC_API_KEY=sk-ant-... node server.js\n');
  process.exit(1);
}

const server = http.createServer((req, res) => {
  // CORS headers so React dev server (port 3000) can call us
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type, anthropic-version, x-api-key');

  if (req.method === 'OPTIONS') {
    res.writeHead(204);
    res.end();
    return;
  }

  if (req.method !== 'POST' || !req.url.startsWith('/v1/')) {
    res.writeHead(404);
    res.end(JSON.stringify({ error: 'Not found' }));
    return;
  }

  let body = '';
  req.on('data', chunk => { body += chunk; });
  req.on('end', () => {
    const options = {
      hostname: ANTHROPIC_HOST,
      port: 443,
      path: req.url,
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'anthropic-version': '2023-06-01',
        'x-api-key': API_KEY,
      },
    };

    const proxyReq = https.request(options, proxyRes => {
      res.writeHead(proxyRes.statusCode, {
        'Content-Type': proxyRes.headers['content-type'] || 'application/json',
        'Access-Control-Allow-Origin': '*',
      });
      proxyRes.pipe(res);
    });

    proxyReq.on('error', err => {
      console.error('Proxy error:', err.message);
      res.writeHead(502);
      res.end(JSON.stringify({ error: 'Proxy error', detail: err.message }));
    });

    proxyReq.write(body);
    proxyReq.end();
  });
});

server.listen(PORT, () => {
  console.log(`\n✅  Anthropic API proxy running on http://localhost:${PORT}`);
  console.log(`    Forwarding to https://${ANTHROPIC_HOST}`);
  console.log(`    API key: ${API_KEY.slice(0, 12)}...${API_KEY.slice(-4)}\n`);
});
