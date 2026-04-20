import http from 'http';
import { readFileSync } from 'fs';
import { dirname, join } from 'path';
import { fileURLToPath } from 'url';

const __dirname = dirname(fileURLToPath(import.meta.url));

const routes = {
  'POST /auth/login':              readFileSync(join(__dirname, 'api-mocks/responses/auth-login.json'), 'utf8'),
  'GET /auth/me':                  readFileSync(join(__dirname, 'api-mocks/responses/auth-me.json'), 'utf8'),
  'GET /auth/me/linked-accounts':  readFileSync(join(__dirname, 'api-mocks/responses/linked-accounts.json'), 'utf8'),
  'GET /auth/me/share-tokens':     readFileSync(join(__dirname, 'api-mocks/responses/share-tokens.json'), 'utf8'),
  'GET /auth/me/notifications':    readFileSync(join(__dirname, 'api-mocks/responses/notifications.json'), 'utf8'),
};

const server = http.createServer((req, res) => {
  const key = `${req.method} ${req.url}`;

  // Playwright polls GET / to detect when the server is ready.
  if (key === 'GET /') {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ status: 'ok' }));
    return;
  }
  if (key === 'HEAD /') {
    res.writeHead(200);
    res.end();
    return;
  }

  const body = routes[key];
  if (body) {
    res.writeHead(200, { 'Content-Type': 'application/json' });
    res.end(body);
  } else {
    res.writeHead(500, { 'Content-Type': 'application/json' });
    res.end(JSON.stringify({ detail: `No mock for ${req.method} ${req.url}` }));
  }
});

const PORT = 8001;
server.listen(PORT, () => {
  console.log(`Mock API server running on http://localhost:${PORT}`);
});
