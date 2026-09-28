const fs = await import('node:fs');
const D = '/tmp/claude-1000/-home-zhuran24-zmd-research-fresh/aa21e6c5-5658-41f5-961a-9993a8cf3d37/scratchpad/qqdoc';
const tree = JSON.parse(fs.readFileSync(D + '/tree.json', 'utf8'));
const task = await taskSpaces.useOrCreate('读QQ文档目录');
page.setDefaultTimeout(20000);
const summary = [];
for (let i = 0; i < tree.length; i++) {
  const t = tree[i];
  const idx = String(i).padStart(3, '0');
  if (fs.existsSync(`${D}/pages/${idx}.json`)) { summary.push(JSON.parse(fs.readFileSync(`${D}/pages/${idx}.json`, 'utf8')).meta); continue; }
  try {
    await page.goto(`https://docs.qq.com/aio/DTmluZ1diWlpQZldw?p=${t.id}`);
    let r = null;
    for (let k = 0; k < 30; k++) {
      await new Promise(res => setTimeout(res, 700));
      r = await page.evaluate(() => {
        const c = document.querySelector('#sc-page-selectable-container');
        if (!c) return null;
        const title = c.querySelector('[placeholder="Please enter a title"]')?.innerText.trim() || '';
        return {title, len: c.innerText.length};
      });
      if (r && r.title && r.len > r.title.length) { await new Promise(res => setTimeout(res, 1500)); break; }
    }
    const data = await page.evaluate(() => {
      const c = document.querySelector('#sc-page-selectable-container');
      const imgs = [...c.querySelectorAll('img')].map(im => im.currentSrc || im.src).filter(s => s && !s.includes('docs-design-resources'));
      return {text: c.innerText, html: c.outerHTML, imgs};
    });
    const meta = {idx, id: t.id, depth: t.depth, title: t.title, textLen: data.text.length, htmlLen: data.html.length, imgCount: data.imgs.length, loadedTitle: r?.title || ''};
    fs.writeFileSync(`${D}/pages/${idx}.json`, JSON.stringify({meta, text: data.text, imgs: data.imgs}));
    fs.writeFileSync(`${D}/pages/${idx}.html`, data.html);
    summary.push(meta);
    console.log(idx, meta.textLen, meta.imgCount, t.title, meta.loadedTitle === t.title ? '' : '!! loaded=' + meta.loadedTitle);
  } catch (e) {
    console.log(idx, 'ERROR', t.title, String(e).slice(0, 200));
  }
}
fs.writeFileSync(`${D}/summary.json`, JSON.stringify(summary, null, 1));
console.log('done', summary.length);
