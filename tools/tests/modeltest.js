/* Owner's pass model: 2 profiles, codes from CODES_FILE (line1=A, line2=B).
   Tests synced countdown, top-up carry-over, old-code adoption, storage event. */
const puppeteer = require('/home/user/node_modules/puppeteer-core');
const fs = require('fs');
const codes = fs.readFileSync(process.env.CODES_FILE || '/tmp/mtcodes.txt','utf8').split('\n').map(s=>s.trim()).filter(Boolean);
const A = codes[0], B = codes[1];
(async () => {
  const b = await puppeteer.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--disable-setuid-sandbox']});
  const errs=[];
  const newProfile = async () => { const p = await (await b.createBrowserContext()).newPage(); p.on('pageerror',e=>errs.push(String(e))); await p.goto('http://127.0.0.1:8901/index.html',{waitUntil:'domcontentloaded'}); await new Promise(r=>setTimeout(r,900)); return p; };
  const chip = (p) => p.evaluate(()=>document.querySelector('#pass-chip').textContent);
  const pass_ = (p) => p.evaluate(()=>localStorage.getItem('docoga_pass'));
  const enter = async (p, code) => {
    await p.evaluate(()=>{ const btn=[...document.querySelectorAll('button')].find(x=>/Have a code\?/i.test(x.textContent)); btn.click(); });
    await p.waitForSelector('#modal-overlay.open',{timeout:3000});
    await p.evaluate(()=>{ document.querySelector('#pass-input').value=''; });
    await p.click('#pass-input'); await p.type('#pass-input', code);
    await p.evaluate(()=>{ [...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='Activate').click(); });
    await new Promise(r=>setTimeout(r,900));
    return p.evaluate(()=>({toast:document.querySelector('#toast').textContent, chip:document.querySelector('#pass-chip').textContent, pass:localStorage.getItem('docoga_pass')}));
  };
  let fails = 0;
  const ok = (n,c,x='') => { c ? console.log('  ✓ '+n) : (console.log('  ✗ FAIL: '+n+' '+x), fails++); };
  const p1 = await newProfile();
  const t1 = await enter(p1, A);
  ok('P1: activate A → ~30d', /OGA PASS ✓ 30d/.test(t1.chip), t1.chip);
  ok('P1: pass has {exp,c,h}', (()=>{const q=JSON.parse(t1.pass);return q.exp>0&&q.c&&q.h;})());
  await p1.reload({waitUntil:'domcontentloaded'}); await new Promise(r=>setTimeout(r,1500));
  const t2c = await chip(p1), t2p = JSON.parse(await pass_(p1));
  ok('P1: reload + server sync → same exp', t2p.exp === JSON.parse(t1.pass).exp && /OGA PASS ✓ 30d/.test(t2c), t2c);
  const t3 = await enter(p1, B);
  ok('P1: top-up B → carry-over → ~60d', /OGA PASS ✓ 60d/.test(t3.chip), t3.chip);
  ok('P1: toast shows real days', /60 day/.test(t3.toast), t3.toast);
  const t4 = await enter(p1, A);
  ok('P1: old code A re-entered → adopts newest, still 60d', /OGA PASS ✓ 60d/.test(t4.chip), t4.chip);
  const p2 = await newProfile();
  ok('P2: fresh device has no pass', (await pass_(p2)) === null);
  const t5 = await enter(p2, A);
  ok('P2: old code on new device → auto-adopts newest → ~60d', /OGA PASS ✓ 60d/.test(t5.chip), t5.chip);
  const p2pass = JSON.parse(await pass_(p2)), p1pass = JSON.parse(await pass_(p1));
  ok('P2: SAME synced expiry as P1', p2pass.exp === p1pass.exp && p2pass.c === p1pass.c);
  ok('P2: toast explains', /60 day/.test(t5.toast), t5.toast);
  ok('zero page errors', errs.length===0, errs.join('; '));
  console.log(fails===0 ? '🏆 ALL MODEL TESTS PASSED' : `💥 ${fails} failed`);
  await b.close(); process.exit(fails?1:0);
})().catch(e=>{console.log('CRASH',e.message);process.exit(1);});
