// Minimal service worker for Password Manager (scope: /passwd/)
self.addEventListener('install', event => {
  // Activate immediately
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(clients.claim());
});

self.addEventListener('message', (event) => {
  if (event.data && event.data.command === 'SKIP_WAITING') {
    self.skipWaiting();
  }
});

// Basic network-first fetch handler with cache fallback for offline resilience
self.addEventListener('fetch', event => {
  const req = event.request;
  // Only attempt to handle GET requests
  if (req.method !== 'GET') return;

  event.respondWith(
    fetch(req).then(res => {
      // Optionally cache responses here if desired
      return res;
    }).catch(() => caches.match(req))
  );
});
