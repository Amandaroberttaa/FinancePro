const CACHE_NAME = "financepro-v2";
const urlsToCache = [
  "/",
  "/static/style.css",
  "/static/script.js",
  "/static/manifest.json",
  "/static/img/logo.png",
  "/static/img/icon-192.png",
  "/static/img/icon-512.png",
  "https://cdn.jsdelivr.net/npm/chart.js"
];

self.addEventListener("install", event => {
  self.skipWaiting();
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener("activate", event => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(
      keys.filter(key => key !== CACHE_NAME).map(key => caches.delete(key))
    ))
  );
  self.clients.claim();
});

self.addEventListener("fetch", event => {
  const requestUrl = new URL(event.request.url);
  if (requestUrl.pathname.startsWith("/api/")) {
    event.respondWith(fetch(event.request));
    return;
  }

  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});
