const fs = await import('node:fs');
const D = '/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/aa21e6c5-5658-41f5-961a-9993a8cf3d37/scratchpad/qqdoc';
const tree = JSON.parse(fs.readFileSync(D + '/tree.json', 'utf8'));
const extra = ['p31mHjuH1cVgqWYczKTC5s', 'WJNJBOl9tQtVZ0GEuD8UaP', 'TqfnbyBtvpeL1zHaxtMv6c', '0DrfFS20HWvPwn5PHyCXKb'];
const ids = JSON.parse(fs.readFileSync(D + '/todo.json', 'utf8'));
const task = await taskSpaces.useOrCreate('读QQ文档目录');
page.setDefaultTimeout(20000);
const log = [];
for (const id of ids) {
  const f = `${D}/blocks/${id}.json`;
  if (fs.existsSync(f)) continue;
  try {
    await page.goto(`https://docs.qq.com/aio/DTmluZ1diWlpQZldw?p=${id}`);
    let st = null;
    for (let k = 0; k < 40; k++) {
      await new Promise(r => setTimeout(r, 600));
      st = await page.evaluate((id) => {
        const c = window.__coreEditor?.dataCore?.defaultMemoryCache?.cache;
        if (!c) return null;
        const pg = c.get('block:' + id)?.value;
        if (!pg) return {ok: false, why: 'nopage'};
        const kids = pg.children || [];
        const missing = kids.filter(x => !c.get('block:' + x)).length;
        return {ok: missing === 0, kids: kids.length, missing, n: c.size};
      }, id);
      if (st && st.ok) break;
    }
    await new Promise(r => setTimeout(r, 1500));
    const dump = await page.evaluate(() => {
      const c = window.__coreEditor.dataCore.defaultMemoryCache.cache;
      const out = {};
      for (const [k, v] of c) { try { out[k] = JSON.parse(JSON.stringify(v?.value ?? v, (kk, vv) => typeof vv === 'function' ? undefined : vv)); } catch (e) {} }
      return out;
    });
    fs.writeFileSync(f, JSON.stringify(dump));
    log.push(`${id} ${JSON.stringify(st)} entries=${Object.keys(dump).length}`);
  } catch (e) { log.push(`${id} ERROR ${String(e).slice(0, 200)}`); }
}
fs.appendFileSync(`${D}/crawl2.log`, '\n' + log.join('\n'));
console.log('done', log.length);
