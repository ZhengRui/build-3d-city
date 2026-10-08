// cdp.mjs: drive a standalone Chrome over its DevTools port (Node 22+, no dependencies). Use it when the
// chrome-devtools MCP is unavailable or shared. Every call attaches to the first page tab, does one thing
// and detaches, so page state (window.__viewer, hooks you installed) survives between calls, but DevTools
// session state (device-metrics emulation, network throttling) does not: use Chrome flags for those (see
// references/testing-and-tooling.md), or do the whole measurement inside one `eval`.
//
// Start a private Chrome first (own profile dir, own port; never the user's browser):
//   google-chrome --user-data-dir=$SCRATCH/chrome-test --remote-debugging-port=9333 --no-first-run \
//     --no-default-browser-check --window-size=1280,800 about:blank &     # record $! and kill that PID later
//   (WebGPU on Linux: add --enable-unsafe-webgpu --enable-features=Vulkan,VulkanFromANGLE,DefaultANGLEVulkan
//    --use-angle=vulkan; a 2x screen: add --force-device-scale-factor=2)
//
// Usage (CDP_PORT defaults to 9333):
//   node cdp.mjs nav <url>              navigate the page (returns at once; wait with eval)
//   node cdp.mjs eval '<js>'            evaluate an expression (awaits promises, 10 min timeout), print JSON
//   node cdp.mjs evalfile <file.js>     the same with the expression read from a file
//   node cdp.mjs shot <file.png>        screenshot of the page
//   node cdp.mjs console [ms]           print console messages and errors for ms (default 5000)
//   node cdp.mjs profile '<js>'         CPU profile while the expression runs: top self times, then total
//                                       times of viewer functions (PROFILE_FILTER regexp on the script URL,
//                                       default main|night|facade|water|trees|cars|rooftops|ground)
// Examples:
//   node cdp.mjs nav "http://127.0.0.1:8762/?view=<a view name from city.json, URL-encoded>"
//   node cdp.mjs eval "(async () => { while (!window.__ready) await new Promise(r => setTimeout(r, 500));
//     return document.getElementById('stats').innerText; })()"
//   node cdp.mjs shot /tmp/day.png
import { readFileSync, writeFileSync } from 'node:fs';

const PORT = Number(process.env.CDP_PORT) || 9333;
const [cmd, arg] = process.argv.slice(2);
if (!cmd) {
  console.error('usage: node cdp.mjs nav <url> | eval <js> | evalfile <file> | shot <file> | console [ms] | profile <js>');
  process.exit(2);
}
const list = await (await fetch(`http://127.0.0.1:${PORT}/json/list`)).json();
const page = list.find((t) => t.type === 'page');
if (!page) throw new Error(`no page tab on port ${PORT}`);
const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((r, e) => { ws.addEventListener('open', r); ws.addEventListener('error', e); });
let id = 0;
const waiting = new Map(), events = [];
ws.addEventListener('message', (e) => {
  const m = JSON.parse(e.data);
  if (m.id && waiting.has(m.id)) { waiting.get(m.id)(m); waiting.delete(m.id); } else if (m.method) events.push(m);
});
const send = (method, params = {}) => new Promise((r) => { const i = ++id; waiting.set(i, r); ws.send(JSON.stringify({ id: i, method, params })); });
const evaluate = async (expression) => {
  const r = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true, timeout: 600000 });
  if (r.result?.exceptionDetails) return { exception: r.result.exceptionDetails.exception?.description ?? r.result.exceptionDetails.text };
  return r.result?.result?.value ?? r.result ?? r.error;
};

try {
  if (cmd === 'nav') {
    await send('Page.enable');
    const r = await send('Page.navigate', { url: arg });
    console.log(JSON.stringify(r.result ?? r.error));
  } else if (cmd === 'eval' || cmd === 'evalfile') {
    console.log(JSON.stringify(await evaluate(cmd === 'eval' ? arg : readFileSync(arg, 'utf8'))));
  } else if (cmd === 'shot') {
    await send('Page.bringToFront');
    const r = await send('Page.captureScreenshot', { format: 'png' });
    writeFileSync(arg, Buffer.from(r.result.data, 'base64'));
    console.log('saved', arg);
  } else if (cmd === 'console') {
    await send('Runtime.enable');
    await send('Log.enable');
    await new Promise((r) => setTimeout(r, Number(arg) || 5000));
    for (const e of events) {
      if (e.method === 'Runtime.consoleAPICalled') {
        console.log(`[${e.params.type}]`, e.params.args.map((a) => a.value ?? a.description ?? a.type).join(' '));
      } else if (e.method === 'Runtime.exceptionThrown') {
        console.log('[exception]', e.params.exceptionDetails.exception?.description ?? e.params.exceptionDetails.text);
      } else if (e.method === 'Log.entryAdded') {
        console.log(`[${e.params.entry.level}]`, e.params.entry.text, e.params.entry.url ?? '');
      }
    }
  } else if (cmd === 'profile') {
    const filter = new RegExp(process.env.PROFILE_FILTER ?? '(main|night|facade|water|trees|cars|rooftops|ground)\\.js');
    await send('Profiler.enable');
    await send('Profiler.setSamplingInterval', { interval: 500 });
    await send('Profiler.start');
    const value = await evaluate(arg);
    const { result: { profile } } = await send('Profiler.stop');
    console.log(JSON.stringify(value));
    const byId = new Map(profile.nodes.map((n) => [n.id, n]));
    const name = (f) => `${f.functionName || '(anon)'} ${f.url.split('/').pop().split('?')[0]}:${f.lineNumber + 1}`;
    const dt = profile.timeDeltas;
    // self time per function
    const self = new Map();
    profile.samples.forEach((sid, k) => { const key = name(byId.get(sid).callFrame); self.set(key, (self.get(key) ?? 0) + (dt[k] ?? 0) / 1000); });
    const top = (m) => [...m].sort((a, b) => b[1] - a[1]).slice(0, 25).map(([k, v]) => `${v.toFixed(0).padStart(7)} ms  ${k}`).join('\n');
    console.log(top(self));
    // total time per viewer function on the stack (each counted once per sample)
    const parent = new Map();
    for (const n of profile.nodes) for (const c of n.children ?? []) parent.set(c, n.id);
    const total = new Map();
    profile.samples.forEach((sid, k) => {
      const seen = new Set();
      for (let x = sid; x !== undefined; x = parent.get(x)) {
        const f = byId.get(x).callFrame;
        if (!filter.test(f.url)) continue;
        const key = name(f);
        if (seen.has(key)) continue;
        seen.add(key);
        total.set(key, (total.get(key) ?? 0) + (dt[k] ?? 0) / 1000);
      }
    });
    console.log('--- total (viewer functions)');
    console.log(top(total));
  } else {
    console.error('unknown command', cmd);
    process.exitCode = 2;
  }
} finally {
  ws.close();
}
