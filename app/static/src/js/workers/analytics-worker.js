/**
 * Analytics Worker - Ecosistema de Emprendimiento
 * ==============================================
 *
 * Este Service Worker está dedicado a manejar la recolección y envío
 * de datos de analíticas de la aplicación.
 *
 * Funcionalidades:
 * - Recibir eventos de analíticas desde la aplicación principal.
 * - Almacenar eventos offline usando IndexedDB.
 * - Enviar eventos al servidor de analíticas usando Background Sync.
 * - Procesamiento en lotes para optimizar envíos.
 *
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025-03-17
 */

const ANALYTICS_DB_NAME = 'ecosistema-analytics-db'
const ANALYTICS_STORE_NAME = 'pending-analytics-events'
const ANALYTICS_SYNC_TAG = 'sync-analytics-events'
const ANALYTICS_ENDPOINT = '/api/v1/analytics/track' // Endpoint del servidor de analíticas
const MAX_BATCH_SIZE = 50 // Máximo de eventos por lote
const MAX_RETENTION_TIME = 24 * 60 * 60 * 1000 // 24 horas en milisegundos

// ============================================================================
// EVENTOS DEL SERVICE WORKER
// ============================================================================

self.addEventListener('install', (event) => {
  // // console.log('Analytics Worker: Instalado')
  // Forzar la activación inmediata del nuevo Service Worker
  event.waitUntil(self.skipWaiting())
})

self.addEventListener('activate', (event) => {
  // // console.log('Analytics Worker: Activado y listo para recolectar analíticas.')
  // Tomar control inmediato de las páginas no controladas
  event.waitUntil(self.clients.claim())
  // Opcional: Limpiar datos antiguos o realizar migraciones de IndexedDB
})

/**
 * Evento 'message': Recibe datos de analíticas desde la aplicación principal.
 */
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'TRACK_ANALYTICS_EVENT') {
    const analyticsEvent = event.data.payload
    // // console.log('Analytics Worker: Evento recibido:', analyticsEvent)

    // Añadir timestamp y metadata si no existen
    analyticsEvent.timestamp = analyticsEvent.timestamp || new Date().toISOString()
    analyticsEvent.meta = analyticsEvent.meta || {}
    analyticsEvent.meta.sw_received_at = new Date().toISOString()

    event.waitUntil(
      storeAnalyticsEvent(analyticsEvent)
        .then(() => {
          // // console.log('Analytics Worker: Evento almacenado.')
          // Intentar registrar una sincronización para enviar los datos
          return registerBackgroundSync()
        })
        .catch(err => {
          // // console.error('Analytics Worker: Error almacenando evento:', err)
        })
    )
  }
})

/**
 * Evento 'sync': Se dispara cuando el navegador detecta que hay conexión
 * y hay un tag de sincronización registrado.
 */
self.addEventListener('sync', (event) => {
  // // console.log('Analytics Worker: Evento sync recibido para el tag:', event.tag)
  if (event.tag === ANALYTICS_SYNC_TAG) {
    event.waitUntil(syncAnalyticsData())
  }
})

// ============================================================================
// LÓGICA DE INDEXEDDB
// ============================================================================

/**
 * Abre la base de datos IndexedDB.
 * @returns {Promise<IDBDatabase>}
 */
function openAnalyticsDB () {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(ANALYTICS_DB_NAME, 1)

    request.onupgradeneeded = (event) => {
      const db = event.target.result
      if (!db.objectStoreNames.contains(ANALYTICS_STORE_NAME)) {
        // Usar 'id' autoincrementado como keyPath
        db.createObjectStore(ANALYTICS_STORE_NAME, { keyPath: 'id', autoIncrement: true })
      }
    }

    request.onsuccess = (event) => {
      resolve(event.target.result)
    }

    request.onerror = (event) => {
      // // console.error('Analytics Worker: Error al abrir IndexedDB:', event.target.errorCode)
      reject('Error al abrir IndexedDB: ' + event.target.errorCode)
    }
  })
}

/**
 * Almacena un evento de analíticas en IndexedDB.
 * @param {object} eventData - El evento de analíticas a almacenar.
 * @returns {Promise<void>}
 */
async function storeAnalyticsEvent (eventData) {
  const db = await openAnalyticsDB()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([ANALYTICS_STORE_NAME], 'readwrite')
    const store = transaction.objectStore(ANALYTICS_STORE_NAME)

    // Añadir un ID único si no lo tiene (aunque el store lo autoincrementa)
    if (!eventData.id) {
      eventData.id = `evt_${new Date().getTime()}_${Math.random().toString(36).substr(2, 9)}`
    }

    const request = store.add(eventData)

    request.onsuccess = () => {
      resolve()
    }
    request.onerror = (event) => {
      // // console.error('Analytics Worker: Error al agregar evento a IndexedDB:', event.target.error)
      reject(event.target.error)
    }
  })
}

/**
 * Obtiene todos los eventos pendientes de IndexedDB.
 * @returns {Promise<Array<object>>}
 */
async function getAllPendingEvents () {
  const db = await openAnalyticsDB()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([ANALYTICS_STORE_NAME], 'readonly')
    const store = transaction.objectStore(ANALYTICS_STORE_NAME)
    const request = store.getAll() // Obtiene todos los registros

    request.onsuccess = (event) => {
      resolve(event.target.result)
    }
    request.onerror = (event) => {
      // // console.error('Analytics Worker: Error al obtener eventos de IndexedDB:', event.target.error)
      reject(event.target.error)
    }
  })
}

/**
 * Elimina eventos de IndexedDB por sus IDs.
 * @param {Array<any>} eventIds - Array de IDs de eventos a eliminar.
 * @returns {Promise<void>}
 */
async function deleteEventsByIds (eventIds) {
  if (!eventIds || eventIds.length === 0) return Promise.resolve()

  const db = await openAnalyticsDB()
  return new Promise((resolve, reject) => {
    const transaction = db.transaction([ANALYTICS_STORE_NAME], 'readwrite')
    const store = transaction.objectStore(ANALYTICS_STORE_NAME)
    let completedDeletes = 0

    eventIds.forEach(id => {
      const request = store.delete(id)
      request.onsuccess = () => {
        completedDeletes++
        if (completedDeletes === eventIds.length) {
          resolve()
        }
      }
      request.onerror = (event) => {
        // No rechazar la promesa completa por un fallo, solo loguear
        // // console.error(`Analytics Worker: Error eliminando evento ${id} de IndexedDB:`, event.target.error)
        completedDeletes++ // Contar como completado para no bloquear la promesa
        if (completedDeletes === eventIds.length) {
          resolve()
        }
      }
    })

    transaction.oncomplete = () => {
      if (completedDeletes !== eventIds.length) {
        // Esto no debería pasar si manejamos los errores individuales
        // console.warn('Analytics Worker: No todos los eventos se eliminaron como se esperaba.')
      }
      resolve()
    }
    transaction.onerror = (event) => {
      // // console.error('Analytics Worker: Error en la transacción de eliminación:', event.target.error)
      reject(event.target.error)
    }
  })
}

// ============================================================================
// LÓGICA DE SINCRONIZACIÓN EN SEGUNDO PLANO
// ============================================================================

/**
 * Registra una tarea de sincronización en segundo plano.
 * @returns {Promise<void>}
 */
async function registerBackgroundSync () {
  // Verificar si SyncManager es soportado
  if (!self.registration.sync) {
    // console.warn('Analytics Worker: BackgroundSync no es soportado por este navegador.')
    // Intentar enviar directamente si hay conexión
    if (navigator.onLine) {
      // // console.log('Analytics Worker: Intentando envío directo por falta de BackgroundSync.')
      return syncAnalyticsData()
    }
    return
  }

  try {
    await self.registration.sync.register(ANALYTICS_SYNC_TAG)
    // // console.log('Analytics Worker: Sincronización en segundo plano registrada:', ANALYTICS_SYNC_TAG)
  } catch (err) {
    // // console.error('Analytics Worker: No se pudo registrar la sincronización en segundo plano:', err)
    // Si falla el registro (ej. por permisos), intentar enviar directamente si hay conexión
    if (navigator.onLine) {
      // // console.log('Analytics Worker: Intentando envío directo por fallo en registro de BackgroundSync.')
      return syncAnalyticsData()
    }
  }
}

/**
 * Envía los datos de analíticas pendientes al servidor.
 */
async function syncAnalyticsData () {
  try {
    const pendingEvents = await getAllPendingEvents()
    if (pendingEvents.length === 0) {
      // // console.log('Analytics Worker: No hay eventos pendientes para sincronizar.')
      return
    }

    // // console.log(`Analytics Worker: Sincronizando ${pendingEvents.length} eventos.`)

    // Dividir en lotes
    const batches = []
    for (let i = 0; i < pendingEvents.length; i += MAX_BATCH_SIZE) {
      batches.push(pendingEvents.slice(i, i + MAX_BATCH_SIZE))
    }

    for (const batch of batches) {
      const eventIdsInBatch = batch.map(event => event.id)
      try {
        const response = await fetch(ANALYTICS_ENDPOINT, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json'
            // Aquí podrías agregar headers de autenticación si son necesarios
            // 'Authorization': 'Bearer <token>'
          },
          body: JSON.stringify({ events: batch })
        })

        if (response.ok) {
          // // console.log(`Analytics Worker: Lote de ${batch.length} eventos enviado exitosamente.`)
          await deleteEventsByIds(eventIdsInBatch)
          // // console.log(`Analytics Worker: ${batch.length} eventos eliminados de la cola local.`)
        } else {
          const errorData = await response.json().catch(() => ({ message: 'Error desconocido del servidor' }))
          // // console.error(`Analytics Worker: Falló el envío del lote. Status: ${response.status}`, errorData)
          // No eliminar los eventos, se reintentarán en la próxima sincronización
          // Podrías implementar lógica para marcar eventos como "fallidos" después de X reintentos
          // o si el servidor devuelve un error específico (ej. 400 Bad Request).
          if (response.status === 400) { // Bad Request, no reintentar
            // console.warn('Analytics Worker: Lote rechazado por el servidor (400), eliminando eventos para evitar bucles.')
            await deleteEventsByIds(eventIdsInBatch)
          } else {
            // Para otros errores de servidor (5xx), dejar que BackgroundSync reintente.
            throw new Error(`Server error: ${response.status}`)
          }
        }
      } catch (error) {
        // // console.error('Analytics Worker: Error de red enviando lote:', error)
        // BackgroundSync reintentará automáticamente si la promesa es rechazada.
        throw error
      }
    }
    // // console.log('Analytics Worker: Sincronización de datos completada.')
    notifyClientSyncStatus(true, pendingEvents.length)
  } catch (error) {
    // // console.error('Analytics Worker: Error durante la sincronización de datos:', error)
    notifyClientSyncStatus(false, 0, error.message)
    // Es importante relanzar el error para que BackgroundSync sepa que la sincronización falló
    // y la reintente más tarde.
    throw error
  }
}

/**
 * Notifica al cliente sobre el estado de la sincronización.
 * @param {boolean} success - Si la sincronización fue exitosa.
 * @param {number} count - Número de eventos procesados.
 * @param {string} [errorMessage] - Mensaje de error si falló.
 */
function notifyClientSyncStatus (success, count, errorMessage) {
  self.clients.matchAll({ includeUncontrolled: true, type: 'window' }).then((clients) => {
    if (clients && clients.length) {
      clients.forEach((client) => {
        client.postMessage({
          type: 'ANALYTICS_SYNC_STATUS',
          payload: {
            success,
            count,
            errorMessage: errorMessage || null,
            timestamp: new Date().toISOString()
          }
        })
      })
    }
  })
}

// // console.log('Analytics Worker: Script cargado y escuchando eventos.')
