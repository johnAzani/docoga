/* Consent-first Analytics regression tests. Uses a fake DOM/storage/network sink;
 * no Google request or real tracking is made by this suite. */
import assert from 'node:assert/strict';
import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..', '..');
const SITE = path.join(ROOT, 'site');
const SOURCE = fs.readFileSync(path.join(SITE, 'analytics-consent.js'), 'utf8');
const RELEASE_OPEN_SOURCE = SOURCE.replace(
  'var ANALYTICS_RELEASE_ENABLED = false;',
  'var ANALYTICS_RELEASE_ENABLED = true;'
);
assert.notEqual(RELEASE_OPEN_SOURCE, SOURCE, 'test must override the closed release gate only in the VM');

function makeElement(tagName) {
  const listeners = Object.create(null);
  const element = {
    tagName: String(tagName).toUpperCase(),
    children: [],
    attributes: Object.create(null),
    style: {},
    parentNode: null,
    textContent: '',
    className: '',
    type: '',
    href: '',
    src: '',
    async: false,
    setAttribute(name, value) { this.attributes[name] = String(value); },
    getAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attributes, name) ? this.attributes[name] : null; },
    addEventListener(name, handler) { (listeners[name] ||= []).push(handler); },
    appendChild(child) {
      if (child.parentNode) child.parentNode.removeChild(child);
      this.children.push(child);
      child.parentNode = this;
      return child;
    },
    removeChild(child) {
      const index = this.children.indexOf(child);
      if (index !== -1) this.children.splice(index, 1);
      child.parentNode = null;
      return child;
    },
    click() { (listeners.click || []).forEach((handler) => handler({ type: 'click', target: this })); },
  };
  Object.defineProperty(element, 'id', {
    get() { return this.attributes.id || ''; },
    set(value) { this.attributes.id = String(value); },
  });
  return element;
}

function walk(root, visit) {
  if (!root) return;
  visit(root);
  (root.children || []).forEach((child) => walk(child, visit));
}

function harness({
  source = RELEASE_OPEN_SOURCE,
  href = 'https://docoga.com.ng/?tx_ref=SECRET-REF&utm_source=facebook&utm_campaign=SECRET-CAMPAIGN&utm_term=SECRET-TERM#agreement',
  referrer = 'https://pay.example/checkout?email=person%40example.com&tx_ref=SECRET-REF#private',
  trackPage = true,
  savedChoice = null,
  savedUpdatedAt = new Date().toISOString(),
  cookieEntries = { _ga: 'old-id', _ga_ABC123: 'old-session', unrelated: 'keep' },
  storageThrows = false,
} = {}) {
  let currentUrl = new URL(href);
  const replacements = [];
  const listeners = Object.create(null);
  const values = new Map();
  if (savedChoice) values.set('docoga.analytics-consent.v1', JSON.stringify({
    version: 1, choice: savedChoice, updatedAt: savedUpdatedAt,
  }));
  const localStorage = {
    getItem(key) { if (storageThrows) throw new Error('storage blocked'); return values.has(key) ? values.get(key) : null; },
    setItem(key, value) { if (storageThrows) throw new Error('storage blocked'); values.set(key, String(value)); },
    removeItem(key) { if (storageThrows) throw new Error('storage blocked'); values.delete(key); },
  };
  const location = {};
  for (const key of ['href', 'protocol', 'hostname', 'origin', 'pathname', 'search', 'hash']) {
    Object.defineProperty(location, key, {
      get() { return currentUrl[key]; },
      set(value) {
        if (key === 'href') currentUrl = new URL(value, currentUrl.href);
        else if (key === 'hash') currentUrl.hash = value;
        else if (key === 'search') currentUrl.search = value;
        else throw new Error('read-only fake location field: ' + key);
      },
    });
  }
  const history = {
    state: { retained: true },
    replaceState(state, _title, relativeUrl) {
      this.state = state;
      replacements.push(String(relativeUrl));
      currentUrl = new URL(relativeUrl, currentUrl.href);
    },
  };
  const head = makeElement('head');
  const body = makeElement('body');
  const document = {
    head,
    body,
    title: 'DocOga — Free Nigerian Document Tools',
    referrer,
    currentScript: { getAttribute(name) { return name === 'data-track-page' && trackPage ? 'true' : null; } },
    createElement: makeElement,
    getElementById(id) {
      let found = null;
      walk(head, (node) => { if (!found && node.id === id) found = node; });
      walk(body, (node) => { if (!found && node.id === id) found = node; });
      return found;
    },
  };
  const cookies = new Map(Object.entries(cookieEntries));
  Object.defineProperty(document, 'cookie', {
    get() { return Array.from(cookies, ([key, value]) => key + '=' + value).join('; '); },
    set(value) {
      const pieces = String(value).split(';');
      const pair = pieces[0].trim();
      const equals = pair.indexOf('=');
      if (equals < 0) return;
      const key = pair.slice(0, equals).trim();
      const expired = pieces.slice(1).some((part) => /max-age\s*=\s*0/i.test(part)) ||
        /expires\s*=\s*thu,\s*01 jan 1970/i.test(String(value));
      if (expired) cookies.delete(key);
      else cookies.set(key, pair.slice(equals + 1));
    },
  });

  const context = {
    document,
    location,
    history,
    localStorage,
    URL,
    URLSearchParams,
    addEventListener(name, handler) { (listeners[name] ||= []).push(handler); },
    dispatch(name) { (listeners[name] || []).forEach((handler) => handler({ type: name })); },
  };
  context.window = context;
  vm.runInNewContext(source, context, { filename: 'site/analytics-consent.js' });
  return {
    window: context,
    document,
    values,
    cookies,
    replacements,
    getById: (id) => document.getElementById(id),
    externalTagScripts() {
      const scripts = [];
      walk(head, (node) => {
        if (node.tagName === 'SCRIPT' && node.src.indexOf('googletagmanager.com/gtag/js') !== -1) scripts.push(node);
      });
      return scripts;
    },
    fireGoogleTagLoad() {
      const tag = this.externalTagScripts()[0];
      assert.ok(tag, 'test stub has a Google tag element to load');
      if (typeof tag.onload === 'function') tag.onload();
    },
    calls() { return (context.dataLayer || []).map((args) => Array.from(args)); },
  };
}

function pageViews(test) {
  return test.calls().filter((call) => call[0] === 'event' && call[1] === 'page_view');
}

console.log('Consent-first Analytics tests (stubbed; no network requests)');

// The production source cannot load GA until the explicit release-control review.
const dormant = harness({ source: SOURCE, savedChoice: 'accepted' });
assert.equal(dormant.externalTagScripts().length, 0, 'closed release gate loads no Google script');
assert.equal(dormant.getById('docoga-consent-banner'), null, 'disabled Analytics does not solicit an unused choice');
assert.equal(dormant.window.dataLayer, undefined, 'closed release gate queues no Google commands');
assert.equal(dormant.cookies.has('_ga'), false, 'closed gate expires any legacy first-party GA cookies locally');
assert.equal(dormant.cookies.has('_ga_ABC123'), false);
assert.ok(dormant.getById('docoga-privacy-choices'), 'disabled release still exposes a status/choices control');
dormant.getById('docoga-privacy-choices').click();
assert.match(dormant.getById('docoga-analytics-disabled-status').textContent, /not enabled/i);
assert.equal(dormant.externalTagScripts().length, 0);
assert.equal(dormant.values.has('docoga.analytics-consent.v1'), false, 'release-off status clears stale choice records so a later release must ask again');
console.log('  ✓ release gate is closed by default; status control stays first-party and inert');

// First visit has no stored affirmative choice, so even on the production host
// there is no Google request and no URL is passed to a third party.
const firstVisit = harness();
assert.ok(firstVisit.getById('docoga-consent-banner'), 'first visit shows the consent banner');
assert.ok(firstVisit.getById('docoga-accept-analytics'), 'accept button is present');
assert.ok(firstVisit.getById('docoga-reject-analytics'), 'reject button is present');
assert.equal(firstVisit.externalTagScripts().length, 0, 'no Google script before a choice');
assert.equal(firstVisit.window.dataLayer, undefined, 'no Google dataLayer before a choice');
assert.match(firstVisit.window.location.href, /tx_ref=SECRET-REF/, 'URL remains unchanged until opt-in');
firstVisit.getById('docoga-reject-analytics').click();
assert.equal(JSON.parse(firstVisit.values.get('docoga.analytics-consent.v1')).choice, 'rejected');
assert.equal(firstVisit.externalTagScripts().length, 0, 'reject keeps Analytics unloaded');
assert.ok(firstVisit.getById('docoga-privacy-choices'), 'choice can be reviewed after rejecting');
firstVisit.getById('docoga-privacy-choices').click();
assert.match(firstVisit.getById('docoga-consent-current-choice').textContent, /rejected/i);
firstVisit.getById('docoga-accept-analytics').click();
assert.equal(firstVisit.externalTagScripts().length, 1, 'acceptance is the only path that starts the tag');
assert.match(firstVisit.externalTagScripts()[0].src, /id=G-BQ1YTR0ZZJ$/);
assert.equal(firstVisit.externalTagScripts()[0].referrerPolicy, 'no-referrer', 'Google script fetch receives no raw referrer');
assert.equal(firstVisit.window.location.href, 'https://docoga.com.ng/?utm_source=facebook#agreement');
assert.ok(firstVisit.replacements.length > 0, 'unsafe query parameters are removed before the tag is appended');
assert.equal(pageViews(firstVisit).length, 0, 'no measurement is queued while the Google library is still loading');
assert.equal(firstVisit.calls().filter((call) => call[0] === 'config').length, 0);
firstVisit.fireGoogleTagLoad();
const acceptedCalls = firstVisit.calls();
const configCall = acceptedCalls.find((call) => call[0] === 'config');
assert.equal(configCall[1], 'G-BQ1YTR0ZZJ', 'only the dedicated DocOga property is configured');
assert.equal(configCall[2].send_page_view, false, 'automatic page view is disabled for manual safe events');
assert.equal(configCall[2].allow_google_signals, false);
assert.equal(configCall[2].allow_ad_personalization_signals, false);
assert.equal(configCall[2].page_location, 'https://docoga.com.ng/?utm_source=facebook#agreement');
assert.equal(configCall[2].page_referrer, 'https://pay.example', 'external referrer is reduced to its origin');
assert.equal(pageViews(firstVisit).length, 1, 'accepted initial visit receives one manual page view');
assert.doesNotMatch(JSON.stringify(acceptedCalls), /SECRET-REF|SECRET-CAMPAIGN|SECRET-TERM|person%40example\.com|private/);

firstVisit.window.location.hash = '#poa';
firstVisit.window.dispatch('hashchange');
assert.equal(pageViews(firstVisit).length, 2, 'safe SPA route changes receive one page view');
assert.equal(pageViews(firstVisit)[1][2].page_location, 'https://docoga.com.ng/?utm_source=facebook#poa');
assert.equal(pageViews(firstVisit)[1][2].page_referrer, 'https://docoga.com.ng/?utm_source=facebook#agreement');
firstVisit.window.location.hash = '#code=OGA-SECRET-PASS';
firstVisit.window.dispatch('hashchange');
assert.equal(firstVisit.window.location.hash, '#home', 'unrecognized/raw code fragments are replaced with an allowlisted route');
assert.equal(pageViews(firstVisit).length, 3);
assert.doesNotMatch(JSON.stringify(firstVisit.calls()), /OGA-SECRET-PASS|SECRET-REF|SECRET-CAMPAIGN|SECRET-TERM|person%40example\.com|private/);

// Withdrawal immediately updates consent, clears first-party GA cookies, and
// prevents any later route page-view from this document.
firstVisit.getById('docoga-privacy-choices').click();
firstVisit.getById('docoga-reject-analytics').click();
const beforeAfterWithdrawal = pageViews(firstVisit).length;
assert.ok(firstVisit.calls().some((call) => call[0] === 'consent' && call[1] === 'update' && call[2].analytics_storage === 'denied'));
assert.equal(firstVisit.cookies.has('_ga'), false);
assert.equal(firstVisit.cookies.has('_ga_ABC123'), false);
assert.equal(firstVisit.cookies.get('unrelated'), 'keep');
firstVisit.window.location.hash = '#receipt';
firstVisit.window.dispatch('hashchange');
assert.equal(pageViews(firstVisit).length, beforeAfterWithdrawal, 'withdrawal stops future SPA measurement');
firstVisit.window.location.search = '?tx_ref=SECRET-REF&utm_campaign=SECRET-CAMPAIGN';
firstVisit.window.location.hash = '#code=OGA-SECRET-PASS';
firstVisit.getById('docoga-privacy-choices').click();
firstVisit.getById('docoga-accept-analytics').click();
assert.equal(firstVisit.window.location.href, 'https://docoga.com.ng/#home',
  're-accepting after withdrawal scrubs unsafe query and raw pass-code fragment before resuming');
assert.equal(pageViews(firstVisit).length, beforeAfterWithdrawal + 1, 're-acceptance resumes with one safe page view');
assert.doesNotMatch(JSON.stringify(firstVisit.calls()), /OGA-SECRET-PASS|SECRET-REF|SECRET-CAMPAIGN/);
console.log('  ✓ accept/reject, safe pageviews, route allowlist, referrer/query scrubbing, withdrawal and safe re-acceptance');

const revokeDuringLoad = harness();
revokeDuringLoad.getById('docoga-accept-analytics').click();
assert.equal(pageViews(revokeDuringLoad).length, 0);
revokeDuringLoad.getById('docoga-privacy-choices').click();
revokeDuringLoad.getById('docoga-reject-analytics').click();
revokeDuringLoad.fireGoogleTagLoad();
assert.equal(revokeDuringLoad.calls().filter((call) => call[0] === 'config').length, 0,
  'withdrawing while the library is in flight prevents config and page-view events');
assert.equal(pageViews(revokeDuringLoad).length, 0);
assert.ok(revokeDuringLoad.calls().some((call) => call[0] === 'consent' && call[1] === 'update' && call[2].analytics_storage === 'denied'));
console.log('  ✓ withdrawal before the library finishes loading queues no measurement');

// Persisted rejection and expired/malformed records fail closed. An accepted
// choice on a non-production host never injects a third-party library.
const rejectedVisit = harness({ savedChoice: 'rejected' });
assert.equal(rejectedVisit.externalTagScripts().length, 0);
assert.equal(rejectedVisit.getById('docoga-consent-banner'), null);
assert.ok(rejectedVisit.getById('docoga-privacy-choices'));
const returningAccepted = harness({ savedChoice: 'accepted' });
assert.equal(returningAccepted.externalTagScripts().length, 1, 'an unexpired stored opt-in can load Analytics on a later visit');
assert.equal(pageViews(returningAccepted).length, 0, 'stored opt-in still waits for the Google library before measurement');
returningAccepted.fireGoogleTagLoad();
assert.equal(pageViews(returningAccepted).length, 1);
const legalPage = harness({ savedChoice: 'accepted', trackPage: false, href: 'https://docoga.com.ng/privacy.html' });
assert.equal(legalPage.externalTagScripts().length, 0, 'privacy and terms pages never load Analytics even after opt-in');
const expiredVisit = harness({ savedChoice: 'accepted', savedUpdatedAt: new Date(Date.now() - 181 * 24 * 60 * 60 * 1000).toISOString() });
assert.equal(expiredVisit.externalTagScripts().length, 0);
assert.ok(expiredVisit.getById('docoga-consent-banner'));
const previewVisit = harness({ savedChoice: 'accepted', href: 'https://preview.example.test/?tx_ref=SECRET-REF#agreement' });
assert.equal(previewVisit.externalTagScripts().length, 0, 'preview and local hosts never send Analytics');
const storageBlocked = harness({ storageThrows: true });
storageBlocked.getById('docoga-accept-analytics').click();
assert.equal(storageBlocked.externalTagScripts().length, 1, 'explicit choice still applies for the current page if storage is blocked');
assert.ok(storageBlocked.getById('docoga-privacy-choices'));
console.log('  ✓ stored choices expire, rejection persists, previews are inert, and blocked storage still requires an explicit choice');

// Assert wiring across every shipped HTML page. Two pages are deliberately
// excluded from both the manager and page-view tracking: the success/payment
// page, and the owner dashboard (admin.html — noindex, Disallow: /admin; the
// owner's own revenue screen is never measured by a third party).
const UNTAGGED_PAGES = new Set(['success.html', 'admin.html']);
const htmlFiles = fs.readdirSync(SITE).filter((name) => name.endsWith('.html')).sort();
assert.ok(htmlFiles.length > 0);
for (const name of htmlFiles) {
  const html = fs.readFileSync(path.join(SITE, name), 'utf8');
  if (UNTAGGED_PAGES.has(name)) {
    assert.doesNotMatch(html, /analytics-consent\.js|G-BQ1YTR0ZZJ|G-GO8VZB3R28|googletagmanager/i, name + ' is untagged');
    continue;
  }
  assert.match(html, /<script src="\/analytics-consent\.js"(?: data-track-page="true")? defer><\/script>/, name + ' includes the privacy manager');
  if (name === 'privacy.html' || name === 'terms.html') {
    assert.doesNotMatch(html, /data-track-page="true"/, name + ' is not page-view tracked');
  } else {
    assert.match(html, /data-track-page="true"/, name + ' is included in consent-gated page measurement');
  }
}
const appHtml = fs.readFileSync(path.join(SITE, 'index.html'), 'utf8');
assert.doesNotMatch(appHtml, /G-GO8VZB3R28|googletagmanager\.com\/gtag\/js/i);
const shareStart = appHtml.indexOf('function shareDoc(type){');
const shareEnd = appHtml.indexOf('/* ================= PAYSLIP', shareStart);
assert.ok(shareStart >= 0 && shareEnd > shareStart, 'shareDoc function can be isolated for a no-network test');
const shareSource = appHtml.slice(shareStart, shareEnd);
assert.doesNotMatch(shareSource, /document\.|RENDERERS|collect[A-Z]|preview|\.value\b/i,
  'WhatsApp share URL must not read form fields, renderers, or document previews');
const shareTypes = ['agreement', 'notice', 'receipt', 'invoice', 'employment', 'caution', 'demand', 'payslip', 'warning', 'poa'];
for (const type of shareTypes) {
  const opened = [];
  const shareContext = {
    SITE_URL: 'https://docoga.com.ng',
    window: { open(...args) { opened.push(args); } },
    toast() { throw new Error('valid share type should not need an error toast'); },
  };
  vm.runInNewContext(`${shareSource}\nshareDoc(${JSON.stringify(type)});`, shareContext);
  assert.equal(opened.length, 1, `${type} opens one WhatsApp share URL`);
  const [shareUrl, target, features] = opened[0];
  const parsedShare = new URL(shareUrl);
  assert.equal(parsedShare.origin, 'https://wa.me');
  assert.equal(target, '_blank');
  assert.equal(features, 'noopener,noreferrer');
  assert.match(parsedShare.searchParams.get('text'), /https:\/\/docoga\.com\.ng/);
  assert.doesNotMatch(parsedShare.searchParams.get('text'), /SECRET|@example\.com|pass|payment reference/i,
    'share URL contains only fixed marketing copy, never private or generated document content');
}
console.log('  ✓ WhatsApp share links use fixed copy only; no generated document fields enter outbound URLs');
console.log(`  ✓ manager covers ${htmlFiles.length - UNTAGGED_PAGES.size} pages; success.html + admin.html stay untagged; legal pages are not measured`);

console.log('✅ Analytics consent suite passed. All Google scripts are stubbed; no network was used.');
