// ============================================================================
//  EGS platform — service-worker logic (the tested core the SW imports)
//  Kept as its own file so the DECISIONS that make updates "just work" are
//  provable in node, and the real service worker runs this exact code via
//  importScripts — no drift between what's tested and what ships.
// ============================================================================
(function(global){

  // Cache name for an app at a version. One app can have many old caches;
  // exactly one is current.
  function cacheName(app, version){ return 'egs-' + app + '-' + version; }

  // Given every cache key on the device, which belong to THIS app but are old
  // and must be deleted on activate. Never touches other apps' caches.
  function staleCaches(keys, app, version){
    var keep = cacheName(app, version);
    return keys.filter(function(k){
      return k.indexOf('egs-' + app + '-') === 0 && k !== keep;
    });
  }

  // The strategy for a request. THE decision that removes update pain:
  // HTML/navigations are NETWORK-FIRST so a fresh deploy is picked up on the
  // next online launch with no cache-clearing; everything else is
  // stale-while-revalidate (instant from cache, refreshed in the background).
  function strategyFor(reqMode, acceptHeader){
    if(reqMode === 'navigate' || (acceptHeader || '').indexOf('text/html') >= 0)
      return 'network-first';
    return 'stale-while-revalidate';
  }

  // A version stamp is YYYY.MM.DD-HHMM — human-readable, sortable, eyeball-able.
  function isValidVersion(v){ return /^\d{4}\.\d{2}\.\d{2}-\d{4}$/.test(v); }

  var api = { cacheName:cacheName, staleCaches:staleCaches, strategyFor:strategyFor, isValidVersion:isValidVersion };
  if(typeof module !== 'undefined') module.exports = api;
  global.EGS_SW = api;

})(typeof self !== 'undefined' ? self : this);
