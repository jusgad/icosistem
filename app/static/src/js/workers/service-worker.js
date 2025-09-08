/**
 * Service Worker - Ecosistema de Emprendimiento
 * =============================================
 *
 * Maneja el caching, notificaciones push, sincronización en segundo plano
 * y funcionalidades offline para la PWA del ecosistema.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 */

// Importar scripts de Workbox (asumiendo que están en una carpeta 'workbox')
importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.5.4/workbox-sw.js')

// Verificar que Workbox se cargó correctamente
if (workbox) {
  console.log('🎉 Workbox cargado exitosamente!')

  // Configuración de Workbox
  workbox.setConfig({
    debug: true // Cambiar a false en producción
  })

  // Precaching de assets principales (App Shell)
  // Estos archivos se cachearán durante la instalación del Service Worker
  workbox.precaching.precacheAndRoute([
    { url: '/', revision: 'app-shell-v1' },
    { url: '/index.html', revision: 'app-shell-v1' },
    { url: '/manifest.json', revision: 'manifest-v1' },
    { url: '/static/css/main.css', revision: 'main-css-v1' },
    { url: '/static/js/main.js', revision: 'main-js-v1' },
    { url: '/static/js/app.js', revision: 'app-js-v1' }, // Tu archivo app.js
    { url: '/static/img/logo.png', revision: 'logo-v1' },
    { url: '/static/img/icons/icon-192x192.png', revision: 'icon-192-v1' },
    { url: '/static/img/icons/icon-512x512.png', revision: 'icon-512-v1' },
    { url: '/offline.html', revision: 'offline-page-v1' } // Página de fallback offline
    // Agrega más assets críticos aquí
  ])

  // Estrategia de cache para fuentes de Google Fonts
  workbox.routing.registerRoute(
    ({ url }) => url.origin === 'https://fonts.googleapis.com' ||
                     url.origin === 'https://fonts.gstatic.com',
    new workbox.strategies.StaleWhileRevalidate({
      cacheName: 'google-fonts',
      plugins: [
        new workbox.cacheableResponse.CacheableResponsePlugin({
          statuses: [0, 200]
        }),
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 30,
          maxAgeSeconds: 60 * 60 * 24 * 365 // 1 año
        })
      ]
    })
  )

  // Estrategia de cache para imágenes
  workbox.routing.registerRoute(
    ({ request }) => request.destination === 'image',
    new workbox.strategies.CacheFirst({
      cacheName: 'images-cache',
      plugins: [
        new workbox.cacheableResponse.CacheableResponsePlugin({
          statuses: [0, 200]
        }),
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 100, // Cachear hasta 100 imágenes
          maxAgeSeconds: 30 * 24 * 60 * 60 // 30 días
        })
      ]
    })
  )

  // Estrategia de cache para archivos CSS y JavaScript
  workbox.routing.registerRoute(
    ({ request }) => request.destination === 'script' ||
                         request.destination === 'style',
    new workbox.strategies.StaleWhileRevalidate({
      cacheName: 'static-resources-cache',
      plugins: [
        new workbox.cacheableResponse.CacheableResponsePlugin({
          statuses: [0, 200]
        })
      ]
    })
  )

  // Estrategia de cache para peticiones API (NetworkFirst)
  workbox.routing.registerRoute(
    ({ url }) => url.pathname.startsWith('/api/'),
    new workbox.strategies.NetworkFirst({
      cacheName: 'api-cache',
      networkTimeoutSeconds: 5, // Timeout para la red
      plugins: [
        new workbox.cacheableResponse.CacheableResponsePlugin({
          statuses: [0, 200]
        }),
        new workbox.expiration.ExpirationPlugin({
          maxEntries: 50,
          maxAgeSeconds: 24 * 60 * 60 // 1 día
        })
      ]
    })
  )

  // Fallback offline para navegación
  // Si una petición de navegación falla, muestra la página offline.html
  const navigationHandler = new workbox.strategies.NetworkFirst({
    cacheName: 'navigation-cache',
    plugins: [
      new workbox.cacheableResponse.CacheableResponsePlugin({
        statuses: [0, 200]
      })
    ]
  })

  const navigationRoute = new workbox.routing.NavigationRoute(navigationHandler, {
    denylist: [
      new RegExp('/api/') // No aplicar a rutas API
    ],
    allowlist: [
      new RegExp('/.*') // Aplicar a todas las demás rutas
    ]
  })
  workbox.routing.registerRoute(navigationRoute)

  // Manejador de fallback offline global
  workbox.routing.setCatchHandler(({ event }) => {
    switch (event.request.destination) {
      case 'document':
        return caches.match('/offline.html')
        // Puedes agregar fallbacks para otros tipos de contenido (imágenes, etc.)
      default:
        return Response.error()
    }
  })

  // ============================================================================
  // EVENTOS DEL SERVICE WORKER
  // ============================================================================

  self.addEventListener('install', (event) => {
    console.log('SW: Instalado')
    // Forzar la activación inmediata del nuevo Service Worker
    event.waitUntil(self.skipWaiting())
  })

  self.addEventListener('activate', (event) => {
    console.log('SW: Activado')
    // Tomar control inmediato de las páginas
    event.waitUntil(self.clients.claim())
    // Limpiar caches antiguas
    event.waitUntil(
      caches.keys().then(cacheNames => {
        return Promise.all(
          cacheNames.filter(cacheName => {
            // Define aquí un patrón para tus caches antiguas si es necesario
            return cacheName.startsWith('ecosistema-') && cacheName !== workbox.core.cacheNames.precache
          }).map(cacheName => {
            console.log('SW: Eliminando cache antigua:', cacheName)
            return caches.delete(cacheName)
          })
        )
      })
    )
  })

  self.addEventListener('message', (event) => {
    console.log('SW: Mensaje recibido:', event.data)
    if (event.data && event.data.type === 'SKIP_WAITING') {
      self.skipWaiting()
    }
    if (event.data && event.data.type === 'GET_VERSION') {
      event.ports[0].postMessage('1.0.0') // Envía la versión del SW
    }
  })

  // ============================================================================
  // BACKGROUND SYNC
  // ============================================================================

  // Registrar una cola para sincronización en segundo plano
  const bgSyncQueue = new workbox.backgroundSync.Queue('ecosistema-bg-sync-queue', {
    maxRetentionTime: 24 * 60, // Reintentar por 24 horas
    onSync: async ({ queue }) => {
      let entry
      while (entry = await queue.shiftRequest()) {
        try {
          await fetch(entry.request.clone())
          console.log('SW: Petición de Background Sync enviada:', entry.request.url)
        } catch (error) {
          console.error('SW: Falló la petición de Background Sync:', entry.request.url, error)
          // Volver a encolar la petición para reintentar más tarde
          await queue.unshiftRequest(entry)
          throw error // Importante para que Workbox sepa que falló y reintente
        }
      }
      console.log('SW: Cola de Background Sync procesada.')
    }
  })

  // Usar el plugin de Background Sync para peticiones POST fallidas a la API
  const bgSyncPlugin = new workbox.backgroundSync.BackgroundSyncPlugin('api-post-queue', {
    maxRetentionTime: 24 * 60 // Reintentar por 24 horas
  })

  workbox.routing.registerRoute(
    ({ url, request }) => url.pathname.startsWith('/api/') && request.method === 'POST',
    new workbox.strategies.NetworkOnly({
      plugins: [bgSyncPlugin]
    })
  )

  // ============================================================================
  // NOTIFICACIONES PUSH
  // ============================================================================

  self.addEventListener('push', (event) => {
    console.log('SW: Notificación Push recibida')

    let data = {}
    if (event.data) {
      try {
        data = event.data.json()
      } catch (e) {
        console.error('SW: Error parseando datos de la notificación push', e)
        data = { title: 'Notificación', body: event.data.text() }
      }
    }

    const title = data.title || 'Ecosistema de Emprendimiento'
    const options = {
      body: data.body || 'Tienes una nueva notificación.',
      icon: data.icon || '/static/img/icons/icon-192x192.png',
      badge: data.badge || '/static/img/icons/icon-96x96.png', // Para Android
      image: data.image, // URL de una imagen grande
      vibrate: data.vibrate || [200, 100, 200],
      data: data.data || { url: '/' }, // Datos adicionales, como la URL a abrir
      actions: data.actions || [] // Botones de acción
      // Ejemplo de actions:
      // actions: [
      //   { action: 'explore', title: 'Explorar', icon: '/static/img/icons/explore.png' },
      //   { action: 'close', title: 'Cerrar', icon: '/static/img/icons/close.png' },
      // ]
    }

    event.waitUntil(
      self.registration.showNotification(title, options)
    )
  })

  self.addEventListener('notificationclick', (event) => {
    console.log('SW: Click en notificación')
    event.notification.close() // Cerrar la notificación

    const notificationData = event.notification.data
    const urlToOpen = notificationData && notificationData.url ? notificationData.url : '/'

    // Abrir la URL o realizar una acción específica
    if (event.action) {
      console.log(`SW: Acción de notificación seleccionada: ${event.action}`)
      // Aquí puedes manejar acciones personalizadas, ej:
      // clients.openWindow(`/actions/${event.action}?data=${encodeURIComponent(JSON.stringify(notificationData))}`);
    } else {
      event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
          // Verificar si ya hay una ventana abierta con la URL
          const existingClient = windowClients.find(client => {
            const clientUrl = new URL(client.url)
            const targetUrl = new URL(urlToOpen, self.location.origin)
            return clientUrl.pathname === targetUrl.pathname
          })

          if (existingClient) {
            existingClient.focus()
          } else {
            clients.openWindow(urlToOpen)
          }
        })
      )
    }
  })

  self.addEventListener('notificationclose', (event) => {
    console.log('SW: Notificación cerrada', event.notification)
    // Aquí puedes realizar acciones si el usuario cierra la notificación sin interactuar
  })

  // Forzar que el Service Worker tome control de las páginas no controladas
  // Esto es útil para que el SW se active inmediatamente después de la instalación
  workbox.core.clientsClaim()
} else {
  console.error('❌ Workbox no se pudo cargar.')
}
