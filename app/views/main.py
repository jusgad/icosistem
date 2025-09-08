"""
Views principales del ecosistema de emprendimiento.
Maneja la cara pública de la plataforma, landing pages, y funcionalidades generales.

Características:
- Landing page optimizada para conversión
- Páginas informativas del ecosistema
- Sistema de contacto y soporte
- Directorio público de emprendimientos
- Búsqueda y filtrado avanzado
- Newsletter y marketing
- SEO optimizado
- Analytics integrado
- Multi-idioma
- Responsive design

Versión: 1.0
Autor: Sistema de Emprendimiento
"""

from flask import (
    Blueprint, render_template, request, redirect, url_for, 
    flash, jsonify, session, current_app, g, abort, make_response
)
from flask_wtf import FlaskForm
from flask_babel import _, get_locale, ngettext
from wtforms import StringField, TextAreaField, SelectField, EmailField, BooleanField
from wtforms.validators import DataRequired, Email, Length, Optional, ValidationError
from sqlalchemy import func, or_, and_, desc
from datetime import datetime, timedelta, timezone
from typing import Optional as TypingOptional, Any
import json
import logging
from collections import defaultdict
from urllib.parse import urlparse, urljoin

# Importaciones locales - solo las esenciales
from app.models.user import User, UserType
# from app.models.entrepreneur import Entrepreneur
from app.models.project import Project, ProjectStatus
from app.models.organization import Organization
# from app.models.program import Program
# from app.models.testimonial import Testimonial  # File doesn't exist
# from app.models.newsletter_subscription import NewsletterSubscription

# Stubos temporales
class ProjectStatus:
    IDEA = 'idea'
    DEVELOPMENT = 'development'
    LAUNCH = 'launch'

class ProjectCategory:
    TECH = 'tech'
    HEALTH = 'health'
# from app.models.contact_message import ContactMessage, MessageType
# from app.models.blog_post import BlogPost, PostStatus
# from app.services.email import EmailService
# from app.services.analytics_service import AnalyticsService

# Stubs temporales
class ContactMessage:
    pass

class MessageType:
    INQUIRY = 'inquiry'

class BlogPost:
    pass

class Testimonial:
    """Stub temporal para Testimonial."""
    @classmethod
    def query(cls):
        class MockQuery:
            def filter(self, *args):
                return self
            def order_by(self, *args):
                return self
            def limit(self, limit):
                return []
        return MockQuery()

class PostStatus:
    PUBLISHED = 'published'
# from app.services.newsletter_service import NewsletterService
# from app.utils.formatters import format_currency, format_datetime, truncate_text
# from app.utils.string_utils import slugify, sanitize_input
# from app.utils.seo import generate_meta_tags, generate_structured_data

# Funciones stub temporales
def format_currency(amount):
    return f"${amount:,.2f}"

def format_datetime(dt):
    return str(dt) if dt else ""

def truncate_text(text, length=100):
    return text[:length] + "..." if text and len(text) > length else text

def slugify(text):
    return text.lower().replace(' ', '-') if text else ""

def sanitize_input(text):
    return text.strip() if text else ""
from app.extensions import db, cache

logger = logging.getLogger(__name__)

# Crear blueprint
main_bp = Blueprint('main', __name__)

# Formularios
class ContactForm(FlaskForm):
    """Formulario de contacto."""
    name = StringField(_('Nombre'), validators=[
        DataRequired(message=_('El nombre es obligatorio')),
        Length(min=2, max=100, message=_('El nombre debe tener entre 2 y 100 caracteres'))
    ])
    
    email = EmailField(_('Email'), validators=[
        DataRequired(message=_('El email es obligatorio')),
        Email(message=_('Ingresa un email válido'))
    ])
    
    phone = StringField(_('Teléfono'), validators=[
        Optional(),
        Length(max=20, message=_('El teléfono no puede tener más de 20 caracteres'))
    ])
    
    company = StringField(_('Empresa/Organización'), validators=[
        Optional(),
        Length(max=100, message=_('El nombre de la empresa no puede tener más de 100 caracteres'))
    ])
    
    message_type = SelectField(_('Tipo de consulta'), choices=[
        ('general', _('Consulta general')),
        ('entrepreneur', _('Soy emprendedor')),
        ('mentor', _('Quiero ser mentor')),
        ('client', _('Soy inversionista/cliente')),
        ('partnership', _('Alianza estratégica')),
        ('support', _('Soporte técnico'))
    ], validators=[DataRequired()])
    
    subject = StringField(_('Asunto'), validators=[
        DataRequired(message=_('El asunto es obligatorio')),
        Length(min=5, max=200, message=_('El asunto debe tener entre 5 y 200 caracteres'))
    ])
    
    message = TextAreaField(_('Mensaje'), validators=[
        DataRequired(message=_('El mensaje es obligatorio')),
        Length(min=10, max=2000, message=_('El mensaje debe tener entre 10 y 2000 caracteres'))
    ])
    
    newsletter = BooleanField(_('Suscribirme al newsletter'))
    
    def validate_phone(self, field):
        """Validación personalizada del teléfono."""
        if field.data:
            # Limpiar el teléfono de caracteres no numéricos
            phone_clean = ''.join(filter(str.isdigit, field.data))
            if len(phone_clean) < 7:
                raise ValidationError(_('El teléfono debe tener al menos 7 dígitos'))

class NewsletterForm(FlaskForm):
    """Formulario de suscripción al newsletter."""
    email = EmailField(_('Email'), validators=[
        DataRequired(message=_('El email es obligatorio')),
        Email(message=_('Ingresa un email válido'))
    ])
    
    interests = SelectField(_('Intereses'), choices=[
        ('entrepreneur', _('Emprendimiento')),
        ('mentorship', _('Mentoría')),
        ('funding', _('Financiamiento')),
        ('innovation', _('Innovación')),
        ('all', _('Todos los temas'))
    ], default='all')
    
    def validate_email(self, field):
        """Validar que el email no esté ya suscrito."""
        existing = NewsletterSubscription.query.filter_by(
            email=field.data,
            is_active=True
        ).first()
        if existing:
            raise ValidationError(_('Este email ya está suscrito al newsletter'))

class SearchForm(FlaskForm):
    """Formulario de búsqueda."""
    query = StringField(_('Buscar'), validators=[
        Optional(),
        Length(max=100, message=_('La búsqueda no puede tener más de 100 caracteres'))
    ])
    
    category = SelectField(_('Categoría'), choices=[
        ('all', _('Todas las categorías')),
        ('projects', _('Proyectos')),
        ('entrepreneurs', _('Emprendedores')),
        ('mentors', _('Mentores')),
        ('organizations', _('Organizaciones'))
    ], default='all')
    
    sector = SelectField(_('Sector'), choices=[
        ('', _('Todos los sectores')),
        ('technology', _('Tecnología')),
        ('health', _('Salud')),
        ('education', _('Educación')),
        ('finance', _('Finanzas')),
        ('retail', _('Comercio')),
        ('agriculture', _('Agricultura')),
        ('environment', _('Medio ambiente')),
        ('social', _('Impacto social'))
    ], default='')

# Rutas principales
@main_bp.route('/')
@cache.cached(timeout=300)  # Cache por 5 minutos
def index():
    """Página de inicio / Landing page."""
    try:
        # Estadísticas para mostrar en el landing
        stats = _get_landing_stats()
        
        # Proyectos destacados
        featured_projects = _get_featured_projects(limit=6)
        
        # Testimonios recientes
        testimonials = _get_recent_testimonials(limit=3)
        
        # Posts del blog
        recent_posts = _get_recent_blog_posts(limit=3)
        
        # Organizaciones aliadas
        partner_organizations = _get_partner_organizations(limit=8)
        
        # Métrica para analytics
        _track_page_view('landing_page')
        
        # Meta tags para SEO
        meta_tags = generate_meta_tags(
            title=_('Ecosistema de Emprendimiento - Conectando emprendedores con mentores'),
            description=_('Plataforma integral para emprendedores que buscan mentoría, financiamiento y conexiones estratégicas. Únete a nuestro ecosistema de innovación.'),
            keywords='emprendimiento, mentores, startups, financiamiento, innovación, business',
            og_image=url_for('static', filename='img/landing-og.jpg', _external=True)
        )
        
        return render_template(
            'main/index.html',
            stats=stats,
            featured_projects=featured_projects,
            testimonials=testimonials,
            recent_posts=recent_posts,
            partner_organizations=partner_organizations,
            meta_tags=meta_tags,
            structured_data=_generate_landing_structured_data()
        )
        
    except Exception as e:
        logger.error(f"Error rendering index page: {str(e)}")
        # En caso de error, mostrar versión simplificada
        return render_template('main/index_simple.html')

@main_bp.route('/about')
@cache.cached(timeout=3600)  # Cache por 1 hora
def about():
    """Página acerca de nosotros."""
    try:
        # Información del equipo
        team_members = _get_team_members()
        
        # Cronología de la empresa
        milestones = _get_company_milestones()
        
        # Estadísticas de impacto
        impact_stats = _get_impact_statistics()
        
        _track_page_view('about_page')
        
        meta_tags = generate_meta_tags(
            title=_('Acerca de Nosotros - Ecosistema de Emprendimiento'),
            description=_('Conoce nuestra misión de impulsar el emprendimiento a través de la mentoría, la innovación y las conexiones estratégicas.'),
            keywords='about, empresa, equipo, misión, visión, emprendimiento'
        )
        
        return render_template(
            'main/about.html',
            team_members=team_members,
            milestones=milestones,
            impact_stats=impact_stats,
            meta_tags=meta_tags
        )
        
    except Exception as e:
        logger.error(f"Error rendering about page: {str(e)}")
        return render_template('main/about.html', error=True)

@main_bp.route('/contact', methods=['GET', 'POST'])
def contact():
    """Página de contacto con formulario."""
    form = ContactForm()
    
    if form.validate_on_submit():
        try:
            # Crear mensaje de contacto
            contact_message = ContactMessage(
                name=sanitize_input(form.name.data),
                email=form.email.data.lower().strip(),
                phone=sanitize_input(form.phone.data) if form.phone.data else None,
                company=sanitize_input(form.company.data) if form.company.data else None,
                message_type=MessageType(form.message_type.data),
                subject=sanitize_input(form.subject.data),
                message=sanitize_input(form.message.data),
                ip_address=request.remote_addr,
                user_agent=request.user_agent.string
            )
            
            db.session.add(contact_message)
            
            # Suscribir al newsletter si lo solicitó
            if form.newsletter.data:
                _subscribe_to_newsletter(form.email.data, 'all')
            
            db.session.commit()
            
            # Enviar email de notificación al equipo
            _send_contact_notification(contact_message)
            
            # Enviar email de confirmación al usuario
            _send_contact_confirmation(contact_message)
            
            # Trackear evento
            _track_contact_form_submission(form.message_type.data)
            
            flash(_('¡Gracias por contactarnos! Te responderemos pronto.'), 'success')
            
            return redirect(url_for('main.contact'))
            
        except Exception as e:
            logger.error(f"Error processing contact form: {str(e)}")
            db.session.rollback()
            flash(_('Ha ocurrido un error. Por favor intenta nuevamente.'), 'error')
    
    _track_page_view('contact_page')
    
    meta_tags = generate_meta_tags(
        title=_('Contacto - Ecosistema de Emprendimiento'),
        description=_('Ponte en contacto con nosotros. Estamos aquí para ayudarte a hacer crecer tu emprendimiento.'),
        keywords='contacto, soporte, ayuda, emprendimiento'
    )
    
    return render_template(
        'main/contact.html',
        form=form,
        meta_tags=meta_tags
    )

@main_bp.route('/directory')
def directory():
    """Directorio público de emprendimientos."""
    try:
        # Formulario de búsqueda
        search_form = SearchForm()
        
        # Parámetros de filtrado
        query = request.args.get('query', '').strip()
        category = request.args.get('category', 'all')
        sector = request.args.get('sector', '')
        page = request.args.get('page', 1, type=int)
        per_page = 12
        
        # Query base de proyectos públicos
        projects_query = Project.query.filter(
            Project.status == ProjectStatus.ACTIVE,
            Project.is_public == True
        ).join(Entrepreneur).join(User)
        
        # Aplicar filtros
        if query:
            search_filter = or_(
                Project.name.ilike(f'%{query}%'),
                Project.description.ilike(f'%{query}%'),
                Project.tags.ilike(f'%{query}%'),
                User.full_name.ilike(f'%{query}%')
            )
            projects_query = projects_query.filter(search_filter)
        
        if sector:
            projects_query = projects_query.filter(Project.sector == sector)
        
        # Ordenar por fecha de creación
        projects_query = projects_query.order_by(desc(Project.created_at))
        
        # Paginar
        pagination = projects_query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Estadísticas del directorio
        directory_stats = {
            'total_projects': Project.query.filter(
                Project.status == ProjectStatus.ACTIVE,
                Project.is_public == True
            ).count(),
            'total_entrepreneurs': User.query.filter(
                User.user_type == UserType.ENTREPRENEUR,
                User.is_active == True
            ).count(),
            'sectors_count': db.session.query(
                func.count(func.distinct(Project.sector))
            ).filter(
                Project.status == ProjectStatus.ACTIVE,
                Project.is_public == True
            ).scalar()
        }
        
        _track_page_view('directory_page', {'search_query': query, 'sector': sector})
        
        meta_tags = generate_meta_tags(
            title=_('Directorio de Emprendimientos - Descubre Proyectos Innovadores'),
            description=_('Explora emprendimientos innovadores en nuestro directorio. Encuentra proyectos por sector, etapa y ubicación.'),
            keywords='directorio, emprendimientos, proyectos, startups, innovación'
        )
        
        return render_template(
            'main/directory.html',
            projects=pagination.items,
            pagination=pagination,
            search_form=search_form,
            directory_stats=directory_stats,
            current_filters={
                'query': query,
                'category': category,
                'sector': sector
            },
            meta_tags=meta_tags
        )
        
    except Exception as e:
        logger.error(f"Error rendering directory: {str(e)}")
        return render_template('main/directory.html', error=True)

@main_bp.route('/project/<int:project_id>')
@main_bp.route('/project/<int:project_id>/<slug>')
def project_detail(project_id, slug=None):
    """Página de detalle de proyecto público."""
    try:
        project = Project.query.filter(
            Project.id == project_id,
            Project.status == ProjectStatus.ACTIVE,
            Project.is_public == True
        ).first_or_404()
        
        # Verificar slug para SEO
        expected_slug = slugify(project.name)
        if slug != expected_slug:
            return redirect(url_for('main.project_detail', 
                                  project_id=project_id, 
                                  slug=expected_slug), code=301)
        
        # Proyectos relacionados
        related_projects = _get_related_projects(project, limit=3)
        
        # Incrementar vistas
        project.view_count = (project.view_count or 0) + 1
        db.session.commit()
        
        _track_page_view('project_detail', {
            'project_id': project_id,
            'project_name': project.name
        })
        
        meta_tags = generate_meta_tags(
            title=f"{project.name} - {_('Emprendimiento Innovador')}",
            description=truncate_text(project.description, 160),
            keywords=f"{project.name}, emprendimiento, {project.sector}, innovación",
            og_image=project.image_url if project.image_url else None
        )
        
        structured_data = _generate_project_structured_data(project)
        
        return render_template(
            'main/project_detail.html',
            project=project,
            related_projects=related_projects,
            meta_tags=meta_tags,
            structured_data=structured_data
        )
        
    except Exception as e:
        logger.error(f"Error rendering project detail {project_id}: {str(e)}")
        abort(404)

@main_bp.route('/entrepreneurs')
def entrepreneurs():
    """Directorio de emprendedores."""
    try:
        page = request.args.get('page', 1, type=int)
        sector = request.args.get('sector', '')
        search = request.args.get('search', '').strip()
        per_page = 16
        
        # Query de emprendedores activos con proyectos públicos
        query = User.query.filter(
            User.user_type == UserType.ENTREPRENEUR,
            User.is_active == True,
            User.is_public_profile == True
        ).join(Entrepreneur).outerjoin(Project).filter(
            or_(
                Project.is_public == True,
                Project.id.is_(None)
            )
        ).distinct()
        
        # Aplicar filtros
        if search:
            query = query.filter(
                or_(
                    User.full_name.ilike(f'%{search}%'),
                    User.bio.ilike(f'%{search}%'),
                    Entrepreneur.expertise.ilike(f'%{search}%')
                )
            )
        
        if sector:
            query = query.join(Project).filter(Project.sector == sector)
        
        # Ordenar por actividad reciente
        query = query.order_by(desc(User.last_login_at))
        
        # Paginar
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        _track_page_view('entrepreneurs_directory', {
            'search': search,
            'sector': sector
        })
        
        meta_tags = generate_meta_tags(
            title=_('Emprendedores - Conecta con Innovadores'),
            description=_('Conoce a emprendedores innovadores y sus proyectos. Conecta con líderes que están transformando industrias.'),
            keywords='emprendedores, innovadores, startups, líderes, networking'
        )
        
        return render_template(
            'main/entrepreneurs.html',
            entrepreneurs=pagination.items,
            pagination=pagination,
            current_filters={'search': search, 'sector': sector},
            meta_tags=meta_tags
        )
        
    except Exception as e:
        logger.error(f"Error rendering entrepreneurs directory: {str(e)}")
        return render_template('main/entrepreneurs.html', error=True)

@main_bp.route('/blog')
def blog():
    """Blog de la plataforma."""
    try:
        page = request.args.get('page', 1, type=int)
        category = request.args.get('category', '')
        per_page = 9
        
        # Query de posts publicados
        query = BlogPost.query.filter(
            BlogPost.status == PostStatus.PUBLISHED,
            BlogPost.published_at <= datetime.now(timezone.utc)
        )
        
        if category:
            query = query.filter(BlogPost.category == category)
        
        query = query.order_by(desc(BlogPost.published_at))
        
        # Paginar
        pagination = query.paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        # Posts destacados
        featured_posts = BlogPost.query.filter(
            BlogPost.status == PostStatus.PUBLISHED,
            BlogPost.is_featured == True
        ).order_by(desc(BlogPost.published_at)).limit(3).all()
        
        # Categorías disponibles
        categories = db.session.query(
            BlogPost.category,
            func.count(BlogPost.id).label('count')
        ).filter(
            BlogPost.status == PostStatus.PUBLISHED
        ).group_by(BlogPost.category).all()
        
        _track_page_view('blog_index', {'category': category})
        
        meta_tags = generate_meta_tags(
            title=_('Blog - Recursos para Emprendedores'),
            description=_('Artículos, consejos y recursos para emprendedores. Aprende de expertos y casos de éxito.'),
            keywords='blog, emprendimiento, consejos, recursos, casos de éxito'
        )
        
        return render_template(
            'main/blog.html',
            posts=pagination.items,
            pagination=pagination,
            featured_posts=featured_posts,
            categories=categories,
            current_category=category,
            meta_tags=meta_tags
        )
        
    except Exception as e:
        logger.error(f"Error rendering blog: {str(e)}")
        return render_template('main/blog.html', error=True)

@main_bp.route('/newsletter/subscribe', methods=['POST'])
def subscribe_newsletter():
    """Suscripción al newsletter via AJAX."""
    form = NewsletterForm()
    
    if form.validate_on_submit():
        try:
            success = _subscribe_to_newsletter(
                form.email.data,
                form.interests.data
            )
            
            if success:
                _track_newsletter_subscription(form.interests.data)
                return jsonify({
                    'success': True,
                    'message': _('¡Gracias por suscribirte! Te enviaremos contenido valioso.')
                })
            else:
                return jsonify({
                    'success': False,
                    'message': _('Ha ocurrido un error. Por favor intenta nuevamente.')
                }), 400
                
        except Exception as e:
            logger.error(f"Error subscribing to newsletter: {str(e)}")
            return jsonify({
                'success': False,
                'message': _('Error interno. Por favor intenta más tarde.')
            }), 500
    
    # Errores de validación
    errors = []
    for field, field_errors in form.errors.items():
        errors.extend(field_errors)
    
    return jsonify({
        'success': False,
        'message': errors[0] if errors else _('Datos inválidos')
    }), 400

@main_bp.route('/search/api')
def search_api():
    """API de búsqueda para autocompletado."""
    query = request.args.get('q', '').strip()
    limit = request.args.get('limit', 10, type=int)
    
    if len(query) < 2:
        return jsonify({'results': []})
    
    try:
        results = []
        
        # Buscar proyectos
        projects = Project.query.filter(
            Project.name.ilike(f'%{query}%'),
            Project.status == ProjectStatus.ACTIVE,
            Project.is_public == True
        ).limit(limit // 2).all()
        
        for project in projects:
            results.append({
                'type': 'project',
                'title': project.name,
                'description': truncate_text(project.description, 100),
                'url': url_for('main.project_detail', 
                              project_id=project.id, 
                              slug=slugify(project.name)),
                'image': project.image_url,
                'sector': project.sector
            })
        
        # Buscar emprendedores
        entrepreneurs = User.query.filter(
            User.user_type == UserType.ENTREPRENEUR,
            User.full_name.ilike(f'%{query}%'),
            User.is_active == True,
            User.is_public_profile == True
        ).limit(limit // 2).all()
        
        for entrepreneur in entrepreneurs:
            results.append({
                'type': 'entrepreneur',
                'title': entrepreneur.full_name,
                'description': entrepreneur.bio or '',
                'url': url_for('main.entrepreneur_profile', user_id=entrepreneur.id),
                'image': entrepreneur.avatar_url,
                'company': entrepreneur.entrepreneur.company_name if entrepreneur.entrepreneur else None
            })
        
        return jsonify({'results': results[:limit]})
        
    except Exception as e:
        logger.error(f"Error in search API: {str(e)}")
        return jsonify({'results': [], 'error': 'Error interno'}), 500

@main_bp.route('/stats/api')
@cache.cached(timeout=600)  # Cache por 10 minutos
def stats_api():
    """API pública de estadísticas."""
    try:
        stats = _get_landing_stats()
        return jsonify(stats)
    except Exception as e:
        logger.error(f"Error getting stats: {str(e)}")
        return jsonify({'error': 'Error obteniendo estadísticas'}), 500

@main_bp.route('/sitemap.xml')
@cache.cached(timeout=86400)  # Cache por 24 horas
def sitemap():
    """Genera sitemap XML dinámico."""
    try:
        urls = []
        
        # URLs estáticas
        static_pages = [
            ('main.index', 'daily', 1.0),
            ('main.about', 'monthly', 0.8),
            ('main.contact', 'monthly', 0.7),
            ('main.directory', 'daily', 0.9),
            ('main.entrepreneurs', 'weekly', 0.8),
            ('main.blog', 'daily', 0.8)
        ]
        
        for endpoint, changefreq, priority in static_pages:
            urls.append({
                'loc': url_for(endpoint, _external=True),
                'changefreq': changefreq,
                'priority': priority,
                'lastmod': datetime.now(timezone.utc).strftime('%Y-%m-%d')
            })
        
        # Proyectos públicos
        projects = Project.query.filter(
            Project.status == ProjectStatus.ACTIVE,
            Project.is_public == True
        ).all()
        
        for project in projects:
            urls.append({
                'loc': url_for('main.project_detail', 
                              project_id=project.id,
                              slug=slugify(project.name),
                              _external=True),
                'changefreq': 'weekly',
                'priority': 0.7,
                'lastmod': project.updated_at.strftime('%Y-%m-%d')
            })
        
        # Posts del blog
        posts = BlogPost.query.filter(
            BlogPost.status == PostStatus.PUBLISHED
        ).all()
        
        for post in posts:
            urls.append({
                'loc': url_for('main.blog_post', 
                              post_id=post.id,
                              slug=slugify(post.title),
                              _external=True),
                'changefreq': 'monthly',
                'priority': 0.6,
                'lastmod': post.published_at.strftime('%Y-%m-%d')
            })
        
        # Generar XML
        xml_content = render_template('sitemaps/sitemap.xml', urls=urls)
        response = make_response(xml_content)
        response.headers['Content-Type'] = 'application/xml'
        
        return response
        
    except Exception as e:
        logger.error(f"Error generating sitemap: {str(e)}")
        abort(500)

# Funciones auxiliares
def _get_landing_stats() -> dict[str, Any]:
    """Obtiene estadísticas para el landing page."""
    try:
        stats = {
            'total_entrepreneurs': User.query.filter(
                User.user_type == UserType.ENTREPRENEUR,
                User.is_active == True
            ).count(),
            
            'total_projects': Project.query.filter(
                Project.status == ProjectStatus.ACTIVE
            ).count(),
            
            'total_mentors': User.query.filter(
                User.user_type == UserType.ALLY,
                User.is_active == True
            ).count(),
            
            'total_funding': db.session.query(
                func.sum(Project.funding_received)
            ).filter(
                Project.status == ProjectStatus.ACTIVE
            ).scalar() or 0,
            
            'success_stories': Project.query.filter(
                Project.status == ProjectStatus.COMPLETED,
                Project.is_success_story == True
            ).count(),
            
            'active_programs': Program.query.filter(
                Program.is_active == True,
                Program.start_date <= datetime.now(timezone.utc),
                Program.end_date >= datetime.now(timezone.utc)
            ).count()
        }
        
        return stats
        
    except Exception as e:
        logger.error(f"Error getting landing stats: {str(e)}")
        return {}

def _get_featured_projects(limit: int = 6) -> list[Project]:
    """Obtiene proyectos destacados."""
    try:
        return Project.query.filter(
            Project.status == ProjectStatus.ACTIVE,
            Project.is_public == True,
            Project.is_featured == True
        ).order_by(desc(Project.featured_at)).limit(limit).all()
    except Exception as e:
        logger.error(f"Error getting featured projects: {str(e)}")
        return []

def _get_recent_testimonials(limit: int = 3) -> list[Testimonial]:
    """Obtiene testimonios recientes."""
    try:
        return Testimonial.query.filter(
            Testimonial.is_active == True,
            Testimonial.is_approved == True
        ).order_by(desc(Testimonial.created_at)).limit(limit).all()
    except Exception as e:
        logger.error(f"Error getting testimonials: {str(e)}")
        return []

def _get_recent_blog_posts(limit: int = 3) -> list[BlogPost]:
    """Obtiene posts recientes del blog."""
    try:
        return BlogPost.query.filter(
            BlogPost.status == PostStatus.PUBLISHED,
            BlogPost.published_at <= datetime.now(timezone.utc)
        ).order_by(desc(BlogPost.published_at)).limit(limit).all()
    except Exception as e:
        logger.error(f"Error getting blog posts: {str(e)}")
        return []

def _get_partner_organizations(limit: int = 8) -> list[Organization]:
    """Obtiene organizaciones aliadas."""
    try:
        return Organization.query.filter(
            Organization.is_active == True,
            Organization.is_partner == True,
            Organization.logo_url.isnot(None)
        ).order_by(func.random()).limit(limit).all()
    except Exception as e:
        logger.error(f"Error getting partner organizations: {str(e)}")
        return []

def _subscribe_to_newsletter(email: str, interests: str) -> bool:
    """Suscribe un email al newsletter."""
    try:
        # Verificar si ya existe
        existing = NewsletterSubscription.query.filter_by(email=email).first()
        
        if existing:
            if existing.is_active:
                return True  # Ya está suscrito
            else:
                # Reactivar suscripción
                existing.is_active = True
                existing.interests = interests
                existing.subscribed_at = datetime.now(timezone.utc)
        else:
            # Nueva suscripción
            subscription = NewsletterSubscription(
                email=email,
                interests=interests,
                source='website',
                ip_address=request.remote_addr
            )
            db.session.add(subscription)
        
        db.session.commit()
        
        # Enviar email de bienvenida
        newsletter_service = NewsletterService()
        newsletter_service.send_welcome_email(email, interests)
        
        return True
        
    except Exception as e:
        logger.error(f"Error subscribing to newsletter: {str(e)}")
        db.session.rollback()
        return False

def _track_page_view(page_name: str, additional_data: Dict = None):
    """Registra vista de página para analytics."""
    try:
        analytics_service = AnalyticsService()
        data = {
            'page': page_name,
            'url': request.url,
            'referrer': request.referrer,
            'user_agent': request.user_agent.string,
            'ip': request.remote_addr,
            'language': get_locale()
        }
        
        if additional_data:
            data.update(additional_data)
        
        analytics_service.track_page_view(data)
        
    except Exception as e:
        logger.error(f"Error tracking page view: {str(e)}")

def _track_contact_form_submission(message_type: str):
    """Registra envío de formulario de contacto."""
    try:
        analytics_service = AnalyticsService()
        analytics_service.track_event('contact_form_submission', {
            'message_type': message_type,
            'page': 'contact',
            'ip': request.remote_addr
        })
    except Exception as e:
        logger.error(f"Error tracking contact form: {str(e)}")

def _track_newsletter_subscription(interests: str):
    """Registra suscripción al newsletter."""
    try:
        analytics_service = AnalyticsService()
        analytics_service.track_event('newsletter_subscription', {
            'interests': interests,
            'source': 'website',
            'ip': request.remote_addr
        })
    except Exception as e:
        logger.error(f"Error tracking newsletter subscription: {str(e)}")

def _send_contact_notification(message: ContactMessage):
    """Envía notificación de nuevo mensaje de contacto."""
    try:
        email_service = EmailService()
        email_service.send_contact_notification(message)
    except Exception as e:
        logger.error(f"Error sending contact notification: {str(e)}")

def _send_contact_confirmation(message: ContactMessage):
    """Envía confirmación al usuario que envió el mensaje."""
    try:
        email_service = EmailService()
        email_service.send_contact_confirmation(message)
    except Exception as e:
        logger.error(f"Error sending contact confirmation: {str(e)}")

def _generate_landing_structured_data() -> str:
    """Genera datos estructurados para el landing page."""
    data = {
        "@context": "https://schema.org",
        "@type": "Organization",
        "name": "Ecosistema de Emprendimiento",
        "description": "Plataforma integral para emprendedores que conecta con mentores y recursos",
        "url": url_for('main.index', _external=True),
        "logo": url_for('static', filename='img/logo.png', _external=True),
        "contactPoint": {
            "@type": "ContactPoint",
            "telephone": current_app.config.get('CONTACT_PHONE', ''),
            "contactType": "customer service",
            "email": current_app.config.get('CONTACT_EMAIL', '')
        },
        "sameAs": [
            current_app.config.get('SOCIAL_LINKEDIN', ''),
            current_app.config.get('SOCIAL_TWITTER', ''),
            current_app.config.get('SOCIAL_FACEBOOK', '')
        ]
    }
    
    return json.dumps(data, ensure_ascii=False)

def _generate_project_structured_data(project: Project) -> str:
    """Genera datos estructurados para un proyecto."""
    data = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": project.name,
        "description": project.description,
        "category": project.sector,
        "brand": {
            "@type": "Organization",
            "name": project.entrepreneur.company_name or project.entrepreneur.user.full_name
        },
        "url": url_for('main.project_detail', 
                      project_id=project.id,
                      slug=slugify(project.name),
                      _external=True)
    }
    
    if project.image_url:
        data["image"] = project.image_url
    
    return json.dumps(data, ensure_ascii=False)

# Procesadores de contexto específicos del blueprint
@main_bp.context_processor
def inject_main_context():
    """Inyecta contexto específico para vistas principales."""
    return {
        'newsletter_form': NewsletterForm(),
        'search_form': SearchForm(),
        'current_year': datetime.now(timezone.utc).year,
        'social_links': {
            'linkedin': current_app.config.get('SOCIAL_LINKEDIN', ''),
            'twitter': current_app.config.get('SOCIAL_TWITTER', ''),
            'facebook': current_app.config.get('SOCIAL_FACEBOOK', ''),
            'instagram': current_app.config.get('SOCIAL_INSTAGRAM', '')
        }
    }

# Manejadores de errores específicos
@main_bp.errorhandler(404)
def not_found_error(error):
    """Maneja errores 404 en el blueprint principal."""
    _track_page_view('404_error', {'requested_url': request.url})
    return render_template('errors/404.html'), 404

@main_bp.errorhandler(500)
def internal_error(error):
    """Maneja errores 500 en el blueprint principal."""
    db.session.rollback()
    _track_page_view('500_error', {'requested_url': request.url})
    return render_template('errors/500.html'), 500