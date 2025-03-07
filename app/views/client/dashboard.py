# app/views/client/dashboard.py

from flask import render_template, current_app, request, jsonify
from flask_login import login_required, current_user

from app.models.entrepreneur import Entrepreneur
from app.models.relationship import Relationship
from app.utils.decorators import client_required
from app.views.client import client  # Importa el blueprint 'client'

@client.route('/dashboard')
@login_required
@client_required
def dashboard():
    """
    Vista principal del dashboard para clientes.
    Muestra un resumen de los datos relevantes para el cliente.
    """
    # Obtener estadísticas globales
    total_entrepreneurs = Entrepreneur.query.filter_by(client_id=current_user.client.id).count()
    active_entrepreneurs = Entrepreneur.query.filter_by(
        client_id=current_user.client.id, 
        status='active'
    ).count()
    
    # Obtener relaciones activas entre emprendedores y aliados
    active_relationships = Relationship.query.join(
        Entrepreneur, Relationship.entrepreneur_id == Entrepreneur.id
    ).filter(
        Entrepreneur.client_id == current_user.client.id,
        Relationship.status == 'active'
    ).count()
    
    # Métricas adicionales que podrían ser relevantes para el cliente
    # Estos podrían ser cálculos más complejos en una aplicación real
    completion_rate = calculate_completion_rate(current_user.client.id)
    recent_activity = get_recent_activity(current_user.client.id, limit=5)
    growth_metrics = get_growth_metrics(current_user.client.id)
    
    return render_template(
        'client/dashboard.html',
        total_entrepreneurs=total_entrepreneurs,
        active_entrepreneurs=active_entrepreneurs,
        active_relationships=active_relationships,
        completion_rate=completion_rate,
        recent_activity=recent_activity,
        growth_metrics=growth_metrics
    )

@client.route('/dashboard/metrics')
@login_required
@client_required
def dashboard_metrics():
    """
    Endpoint para obtener métricas adicionales via AJAX.
    Permite actualizar partes del dashboard dinámicamente.
    """
    metric_type = request.args.get('type', 'general')
    time_period = request.args.get('period', 'month')
    
    if metric_type == 'general':
        data = get_general_metrics(current_user.client.id, time_period)
    elif metric_type == 'entrepreneurs':
        data = get_entrepreneur_metrics(current_user.client.id, time_period)
    elif metric_type == 'allies':
        data = get_ally_metrics(current_user.client.id, time_period)
    else:
        data = {}
    
    return jsonify(data)

# Funciones auxiliares para calcular métricas
def calculate_completion_rate(client_id):
    """Calcula la tasa de completitud de tareas para los emprendedores del cliente."""
    from app.models.task import Task
    from app.models.entrepreneur import Entrepreneur
    
    # Obtener todos los emprendedores asociados al cliente
    entrepreneurs = Entrepreneur.query.filter_by(client_id=client_id).all()
    
    if not entrepreneurs:
        return 0
    
    entrepreneur_ids = [e.id for e in entrepreneurs]
    
    # Contar tareas completadas y totales
    total_tasks = Task.query.filter(Task.entrepreneur_id.in_(entrepreneur_ids)).count()
    
    if total_tasks == 0:
        return 0
        
    completed_tasks = Task.query.filter(
        Task.entrepreneur_id.in_(entrepreneur_ids),
        Task.status == 'completed'
    ).count()
    
    # Calcular porcentaje de completitud
    completion_rate = (completed_tasks / total_tasks) * 100
    return round(completion_rate, 1)


def get_recent_activity(client_id, limit=5):
    """Obtiene las actividades recientes relevantes para el cliente."""
    from app.models.entrepreneur import Entrepreneur
    from app.models.meeting import Meeting
    from app.models.document import Document
    from app.models.relationship import Relationship
    from app.models.ally import Ally
    from datetime import datetime, timedelta
    from sqlalchemy import desc
    
    # Período de tiempo a considerar (últimos 30 días)
    start_date = datetime.now() - timedelta(days=30)
    
    # Obtener emprendedores del cliente
    entrepreneur_ids = [e.id for e in Entrepreneur.query.filter_by(client_id=client_id).all()]
    
    activities = []
    
    # Nuevos emprendedores
    new_entrepreneurs = Entrepreneur.query.filter(
        Entrepreneur.client_id == client_id,
        Entrepreneur.created_at >= start_date
    ).order_by(desc(Entrepreneur.created_at)).limit(limit).all()
    
    for entrepreneur in new_entrepreneurs:
        activities.append({
            'type': 'new_entrepreneur',
            'name': entrepreneur.company_name,
            'date': entrepreneur.created_at.strftime('%Y-%m-%d'),
            'description': f'Nuevo emprendimiento registrado: {entrepreneur.company_name}'
        })
    
    # Reuniones programadas
    upcoming_meetings = Meeting.query.filter(
        Meeting.entrepreneur_id.in_(entrepreneur_ids),
        Meeting.date >= datetime.now(),
        Meeting.date <= datetime.now() + timedelta(days=14)
    ).order_by(Meeting.date).limit(limit).all()
    
    for meeting in upcoming_meetings:
        entrepreneur = Entrepreneur.query.get(meeting.entrepreneur_id)
        activities.append({
            'type': 'meeting_scheduled',
            'name': meeting.title,
            'date': meeting.date.strftime('%Y-%m-%d'),
            'description': f'Reunión: {meeting.title} con {entrepreneur.company_name}'
        })
    
    # Documentos importantes subidos
    new_documents = Document.query.filter(
        Document.entrepreneur_id.in_(entrepreneur_ids),
        Document.created_at >= start_date,
        Document.type.in_(['contract', 'report', 'pitch'])
    ).order_by(desc(Document.created_at)).limit(limit).all()
    
    for document in new_documents:
        entrepreneur = Entrepreneur.query.get(document.entrepreneur_id)
        activities.append({
            'type': 'document_uploaded',
            'name': document.title,
            'date': document.created_at.strftime('%Y-%m-%d'),
            'description': f'Documento: {document.title} subido por {entrepreneur.company_name}'
        })
    
    # Nuevas asignaciones de aliados
    new_relationships = Relationship.query.filter(
        Relationship.entrepreneur_id.in_(entrepreneur_ids),
        Relationship.created_at >= start_date
    ).order_by(desc(Relationship.created_at)).limit(limit).all()
    
    for relationship in new_relationships:
        entrepreneur = Entrepreneur.query.get(relationship.entrepreneur_id)
        ally = Ally.query.get(relationship.ally_id)
        activities.append({
            'type': 'new_relationship',
            'name': f'{entrepreneur.company_name} - {ally.user.name}',
            'date': relationship.created_at.strftime('%Y-%m-%d'),
            'description': f'Nueva asignación: {ally.user.name} como mentor de {entrepreneur.company_name}'
        })
    
    # Ordenar por fecha (más reciente primero) y limitar al número solicitado
    activities.sort(key=lambda x: datetime.strptime(x['date'], '%Y-%m-%d'), reverse=True)
    return activities[:limit]


def get_growth_metrics(client_id):
    """Obtiene métricas de crecimiento para los emprendedores del cliente."""
    from app.models.entrepreneur import Entrepreneur
    from app.models.document import Document
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    # Considerar datos de los últimos 3 meses
    three_months_ago = datetime.now() - timedelta(days=90)
    six_months_ago = datetime.now() - timedelta(days=180)
    
    # Obtener emprendedores del cliente
    entrepreneurs = Entrepreneur.query.filter_by(client_id=client_id).all()
    entrepreneur_ids = [e.id for e in entrepreneurs]
    
    if not entrepreneurs:
        return {
            'revenue_growth': 0,
            'employee_growth': 0,
            'market_expansion': 0,
            'months_active': 0,
            'avg_support_hours': 0
        }
    
    # Calcular crecimiento de ingresos
    recent_revenue_docs = Document.query.filter(
        Document.entrepreneur_id.in_(entrepreneur_ids),
        Document.type == 'financial_report',
        Document.created_at >= three_months_ago
    ).order_by(Document.created_at.desc()).all()
    
    previous_revenue_docs = Document.query.filter(
        Document.entrepreneur_id.in_(entrepreneur_ids),
        Document.type == 'financial_report',
        Document.created_at >= six_months_ago,
        Document.created_at < three_months_ago
    ).order_by(Document.created_at.desc()).all()
    
    # Extraer datos financieros de los documentos (simplificado)
    # En un caso real, habría una estructura más compleja para almacenar estos datos
    recent_revenue = sum([doc.metadata.get('revenue', 0) for doc in recent_revenue_docs]) if recent_revenue_docs else 0
    previous_revenue = sum([doc.metadata.get('revenue', 0) for doc in previous_revenue_docs]) if previous_revenue_docs else 0
    
    revenue_growth = ((recent_revenue - previous_revenue) / previous_revenue * 100) if previous_revenue > 0 else 0
    
    # Calcular crecimiento de empleados
    recent_employees = sum([e.current_employees for e in entrepreneurs])
    previous_employees = sum([e.initial_employees for e in entrepreneurs])
    
    employee_growth = ((recent_employees - previous_employees) / previous_employees * 100) if previous_employees > 0 else 0
    
    # Calcular expansión de mercado (basado en nuevos mercados o regiones)
    # Ejemplo simplificado
    market_expansion = sum([len(e.metadata.get('new_markets', [])) for e in entrepreneurs if e.metadata])
    
    # Calcular promedio de meses activos
    months_active = sum([(datetime.now() - e.created_at).days // 30 for e in entrepreneurs]) / len(entrepreneurs)
    
    # Calcular promedio de horas de apoyo por aliado
    from app.models.relationship import Relationship
    
    total_hours = db.session.query(func.sum(Relationship.hours_logged)).filter(
        Relationship.entrepreneur_id.in_(entrepreneur_ids)
    ).scalar() or 0
    
    avg_support_hours = total_hours / len(entrepreneurs) if entrepreneurs else 0
    
    return {
        'revenue_growth': round(revenue_growth, 1),
        'employee_growth': round(employee_growth, 1),
        'market_expansion': market_expansion,
        'months_active': round(months_active, 1),
        'avg_support_hours': round(avg_support_hours, 1)
    }


def get_general_metrics(client_id, period):
    """Obtiene métricas generales según el período especificado."""
    from app.models.entrepreneur import Entrepreneur
    from app.models.relationship import Relationship
    from app.models.task import Task
    from sqlalchemy import func
    from datetime import datetime, timedelta
    
    periods = {
        'month': 30,
        'quarter': 90,
        'year': 365
    }
    days = periods.get(period, 30)
    
    # Generar etiquetas de fechas según el período
    labels = []
    datasets = []
    
    # Para período mensual: últimos 5 meses
    if period == 'month':
        # Generar etiquetas para los últimos 5 meses
        for i in range(4, -1, -1):
            month = datetime.now() - timedelta(days=i*30)
            labels.append(month.strftime('%b'))
        
        # Datos de emprendedores activos por mes
        active_data = []
        for i in range(4, -1, -1):
            end_date = datetime.now() - timedelta(days=i*30)
            start_date = end_date - timedelta(days=30)
            
            active_count = Entrepreneur.query.filter(
                Entrepreneur.client_id == client_id,
                Entrepreneur.status == 'active',
                Entrepreneur.created_at <= end_date
            ).count()
            
            active_data.append(active_count)
        
        datasets.append({
            'label': 'Emprendedores Activos',
            'data': active_data,
            'backgroundColor': 'rgba(54, 162, 235, 0.2)',
            'borderColor': 'rgba(54, 162, 235, 1)',
            'borderWidth': 1
        })
        
        # Datos de tareas completadas por mes
        entrepreneur_ids = [e.id for e in Entrepreneur.query.filter_by(client_id=client_id).all()]
        
        task_data = []
        for i in range(4, -1, -1):
            end_date = datetime.now() - timedelta(days=i*30)
            start_date = end_date - timedelta(days=30)
            
            task_count = Task.query.filter(
                Task.entrepreneur_id.in_(entrepreneur_ids),
                Task.status == 'completed',
                Task.completed_at >= start_date,
                Task.completed_at <= end_date
            ).count()
            
            task_data.append(task_count)
        
        datasets.append({
            'label': 'Tareas Completadas',
            'data': task_data,
            'backgroundColor': 'rgba(75, 192, 192, 0.2)',
            'borderColor': 'rgba(75, 192, 192, 1)',
            'borderWidth': 1
        })
    
    # Para período trimestral: últimos 4 trimestres
    elif period == 'quarter':
        for i in range(3, -1, -1):
            quarter = datetime.now() - timedelta(days=i*90)
            labels.append(f'Q{(quarter.month-1)//3+1} {quarter.year}')
        
        # Implementación similar a la mensual, pero con intervalos trimestrales
        # (código omitido por brevedad)
    
    # Para período anual: últimos 5 años
    elif period == 'year':
        for i in range(4, -1, -1):
            year = datetime.now().year - i
            labels.append(str(year))
        
        # Implementación similar a la mensual, pero con intervalos anuales
        # (código omitido por brevedad)
    
    return {
        'labels': labels,
        'datasets': datasets
    }


def get_entrepreneur_metrics(client_id, period):
    """Obtiene métricas específicas de emprendedores."""
    from app.models.entrepreneur import Entrepreneur
    from sqlalchemy import func
    
    # Distribución por categoría
    category_distribution = db.session.query(
        Entrepreneur.category, func.count(Entrepreneur.id)
    ).filter(
        Entrepreneur.client_id == client_id
    ).group_by(Entrepreneur.category).all()
    
    category_labels = [cat[0] for cat in category_distribution]
    category_data = [cat[1] for cat in category_distribution]
    
    # Distribución por etapa de desarrollo
    stage_distribution = db.session.query(
        Entrepreneur.stage, func.count(Entrepreneur.id)
    ).filter(
        Entrepreneur.client_id == client_id
    ).group_by(Entrepreneur.stage).all()
    
    stage_labels = [stage[0] for stage in stage_distribution]
    stage_data = [stage[1] for stage in stage_distribution]
    
    # Distribución por ubicación geográfica
    location_distribution = db.session.query(
        Entrepreneur.location, func.count(Entrepreneur.id)
    ).filter(
        Entrepreneur.client_id == client_id
    ).group_by(Entrepreneur.location).all()
    
    location_labels = [loc[0] for loc in location_distribution]
    location_data = [loc[1] for loc in location_distribution]
    
    return {
        'categoryDistribution': {
            'labels': category_labels,
            'datasets': [{
                'label': 'Distribución por Categoría',
                'data': category_data,
                'backgroundColor': [
                    'rgba(255, 99, 132, 0.2)',
                    'rgba(54, 162, 235, 0.2)',
                    'rgba(255, 206, 86, 0.2)',
                    'rgba(75, 192, 192, 0.2)',
                    'rgba(153, 102, 255, 0.2)'
                ],
                'borderColor': [
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(75, 192, 192, 1)',
                    'rgba(153, 102, 255, 1)'
                ],
                'borderWidth': 1
            }]
        },
        'stageDistribution': {
            'labels': stage_labels,
            'datasets': [{
                'label': 'Distribución por Etapa',
                'data': stage_data,
                'backgroundColor': [
                    'rgba(255, 159, 64, 0.2)',
                    'rgba(255, 99, 132, 0.2)',
                    'rgba(54, 162, 235, 0.2)',
                    'rgba(75, 192, 192, 0.2)'
                ],
                'borderColor': [
                    'rgba(255, 159, 64, 1)',
                    'rgba(255, 99, 132, 1)',
                    'rgba(54, 162, 235, 1)',
                    'rgba(75, 192, 192, 1)'
                ],
                'borderWidth': 1
            }]
        },
        'locationDistribution': {
            'labels': location_labels,
            'datasets': [{
                'label': 'Distribución por Ubicación',
                'data': location_data,
                'backgroundColor': 'rgba(54, 162, 235, 0.2)',
                'borderColor': 'rgba(54, 162, 235, 1)',
                'borderWidth': 1
            }]
        }
    }


def get_ally_metrics(client_id, period):
    """Obtiene métricas específicas de aliados."""
    from app.models.ally import Ally
    from app.models.relationship import Relationship
    from app.models.entrepreneur import Entrepreneur
    from app.models.meeting import Meeting
    from sqlalchemy import func, desc
    from datetime import datetime, timedelta
    
    # Obtener emprendedores del cliente
    entrepreneur_ids = [e.id for e in Entrepreneur.query.filter_by(client_id=client_id).all()]
    
    # Obtener relaciones entre aliados y emprendedores
    relationships = Relationship.query.filter(
        Relationship.entrepreneur_id.in_(entrepreneur_ids)
    ).all()
    
    ally_ids = [r.ally_id for r in relationships]
    
    # Si no hay aliados asociados, devolver datos vacíos
    if not ally_ids:
        return {
            'effectivenessDistribution': {
                'labels': ['Sin datos'],
                'datasets': [{
                    'label': 'Efectividad de Aliados',
                    'data': [0],
                    'backgroundColor': 'rgba(200, 200, 200, 0.2)',
                    'borderColor': 'rgba(200, 200, 200, 1)',
                    'borderWidth': 1
                }]
            },
            'topAllies': {
                'labels': [],
                'datasets': [{
                    'label': 'Horas de Mentoría',
                    'data': [],
                    'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                    'borderColor': 'rgba(75, 192, 192, 1)',
                    'borderWidth': 1
                }]
            },
            'mentorshipHours': {
                'labels': [],
                'datasets': [{
                    'label': 'Horas por Mes',
                    'data': [],
                    'backgroundColor': 'rgba(153, 102, 255, 0.2)',
                    'borderColor': 'rgba(153, 102, 255, 1)',
                    'borderWidth': 1
                }]
            }
        }
    
    # Clasificación de efectividad basada en horas registradas y tareas completadas
    ally_effectiveness = {}
    
    for relationship in relationships:
        if relationship.ally_id not in ally_effectiveness:
            # Calcular métricas para este aliado
            from app.models.task import Task
            
            # Tareas completadas para emprendedores asociados a este aliado
            tasks_completed = Task.query.filter(
                Task.entrepreneur_id == relationship.entrepreneur_id,
                Task.status == 'completed',
                Task.assigned_by_id == relationship.ally_id
            ).count()
            
            # Horas de mentoría registradas
            mentorship_hours = relationship.hours_logged or 0
            
            # Reuniones realizadas
            meetings_held = Meeting.query.filter(
                Meeting.entrepreneur_id == relationship.entrepreneur_id,
                Meeting.ally_id == relationship.ally_id,
                Meeting.status == 'completed'
            ).count()
            
            # Calcular puntuación ponderada de efectividad
            effectiveness_score = (tasks_completed * 10) + (mentorship_hours * 5) + (meetings_held * 15)
            
            # Clasificar efectividad
            if effectiveness_score >= 200:
                category = 'Alta'
            elif effectiveness_score >= 100:
                category = 'Media'
            else:
                category = 'Baja'
            
            ally = Ally.query.get(relationship.ally_id)
            ally_name = ally.user.name if ally and ally.user else f"Aliado #{relationship.ally_id}"
            
            ally_effectiveness[relationship.ally_id] = {
                'id': relationship.ally_id,
                'name': ally_name,
                'category': category,
                'score': effectiveness_score,
                'hours': mentorship_hours,
                'tasks': tasks_completed,
                'meetings': meetings_held
            }
        else:
            # Sumar horas para este aliado si tiene múltiples relaciones
            ally_effectiveness[relationship.ally_id]['hours'] += relationship.hours_logged or 0
    
    # Distribución de efectividad
    categories = {'Alta': 0, 'Media': 0, 'Baja': 0}
    for ally_id, data in ally_effectiveness.items():
        categories[data['category']] += 1
    
    # Top aliados por horas de mentoría
    top_allies = sorted(ally_effectiveness.values(), key=lambda x: x['hours'], reverse=True)[:5]
    
    # Horas de mentoría por mes (últimos 6 meses)
    mentorship_by_month = []
    for i in range(5, -1, -1):
        end_date = datetime.now() - timedelta(days=i*30)
        start_date = end_date - timedelta(days=30)
        month_label = end_date.strftime('%b')
        
        hours = db.session.query(func.sum(Relationship.hours_logged)).filter(
            Relationship.entrepreneur_id.in_(entrepreneur_ids),
            Relationship.updated_at >= start_date,
            Relationship.updated_at < end_date
        ).scalar() or 0
        
        mentorship_by_month.append({
            'month': month_label,
            'hours': float(hours)
        })
    
    return {
        'effectivenessDistribution': {
            'labels': list(categories.keys()),
            'datasets': [{
                'label': 'Efectividad de Aliados',
                'data': list(categories.values()),
                'backgroundColor': [
                    'rgba(75, 192, 192, 0.2)',
                    'rgba(255, 206, 86, 0.2)',
                    'rgba(255, 99, 132, 0.2)'
                ],
                'borderColor': [
                    'rgba(75, 192, 192, 1)',
                    'rgba(255, 206, 86, 1)',
                    'rgba(255, 99, 132, 1)'
                ],
                'borderWidth': 1
            }]
        },
        'topAllies': {
            'labels': [ally['name'] for ally in top_allies],
            'datasets': [{
                'label': 'Horas de Mentoría',
                'data': [ally['hours'] for ally in top_allies],
                'backgroundColor': 'rgba(75, 192, 192, 0.2)',
                'borderColor': 'rgba(75, 192, 192, 1)',
                'borderWidth': 1
            }]
        },
        'mentorshipHours': {
            'labels': [item['month'] for item in mentorship_by_month],
            'datasets': [{
                'label': 'Horas por Mes',
                'data': [item['hours'] for item in mentorship_by_month],
                'backgroundColor': 'rgba(153, 102, 255, 0.2)',
                'borderColor': 'rgba(153, 102, 255, 1)',
                'borderWidth': 1
            }]
        }
    }