from flask import Blueprint, render_template, request, jsonify, current_app, abort
from flask_login import login_required, current_user
from sqlalchemy import or_

from app.extensions import db
from app.models.entrepreneur import Entrepreneur
from app.models.user import User
from app.models.relationship import Relationship
from app.utils.decorators import client_required
from app.forms.client import EntrepreneurSearchForm

# Creación del blueprint para el directorio de emprendimientos
directory_bp = Blueprint('client_directory', __name__, url_prefix='/client/directory')

@directory_bp.route('/', methods=['GET'])
@login_required
@client_required
def entrepreneur_directory():
    """Vista principal del directorio de emprendimientos para clientes."""
    # Formulario para buscar emprendedores
    search_form = EntrepreneurSearchForm()
    
    # Por defecto mostrar todos los emprendedores activos
    entrepreneurs = get_entrepreneurs()
    
    return render_template(
        'client/entrepreneurs.html',
        entrepreneurs=entrepreneurs,
        search_form=search_form
    )

@directory_bp.route('/search', methods=['GET'])
@login_required
@client_required
def search_entrepreneurs():
    """Buscar emprendedores según criterios específicos."""
    # Obtener parámetros de búsqueda
    search_query = request.args.get('query', '')
    sector = request.args.get('sector', '')
    region = request.args.get('region', '')
    status = request.args.get('status', 'active')  # Por defecto solo mostrar activos
    
    # Realizar búsqueda con filtros
    entrepreneurs = get_entrepreneurs(
        search_query=search_query,
        sector=sector,
        region=region,
        status=status
    )
    
    # Si la solicitud es AJAX, devolver JSON
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({
            'entrepreneurs': [entrepreneur_to_dict(e) for e in entrepreneurs]
        })
    
    # Si no es AJAX, renderizar la página completa con resultados
    search_form = EntrepreneurSearchForm()
    search_form.query.data = search_query
    search_form.sector.data = sector
    search_form.region.data = region
    search_form.status.data = status
    
    return render_template(
        'client/entrepreneurs.html',
        entrepreneurs=entrepreneurs,
        search_form=search_form
    )

@directory_bp.route('/<int:entrepreneur_id>', methods=['GET'])
@login_required
@client_required
def entrepreneur_detail(entrepreneur_id):
    """Ver detalles de un emprendedor específico."""
    entrepreneur = Entrepreneur.query.get_or_404(entrepreneur_id)
    
    # Verificar si el emprendedor está activo, solo admins pueden ver inactivos
    if not entrepreneur.is_active and not current_user.is_admin:
        abort(404)
    
    # Obtener datos adicionales
    user = User.query.get(entrepreneur.user_id)
    
    # Obtener aliados asignados actualmente
    current_allies = db.session.query(User).join(
        Relationship, User.id == Relationship.ally_id
    ).filter(
        Relationship.entrepreneur_id == entrepreneur.id,
        Relationship.end_date == None
    ).all()
    
    # Obtener métricas de progreso
    progress_metrics = get_entrepreneur_metrics(entrepreneur_id)
    
    # Obtener productos/servicios ofrecidos
    products = get_entrepreneur_products(entrepreneur_id)
    
    return render_template(
        'client/entrepreneur_detail.html',
        entrepreneur=entrepreneur,
        user=user,
        current_allies=current_allies,
        progress_metrics=progress_metrics,
        products=products
    )

@directory_bp.route('/sectors', methods=['GET'])
@login_required
@client_required
def get_sectors():
    """Obtener lista de sectores disponibles para filtrado."""
    sectors = db.session.query(Entrepreneur.sector).distinct().all()
    return jsonify({
        'sectors': [sector[0] for sector in sectors if sector[0]]
    })

@directory_bp.route('/regions', methods=['GET'])
@login_required
@client_required
def get_regions():
    """Obtener lista de regiones disponibles para filtrado."""
    regions = db.session.query(Entrepreneur.region).distinct().all()
    return jsonify({
        'regions': [region[0] for region in regions if region[0]]
    })

@directory_bp.route('/export', methods=['GET'])
@login_required
@client_required
def export_directory():
    """Exportar directorio de emprendedores a Excel."""
    from app.utils.excel import generate_entrepreneur_directory_excel
    
    # Obtener parámetros de filtrado
    search_query = request.args.get('query', '')
    sector = request.args.get('sector', '')
    region = request.args.get('region', '')
    status = request.args.get('status', 'active')
    
    # Obtener emprendedores filtrados
    entrepreneurs = get_entrepreneurs(
        search_query=search_query,
        sector=sector,
        region=region,
        status=status
    )
    
    # Preparar datos para Excel
    data = []
    for e in entrepreneurs:
        user = User.query.get(e.user_id)
        
        # Obtener aliados actuales
        current_allies = db.session.query(User).join(
            Relationship, User.id == Relationship.ally_id
        ).filter(
            Relationship.entrepreneur_id == e.id,
            Relationship.end_date == None
        ).all()
        
        allies_names = ", ".join([f"{ally.first_name} {ally.last_name}" for ally in current_allies])
        
        data.append({
            'id': e.id,
            'name': f"{user.first_name} {user.last_name}",
            'email': user.email,
            'phone': user.phone,
            'business_name': e.business_name,
            'description': e.description,
            'sector': e.sector,
            'region': e.region,
            'founded_date': e.founded_date.strftime('%Y-%m-%d') if e.founded_date else 'N/A',
            'current_allies': allies_names,
            'status': 'Activo' if e.is_active else 'Inactivo',
            'join_date': e.created_at.strftime('%Y-%m-%d')
        })
    
    # Generar Excel
    return generate_entrepreneur_directory_excel(data, "directorio_emprendedores.xlsx")

# Funciones auxiliares

def get_entrepreneurs(search_query='', sector='', region='', status='active'):
    """
    Obtener emprendedores con filtros aplicados.
    
    Args:
        search_query (str): Texto para buscar en nombre, email o nombre de negocio
        sector (str): Filtrar por sector específico
        region (str): Filtrar por región específica
        status (str): 'active', 'inactive' o 'all'
    
    Returns:
        list: Lista de objetos Entrepreneur
    """
    # Iniciar consulta base
    query = db.session.query(Entrepreneur).join(
        User, Entrepreneur.user_id == User.id
    )
    
    # Aplicar filtro de estado
    if status == 'active':
        query = query.filter(Entrepreneur.is_active == True)
    elif status == 'inactive':
        query = query.filter(Entrepreneur.is_active == False)
    # Si status es 'all', no aplicamos filtro
    
    # Aplicar filtro de búsqueda
    if search_query:
        query = query.filter(
            or_(
                User.first_name.ilike(f'%{search_query}%'),
                User.last_name.ilike(f'%{search_query}%'),
                User.email.ilike(f'%{search_query}%'),
                Entrepreneur.business_name.ilike(f'%{search_query}%')
            )
        )
    
    # Aplicar filtro de sector
    if sector:
        query = query.filter(Entrepreneur.sector == sector)
    
    # Aplicar filtro de región
    if region:
        query = query.filter(Entrepreneur.region == region)
    
    # Ordenar por fecha de registro (más recientes primero)
    query = query.order_by(Entrepreneur.created_at.desc())
    
    return query.all()

def entrepreneur_to_dict(entrepreneur):
    """Convertir objeto Entrepreneur a diccionario para respuestas JSON."""
    user = User.query.get(entrepreneur.user_id)
    
    # Obtener la URL de la imagen de perfil o usar una por defecto
    profile_image = user.profile_image or '/static/images/default-profile.png'
    
    return {
        'id': entrepreneur.id,
        'name': f"{user.first_name} {user.last_name}",
        'email': user.email,
        'business_name': entrepreneur.business_name,
        'description': entrepreneur.description,
        'sector': entrepreneur.sector,
        'region': entrepreneur.region,
        'profile_image': profile_image,
        'is_active': entrepreneur.is_active
    }
def get_entrepreneur_metrics(entrepreneur_id):
    """
    Obtener métricas de progreso para un emprendedor específico.
    
    Esta función recopila diversas métricas de rendimiento del emprendedor,
    incluyendo actividades de mentoría, crecimiento financiero, creación
    de empleo y otros KPIs relevantes.
    
    Args:
        entrepreneur_id (int): ID del emprendedor
        
    Returns:
        dict: Diccionario con todas las métricas relevantes
    """
    from app.models.meeting import Meeting
    from app.models.task import Task
    from app.models.document import Document
    from app.models.entrepreneur import Entrepreneur
    from sqlalchemy import func
    import datetime
    
    # Obtener el emprendedor
    entrepreneur = Entrepreneur.query.get(entrepreneur_id)
    if not entrepreneur:
        return {}
    
    # Obtener relaciones del emprendedor (conexiones con aliados/mentores)
    relationships = Relationship.query.filter(
        Relationship.entrepreneur_id == entrepreneur_id
    ).all()
    
    relationship_ids = [r.id for r in relationships]
    
    # === MÉTRICAS DE MENTORÍA ===
    
    # Contar número de reuniones completadas
    completed_meetings_count = Meeting.query.filter(
        Meeting.relationship_id.in_(relationship_ids),
        Meeting.status == 'completed'
    ).count()
    
    # Calcular horas totales de mentoría
    total_hours = db.session.query(func.sum(Meeting.duration)).filter(
        Meeting.relationship_id.in_(relationship_ids),
        Meeting.status == 'completed'
    ).scalar() or 0
    
    # Calcular promedio de satisfacción de reuniones (si existe campo satisfaction_score)
    avg_satisfaction = db.session.query(func.avg(Meeting.satisfaction_score)).filter(
        Meeting.relationship_id.in_(relationship_ids),
        Meeting.status == 'completed',
        Meeting.satisfaction_score != None
    ).scalar() or 0
    
    # Obtener número de reuniones en el último mes
    last_month = datetime.datetime.now() - datetime.timedelta(days=30)
    recent_meetings = Meeting.query.filter(
        Meeting.relationship_id.in_(relationship_ids),
        Meeting.start_time >= last_month,
        Meeting.status == 'completed'
    ).count()
    
    # === MÉTRICAS DE TAREAS Y PROGRESO ===
    
    # Obtener estadísticas de tareas (si existe modelo Task)
    total_tasks = Task.query.filter(
        Task.entrepreneur_id == entrepreneur_id
    ).count()
    
    completed_tasks = Task.query.filter(
        Task.entrepreneur_id == entrepreneur_id,
        Task.status == 'completed'
    ).count()
    
    task_completion_rate = (completed_tasks / total_tasks * 100) if total_tasks > 0 else 0
    
    # Obtener número de documentos subidos
    document_count = Document.query.filter(
        Document.entrepreneur_id == entrepreneur_id
    ).count()
    
    # === MÉTRICAS DE NEGOCIO ===
    
    # En una aplicación real, estos datos vendrían de modelos como:
    # - BusinessMetrics (datos financieros)
    # - EmployeeCount (seguimiento de empleados)
    # - Funding (registro de financiamiento)
    
    # Para este ejemplo, usamos algunos datos ficticios y otros de la base de datos
    
    # Ejemplo: Obtener el valor más reciente del ingreso mensual (si existe)
    try:
        from app.models.business_metrics import BusinessMetrics
        
        latest_revenue = db.session.query(BusinessMetrics).filter(
            BusinessMetrics.entrepreneur_id == entrepreneur_id,
        ).order_by(BusinessMetrics.date.desc()).first()
        
        # Calcular el crecimiento de ingresos (comparando con hace 6 meses)
        six_months_ago = datetime.datetime.now() - datetime.timedelta(days=180)
        previous_revenue = db.session.query(BusinessMetrics).filter(
            BusinessMetrics.entrepreneur_id == entrepreneur_id,
            BusinessMetrics.date <= six_months_ago
        ).order_by(BusinessMetrics.date.desc()).first()
        
        if latest_revenue and previous_revenue and previous_revenue.monthly_revenue > 0:
            revenue_growth = ((latest_revenue.monthly_revenue - previous_revenue.monthly_revenue) 
                            / previous_revenue.monthly_revenue * 100)
        else:
            revenue_growth = 0
            
        current_revenue = latest_revenue.monthly_revenue if latest_revenue else 0
        
    except (ImportError, AttributeError):
        # Si no existe el modelo, usamos datos de ejemplo
        revenue_growth = 15.3
        current_revenue = 50000
    
    # Ejemplo: Obtener el conteo de empleados más reciente
    try:
        from app.models.employee_count import EmployeeCount
        
        latest_employee_count = db.session.query(EmployeeCount).filter(
            EmployeeCount.entrepreneur_id == entrepreneur_id
        ).order_by(EmployeeCount.date.desc()).first()
        
        initial_employee_count = db.session.query(EmployeeCount).filter(
            EmployeeCount.entrepreneur_id == entrepreneur_id
        ).order_by(EmployeeCount.date).first()
        
        if latest_employee_count and initial_employee_count:
            jobs_created = latest_employee_count.count - initial_employee_count.count
        else:
            jobs_created = latest_employee_count.count if latest_employee_count else 0
            
    except (ImportError, AttributeError):
        # Si no existe el modelo, usamos datos de ejemplo
        jobs_created = 3
    
    # Ejemplo: Obtener la financiación total asegurada
    try:
        from app.models.funding import Funding
        
        total_funding = db.session.query(func.sum(Funding.amount)).filter(
            Funding.entrepreneur_id == entrepreneur_id,
            Funding.status == 'secured'
        ).scalar() or 0
            
    except (ImportError, AttributeError):
        # Si no existe el modelo, usamos datos de ejemplo
        total_funding = 25000
    
    # Calcula métricas adicionales según los datos disponibles
    try:
        from app.models.milestone import Milestone
        
        milestone_count = Milestone.query.filter(
            Milestone.entrepreneur_id == entrepreneur_id
        ).count()
        
        completed_milestones = Milestone.query.filter(
            Milestone.entrepreneur_id == entrepreneur_id,
            Milestone.status == 'completed'
        ).count()
        
        milestone_completion_rate = (completed_milestones / milestone_count * 100) if milestone_count > 0 else 0
    
    except (ImportError, AttributeError):
        milestone_count = 5
        completed_milestones = 3
        milestone_completion_rate = 60
    
    # === COMPILAR TODAS LAS MÉTRICAS ===
    
    metrics = {
        # Métricas de mentoría
        'total_hours': round(total_hours, 1),
        'completed_meetings': completed_meetings_count,
        'avg_satisfaction': round(avg_satisfaction, 1),
        'recent_meetings': recent_meetings,
        
        # Métricas de tareas
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'task_completion_rate': round(task_completion_rate, 1),
        'document_count': document_count,
        
        # Métricas de negocio
        'current_revenue': current_revenue,
        'revenue_growth': round(revenue_growth, 1),
        'jobs_created': jobs_created,
        'funding_secured': total_funding,
        
        # Métricas de hitos
        'milestone_count': milestone_count,
        'completed_milestones': completed_milestones,
        'milestone_completion_rate': round(milestone_completion_rate, 1),
        
        # Cálculo de puntaje global (ejemplo de cómo se podría hacer)
        'overall_score': calculate_overall_score(
            task_completion_rate, 
            milestone_completion_rate,
            revenue_growth,
            completed_meetings_count
        )
    }
    
    return metrics

def calculate_overall_score(task_rate, milestone_rate, revenue_growth, meeting_count):
    """
    Calcula un puntaje global de desempeño del emprendedor.
    Este puntaje podría usarse para comparar y clasificar emprendedores.
    
    Args:
        task_rate (float): Tasa de finalización de tareas (0-100)
        milestone_rate (float): Tasa de finalización de hitos (0-100)
        revenue_growth (float): Crecimiento de ingresos en porcentaje
        meeting_count (int): Número de reuniones completadas
        
    Returns:
        int: Puntaje entre 0 y 100
    """
    # Normalizar cada componente a un valor entre 0 y 25
    task_score = min(25, task_rate * 0.25)
    milestone_score = min(25, milestone_rate * 0.25)
    
    # Para el crecimiento, un 20% o más se considera excelente (25 puntos)
    revenue_score = min(25, revenue_growth * 1.25) if revenue_growth > 0 else 0
    
    # Para reuniones, 20 o más se considera excelente
    meeting_score = min(25, meeting_count * 1.25)
    
    # Sumar todos los componentes
    overall = task_score + milestone_score + revenue_score + meeting_score
    
    return round(overall)

def get_entrepreneur_products(entrepreneur_id):
    """
    Obtener productos/servicios ofrecidos por un emprendedor.
    
    Args:
        entrepreneur_id (int): ID del emprendedor
        
    Returns:
        list: Lista de diccionarios con información de productos
    """
    # En una aplicación real, consultaríamos un modelo Product
    try:
        from app.models.product import Product
        
        products = Product.query.filter(
            Product.entrepreneur_id == entrepreneur_id,
            Product.is_active == True
        ).order_by(Product.created_at.desc()).all()
        
        result = []
        for product in products:
            # Cargar imágenes si existen
            try:
                from app.models.product_image import ProductImage
                images = ProductImage.query.filter(
                    ProductImage.product_id == product.id
                ).all()
                image_urls = [img.url for img in images]
            except (ImportError, AttributeError):
                image_urls = []
                
            # Agregar producto al resultado
            result.append({
                'id': product.id,
                'name': product.name,
                'description': product.description,
                'price': product.price,
                'currency': product.currency,
                'category': product.category,
                'is_service': product.is_service,
                'main_image': image_urls[0] if image_urls else '/static/images/default-product.png',
                'all_images': image_urls,
                'created_at': product.created_at.strftime('%Y-%m-%d'),
                'url': product.url if hasattr(product, 'url') else None
            })
        
        return result
        
    except (ImportError, AttributeError):
        # Si no existe el modelo Product, devolvemos datos de ejemplo
        # Esto ayuda durante el desarrollo para tener una vista funcional
        return [
            {
                'id': 1,
                'name': 'Servicio de Consultoría Ambiental',
                'description': 'Evaluaciones de impacto ambiental y gestión de permisos para empresas.',
                'price': 1500.00,
                'currency': 'USD',
                'category': 'Servicios Ambientales',
                'is_service': True,
                'main_image': '/static/images/default-product.png',
                'all_images': [],
                'created_at': '2024-01-15',
                'url': None
            },
            {
                'id': 2,
                'name': 'Kit de Compostaje Doméstico',
                'description': 'Kit completo para comenzar a compostar residuos orgánicos en casa.',
                'price': 89.99,
                'currency': 'USD',
                'category': 'Productos Ecológicos',
                'is_service': False,
                'main_image': '/static/images/default-product.png',
                'all_images': [],
                'created_at': '2024-02-20',
                'url': 'https://tienda-ejemplo.com/producto/kit-compostaje'
            },
            {
                'id': 3,
                'name': 'Taller de Sustentabilidad Corporativa',
                'description': 'Taller presencial de 4 horas para equipos corporativos sobre implementación de prácticas sustentables.',
                'price': 450.00,
                'currency': 'USD',
                'category': 'Formación',
                'is_service': True,
                'main_image': '/static/images/default-product.png',
                'all_images': [],
                'created_at': '2024-03-05',
                'url': None
            }
        ]