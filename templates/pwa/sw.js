/* Service worker de AgroSismo (paso 7.1).
   - Guarda solo archivos públicos (estilos, íconos y la página "sin conexión").
   - NO guarda páginas con datos del productor (privacidad, RNF-04).
   - Las páginas siempre se piden primero a internet. */
const VERSION = "agrosismo-v9";
const PRECACHE = [
  "/sin-conexion/",
  "/registro-rapido/",
  "/static/css/app.css",
  "/static/css/panel.css",
  "/static/css/rapido.css",
  "/static/js/offline.js",
  "/static/js/rapido.js?v=2",
  "/static/js/formato.js",
  "/static/pwa/icono-192.png?v=2",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(VERSION).then((cache) => cache.addAll(PRECACHE)).then(() => self.skipWaiting())
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((claves) => Promise.all(claves.filter((c) => c !== VERSION).map((c) => caches.delete(c))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const peticion = event.request;
  if (peticion.method !== "GET") return;
  const url = new URL(peticion.url);
  if (url.origin !== self.location.origin) return;

  // Páginas: internet primero; sin conexión solo se abre "Registro rápido" o el aviso "sin conexión".
  if (peticion.mode === "navigate") {
    event.respondWith(
      fetch(peticion).catch(() => {
        if (url.pathname === "/registro-rapido/") {
          return caches.match("/registro-rapido/").then((r) => r || caches.match("/sin-conexion/"));
        }
        return caches.match("/sin-conexion/");
      })
    );
    return;
  }

  // Archivos estáticos: usar la copia guardada y actualizarla en segundo plano.
  if (url.pathname.startsWith("/static/")) {
    event.respondWith(
      caches.open(VERSION).then((cache) =>
        cache.match(peticion).then((guardado) => {
          const red = fetch(peticion).then((resp) => {
            if (resp.ok) cache.put(peticion, resp.clone());
            return resp;
          }).catch(() => guardado);
          return guardado || red;
        })
      )
    );
  }
});
