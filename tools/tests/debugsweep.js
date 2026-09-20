/* DOCOGA FULL DEBUG SWEEP — every route, every tool, hostile inputs, pass states, persistence.
   Exit 0 = all green. Any FAIL line = bug found. */
const puppeteer = require('/home/user/node_modules/puppeteer-core');
(async () => {
  const b = await puppeteer.launch({ executablePath: '/usr/bin/chromium', args: ['--no-sandbox', '--disable-setuid-sandbox'] });
  const p = await b.newPage();
  const errs = []; const consErrs = []; const res404 = [];
  p.on('response', r => { if (r.status() === 404) res404.push(r.url()); });
  p.on('pageerror', e => errs.push('PAGEERROR: ' + String(e)));
  p.on('console', m => { if (m.type() === 'error') consErrs.push('CONSOLE: ' + m.text()); });
  let fails = 0;
  const ok = (n, c, x = '') => { c ? console.log('  ✓ ' + n) : (console.log('  ✗ FAIL: ' + n + ' | ' + x), fails++); };

  await p.goto('http://127.0.0.1:8901/index.html', { waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1000));

  // ---------- PART 1: all 12 routes ----------
  console.log('— PART 1: all 12 routes —');
  const pages = ['home','agreement','notice','receipt','invoice','employment','caution','demand','payslip','warning','docs','pricing'];
  for (const pg of pages) {
    await p.evaluate(g => { location.hash = '#' + g; route(); }, pg);
    await new Promise(r => setTimeout(r, 150));
    const vis = await p.evaluate(id => { const el = document.querySelector('#page-' + id); return !!el && el.offsetParent !== null; }, pg);
    ok('route #' + pg + ' renders its section', vis);
  }
  ok('zero page errors across all routes', errs.length === 0, errs.slice(0, 3).join(' ;; '));

  // ---------- PART 2: hostile input sweep on every form ----------
  console.log('— PART 2: hostile inputs on all 9 tool forms —');
  const NASTY = 'Mr. "Q" O\'Brien 🇳🇬 <script>alert(1)</' + 'script><img src=x onerror=a()> ₦10,000 — émoji… ' + 'A'.repeat(300);
  const forms = await p.evaluate(() => Array.from(document.querySelectorAll('form[id^="form-"]')).map(f => f.id));
  ok('found 9 tool forms', forms.length === 9, forms.join(','));
  for (const fid of forms) {
    await p.evaluate((fid, NASTY) => {
      const f = document.getElementById(fid);
      f.querySelectorAll('input,textarea').forEach(el => {
        if (el.type === 'date') { el.value = '2026-09-20'; }
        else if (el.type === 'number' || el.getAttribute('inputmode') === 'numeric') { el.value = '150,000'; }
        else { el.value = NASTY; }
        el.dispatchEvent(new Event('input', { bubbles: true }));
      });
      f.querySelectorAll('select').forEach(el => { const o = el.querySelectorAll('option'); if (o.length > 1) { el.selectedIndex = 1; } el.dispatchEvent(new Event('input', { bubbles: true })); });
    }, fid, NASTY);
    await new Promise(r => setTimeout(r, 120));
  }
  ok('hostile inputs on all forms: zero page errors', errs.length === 0, errs.slice(0, 3).join(' ;; '));
  const previews = await p.evaluate(() => PAGES.filter(x => x !== 'home' && x !== 'docs' && x !== 'pricing').map(t => {
    const el = document.querySelector('#preview-' + t); return t + ':' + (el && el.innerText.trim().length > 0 ? 'ok' : 'EMPTY');
  }));
  ok('all 9 previews rendered non-empty', previews.every(x => x.endsWith(':ok')), previews.join(' '));

  // numeric commas: payslip must not silently show ₦0 (informational + comma behavior)
  const commaNet = await p.evaluate(() => {
    ['p_house','p_trans','p_other','p_paye','p_pen','p_nhf','p_ded'].forEach(id => $(id).value = '');
    $('p_basic').value = '₦150,000'; renderPayslip();
    return document.querySelector('#hint-p_net').textContent;
  });
  ok('comma+₦ input "₦150,000" parses to ₦150,000 net', commaNet.includes('150,000'), commaNet.slice(0, 70));

  // negative + decimal amounts
  await p.evaluate(() => { $('p_basic').value = '-5000'; $('p_paye').value = '12.5'; renderPayslip(); });
  const negOk = await p.evaluate(() => document.querySelector('#preview-payslip').innerText.includes('-'));
  ok('negative/decimal amounts handled (rendered, no crash)', negOk && errs.length === 0);

  // ---------- PART 3: XSS on all new-tool fields ----------
  console.log('— PART 3: XSS full-field proof (payslip + warning) —');
  const xss = await p.evaluate(() => {
    let n = 0;
    document.querySelectorAll('#form-payslip input, #form-payslip textarea, #form-warning input, #form-warning textarea').forEach(el => {
      el.value = '<script>a()</' + 'script><img src=x onerror=b()><svg onload=c()>"'; el.dispatchEvent(new Event('input', { bubbles: true }));
    });
    renderPayslip(); renderWarning();
    n = document.querySelectorAll('#preview-payslip script, #preview-payslip img, #preview-payslip svg[onload], #preview-warning script, #preview-warning img, #preview-warning svg[onload]').length;
    return n;
  });
  ok('XSS: 0 executable elements in previews', xss === 0, 'count=' + xss);

  // ---------- PART 4: save all 9 + docs list + round-trip ----------
  console.log('— PART 4: save all 9 docs + round-trip —');
  await p.evaluate(() => { ['agreement','notice','receipt','invoice','employment','caution','demand','payslip','warning'].forEach(t => saveDoc(t)); });
  await p.evaluate(() => { location.hash = '#docs'; route(); renderDocs(); });
  await new Promise(r => setTimeout(r, 200));
  const docsText = await p.evaluate(() => document.querySelector('#page-docs').innerText);
  const docCount = (docsText.match(/\bOpen\b/g) || []).length;
  ok('docs list shows all 9 saved docs', docCount === 9, 'found ' + docCount);
  const rt = await p.evaluate(() => {
    const before = collectPayslip(); const cp = JSON.parse(JSON.stringify(before));
    Object.values({}).forEach(() => {});
    applyPayslip({});
    const empty = !$('p_emp').value;
    applyPayslip(cp);
    return { empty, restored: JSON.stringify(collectPayslip()) === JSON.stringify(before) };
  });
  ok('apply/collect round-trip: clear + restore exact', rt.empty && rt.restored, JSON.stringify(rt));

  // ---------- PART 5: print + share stubs for all 9 ----------
  console.log('— PART 5: print/share no-throw —');
  const ps = await p.evaluate(() => {
    let printed = 0; window.print = () => printed++;
    const oldOpen = window.open; window.open = () => ({});
    let bad = 0;
    ['agreement','notice','receipt','invoice','employment','caution','demand','payslip','warning'].forEach(t => {
      try { printCurrent(t); } catch (e) { bad++; console.log('print ' + t + ': ' + e.message); }
      try { shareDoc(t); } catch (e) { bad++; console.log('share ' + t + ': ' + e.message); }
    });
    window.open = oldOpen;
    return { printed, bad };
  });
  ok('printCurrent works for all 9 (dialog stubbed)', ps.printed === 9 && ps.bad === 0, JSON.stringify(ps));
  ok('shareDoc works for all 9', ps.bad === 0);

  // ---------- PART 6: pass states ----------
  console.log('— PART 6: pass UI states —');
  const emptyRes = await p.evaluate(async () => { $('pass-input').value = '   '; try { await submitCode(); return 'ok'; } catch (e) { return 'THREW: ' + e.message; } });
  ok('blank code submit → graceful (no crash)', emptyRes === 'ok', emptyRes);
  const inval = await p.evaluate(async () => { $('pass-input').value = 'oga-nope-nope-0000'; try { await submitCode(); return 'ok'; } catch (e) { return 'THREW: ' + e.message; } });
  ok('lowercase invalid code → graceful rejection', inval === 'ok', inval);
  const chipAfterBad = await p.evaluate(() => document.querySelector('#pass-chip') ? document.querySelector('#pass-chip').textContent : 'none');
  ok('pass chip still sane after bad code', /FREE|OGA/i.test(chipAfterBad), chipAfterBad);
  // malformed magic links
  const magic1 = await p.evaluate(() => { location.hash = '#code=short'; return 'ok'; });
  await new Promise(r => setTimeout(r, 400));
  ok('malformed magic link ignored, no errors', errs.length === 0, errs.slice(0, 2).join(';'));
  // fake stored pass (deleted code) → site must degrade to FREE
  await p.evaluate(() => { localStorage.setItem('docoga_pass', JSON.stringify({ exp: Date.now() - 5000, c: 'OGA-FAKE-0000-0000', h: 'deadbeef' })); });
  await p.reload({ waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 2500));
  const chipExpired = await p.evaluate(() => { const c = document.querySelector('#pass-chip'); return c ? c.textContent : 'none'; });
  ok('expired/fake stored pass degrades to FREE PLAN chip', /FREE/i.test(chipExpired), 'chip="' + chipExpired + '"');
  ok('zero page errors after expired-pass reload', errs.length === 0, errs.slice(0, 3).join(' ;; '));
  await p.evaluate(() => localStorage.removeItem('docoga_pass'));

  // ---------- PART 7: draft persistence ----------
  console.log('— PART 7: draft persistence —');
  await p.evaluate(() => { location.hash = '#payslip'; route(); $('p_emp').value = 'Persistence Test'; $('p_emp').dispatchEvent(new Event('input', { bubbles: true })); });
  await new Promise(r => setTimeout(r, 1200));
  await p.reload({ waitUntil: 'domcontentloaded' });
  await new Promise(r => setTimeout(r, 1000));
  const persisted = await p.evaluate(() => $('p_emp') ? $('p_emp').value : 'MISSING');
  ok('payslip draft survives reload', persisted === 'Persistence Test', 'got: "' + persisted + '"');

  // ---------- PART 8: iOS zoom + tap targets ----------
  console.log('— PART 8: mobile sanity —');
  const fontOk = await p.evaluate(() => {
    const bad = [];
    document.querySelectorAll('#form-payslip input, #form-warning input, #form-employment input').forEach(el => {
      const fs = parseFloat(getComputedStyle(el).fontSize);
      if (fs < 16 && el.type !== 'hidden') bad.push(el.id + '=' + fs);
    });
    return bad;
  });
  ok('all inputs ≥16px (no iOS zoom)', fontOk.length === 0, fontOk.slice(0, 4).join(','));

  const unexpected = consErrs.filter(e => !(/Failed to load resource.*404/.test(e) && res404.some(u => u.includes('/activate'))));
  ok('zero unexpected console.errors (worker /activate 404 for fake codes = expected)', unexpected.length === 0, unexpected.slice(0, 3).join(' ;; '));
  ok('zero page errors entire sweep', errs.length === 0, errs.slice(0, 3).join(' ;; '));

  console.log(fails === 0 ? '\n🏆 DEBUG SWEEP: ALL ' + 'CHECKS PASSED' : '\n💥 ' + fails + ' ISSUE(S) FOUND');
  await b.close(); process.exit(fails ? 1 : 0);
})().catch(e => { console.log('CRASH', e.message); process.exit(1); });
