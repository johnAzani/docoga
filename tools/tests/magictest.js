/* Magic link test: #code= URL auto-activates, cleans the URL, no typing.
   Usage: CODES_FILE=/tmp/magiccode.txt node magictest.js (line 1 = code) */
const puppeteer = require('/home/user/node_modules/puppeteer-core');
const fs = require('fs');
const A = fs.readFileSync(process.env.CODES_FILE || '/tmp/magiccode.txt', 'utf8').split('\n')[0].trim();
(async () => {
  const b = await puppeteer.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--disable-setuid-sandbox']});
  const errs=[];
  let fails = 0;
  const ok = (n,c,x='') => { c ? console.log('  ✓ '+n) : (console.log('  ✗ FAIL: '+n+' '+x), fails++); };
  // T1: fresh browser + magic link → auto-activated
  const ctx = await b.createBrowserContext();
  const p = await ctx.newPage(); p.on('pageerror',e=>errs.push(String(e)));
  await p.goto('http://127.0.0.1:8901/index.html#code='+A,{waitUntil:'domcontentloaded'});
  await new Promise(r=>setTimeout(r,1300));
  let chip = await p.evaluate(()=>document.querySelector('#pass-chip').textContent);
  const url = await p.evaluate(()=>location.search+location.hash);
  const pass_ = await p.evaluate(()=>localStorage.getItem('docoga_pass'));
  ok('T1 magic link → auto OGA PASS (zero typing)', /OGA PASS/.test(chip), chip);
  ok('T1 code stripped from address bar', url===''||url==='#'||url==='/', JSON.stringify(url));
  ok('T1 pass stored with code + hash', (()=>{try{const q=JSON.parse(pass_);return q.c&&q.h&&q.exp>Date.now();}catch(e){return false;}})());
  // T2: same link again in same browser → already-active, no double
  await p.goto('http://127.0.0.1:8901/index.html#code='+A,{waitUntil:'domcontentloaded'});
  await p.reload({waitUntil:'domcontentloaded'});
  await new Promise(r=>setTimeout(r,1100));
  chip = await p.evaluate(()=>document.querySelector('#pass-chip').textContent);
  const toast = await p.evaluate(()=>document.querySelector('#toast').textContent);
  ok('T2 same link again → still active, no double-count', /OGA PASS/.test(chip) && /already active/.test(toast), chip+' | '+toast);
  // T3: invalid code link → stays free
  const p2 = await (await b.createBrowserContext()).newPage(); p2.on('pageerror',e=>errs.push('p2:'+e));
  await p2.goto('http://127.0.0.1:8901/index.html#code=OGA-BAD1-CODE-BAD1',{waitUntil:'domcontentloaded'});
  await new Promise(r=>setTimeout(r,1100));
  const chip2 = await p2.evaluate(()=>document.querySelector('#pass-chip').textContent);
  const pass2 = await p2.evaluate(()=>localStorage.getItem('docoga_pass'));
  ok('T3 invalid link → stays FREE, nothing stored', /FREE PLAN/.test(chip2) && (pass2===null), chip2+' | '+pass2);
  ok('zero page errors', errs.length===0, errs.join('; '));
  console.log(fails===0 ? '🏆 MAGIC LINK PROVEN — WhatsApp tap = login' : `💥 ${fails} failed`);
  await b.close(); process.exit(fails?1:0);
})().catch(e=>{console.log('CRASH',e.message);process.exit(1);});
