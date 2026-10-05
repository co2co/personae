// 左栏布局与信息边界实测。
//
// 两组判据：
//  【布局】1) .rail-body 可滚  2) 无面板被压扁（offsetHeight < scrollHeight）
//         3) 滚到底后末面板底边 <= 视口底边  4) 面板内部滚动容器生效
//  【边界】5) 子面板名不得与左栏栏目名重名（重名引起误会）
//         6) **不得出现「引擎中间产物」面板**（关系 / 本轮行动 / 当前意图）
//            ——它们是叙事正文的原料，展示出来会把玩家注意力从正文带走。
//            这条是产品决策的守护：任何「顺手加回一个面板」的改动都会在此变红。
//
// 运行：node tests/_probe_leftrail.js
const puppeteer = require('puppeteer-core');
const path = require('path');

const PAGE = 'file:///' + path.resolve('D:/codes/personae/engine/static/index.html').replace(/\\/g, '/');

// demo 真实数据：12 条长叙述关系边（已不展示，但快照里仍存在）
const SNAP = {
  present: ['沈川', '周岚', '周子航', '林小满'],
  scene: { place: '四楼单元', time: '夜', weather: '', round: 12 },
  relations: { '沈川 → 周岚': '视其献身为理所当然的庇护代价，冷硬占有' },
  relation_locked: ['周岚 → 周子航'],
  actions: { 沈川: '清点药品存量并重新分配守夜班次', 周岚: '收拾客厅腾出铺位' },
  goals: { 沈川: '守住这栋楼，把地库那几箱东西弄上来', 周岚: '不让儿子看出破绽' },
  secrets: [
    { owner: '沈川', state: '潜伏', known_by: [], suspicions: [] },
    { owner: '周岚', state: '暴露', known_by: ['林小满'], suspicions: [] },
  ],
  states: { '单元门': { value: '被柜子抵死', round: 2 }, '抗生素': { value: '仅剩两支', round: 5 } },
  silent_rounds: { 沈川: 0, 周岚: 0, 周子航: 2, 林小满: 0 },
  aux: [{ name: '楼下邻居', role: '临时群演（导演/叙事引入）', intro_round: 8, status: '活跃' }],
};

// 不得作为面板出现的信息（引擎中间产物，正文才是主角）
const BANNED_PANELS = ['关系', '本轮行动', '当前意图', '不可逆事实'];

const VPS = [
  { width: 1090, height: 876 },   // simon 截图的视口
  { width: 1400, height: 800 },
  { width: 1280, height: 620 },   // 矮屏：最容易溢出
  { width: 1920, height: 1080 },
];

(async () => {
  const browser = await puppeteer.launch({
    executablePath: 'C:/Program Files/Google/Chrome/Application/chrome.exe',
    headless: 'new',
    args: ['--no-sandbox', '--disable-gpu'],
  });

  let allPass = true;
  for (const vp of VPS) {
    const page = await browser.newPage();
    await page.setViewport(vp);
    const errs = [];
    page.on('pageerror', e => errs.push(e.message));
    await page.goto(PAGE, { waitUntil: 'networkidle0' });
    await page.evaluate((snap) => {
      document.getElementById('board')?.classList.remove('hide');
      const lr = document.getElementById('left-rail');
      lr.classList.remove('collapsed');
      lr.classList.add('open');
      try { renderSnapshot(snap); } catch (e) { window.__err = e.message; }
    }, SNAP);
    await new Promise(r => setTimeout(r, 250));

    const m = await page.evaluate(() => {
      const rb = document.querySelector('#left-rail .rail-body');
      const panels = [...document.querySelectorAll('#left-rail .panel')];
      rb.scrollTop = rb.scrollHeight;
      const last = panels[panels.length - 1];
      const lb = last.getBoundingClientRect();
      const rbRect = rb.getBoundingClientRect();
      return {
        err: window.__err || null,
        clientH: rb.clientHeight, scrollH: rb.scrollHeight,
        scrollable: rb.scrollHeight > rb.clientHeight + 1,
        minHeight: getComputedStyle(rb).minHeight,
        squashed: panels.filter(p => p.offsetHeight < p.scrollHeight - 1)
                        .map(p => p.querySelector('h3')?.textContent || '?'),
        // 默认态：应全部展开（v0.16.1 起 4 个面板默认展开，点标题可各自收起）
        collapsedByDefault: panels.filter(p => p.classList.contains('collapsed'))
                        .map(p => (p.querySelector('h3')?.textContent || '?').trim()),
        panelTitles: panels.map(p => (p.querySelector('h3')?.textContent || '?').trim()),
        railTitle: (document.querySelector('#left-rail .rail-title')?.textContent || '').trim(),
        lastVisible: lb.bottom <= rbRect.bottom + 1,
        lastBottom: Math.round(lb.bottom), railBottom: Math.round(rbRect.bottom),
        innerScroll: [...document.querySelectorAll('.panel-body-scroll')].length,
        // 中间产物不该出现在 DOM 可见文本里
        leaked: ['本轮行动', '当前意图'].filter(t => document.body.innerText.includes(t)),
        relRowCount: document.querySelectorAll('#left-rail .rel-row').length,
        locks: document.querySelectorAll('.rel-lock').length,
        auxChips: document.querySelectorAll('.chip-aux').length,
        silentMarks: document.querySelectorAll('.chip-warn').length,
        stateRows: document.querySelectorAll('#states .rel-row').length,
      };
    });

    const banned = m.panelTitles.filter(t => BANNED_PANELS.includes(t));
    const dup = m.panelTitles.filter(t => t === m.railTitle);
    // 默认全展开：面板数少、一屏放得下；玩家想精简可自行点标题收起
    const pass = m.err === null && m.squashed.length === 0 && m.lastVisible
                 && m.minHeight === '0px' && banned.length === 0
                 && dup.length === 0 && m.leaked.length === 0
                 && m.collapsedByDefault.length === 0;
    if (!pass) allPass = false;

    console.log(`视口 ${vp.width}x${vp.height}  ${pass ? '通过' : '★ 失败'}`);
    console.log(`  布局: clientH=${m.clientH} scrollH=${m.scrollH} 可滚=${m.scrollable} minHeight=${m.minHeight}`);
    console.log(`  面板数=${m.panelTitles.length} 被压扁=${m.squashed.length ? m.squashed.join(',') : '无'}`);
    console.log(`  默认收起的面板: ${m.collapsedByDefault.length ? '★' + m.collapsedByDefault.join(',') : '无（应全展开）'}`);
    console.log(`  滚到底: 末面板 bottom=${m.lastBottom} / 视口 bottom=${m.railBottom} → ${m.lastVisible ? '可见' : '★被截断'}`);
    console.log(`  内部滚动容器=${m.innerScroll} 现状行数=${m.stateRows}`);
    console.log(`  栏目名=「${m.railTitle}」 子面板=${m.panelTitles.join(' / ')}`);
    console.log(`  与栏目名重名: ${dup.length ? '★' + dup.join(',') : '无'}`);
    console.log(`  中间产物面板: ${banned.length ? '★' + banned.join(',') : '无'} | 正文外泄文本: ${m.leaked.length ? '★' + m.leaked.join(',') : '无'}`);
    console.log(`  锁标记=${m.locks}(应为0，已下架) aux=${m.auxChips} 静默=${m.silentMarks} 渲染异常=${m.err || '无'}`);
    console.log('');
    if (vp.width === 1090) {
      // 交互验证：点第一个面板标题应收起，再点应恢复
      const toggled = await page.evaluate(() => {
        const head = document.querySelector('#left-rail .panel .panel-head');
        const panel = head.parentElement;
        const before = panel.classList.contains('collapsed');
        head.click();
        const after = panel.classList.contains('collapsed');
        head.click();
        const restored = panel.classList.contains('collapsed');
        return { before, after, restored };
      });
      const toggleOk = !toggled.before && toggled.after && !toggled.restored;
      if (!toggleOk) allPass = false;
      console.log(`  点击标题可折叠: ${toggleOk ? '通过' : '★失败'} (初始收起=${toggled.before} 点击后=${toggled.after} 再点恢复=${toggled.restored})`);
      console.log('');
      await page.screenshot({ path: 'D:/codes/personae/tests/_leftrail_probe.png' });
    }
    await page.close();
  }

  console.log(allPass ? '全部视口通过' : '★ 存在失败项');
  await browser.close();
  process.exit(allPass ? 0 : 1);
})().catch(e => { console.error('探针失败:', e.message); process.exit(1); });
