// SPEC: SPEC-COMP-03
// Copia local de los estáticos del login. Simula la caché de borde del móvil.
const CACHE = "trotamundos-movil-v1";
const ARCHIVOS = [
  "/movil/",
  "/movil/index.html",
  "/movil/estilos.css",
  "/movil/app.js",
  "/movil/manifest.webmanifest",
  "/movil/icono.svg",
];

self.addEventListener("install", (evento) => {
  evento.waitUntil(caches.open(CACHE).then((cache) => cache.addAll(ARCHIVOS)));
  self.skipWaiting();
});

self.addEventListener("activate", (evento) => {
  evento.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", (evento) => {
  const url = new URL(evento.request.url);
  if (url.origin !== self.location.origin || !url.pathname.startsWith("/movil")) return;
  evento.respondWith(caches.match(evento.request).then((guardado) => guardado || fetch(evento.request)));
});
