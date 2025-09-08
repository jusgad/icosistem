"""
Utilidades de Exportación de Datos para el Ecosistema de Emprendimiento

Este módulo proporciona funcionalidades para exportar datos del sistema
a formatos comunes como CSV, JSON y Excel.

Author: Sistema de Emprendimiento
Version: 1.0.0
"""

import csv
import json
import logging
from datetime import datetime
from io import StringIO, BytesIO
from typing import Any, Optional, Callable

import pandas as pd
from flask import current_app, Response

from app.extensions import db
from app.models.user import User
from app.models.entrepreneur import Entrepreneur
from app.models.project import Project
from app.models.organization import Organization
from app.models.program import Program
from app.models.ally import Ally
from app.models.client import Client
from app.models.meeting import Meeting
from app.models.task import Task
from app.models.document import Document
from app.models.activity_log import ActivityLog

logger = logging.getLogger(__name__)

class ExportUtils:
    """
    Clase de utilidad para exportar datos del sistema.
    """

    def __init__(self, app=None):
        self.app = app or current_app

    def _get_filename(self, base_name: str, extension: str) -> str:
        """Genera un nombre de archivo con timestamp."""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        return f"{base_name}_{timestamp}.{extension}"

    def _queryset_to_dicts(self, queryset: list[db.Model], fields: Optional[list[str]] = None) -> list[dict[str, Any]]:
        """Convierte un queryset de SQLAlchemy a una lista de diccionarios."""
        data_list = []
        for item in queryset:
            if hasattr(item, 'to_dict'):
                item_dict = item.to_dict()
                if fields:
                    data_list.append({field: item_dict.get(field) for field in fields})
                else:
                    data_list.append(item_dict)
            else:
                # Fallback si no hay to_dict (menos detallado)
                item_dict = {c.name: getattr(item, c.name) for c in item.__table__.columns}
                if fields:
                     data_list.append({field: item_dict.get(field) for field in fields})
                else:
                    data_list.append(item_dict)
        return data_list

    def export_to_csv(self, data: list[dict[str, Any]], filename_base: str = "export") -> Response:
        """
        Exporta datos a formato CSV.

        Args:
            data: Lista de diccionarios a exportar.
            filename_base: Nombre base para el archivo.

        Returns:
            Response: Objeto Response de Flask con el archivo CSV.
        """
        if not data:
            logger.warning("No hay datos para exportar a CSV.")
            return Response("No hay datos para exportar", mimetype="text/plain", status=204)

        output = StringIO()
        writer = csv.DictWriter(output, fieldnames=data[0].keys())
        writer.writeheader()
        writer.writerows(data)

        filename = self._get_filename(filename_base, "csv")
        
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    def export_to_json(self, data: list[dict[str, Any]], filename_base: str = "export") -> Response:
        """
        Exporta datos a formato JSON.

        Args:
            data: Lista de diccionarios a exportar.
            filename_base: Nombre base para el archivo.

        Returns:
            Response: Objeto Response de Flask con el archivo JSON.
        """
        if not data:
            logger.warning("No hay datos para exportar a JSON.")
            return Response("No hay datos para exportar", mimetype="text/plain", status=204)

        json_data = json.dumps(data, indent=2, ensure_ascii=False, default=str)
        filename = self._get_filename(filename_base, "json")

        return Response(
            json_data,
            mimetype="application/json",
            headers={"Content-Disposition": f"attachment;filename={filename}"}
        )

    def export_to_excel(self, data: list[dict[str, Any]], filename_base: str = "export", sheet_name: str = "Datos") -> Response:
        """
        Exporta datos a formato Excel (XLSX).

        Args:
            data: Lista de diccionarios a exportar.
            filename_base: Nombre base para el archivo.
            sheet_name: Nombre de la hoja en el archivo Excel.

        Returns:
            Response: Objeto Response de Flask con el archivo Excel.
        """
        if not data:
            logger.warning("No hay datos para exportar a Excel.")
            return Response("No hay datos para exportar", mimetype="text/plain", status=204)

        try:
            df = pd.DataFrame(data)
            output = BytesIO()
            
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df.to_excel(writer, sheet_name=sheet_name, index=False)
            
            output.seek(0)
            filename = self._get_filename(filename_base, "xlsx")

            return Response(
                output,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment;filename={filename}"}
            )
        except ImportError:
            logger.error("Pandas y XlsxWriter son necesarios para exportar a Excel.")
            return Response("Error: Librerías para Excel no instaladas.", mimetype="text/plain", status=500)
        except Exception as e:
            logger.error(f"Error exportando a Excel: {str(e)}")
            return Response(f"Error generando Excel: {str(e)}", mimetype="text/plain", status=500)

    def export_users(self, format: str = 'csv', fields: Optional[list[str]] = None, filters: Optional[dict[str, Any]] = None) -> Response:
        """Exporta datos de usuarios."""
        query = User.query
        if filters:
            query = query.filter_by(**filters)
        
        users = query.all()
        data = self._queryset_to_dicts(users, fields)
        
        if format == 'json':
            return self.export_to_json(data, "users_export")
        elif format == 'excel':
            return self.export_to_excel(data, "users_export", "Usuarios")
        else: # CSV por defecto
            return self.export_to_csv(data, "users_export")

    def export_entrepreneurs(self, format: str = 'csv', fields: Optional[list[str]] = None, filters: Optional[dict[str, Any]] = None) -> Response:
        """Exporta datos de emprendedores."""
        query = Entrepreneur.query.join(User) # Para poder filtrar por campos de User
        if filters:
            # Aquí se podrían aplicar filtros más complejos si es necesario
            # Ejemplo: query = query.filter(User.email.like(f"%{filters['email_contains']}%"))
            query = query.filter_by(**filters)
            
        entrepreneurs = query.all()
        
        # Preparar datos, incluyendo campos de User y Entrepreneur
        data_list = []
        for entrepreneur_profile in entrepreneurs:
            user_data = entrepreneur_profile.user.to_dict() if entrepreneur_profile.user else {}
            profile_data = entrepreneur_profile.to_dict()
            # Unir diccionarios, dando prioridad a los datos del perfil específico
            combined_data = {**user_data, **profile_data}
            
            if fields:
                data_list.append({field: combined_data.get(field) for field in fields})
            else:
                data_list.append(combined_data)

        if format == 'json':
            return self.export_to_json(data_list, "entrepreneurs_export")
        elif format == 'excel':
            return self.export_to_excel(data_list, "entrepreneurs_export", "Emprendedores")
        else:
            return self.export_to_csv(data_list, "entrepreneurs_export")

    def export_projects(self, format: str = 'csv', fields: Optional[list[str]] = None, filters: Optional[dict[str, Any]] = None) -> Response:
        """Exporta datos de proyectos."""
        query = Project.query
        if filters:
            query = query.filter_by(**filters)
            
        projects = query.all()
        data = self._queryset_to_dicts(projects, fields)
        
        if format == 'json':
            return self.export_to_json(data, "projects_export")
        elif format == 'excel':
            return self.export_to_excel(data, "projects_export", "Proyectos")
        else:
            return self.export_to_csv(data, "projects_export")

    def export_organizations(self, format: str = 'csv', fields: Optional[list[str]] = None, filters: Optional[dict[str, Any]] = None) -> Response:
        """Exporta datos de organizaciones."""
        query = Organization.query
        if filters:
            query = query.filter_by(**filters)
            
        organizations = query.all()
        data = self._queryset_to_dicts(organizations, fields)
        
        if format == 'json':
            return self.export_to_json(data, "organizations_export")
        elif format == 'excel':
            return self.export_to_excel(data, "organizations_export", "Organizaciones")
        else:
            return self.export_to_csv(data, "organizations_export")

    def export_all_data(self, format: str = 'excel') -> Response:
        """
        Exporta datos de múltiples modelos a un archivo Excel con diferentes hojas.
        Solo soporta Excel por la complejidad de múltiples datasets.
        """
        if format != 'excel':
            logger.warning("La exportación de todos los datos solo está optimizada para Excel.")
            # Podría implementarse para otros formatos, pero sería más complejo (ej. zip de CSVs)

        try:
            output = BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Usuarios
                users = User.query.all()
                user_data = self._queryset_to_dicts(users)
                pd.DataFrame(user_data).to_excel(writer, sheet_name='Usuarios', index=False)
                
                # Emprendedores
                entrepreneurs = Entrepreneur.query.all()
                entrepreneur_data_list = []
                for e in entrepreneurs:
                    user_data = e.user.to_dict() if e.user else {}
                    profile_data = e.to_dict()
                    entrepreneur_data_list.append({**user_data, **profile_data})
                pd.DataFrame(entrepreneur_data_list).to_excel(writer, sheet_name='Emprendedores', index=False)

                # Proyectos
                projects = Project.query.all()
                project_data = self._queryset_to_dicts(projects)
                pd.DataFrame(project_data).to_excel(writer, sheet_name='Proyectos', index=False)

                # Organizaciones
                organizations = Organization.query.all()
                org_data = self._queryset_to_dicts(organizations)
                pd.DataFrame(org_data).to_excel(writer, sheet_name='Organizaciones', index=False)
                
                # Programas
                programs = Program.query.all()
                program_data = self._queryset_to_dicts(programs)
                pd.DataFrame(program_data).to_excel(writer, sheet_name='Programas', index=False)

            output.seek(0)
            filename = self._get_filename("ecosistema_export_completo", "xlsx")

            return Response(
                output,
                mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": f"attachment;filename={filename}"}
            )
        except ImportError:
            logger.error("Pandas y XlsxWriter son necesarios para exportar a Excel.")
            return Response("Error: Librerías para Excel no instaladas.", mimetype="text/plain", status=500)
        except Exception as e:
            logger.error(f"Error exportando todos los datos a Excel: {str(e)}")
            return Response(f"Error generando Excel: {str(e)}", mimetype="text/plain", status=500)

# Instancia global para usar como funciones de conveniencia
_export_utils = None

def get_export_utils():
    """Obtener instancia global de ExportUtils"""
    global _export_utils
    if _export_utils is None:
        _export_utils = ExportUtils()
    return _export_utils

# Funciones de conveniencia
def export_to_csv(data: list[dict[str, Any]], filename_base: str = "export") -> Response:
    """Exportar datos a CSV"""
    return get_export_utils().export_to_csv(data, filename_base)

def export_to_excel(data: list[dict[str, Any]], filename_base: str = "export", sheet_name: str = "Datos") -> Response:
    """Exportar datos a Excel"""
    return get_export_utils().export_to_excel(data, filename_base, sheet_name)

def export_to_pdf(data: list[dict[str, Any]], filename_base: str = "export") -> Response:
    """Exportar datos a PDF (actualmente no implementado, devuelve CSV)"""
    # TODO: Implementar exportación a PDF
    return export_to_csv(data, filename_base)

def export_to_json(data: list[dict[str, Any]], filename_base: str = "export") -> Response:
    """Exportar datos a JSON"""
    return get_export_utils().export_to_json(data, filename_base)

# Exportaciones principales del módulo
__all__ = ['ExportUtils', 'export_to_csv', 'export_to_excel', 'export_to_pdf', 'export_to_json']
