/* ================================================
   OnlyJobs Service Worker  –  sw.js
   Handles: Offline cache, Background sync,
            Push notifications
   ================================================ */

var CACHE = 'onlyjobs-v1';
var OFFLINE_URL = '/onlyjob/index.html';

var PRECACHE = [
  '/onlyjob/index.html',
  '/onlyjob/latestjobs.html',
  '/onlyjob/mocktest.html',
  '/onlyjob/auth.html',
  '/onlyjob/manifest.json'
];

/* ── INSTALL: cache all core pages ── */
self.addEventListener('install', function(e) {
  e.waitUntil(
    caches.open(CACHE).then(function(cache) {
      return cache.addAll(PRECACHE);
    }).then(function() {
      return self.skipWaiting();
    })
  );
});

/* ── ACTIVATE: clean old caches ── */
self.addEventListener('activate', function(e) {
  e.waitUntil(
    caches.keys().then(function(keys) {
      return Promise.all(
        keys.filter(function(k) { return k !== CACHE; })
            .map(function(k) { return caches.delete(k); })
      );
    }).then(function() {
      return self.clients.claim();
    })
  );
});

/* ── FETCH: Network first, fallback to cache ── */
self.addEventListener('fetch', function(e) {
  if (e.request.method !== 'GET') return;

  var url = e.request.url;

  /* Always network-first for HTML pages */
  if (e.request.mode === 'navigate') {
    e.respondWith(
      fetch(e.request).then(function(res) {
        var clone = res.clone();
        caches.open(CACHE).then(function(c) { c.put(e.request, clone); });
        return res;
      }).catch(function() {
        return caches.match(e.request).then(function(cached) {
          return cached || caches.match(OFFLINE_URL);
        });
      })
    );
    return;
  }

  /* Cache first for fonts / static assets */
  if (url.includes('fonts.googleapis') || url.includes('fonts.gstatic')) {
    e.respondWith(
      caches.match(e.request).then(function(cached) {
        if (cached) return cached;
        return fetch(e.request).then(function(res) {
          var clone = res.clone();
          caches.open(CACHE).then(function(c) { c.put(e.request, clone); });
          return res;
        });
      })
    );
    return;
  }

  /* Default: network with cache fallback */
  e.respondWith(
    fetch(e.request).catch(function() {
      return caches.match(e.request);
    })
  );
});

/* ── PUSH NOTIFICATIONS ── */
self.addEventListener('push', function(e) {
  var data = {};
  try {
    data = e.data ? e.data.json() : {};
  } catch(err) {
    data = { title: 'OnlyJobs', body: e.data ? e.data.text() : 'New update!', url: '/onlyjob/latestjobs.html' };
  }

  var title = data.title || 'OnlyJobs – New Job Alert!';
  var options = {
    body: data.body || 'New government job notification available. Tap to view!',
    icon: '/onlyjob/icon-192.png',
    badge: '/onlyjob/icon-192.png',
    vibrate: [200, 100, 200],
    tag: data.tag || 'onlyjobs-alert',
    renotify: true,
    requireInteraction: false,
    data: { url: data.url || '/onlyjob/latestjobs.html' },
    actions: [
      { action: 'view', title: 'View Jobs' },
      { action: 'test', title: 'Take Mock Test' }
    ]
  };

  e.waitUntil(self.registration.showNotification(title, options));
});

/* ── NOTIFICATION CLICK ── */
self.addEventListener('notificationclick', function(e) {
  e.notification.close();
  var url = '/onlyjob/index.html';

  if (e.action === 'view') url = '/onlyjob/latestjobs.html';
  else if (e.action === 'test') url = '/onlyjob/mocktest.html';
  else if (e.notification.data && e.notification.data.url) url = e.notification.data.url;

  e.waitUntil(
    clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function(wins) {
      for (var i = 0; i < wins.length; i++) {
        if (wins[i].url.includes('onlyjob') && 'focus' in wins[i]) {
          wins[i].navigate(url);
          return wins[i].focus();
        }
      }
      return clients.openWindow(url);
    })
  );
});

/* ── BACKGROUND SYNC (for offline form saves) ── */
self.addEventListener('sync', function(e) {
  if (e.tag === 'sync-scores') {
    e.waitUntil(syncScores());
  }
});

function syncScores() {
  return new Promise(function(resolve) {
    /* Future: sync scores to Firebase when back online */
    resolve();
  });
}
