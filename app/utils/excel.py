# app/utils/excel.py

import os
import uuid
from datetime import datetime
import pandas as pd
import numpy as np
import xlsxwriter
from io import BytesIO
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from openpyxl.utils import get_column_letter
from openpyxl.drawing.image import Image
from flask import current_app, url_for
import logging

logger = logging.getLogger(__name__)

def generate_excel(data, columns=None, sheet_name='Hoja1', filename=None):
    """
    Genera un archivo Excel básico a partir de datos.
    
    Args:
        data (list): Lista de diccionarios o filas de datos
        columns (list): Lista de columnas a incluir (opcional)
        sheet_name (str): Nombre de la hoja de cálculo
        filename (str): Nombre del archivo (opcional)
        
    Returns:
        BytesIO/str: Objeto BytesIO con el Excel o ruta del archivo guardado
    """
    try:
        # Crear DataFrame con los datos
        df = pd.DataFrame(data)
        
        # Filtrar columnas si se especificaron
        if columns:
            df = df[columns]
        
        # Crear un objeto BytesIO para guardar el Excel
        output = BytesIO()
        
        # Crear un escritor de Excel
        writer = pd.ExcelWriter(output, engine='xlsxwriter')
        
        # Convertir el DataFrame a Excel
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        
        # Obtener el objeto xlsxwriter workbook y worksheet
        workbook = writer.book
        worksheet = writer.sheets[sheet_name]
        
        # Agregar formato a la cabecera
        header_format = workbook.add_format({
            'bold': True,
            'text_wrap': True,
            'valign': 'top',
            'fg_color': '#D7E4BC',
            'border': 1
        })
        
        # Aplicar formato a la cabecera
        for col_num, value in enumerate(df.columns.values):
            worksheet.write(0, col_num, value, header_format)
            # Ajustar ancho de columna basado en el contenido
            column_width = max(
                df[value].astype(str).map(len).max(),
                len(str(value))
            )
            worksheet.set_column(col_num, col_num, column_width + 2)
        
        # Guardar el archivo
        writer.close()
        output.seek(0)
        
        # Si se especificó un nombre de archivo, guardar en disco
        if filename:
            # Asegurar que tiene extensión .xlsx
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Guardar el archivo
            with open(filename, 'wb') as f:
                f.write(output.getvalue())
            
            return filename
        else:
            # Devolver el objeto BytesIO
            return output
    except Exception as e:
        logger.error(f"Error al generar Excel: {str(e)}")
        raise

def generate_report_excel(report_type, data, user=None, filename=None):
    """
    Genera un archivo Excel con formato para reportes específicos.
    
    Args:
        report_type (str): Tipo de reporte ('entrepreneur_progress', 'ally_hours', etc.)
        data (dict): Datos para incluir en el reporte
        user (User): Usuario que genera el reporte (opcional)
        filename (str): Nombre del archivo (opcional)
        
    Returns:
        BytesIO/str: Objeto BytesIO con el Excel o ruta del archivo guardado
    """
    try:
        # Crear un nuevo libro de trabajo
        wb = Workbook()
        ws = wb.active
        
        # Configurar nombre de la hoja según el tipo de reporte
        report_names = {
            'entrepreneur_progress': 'Progreso de Emprendedores',
            'ally_hours': 'Horas de Aliados',
            'impact_summary': 'Resumen de Impacto',
            'client_report': 'Reporte de Cliente'
        }
        
        ws.title = report_names.get(report_type, 'Reporte')
        
        # Definir estilos
        header_font = Font(name='Arial', size=12, bold=True, color='FFFFFF')
        header_fill = PatternFill(start_color='366092', end_color='366092', fill_type='solid')
        header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        
        # Agregar información de encabezado del reporte
        ws['A1'] = 'REPORTE: ' + report_names.get(report_type, 'Reporte')
        ws.merge_cells('A1:D1')
        ws['A1'].font = Font(name='Arial', size=14, bold=True)
        ws['A1'].alignment = Alignment(horizontal='center')
        
        ws['A2'] = 'Fecha de generación:'
        ws['B2'] = datetime.now().strftime('%d/%m/%Y %H:%M')
        if user:
            ws['C2'] = 'Generado por:'
            ws['D2'] = f"{user.first_name} {user.last_name}"
        
        # Agregar logo si está disponible
        try:
            logo_path = os.path.join(current_app.static_folder, 'images/logo.png')
            if os.path.exists(logo_path):
                img = Image(logo_path)
                # Redimensionar imagen si es necesario
                img.width = 100
                img.height = 100
                ws.add_image(img, 'E1')
        except Exception as e:
            logger.warning(f"No se pudo agregar el logo: {str(e)}")
        
        # Espacio antes de los datos
        current_row = 4
        
        # Generar contenido según el tipo de reporte
        if report_type == 'entrepreneur_progress':
            _add_entrepreneur_progress_data(ws, data, current_row, header_font, header_fill, header_alignment, thin_border)
        elif report_type == 'ally_hours':
            _add_ally_hours_data(ws, data, current_row, header_font, header_fill, header_alignment, thin_border)
        elif report_type == 'impact_summary':
            _add_impact_summary_data(ws, data, current_row, header_font, header_fill, header_alignment, thin_border)
        elif report_type == 'client_report':
            _add_client_report_data(ws, data, current_row, header_font, header_fill, header_alignment, thin_border)
        else:
            # Reporte genérico
            _add_generic_report_data(ws, data, current_row, header_font, header_fill, header_alignment, thin_border)
        
        # Ajustar anchos de columna
        for column in ws.columns:
            max_length = 0
            column_letter = get_column_letter(column[0].column)
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column_letter].width = adjusted_width
        
        # Guardar el archivo
        if filename:
            # Asegurar que tiene extensión .xlsx
            if not filename.endswith('.xlsx'):
                filename += '.xlsx'
            
            # Crear directorio si no existe
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            
            # Guardar el archivo
            wb.save(filename)
            return filename
        else:
            # Devolver como BytesIO
            output = BytesIO()
            wb.save(output)
            output.seek(0)
            return output
    except Exception as e:
        logger.error(f"Error al generar reporte Excel: {str(e)}")
        raise

def _add_entrepreneur_progress_data(ws, data, current_row, header_font, header_fill, header_alignment, thin_border):
    """
    Agrega datos de progreso de emprendedores a una hoja de Excel.
    
    Args:
        ws: Hoja de trabajo de Excel
        data: Datos a agregar
        current_row: Fila actual
        header_font: Estilo de fuente para encabezados
        header_fill: Estilo de relleno para encabezados
        header_alignment: Estilo de alineación para encabezados
        thin_border: Estilo de borde
    """
    # Encabezados
    headers = ['Emprendedor', 'Sector', 'Aliado Asignado', 'Progreso (%)', 'Inicio', 'Última Actualización', 'Estado']
    
    # Agregar encabezados
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
    
    # Agregar datos
    for entrepreneur in data.get('entrepreneurs', []):
        current_row += 1
        
        # Información básica
        ws.cell(row=current_row, column=1, value=entrepreneur.get('name')).border = thin_border
        ws.cell(row=current_row, column=2, value=entrepreneur.get('sector')).border = thin_border
        ws.cell(row=current_row, column=3, value=entrepreneur.get('ally_name')).border = thin_border
        
        # Progreso
        progress_cell = ws.cell(row=current_row, column=4, value=entrepreneur.get('progress', 0))
        progress_cell.border = thin_border
        progress_cell.number_format = '0.00%'
        
        # Fechas
        ws.cell(row=current_row, column=5, value=entrepreneur.get('start_date')).border = thin_border
        ws.cell(row=current_row, column=6, value=entrepreneur.get('last_update')).border = thin_border
        
        # Estado
        status_cell = ws.cell(row=current_row, column=7, value=entrepreneur.get('status'))
        status_cell.border = thin_border
        
        # Colorear según estado
        status_colors = {
            'activo': 'C6EFCE',  # Verde
            'completado': '92D050',  # Verde más oscuro
            'en pausa': 'FFEB9C',  # Amarillo
            'cancelado': 'FFC7CE'   # Rojo
        }
        if entrepreneur.get('status', '').lower() in status_colors:
            status_cell.fill = PatternFill(
                start_color=status_colors[entrepreneur.get('status', '').lower()],
                end_color=status_colors[entrepreneur.get('status', '').lower()],
                fill_type='solid'
            )

def _add_ally_hours_data(ws, data, current_row, header_font, header_fill, header_alignment, thin_border):
    """
    Agrega datos de horas de aliados a una hoja de Excel.
    
    Args:
        ws: Hoja de trabajo de Excel
        data: Datos a agregar
        current_row: Fila actual
        header_font: Estilo de fuente para encabezados
        header_fill: Estilo de relleno para encabezados
        header_alignment: Estilo de alineación para encabezados
        thin_border: Estilo de borde
    """
    # Encabezados
    headers = ['Aliado', 'Tipo', 'Total Horas', 'Emprendedores Asignados', 'Promedio Horas/Emprendedor', 'Último Registro']
    
    # Agregar encabezados
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
    
    # Agregar datos
    for ally in data.get('allies', []):
        current_row += 1
        
        ws.cell(row=current_row, column=1, value=ally.get('name')).border = thin_border
        ws.cell(row=current_row, column=2, value=ally.get('type')).border = thin_border
        
        hours_cell = ws.cell(row=current_row, column=3, value=ally.get('total_hours', 0))
        hours_cell.border = thin_border
        hours_cell.number_format = '0.00'
        
        ws.cell(row=current_row, column=4, value=ally.get('assigned_entrepreneurs', 0)).border = thin_border
        
        avg_cell = ws.cell(row=current_row, column=5, value=ally.get('avg_hours_per_entrepreneur', 0))
        avg_cell.border = thin_border
        avg_cell.number_format = '0.00'
        
        ws.cell(row=current_row, column=6, value=ally.get('last_record_date')).border = thin_border

def _add_impact_summary_data(ws, data, current_row, header_font, header_fill, header_alignment, thin_border):
    """
    Agrega datos de resumen de impacto a una hoja de Excel.
    
    Args:
        ws: Hoja de trabajo de Excel
        data: Datos a agregar
        current_row: Fila actual
        header_font: Estilo de fuente para encabezados
        header_fill: Estilo de relleno para encabezados
        header_alignment: Estilo de alineación para encabezados
        thin_border: Estilo de borde
    """
    # Agregar resumen general
    ws.cell(row=current_row, column=1, value="RESUMEN DE IMPACTO")
    ws.merge_cells(f'A{current_row}:F{current_row}')
    ws.cell(row=current_row, column=1).font = Font(name='Arial', size=12, bold=True)
    ws.cell(row=current_row, column=1).alignment = Alignment(horizontal='center')
    
    current_row += 2
    
    # Indicadores clave
    key_indicators = [
        ('Total de Emprendedores', data.get('total_entrepreneurs', 0)),
        ('Emprendedores Activos', data.get('active_entrepreneurs', 0)),
        ('Horas de Mentoría', data.get('total_mentoring_hours', 0)),
        ('Empleos Generados', data.get('jobs_created', 0)),
        ('Tasa de Éxito', data.get('success_rate', 0)),
        ('Inversión Total Captada', data.get('total_investment', 0))
    ]
    
    for i, (label, value) in enumerate(key_indicators):
        col = (i % 3) * 2 + 1
        row = current_row + (i // 3)
        
        ws.cell(row=row, column=col, value=label).font = Font(bold=True)
        value_cell = ws.cell(row=row, column=col + 1, value=value)
        
        if 'Tasa' in label:
            value_cell.number_format = '0.00%'
        elif 'Inversión' in label:
            value_cell.number_format = '"$"#,##0.00'
    
    current_row += 4
    
    # Encabezados para tabla de sectores
    headers = ['Sector', 'Emprendedores', '% del Total', 'Inversión Promedio', 'Empleos Promedio']
    
    # Agregar encabezados
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
    
    # Agregar datos por sector
    for sector in data.get('sectors', []):
        current_row += 1
        
        ws.cell(row=current_row, column=1, value=sector.get('name')).border = thin_border
        ws.cell(row=current_row, column=2, value=sector.get('entrepreneur_count', 0)).border = thin_border
        
        percent_cell = ws.cell(row=current_row, column=3, value=sector.get('percentage', 0))
        percent_cell.border = thin_border
        percent_cell.number_format = '0.00%'
        
        inv_cell = ws.cell(row=current_row, column=4, value=sector.get('avg_investment', 0))
        inv_cell.border = thin_border
        inv_cell.number_format = '"$"#,##0.00'
        
        ws.cell(row=current_row, column=5, value=sector.get('avg_jobs', 0)).border = thin_border

def _add_client_report_data(ws, data, current_row, header_font, header_fill, header_alignment, thin_border):
    """
    Agrega datos de reporte de cliente a una hoja de Excel.
    
    Args:
        ws: Hoja de trabajo de Excel
        data: Datos a agregar
        current_row: Fila actual
        header_font: Estilo de fuente para encabezados
        header_fill: Estilo de relleno para encabezados
        header_alignment: Estilo de alineación para encabezados
        thin_border: Estilo de borde
    """
    # Información del cliente
    ws.cell(row=current_row, column=1, value="Cliente:").font = Font(bold=True)
    ws.cell(row=current_row, column=2, value=data.get('client_name', ''))
    
    current_row += 1
    ws.cell(row=current_row, column=1, value="Período:").font = Font(bold=True)
    ws.cell(row=current_row, column=2, value=f"{data.get('start_date', '')} - {data.get('end_date', '')}")
    
    current_row += 2
    
    # Encabezados para tabla de emprendedores
    headers = ['Emprendedor', 'Sector', 'Fecha de Inicio', 'Estado', 'Progreso', 'Inversión', 'KPI 1', 'KPI 2']
    
    # Agregar encabezados
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=current_row, column=col, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_alignment
        cell.border = thin_border
    
    # Agregar datos de emprendedores
    for entrepreneur in data.get('entrepreneurs', []):
        current_row += 1
        
        ws.cell(row=current_row, column=1, value=entrepreneur.get('name')).border = thin_border
        ws.cell(row=current_row, column=2, value=entrepreneur.get('sector')).border = thin_border
        ws.cell(row=current_row, column=3, value=entrepreneur.get('start_date')).border = thin_border
        ws.cell(row=current_row, column=4, value=entrepreneur.get('status')).border = thin_border
        
        progress_cell = ws.cell(row=current_row, column=5, value=entrepreneur.get('progress', 0))
        progress_cell.border = thin_border
        progress_cell.number_format = '0.00%'
        
        inv_cell = ws.cell(row=current_row, column=6, value=entrepreneur.get('investment', 0))
        inv_cell.border = thin_border
        inv_cell.number_format = '"$"#,##0.00'
        
        ws.cell(row=current_row, column=7, value=entrepreneur.get('kpi1', 0)).border = thin_border
        ws.cell(row=current_row, column=8, value=entrepreneur.get('kpi2', 0)).border = thin_border

def _add_generic_report_data(ws, data, current_row, header_font, header_fill, header_alignment, thin_border):
    """
    Agrega datos genéricos a una hoja de Excel.
    
    Args:
        ws: Hoja de trabajo de Excel
        data: Datos a agregar
        current_row: Fila actual
        header_font: Estilo de fuente para encabezados
        header_fill: Estilo de relleno para encabezados
        header_alignment: Estilo de alineación para encabezados
        thin_border: Estilo de borde
    """
    # Detectar encabezados a partir de los datos
    if 'items' in data and data['items'] and isinstance(data['items'], list) and len(data['items']) > 0:
        headers = list(data['items'][0].keys())
        
        # Agregar encabezados
        for col, header in enumerate(headers, 1):
            cell = ws.cell(row=current_row, column=col, value=header)
            cell.font = header_font
            cell.fill = header_fill
            cell.alignment = header_alignment
            cell.border = thin_border
        
        # Agregar datos
        for item in data['items']:
            current_row += 1
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=current_row, column=col, value=item.get(header))
                cell.border = thin_border
    else:
        # Si no hay datos estructurados, agregar mensaje
        ws.cell(row=current_row, column=1, value="No hay datos disponibles para este reporte.")
        ws.merge_cells(f'A{current_row}:D{current_row}')

def export_model_to_excel(model_class, query=None, filename=None, exclude_columns=None):
    """
    Exporta registros de un modelo SQLAlchemy a Excel.
    
    Args:
        model_class: Clase del modelo SQLAlchemy
        query: Consulta SQLAlchemy (opcional)
        filename (str): Nombre del archivo (opcional)
        exclude_columns (list): Columnas a excluir
        
    Returns:
        BytesIO/str: Objeto BytesIO con el Excel o ruta del archivo guardado
    """
    try:
        # Obtener nombre de la tabla
        table_name = model_class.__tablename__
        
        # Usar consulta proporcionada o crear una básica
        if query is None:
            query = model_class.query
        
        # Ejecutar consulta
        records = query.all()
        
        # Convertir a diccionarios
        data = []
        for record in records:
            if hasattr(record, 'to_dict'):
                # Si el modelo tiene método to_dict
                item = record.to_dict()
            else:
                # Convertir manualmente
                item = {}
                for column in model_class.__table__.columns:
                    col_name = column.name
                    if exclude_columns and col_name in exclude_columns:
                        continue
                    item[col_name] = getattr(record, col_name)
            data.append(item)
        
        # Generar Excel
        if not filename:
            filename = f"export_{table_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return generate_excel(data, sheet_name=table_name, filename=filename)
    except Exception as e:
        logger.error(f"Error al exportar modelo a Excel: {str(e)}")
        raise

def import_excel_to_model(file_path, model_class, session, unique_columns=None, update_if_exists=True):
    """
    Importa datos de Excel a un modelo SQLAlchemy.
    
    Args:
        file_path (str): Ruta del archivo Excel
        model_class: Clase del modelo SQLAlchemy
        session: Sesión SQLAlchemy
        unique_columns (list): Columnas que identifican registros únicos
        update_if_exists (bool): Si es True, actualiza registros existentes
        
    Returns:
        dict: Estadísticas de importación
    """
    try:
        # Cargar datos del Excel
        df = pd.read_excel(file_path)
        
        # Estadísticas de importación
        stats = {
            'total': len(df),
            'created': 0,
            'updated': 0,
            'errors': 0,
            'error_details': []
        }
        
        # Obtener columnas del modelo
        model_columns = [column.name for column in model_class.__table__.columns]
        
        # Filtrar columnas que no pertenecen al modelo
        valid_columns = [col for col in df.columns if col in model_columns]
        df = df[valid_columns]
        
        # Procesar cada fila
        for index, row in df.iterrows():
            try:
                # Convertir a diccionario y limpiar valores NaN
                data = row.to_dict()
                for key, value in list(data.items()):
                    if pd.isna(value):
                        data[key] = None
                
                # Verificar si el registro ya existe
                if unique_columns and update_if_exists:
                    filters = {col: data[col] for col in unique_columns if col in data}
                    existing_record = model_class.query.filter_by(**filters).first()
                    
                    if existing_record:
                        # Actualizar registro existente
                        for key, value in data.items():
                            if key in model_columns:
                                setattr(existing_record, key, value)
                        stats['updated'] += 1
                        continue
                
                # Crear nuevo registro
                new_record = model_class(**{k: v for k, v in data.items() if k in model_columns})
                session.add(new_record)
                stats['created'] += 1
                
            except Exception as e:
                stats['errors'] += 1
                stats['error_details'].append(f"Error en fila {index+2}: {str(e)}")
        
        # Guardar cambios en la base de datos
        session.commit()
        
        return stats
    except Exception as e:
        logger.error(f"Error al importar Excel a modelo: {str(e)}")
        session.rollback()
        raise