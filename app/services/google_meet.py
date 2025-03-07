"""
Servicio para integración con Google Meet.
Permite la creación y gestión de videoconferencias mediante Google Meet.
"""
import os
import datetime
import json
from flask import current_app, url_for, redirect, request, session
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from uuid import uuid4
from ..extensions import db
from ..models.user import User
from ..models.meeting import Meeting

class GoogleMeetService:
    """Clase para manejar la integración con Google Meet."""
    
    # Alcances requeridos para la API de Google Meet
    SCOPES = [
        'https://www.googleapis.com/auth/calendar',
        'https://www.googleapis.com/auth/calendar.events'
    ]
    CALENDAR_API_SERVICE_NAME = 'calendar'
    CALENDAR_API_VERSION = 'v3'
    
    def __init__(self, app=None):
        """Inicializa el servicio de Google Meet."""
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Configura el servicio con la aplicación Flask."""
        self.app = app
        
        # Registrar las rutas de callback para la autorización
        app.add_url_rule('/services/google-meet/authorize', 
                         'google_meet_authorize', 
                         self.authorize)
        app.add_url_rule('/services/google-meet/callback', 
                         'google_meet_callback', 
                         self.callback)
    
    def get_auth_url(self, user_id, next_url=None):
        """
        Genera la URL para autorizar acceso a Google Meet.
        
        Args:
            user_id: ID del usuario que autoriza el acceso
            next_url: URL a redireccionar después de la autorización
            
        Returns:
            str: URL para iniciar flujo de autorización
        """
        if next_url:
            session['gmeet_next_url'] = next_url
        
        session['gmeet_user_id'] = user_id
        
        # Crear flujo de OAuth para Google Meet
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            current_app.config['GOOGLE_CLIENT_SECRETS_FILE'],
            scopes=self.SCOPES
        )
        
        flow.redirect_uri = url_for('google_meet_callback', _external=True)
        
        # Generar URL de autorización
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        # Guardar el estado para verificar la respuesta
        session['gmeet_state'] = state
        
        return authorization_url
    
    def authorize(self):
        """
        Inicia el flujo de autorización para Google Meet.
        
        Returns:
            Response: Redirección a Google para autorización
        """
        if 'user_id' not in request.args:
            return redirect(url_for('main.index'))
        
        user_id = request.args.get('user_id')
        next_url = request.args.get('next', url_for('main.index'))
        
        auth_url = self.get_auth_url(user_id, next_url)
        return redirect(auth_url)
    
    def callback(self):
        """
        Maneja el callback de autorización de Google Meet.
        
        Returns:
            Response: Redirección a la URL adecuada tras autorización
        """
        # Verificar que no haya errores
        if 'error' in request.args:
            error = request.args.get('error')
            return redirect(url_for('main.index', error=f"gmeet_auth_error:{error}"))
        
        # Verificar que tengamos el código y el estado
        if 'code' not in request.args or 'state' not in request.args:
            return redirect(url_for('main.index'))
        
        # Verificar que el estado coincide (previene ataques CSRF)
        if session.get('gmeet_state') != request.args.get('state'):
            return redirect(url_for('main.index', error="gmeet_state_mismatch"))
        
        # Obtener el ID del usuario
        user_id = session.get('gmeet_user_id')
        if not user_id:
            return redirect(url_for('main.index', error="gmeet_missing_user"))
        
        # Crear flujo de OAuth y obtener credenciales
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            current_app.config['GOOGLE_CLIENT_SECRETS_FILE'],
            scopes=self.SCOPES,
            state=session.get('gmeet_state')
        )
        flow.redirect_uri = url_for('google_meet_callback', _external=True)
        
        # Intercambiar el código de autorización por tokens
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        # Guardar credenciales en la base de datos
        self._save_credentials(user_id, credentials)
        
        # Redireccionar a la página adecuada
        next_url = session.pop('gmeet_next_url', url_for('main.index'))
        return redirect(next_url)
    
    def _save_credentials(self, user_id, credentials):
        """
        Guarda las credenciales en la base de datos.
        
        Args:
            user_id: ID del usuario
            credentials: Credenciales de Google
        """
        user = User.query.get(user_id)
        if not user:
            current_app.logger.error(f"Usuario no encontrado: {user_id}")
            return
        
        # Convertir credenciales a JSON
        creds_data = {
            'token': credentials.token,
            'refresh_token': credentials.refresh_token,
            'token_uri': credentials.token_uri,
            'client_id': credentials.client_id,
            'client_secret': credentials.client_secret,
            'scopes': credentials.scopes,
            'expiry': credentials.expiry.isoformat() if credentials.expiry else None
        }
        
        # Guardar en la base de datos
        user.google_meet_credentials = json.dumps(creds_data)
        user.has_google_meet_access = True
        db.session.commit()
    
    def _get_credentials(self, user_id):
        """
        Obtiene las credenciales de Google Meet para un usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Credentials: Objeto de credenciales de Google o None
        """
        user = User.query.get(user_id)
        if not user or not user.google_meet_credentials:
            return None
        
        try:
            creds_data = json.loads(user.google_meet_credentials)
            
            # Convertir fecha de expiración de string a datetime
            if creds_data.get('expiry'):
                creds_data['expiry'] = datetime.datetime.fromisoformat(creds_data['expiry'])
            
            # Crear objeto de credenciales
            credentials = google.oauth2.credentials.Credentials(
                token=creds_data.get('token'),
                refresh_token=creds_data.get('refresh_token'),
                token_uri=creds_data.get('token_uri'),
                client_id=creds_data.get('client_id'),
                client_secret=creds_data.get('client_secret'),
                scopes=creds_data.get('scopes')
            )
            
            # Actualizar expiración
            credentials.expiry = creds_data.get('expiry')
            
            return credentials
        except Exception as e:
            current_app.logger.error(f"Error al obtener credenciales: {str(e)}")
            return None
    
    def _get_calendar_service(self, user_id):
        """
        Obtiene un servicio autorizado de Google Calendar.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Resource: Servicio de Google Calendar o None
        """
        credentials = self._get_credentials(user_id)
        if not credentials:
            return None
        
        try:
            # Crear servicio con las credenciales
            service = googleapiclient.discovery.build(
                self.CALENDAR_API_SERVICE_NAME,
                self.CALENDAR_API_VERSION,
                credentials=credentials
            )
            return service
        except Exception as e:
            current_app.logger.error(f"Error al crear servicio de calendario: {str(e)}")
            return None
    
    def create_meeting(self, user_id, meeting_data):
        """
        Crea una videoconferencia de Google Meet.
        
        Args:
            user_id: ID del usuario que crea la reunión
            meeting_data: Diccionario con datos de la reunión (título, descripción, fecha_inicio, fecha_fin, participantes)
            
        Returns:
            dict: Información de la reunión creada o None
        """
        service = self._get_calendar_service(user_id)
        if not service:
            return None
        
        # Obtener datos de la reunión
        title = meeting_data.get('title', 'Nueva reunión')
        description = meeting_data.get('description', '')
        start_time = meeting_data.get('start_time')
        end_time = meeting_data.get('end_time')
        attendees = meeting_data.get('attendees', [])
        
        # Verificar datos obligatorios
        if not start_time or not end_time:
            current_app.logger.error("Faltan datos obligatorios para crear reunión")
            return None
        
        # Preparar la lista de asistentes
        attendee_list = [{'email': email} for email in attendees]
        
        # Crear evento con videoconferencia
        event = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': start_time.isoformat(),
                'timeZone': 'America/Bogota',  # Ajustar según zona horaria
            },
            'end': {
                'dateTime': end_time.isoformat(),
                'timeZone': 'America/Bogota',  # Ajustar según zona horaria
            },
            'attendees': attendee_list,
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f"meet-{uuid4()}",
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            }
        }
        
        try:
            # Crear el evento en Google Calendar con videoconferencia
            event = service.events().insert(
                calendarId='primary',
                body=event,
                conferenceDataVersion=1,
                sendUpdates='all'
            ).execute()
            
            # Extraer información de la videoconferencia
            meet_info = None
            if 'conferenceData' in event:
                meet_info = {
                    'meeting_id': event['id'],
                    'meet_link': event.get('hangoutLink', ''),
                    'conference_id': event['conferenceData'].get('conferenceId', ''),
                    'entry_points': event['conferenceData'].get('entryPoints', [])
                }
            
            return {
                'event_id': event['id'],
                'event_link': event.get('htmlLink', ''),
                'meet_info': meet_info
            }
        except googleapiclient.errors.HttpError as e:
            current_app.logger.error(f"Error al crear videoconferencia: {str(e)}")
            return None
    
    def get_meeting_link(self, user_id, event_id):
        """
        Obtiene el enlace de Google Meet para un evento.
        
        Args:
            user_id: ID del usuario
            event_id: ID del evento de Google Calendar
            
        Returns:
            str: Enlace de Google Meet o None
        """
        service = self._get_calendar_service(user_id)
        if not service or not event_id:
            return None
        
        try:
            # Obtener el evento
            event = service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            # Extraer enlace de Meet
            if 'conferenceData' in event and 'hangoutLink' in event:
                return event['hangoutLink']
            
            return None
        except googleapiclient.errors.HttpError as e:
            current_app.logger.error(f"Error al obtener enlace de Meet: {str(e)}")
            return None
    
    def update_meeting(self, user_id, event_id, meeting_data):
        """
        Actualiza una videoconferencia existente.
        
        Args:
            user_id: ID del usuario
            event_id: ID del evento de Google Calendar
            meeting_data: Diccionario con datos actualizados
            
        Returns:
            dict: Información actualizada o None
        """
        service = self._get_calendar_service(user_id)
        if not service or not event_id:
            return None
        
        try:
            # Obtener el evento actual
            event = service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            # Actualizar datos si están presentes
            if 'title' in meeting_data:
                event['summary'] = meeting_data['title']
            
            if 'description' in meeting_data:
                event['description'] = meeting_data['description']
            
            if 'start_time' in meeting_data:
                event['start']['dateTime'] = meeting_data['start_time'].isoformat()
            
            if 'end_time' in meeting_data:
                event['end']['dateTime'] = meeting_data['end_time'].isoformat()
            
            if 'attendees' in meeting_data:
                attendee_list = [{'email': email} for email in meeting_data['attendees']]
                event['attendees'] = attendee_list
            
            # Actualizar el evento
            updated_event = service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=event,
                conferenceDataVersion=1,
                sendUpdates='all'
            ).execute()
            
            # Extraer información de la videoconferencia
            meet_info = None
            if 'conferenceData' in updated_event:
                meet_info = {
                    'meeting_id': updated_event['id'],
                    'meet_link': updated_event.get('hangoutLink', ''),
                    'conference_id': updated_event['conferenceData'].get('conferenceId', ''),
                    'entry_points': updated_event['conferenceData'].get('entryPoints', [])
                }
            
            return {
                'event_id': updated_event['id'],
                'event_link': updated_event.get('htmlLink', ''),
                'meet_info': meet_info
            }
        except googleapiclient.errors.HttpError as e:
            current_app.logger.error(f"Error al actualizar videoconferencia: {str(e)}")
            return None
    
    def delete_meeting(self, user_id, event_id):
        """
        Elimina una videoconferencia de Google Meet.
        
        Args:
            user_id: ID del usuario
            event_id: ID del evento de Google Calendar
            
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        service = self._get_calendar_service(user_id)
        if not service or not event_id:
            return False
        
        try:
            # Eliminar el evento de Google Calendar
            service.events().delete(
                calendarId='primary',
                eventId=event_id,
                sendUpdates='all'
            ).execute()
            
            return True
        except googleapiclient.errors.HttpError as e:
            current_app.logger.error(f"Error al eliminar videoconferencia: {str(e)}")
            return False
    
    def create_instant_meeting(self, user_id, title="Reunión instantánea", participants=None):
        """
        Crea una reunión instantánea de Google Meet.
        
        Args:
            user_id: ID del usuario que crea la reunión
            title: Título de la reunión
            participants: Lista de correos de participantes
            
        Returns:
            dict: Información de la reunión creada o None
        """
        # Definir horario (ahora + 1 hora)
        now = datetime.datetime.now()
        start_time = now
        end_time = now + datetime.timedelta(hours=1)
        
        # Preparar datos de la reunión
        meeting_data = {
            'title': title,
            'description': 'Reunión instantánea creada desde la plataforma',
            'start_time': start_time,
            'end_time': end_time,
            'attendees': participants or []
        }
        
        return self.create_meeting(user_id, meeting_data)
    
    def add_participant(self, user_id, event_id, email):
        """
        Añade un participante a una reunión existente.
        
        Args:
            user_id: ID del usuario
            event_id: ID del evento de Google Calendar
            email: Correo electrónico del nuevo participante
            
        Returns:
            bool: True si se añadió correctamente, False en caso contrario
        """
        service = self._get_calendar_service(user_id)
        if not service or not event_id:
            return False
        
        try:
            # Obtener el evento actual
            event = service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            # Añadir participante
            attendees = event.get('attendees', [])
            attendees.append({'email': email})
            event['attendees'] = attendees
            
            # Actualizar el evento
            service.events().update(
                calendarId='primary',
                eventId=event_id,
                body=event,
                sendUpdates='all'
            ).execute()
            
            return True
        except googleapiclient.errors.HttpError as e:
            current_app.logger.error(f"Error al añadir participante: {str(e)}")
            return False
    
    def get_meeting_details(self, user_id, event_id):
        """
        Obtiene detalles completos de una reunión.
        
        Args:
            user_id: ID del usuario
            event_id: ID del evento de Google Calendar
            
        Returns:
            dict: Detalles completos de la reunión o None
        """
        service = self._get_calendar_service(user_id)
        if not service or not event_id:
            return None
        
        try:
            # Obtener el evento
            event = service.events().get(
                calendarId='primary',
                eventId=event_id
            ).execute()
            
            # Extraer datos relevantes
            meeting_details = {
                'id': event['id'],
                'title': event.get('summary', ''),
                'description': event.get('description', ''),
                'start_time': event['start'].get('dateTime', event['start'].get('date')),
                'end_time': event['end'].get('dateTime', event['end'].get('date')),
                'attendees': [a.get('email') for a in event.get('attendees', [])],
                'meet_link': event.get('hangoutLink', ''),
                'created': event.get('created', ''),
                'updated': event.get('updated', ''),
                'status': event.get('status', '')
            }
            
            # Agregar datos de conferencia si existen
            if 'conferenceData' in event:
                meeting_details['conference'] = {
                    'type': event['conferenceData'].get('conferenceSolution', {}).get('name', 'Google Meet'),
                    'conference_id': event['conferenceData'].get('conferenceId', ''),
                    'entry_points': event['conferenceData'].get('entryPoints', [])
                }
            
            return meeting_details
        except googleapiclient.errors.HttpError as e:
            current_app.logger.error(f"Error al obtener detalles de reunión: {str(e)}")
            return None
    
    def sync_meeting_with_db(self, meeting_id):
        """
        Sincroniza los datos de una reunión de la base de datos con Google Meet.
        
        Args:
            meeting_id: ID de la reunión en la base de datos
            
        Returns:
            bool: True si se sincronizó correctamente, False en caso contrario
        """
        # Obtener reunión de la base de datos
        meeting = Meeting.query.get(meeting_id)
        if not meeting:
            current_app.logger.error(f"Reunión no encontrada: {meeting_id}")
            return False
        
        # Verificar si ya tiene un evento de Google Calendar
        if meeting.calendar_event_id:
            # Actualizar evento existente
            meeting_data = {
                'title': meeting.title,
                'description': meeting.description,
                'start_time': meeting.start_time,
                'end_time': meeting.end_time,
                'attendees': [meeting.entrepreneur.email, meeting.ally.email]
            }
            
            result = self.update_meeting(
                meeting.created_by_id, 
                meeting.calendar_event_id, 
                meeting_data
            )
        else:
            # Crear nuevo evento
            meeting_data = {
                'title': meeting.title,
                'description': meeting.description,
                'start_time': meeting.start_time,
                'end_time': meeting.end_time,
                'attendees': [meeting.entrepreneur.email, meeting.ally.email]
            }
            
            result = self.create_meeting(meeting.created_by_id, meeting_data)
        
        if result:
            # Actualizar datos en la base de datos
            meeting.calendar_event_id = result.get('event_id')
            if result.get('meet_info'):
                meeting.meet_link = result['meet_info'].get('meet_link', '')
            
            db.session.commit()
            return True
        
        return False

# Crear una instancia del servicio
google_meet_service = GoogleMeetService()