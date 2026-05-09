const CACHE_NAME = "financepro-v1";
const urlsToCache = [
  "/",
  "/static/style.css",
  "/static/script.js",
  "/static/manifest.json",
  "/static/img/img.jpg",
  "/static/img/icon-192.png",
  "/static/img/icon-512.png",
  "https://cdn.jsdelivr.net/npm/chart.js"
];

self.addEventListener("install", event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => cache.addAll(urlsToCache))
  );
});

self.addEventListener("fetch", event => {
  event.respondWith(
    caches.match(event.request).then(response => response || fetch(event.request))
  );
});