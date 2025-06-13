/**
 * Push Worker - Ecosistema de Emprendimiento
 * ==========================================
 * 
 * Este Service Worker está dedicado a manejar las notificaciones push.
 * Recibe mensajes push del servidor, muestra notificaciones al usuario
 * y gestiona las acciones del usuario sobre estas notificaciones.
 * 
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.1.0
 * @updated: 2025-03-15
 */

// Nombre de la caché para assets de notificaciones (opcional, si se usan iconos/imágenes cacheadas)
const NOTIFICATION_ASSETS_CACHE_NAME = 'notification-assets-v1';

// ============================================================================
// EVENTOS DEL SERVICE WORKER (PUSH)
// ============================================================================

/**
 * Evento 'install': Se dispara cuando el Service Worker se instala.
 * Usamos skipWaiting() para activar el nuevo Service Worker inmediatamente.
 */
self.addEventListener('install', (event) => {
    console.log('Push Worker: Instalado');
    // Forzar la activación inmediata del nuevo Service Worker
    // Esto es útil para que las actualizaciones de push se apliquen rápidamente.
    event.waitUntil(self.skipWaiting());
});

/**
 * Evento 'activate': Se dispara cuando el Service Worker se activa.
 * Usamos clients.claim() para que el Service Worker tome control de las
 * páginas abiertas inmediatamente.
 */
self.addEventListener('activate', (event) => {
    console.log('Push Worker: Activado y listo para manejar notificaciones push.');
    // Tomar control inmediato de las páginas no controladas
    event.waitUntil(self.clients.claim());
    // Opcional: Limpiar caches antiguas si este worker manejara caches.
});

/**
 * Evento 'push': Se dispara cuando el Service Worker recibe un mensaje push
 * desde el servidor (a través de un servicio como FCM, Web Push Protocol, etc.).
 */
self.addEventListener('push', (event) => {
    console.log('Push Worker: Notificación Push Recibida.');

    let notificationData = {};
    let payloadText = 'Tienes una nueva notificación.';

    // Intentar parsear el payload de la notificación
    if (event.data) {
        try {
            payloadText = event.data.text(); // Guardar el texto original por si el JSON falla
            notificationData = event.data.json();
            console.log('Push Worker: Payload JSON parseado:', notificationData);
        } catch (e) {
            console.warn('Push Worker: No se pudo parsear el payload como JSON, usando texto plano.', e);
            // Si falla el parseo JSON, usamos el texto directamente como cuerpo.
            // El título será uno por defecto.
            notificationData = {
                title: 'Nueva Notificación',
                body: payloadText,
                icon: '/static/img/icons/icon-192x192.png', // Icono por defecto
                data: { url: '/' } // URL por defecto al hacer clic
            };
        }
    } else {
        console.log('Push Worker: Notificación push recibida sin payload.');
        // Configurar datos por defecto si no hay payload
        notificationData = {
            title: 'Notificación del Ecosistema',
            body: payloadText,
            icon: '/static/img/icons/icon-192x192.png',
            data: { url: '/' }
        };
    }

    // Definir el título y las opciones de la notificación
    const title = notificationData.title || 'Ecosistema de Emprendimiento';
    const options = {
        body: notificationData.body || 'Haz clic para ver más detalles.',
        icon: notificationData.icon || '/static/img/icons/icon-192x192.png', // Icono principal
        badge: notificationData.badge || '/static/img/icons/icon-96x96.png', // Icono para la barra de estado (Android)
        image: notificationData.image, // URL de una imagen grande para mostrar en la notificación
        vibrate: notificationData.vibrate || [200, 100, 200, 100, 200], // Patrón de vibración
        tag: notificationData.tag || 'ecosistema-notification', // Agrupa notificaciones
        renotify: notificationData.renotify || false, // Si una nueva notificación con el mismo tag debe vibrar/sonar
        requireInteraction: notificationData.requireInteraction || false, // Si la notificación debe permanecer hasta que el usuario interactúe
        silent: notificationData.silent || false, // Si la notificación debe ser silenciosa
        timestamp: notificationData.timestamp || Date.now(), // Timestamp de la notificación
        
        // Datos adicionales que se pueden pasar a la aplicación al hacer clic
        data: {
            url: notificationData.data?.url || '/', // URL a abrir al hacer clic
            id: notificationData.data?.id, // ID específico del elemento (ej. proyecto, mensaje)
            type: notificationData.data?.type, // Tipo de notificación para manejo en cliente
            ...(notificationData.data || {}) // Fusionar cualquier otro dato
        },
        
        // Acciones personalizadas (botones en la notificación)
        actions: notificationData.actions || []
        // Ejemplo de actions:
        // actions: [
        //   { action: 'ver_proyecto', title: 'Ver Proyecto', icon: '/static/img/icons/view.png' },
        //   { action: 'marcar_leido', title: 'Marcar como Leído', icon: '/static/img/icons/read.png' }
        // ]
    };

    // Mostrar la notificación
    // event.waitUntil() asegura que el Service Worker no se termine
    // hasta que la promesa de showNotification se resuelva.
    event.waitUntil(
        self.registration.showNotification(title, options)
            .then(() => console.log('Push Worker: Notificación mostrada.'))
            .catch(err => console.error('Push Worker: Error al mostrar notificación:', err))
    );
});

/**
 * Evento 'notificationclick': Se dispara cuando el usuario hace clic en una notificación
 * generada por este Service Worker.
 */
self.addEventListener('notificationclick', (event) => {
    console.log('Push Worker: Clic en notificación recibido.');

    // Cerrar la notificación
    event.notification.close();

    const notificationData = event.notification.data;
    const action = event.action; // Identificador de la acción si se hizo clic en un botón

    console.log('Push Worker: Datos de la notificación:', notificationData);
    if (action) {
        console.log('Push Worker: Acción seleccionada:', action);
    }

    // Lógica para manejar el clic en la notificación o en una acción
    event.waitUntil(
        clients.matchAll({ type: 'window', includeUncontrolled: true }).then((windowClients) => {
            const urlToOpen = notificationData?.url || '/';
            
            // Si se hizo clic en una acción específica
            if (action) {
                // Ejemplo: Abrir una URL diferente o enviar un mensaje a la página
                if (action === 'ver_proyecto' && notificationData?.id) {
                    const projectUrl = `/proyectos/${notificationData.id}`;
                    console.log(`Push Worker: Abriendo URL de acción: ${projectUrl}`);
                    return clients.openWindow(projectUrl);
                } else if (action === 'marcar_leido' && notificationData?.id) {
                    // Lógica para marcar como leído (podría ser una petición fetch a la API)
                    console.log(`Push Worker: Marcando notificación ${notificationData.id} como leída.`);
                    // fetch(`/api/notifications/${notificationData.id}/read`, { method: 'POST' });
                    return; // No abrir ventana para esta acción
                }
                // Manejar otras acciones...
            }

            // Comportamiento por defecto al hacer clic en el cuerpo de la notificación
            // Buscar si ya hay una ventana/tab abierta con la URL de destino
            for (let i = 0; i < windowClients.length; i++) {
                const client = windowClients[i];
                // Comparamos solo el pathname para evitar problemas con hashes o query params
                // si no son relevantes para la decisión de re-enfocar.
                const clientPath = new URL(client.url).pathname;
                const targetPath = new URL(urlToOpen, self.location.origin).pathname;

                if (clientPath === targetPath && 'focus' in client) {
                    console.log('Push Worker: Cliente existente encontrado, enfocando:', client.url);
                    return client.focus();
                }
            }

            // Si no hay cliente existente, abrir una nueva ventana/tab
            if (clients.openWindow) {
                console.log('Push Worker: Abriendo nueva ventana:', urlToOpen);
                return clients.openWindow(urlToOpen);
            }
        })
        .catch(err => console.error('Push Worker: Error en notificationclick:', err))
    );
});

/**
 * Evento 'notificationclose': Se dispara cuando el usuario cierra una notificación
 * sin hacer clic en ella (ej. la descarta).
 * Opcional, pero útil para analíticas o limpieza.
 */
self.addEventListener('notificationclose', (event) => {
    console.log('Push Worker: Notificación cerrada por el usuario.');
    const dismissedNotification = event.notification;
    console.log('Push Worker: Datos de la notificación cerrada:', dismissedNotification.data);

    // Aquí podrías enviar un evento de analítica al servidor para registrar
    // que la notificación fue descartada.
    // Ejemplo:
    // const analyticsData = {
    //   notificationId: dismissedNotification.data?.id,
    //   action: 'dismissed',
    //   timestamp: new Date().toISOString()
    // };
    // fetch('/api/analytics/notification_event', {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify(analyticsData)
    // });
});

/**
 * Evento 'message': Para comunicación desde las páginas del cliente al Service Worker.
 * Puede ser útil para, por ejemplo, forzar una actualización del SW o pedir datos.
 */
self.addEventListener('message', (event) => {
    if (event.data && event.data.type === 'GET_PUSH_WORKER_VERSION') {
        console.log('Push Worker: Solicitud de versión recibida.');
        event.ports[0].postMessage({ version: '1.1.0' });
    }
    // Manejar otros tipos de mensajes si es necesario
});

console.log('Push Worker: Script cargado y escuchando eventos.');

