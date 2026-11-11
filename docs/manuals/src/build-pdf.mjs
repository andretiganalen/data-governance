// Print the manuals to PDF via headless Chrome (DevTools protocol; Node 22, no npm deps).
// Usage: node build-pdf.mjs <out-dir> '<json [{src, out, title}]>'   (called by rilis.py)
import { spawn } from 'node:child_process';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve, dirname } from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const here = dirname(fileURLToPath(import.meta.url));
const outDir = resolve(process.argv[2] || join(here, '..'));
const jobs = JSON.parse(process.argv[3]);
const CHROME = process.env.CHROME || '/usr/bin/google-chrome';
const PORT = 9333;


const profile = mkdtempSync(join(tmpdir(), 'chrome-'));
const chrome = spawn(CHROME, ['--headless=new', '--no-sandbox', '--disable-gpu', '--allow-file-access-from-files',
  `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' });

const sleep = ms => new Promise(r => setTimeout(r, ms));
let target;
for (let i = 0; i < 50 && !target; i++) {
  try { target = (await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json()).find(t => t.type === 'page'); }
  catch { await sleep(200); }
}
const ws = new WebSocket(target.webSocketDebuggerUrl);
await new Promise(r => ws.addEventListener('open', r, { once: true }));
let id = 0; const pending = new Map(); const waiters = [];
ws.addEventListener('message', ev => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { const p = pending.get(m.id); pending.delete(m.id); m.error ? p.rej(new Error(m.error.message)) : p.res(m.result); }
  else if (m.method) waiters.filter(w => w.method === m.method).forEach(w => { waiters.splice(waiters.indexOf(w), 1); w.res(m.params); });
});
const send = (method, params = {}) => new Promise((res, rej) => { const i = ++id; pending.set(i, { res, rej }); ws.send(JSON.stringify({ id: i, method, params })); });
const once = method => new Promise(res => waiters.push({ method, res }));

await send('Page.enable');
const foot = title => `<div style="width:100%;font:7.5px 'UIx Poppins',Arial,sans-serif;color:#6a7282;padding:0 18mm;display:flex;justify-content:space-between">
  <span>Len Data Governance · ${title}</span><span>Halaman <span class="pageNumber"></span> / <span class="totalPages"></span></span></div>`;

for (const { src, out: file, title } of jobs) {
  const loaded = once('Page.loadEventFired');
  await send('Page.navigate', { url: pathToFileURL(join(here, src)).href });
  await loaded;
  await send('Runtime.evaluate', { expression: 'document.fonts.ready.then(() => true)', awaitPromise: true });
  await sleep(300);
  const err = await send('Runtime.evaluate', { expression: 'window.__err || ""', returnByValue: true });
  if (err.result.value) throw new Error(`${src}: ${err.result.value}`);
  const { data } = await send('Page.printToPDF', {
    printBackground: true, preferCSSPageSize: true, displayHeaderFooter: true,
    headerTemplate: '<div></div>', footerTemplate: foot(title),
  });
  writeFileSync(join(outDir, file), Buffer.from(data, 'base64'));
  console.log('wrote', join(outDir, file));
}
ws.close(); chrome.kill(); await sleep(300); rmSync(profile, { recursive: true, force: true });
