const fs = await import('node:fs');
const cfg = JSON.parse(fs.readFileSync('/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/aa21e6c5-5658-41f5-961a-9993a8cf3d37/scratchpad/qqdoc/ext/space2/cfg.json', 'utf8'));
const task = await taskSpaces.useOrCreate('读QQ文档目录');
page.setDefaultTimeout(20000);
const done = new Set(fs.readdirSync(cfg.dir).map(f => f.replace(/\.json$/, '')));
let todo = [cfg.start].filter(x => !done.has(x));
const log = [];
for (let round = 0; round < 8 && todo.length; round++) {
  for (const id of todo) {
    await page.goto(`${cfg.url}?p=${id}`);
    let st = null;
    for (let k = 0; k < 40; k++) {
      await new Promise(r => setTimeout(r, 600));
      st = await page.evaluate((id) => { const c = window.__coreEditor?.dataCore?.defaultMemoryCache?.cache; if (!c) return null; const pg = c.get('block:' + id)?.value; if (!pg) return {ok: false}; const kids = pg.children || []; const missing = kids.filter(x => !c.get('block:' + x)).length; return {ok: missing === 0, kids: kids.length, missing}; }, id);
      if (st && st.ok) break;
    }
    await new Promise(r => setTimeout(r, 1500));
    const dump = await page.evaluate(() => { const c = window.__coreEditor.dataCore.defaultMemoryCache.cache; const out = {}; for (const [k, v] of c) { try { out[k] = JSON.parse(JSON.stringify(v?.value ?? v, (kk, vv) => typeof vv === 'function' ? undefined : vv)); } catch (e) {} } return out; });
    fs.writeFileSync(`${cfg.dir}/${id}.json`, JSON.stringify(dump));
    done.add(id);
    log.push(id + ' ' + JSON.stringify(st));
  }
  // next: every page block in any dump of this space
  const next = new Set();
  for (const f of fs.readdirSync(cfg.dir)) {
    const d = JSON.parse(fs.readFileSync(`${cfg.dir}/${f}`, 'utf8'));
    for (const [k, v] of Object.entries(d)) {
      if (k.startsWith('block:') && v && v.type === 'page' && v.spaceId === cfg.spaceId) next.add(v.id);
      const s = JSON.stringify(v || {});
      for (const m of s.matchAll(new RegExp(cfg.key + '\\?p=([A-Za-z0-9]{22})', 'g'))) next.add(m[1]);
    }
  }
  todo = [...next].filter(x => !done.has(x));
  log.push(`round ${round} next ${todo.length}`);
}
console.log(log.join('\n'));
