/* Fence test: 4 devices (browser contexts), 1 code — 3 in, 4th politely blocked.
   Usage: CODES_FILE=/tmp/dgcode.txt node fencetest.js  (file = one code per line) */
const puppeteer = require('/home/user/node_modules/puppeteer-core');
const fs = require('fs');
const A = fs.readFileSync(process.env.CODES_FILE || '/tmp/dgcode.txt', 'utf8').split('\n')[0].trim();
(async () => {
  const b = await puppeteer.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--disable-setuid-sandbox']});
  const enter = async () => {
    const p = await (await b.createBrowserContext()).newPage();
    const errs=[]; p.on('pageerror',e=>errs.push(String(e)));
    await p.goto('http://127.0.0.1:8901/index.html',{waitUntil:'domcontentloaded'});
    await new Promise(r=>setTimeout(r,800));
    await p.evaluate(()=>{ const btn=[...document.querySelectorAll('button')].find(x=>/Have a code\?/i.test(x.textContent)); btn.click(); });
    await p.waitForSelector('#modal-overlay.open',{timeout:3000});
    await p.click('#pass-input'); await p.type('#pass-input', A);
    await p.evaluate(()=>{ [...document.querySelectorAll('button')].find(x=>x.textContent.trim()==='Activate').click(); });
    await new Promise(r=>setTimeout(r,1000));
    const out = await p.evaluate(()=>({chip:document.querySelector('#pass-chip').textContent, toast:document.querySelector('#toast').textContent, did:localStorage.getItem('docoga_did')}));
    out.errs = errs; return out;
  };
  let fails = 0;
  const ok = (n,c,x='') => { c ? console.log('  ✓ '+n) : (console.log('  ✗ FAIL: '+n+' '+x), fails++); };
  const f1 = await enter(); ok('friend 1 (phone):  OGA PASS', /OGA PASS/.test(f1.chip), f1.chip);
  const f2 = await enter(); ok('friend 2 (laptop): OGA PASS', /OGA PASS/.test(f2.chip), f2.chip);
  const f3 = await enter(); ok('friend 3 (tablet): OGA PASS', /OGA PASS/.test(f3.chip), f3.chip);
  const f4 = await enter();
  ok('friend 4: BLOCKED, friendly message + ₦2,000 hint', /FREE PLAN/.test(f4.chip) && /3 devices/.test(f4.toast) && /₦2,000/.test(f4.toast), f4.chip+' | '+f4.toast);
  ok('each device has its own fingerprint', new Set([f1.did,f2.did,f3.did,f4.did]).size === 4);
  ok('zero page errors', [f1,f2,f3,f4].every(f=>f.errs.length===0));
  console.log(fails===0 ? '🏆 FENCE PROVEN: 3 devices in, 4th politely shown the door' : `💥 ${fails} failed`);
  await b.close(); process.exit(fails?1:0);
})().catch(e=>{console.log('CRASH',e.message);process.exit(1);});
