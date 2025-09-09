/**
 * Sync Worker - Ecosistema de Emprendimiento
 * ==========================================
 *
 * Este Service Worker está dedicado a manejar la sincronización en segundo plano.
 * Permite que la aplicación guarde datos offline y los envíe al servidor
 * cuando la conexión esté disponible.
 *
 * Funcionalidades:
 * - Sincronización de datos de formularios (ej. creación de proyectos, tareas).
 * - Reintento de peticiones API fallidas.
 * - Notificación al usuario sobre el estado de la sincronización.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025-03-16
 */

/* global importScripts, workbox, clients, self */

// Importar Workbox si se usa para estrategias de reintento de red
importScripts('https://storage.googleapis.com/workbox-cdn/releases/6.5.4/workbox-sw.js')

const SYNC_TAG_PROJECT_SUBMISSION = 'sync-new-project'
const SYNC_TAG_TASK_UPDATE = 'sync-task-update'
const QUEUE_NAME_FAILED_REQUESTS = 'ecosistema-failed-requests-queue'

// Nombre para la base de datos IndexedDB donde se guardarán los datos pendientes
const PENDING_SYNC_DB_NAME = 'ecosistema-pending-sync'
const PENDING_PROJECTS_STORE = 'pending-projects'
const PENDING_TASKS_STORE = 'pending-tasks'

if (workbox) {
  // // // console.log('Sync Worker: Workbox cargado exitosamente!')

  // Configurar un plugin de Background Sync para reintentar peticiones POST fallidas
  const bgSyncPlugin = new workbox.backgroundSync.BackgroundSyncPlugin(QUEUE_NAME_FAILED_REQUESTS, {
    maxRetentionTime: 24 * 60, // Reintentar por 24 horas
    onSync: async ({ queue }) => {
      let entry
      while (entry = await queue.shiftRequest()) {
        try {
          const response = await fetch(entry.request.clone())
          // // // console.log('Sync Worker (Workbox): Petición reintentada y enviada:', entry.request.url)
          // Opcional: notificar al cliente sobre el éxito
          self.clients.matchAll().then(clients => {
            clients.forEach(client => client.postMessage({
              type: 'SYNC_SUCCESS_WORKBOX',
              url: entry.request.url
            }))
          })
        } catch (error) {
          // // // console.error('Sync Worker (Workbox): Falló el reintento de la petición:', entry.request.url, error)
          // Volver a encolar la petición para reintentar más tarde
          await queue.unshiftRequest(entry)
          // Opcional: notificar al cliente sobre el fallo persistente
          self.clients.matchAll().then(clients => {
            clients.forEach(client => client.postMessage({
              type: 'SYNC_FAILURE_WORKBOX',
              url: entry.request.url,
              error: error.message
            }))
          })
          throw error // Importante para que Workbox sepa que falló y reintente
        }
      }
      // // // console.log('Sync Worker (Workbox): Cola de peticiones fallidas procesada.')
    }
  })

  // Registrar una ruta para que las peticiones POST a la API usen el plugin de Background Sync
  workbox.routing.registerRoute(
    ({ url, request }) => url.pathname.startsWith('/api/') && request.method === 'POST',
    new workbox.strategies.NetworkOnly({
      plugins: [bgSyncPlugin]
    })
  )
} else {
  // // console.warn('Sync Worker: Workbox no se pudo cargar. Algunas funcionalidades de reintento automático podrían no estar disponibles.')
}

// ============================================================================
// EVENTOS DEL SERVICE WORKER (SYNC)
// ============================================================================

self.addEventListener('install', (event) => {
  // // // console.log('Sync Worker: Instalado')
  event.waitUntil(self.skipWaiting())
})

self.addEventListener('activate', (event) => {
  // // // console.log('Sync Worker: Activado y listo para manejar sincronización en segundo plano.')
  event.waitUntil(self.clients.claim())
})

/**
 * Evento 'sync': Se dispara cuando el navegador detecta que hay conexión
 * y hay un tag de sincronización registrado.
 */
self.addEventListener('sync', (event) => {
  // // // console.log('Sync Worker: Evento sync recibido para el tag:', event.tag)

  if (event.tag === SYNC_TAG_PROJECT_SUBMISSION) {
    event.waitUntil(syncNewProjects())
  } else if (event.tag === SYNC_TAG_TASK_UPDATE) {
    event.waitUntil(syncTaskUpdates())
  }
  // Aquí puedes agregar más manejadores para diferentes tags de sincronización
})

/**
 * Evento 'message': Para comunicación desde las páginas del cliente al Service Worker.
 * Puede ser útil para, por ejemplo, registrar datos para sincronización.
 */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'QUEUE_PROJECT_FOR_SYNC') {
    // // // console.log('Sync Worker: Recibido proyecto para encolar:', event.data.payload)
    event.waitUntil(
      addPendingData(PENDING_PROJECTS_STORE, event.data.payload)
        .then(() => registerBackgroundSync(SYNC_TAG_PROJECT_SUBMISSION))
        .then(() => {
          // Enviar confirmación de vuelta al cliente
          if (event.ports && event.ports[0]) {
            event.ports[0].postMessage({ status: 'PROJECT_QUEUED', id: event.data.payload.id })
          }
        })
        .catch(err => {
          if (event.ports && event.ports[0]) {
            event.ports[0].postMessage({ status: 'PROJECT_QUEUE_FAILED', error: err.message })
          }
        })
    )
  }
  // Agrega más manejadores de mensajes si es necesario
})

// ============================================================================
// LÓGICA DE SINCRONIZACIÓN PERSONALIZADA (CON INDEXEDDB)
// ============================================================================

/**
 * Abre la base de datos IndexedDB.
 * @returns {Promise<IDBDatabase>}
 */
function openPendingSyncDB () {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(PENDING_SYNC_DB_NAME, 1)

    request.onupgradeneeded = (event) => {
      const db = event.target.result
      if (!db.objectStoreNames.contains(PENDING_PROJECTS_STORE)) {
        db.createObjectStore(PENDING_PROJECTS_STORE, { keyPath: 'id', autoIncrement: true })
      }
      if (!db.objectStoreNames.contains(PENDING_TASKS_STORE)) {
        db.createObjectStore(PENDING_TASKS_STORE, { keyPath: 'id', autoIncrement: true })
      }
    }

    request.onsuccess = (event) => {
      resolve(event.target.result)
    }

    request.onerror = (event) => {
      reject('Error al abrir IndexedDB: ' + event.target.errorCode)
    }
  })
}

/**
 * Agrega datos a una store de IndexedDB.
 * @param {string} storeName - Nombre del object store.
 * @param {object} data - Datos a guardar.
 * @returns {Promise<void>}
 */
async function addPendingData (storeName, data) {
  const db = await openPendingSyncDB()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([storeName], 'readwrite')
    const store = transaction.objectStore(storeName)
    const request = store.add(data)

    request.onsuccess = () => {
      // // // console.log(`Sync Worker: Datos agregados a ${storeName}:`, data.id || data)
      resolve()
    }
    request.onerror = (event) => {
      // // console.error(`Sync Worker: Error agregando datos a ${storeName}:`, event.target.error)
      reject(event.target.error)
    }
  })
}

/**
 * Obtiene todos los datos pendientes de una store.
 * @param {string} storeName - Nombre del object store.
 * @returns {Promise<Array<object>>}
 */
async function getAllPendingData (storeName) {
  const db = await openPendingSyncDB()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([storeName], 'readonly')
    const store = transaction.objectStore(storeName)
    const request = store.getAll()

    request.onsuccess = (event) => {
      resolve(event.target.result)
    }
    request.onerror = (event) => {
      reject(event.target.error)
    }
  })
}

/**
 * Elimina un dato de una store por su ID.
 * @param {string} storeName - Nombre del object store.
 * @param {any} id - ID del dato a eliminar.
 * @returns {Promise<void>}
 */
async function deletePendingData (storeName, id) {
  const db = await openPendingSyncDB()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([storeName], 'readwrite')
    const store = transaction.objectStore(storeName)
    const request = store.delete(id)

    request.onsuccess = () => {
      // // console.log(`Sync Worker: Dato eliminado de ${storeName}:`, id)
      resolve()
    }
    request.onerror = (event) => {
      reject(event.target.error)
    }
  })
}

/**
 * Registra un tag para sincronización en segundo plano.
 * @param {string} syncTag - El tag de sincronización.
 * @returns {Promise<void>}
 */
async function registerBackgroundSync (syncTag) {
  if ('serviceWorker' in navigator && 'SyncManager' in window) {
    try {
      const registration = await navigator.serviceWorker.ready
      await registration.sync.register(syncTag)
      // // console.log(`Sync Worker: Sincronización en segundo plano registrada para '${syncTag}'`)
    } catch (err) {
      // // console.error(`Sync Worker: No se pudo registrar la sincronización en segundo plano para '${syncTag}':`, err)
    }
  } else {
    // console.warn('Sync Worker: SyncManager no soportado.')
  }
}

/**
 * Sincroniza los nuevos proyectos pendientes.
 */
async function syncNewProjects () {
  try {
    const pendingProjects = await getAllPendingData(PENDING_PROJECTS_STORE)
    // // console.log('Sync Worker: Sincronizando proyectos pendientes:', pendingProjects.length)

    for (const project of pendingProjects) {
      try {
        const response = await fetch('/api/v1/projects', { // Ajusta el endpoint de tu API
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
            // Aquí podrías agregar headers de autenticación si son necesarios
            // y si el token se puede obtener de alguna forma segura en el SW
            // o si la API permite envíos anónimos que luego se asocian.
          },
          body: JSON.stringify(project)
        })

        if (response.ok) {
          const responseData = await response.json()
          // // console.log('Sync Worker: Proyecto sincronizado exitosamente:', responseData)
          await deletePendingData(PENDING_PROJECTS_STORE, project.id)
          notifyClient('PROJECT_SYNC_SUCCESS', { projectId: project.id, serverId: responseData.id })
        } else {
          const errorData = await response.json().catch(() => ({ message: 'Error desconocido del servidor' }))
          // // console.error('Sync Worker: Falló la sincronización del proyecto:', project.id, response.status, errorData)
          notifyClient('PROJECT_SYNC_FAILURE', { projectId: project.id, status: response.status, error: errorData.message })
          // No eliminar, se reintentará en la próxima sincronización o manualmente
        }
      } catch (error) {
        // // console.error('Sync Worker: Error de red sincronizando proyecto:', project.id, error)
        notifyClient('PROJECT_SYNC_NETWORK_ERROR', { projectId: project.id, error: error.message })
        // No eliminar, se reintentará
      }
    }
    showSyncNotification('Proyectos Sincronizados', 'Todos los proyectos pendientes han sido enviados al servidor.')
  } catch (error) {
    // // console.error('Sync Worker: Error procesando la cola de proyectos:', error)
    showSyncNotification('Error de Sincronización', 'Hubo un problema al sincronizar los proyectos.', true)
  }
}

/**
 * Sincroniza las actualizaciones de tareas pendientes.
 * (Implementación similar a syncNewProjects)
 */
async function syncTaskUpdates () {
  // Lógica similar a syncNewProjects pero para PENDING_TASKS_STORE
  // y el endpoint /api/v1/tasks o similar.
  // // console.log('Sync Worker: Sincronizando actualizaciones de tareas...')
  // ...
}

// ============================================================================
// UTILIDADES DE NOTIFICACIÓN Y COMUNICACIÓN CON CLIENTE
// ============================================================================

/**
 * Envía un mensaje a todas las pestañas/clientes controlados por este SW.
 * @param {string} type - Tipo de mensaje.
 * @param {object} payload - Datos del mensaje.
 */
function notifyClient (type, payload) {
  self.clients.matchAll({ includeUncontrolled: true, type: 'window' }).then((clients) => {
    if (clients && clients.length) {
      clients.forEach((client) => {
        client.postMessage({ type, payload })
      })
    }
  })
}

/**
 * Muestra una notificación al usuario.
 * @param {string} title - Título de la notificación.
 * @param {string} body - Cuerpo de la notificación.
 * @param {boolean} isError - Si es una notificación de error.
 */
function showSyncNotification (title, body, isError = false) {
  const options = {
    body,
    icon: isError ? '/static/img/icons/sync-error-icon.png' : '/static/img/icons/sync-success-icon.png',
    badge: '/static/img/icons/sync-badge.png',
    vibrate: isError ? [200, 100, 200] : [100, 50, 100],
    tag: isError ? 'sync-error-notification' : 'sync-success-notification',
    renotify: true, // Reemplaza notificaciones anteriores con el mismo tag
    actions: [
      { action: 'view_app', title: 'Abrir App' }
    ]
  }
  self.registration.showNotification(title, options)
}

// Manejador para clicks en notificaciones del Sync Worker
self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  if (event.action === 'view_app') {
    clients.openWindow('/') // O la URL específica de tu app
  }
})

// // console.log('Sync Worker: Script cargado y escuchando eventos.')
