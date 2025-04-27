// Version identifier - increase this number on each deployment
const CACHE_VERSION = 1;
const CACHE_NAME = `mqtt-thermometer-v${CACHE_VERSION}`;

// Assets to cache
const urlsToCache = [
  '/',
  '/static/styles.css',
  '/static/favicon.ico',
  '/static/apple-touch-icon.png',
  '/static/android-chrome-192x192.png',
  '/static/android-chrome-512x512.png',
  '/manifest.json',
  '/site.webmanifest'
];

// Install event - cache assets
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
      .then(() => {
        // Activate the new service worker immediately
        return self.skipWaiting();
      })
  );
});

// Activate event - clean up old caches
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.filter(cacheName => {
          return cacheName.startsWith('mqtt-thermometer-') && cacheName !== CACHE_NAME;
        }).map(cacheName => {
          console.log('Deleting old cache:', cacheName);
          return caches.delete(cacheName);
        })
      );
    }).then(() => {
      // Take control of all clients
      return self.clients.claim();
    })
  );
});

// Fetch event - serve from cache, fall back to network
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cached response if found
        if (response) {
          return response;
        }
        
        // Otherwise fetch from network
        return fetch(event.request).then(response => {
          // Don't cache non-successful responses
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }
          
          // Clone the response
          const responseToCache = response.clone();
          
          // Add to cache for future requests
          caches.open(CACHE_NAME).then(cache => {
            cache.put(event.request, responseToCache);
          });
          
          return response;
        });
      })
  );
});

// Listen for messages from the main thread
self.addEventListener('message', event => {
  if (event.data.action === 'skipWaiting') {
    self.skipWaiting();
  }
});
