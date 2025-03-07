"""
Servicio para integración con Google Calendar.
Permite la creación, actualización y gestión de eventos en Google Calendar.
"""
import os
import datetime
import json
from flask import current_app, url_for, redirect, session, request
import google.oauth2.credentials
import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
from ..extensions import db
from ..models.meeting import Meeting
from ..models.user import User

class GoogleCalendarService:
    """Clase para manejar la integración con Google Calendar."""
    
    # Alcances requeridos para la API de Google Calendar
    SCOPES = ['https://www.googleapis.com/auth/calendar']
    API_SERVICE_NAME = 'calendar'
    API_VERSION = 'v3'
    
    def __init__(self, app=None):
        """Inicializa el servicio de Google Calendar."""
        self.app = app
        if app is not None:
            self.init_app(app)
    
    def init_app(self, app):
        """Configura el servicio con la aplicación Flask."""
        self.app = app
        
        # Registrar las rutas de callback para la autorización
        app.add_url_rule('/services/google-calendar/authorize', 
                         'google_calendar_authorize', 
                         self.authorize)
        app.add_url_rule('/services/google-calendar/callback', 
                         'google_calendar_callback', 
                         self.callback)
    
    def get_auth_url(self, user_id, next_url=None):
        """
        Genera la URL para autorizar acceso a Google Calendar.
        
        Args:
            user_id: ID del usuario que autoriza el acceso
            next_url: URL a redireccionar después de la autorización
            
        Returns:
            str: URL para iniciar flujo de autorización
        """
        if next_url:
            session['gcal_next_url'] = next_url
        
        session['gcal_user_id'] = user_id
        
        # Crear flujo de OAuth para Google Calendar
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            current_app.config['GOOGLE_CLIENT_SECRETS_FILE'],
            scopes=self.SCOPES
        )
        
        flow.redirect_uri = url_for('google_calendar_callback', _external=True)
        
        # Generar URL de autorización
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent'
        )
        
        # Guardar el estado para verificar la respuesta
        session['gcal_state'] = state
        
        return authorization_url
    
    def authorize(self):
        """
        Inicia el flujo de autorización para Google Calendar.
        
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
        Maneja el callback de autorización de Google Calendar.
        
        Returns:
            Response: Redirección a la URL adecuada tras autorización
        """
        # Verificar que no haya errores
        if 'error' in request.args:
            error = request.args.get('error')
            return redirect(url_for('main.index', error=f"gcal_auth_error:{error}"))
        
        # Verificar que tengamos el código y el estado
        if 'code' not in request.args or 'state' not in request.args:
            return redirect(url_for('main.index'))
        
        # Verificar que el estado coincide (previene ataques CSRF)
        if session.get('gcal_state') != request.args.get('state'):
            return redirect(url_for('main.index', error="gcal_state_mismatch"))
        
        # Obtener el ID del usuario
        user_id = session.get('gcal_user_id')
        if not user_id:
            return redirect(url_for('main.index', error="gcal_missing_user"))
        
        # Crear flujo de OAuth y obtener credenciales
        flow = google_auth_oauthlib.flow.Flow.from_client_secrets_file(
            current_app.config['GOOGLE_CLIENT_SECRETS_FILE'],
            scopes=self.SCOPES,
            state=session.get('gcal_state')
        )
        flow.redirect_uri = url_for('google_calendar_callback', _external=True)
        
        # Intercambiar el código de autorización por tokens
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        
        # Guardar credenciales en la base de datos
        self._save_credentials(user_id, credentials)
        
        # Redireccionar a la página adecuada
        next_url = session.pop('gcal_next_url', url_for('main.index'))
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
        user.google_calendar_credentials = json.dumps(creds_data)
        user.has_google_calendar_access = True
        db.session.commit()
    
    def _get_credentials(self, user_id):
        """
        Obtiene las credenciales de Google Calendar para un usuario.
        
        Args:
            user_id: ID del usuario
            
        Returns:
            Credentials: Objeto de credenciales de Google o None
        """
        user = User.query.get(user_id)
        if not user or not user.google_calendar_credentials:
            return None
        
        try:
            creds_data = json.loads(user.google_calendar_credentials)
            
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
    
    def _get_service(self, user_id):
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
                self.API_SERVICE_NAME,
                self.API_VERSION,
                credentials=credentials
            )
            return service
        except Exception as e:
            current_app.logger.error(f"Error al crear servicio: {str(e)}")
            return None
    
    def create_event(self, user_id, meeting):
        """
        Crea un evento en Google Calendar para una reunión.
        
        Args:
            user_id: ID del usuario que crea el evento
            meeting: Objeto Meeting con la información
            
        Returns:
            dict: Datos del evento creado o None
        """
        service = self._get_service(user_id)
        if not service:
            return None
        
        # Preparar datos del evento
        event = {
            'summary': meeting.title,
            'location': meeting.location,
            'description': meeting.description,
            'start': {
                'dateTime': meeting.start_time.isoformat(),
                'timeZone': 'America/Bogota',  # Ajustar según zona horaria
            },
            'end': {
                'dateTime': meeting.end_time.isoformat(),
                'timeZone': 'America/Bogota',  # Ajustar según zona horaria
            },
            'attendees': [
                {'email': meeting.entrepreneur.email},
                {'email': meeting.ally.email}
            ],
            'reminders': {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 30},
                ],
            },
            'conferenceData': {
                'createRequest': {
                    'requestId': f"meeting-{meeting.id}",
                    'conferenceSolutionKey': {
                        'type': 'hangoutsMeet'
                    }
                }
            }
        }
        
        try:
            # Crear el evento en Google Calendar
            event = service.events().insert(
                calendarId='primary',
                body=event,
                conferenceDataVersion=1,
                sendUpdates='all'
            ).execute()
            
            # Actualizar la reunión con los datos del evento
            meeting.calendar_event_id = event.get('id')
            meeting.meet_link = event.get('hangoutLink') or ''
            db.session.commit()
            
            return event
        except googleapiclient.errors.HttpError as e:
            current_app.logger.error(f"Error al crear evento: {str(e)}")
            return None
    
    def update_event(self, user_id, meeting):
        """
        Actualiza un evento existente en Google Calendar.
        
        Args:
            user_id: ID del usuario que actualiza el evento
            meeting: Objeto Meeting con la información actualizada
            
        Returns:
            dict: Datos del evento actualizado o None
        """
        service = self._get_service(user_id)
        if not service or not meeting.calendar_event_id:
            return None
        
        try:
            # Obtener el evento actual
            event = service.events().get(
                calendarId='primary',
                eventId=meeting.calendar_event_id
            ).execute()
            
            # Actualizar datos del evento
            event['summary'] = meeting.title
            event['location'] = meeting.location
            event['description'] = meeting.description
            event['start']['dateTime'] = meeting.start_time.isoformat()
            event['end']['dateTime'] = meeting.end_time.isoformat()
            
            # Actualizar el evento en Google Calendar
            updated_event = service.events().update(
                calendarId='primary',
                eventId=meeting.calendar_event_id,
                body=event,
                sendUpdates='all'
            ).execute()
            
            return updated_event
        except googleapiclient.errors.HttpError as e:
            current_app.logger.error(f"Error al actualizar evento: {str(e)}")
            return None
    
    def delete_event(self, user_id, meeting):
        """
        Elimina un evento de Google Calendar.
        
        Args:
            user_id: ID del usuario que elimina el evento
            meeting: Objeto Meeting a eliminar
            
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        service = self._get_service(user_id)
        if not service or not meeting.calendar_event_id:
            return False
        
        try:
            # Eliminar el evento de Google Calendar
            service.events().delete(
                calendarId='primary',
                eventId=meeting.calendar_event_id,
                sendUpdates='all'
            ).execute()
            
            # Limpiar datos del evento en la reunión
            meeting.calendar_event_id = None
            meeting.meet_link = None
            db.session.commit()
            
            return True
        except googleapiclient.errors.HttpError as e:
            current_app.logger.error(f"Error al eliminar evento: {str(e)}")
            return False
    
    def get_upcoming_events(self, user_id, max_results=10):
        """
        Obtiene los próximos eventos del calendario del usuario.
        
        Args:
            user_id: ID del usuario
            max_results: Número máximo de eventos a obtener
            
        Returns:
            list: Lista de eventos próximos o None
        """
        service = self._get_service(user_id)
        if not service:
            return None
        
        # Obtener la hora actual
        now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indica UTC
        
        try:
            # Obtener eventos
            events_result = service.events().list(
                calendarId='primary',
                timeMin=now,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            return events_result.get('items', [])
        except googleapiclient.errors.HttpError as e:
            current_app.logger.error(f"Error al obtener eventos: {str(e)}")
            return None
    
    def check_availability(self, user_id, start_time, end_time):
        """
        Verifica la disponibilidad de un usuario en un rango de tiempo.
        
        Args:
            user_id: ID del usuario
            start_time: Hora de inicio (datetime)
            end_time: Hora de fin (datetime)
            
        Returns:
            bool: True si está disponible, False si tiene eventos
        """
        service = self._get_service(user_id)
        if not service:
            return False
        
        # Convertir a formato ISO
        time_min = start_time.isoformat()
        time_max = end_time.isoformat()
        
        try:
            # Buscar eventos en el rango de tiempo
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True
            ).execute()
            
            events = events_result.get('items', [])
            return len(events) == 0  # Disponible si no hay eventos
        except googleapiclient.errors.HttpError as e:
            current_app.logger.error(f"Error al verificar disponibilidad: {str(e)}")
            return False
    
    def find_available_slots(self, user_id, date, duration_minutes=60):
        """
        Encuentra espacios disponibles en un día específico.
        
        Args:
            user_id: ID del usuario
            date: Fecha a buscar (datetime.date)
            duration_minutes: Duración deseada en minutos
            
        Returns:
            list: Lista de slots disponibles [(start, end), ...] o None
        """
        service = self._get_service(user_id)
        if not service:
            return None
        
        # Definir horario laboral (9am a 5pm)
        work_start_hour = 9
        work_end_hour = 17
        
        # Crear datetime para el inicio y fin del día laboral
        start_dt = datetime.datetime.combine(date, datetime.time(work_start_hour, 0))
        end_dt = datetime.datetime.combine(date, datetime.time(work_end_hour, 0))
        
        time_min = start_dt.isoformat() + 'Z'
        time_max = end_dt.isoformat() + 'Z'
        
        try:
            # Obtener eventos del día
            events_result = service.events().list(
                calendarId='primary',
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Encontrar slots disponibles
            available_slots = []
            current_time = start_dt
            
            for event in events:
                # Obtener horarios del evento
                event_start = datetime.datetime.fromisoformat(
                    event['start'].get('dateTime', event['start'].get('date'))
                )
                event_end = datetime.datetime.fromisoformat(
                    event['end'].get('dateTime', event['end'].get('date'))
                )
                
                # Verificar si hay espacio antes del evento
                if (event_start - current_time).total_seconds() / 60 >= duration_minutes:
                    available_slots.append((current_time, event_start))
                
                # Actualizar tiempo actual
                current_time = max(current_time, event_end)
            
            # Verificar si hay espacio después del último evento
            if (end_dt - current_time).total_seconds() / 60 >= duration_minutes:
                available_slots.append((current_time, end_dt))
            
            return available_slots
        except googleapiclient.errors.HttpError as e:
            current_app.logger.error(f"Error al buscar slots disponibles: {str(e)}")
            return None

# Crear una instancia del servicio
google_calendar_service = GoogleCalendarService()