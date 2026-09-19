/* New tools test: payslip + warning letter — fill, preview, save, docs list, XSS probe. */
const puppeteer = require('/home/user/node_modules/puppeteer-core');
(async () => {
  const b = await puppeteer.launch({executablePath:'/usr/bin/chromium',args:['--no-sandbox','--disable-setuid-sandbox']});
  const p = await b.newPage();
  const errs=[]; p.on('pageerror',e=>errs.push(String(e)));
  let fails=0; const ok=(n,c,x='')=>{ c?console.log('  ✓ '+n):(console.log('  ✗ FAIL: '+n+' '+x),fails++); };
  await p.goto('http://127.0.0.1:8901/index.html#payslip',{waitUntil:'domcontentloaded'});
  await new Promise(r=>setTimeout(r,900));
  // nav + cards
  const navLinks = await p.evaluate(()=>document.querySelectorAll('header nav a').length);
  const cards = await p.evaluate(()=>document.querySelectorAll('.cards .card').length);
  ok('nav has 12 links', navLinks===12, navLinks);
  ok('home has 9 tool cards', cards===9, cards);
  // fill payslip
  await p.evaluate(()=>{ $('p_biz').value='Kola Ventures Ltd'; $('p_addr').value='12 Ahmadu Bello Way, Abuja'; $('p_emp').value='Mr. Chidi Eze';
    $('p_role').value='Sales Officer'; $('p_id').value='ST-014'; $('p_period').value='September 2026'; $('p_date').value='2026-09-30';
    $('p_basic').value='150000'; $('p_house').value='20000'; $('p_trans').value='10000'; $('p_other').value='5000';
    $('p_paye').value='15000'; $('p_pen').value='12000'; $('p_nhf').value='3750'; $('p_ded').value='0'; $('p_bank').value='GTBank'; renderPayslip(); });
  await new Promise(r=>setTimeout(r,400));
  let pv = await p.evaluate(()=>document.querySelector('#preview-payslip').innerText);
  ok('payslip: title + employer + employee', /PAYSLIP/.test(pv)&&/Kola Ventures/.test(pv)&&/Chidi Eze/.test(pv));
  ok('payslip: gross ₦185,000', /185,000/.test(pv), pv.match(/GROSS PAY[^\n]*/));
  ok('payslip: deductions ₦30,750', /30,750/.test(pv));
  ok('payslip: net ₦154,250', /154,250/.test(pv));
  ok('payslip: net in words', /One Hundred and Fifty-Four Thousand, Two Hundred and Fifty/.test(pv), pv.match(/words:[^\\n]*/));
  ok('payslip: computer-generated footer', /computer-generated payslip/.test(pv));
  // save payslip
  await p.evaluate(()=>saveDoc('payslip'));
  // warning letter
  await p.evaluate(()=>{ location.hash='#warning'; route(); });
  await new Promise(r=>setTimeout(r,400));
  await p.evaluate(()=>{ $('w_biz').value='Kola Ventures Ltd'; $('w_emp').value='Mr. Chidi Eze'; $('w_role').value='Sales Officer';
    $('w_date').value='2026-09-19'; $('w_incident').value='12 & 15 Sep 2026'; $('w_count').value='First written warning';
    $('w_offence').value='repeated lateness to work'; $('w_expect').value='resume work by 8:00am daily'; $('w_deadline').value='2026-10-01';
    $('w_signer').value='Mrs. Bisi Ade — HR Manager'; renderWarning(); });
  await new Promise(r=>setTimeout(r,400));
  pv = await p.evaluate(()=>document.querySelector('#preview-warning').innerText);
  ok('warning: RE: line', /RE: FIRST WRITTEN WARNING/.test(pv));
  ok('warning: expected improvement + deadline', /EXPECTED IMPROVEMENT/.test(pv)&&/1 October 2026/.test(pv));
  ok('warning: consequence + acknowledgement', /termination of your employment/.test(pv)&&/ACKNOWLEDGEMENT/.test(pv));
  await p.evaluate(()=>saveDoc('warning'));
  // docs list shows both
  await p.evaluate(()=>{ location.hash='#docs'; route(); renderDocs(); });
  await new Promise(r=>setTimeout(r,400));
  const docs = await p.evaluate(()=>document.querySelector('#page-docs').innerText);
  ok('docs list: Payslip — Mr. Chidi Eze', /Payslip — Mr\. Chidi Eze/.test(docs));
  ok('docs list: Warning — Mr. Chidi Eze', /Warning — Mr\. Chidi Eze/.test(docs));
  // XSS probe on new fields
  await p.evaluate(()=>{ location.hash='#payslip'; route(); });
  await p.evaluate(()=>{ $('p_emp').value='<script>alert(1)<\/script><img src=x onerror=alert(2)>'; renderPayslip(); });
  await new Promise(r=>setTimeout(r,500));
  const xss = await p.evaluate(()=>({n: document.querySelectorAll('#preview-payslip script, #preview-payslip img, #preview-payslip svg[onload]').length, inert: document.querySelector('#preview-payslip').innerText.includes('<script')}));
  ok('XSS probe: zero executable elements, payload shown as inert text', xss.n===0 && xss.inert, JSON.stringify(xss));
  ok('zero page errors', errs.length===0, errs.join(';'));
  console.log(fails===0?'🏆 NEW TOOLS: ALL TESTS PASSED':`💥 ${fails} failed`);
  await b.close(); process.exit(fails?1:0);
})().catch(e=>{console.log('CRASH',e.message);process.exit(1);});
