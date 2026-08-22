/* ============================================================================
   EGS STANDARD SERVICE WORKER — identical across every EGS app, EXCEPT the
   install handler below: notebuilt is the one EGS app with a vault key that
   lives only in page memory, so it's the one app where an instant activation
   (skipWaiting -> clients.claim -> reload) can silently drop that key mid-use.
   Every other app still self-activates on install; here activation waits for
   an explicit SKIP_WAITING message that index.html only sends once the vault
   is locked and no capture is in flight. See VAULT_SW_GATE in index.html.

   You change ONE line per app: APP_NAME. egs-deploy.sh stamps CACHE_VERSION
   on every deploy. The caching DECISIONS live in sw_logic.js (unit-tested);
   this worker imports and runs that exact code, so what's tested is what ships.

   Why updates "just work": HTML is served NETWORK-FIRST. Online, the browser
   always fetches the freshly deployed index.html; the cache is only the
   offline fallback. No re-download, no manual cache clearing, ever.
   ========================================================================== */

importScripts('./sw_logic.js');   // provides self.EGS_SW

const APP_NAME      = 'notebuilt';   // <-- the ONE line you change per app
const CACHE_VERSION = '2026.08.22-1222';             // <-- egs-deploy.sh stamps this each deploy
const CACHE = EGS_SW.cacheName(APP_NAME, CACHE_VERSION);

// Offline shell. For single-file apps this is basically index.html + icons.
const SHELL = [
  './', './index.html', './manifest.webmanifest',
  './icons/icon-192.png', './icons/icon-512.png'
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(CACHE)
      .then((c) => c.addAll(SHELL).catch(() => {}))   // tolerate a missing asset
    // VAULT_SW_GATE: no self.skipWaiting() here. With no prior controller
    // (first install ever) the browser activates this worker on its own —
    // nothing changes for a fresh install. With a prior controller (an
    // update), this worker now WAITS until the page tells it to go, via the
    // 'message' listener below. That page-side gate is what makes it safe
    // for this one app to defer activation without touching the network-first
    // fetch path (unchanged below) or breaking every other EGS app's
    // instant-activate behavior.
  );
});

self.addEventListener('message', (e) => {
  if (e.data === 'SKIP_WAITING') self.skipWaiting();   // sent only when index.html has confirmed it's safe
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        EGS_SW.staleCaches(keys, APP_NAME, CACHE_VERSION).map((k) => caches.delete(k))
      ))
      .then(() => self.clients.claim())                // control open pages immediately
  );
});

self.addEventListener('fetch', (e) => {
  const req = e.request;
  if (req.method !== 'GET') return;                    // never cache writes (backend-safe)

  const strategy = EGS_SW.strategyFor(req.mode, req.headers.get('accept'));

  if (strategy === 'network-first') {
    // SW_DEADLINE — fresh HTML when online; cached HTML when offline OR when
    // the network hangs without answering. The cache write is attached to the
    // NETWORK promise, not to the race, so a response that arrives after the
    // deadline still lands in the cache for the next launch.
    const net = fetch(req)
      .then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); return res; });
    net.catch(() => {});                               // a late failure is not an unhandled rejection
    e.respondWith(
      EGS_SW.raceTimeout(net, EGS_SW.NET_TIMEOUT_MS, () =>
        caches.match(req)
          .then((r) => r || caches.match('./index.html'))
          .then((r) => r || net))                      // nothing cached at all: the network is all there is
    );
    return;
  }

  // stale-while-revalidate: instant from cache, refreshed in the background.
  e.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((res) => { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); return res; })
        .catch(() => cached);
      return cached || network;
    })
  );
});
