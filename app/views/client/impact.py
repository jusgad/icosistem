from flask import Blueprint, render_template, request, jsonify, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models.entrepreneur import Entrepreneur
from app.models.relationship import Relationship
from app.models.user import User
from app.models.ally import Ally
from app.utils.decorators import client_required
from app.forms.client import FilterForm
from datetime import datetime, timedelta
import json

# Creación del blueprint para el dashboard de impacto del cliente
impact_bp = Blueprint('client_impact', __name__, url_prefix='/client/impact')

@impact_bp.route('/', methods=['GET'])
@login_required
@client_required
def impact_dashboard():
    """Vista principal del dashboard de impacto para clientes."""
    # Formulario para filtrado de datos
    filter_form = FilterForm()
    
    # Por defecto mostrar datos de los últimos 6 meses
    end_date = datetime.now()
    start_date = end_date - timedelta(days=180)
    
    # Obtener estadísticas básicas
    stats = get_basic_stats(start_date, end_date)
    
    return render_template(
        'client/impact_dashboard.html',
        stats=stats,
        filter_form=filter_form
    )

@impact_bp.route('/data', methods=['GET'])
@login_required
@client_required
def impact_data():
    """Endpoint para obtener datos de impacto filtrados."""
    # Obtener parámetros de filtrado
    start_date = request.args.get('start_date', None)
    end_date = request.args.get('end_date', None)
    
    # Convertir fechas si fueron proporcionadas
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start_date = datetime.now() - timedelta(days=180)
        
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    # Obtener datos específicos para los gráficos
    data = {
        'basic_stats': get_basic_stats(start_date, end_date),
        'entrepreneurs_growth': get_entrepreneurs_growth(start_date, end_date),
        'hours_by_month': get_hours_by_month(start_date, end_date),
        'sector_distribution': get_sector_distribution(),
        'gender_distribution': get_gender_distribution(),
        'regional_impact': get_regional_impact(),
        'satisfaction_scores': get_satisfaction_scores(start_date, end_date)
    }
    
    return jsonify(data)

@impact_bp.route('/export', methods=['GET'])
@login_required
@client_required
def export_impact_report():
    """Exportar datos de impacto a Excel."""
    from app.utils.excel import generate_impact_excel
    
    # Obtener parámetros de filtrado
    start_date = request.args.get('start_date', None)
    end_date = request.args.get('end_date', None)
    
    # Convertir fechas si fueron proporcionadas
    if start_date:
        start_date = datetime.strptime(start_date, '%Y-%m-%d')
    else:
        start_date = datetime.now() - timedelta(days=180)
        
    if end_date:
        end_date = datetime.strptime(end_date, '%Y-%m-%d')
    else:
        end_date = datetime.now()
    
    # Obtener datos para el reporte
    data = {
        'basic_stats': get_basic_stats(start_date, end_date),
        'entrepreneurs_details': get_entrepreneurs_details(start_date, end_date),
        'hours_details': get_hours_details(start_date, end_date)
    }
    
    # Generar archivo Excel y devolverlo como respuesta
    return generate_impact_excel(data, f"impact_report_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.xlsx")

# Funciones auxiliares para obtener datos

def get_basic_stats(start_date, end_date):
    """Obtener estadísticas básicas de impacto."""
    # Total de emprendedores en el sistema
    total_entrepreneurs = Entrepreneur.query.count()
    
    # Emprendedores activos en el periodo
    active_entrepreneurs = Entrepreneur.query.filter(
        Entrepreneur.created_at <= end_date,
        Entrepreneur.is_active == True
    ).count()
    
    # Nuevos emprendedores en el periodo
    new_entrepreneurs = Entrepreneur.query.filter(
        Entrepreneur.created_at >= start_date,
        Entrepreneur.created_at <= end_date
    ).count()
    
    # Total de horas de mentoría en el periodo
    from app.models.meeting import Meeting
    total_hours = db.session.query(db.func.sum(Meeting.duration)).filter(
        Meeting.start_time >= start_date,
        Meeting.end_time <= end_date,
        Meeting.status == 'completed'
    ).scalar() or 0
    
    # Total de aliados activos
    active_allies = Ally.query.filter(
        Ally.is_active == True
    ).count()
    
    # Número de relaciones activas
    active_relationships = Relationship.query.filter(
        Relationship.start_date <= end_date,
        (Relationship.end_date >= start_date) | (Relationship.end_date == None)
    ).count()
    
    return {
        'total_entrepreneurs': total_entrepreneurs,
        'active_entrepreneurs': active_entrepreneurs,
        'new_entrepreneurs': new_entrepreneurs,
        'total_hours': total_hours,
        'active_allies': active_allies,
        'active_relationships': active_relationships,
        'avg_hours_per_entrepreneur': round(total_hours / active_entrepreneurs, 2) if active_entrepreneurs > 0 else 0
    }

def get_entrepreneurs_growth(start_date, end_date):
    """Obtener datos de crecimiento mensual de emprendedores."""
    # Calcular el número de meses en el rango
    months_diff = (end_date.year - start_date.year) * 12 + end_date.month - start_date.month
    
    data = []
    current_date = start_date
    
    for i in range(months_diff + 1):
        month_end = datetime(current_date.year, current_date.month, 1) + timedelta(days=32)
        month_end = datetime(month_end.year, month_end.month, 1) - timedelta(days=1)
        
        # Contar nuevos emprendedores en este mes
        new_count = Entrepreneur.query.filter(
            Entrepreneur.created_at >= datetime(current_date.year, current_date.month, 1),
            Entrepreneur.created_at <= month_end
        ).count()
        
        # Contar emprendedores acumulados hasta este mes
        total_count = Entrepreneur.query.filter(
            Entrepreneur.created_at <= month_end
        ).count()
        
        data.append({
            'month': current_date.strftime('%b %Y'),
            'new': new_count,
            'total': total_count
        })
        
        # Avanzar al siguiente mes
        if current_date.month == 12:
            current_date = datetime(current_date.year + 1, 1, 1)
        else:
            current_date = datetime(current_date.year, current_date.month + 1, 1)
    
    return data

def get_hours_by_month(start_date, end_date):
    """Obtener horas de mentoría por mes."""
    from app.models.meeting import Meeting
    from sqlalchemy import func, extract
    
    # Consulta para agrupar horas por mes
    results = db.session.query(
        extract('year', Meeting.start_time).label('year'),
        extract('month', Meeting.start_time).label('month'),
        func.sum(Meeting.duration).label('total_hours')
    ).filter(
        Meeting.start_time >= start_date,
        Meeting.end_time <= end_date,
        Meeting.status == 'completed'
    ).group_by(
        extract('year', Meeting.start_time),
        extract('month', Meeting.start_time)
    ).order_by(
        extract('year', Meeting.start_time),
        extract('month', Meeting.start_time)
    ).all()
    
    # Convertir resultados a formato esperado por el frontend
    data = []
    for result in results:
        month_date = datetime(int(result.year), int(result.month), 1)
        data.append({
            'month': month_date.strftime('%b %Y'),
            'hours': float(result.total_hours)
        })
    
    return data

def get_sector_distribution():
    """Obtener distribución de emprendedores por sector."""
    # Suponiendo que los emprendedores tienen un campo 'sector'
    from sqlalchemy import func
    
    results = db.session.query(
        Entrepreneur.sector,
        func.count(Entrepreneur.id).label('count')
    ).group_by(
        Entrepreneur.sector
    ).all()
    
    data = [{'sector': r.sector, 'count': r.count} for r in results]
    return data

def get_gender_distribution():
    """Obtener distribución de emprendedores por género."""
    # Suponiendo que el modelo de usuario tiene un campo 'gender'
    from sqlalchemy import func
    
    results = db.session.query(
        User.gender,
        func.count(User.id).label('count')
    ).join(
        Entrepreneur, User.id == Entrepreneur.user_id
    ).group_by(
        User.gender
    ).all()
    
    data = [{'gender': r.gender, 'count': r.count} for r in results]
    return data

def get_regional_impact():
    """Obtener distribución de emprendedores por región."""
    # Suponiendo que los emprendedores tienen un campo 'region'
    from sqlalchemy import func
    
    results = db.session.query(
        Entrepreneur.region,
        func.count(Entrepreneur.id).label('count')
    ).group_by(
        Entrepreneur.region
    ).all()
    
    data = [{'region': r.region, 'count': r.count} for r in results]
    return data

def get_satisfaction_scores(start_date, end_date):
    """Obtener puntuaciones de satisfacción."""
    # Suponiendo que hay un modelo de feedback con puntuaciones
    from app.models.meeting import Meeting
    from sqlalchemy import func, and_
    
    # Calculamos la puntuación media por mes
    results = db.session.query(
        extract('year', Meeting.start_time).label('year'),
        extract('month', Meeting.start_time).label('month'),
        func.avg(Meeting.satisfaction_score).label('avg_score')
    ).filter(
        Meeting.start_time >= start_date,
        Meeting.end_time <= end_date,
        Meeting.status == 'completed',
        Meeting.satisfaction_score != None
    ).group_by(
        extract('year', Meeting.start_time),
        extract('month', Meeting.start_time)
    ).order_by(
        extract('year', Meeting.start_time),
        extract('month', Meeting.start_time)
    ).all()
    
    # Convertir resultados a formato esperado por el frontend
    data = []
    for result in results:
        month_date = datetime(int(result.year), int(result.month), 1)
        data.append({
            'month': month_date.strftime('%b %Y'),
            'score': float(result.avg_score)
        })
    
    return data

def get_entrepreneurs_details(start_date, end_date):
    """Obtener detalles de emprendedores para exportación."""
    # Obtener emprendedores que se unieron en el periodo
    entrepreneurs = Entrepreneur.query.filter(
        Entrepreneur.created_at >= start_date,
        Entrepreneur.created_at <= end_date
    ).all()
    
    data = []
    for e in entrepreneurs:
        user = User.query.get(e.user_id)
        data.append({
            'id': e.id,
            'name': f"{user.first_name} {user.last_name}",
            'email': user.email,
            'business_name': e.business_name,
            'sector': e.sector,
            'region': e.region,
            'join_date': e.created_at.strftime('%Y-%m-%d'),
            'status': 'Activo' if e.is_active else 'Inactivo'
        })
    
    return data

def get_hours_details(start_date, end_date):
    """Obtener detalles de horas de mentoría para exportación."""
    from app.models.meeting import Meeting
    
    # Obtener reuniones completadas en el periodo
    meetings = Meeting.query.filter(
        Meeting.start_time >= start_date,
        Meeting.end_time <= end_date,
        Meeting.status == 'completed'
    ).all()
    
    data = []
    for m in meetings:
        # Obtener nombres de aliado y emprendedor
        relationship = Relationship.query.get(m.relationship_id)
        entrepreneur = Entrepreneur.query.get(relationship.entrepreneur_id)
        entrepreneur_user = User.query.get(entrepreneur.user_id)
        
        ally = Ally.query.get(relationship.ally_id)
        ally_user = User.query.get(ally.user_id)
        
        data.append({
            'date': m.start_time.strftime('%Y-%m-%d'),
            'entrepreneur': f"{entrepreneur_user.first_name} {entrepreneur_user.last_name}",
            'ally': f"{ally_user.first_name} {ally_user.last_name}",
            'duration': m.duration,
            'topics': m.topics,
            'satisfaction_score': m.satisfaction_score or 'N/A'
        })
    
    return data