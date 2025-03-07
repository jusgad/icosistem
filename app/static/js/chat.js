/**
 * chat.js - Scripts para la funcionalidad de mensajería en tiempo real
 */

// Clase para manejar la funcionalidad de chat
class ChatManager {
    constructor(options = {}) {
        // Opciones por defecto
        this.options = Object.assign({
            socketUrl: '', // URL del servidor Socket.IO
            chatContainer: '#chat-container',
            messagesList: '#messages-list',
            messageInput: '#message-input',
            sendButton: '#send-button',
            userTypingIndicator: '#user-typing',
            usersList: '#users-list',
            currentUserId: null,
            currentUserName: null,
            currentRelationshipId: null
        }, options);
        
        // Referencias a elementos del DOM
        this.chatContainer = document.querySelector(this.options.chatContainer);
        this.messagesList = document.querySelector(this.options.messagesList);
        this.messageInput = document.querySelector(this.options.messageInput);
        this.sendButton = document.querySelector(this.options.sendButton);
        this.userTypingIndicator = document.querySelector(this.options.userTypingIndicator);
        this.usersList = document.querySelector(this.options.usersList);
        
        // Estado del chat
        this.socket = null;
        this.isConnected = false;
        this.activeConversation = null;
        this.conversations = {};
        this.typingTimeout = null;
        
        // Inicializar
        this.init();
    }
    
    // Inicializar el chat
    init() {
        // Verificar si los elementos necesarios existen
        if (!this.chatContainer || !this.messagesList || !this.messageInput || !this.sendButton) {
            console.warn('Elementos de chat no encontrados en el DOM');
            return;
        }
        
        // Verificar si Socket.IO está disponible
        if (typeof io === 'undefined') {
            console.warn('Socket.IO no está disponible. La funcionalidad de chat en tiempo real no funcionará.');
            return;
        }
        
        // Verificar si se proporcionó un ID de usuario
        if (!this.options.currentUserId) {
            console.warn('No se proporcionó un ID de usuario. La funcionalidad de chat no se inicializará.');
            return;
        }
        
        // Conectar al servidor Socket.IO
        this.connectSocket();
        
        // Configurar eventos de la interfaz
        this.setupUIEvents();
    }
    
    // Conectar al servidor Socket.IO
    connectSocket() {
        // Crear conexión Socket.IO
        this.socket = io(this.options.socketUrl, {
            query: {
                userId: this.options.currentUserId,
                userName: this.options.currentUserName
            }
        });
        
        // Configurar eventos del socket
        this.socket.on('connect', () => {
            console.log('Conectado al servidor de chat');
            this.isConnected = true;
            
            // Unirse a la sala de la relación si existe
            if (this.options.currentRelationshipId) {
                this.socket.emit('join_relationship', {
                    relationshipId: this.options.currentRelationshipId
                });
            }
        });
        
        this.socket.on('disconnect', () => {
            console.log('Desconectado del servidor de chat');
            this.isConnected = false;
        });
        
        // Recibir mensajes
        this.socket.on('new_message', (data) => {
            this.receiveMessage(data);
        });
        
        // Indicador de escritura
        this.socket.on('user_typing', (data) => {
            this.showUserTyping(data);
        });
        
        // Actualización de usuarios en línea
        this.socket.on('users_online', (data) => {
            this.updateOnlineUsers(data);
        });
        
        // Historial de mensajes
        this.socket.on('message_history', (data) => {
            this.loadMessageHistory(data);
        });
    }
    
    // Configurar eventos de la interfaz
    setupUIEvents() {
        // Enviar mensaje al hacer clic en el botón
        if (this.sendButton) {
            this.sendButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.sendMessage();
            });
        }
        
        // Enviar mensaje al presionar Enter
        if (this.messageInput) {
            this.messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    this.sendMessage();
                }
            });
            
            // Emitir evento de escritura
            this.messageInput.addEventListener('input', () => {
                this.emitTyping();
            });
        }
        
        // Cambiar de conversación al hacer clic en un usuario
        if (this.usersList) {
            this.usersList.addEventListener('click', (e) => {
                const userItem = e.target.closest('.user-item');
                if (userItem) {
                    const userId = userItem.dataset.userId;
                    this.changeConversation(userId);
                }
            });
        }
    }
    
    // Enviar un mensaje
    sendMessage() {
        if (!this.messageInput || !this.isConnected) return;
        
        const messageText = this.messageInput.value.trim();
        if (!messageText) return;
        
        // Crear objeto de mensaje
        const message = {
            text: messageText,
            senderId: this.options.currentUserId,
            senderName: this.options.currentUserName,
            relationshipId: this.options.currentRelationshipId,
            timestamp: new Date().toISOString()
        };
        
        // Enviar mensaje al servidor
        this.socket.emit('send_message', message);
        
        // Limpiar campo de entrada
        this.messageInput.value = '';
        
        // Mostrar mensaje en la interfaz
        this.displayMessage(message, true);
    }
    
    // Recibir un mensaje
    receiveMessage(message) {
        // Verificar si el mensaje es para la conversación actual
        if (this.activeConversation && message.senderId !== this.activeConversation && 
            message.senderId !== this.options.currentUserId) {
            // Almacenar mensaje en la conversación correspondiente
            if (!this.conversations[message.senderId]) {
                this.conversations[message.senderId] = [];
            }
            this.conversations[message.senderId].push(message);
            
            // Mostrar indicador de mensaje no leído
            this.showUnreadIndicator(message.senderId);
        } else {
            // Mostrar mensaje en la interfaz
            this.displayMessage(message, false);
        }
    }
    
    // Mostrar mensaje en la interfaz
    displayMessage(message, isOwnMessage) {
        if (!this.messagesList) return;
        
        const messageElement = document.createElement('div');
        messageElement.classList.add('message');
        messageElement.classList.add(isOwnMessage ? 'message-own' : 'message-other');
        
        const timestamp = new Date(message.timestamp);
        const formattedTime = timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        
        messageElement.innerHTML = `
            <div class="message-content">
                ${!isOwnMessage ? `<div class="message-sender">${message.senderName}</div>` : ''}
                <div class="message-text">${this.escapeHtml(message.text)}</div>
                <div class="message-time">${formattedTime}</div>
            </div>
        `;
        
        this.messagesList.appendChild(messageElement);
        
        // Desplazar al final
        this.messagesList.scrollTop = this.messagesList.scrollHeight;
    }
    
    // Emitir evento de escritura
    emitTyping() {
        if (!this.isConnected) return;
        
        // Limpiar timeout anterior
        if (this.typingTimeout) {
            clearTimeout(this.typingTimeout);
        }
        
        // Emitir evento de escritura
        this.socket.emit('typing', {
            userId: this.options.currentUserId,
            userName: this.options.currentUserName,
            relationshipId: this.options.currentRelationshipId
        });
        
        // Establecer timeout para dejar de mostrar "escribiendo..."
        this.typingTimeout = setTimeout(() => {
            this.socket.emit('stop_typing', {
                userId: this.options.currentUserId,
                relationshipId: this.options.currentRelationshipId
            });
        }, 2000);
    }
    
    // Mostrar indicador de escritura
    showUserTyping(data) {
        if (!this.userTypingIndicator) return;
        
        if (data.isTyping) {
            this.userTypingIndicator.textContent = `${data.userName} está escribiendo...`;
            this.userTypingIndicator.style.display = 'block';
        } else {
            this.userTypingIndicator.style.display = 'none';
        }
    }
    
    // Actualizar lista de usuarios en línea
    updateOnlineUsers(users) {
        if (!this.usersList) return;
        
        // Limpiar lista actual
        this.usersList.innerHTML = '';
        
        // Agregar cada usuario
        users.forEach(user => {
            if (user.id === this.options.currentUserId) return;
            
            const userElement = document.createElement('div');
            userElement.classList.add('user-item');
            userElement.dataset.userId = user.id;
            
            // Agregar indicador de mensaje no leído si corresponde
            const hasUnread = this.conversations[user.id] && this.conversations[user.id].length > 0;
            
            userElement.innerHTML = `
                <div class="user-avatar">
                    <div class="user-status ${user.online ? 'online' : 'offline'}"></div>
                </div>
                <div class="user-info">
                    <div class="user-name">${user.name}</div>
                    ${hasUnread ? '<div class="unread-indicator">Nuevo</div>' : ''}
                </div>
            `;
            
            this.usersList.appendChild(userElement);
        });
    }
    
    // Cambiar a otra conversación
    changeConversation(userId) {
        // Guardar conversación anterior
        if (this.activeConversation) {
            // Implementar lógica para guardar mensajes si es necesario
        }
        
        // Establecer nueva conversación activa
        this.activeConversation = userId;
        
        // Limpiar mensajes actuales
        if (this.messagesList) {
            this.messagesList.innerHTML = '';
        }
        
        // Cargar mensajes de la conversación
        if (this.conversations[userId]) {
            this.conversations[userId].forEach(message => {
                this.displayMessage(message, message.senderId === this.options.currentUserId);
            });
            
            // Limpiar mensajes no leídos
            this.conversations[userId] = [];
            this.clearUnreadIndicator(userId);
        }
        
        // Solicitar historial de mensajes al servidor
        this.socket.emit('get_message_history', {
            userId: this.options.currentUserId,
            otherUserId: userId
        });
    }
    
    // Cargar historial de mensajes
    loadMessageHistory(messages) {
        if (!this.messagesList) return;
        
        // Limpiar mensajes actuales
        this.messagesList.innerHTML = '';
        
        // Mostrar mensajes
        messages.forEach(message => {
            this.displayMessage(message, message.senderId === this.options.currentUserId);
        });
    }
    
    // Mostrar indicador de mensaje no leído
    showUnreadIndicator(userId) {
        const userItem = this.usersList ? this.usersList.querySelector(`[data-user-id="${userId}"]`) : null;
        if (!userItem) return;
        
        let unreadIndicator = userItem.querySelector('.unread-indicator');
        if (!unreadIndicator) {
            unreadIndicator = document.createElement('div');
            unreadIndicator.classList.add('unread-indicator');
            unreadIndicator.textContent = 'Nuevo';
            userItem.querySelector('.user-info').appendChild(unreadIndicator);
        }
    }
    
    // Limpiar indicador de mensaje no leído
    clearUnreadIndicator(userId) {
        const userItem = this.usersList ? this.usersList.querySelector(`[data-user-id="${userId}"]`) : null;
        if (!userItem) return;
        
        const unreadIndicator = userItem.querySelector('.unread-indicator');
        if (unreadIndicator) {
            unreadIndicator.remove();
        }
    }
    
    // Escapar HTML para prevenir XSS
    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// Inicializar chat cuando el DOM esté listo
document.addEventListener('DOMContentLoaded', function() {
    // Obtener datos del usuario actual del elemento data
    const chatContainer = document.querySelector('#chat-container');
    if (!chatContainer) return;
    
    const currentUserId = chatContainer.dataset.userId;
    const currentUserName = chatContainer.dataset.userName;
    const currentRelationshipId = chatContainer.dataset.relationshipId;
    const socketUrl = chatContainer.dataset.socketUrl || window.location.origin;
    
    // Inicializar gestor de chat
    window.chatManager = new ChatManager({
        socketUrl: socketUrl,
        currentUserId: currentUserId,
        currentUserName: currentUserName,
        currentRelationshipId: currentRelationshipId
    });
});