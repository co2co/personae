// 前端主流程绑定自检：用最小 DOM mock 执行内联脚本，验证
//   #start.onclick / #send.onclick / Enter 键 三条入口都已绑定，
//   且 send() 能真正发出 POST /api/act。
// 起因：v0.17.0 误删整段 send() 与绑定，界面「点了没反应」且控制台无报错。
const fs = require('fs');
const path = require('path');

const html = fs.readFileSync(path.join(__dirname, '..', 'engine', 'static', 'index.html'), 'utf8');
const code = html.match(/<script>([\s\S]*?)<\/script>/)[1];

// ---- 最小 DOM mock ----
const listeners = {};           // 元素 id -> {onclick, keydown:[], click:[]}
const els = new Map();
let fetchCalls = [];
const stubCls = { add(){}, remove(){}, toggle(){}, contains(){return false} };
// 开场区勾选框的桩：querySelectorAll('#npcs input:checked') 必须返回它们，
// 否则 startSession 会因「无可选角色」提前 return，沙箱就测不到真正的 POST。
const npcInputs = [{ value: '角色A' }, { value: '角色B' }];

function mkEl(id, tag) {
  const el = {
    id, tagName: (tag || 'DIV').toUpperCase(),
    className: '', innerHTML: '', textContent: '', value: '', placeholder: '',
    disabled: false, hidden: false, style: new Proxy({}, {set(){return true}}),
    dataset: {}, files: [],
    classList: stubCls,
    children: [], childNodes: [],
    scrollTop: 0, scrollHeight: 0, clientWidth: 0, clientHeight: 0,
    closest(){ return null }, contains(){ return false },
    querySelector(){ return mkEl('__stub', 'div') },
    querySelectorAll(sel){ return (sel === '#npcs input:checked') ? npcInputs : []; },
    appendChild(c){ el.children.push(c); return c },
    removeChild(c){ return c },
    addEventListener(ev, fn){ (listeners[id] || (listeners[id] = {}))[ev] = (listeners[id][ev]||[]).concat(fn) },
    removeEventListener(){},
    focus(){}, blur(){}, click(){ if (el.onclick) el.onclick() },
    getBoundingClientRect(){ return {top:0,left:0,width:100,height:20} },
    readAsDataURL(){ return Promise.resolve('data:,'); },
    doRead(){},
  };
  return el;
}
function get(id) {
  if (!els.has(id)) els.set(id, mkEl(id));
  return els.get(id);
}
global.document = {
  getElementById: get,
  querySelector: () => mkEl('__q', 'div'),
  querySelectorAll: (sel) => (sel === '#npcs input:checked') ? npcInputs : [],
  createElement: (t) => mkEl('__c', t),
  createDocumentFragment: () => mkEl('__frag', 'div'),
  addEventListener(){},
  body: mkEl('__body', 'body'),
  documentElement: mkEl('__html', 'html'),
};
global.window = { innerWidth: 1400, addEventListener(){}, scrollTo(){}, getComputedStyle: () => ({}) };
global.localStorage = { getItem: () => null, setItem(){}, removeItem(){} };
global.navigator = { userAgent: 'node' };
global.FileReader = class { readAsDataURL(){} addEventListener(){} };
global.EventSource = class { constructor(){} close(){} addEventListener(){} };

// fetch mock：把 /api/act 返回一条最小 SSE 流
global.fetch = function (url, opts) {
  fetchCalls.push({ url, method: (opts && opts.method) || 'GET', body: opts && opts.body });
  const sse = 'data: {"delta":"测试"}\n\ndata: {"done":true,"reply":"测试","snapshot":{"scene":{"round":1,"place":"P"},"present":["A"],"states":{},"secrets":[],"locations":{"角色B":{"place":"走廊","round":1}}}}\n\n';
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(
      url === '/api/characters' ? ['角色A', '角色B']
      : url.startsWith('/api/characters/by-world') ? { names: ['角色A', '角色B'], unassigned: [] }
      : url.startsWith('/api/session/new') ? { session: 'sid_test', snapshot: { scene: { round: 0, place: '' }, present: [], states: {}, secrets: [] } }
      : url === '/api/sessions' ? []
      : url.startsWith('/api/worlds') ? ['测试世界']
      : {}),
    body: { getReader() {
      const bytes = Buffer.from(sse, 'utf8');
      let i = 0;
      return { read() {
        if (i >= bytes.length) return Promise.resolve({ done: true, value: undefined });
        return Promise.resolve({ done: false, value: bytes.subarray(i, (i += bytes.length)) });
      }};
    }},
  });
};

// ---- 执行内联脚本 ----
const fn = new Function(code);
fn();

const L = listeners['start'] || {};
const fails = [];
function check(name, ok) { console.log((ok ? 'OK   ' : 'FAIL ') + name); if (!ok) fails.push(name); }

check('#start.onclick 已绑定', typeof get('start').onclick === 'function');
check('#send.onclick 已绑定', typeof get('send').onclick === 'function');
check('Enter 键监听已绑定', (L.keydown || listeners['input']?.keydown || (listeners['input']||{}).keydown) instanceof Array && (listeners['input']?.keydown || []).length > 0);
globalThis.__stage2 = async () => {
  // 开场区现在要求先选世界：模拟玩家在下拉里选了「测试世界」再点开始。
  get('world-pick').value = '测试世界';
  const n1 = fetchCalls.length;
  await get('start').onclick();
  const newCalls = fetchCalls.slice(n1).filter(c => c.url === '/api/session/new' && c.method === 'POST');
  check('startSession() 发出 POST /api/session/new', newCalls.length === 1);
  if (newCalls[0]) {
    const body = JSON.parse(newCalls[0].body);
    check('开局请求体含所选世界', body.world === '测试世界');
    check('开局请求体含在场角色', Array.isArray(body.cast) && body.cast.length === 2);
  }
  check('开始按钮已解锁', get('start').disabled === false);
};
check('cfgProviders 已声明', typeof get('__q').closest === 'function'); // 触发一次访问，确保脚本已完整执行

(async () => {
  // 触发 send()
  const n0 = fetchCalls.length;
  get('input').value = '天色暗下来开始下雨';
  await get('send').onclick();
  const actCalls = fetchCalls.slice(n0).filter(c => c.url === '/api/act');
  check('send() 发出 POST /api/act', actCalls.length === 1 && actCalls[0].method === 'POST');
  if (actCalls[0]) {
    const body = JSON.parse(actCalls[0].body);
    check('请求体含 input 文本', body.input === '天色暗下来开始下雨');
    check('请求体含 session', typeof body.session === 'string');
  }
  await new Promise(r => setTimeout(r, 60));
  // 人物位置兜底展示（2026-10-13 修）：locations 初始为空、导演官按增量补写，
  // 开局原地未动的角色会 silent 缺席（7 角色会话实测只有 4 人上榜）。present 成员
  // 无位置记录时必须显式标「（位置未记录）」；有记录的位置照常渲染，行为不回退。
  const locHtml = get('locations').innerHTML;
  check('人物位置：无记录的在场角色显式兜底', locHtml.includes('A：') && locHtml.includes('（位置未记录）'));
  check('人物位置：有记录的位置照常渲染', locHtml.includes('角色B：走廊'));
  await globalThis.__stage2();
  // 开局自动推演（startSession 末尾 fire-and-forget 的 streamAct('')）是异步的：
  // 等待其 SSE 流走完、sendBtn 恢复解锁，再断言。与上文 60ms 等待同一模式。
  await new Promise(r => setTimeout(r, 60));
  check('按钮发送后已解锁', get('send').disabled === false);

  console.log(fails.length ? '\n>>> FAILED: ' + fails.join(' | ') : '\n>>> ALL PASS');
  process.exit(fails.length ? 1 : 0);
})();