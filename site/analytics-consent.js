/*
 * DocOga privacy-first GA4 bootstrap.
 *
 * Safety boundary: the dedicated GA4 property is deliberately release-gated.
 * Keep ANALYTICS_RELEASE_ENABLED false until the privacy/data-transfer review,
 * Google contract/settings review, and the related owner confirmations are
 * complete. This script never loads Google's library while that gate is false.
 * When the gate is opened, an affirmative, unexpired choice is still required.
 *
 * This file is first-party and safe to include on local previews: the GA library
 * is restricted to the HTTPS DocOga production host and tagged pages only.
 */
(function (window, document) {
  'use strict';

  var GA4_ID = 'G-BQ1YTR0ZZJ';
  var ANALYTICS_RELEASE_ENABLED = false;
  var CONSENT_KEY = 'docoga.analytics-consent.v1';
  // Bump this version after any material change to purpose, data, provider, or transfer disclosures.
  var CONSENT_VERSION = 1;
  var CONSENT_MAX_AGE_MS = 180 * 24 * 60 * 60 * 1000;
  var GA_COOKIE_MAX_AGE_SECONDS = 90 * 24 * 60 * 60;
  var scriptElement = document.currentScript;
  var trackPage = !!(scriptElement && scriptElement.getAttribute('data-track-page') === 'true');
  var appRouteLabels = {
    home: 'Home', agreement: 'Tenancy Agreement', notice: 'Notice to Quit',
    receipt: 'Rent Receipt', invoice: 'Invoice', employment: 'Employment Contract',
    caution: 'Caution Fee Receipt', demand: 'Letter of Demand', payslip: 'Payslip',
    warning: 'Warning Letter', poa: 'Power of Attorney', docs: 'My Documents',
    pricing: 'Pricing'
  };
  var utmKeys = ['utm_source', 'utm_medium'];
  var safeUtmValues = {
    utm_source: ['google', 'bing', 'facebook', 'instagram', 'tiktok', 'youtube', 'whatsapp', 'email', 'sms', 'nairaland', 'linkedin', 'x', 'twitter', 'threads', 'docoga'],
    utm_medium: ['organic', 'social', 'referral', 'email', 'cpc', 'paid-social', 'display', 'affiliate', 'qr', 'direct', 'sms']
  };
  var deniedConsent = {
    analytics_storage: 'denied', ad_storage: 'denied',
    ad_user_data: 'denied', ad_personalization: 'denied'
  };
  var grantedAnalyticsOnly = {
    analytics_storage: 'granted', ad_storage: 'denied',
    ad_user_data: 'denied', ad_personalization: 'denied'
  };
  var currentChoice = null;
  var bannerNode = null;
  var choiceButton = null;
  var trackingStarted = false;
  var tagRequested = false;
  var tagLoaded = false;
  var lastPageLocation = null;

  if (!ANALYTICS_RELEASE_ENABLED) {
    // Retire first-party identifiers and stale choices from a previous release
    // without sending a request. Do not ask for a choice while the destination is unavailable.
    if (isProductionOrigin()) clearGoogleAnalyticsCookies();
    try { window.localStorage.removeItem(CONSENT_KEY); } catch (error) { /* storage may be blocked */ }
    installStyles();
    renderDisabledChoiceButton();
    window.DocOgaPrivacyChoices = {
      open: showDisabledNotice,
      getChoice: function () { return null; }
    };
    return;
  }

  currentChoice = readChoice();
  if (currentChoice !== 'accepted' && isProductionOrigin()) clearGoogleAnalyticsCookies();
  installStyles();
  if (currentChoice) renderChoiceButton();
  else showBanner(false);

  if (currentChoice === 'accepted') loadAnalytics();

  if (trackPage && window.addEventListener) {
    window.addEventListener('hashchange', function () {
      if (currentChoice !== 'accepted' || !trackingStarted || !isAppPage()) return;
      var info = pageInfo();
      if (!info || info.pageLocation === lastPageLocation || !sanitizeAddressBar(info)) return;
      sendPageView(info, lastPageLocation || safeReferrer(document.referrer));
      lastPageLocation = info.pageLocation;
    });
  }

  // A small public hook makes the choice control easy to integrate and test.
  window.DocOgaPrivacyChoices = {
    open: function () { showBanner(true); },
    getChoice: function () { return currentChoice; }
  };

  function readChoice() {
    try {
      var raw = window.localStorage.getItem(CONSENT_KEY);
      if (!raw) return null;
      var saved = JSON.parse(raw);
      if (!saved || saved.version !== CONSENT_VERSION ||
          (saved.choice !== 'accepted' && saved.choice !== 'rejected')) return null;
      var updatedAt = Date.parse(saved.updatedAt || '');
      if (!isFinite(updatedAt) || updatedAt > Date.now() ||
          Date.now() - updatedAt > CONSENT_MAX_AGE_MS) return null;
      return saved.choice;
    } catch (error) {
      // Storage restrictions fail closed: no recorded acceptance means no tag.
      return null;
    }
  }

  function saveChoice(choice) {
    currentChoice = choice;
    try {
      window.localStorage.setItem(CONSENT_KEY, JSON.stringify({
        version: CONSENT_VERSION,
        choice: choice,
        updatedAt: new Date().toISOString()
      }));
    } catch (error) {
      // The choice still applies for this page; it will be asked again later.
    }
  }

  function isProductionOrigin() {
    return window.location.protocol === 'https:' &&
      /^(www\.)?docoga\.com\.ng$/i.test(window.location.hostname || '');
  }

  function isAppPage() {
    var path = String(window.location.pathname || '/').toLowerCase();
    return path === '/' || /\/index\.html$/.test(path);
  }

  function appRouteFromHash(hash) {
    var raw = String(hash || '').replace(/^#/, '').split(/[?&]/, 1)[0];
    try { raw = decodeURIComponent(raw); } catch (error) { /* invalid escapes fail closed */ }
    raw = raw.toLowerCase();
    return Object.prototype.hasOwnProperty.call(appRouteLabels, raw) ? raw : 'home';
  }

  function currentAppRoute() {
    return appRouteFromHash(window.location.hash);
  }

  function safeUtmValue(key, value) {
    var text = String(value || '').trim().toLowerCase();
    if (!safeUtmValues[key] || safeUtmValues[key].indexOf(text) === -1) return '';
    return text;
  }

  function safeSearch(url) {
    var result = new URLSearchParams();
    var seen = Object.create(null);
    var params = new URLSearchParams(url.search || '');
    params.forEach(function (value, key) {
      var normalizedKey = String(key).toLowerCase();
      if (utmKeys.indexOf(normalizedKey) === -1 || seen[normalizedKey]) return;
      var safeValue = safeUtmValue(normalizedKey, value);
      if (!safeValue) return;
      seen[normalizedKey] = true;
      result.append(normalizedKey, safeValue);
    });
    return result.toString();
  }

  function pageInfo() {
    try {
      var url = new URL(window.location.href);
      var search = safeSearch(url);
      var route = isAppPage() ? currentAppRoute() : null;
      var path = isAppPage() ? '/' : url.pathname;
      var fragment = route ? '#' + route : '';
      var pageLocation = url.origin + path + (search ? '?' + search : '') + fragment;
      var title = route ? 'DocOga — ' + appRouteLabels[route] : String(document.title || 'DocOga').slice(0, 160);
      return {
        pageLocation: pageLocation,
        pageTitle: title,
        route: route,
        search: search,
        path: path
      };
    } catch (error) {
      return null;
    }
  }

  function safeReferrer(referrer) {
    if (!referrer) return '';
    try {
      var url = new URL(referrer);
      if (url.protocol !== 'http:' && url.protocol !== 'https:') return '';
      // Same-origin referrers retain only a static path and a whitelisted SPA
      // route. External referrers are reduced to origin only.
      if (url.origin === window.location.origin) {
        var route = (/^\/$|\/index\.html$/i.test(url.pathname)) ? appRouteFromHash(url.hash) : null;
        return url.origin + url.pathname + (route ? '#' + route : '');
      }
      return url.origin;
    } catch (error) {
      return '';
    }
  }

  function sanitizeAddressBar(info) {
    try {
      var url = new URL(window.location.href);
      var next = info.path + (info.search ? '?' + info.search : '') + (isAppPage() ? '#' + info.route : url.hash);
      var expected = url.origin + next;
      if (url.href !== expected) {
        if (!window.history || typeof window.history.replaceState !== 'function') return false;
        window.history.replaceState(window.history.state, '', next);
      }
      return true;
    } catch (error) {
      // Do not start Analytics if unsafe URL parameters could not be removed.
      return false;
    }
  }

  function loadAnalytics() {
    if (!ANALYTICS_RELEASE_ENABLED || !trackPage || currentChoice !== 'accepted' ||
        !isProductionOrigin() || trackingStarted) return;
    var info = pageInfo();
    if (!info || !sanitizeAddressBar(info)) return;
    if (tagLoaded) {
      startMeasurement(info);
      return;
    }
    if (tagRequested) return;

    try {
      window.dataLayer = window.dataLayer || [];
      window.gtag = function () { window.dataLayer.push(arguments); };
      // Queue only a denied default before the library loads. If consent is
      // withdrawn while the script is in flight, no config or page_view is queued.
      window.gtag('consent', 'default', deniedConsent);

      var googleTag = document.createElement('script');
      googleTag.async = true;
      googleTag.referrerPolicy = 'no-referrer';
      googleTag.src = 'https://www.googletagmanager.com/gtag/js?id=' + encodeURIComponent(GA4_ID);
      googleTag.onload = function () {
        tagRequested = false;
        tagLoaded = true;
        if (currentChoice !== 'accepted' || !ANALYTICS_RELEASE_ENABLED) {
          if (window.gtag) window.gtag('consent', 'update', deniedConsent);
          clearGoogleAnalyticsCookies();
          return;
        }
        var readyInfo = pageInfo();
        if (!readyInfo || !sanitizeAddressBar(readyInfo)) return;
        startMeasurement(readyInfo);
      };
      googleTag.onerror = function () { tagRequested = false; trackingStarted = false; };
      if (!document.head) return;
      tagRequested = true;
      document.head.appendChild(googleTag);
    } catch (error) {
      tagRequested = false;
      trackingStarted = false;
    }
  }

  function startMeasurement(info) {
    if (currentChoice !== 'accepted' || !window.gtag) return;
    var referrer = safeReferrer(document.referrer);
    window.gtag('consent', 'update', grantedAnalyticsOnly);
    window.gtag('js', new Date());
    window.gtag('config', GA4_ID, {
      send_page_view: false,
      page_location: info.pageLocation,
      page_referrer: referrer,
      page_title: info.pageTitle,
      allow_google_signals: false,
      allow_ad_personalization_signals: false,
      cookie_expires: GA_COOKIE_MAX_AGE_SECONDS,
      cookie_update: false
    });
    trackingStarted = true;
    sendPageView(info, referrer);
    lastPageLocation = info.pageLocation;
  }

  function sendPageView(info, referrer) {
    if (!window.gtag || !info || currentChoice !== 'accepted') return;
    window.gtag('event', 'page_view', {
      page_location: info.pageLocation,
      page_referrer: referrer || '',
      page_title: info.pageTitle
    });
  }

  function clearGoogleAnalyticsCookies() {
    var cookies;
    try { cookies = String(document.cookie || '').split(';'); }
    catch (error) { return; }
    var domains = ['', 'docoga.com.ng', '.docoga.com.ng'];
    cookies.forEach(function (cookie) {
      var name = cookie.split('=', 1)[0].trim();
      if (!/^_ga(?:_|$)/i.test(name)) return;
      domains.forEach(function (domain) {
        var expire = name + '=; Max-Age=0; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/';
        if (domain) expire += '; domain=' + domain;
        try { document.cookie = expire; } catch (error) { /* best effort */ }
      });
    });
  }

  function choose(choice) {
    saveChoice(choice);
    removeBanner();
    renderChoiceButton();

    if (choice === 'rejected') {
      if ((trackingStarted || tagRequested) && window.gtag) window.gtag('consent', 'update', deniedConsent);
      trackingStarted = false;
      lastPageLocation = null;
      clearGoogleAnalyticsCookies();
      return;
    }

    if (!trackingStarted && !tagRequested) loadAnalytics();
  }

  function installStyles() {
    if (document.getElementById('docoga-consent-styles')) return;
    var style = document.createElement('style');
    style.id = 'docoga-consent-styles';
    style.textContent = [
      '#docoga-consent-banner{position:fixed;inset:0 0 auto;z-index:2147483000;background:#fff;color:#14211a;border-bottom:3px solid #0047e1;box-shadow:0 5px 24px rgba(20,31,51,.2);padding:calc(12px + env(safe-area-inset-top,0px)) 16px 14px;font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}',
      '#docoga-consent-banner .docoga-consent-inner{max-width:1040px;margin:0 auto}',
      '#docoga-consent-banner h2{margin:0 0 5px;font-size:18px;line-height:1.3}',
      '#docoga-consent-banner p{margin:6px 0}',
      '#docoga-consent-banner a{color:#0035a8;font-weight:700;text-decoration:underline}',
      '#docoga-consent-banner .docoga-consent-actions{display:flex;gap:10px;margin-top:11px}',
      '#docoga-consent-banner button,#docoga-privacy-choices{font:700 14px/1.25 system-ui,-apple-system,"Segoe UI",sans-serif;cursor:pointer;border:2px solid #0047e1;border-radius:9px;background:#0047e1;color:#fff;padding:10px 14px}',
      '#docoga-consent-banner .docoga-consent-actions button{flex:1;min-height:44px}',
      '#docoga-consent-banner button:focus-visible,#docoga-privacy-choices:focus-visible{outline:3px solid #f2a93b;outline-offset:2px}',
      '#docoga-consent-banner .docoga-consent-close{display:block;margin:8px 0 0 auto;background:#fff;color:#0035a8;min-height:44px}',
      '#docoga-privacy-choices{position:fixed;left:12px;bottom:calc(76px + env(safe-area-inset-bottom,0px));z-index:2147482000;box-shadow:0 2px 12px rgba(0,0,0,.2);font-size:12px;padding:9px 12px;min-height:44px}',
      '@media(max-width:520px){#docoga-consent-banner{font-size:13px;padding-left:12px;padding-right:12px}#docoga-consent-banner h2{font-size:16px}#docoga-consent-banner .docoga-consent-actions{gap:8px}#docoga-consent-banner button{font-size:13px;padding:10px 8px}}'
    ].join('\n');
    (document.head || document.body).appendChild(style);
  }

  function showBanner(isSettings) {
    removeBanner();
    var banner = document.createElement('section');
    banner.id = 'docoga-consent-banner';
    banner.setAttribute('role', 'region');
    banner.setAttribute('aria-labelledby', 'docoga-consent-title');
    banner.setAttribute('aria-live', 'polite');

    var inner = document.createElement('div');
    inner.className = 'docoga-consent-inner';
    var heading = document.createElement('h2');
    heading.id = 'docoga-consent-title';
    heading.textContent = 'Your analytics choice';
    inner.appendChild(heading);

    if (isSettings && currentChoice) {
      var status = document.createElement('p');
      status.id = 'docoga-consent-current-choice';
      status.textContent = 'Current choice: ' + (currentChoice === 'accepted' ? 'Analytics accepted.' : 'Analytics rejected.');
      inner.appendChild(status);
    }

    var details = document.createElement('p');
    details.textContent = 'Optional Google Analytics helps DocOga understand which pages are useful. If you accept, Google may receive page views, session/engagement timing signals, broad browser/device details, approximate location, and (if separately enabled) interaction metadata such as scrolls, outbound link clicks, and form identifiers (not form field values). Google may process data outside Nigeria; read the Privacy Policy for details. DocOga does not send document contents, pass codes, or payment references. Rejecting does not limit any DocOga feature.';
    inner.appendChild(details);

    var policy = document.createElement('a');
    policy.href = new URL('privacy.html', window.location.href).href;
    policy.textContent = 'Read the Privacy Policy';
    inner.appendChild(policy);

    var actions = document.createElement('div');
    actions.className = 'docoga-consent-actions';
    var accept = document.createElement('button');
    accept.type = 'button';
    accept.id = 'docoga-accept-analytics';
    accept.textContent = 'Accept analytics';
    accept.addEventListener('click', function () { choose('accepted'); });
    var reject = document.createElement('button');
    reject.type = 'button';
    reject.id = 'docoga-reject-analytics';
    reject.textContent = 'Reject analytics';
    reject.addEventListener('click', function () { choose('rejected'); });
    actions.appendChild(accept);
    actions.appendChild(reject);
    inner.appendChild(actions);

    if (currentChoice) {
      var close = document.createElement('button');
      close.type = 'button';
      close.className = 'docoga-consent-close';
      close.id = 'docoga-close-analytics-settings';
      close.textContent = 'Close';
      close.addEventListener('click', removeBanner);
      inner.appendChild(close);
    }

    banner.appendChild(inner);
    document.body.appendChild(banner);
    bannerNode = banner;
  }

  function removeBanner() {
    if (bannerNode && bannerNode.parentNode) bannerNode.parentNode.removeChild(bannerNode);
    bannerNode = null;
    var existing = document.getElementById('docoga-consent-banner');
    if (existing && existing.parentNode) existing.parentNode.removeChild(existing);
  }

  function showDisabledNotice() {
    removeBanner();
    var banner = document.createElement('section');
    banner.id = 'docoga-consent-banner';
    banner.setAttribute('role', 'region');
    banner.setAttribute('aria-labelledby', 'docoga-consent-title');
    var inner = document.createElement('div');
    inner.className = 'docoga-consent-inner';
    var heading = document.createElement('h2');
    heading.id = 'docoga-consent-title';
    heading.textContent = 'Optional analytics is off';
    var status = document.createElement('p');
    status.id = 'docoga-analytics-disabled-status';
    status.textContent = 'DocOga has not enabled Google Analytics in this release. This build does not request or write an Analytics choice or tracking cookie, and all document tools remain available. If Analytics is enabled after the privacy, property, and transfer reviews, you will be asked before any measurement starts.';
    var policy = document.createElement('a');
    policy.href = new URL('privacy.html', window.location.href).href;
    policy.textContent = 'Read the Privacy Policy';
    var close = document.createElement('button');
    close.type = 'button';
    close.className = 'docoga-consent-close';
    close.id = 'docoga-close-analytics-status';
    close.textContent = 'Close';
    close.addEventListener('click', removeBanner);
    inner.appendChild(heading);
    inner.appendChild(status);
    inner.appendChild(policy);
    inner.appendChild(close);
    banner.appendChild(inner);
    document.body.appendChild(banner);
    bannerNode = banner;
  }

  function renderDisabledChoiceButton() {
    if (choiceButton) return;
    var button = document.createElement('button');
    button.type = 'button';
    button.id = 'docoga-privacy-choices';
    button.textContent = 'Privacy choices';
    button.setAttribute('aria-label', 'Review analytics status and privacy choices');
    button.addEventListener('click', showDisabledNotice);
    document.body.appendChild(button);
    choiceButton = button;
  }

  function renderChoiceButton() {
    if (!currentChoice || choiceButton) return;
    var button = document.createElement('button');
    button.type = 'button';
    button.id = 'docoga-privacy-choices';
    button.textContent = 'Privacy choices';
    button.setAttribute('aria-label', 'Review or change your analytics choice');
    button.addEventListener('click', function () { showBanner(true); });
    document.body.appendChild(button);
    choiceButton = button;
  }

})(window, document);
