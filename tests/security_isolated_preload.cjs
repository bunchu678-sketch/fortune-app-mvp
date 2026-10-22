// Routing adapter for the unchanged existing UI suites. Assertions and application logic are preserved.
// NODE_OPTIONS=--require=<absolute path> propagates the adapter to owned test children.
const Module = require('node:module');
const path = require('node:path');
const fs = require('node:fs');
const child = require('node:child_process');
const testRoot = path.resolve(__dirname);
if (process.env.FORTUNE_TEST_PRODUCTION === '1') throw Error('Security UI adapter is localhost-only');
const web = Number(process.env.FORTUNE_SECURITY_WEB_PORT);
const api = Number(process.env.FORTUNE_SECURITY_API_PORT);
if (![web, api].every(p => Number.isInteger(p) && p >= 1024 && p <= 65535) ||
    web === api || [web, api].some(p => [3000, 8765].includes(p))) {
  throw Error('Explicit isolated web/API ports required');
}
const compile = Module.prototype._compile;
Module.prototype._compile = function(source, filename) {
  if (path.dirname(filename) === testRoot && filename !== __filename && filename.endsWith('.cjs')) {
    source = source.replace(/\b3000\b/g, String(web)).replace(/\b8765\b/g, String(api));
    source = source.replace(/path\.join\(root,\s*'\.venv',\s*'Scripts',\s*'python\.exe'\)/g, 'process.env.FORTUNE_TEST_PYTHON');
  }
  return compile.call(this, source, filename);
};
const spawn = child.spawn;
child.spawn = function(exe, args, options) {
  if (args?.some(s => typeof s === 'string' && s.replaceAll('\\', '/').endsWith('fortune-next-app/backend/server.py'))) {
    const backend = path.resolve(testRoot, '../fortune-next-app/backend');
    args = ['-B', '-m', 'uvicorn', 'server:app', '--app-dir', backend, '--host', '127.0.0.1', '--port', String(api), '--no-access-log'];
  }
  const proc = spawn.call(this, exe, args, options);
  if (process.env.FORTUNE_SECURITY_SERVER_LOG && proc.stderr) {
    proc.stderr.on('data', data => fs.appendFileSync(process.env.FORTUNE_SECURITY_SERVER_LOG, data));
  }
  return proc;
};
if (process.env.PLAYWRIGHT_MODULE) {
  const pw = require(process.env.PLAYWRIGHT_MODULE);
  const launch = pw.chromium.launch.bind(pw.chromium);
  pw.chromium.launch = async (...args) => {
    const browser = await launch(...args);
    const newContext = browser.newContext.bind(browser);
    browser.newContext = async (...options) => {
      const context = await newContext(...options);
      context.on('page', page => {
        page.on('response', response => {
          if (new URL(response.url()).pathname === '/api/export/pdf') {
            console.log('PDF_HTTP_STATUS=' + response.status());
            if (!response.ok()) response.text().then(body => console.log('PDF_ERROR=' + body.slice(0, 1000)));
          }
        });
        page.on('requestfailed', request => {
          if (new URL(request.url()).pathname === '/api/export/pdf') console.log('PDF_TRANSPORT_FAILURE=' + request.failure()?.errorText);
        });
      });
      return context;
    };
    return browser;
  };
}
