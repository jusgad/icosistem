from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    flash,
    current_app,
    jsonify,
    abort
)
from flask_login import current_user, login_required
from app.extensions import db, cache
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.ally import Ally
from app.forms.contact import ContactForm
from app.utils.email import send_email
from app.utils.analytics import track_page_view
from datetime import datetime
import logging

# Crear el blueprint para las rutas principales
main_bp = Blueprint('main', __name__)

# Configurar logger
logger = logging.getLogger(__name__)

@main_bp.before_request
def before_request():
    """Se ejecuta antes de cada request en las rutas de main."""
    track_page_view(request.endpoint)

@main_bp.route('/')
@cache.cached(timeout=300)  # Cache por 5 minutos
def index():
    """Página principal de la aplicación."""
    try:
        # Obtener estadísticas para mostrar
        stats = {
            'entrepreneurs_count': Entrepreneur.query.filter_by(is_active=True).count(),
            'allies_count': Ally.query.filter_by(is_active=True).count(),
            'success_stories': get_featured_success_stories(),
            'upcoming_events': get_upcoming_events()
        }

        # Obtener testimonios destacados
        testimonials = get_featured_testimonials()

        return render_template('index.html',
                             stats=stats,
                             testimonials=testimonials,
                             current_year=datetime.utcnow().year)

    except Exception as e:
        logger.error(f"Error en página principal: {str(e)}")
        return render_template('error/500.html'), 500

@main_bp.route('/about')
@cache.cached(timeout=3600)  # Cache por 1 hora
def about():
    """Página Acerca de Nosotros."""
    try:
        team_members = get_team_members()
        platform_stats = get_platform_stats()
        
        return render_template('about.html',
                             team_members=team_members,
                             stats=platform_stats)
    
    except Exception as e:
        logger.error(f"Error en página about: {str(e)}")
        return render_template('error/500.html'), 500

@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """Página de contacto con formulario."""
    form = ContactForm()
    
    if form.validate_on_submit():
        try:
            # Enviar email de contacto
            send_email(
                subject=f"Nuevo contacto: {form.subject.data}",
                sender=form.email.data,
                recipients=[current_app.config['CONTACT_EMAIL']],
                text_body=render_template('email/contact.txt',
                                        name=form.name.data,
                                        email=form.email.data,
                                        message=form.message.data),
                html_body=render_template('email/contact.html',
                                        name=form.name.data,
                                        email=form.email.data,
                                        message=form.message.data)
            )
            
            # Registrar el contacto en la base de datos
            save_contact_request(form)
            
            flash('Tu mensaje ha sido enviado. Te contactaremos pronto.', 'success')
            return redirect(url_for('main.contact'))
            
        except Exception as e:
            logger.error(f"Error al procesar formulario de contacto: {str(e)}")
            flash('Hubo un error al enviar tu mensaje. Por favor intenta más tarde.', 'error')
    
    return render_template('contact.html', form=form)

@main_bp.route('/services')
def services():
    """Página de servicios ofrecidos."""
    services = {
        'mentoring': {
            'title': 'Mentoría Personalizada',
            'description': 'Conexión con mentores expertos en tu industria',
            'icon': 'mentoring-icon.png'
        },
        'networking': {
            'title': 'Networking',
            'description': 'Acceso a una red de emprendedores y aliados',
            'icon': 'networking-icon.png'
        },
        'resources': {
            'title': 'Recursos',
            'description': 'Acceso a herramientas y recursos exclusivos',
            'icon': 'resources-icon.png'
        }
    }
    
    return render_template('services.html', services=services)

@main_bp.route('/success-stories')
def success_stories():
    """Página de casos de éxito."""
    try:
        stories = get_success_stories()
        return render_template('success_stories.html', stories=stories)
    except Exception as e:
        logger.error(f"Error al cargar casos de éxito: {str(e)}")
        return render_template('error/500.html'), 500

@main_bp.route('/faq')
@cache.cached(timeout=3600)
def faq():
    """Página de preguntas frecuentes."""
    faqs = get_faqs_by_category()
    return render_template('faq.html', faqs=faqs)

@main_bp.route('/terms')
@cache.cached(timeout=86400)  # Cache por 24 horas
def terms():
    """Términos y condiciones."""
    return render_template('legal/terms.html')

@main_bp.route('/privacy')
@cache.cached(timeout=86400)  # Cache por 24 horas
def privacy():
    """Política de privacidad."""
    return render_template('legal/privacy.html')

@main_bp.route('/blog')
def blog():
    """Blog de la plataforma."""
    page = request.args.get('page', 1, type=int)
    posts = get_blog_posts(page)
    return render_template('blog/index.html', posts=posts)

@main_bp.route('/blog/<slug>')
def blog_post(slug):
    """Muestra un post específico del blog."""
    post = get_blog_post(slug)
    if not post:
        abort(404)
    return render_template('blog/post.html', post=post)

@main_bp.route('/newsletter-signup', methods=['POST'])
def newsletter_signup():
    """Endpoint para suscripción al newsletter."""
    try:
        email = request.form.get('email')
        if not email:
            return jsonify({'success': False, 'error': 'Email es requerido'}), 400
        
        # Validar email y agregar a lista de suscriptores
        subscribe_to_newsletter(email)
        
        return jsonify({
            'success': True,
            'message': '¡Gracias por suscribirte a nuestro newsletter!'
        })
        
    except Exception as e:
        logger.error(f"Error en suscripción newsletter: {str(e)}")
        return jsonify({
            'success': False,
            'error': 'Error al procesar la suscripción'
        }), 500

# Funciones auxiliares
def get_featured_success_stories(limit=3):
    """Obtiene historias de éxito destacadas."""
    return Entrepreneur.query.filter_by(
        is_featured=True,
        is_active=True
    ).limit(limit).all()

def get_upcoming_events(limit=5):
    """Obtiene próximos eventos."""
    return Event.query.filter(
        Event.date >= datetime.utcnow()
    ).order_by(Event.date).limit(limit).all()

def get_featured_testimonials(limit=6):
    """Obtiene testimonios destacados."""
    return Testimonial.query.filter_by(
        is_approved=True,
        is_featured=True
    ).limit(limit).all()

def get_team_members():
    """Obtiene información del equipo."""
    return [
        {
            'name': 'Juan Pérez',
            'position': 'CEO',
            'bio': 'Fundador y CEO con más de 15 años de experiencia...',
            'image': 'juan.jpg'
        },
        # Más miembros del equipo...
    ]

def get_platform_stats():
    """Obtiene estadísticas de la plataforma."""
    return {
        'entrepreneurs': Entrepreneur.query.count(),
        'allies': Ally.query.count(),
        'success_stories': SuccessStory.query.count(),
        'countries': User.query.with_entities(User.country).distinct().count()
    }

def save_contact_request(form):
    """Guarda una solicitud de contacto en la base de datos."""
    contact = ContactRequest(
        name=form.name.data,
        email=form.email.data,
        subject=form.subject.data,
        message=form.message.data
    )
    db.session.add(contact)
    db.session.commit()

def get_faqs_by_category():
    """Obtiene FAQs organizadas por categoría."""
    return {
        'general': [
            {
                'question': '¿Qué es esta plataforma?',
                'answer': 'Una plataforma de conexión entre emprendedores y mentores...'
            },
            # Más FAQs...
        ],
        'mentoring': [
            {
                'question': '¿Cómo funciona la mentoría?',
                'answer': 'Los emprendedores son asignados a mentores según su industria...'
            },
            # Más FAQs...
        ]
    }

def get_blog_posts(page):
    """Obtiene posts del blog paginados."""
    return BlogPost.query.filter_by(
        is_published=True
    ).order_by(
        BlogPost.created_at.desc()
    ).paginate(
        page=page,
        per_page=current_app.config['POSTS_PER_PAGE'],
        error_out=False
    )

def subscribe_to_newsletter(email):
    """Procesa la suscripción al newsletter."""
    if NewsletterSubscription.query.filter_by(email=email).first():
        raise ValueError('Email ya está suscrito')
    
    subscription = NewsletterSubscription(email=email)
    db.session.add(subscription)
    db.session.commit()
    
    # Enviar email de confirmación
    send_email(
        subject='Bienvenido a nuestro Newsletter',
        sender=current_app.config['MAIL_DEFAULT_SENDER'],
        recipients=[email],
        text_body=render_template('email/newsletter_welcome.txt'),
        html_body=render_template('email/newsletter_welcome.html')
    )

    # Continuación de app/views/main.py
    @main_bp.route('/search')
    def search():
        """Búsqueda global en la plataforma."""
        query = request.args.get('q', '')
        category = request.args.get('category', 'all')
        page = request.args.get('page', 1, type=int)

        if not query:
            return render_template('search.html', results=None)

        try:
            results = perform_global_search(query, category, page)
            return render_template('search.html',
                                results=results,
                                query=query,
                                category=category)
        except Exception as e:
            logger.error(f"Error en búsqueda: {str(e)}")
            flash('Error al procesar la búsqueda. Por favor intenta de nuevo.', 'error')
            return redirect(url_for('main.index'))

    @main_bp.route('/events')
    def events():
        """Listado de eventos de la plataforma."""
        try:
            # Filtros
            category = request.args.get('category')
            date_from = request.args.get('date_from')
            date_to = request.args.get('date_to')
            format_type = request.args.get('format', 'all')  # presencial/virtual/híbrido
            
            events = get_filtered_events(
                category=category,
                date_from=date_from,
                date_to=date_to,
                format_type=format_type
            )
            
            return render_template('events/index.html',
                                events=events,
                                categories=get_event_categories(),
                                current_filters={
                                    'category': category,
                                    'date_from': date_from,
                                    'date_to': date_to,
                                    'format': format_type
                                })
        except Exception as e:
            logger.error(f"Error al cargar eventos: {str(e)}")
            flash('Error al cargar los eventos. Por favor intenta más tarde.', 'error')
            return redirect(url_for('main.index'))

    @main_bp.route('/events/<slug>')
    def event_detail(slug):
        """Detalle de un evento específico."""
        event = Event.query.filter_by(slug=slug).first_or_404()
        
        # Verificar si el evento es privado y el usuario tiene acceso
        if event.is_private and not current_user.has_access_to_event(event):
            abort(403)
        
        related_events = get_related_events(event)
        
        return render_template('events/detail.html',
                            event=event,
                            related_events=related_events)

    @main_bp.route('/directory')
    def directory():
        """Directorio público de emprendimientos."""
        try:
            # Parámetros de filtrado
            industry = request.args.get('industry')
            location = request.args.get('location')
            stage = request.args.get('stage')
            sort_by = request.args.get('sort', 'newest')
            page = request.args.get('page', 1, type=int)
            
            # Obtener emprendimientos filtrados
            entrepreneurs = get_filtered_entrepreneurs(
                industry=industry,
                location=location,
                stage=stage,
                sort_by=sort_by,
                page=page
            )
            
            return render_template('directory/index.html',
                                entrepreneurs=entrepreneurs,
                                industries=get_industry_list(),
                                locations=get_location_list(),
                                stages=get_stage_list(),
                                current_filters={
                                    'industry': industry,
                                    'location': location,
                                    'stage': stage,
                                    'sort': sort_by
                                })
        except Exception as e:
            logger.error(f"Error al cargar directorio: {str(e)}")
            return render_template('error/500.html'), 500

    @main_bp.route('/impact')
    @cache.cached(timeout=3600)
    def impact():
        """Página de impacto y métricas de la plataforma."""
        try:
            impact_metrics = calculate_platform_impact()
            return render_template('impact.html', metrics=impact_metrics)
        except Exception as e:
            logger.error(f"Error al cargar métricas de impacto: {str(e)}")
            return render_template('error/500.html'), 500

    @main_bp.route('/resources')
    @login_required
    def resources():
        """Biblioteca de recursos."""
        try:
            category = request.args.get('category', 'all')
            search = request.args.get('search', '')
            page = request.args.get('page', 1, type=int)
            
            resources = get_filtered_resources(
                category=category,
                search=search,
                page=page
            )
            
            return render_template('resources/index.html',
                                resources=resources,
                                categories=get_resource_categories(),
                                current_filters={
                                    'category': category,
                                    'search': search
                                })
        except Exception as e:
            logger.error(f"Error al cargar recursos: {str(e)}")
            flash('Error al cargar los recursos. Por favor intenta más tarde.', 'error')
            return redirect(url_for('main.index'))

    @main_bp.route('/download/<token>')
    @login_required
    def download_resource(token):
        """Descarga de recursos protegidos."""
        try:
            # Verificar token y obtener recurso
            resource = verify_download_token(token)
            if not resource:
                abort(404)
            
            # Verificar permisos
            if not current_user.can_download_resource(resource):
                abort(403)
            
            # Registrar la descarga
            log_resource_download(resource, current_user)
            
            return send_file(
                resource.file_path,
                as_attachment=True,
                download_name=resource.filename
            )
        except Exception as e:
            logger.error(f"Error en descarga de recurso: {str(e)}")
            flash('Error al descargar el recurso. Por favor intenta más tarde.', 'error')
            return redirect(url_for('main.resources'))

    @main_bp.route('/feedback', methods=['POST'])
    @login_required
    def submit_feedback():
        """Envío de feedback sobre la plataforma."""
        try:
            data = request.json
            feedback = PlatformFeedback(
                user_id=current_user.id,
                category=data.get('category'),
                rating=data.get('rating'),
                comment=data.get('comment')
            )
            db.session.add(feedback)
            db.session.commit()
            
            # Notificar a administradores si el rating es bajo
            if feedback.rating <= 2:
                notify_admins_low_rating(feedback)
            
            return jsonify({'success': True})
        except Exception as e:
            logger.error(f"Error al procesar feedback: {str(e)}")
            return jsonify({
                'success': False,
                'error': 'Error al procesar el feedback'
            }), 500

    # Funciones auxiliares adicionales

    def perform_global_search(query, category, page):
        """Realiza búsqueda global en la plataforma."""
        results = {
            'entrepreneurs': [],
            'events': [],
            'resources': [],
            'blog_posts': []
        }
        
        if category in ['all', 'entrepreneurs']:
            results['entrepreneurs'] = Entrepreneur.query.filter(
                Entrepreneur.company_name.ilike(f'%{query}%')
            ).paginate(page=page, per_page=10)
        
        if category in ['all', 'events']:
            results['events'] = Event.query.filter(
                Event.title.ilike(f'%{query}%')
            ).paginate(page=page, per_page=10)
        
        # ... más categorías de búsqueda
        
        return results

    def calculate_platform_impact():
        """Calcula métricas de impacto de la plataforma."""
        return {
            'total_entrepreneurs': Entrepreneur.query.count(),
            'total_mentoring_hours': calculate_total_mentoring_hours(),
            'jobs_created': calculate_jobs_created(),
            'total_investment': calculate_total_investment(),
            'success_rate': calculate_success_rate(),
            'social_impact': calculate_social_impact_metrics(),
            'environmental_impact': calculate_environmental_impact()
        }

    def get_filtered_entrepreneurs(industry=None, location=None, stage=None, 
                                sort_by='newest', page=1):
        """Obtiene lista filtrada de emprendimientos."""
        query = Entrepreneur.query.filter_by(is_public=True)
        
        if industry:
            query = query.filter_by(industry=industry)
        if location:
            query = query.filter_by(location=location)
        if stage:
            query = query.filter_by(stage=stage)
        
        if sort_by == 'newest':
            query = query.order_by(Entrepreneur.created_at.desc())
        elif sort_by == 'name':
            query = query.order_by(Entrepreneur.company_name)
        
        return query.paginate(page=page, per_page=12)

    def get_filtered_resources(category=None, search=None, page=1):
        """Obtiene recursos filtrados."""
        query = Resource.query.filter_by(is_active=True)
        
        if category and category != 'all':
            query = query.filter_by(category=category)
        
        if search:
            query = query.filter(
                or_(
                    Resource.title.ilike(f'%{search}%'),
                    Resource.description.ilike(f'%{search}%')
                )
            )
        
        return query.order_by(Resource.created_at.desc()).paginate(
            page=page, per_page=15
        )

    def notify_admins_low_rating(feedback):
        """Notifica a administradores sobre feedback negativo."""
        admin_emails = [u.email for u in User.query.filter_by(role='admin').all()]
        
        send_email(
            subject='Feedback Negativo Recibido',
            sender=current_app.config['MAIL_DEFAULT_SENDER'],
            recipients=admin_emails,
            text_body=render_template('email/low_rating_notification.txt',
                                    feedback=feedback),
            html_body=render_template('email/low_rating_notification.html',
                                    feedback=feedback)
        )