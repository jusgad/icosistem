"""
API v1 Users Endpoints
=====================

Este módulo implementa todos los endpoints para gestión de usuarios en la API v1,
incluyendo CRUD completo, búsqueda avanzada, gestión de perfiles y operaciones
administrativas.

Funcionalidades:
- CRUD completo de usuarios
- Búsqueda y filtrado avanzado
- Gestión de perfiles por tipo de usuario
- Operaciones en lote
- Estadísticas y métricas
- Importación/exportación de datos
- Gestión de permisos y roles
"""

from flask import Blueprint, request, jsonify, current_app, g, send_file
from flask_restful import Resource, Api
from sqlalchemy import or_, and_, func, desc, asc
from sqlalchemy.orm import joinedload
from datetime import datetime, timedelta, timezone
from typing import Any, Optional
import csv
import io
import xlsxwriter
from werkzeug.utils import secure_filename
import os

from app.extensions import db, limiter
from app.models.user import User
from app.models.admin import Admin
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.models.client import Client
from app.models.organization import Organization
from app.models.activity_log import ActivityLog, ActivityType, ActivitySeverity
from app.core.exceptions import (
    ValidationError, 
    AuthenticationError, 
    AuthorizationError,
    ResourceNotFoundError,
    BusinessLogicError
)
from app.services.user_service import UserService
from app.services.email import EmailService
from app.services.file_storage import FileStorageService
from app.utils.decorators import validate_json, log_activity
from app.api.middleware.auth import api_auth_required, admin_required, get_current_user
from app.api import paginated_response, api_response
from app.api.v1 import APIv1Validator


# Crear blueprint para users
users_bp = Blueprint('users', __name__)
api = Api(users_bp)


class UsersListResource(Resource):
    """Endpoint para listar y crear usuarios"""
    
    @api_auth_required
    def get(self):
        """
        Listar usuarios con filtros y paginación
        
        Query Parameters:
            page: Número de página (default: 1)
            per_page: Elementos por página (default: 20)
            search: Término de búsqueda
            user_type: Filtrar por tipo de usuario
            is_active: Filtrar por estado activo
            organization_id: Filtrar por organización
            created_after: Filtrar por fecha de creación
            created_before: Filtrar por fecha de creación
            sort_by: Campo para ordenar (default: created_at)
            sort_order: Orden (asc/desc, default: desc)
        
        Returns:
            Lista paginada de usuarios
        """
        current_user = get_current_user()
        
        # Parámetros de paginación
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        page, per_page = APIv1Validator.validate_pagination_params(page, per_page)
        
        # Parámetros de filtrado
        search = request.args.get('search', '').strip()
        user_type = request.args.get('user_type', '').strip()
        is_active = request.args.get('is_active', type=bool)
        organization_id = request.args.get('organization_id', type=int)
        created_after = request.args.get('created_after')
        created_before = request.args.get('created_before')
        
        # Parámetros de ordenamiento
        sort_by = request.args.get('sort_by', 'created_at')
        sort_order = request.args.get('sort_order', 'desc')
        
        # Construir query base
        query = User.query
        
        # Aplicar filtros basados en permisos
        if not current_user.is_admin():
            # Usuarios no admin solo ven usuarios de su organización o públicos
            if hasattr(current_user, 'organization_id') and current_user.organization_id:
                query = query.filter(
                    or_(
                        User.organization_id == current_user.organization_id,
                        User.is_public_profile == True
                    )
                )
            else:
                query = query.filter(User.is_public_profile == True)
        
        # Aplicar filtro de búsqueda
        if search:
            search_filter = or_(
                User.first_name.ilike(f'%{search}%'),
                User.last_name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%'),
                func.concat(User.first_name, ' ', User.last_name).ilike(f'%{search}%')
            )
            query = query.filter(search_filter)
        
        # Filtro por tipo de usuario
        if user_type:
            valid_types = ['admin', 'entrepreneur', 'ally', 'client']
            if user_type in valid_types:
                query = query.filter(User.user_type == user_type)
        
        # Filtro por estado activo
        if is_active is not None:
            query = query.filter(User.is_active == is_active)
        
        # Filtro por organización
        if organization_id:
            query = query.filter(User.organization_id == organization_id)
        
        # Filtros por fecha
        if created_after:
            try:
                date_after = datetime.fromisoformat(created_after.replace('Z', '+00:00'))
                query = query.filter(User.created_at >= date_after)
            except ValueError:
                raise ValidationError("Formato de fecha inválido para created_after")
        
        if created_before:
            try:
                date_before = datetime.fromisoformat(created_before.replace('Z', '+00:00'))
                query = query.filter(User.created_at <= date_before)
            except ValueError:
                raise ValidationError("Formato de fecha inválido para created_before")
        
        # Aplicar ordenamiento
        valid_sort_fields = ['created_at', 'updated_at', 'first_name', 'last_name', 'email', 'last_login']
        if sort_by not in valid_sort_fields:
            sort_by = 'created_at'
        
        if sort_order.lower() == 'asc':
            query = query.order_by(asc(getattr(User, sort_by)))
        else:
            query = query.order_by(desc(getattr(User, sort_by)))
        
        # Ejecutar paginación
        return paginated_response(
            query=query,
            page=page,
            per_page=per_page,
            endpoint='users.userslistresource'
        )
    
    @api_auth_required
    @admin_required
    @validate_json
    @log_activity(ActivityType.USER_CREATE, "Admin user creation")
    def post(self):
        """
        Crear nuevo usuario (solo admin)
        
        Body:
            email: Email del usuario
            first_name: Nombre
            last_name: Apellido
            user_type: Tipo de usuario
            password: Contraseña (opcional, se genera automática)
            phone: Teléfono (opcional)
            organization_id: ID de organización (opcional)
            is_active: Estado activo (opcional, default: True)
            send_welcome_email: Enviar email de bienvenida (opcional, default: True)
            profile_data: Datos específicos del perfil según tipo de usuario
        
        Returns:
            Usuario creado
        """
        data = request.get_json()
        
        # Validar campos requeridos
        required_fields = ['email', 'first_name', 'last_name', 'user_type']
        for field in required_fields:
            if not data.get(field):
                raise ValidationError(f"El campo {field} es requerido")
        
        email = data['email'].strip().lower()
        first_name = data['first_name'].strip()
        last_name = data['last_name'].strip()
        user_type = data['user_type'].lower()
        
        # Verificar si el usuario ya existe
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            raise BusinessLogicError("Ya existe un usuario con este email")
        
        # Crear usuario usando el servicio
        try:
            user = UserService.create_user(
                email=email,
                first_name=first_name,
                last_name=last_name,
                user_type=user_type,
                password=data.get('password'),
                phone=data.get('phone'),
                organization_id=data.get('organization_id'),
                is_active=data.get('is_active', True),
                profile_data=data.get('profile_data', {}),
                created_by=get_current_user().id
            )
            
            # Enviar email de bienvenida si se solicita
            if data.get('send_welcome_email', True):
                try:
                    EmailService.send_welcome_email(user, data.get('password'))
                except Exception as e:
                    current_app.logger.error(f"Failed to send welcome email: {e}")
            
            return user.to_dict(include_sensitive=False), 201
            
        except Exception as e:
            current_app.logger.error(f"Error creating user: {e}")
            raise BusinessLogicError("Error al crear usuario")


class UserDetailResource(Resource):
    """Endpoint para operaciones con usuario específico"""
    
    @api_auth_required
    def get(self, user_id):
        """
        Obtener detalles de un usuario específico
        
        Args:
            user_id: ID del usuario
        
        Returns:
            Información detallada del usuario
        """
        current_user = get_current_user()
        user = User.query.get_or_404(user_id)
        
        # Verificar permisos
        if not self._can_view_user(current_user, user):
            raise AuthorizationError("No tiene permisos para ver este usuario")
        
        # Obtener información completa del usuario
        user_data = user.to_dict(include_sensitive=current_user.is_admin())
        
        # Agregar información específica del perfil
        profile_data = UserService.get_user_profile_data(user)
        if profile_data:
            user_data['profile'] = profile_data
        
        # Agregar estadísticas si es admin o el propio usuario
        if current_user.is_admin() or current_user.id == user.id:
            user_data['statistics'] = UserService.get_user_statistics(user)
        
        return user_data
    
    @api_auth_required
    @validate_json
    @log_activity(ActivityType.USER_UPDATE, "User profile update")
    def put(self, user_id):
        """
        Actualizar usuario completo
        
        Args:
            user_id: ID del usuario
        
        Body:
            Campos del usuario a actualizar
        
        Returns:
            Usuario actualizado
        """
        current_user = get_current_user()
        user = User.query.get_or_404(user_id)
        
        # Verificar permisos
        if not self._can_edit_user(current_user, user):
            raise AuthorizationError("No tiene permisos para editar este usuario")
        
        data = request.get_json()
        
        try:
            # Actualizar usando el servicio
            updated_user = UserService.update_user(
                user=user,
                update_data=data,
                updated_by=current_user.id
            )
            
            return updated_user.to_dict(include_sensitive=False)
            
        except Exception as e:
            current_app.logger.error(f"Error updating user: {e}")
            raise BusinessLogicError("Error al actualizar usuario")
    
    @api_auth_required
    @validate_json
    def patch(self, user_id):
        """
        Actualización parcial de usuario
        
        Args:
            user_id: ID del usuario
        
        Body:
            Campos específicos a actualizar
        
        Returns:
            Usuario actualizado
        """
        return self.put(user_id)  # Reutilizar lógica de PUT
    
    @api_auth_required
    @admin_required
    @log_activity(ActivityType.USER_DELETE, "User deletion")
    def delete(self, user_id):
        """
        Eliminar usuario (solo admin)
        
        Args:
            user_id: ID del usuario
        
        Returns:
            Confirmación de eliminación
        """
        user = User.query.get_or_404(user_id)
        current_user = get_current_user()
        
        # No permitir auto-eliminación
        if user.id == current_user.id:
            raise BusinessLogicError("No puede eliminar su propia cuenta")
        
        try:
            # Eliminación lógica usando el servicio
            UserService.delete_user(user, deleted_by=current_user.id)
            
            return {'message': 'Usuario eliminado exitosamente'}, 200
            
        except Exception as e:
            current_app.logger.error(f"Error deleting user: {e}")
            raise BusinessLogicError("Error al eliminar usuario")
    
    def _can_view_user(self, current_user: User, target_user: User) -> bool:
        """Verifica si el usuario actual puede ver el usuario objetivo"""
        # Admin puede ver todo
        if current_user.is_admin():
            return True
        
        # Puede ver su propio perfil
        if current_user.id == target_user.id:
            return True
        
        # Puede ver perfiles públicos
        if target_user.is_public_profile:
            return True
        
        # Puede ver usuarios de la misma organización
        if (hasattr(current_user, 'organization_id') and 
            hasattr(target_user, 'organization_id') and
            current_user.organization_id == target_user.organization_id):
            return True
        
        return False
    
    def _can_edit_user(self, current_user: User, target_user: User) -> bool:
        """Verifica si el usuario actual puede editar el usuario objetivo"""
        # Admin puede editar todo
        if current_user.is_admin():
            return True
        
        # Puede editar su propio perfil
        if current_user.id == target_user.id:
            return True
        
        return False


class UserProfilePhotoResource(Resource):
    """Endpoint para gestión de foto de perfil"""
    
    @api_auth_required
    def post(self, user_id):
        """
        Subir foto de perfil
        
        Args:
            user_id: ID del usuario
        
        Form Data:
            photo: Archivo de imagen
        
        Returns:
            URL de la foto subida
        """
        current_user = get_current_user()
        user = User.query.get_or_404(user_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == user.id):
            raise AuthorizationError("No tiene permisos para cambiar esta foto")
        
        if 'photo' not in request.files:
            raise ValidationError("No se proporcionó archivo de foto")
        
        file = request.files['photo']
        if file.filename == '':
            raise ValidationError("No se seleccionó archivo")
        
        # Validar archivo
        if not self._allowed_file(file.filename):
            raise ValidationError("Tipo de archivo no permitido")
        
        try:
            # Subir archivo usando el servicio de almacenamiento
            file_url = FileStorageService.upload_profile_photo(
                file=file,
                user_id=user.id
            )
            
            # Actualizar URL en el usuario
            user.profile_photo_url = file_url
            db.session.commit()
            
            # Log de actividad
            ActivityLog.log_activity(
                activity_type=ActivityType.PROFILE_PHOTO_UPDATE,
                description=f"Profile photo updated for user {user.email}",
                user_id=user.id,
                metadata={'file_url': file_url},
                ip_address=request.remote_addr,
                user_agent=request.headers.get('User-Agent')
            )
            
            return {
                'message': 'Foto de perfil actualizada',
                'photo_url': file_url
            }
            
        except Exception as e:
            current_app.logger.error(f"Error uploading profile photo: {e}")
            raise BusinessLogicError("Error al subir foto de perfil")
    
    @api_auth_required
    def delete(self, user_id):
        """
        Eliminar foto de perfil
        
        Args:
            user_id: ID del usuario
        
        Returns:
            Confirmación de eliminación
        """
        current_user = get_current_user()
        user = User.query.get_or_404(user_id)
        
        # Verificar permisos
        if not (current_user.is_admin() or current_user.id == user.id):
            raise AuthorizationError("No tiene permisos para eliminar esta foto")
        
        if not user.profile_photo_url:
            raise ValidationError("El usuario no tiene foto de perfil")
        
        try:
            # Eliminar archivo del almacenamiento
            FileStorageService.delete_profile_photo(user.id)
            
            # Actualizar usuario
            user.profile_photo_url = None
            db.session.commit()
            
            return {'message': 'Foto de perfil eliminada'}
            
        except Exception as e:
            current_app.logger.error(f"Error deleting profile photo: {e}")
            raise BusinessLogicError("Error al eliminar foto de perfil")
    
    def _allowed_file(self, filename: str) -> bool:
        """Verifica si el tipo de archivo está permitido"""
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in allowed_extensions


class UserSearchResource(Resource):
    """Endpoint para búsqueda avanzada de usuarios"""
    
    @api_auth_required
    def post(self):
        """
        Búsqueda avanzada de usuarios
        
        Body:
            query: Término de búsqueda
            filters: Filtros específicos
            sort: Opciones de ordenamiento
            limit: Límite de resultados
        
        Returns:
            Resultados de búsqueda
        """
        current_user = get_current_user()
        data = request.get_json() or {}
        
        query_term = data.get('query', '').strip()
        filters = data.get('filters', {})
        sort_options = data.get('sort', {})
        limit = min(data.get('limit', 50), 1000)  # Límite máximo de 1000
        
        try:
            results = UserService.advanced_search(
                query=query_term,
                filters=filters,
                sort_options=sort_options,
                limit=limit,
                current_user=current_user
            )
            
            return {
                'results': [user.to_dict(include_sensitive=False) for user in results],
                'total': len(results),
                'query': query_term,
                'filters_applied': filters
            }
            
        except Exception as e:
            current_app.logger.error(f"Error in user search: {e}")
            raise BusinessLogicError("Error en búsqueda de usuarios")


class UserBulkOperationsResource(Resource):
    """Endpoint para operaciones en lote"""
    
    @api_auth_required
    @admin_required
    @validate_json
    @log_activity(ActivityType.USER_UPDATE, "Bulk user operations")
    def post(self):
        """
        Operaciones en lote sobre usuarios
        
        Body:
            operation: Tipo de operación (activate, deactivate, delete, update)
            user_ids: Lista de IDs de usuarios
            data: Datos adicionales según la operación
        
        Returns:
            Resultado de las operaciones
        """
        data = request.get_json()
        
        operation = data.get('operation')
        user_ids = data.get('user_ids', [])
        operation_data = data.get('data', {})
        
        if not operation or not user_ids:
            raise ValidationError("Operation y user_ids son requeridos")
        
        # Validar límite de operaciones en lote
        APIv1Validator.validate_bulk_operation(user_ids)
        
        valid_operations = ['activate', 'deactivate', 'delete', 'update']
        if operation not in valid_operations:
            raise ValidationError(f"Operación no válida. Válidas: {', '.join(valid_operations)}")
        
        try:
            result = UserService.bulk_operation(
                operation=operation,
                user_ids=user_ids,
                operation_data=operation_data,
                performed_by=get_current_user().id
            )
            
            return {
                'operation': operation,
                'total_requested': len(user_ids),
                'successful': result['successful'],
                'failed': result['failed'],
                'errors': result['errors']
            }
            
        except Exception as e:
            current_app.logger.error(f"Error in bulk operation: {e}")
            raise BusinessLogicError("Error en operación en lote")


class UserStatisticsResource(Resource):
    """Endpoint para estadísticas de usuarios"""
    
    @api_auth_required
    def get(self):
        """
        Obtener estadísticas generales de usuarios
        
        Query Parameters:
            organization_id: Filtrar por organización
            user_type: Filtrar por tipo de usuario
            period: Período de análisis (7d, 30d, 90d, 1y)
        
        Returns:
            Estadísticas de usuarios
        """
        current_user = get_current_user()
        
        # Solo admin puede ver estadísticas globales
        if not current_user.is_admin():
            raise AuthorizationError("No tiene permisos para ver estadísticas")
        
        organization_id = request.args.get('organization_id', type=int)
        user_type = request.args.get('user_type')
        period = request.args.get('period', '30d')
        
        try:
            stats = UserService.get_user_statistics_summary(
                organization_id=organization_id,
                user_type=user_type,
                period=period
            )
            
            return stats
            
        except Exception as e:
            current_app.logger.error(f"Error getting user statistics: {e}")
            raise BusinessLogicError("Error al obtener estadísticas")


class UserExportResource(Resource):
    """Endpoint para exportar datos de usuarios"""
    
    @api_auth_required
    @admin_required
    def get(self):
        """
        Exportar usuarios a CSV o Excel
        
        Query Parameters:
            format: Formato de exportación (csv, xlsx)
            user_type: Filtrar por tipo de usuario
            organization_id: Filtrar por organización
            is_active: Filtrar por estado activo
            fields: Campos específicos a exportar
        
        Returns:
            Archivo de exportación
        """
        export_format = request.args.get('format', 'csv').lower()
        user_type = request.args.get('user_type')
        organization_id = request.args.get('organization_id', type=int)
        is_active = request.args.get('is_active', type=bool)
        fields = request.args.get('fields', '').split(',') if request.args.get('fields') else None
        
        if export_format not in ['csv', 'xlsx']:
            raise ValidationError("Formato no válido. Use 'csv' o 'xlsx'")
        
        try:
            # Construir query
            query = User.query
            
            if user_type:
                query = query.filter(User.user_type == user_type)
            if organization_id:
                query = query.filter(User.organization_id == organization_id)
            if is_active is not None:
                query = query.filter(User.is_active == is_active)
            
            # Límite máximo para exportación
            users = query.limit(10000).all()
            
            if export_format == 'csv':
                return self._export_csv(users, fields)
            else:
                return self._export_xlsx(users, fields)
                
        except Exception as e:
            current_app.logger.error(f"Error exporting users: {e}")
            raise BusinessLogicError("Error al exportar usuarios")
    
    def _export_csv(self, users: list[User], fields: Optional[list[str]]) -> Any:
        """Exporta usuarios a CSV"""
        output = io.StringIO()
        
        # Definir campos por defecto
        default_fields = ['id', 'email', 'first_name', 'last_name', 'user_type', 
                         'is_active', 'created_at', 'last_login']
        export_fields = fields if fields else default_fields
        
        writer = csv.DictWriter(output, fieldnames=export_fields)
        writer.writeheader()
        
        for user in users:
            user_dict = user.to_dict(include_sensitive=False)
            row = {field: user_dict.get(field, '') for field in export_fields}
            writer.writerow(row)
        
        output.seek(0)
        
        # Crear respuesta de archivo
        return send_file(
            io.BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'users_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )
    
    def _export_xlsx(self, users: list[User], fields: Optional[list[str]]) -> Any:
        """Exporta usuarios a Excel"""
        output = io.BytesIO()
        
        # Crear workbook
        workbook = xlsxwriter.Workbook(output)
        worksheet = workbook.add_worksheet('Users')
        
        # Definir campos
        default_fields = ['id', 'email', 'first_name', 'last_name', 'user_type', 
                         'is_active', 'created_at', 'last_login']
        export_fields = fields if fields else default_fields
        
        # Escribir headers
        for col, field in enumerate(export_fields):
            worksheet.write(0, col, field.replace('_', ' ').title())
        
        # Escribir datos
        for row, user in enumerate(users, 1):
            user_dict = user.to_dict(include_sensitive=False)
            for col, field in enumerate(export_fields):
                value = user_dict.get(field, '')
                worksheet.write(row, col, str(value) if value else '')
        
        workbook.close()
        output.seek(0)
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=f'users_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.xlsx'
        )


class UserImportResource(Resource):
    """Endpoint para importar usuarios"""
    
    @api_auth_required
    @admin_required
    @limiter.limit("2 per hour")
    def post(self):
        """
        Importar usuarios desde archivo CSV/Excel
        
        Form Data:
            file: Archivo CSV o Excel
            update_existing: Si actualizar usuarios existentes
            send_welcome_emails: Si enviar emails de bienvenida
        
        Returns:
            Resultado de la importación
        """
        if 'file' not in request.files:
            raise ValidationError("No se proporcionó archivo")
        
        file = request.files['file']
        if file.filename == '':
            raise ValidationError("No se seleccionó archivo")
        
        update_existing = request.form.get('update_existing', 'false').lower() == 'true'
        send_welcome_emails = request.form.get('send_welcome_emails', 'false').lower() == 'true'
        
        # Validar tipo de archivo
        allowed_extensions = {'csv', 'xlsx', 'xls'}
        file_ext = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            raise ValidationError("Tipo de archivo no permitido. Use CSV o Excel")
        
        try:
            result = UserService.import_users_from_file(
                file=file,
                update_existing=update_existing,
                send_welcome_emails=send_welcome_emails,
                imported_by=get_current_user().id
            )
            
            return {
                'message': 'Importación completada',
                'total_processed': result['total_processed'],
                'successful': result['successful'],
                'failed': result['failed'],
                'errors': result['errors'][:10]  # Limitar errores mostrados
            }
            
        except Exception as e:
            current_app.logger.error(f"Error importing users: {e}")
            raise BusinessLogicError("Error al importar usuarios")


# Registrar recursos en la API
api.add_resource(UsersListResource, '')
api.add_resource(UserDetailResource, '/<int:user_id>')
api.add_resource(UserProfilePhotoResource, '/<int:user_id>/photo')
api.add_resource(UserSearchResource, '/search')
api.add_resource(UserBulkOperationsResource, '/bulk')
api.add_resource(UserStatisticsResource, '/statistics')
api.add_resource(UserExportResource, '/export')
api.add_resource(UserImportResource, '/import')


# Endpoints adicionales específicos por tipo de usuario
@users_bp.route('/<int:user_id>/activate', methods=['POST'])
@api_auth_required
@admin_required
def activate_user(user_id):
    """Activar usuario específico"""
    user = User.query.get_or_404(user_id)
    
    if user.is_active:
        return jsonify({'message': 'Usuario ya está activo'}), 200
    
    user.is_active = True
    user.activated_at = datetime.now(timezone.utc)
    user.activated_by = get_current_user().id
    db.session.commit()
    
    # Log activación
    ActivityLog.log_activity(
        activity_type=ActivityType.USER_ACTIVATE,
        description=f"User activated: {user.email}",
        user_id=user.id,
        severity=ActivitySeverity.MEDIUM,
        metadata={'activated_by': get_current_user().id},
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    
    return jsonify({
        'message': 'Usuario activado exitosamente',
        'user': user.to_dict(include_sensitive=False)
    })


@users_bp.route('/<int:user_id>/deactivate', methods=['POST'])
@api_auth_required
@admin_required
def deactivate_user(user_id):
    """Desactivar usuario específico"""
    current_user = get_current_user()
    user = User.query.get_or_404(user_id)
    
    # No permitir auto-desactivación
    if user.id == current_user.id:
        raise BusinessLogicError("No puede desactivar su propia cuenta")
    
    if not user.is_active:
        return jsonify({'message': 'Usuario ya está inactivo'}), 200
    
    data = request.get_json() or {}
    reason = data.get('reason', '')
    
    user.is_active = False
    user.deactivated_at = datetime.now(timezone.utc)
    user.deactivated_by = current_user.id
    user.deactivation_reason = reason
    db.session.commit()
    
    # Log desactivación
    ActivityLog.log_activity(
        activity_type=ActivityType.USER_DEACTIVATE,
        description=f"User deactivated: {user.email}",
        user_id=user.id,
        severity=ActivitySeverity.HIGH,
        metadata={
            'deactivated_by': current_user.id,
            'reason': reason
        },
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    
    return jsonify({
        'message': 'Usuario desactivado exitosamente',
        'user': user.to_dict(include_sensitive=False)
    })


@users_bp.route('/<int:user_id>/reset-password', methods=['POST'])
@api_auth_required
@admin_required
def admin_reset_password(user_id):
    """Reset de contraseña por admin"""
    user = User.query.get_or_404(user_id)
    data = request.get_json() or {}
    
    # Generar nueva contraseña temporal
    import secrets
    import string
    
    new_password = ''.join(secrets.choice(
        string.ascii_letters + string.digits + '!@#$%^&*'
    ) for _ in range(12))
    
    user.set_password(new_password)
    user.must_change_password = True  # Forzar cambio en próximo login
    db.session.commit()
    
    # Enviar nueva contraseña por email
    send_email = data.get('send_email', True)
    if send_email:
        try:
            EmailService.send_password_reset_admin(user, new_password)
        except Exception as e:
            current_app.logger.error(f"Failed to send password reset email: {e}")
    
    # Log reset de contraseña
    ActivityLog.log_activity(
        activity_type=ActivityType.PASSWORD_RESET,
        description=f"Admin password reset for {user.email}",
        user_id=user.id,
        severity=ActivitySeverity.HIGH,
        metadata={
            'reset_by': get_current_user().id,
            'email_sent': send_email
        },
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    
    return jsonify({
        'message': 'Contraseña reseteada exitosamente',
        'password_sent_by_email': send_email,
        'temporary_password': new_password if not send_email else None
    })


@users_bp.route('/<int:user_id>/impersonate', methods=['POST'])
@api_auth_required
@admin_required
@limiter.limit("10 per hour")
def impersonate_user(user_id):
    """Impersonar usuario (solo admin)"""
    current_user = get_current_user()
    target_user = User.query.get_or_404(user_id)
    
    # No permitir impersonar otros admins
    if target_user.is_admin() and target_user.id != current_user.id:
        raise AuthorizationError("No puede impersonar otros administradores")
    
    # Generar token de impersonación
    from app.api.v1.auth import generate_api_token
    
    impersonation_token = generate_api_token(
        user=target_user,
        permissions=['impersonation']
    )
    
    # Log impersonación
    ActivityLog.log_activity(
        activity_type=ActivityType.ADMIN_USER_IMPERSONATE,
        description=f"Admin impersonation: {current_user.email} -> {target_user.email}",
        user_id=target_user.id,
        severity=ActivitySeverity.CRITICAL,
        metadata={
            'impersonated_by': current_user.id,
            'impersonated_user': target_user.id
        },
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    
    return jsonify({
        'message': 'Impersonación iniciada',
        'impersonation_token': impersonation_token,
        'target_user': target_user.to_dict(include_sensitive=False),
        'expires_in': 3600  # 1 hora
    })


@users_bp.route('/<int:user_id>/activity', methods=['GET'])
@api_auth_required
def get_user_activity(user_id):
    """Obtener actividad reciente del usuario"""
    current_user = get_current_user()
    target_user = User.query.get_or_404(user_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == target_user.id):
        raise AuthorizationError("No tiene permisos para ver esta actividad")
    
    # Parámetros de consulta
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    activity_type = request.args.get('activity_type')
    days = request.args.get('days', 30, type=int)
    
    # Construir query de actividades
    query = ActivityLog.query.filter(ActivityLog.user_id == user_id)
    
    # Filtro por tipo de actividad
    if activity_type:
        try:
            activity_enum = ActivityType(activity_type)
            query = query.filter(ActivityLog.activity_type == activity_enum)
        except ValueError:
            raise ValidationError("Tipo de actividad inválido")
    
    # Filtro por período
    if days > 0:
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=days)
        query = query.filter(ActivityLog.created_at >= cutoff_date)
    
    # Ordenar por fecha descendente
    query = query.order_by(ActivityLog.created_at.desc())
    
    # Paginación
    activities = query.paginate(
        page=page,
        per_page=per_page,
        error_out=False
    )
    
    return jsonify({
        'activities': [activity.to_dict() for activity in activities.items],
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': activities.total,
            'pages': activities.pages,
            'has_next': activities.has_next,
            'has_prev': activities.has_prev
        }
    })


@users_bp.route('/<int:user_id>/relationships', methods=['GET'])
@api_auth_required
def get_user_relationships(user_id):
    """Obtener relaciones del usuario"""
    current_user = get_current_user()
    target_user = User.query.get_or_404(user_id)
    
    # Verificar permisos
    if not (current_user.is_admin() or current_user.id == target_user.id):
        raise AuthorizationError("No tiene permisos para ver estas relaciones")
    
    try:
        from app.models.relationship import RelationshipManager
        
        # Obtener relaciones del usuario
        relationships = RelationshipManager.get_relationships_for_entity(
            entity_type='user',
            entity_id=user_id,
            status_filter=None  # Todas las relaciones
        )
        
        # Agrupar por tipo de relación
        relationships_by_type = {}
        for rel in relationships:
            rel_type = rel.relationship_type.value
            if rel_type not in relationships_by_type:
                relationships_by_type[rel_type] = []
            
            relationships_by_type[rel_type].append(
                rel.to_dict(include_entities=True)
            )
        
        return jsonify({
            'user_id': user_id,
            'total_relationships': len(relationships),
            'relationships_by_type': relationships_by_type,
            'summary': {
                rel_type: len(rels) 
                for rel_type, rels in relationships_by_type.items()
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Error getting user relationships: {e}")
        raise BusinessLogicError("Error al obtener relaciones del usuario")


@users_bp.route('/<int:user_id>/permissions', methods=['GET'])
@api_auth_required
@admin_required
def get_user_permissions(user_id):
    """Obtener permisos del usuario"""
    user = User.query.get_or_404(user_id)
    
    permissions = user.get_permissions()
    role_permissions = user.get_role_permissions() if hasattr(user, 'get_role_permissions') else []
    
    return jsonify({
        'user_id': user_id,
        'user_type': user.user_type,
        'permissions': permissions,
        'role_permissions': role_permissions,
        'is_admin': user.is_admin(),
        'effective_permissions': list(set(permissions + role_permissions))
    })


@users_bp.route('/<int:user_id>/permissions', methods=['PUT'])
@api_auth_required
@admin_required
@validate_json
def update_user_permissions(user_id):
    """Actualizar permisos del usuario"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    new_permissions = data.get('permissions', [])
    
    # Validar permisos
    valid_permissions = [
        'read_users', 'write_users', 'delete_users',
        'read_projects', 'write_projects', 'delete_projects',
        'read_organizations', 'write_organizations',
        'manage_system', 'access_analytics',
        'impersonate_users', 'manage_permissions'
    ]
    
    for permission in new_permissions:
        if permission not in valid_permissions:
            raise ValidationError(f"Permiso inválido: {permission}")
    
    # Actualizar permisos según tipo de usuario
    if user.user_type == 'admin':
        admin_profile = Admin.query.filter_by(user_id=user.id).first()
        if admin_profile:
            admin_profile.permissions = new_permissions
    else:
        # Para otros tipos de usuario, crear tabla de permisos personalizada
        # (implementar según necesidades específicas)
        pass
    
    db.session.commit()
    
    # Log cambio de permisos
    ActivityLog.log_activity(
        activity_type=ActivityType.USER_UPDATE,
        description=f"Permissions updated for {user.email}",
        user_id=user.id,
        severity=ActivitySeverity.HIGH,
        metadata={
            'updated_by': get_current_user().id,
            'new_permissions': new_permissions
        },
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent')
    )
    
    return jsonify({
        'message': 'Permisos actualizados exitosamente',
        'permissions': user.get_permissions()
    })


@users_bp.route('/types', methods=['GET'])
@api_auth_required
def get_user_types():
    """Obtener tipos de usuario disponibles"""
    user_types = [
        {
            'value': 'entrepreneur',
            'label': 'Emprendedor',
            'description': 'Usuario que desarrolla proyectos emprendedores'
        },
        {
            'value': 'ally',
            'label': 'Aliado/Mentor',
            'description': 'Usuario que proporciona mentoría y apoyo'
        },
        {
            'value': 'client',
            'label': 'Cliente/Stakeholder',
            'description': 'Usuario interesado en seguir emprendimientos'
        },
        {
            'value': 'admin',
            'label': 'Administrador',
            'description': 'Usuario con permisos administrativos'
        }
    ]
    
    return jsonify({
        'user_types': user_types,
        'default_type': 'entrepreneur'
    })


@users_bp.route('/validate-email', methods=['POST'])
@api_auth_required
@validate_json
def validate_email_availability():
    """Validar disponibilidad de email"""
    data = request.get_json()
    email = data.get('email', '').strip().lower()
    exclude_user_id = data.get('exclude_user_id')  # Para edición de perfil
    
    if not email:
        raise ValidationError("Email es requerido")
    
    # Validar formato
    try:
        from email_validator import validate_email as validate_email_format
        validate_email_format(email)
    except:
        raise ValidationError("Formato de email inválido")
    
    # Verificar disponibilidad
    query = User.query.filter(User.email == email)
    if exclude_user_id:
        query = query.filter(User.id != exclude_user_id)
    
    existing_user = query.first()
    is_available = existing_user is None
    
    return jsonify({
        'email': email,
        'is_available': is_available,
        'message': 'Email disponible' if is_available else 'Email ya está en uso'
    })


@users_bp.route('/dashboard-stats', methods=['GET'])
@api_auth_required
@admin_required
def get_dashboard_stats():
    """Obtener estadísticas para dashboard de admin"""
    # Estadísticas básicas
    total_users = User.query.count()
    active_users = User.query.filter(User.is_active == True).count()
    
    # Usuarios por tipo
    user_types = db.session.query(
        User.user_type,
        func.count(User.id).label('count')
    ).group_by(User.user_type).all()
    
    # Usuarios registrados en los últimos 30 días
    thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
    new_users_30d = User.query.filter(
        User.created_at >= thirty_days_ago
    ).count()
    
    # Usuarios activos en los últimos 7 días
    seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
    active_users_7d = User.query.filter(
        User.last_login >= seven_days_ago
    ).count()
    
    # Top organizaciones por número de usuarios
    top_organizations = db.session.query(
        Organization.name,
        func.count(User.id).label('user_count')
    ).join(User, User.organization_id == Organization.id)\
     .group_by(Organization.id, Organization.name)\
     .order_by(func.count(User.id).desc())\
     .limit(5).all()
    
    return jsonify({
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': total_users - active_users,
        'new_users_30d': new_users_30d,
        'active_users_7d': active_users_7d,
        'user_types': {
            user_type: count for user_type, count in user_types
        },
        'top_organizations': [
            {'name': name, 'user_count': count} 
            for name, count in top_organizations
        ],
        'growth_rate_30d': round((new_users_30d / max(total_users - new_users_30d, 1)) * 100, 2),
        'activity_rate_7d': round((active_users_7d / max(total_users, 1)) * 100, 2)
    })


# Manejadores de errores específicos del módulo users
@users_bp.errorhandler(ResourceNotFoundError)
def handle_user_not_found(error):
    """Maneja errores de usuario no encontrado"""
    return jsonify({
        'error': 'User Not Found',
        'message': str(error),
        'code': 'USER_NOT_FOUND',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 404


@users_bp.errorhandler(BusinessLogicError)
def handle_user_business_error(error):
    """Maneja errores de lógica de negocio específicos de usuarios"""
    return jsonify({
        'error': 'User Business Logic Error',
        'message': str(error),
        'code': 'USER_BUSINESS_ERROR',
        'timestamp': datetime.now(timezone.utc).isoformat()
    }), 422


# Funciones auxiliares para otros módulos
def get_user_summary(user_id: int) -> Optional[dict[str, Any]]:
    """
    Obtiene resumen básico de un usuario
    
    Args:
        user_id: ID del usuario
        
    Returns:
        Resumen del usuario o None si no existe
    """
    user = User.query.get(user_id)
    if not user:
        return None
    
    return {
        'id': user.id,
        'email': user.email,
        'full_name': user.full_name,
        'user_type': user.user_type,
        'is_active': user.is_active,
        'profile_photo_url': user.profile_photo_url
    }


def check_user_permissions(user_id: int, required_permissions: list[str]) -> bool:
    """
    Verifica si un usuario tiene los permisos requeridos
    
    Args:
        user_id: ID del usuario
        required_permissions: Lista de permisos requeridos
        
    Returns:
        True si tiene todos los permisos
    """
    user = User.query.get(user_id)
    if not user or not user.is_active:
        return False
    
    user_permissions = user.get_permissions()
    return all(permission in user_permissions for permission in required_permissions)


# Exportaciones para otros módulos
__all__ = [
    'users_bp',
    'get_user_summary',
    'check_user_permissions'
]