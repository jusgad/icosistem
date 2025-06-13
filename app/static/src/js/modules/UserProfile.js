/**
 * Ecosistema Emprendimiento - User Profile Module
 * ==============================================
 * 
 * Módulo para gestionar el perfil del usuario, incluyendo
 * visualización, edición de datos personales, foto de perfil
 * y configuraciones de privacidad.
 * 
 * @author: Ecosistema Emprendimiento Team
 * @version: 1.0.0
 * @updated: 2025
 * @requires: main.js, app.js, state.js, AuthManager.js
 */

'use strict';

class UserProfile {
    constructor(container, app) {
        this.container = typeof container === 'string' ? 
            document.querySelector(container) : container;
        
        if (!this.container) {
            throw new Error('Container for UserProfile not found');
        }

        this.app = app || window.EcosistemaApp;
        this.main = this.app?.main || window.App;
        this.state = this.app?.state || window.EcosistemaStateManager;
        this.authManager = this.app?.authManager || window.AuthManager;
        this.config = window.getConfig ? window.getConfig('modules.userProfile', {}) : {};

        // Configuración del módulo
        this.moduleConfig = {
            profileApiEndpoint: '/users/profile',
            avatarUploadEndpoint: '/users/profile/avatar',
            privacySettingsEndpoint: '/users/profile/privacy',
            defaultAvatar: '/static/img/default-avatar.png',
            maxAvatarSize: 2 * 1024 * 1024, // 2MB
            allowedAvatarTypes: ['image/jpeg', 'image/png', 'image/gif'],
            ...this.config
        };

        // Estado interno del módulo
        this.moduleState = {
            isInitialized: false,
            isLoading: false,
            userData: null,
            editMode: false,
            privacySettings: {}
        };

        this.elements = {};
        this.eventListeners = new Map();

        this.init();
    }

    /**
     * Inicializar módulo
     */
    async init() {
        if (this.moduleState.isInitialized) return;

        try {
            console.log('👤 Inicializando User Profile');
            this.showLoader(true, 'Cargando perfil...');

            this.createStructure();
            this.bindElements();
            this.setupEventListeners();
            
            await this.loadUserProfile();
            
            this.moduleState.isInitialized = true;
            console.log('✅ User Profile inicializado');
        } catch (error) {
            console.error('❌ Error inicializando User Profile:', error);
            this.showError('Error al inicializar el perfil de usuario', error.message);
        } finally {
            this.showLoader(false);
        }
    }

    /**
     * Crear estructura DOM del módulo
     */
    createStructure() {
        this.container.innerHTML = `
            <div class="user-profile" data-module="user-profile">
                <div class="profile-header card mb-4">
                    <div class="card-body text-center">
                        <div class="avatar-container mb-3">
                            <img src="${this.moduleConfig.defaultAvatar}" alt="Avatar" 
                                 class="profile-avatar rounded-circle" 
                                 id="profileAvatarImage" width="150" height="150">
                            <label for="avatarUpload" class="avatar-edit-btn btn btn-sm btn-light" title="Cambiar avatar">
                                <i class="fas fa-camera"></i>
                            </label>
                            <input type="file" id="avatarUpload" class="d-none" accept="image/*">
                        </div>
                        <h3 id="profileName" class="mb-1"></h3>
                        <p id="profileEmail" class="text-muted mb-2"></p>
                        <p id="profileRole" class="badge bg-primary"></p>
                        <div class="mt-3">
                            <button class="btn btn-outline-primary btn-sm" data-action="toggle-edit-mode">
                                <i class="fas fa-edit me-1"></i> Editar Perfil
                            </button>
                        </div>
                    </div>
                </div>

                <div class="profile-content">
                    <!-- Vista de Perfil -->
                    <div id="profileViewSection" class="card">
                        <div class="card-header">
                            <h5 class="card-title mb-0">Información Personal</h5>
                        </div>
                        <div class="card-body">
                            <dl class="row">
                                <dt class="col-sm-3">Nombre Completo:</dt>
                                <dd class="col-sm-9" data-field="full_name"></dd>
                                
                                <dt class="col-sm-3">Email:</dt>
                                <dd class="col-sm-9" data-field="email"></dd>

                                <dt class="col-sm-3">Teléfono:</dt>
                                <dd class="col-sm-9" data-field="phone"></dd>

                                <dt class="col-sm-3">Rol:</dt>
                                <dd class="col-sm-9" data-field="role_display_name"></dd>
                                
                                <dt class="col-sm-3">Organización:</dt>
                                <dd class="col-sm-9" data-field="company"></dd>

                                <dt class="col-sm-3">Cargo:</dt>
                                <dd class="col-sm-9" data-field="job_title"></dd>

                                <dt class="col-sm-3">Biografía:</dt>
                                <dd class="col-sm-9" data-field="bio" style="white-space: pre-wrap;"></dd>
                            </dl>
                        </div>
                    </div>

                    <!-- Formulario de Edición -->
                    <div id="profileEditSection" class="card d-none">
                        <div class="card-header">
                            <h5 class="card-title mb-0">Editar Perfil</h5>
                        </div>
                        <div class="card-body">
                            <form id="profileEditForm">
                                <div class="row">
                                    <div class="col-md-6 mb-3">
                                        <label for="editFirstName" class="form-label">Nombre</label>
                                        <input type="text" class="form-control" id="editFirstName" name="first_name" required>
                                    </div>
                                    <div class="col-md-6 mb-3">
                                        <label for="editLastName" class="form-label">Apellido</label>
                                        <input type="text" class="form-control" id="editLastName" name="last_name" required>
                                    </div>
                                </div>
                                <div class="mb-3">
                                    <label for="editPhone" class="form-label">Teléfono</label>
                                    <input type="tel" class="form-control" id="editPhone" name="phone">
                                </div>
                                <div class="mb-3">
                                    <label for="editCompany" class="form-label">Organización</label>
                                    <input type="text" class="form-control" id="editCompany" name="company">
                                </div>
                                <div class="mb-3">
                                    <label for="editJobTitle" class="form-label">Cargo</label>
                                    <input type="text" class="form-control" id="editJobTitle" name="job_title">
                                </div>
                                <div class="mb-3">
                                    <label for="editBio" class="form-label">Biografía</label>
                                    <textarea class="form-control" id="editBio" name="bio" rows="4"></textarea>
                                </div>
                                <div class="form-actions text-end">
                                    <button type="button" class="btn btn-secondary me-2" data-action="cancel-edit">Cancelar</button>
                                    <button type="submit" class="btn btn-primary">Guardar Cambios</button>
                                </div>
                            </form>
                        </div>
                    </div>

                    <!-- Configuración de Privacidad -->
                    <div id="privacySettingsSection" class="card mt-4">
                        <div class="card-header">
                            <h5 class="card-title mb-0">Configuración de Privacidad</h5>
                        </div>
                        <div class="card-body">
                            <form id="privacySettingsForm">
                                <div class="form-check form-switch mb-2">
                                    <input class="form-check-input" type="checkbox" role="switch" id="profilePublic" name="profile_public">
                                    <label class="form-check-label" for="profilePublic">Perfil Público</label>
                                </div>
                                <div class="form-check form-switch mb-2">
                                    <input class="form-check-input" type="checkbox" role="switch" id="contactInfoPublic" name="contact_info_public">
                                    <label class="form-check-label" for="contactInfoPublic">Información de Contacto Pública</label>
                                </div>
                                <div class="form-check form-switch mb-2">
                                    <input class="form-check-input" type="checkbox" role="switch" id="activityPublic" name="activity_public">
                                    <label class="form-check-label" for="activityPublic">Actividad Pública</label>
                                </div>
                                <div class="mt-3 text-end">
                                    <button type="submit" class="btn btn-primary btn-sm">Guardar Privacidad</button>
                                </div>
                            </form>
                        </div>
                    </div>
                </div>
                <div class="profile-loader d-none">
                    <div class="spinner-border text-primary" role="status">
                        <span class="visually-hidden">Cargando...</span>
                    </div>
                    <p class="mt-2">Actualizando perfil...</p>
                </div>
            </div>
        `;
    }

    /**
     * Obtener referencias a elementos DOM
     */
    bindElements() {
        this.elements = {
            // Header
            avatarImage: this.container.querySelector('#profileAvatarImage'),
            avatarUploadInput: this.container.querySelector('#avatarUpload'),
            profileName: this.container.querySelector('#profileName'),
            profileEmail: this.container.querySelector('#profileEmail'),
            profileRole: this.container.querySelector('#profileRole'),
            toggleEditButton: this.container.querySelector('[data-action="toggle-edit-mode"]'),
            // View Section
            profileViewSection: this.container.querySelector('#profileViewSection'),
            viewFields: this.container.querySelectorAll('#profileViewSection [data-field]'),
            // Edit Section
            profileEditSection: this.container.querySelector('#profileEditSection'),
            profileEditForm: this.container.querySelector('#profileEditForm'),
            cancelEditButton: this.container.querySelector('[data-action="cancel-edit"]'),
            // Privacy Section
            privacySettingsForm: this.container.querySelector('#privacySettingsForm'),
            // Loader
            loader: this.container.querySelector('.profile-loader')
        };
    }

    /**
     * Configurar event listeners
     */
    setupEventListeners() {
        this.elements.toggleEditButton?.addEventListener('click', () => {
            this.toggleEditMode(!this.moduleState.editMode);
        });

        this.elements.profileEditForm?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleProfileUpdate();
        });

        this.elements.cancelEditButton?.addEventListener('click', () => {
            this.toggleEditMode(false);
        });

        this.elements.avatarUploadInput?.addEventListener('change', (e) => {
            this.handleAvatarUpload(e);
        });
        
        this.elements.privacySettingsForm?.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handlePrivacyUpdate();
        });
    }

    /**
     * Cargar datos del perfil del usuario
     */
    async loadUserProfile() {
        this.showLoader(true);
        try {
            // Intentar obtener del AuthManager primero
            let userData = this.authManager?.getCurrentUser();
            
            if (!userData || !userData.profile_details) { // Asumimos que profile_details tiene más info
                userData = await this.main.http.get(this.moduleConfig.profileApiEndpoint);
            }
            
            this.moduleState.userData = userData;
            this.moduleState.privacySettings = userData.privacy_settings || {};
            this.renderProfile();
            this.renderPrivacySettings();
        } catch (error) {
            console.error('Error cargando perfil:', error);
            this.showError('No se pudo cargar la información del perfil.');
        } finally {
            this.showLoader(false);
        }
    }

    /**
     * Renderizar datos del perfil en la UI
     */
    renderProfile() {
        const user = this.moduleState.userData;
        if (!user) return;

        this.elements.avatarImage.src = user.avatar_url || this.moduleConfig.defaultAvatar;
        this.elements.profileName.textContent = user.full_name || `${user.first_name} ${user.last_name}`;
        this.elements.profileEmail.textContent = user.email;
        this.elements.profileRole.textContent = user.role_display_name || user.role;

        this.elements.viewFields.forEach(field => {
            const fieldName = field.dataset.field;
            field.textContent = user[fieldName] || 'No especificado';
        });

        // Si estamos en modo edición, también actualizar el formulario
        if (this.moduleState.editMode) {
            this.populateEditForm();
        }
    }
    
    /**
     * Renderizar configuración de privacidad
     */
    renderPrivacySettings() {
        const settings = this.moduleState.privacySettings;
        const form = this.elements.privacySettingsForm;
        if (!form) return;

        for (const key in settings) {
            const input = form.querySelector(`[name="${key}"]`);
            if (input && input.type === 'checkbox') {
                input.checked = settings[key];
            }
        }
    }

    /**
     * Alternar modo de edición
     * @param {boolean} edit - True para modo edición, false para modo vista
     */
    toggleEditMode(edit) {
        this.moduleState.editMode = edit;
        if (edit) {
            this.populateEditForm();
            this.elements.profileViewSection.classList.add('d-none');
            this.elements.profileEditSection.classList.remove('d-none');
            this.elements.toggleEditButton.innerHTML = '<i class="fas fa-times me-1"></i> Cancelar Edición';
        } else {
            this.elements.profileViewSection.classList.remove('d-none');
            this.elements.profileEditSection.classList.add('d-none');
            this.elements.toggleEditButton.innerHTML = '<i class="fas fa-edit me-1"></i> Editar Perfil';
        }
    }

    /**
     * Llenar formulario de edición con datos actuales
     */
    populateEditForm() {
        const user = this.moduleState.userData;
        const form = this.elements.profileEditForm;
        if (!user || !form) return;

        form.querySelector('#editFirstName').value = user.first_name || '';
        form.querySelector('#editLastName').value = user.last_name || '';
        form.querySelector('#editPhone').value = user.phone || '';
        form.querySelector('#editCompany').value = user.company || '';
        form.querySelector('#editJobTitle').value = user.job_title || '';
        form.querySelector('#editBio').value = user.bio || '';
    }

    /**
     * Manejar actualización del perfil
     */
    async handleProfileUpdate() {
        const form = this.elements.profileEditForm;
        const formData = new FormData(form);
        const dataToUpdate = Object.fromEntries(formData.entries());

        this.showLoader(true, 'Actualizando perfil...');
        try {
            const updatedUser = await this.main.http.put(this.moduleConfig.profileApiEndpoint, dataToUpdate);
            
            this.moduleState.userData = { ...this.moduleState.userData, ...updatedUser };
            this.authManager?.updateAuthState(true, this.moduleState.userData, this.authManager.getToken(), this.authManager.moduleState.tokenExpiresAt); // Actualizar AuthManager
            
            this.renderProfile();
            this.toggleEditMode(false);
            this.main.notifications.success('Perfil actualizado exitosamente.');
        } catch (error) {
            console.error('Error actualizando perfil:', error);
            this.showError('No se pudo actualizar el perfil.', error.message || '');
        } finally {
            this.showLoader(false);
        }
    }

    /**
     * Manejar subida de avatar
     * @param {Event} event - Evento de cambio del input file
     */
    async handleAvatarUpload(event) {
        const file = event.target.files[0];
        if (!file) return;

        // Validar archivo
        if (file.size > this.moduleConfig.maxAvatarSize) {
            this.showError('El archivo es demasiado grande.', `Máximo ${this.moduleConfig.maxAvatarSize / 1024 / 1024}MB`);
            return;
        }
        if (!this.moduleConfig.allowedAvatarTypes.includes(file.type)) {
            this.showError('Tipo de archivo no permitido.', `Permitidos: ${this.moduleConfig.allowedAvatarTypes.join(', ')}`);
            return;
        }

        const formData = new FormData();
        formData.append('avatar', file);

        this.showLoader(true, 'Subiendo avatar...');
        try {
            const response = await this.main.http.post(this.moduleConfig.avatarUploadEndpoint, formData, {
                headers: {} // Dejar que el navegador establezca Content-Type para FormData
            });
            
            this.moduleState.userData.avatar_url = response.avatar_url;
            this.authManager?.updateAuthState(true, this.moduleState.userData, this.authManager.getToken(), this.authManager.moduleState.tokenExpiresAt);
            
            this.elements.avatarImage.src = response.avatar_url;
            this.main.notifications.success('Avatar actualizado exitosamente.');
        } catch (error) {
            console.error('Error subiendo avatar:', error);
            this.showError('No se pudo subir el avatar.', error.message || '');
        } finally {
            this.showLoader(false);
            event.target.value = ''; // Resetear input file
        }
    }
    
    /**
     * Manejar actualización de configuración de privacidad
     */
    async handlePrivacyUpdate() {
        const form = this.elements.privacySettingsForm;
        const formData = new FormData(form);
        const privacyData = {};
        
        form.querySelectorAll('input[type="checkbox"]').forEach(input => {
            privacyData[input.name] = input.checked;
        });

        this.showLoader(true, 'Actualizando privacidad...');
        try {
            const updatedSettings = await this.main.http.put(this.moduleConfig.privacySettingsEndpoint, privacyData);
            
            this.moduleState.privacySettings = updatedSettings;
            this.moduleState.userData.privacy_settings = updatedSettings; // Asegurar que el user data también se actualice
            this.authManager?.updateAuthState(true, this.moduleState.userData, this.authManager.getToken(), this.authManager.moduleState.tokenExpiresAt);
            
            this.renderPrivacySettings();
            this.main.notifications.success('Configuración de privacidad actualizada.');
        } catch (error) {
            console.error('Error actualizando privacidad:', error);
            this.showError('No se pudo actualizar la configuración de privacidad.', error.message || '');
        } finally {
            this.showLoader(false);
        }
    }

    /**
     * Mostrar/ocultar loader
     */
    showLoader(show, message = 'Cargando...') {
        if (this.elements.loader) {
            this.elements.loader.classList.toggle('d-none', !show);
            if (show) {
                const messageEl = this.elements.loader.querySelector('p');
                if (messageEl) messageEl.textContent = message;
            }
        }
        this.moduleState.isLoading = show;
    }

    /**
     * Mostrar mensaje de error
     */
    showError(title, message = '') {
        if (this.main.notifications) {
            this.main.notifications.error(message || title, { title: message ? title : 'Error' });
        } else {
            console.error(title, message);
        }
    }

    /**
     * Destruir módulo y limpiar recursos
     */
    destroy() {
        this.eventListeners.forEach((handler, element) => {
            element.removeEventListener(handler.event, handler.callback);
        });
        this.container.innerHTML = '';
        this.moduleState.isInitialized = false;
        console.log('🧹 User Profile destruido');
    }
}

// Exportar para uso en módulos o inicialización global
if (typeof module !== 'undefined' && module.exports) {
    module.exports = UserProfile;
} else {
    window.UserProfile = UserProfile;
}

// Inicialización automática si el contenedor existe
document.addEventListener('DOMContentLoaded', () => {
    const userProfileContainer = document.getElementById('user-profile-container');
    if (userProfileContainer && window.EcosistemaApp && window.AuthManager) {
        // Asegurarse que AuthManager esté disponible y el usuario autenticado
        if (window.EcosistemaApp.authManager?.isAuthenticated()) {
            window.EcosistemaApp.userProfile = new UserProfile(userProfileContainer, window.EcosistemaApp);
        } else {
            // Si no está autenticado, podría redirigir o mostrar un mensaje
            // userProfileContainer.innerHTML = '<p class="text-center text-muted">Debes iniciar sesión para ver tu perfil.</p>';
        }
    }
});
