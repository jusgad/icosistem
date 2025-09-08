"""
Utilidades de PDF - Ecosistema de Emprendimiento
===============================================

Este módulo proporciona un conjunto completo de utilidades para la generación
de documentos PDF específicos para el ecosistema de emprendimiento colombiano,
incluyendo reportes, certificados, planes de negocio, facturas y más.

Características principales:
- Generación de PDFs profesionales con templates
- Reportes específicos para emprendimiento
- Certificados y documentos oficiales
- Planes de negocio estructurados
- Facturas y presupuestos
- Reportes de mentoría y seguimiento
- Gráficos y visualizaciones integradas
- Watermarks y elementos de seguridad
- Formatos colombianos (moneda, fechas, direcciones)
- Optimización para impresión y digital

Uso básico:
-----------
    from app.utils.pdf import PDFGenerator, generate_entrepreneur_report
    
    # Generar reporte de emprendedor
    pdf_generator = PDFGenerator()
    pdf_path = pdf_generator.generate_entrepreneur_report(entrepreneur_data)
    
    # Generar certificado
    certificate_path = generate_certificate(
        participant_name="Juan Pérez",
        program_name="Programa de Aceleración TechStart 2024",
        completion_date="2024-12-13"
    )

Tipos de documentos soportados:
------------------------------
- Reportes de emprendedores
- Planes de negocio
- Reportes de proyectos
- Certificados de participación
- Facturas y presupuestos
- Reportes de mentoría
- Documentos de evaluación
- Contratos básicos
- Presentaciones (pitch decks)
"""

import os
import io
import logging
import tempfile
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
from typing import Optional, Union, Any, BinaryIO
from dataclasses import dataclass, field
from enum import Enum
import base64

# Imports de ReportLab (principal librería de PDF)
try:
    from reportlab.lib import colors
    from reportlab.lib.colors import Color
    from reportlab.lib.pagesizes import letter, A4, legal
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch, cm, mm
    from reportlab.lib.utils import ImageReader
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        Image, PageBreak, Frame, FrameBreak, NextPageTemplate,
        PageTemplate, BaseDocTemplate, Flowable
    )
    from reportlab.platypus.tableofcontents import TableOfContents
    from reportlab.graphics.shapes import Drawing, Rect, Line, Circle
    from reportlab.graphics.charts.barcharts import VerticalBarChart
    from reportlab.graphics.charts.piecharts import Pie
    from reportlab.graphics.charts.linecharts import HorizontalLineChart
    from reportlab.graphics import renderPDF
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    REPORTLAB_AVAILABLE = True
except ImportError:
    REPORTLAB_AVAILABLE = False
    logging.warning("ReportLab no disponible. Funcionalidad PDF limitada.")

# Imports opcionales
try:
    import matplotlib.pyplot as plt
    import matplotlib
    matplotlib.use('Agg')  # Backend sin GUI
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

try:
    from PIL import Image as PILImage
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import qrcode
    QRCODE_AVAILABLE = True
except ImportError:
    QRCODE_AVAILABLE = False

# Configurar logger
logger = logging.getLogger(__name__)

# ==============================================================================
# CONFIGURACIÓN Y CONSTANTES
# ==============================================================================

# Configuración de PDF
PDF_CONFIG = {
    'default_page_size': A4,
    'default_margins': {
        'top': 2*cm,
        'bottom': 2*cm,
        'left': 2*cm,
        'right': 2*cm
    },
    'default_font': 'Helvetica',
    'default_font_size': 10,
    'title_font_size': 16,
    'header_font_size': 12,
    'output_dir': 'pdfs',
    'temp_dir': tempfile.gettempdir(),
    'quality': 'high',  # high, medium, low
    'compress': True,
    'embed_fonts': False,
    'watermark_opacity': 0.1,
    'logo_max_width': 3*cm,
    'logo_max_height': 2*cm,
}

# Colores corporativos del ecosistema
ECOSYSTEM_COLORS = {
    'primary': Color(0.2, 0.4, 0.8),        # Azul principal
    'secondary': Color(0.8, 0.4, 0.2),      # Naranja secundario
    'accent': Color(0.2, 0.8, 0.4),         # Verde acento
    'success': Color(0.2, 0.7, 0.3),        # Verde éxito
    'warning': Color(0.9, 0.7, 0.1),        # Amarillo advertencia
    'danger': Color(0.8, 0.2, 0.2),         # Rojo peligro
    'dark': Color(0.2, 0.2, 0.2),           # Gris oscuro
    'light': Color(0.9, 0.9, 0.9),          # Gris claro
    'white': colors.white,
    'black': colors.black
}

# Estilos de texto
TEXT_STYLES = {
    'title': ParagraphStyle(
        'CustomTitle',
        parent=getSampleStyleSheet()['Title'] if REPORTLAB_AVAILABLE else None,
        fontSize=18,
        textColor=ECOSYSTEM_COLORS['primary'],
        spaceAfter=20,
        alignment=1  # Centrado
    ) if REPORTLAB_AVAILABLE else None,
    
    'heading1': ParagraphStyle(
        'CustomHeading1',
        parent=getSampleStyleSheet()['Heading1'] if REPORTLAB_AVAILABLE else None,
        fontSize=14,
        textColor=ECOSYSTEM_COLORS['dark'],
        spaceAfter=12,
        spaceBefore=12
    ) if REPORTLAB_AVAILABLE else None,
    
    'heading2': ParagraphStyle(
        'CustomHeading2',
        parent=getSampleStyleSheet()['Heading2'] if REPORTLAB_AVAILABLE else None,
        fontSize=12,
        textColor=ECOSYSTEM_COLORS['dark'],
        spaceAfter=10,
        spaceBefore=10
    ) if REPORTLAB_AVAILABLE else None,
    
    'normal': ParagraphStyle(
        'CustomNormal',
        parent=getSampleStyleSheet()['Normal'] if REPORTLAB_AVAILABLE else None,
        fontSize=10,
        textColor=ECOSYSTEM_COLORS['dark'],
        spaceAfter=6
    ) if REPORTLAB_AVAILABLE else None,
    
    'small': ParagraphStyle(
        'CustomSmall',
        parent=getSampleStyleSheet()['Normal'] if REPORTLAB_AVAILABLE else None,
        fontSize=8,
        textColor=ECOSYSTEM_COLORS['dark'],
        spaceAfter=4
    ) if REPORTLAB_AVAILABLE else None
}

# ==============================================================================
# CLASES DE DATOS Y ENUMS
# ==============================================================================

class DocumentType(Enum):
    """Tipos de documento PDF."""
    ENTREPRENEUR_REPORT = 'entrepreneur_report'
    PROJECT_REPORT = 'project_report'
    BUSINESS_PLAN = 'business_plan'
    CERTIFICATE = 'certificate'
    INVOICE = 'invoice'
    QUOTE = 'quote'
    MENTORSHIP_REPORT = 'mentorship_report'
    EVALUATION = 'evaluation'
    PITCH_DECK = 'pitch_deck'
    PROGRAM_REPORT = 'program_report'
    CONTRACT = 'contract'

class PageOrientation(Enum):
    """Orientación de página."""
    PORTRAIT = 'portrait'
    LANDSCAPE = 'landscape'

@dataclass
class PDFMetadata:
    """Metadatos del documento PDF."""
    title: str
    author: str = "Ecosistema de Emprendimiento"
    subject: str = ""
    creator: str = "Sistema de Gestión de Emprendimiento"
    keywords: list[str] = field(default_factory=list)
    creation_date: Optional[datetime] = None

@dataclass
class PDFSettings:
    """Configuración para generación de PDF."""
    page_size: tuple[float, float] = A4
    orientation: PageOrientation = PageOrientation.PORTRAIT
    margins: dict[str, float] = field(default_factory=lambda: PDF_CONFIG['default_margins'].copy())
    font_family: str = 'Helvetica'
    font_size: int = 10
    include_header: bool = True
    include_footer: bool = True
    include_page_numbers: bool = True
    watermark_text: Optional[str] = None
    logo_path: Optional[str] = None
    compress: bool = True
    quality: str = 'high'

class PDFError(Exception):
    """Excepción base para errores de PDF."""
    pass

class TemplateError(PDFError):
    """Error en template de PDF."""
    pass

class RenderError(PDFError):
    """Error en renderizado de PDF."""
    pass

# ==============================================================================
# GENERADOR PRINCIPAL DE PDF
# ==============================================================================

class PDFGenerator:
    """Generador principal de documentos PDF."""
    
    def __init__(self, settings: Optional[PDFSettings] = None):
        if not REPORTLAB_AVAILABLE:
            raise PDFError("ReportLab no está disponible")
        
        self.settings = settings or PDFSettings()
        self.styles = getSampleStyleSheet()
        self.custom_styles = TEXT_STYLES
        self.colors = ECOSYSTEM_COLORS
        
        # Crear directorio de salida
        output_dir = Path(PDF_CONFIG['output_dir'])
        output_dir.mkdir(exist_ok=True)
        
        logger.info("PDFGenerator inicializado")
    
    def generate_document(self, content: list[Any], 
                         output_path: str,
                         metadata: Optional[PDFMetadata] = None) -> str:
        """
        Genera documento PDF con contenido especificado.
        
        Args:
            content: Lista de elementos del documento
            output_path: Ruta de salida
            metadata: Metadatos del documento
            
        Returns:
            Ruta del archivo generado
            
        Examples:
            >>> generator = PDFGenerator()
            >>> content = [Paragraph("Hola Mundo", style)]
            >>> path = generator.generate_document(content, "output.pdf")
        """
        try:
            # Crear documento
            doc = SimpleDocTemplate(
                output_path,
                pagesize=self.settings.page_size,
                topMargin=self.settings.margins['top'],
                bottomMargin=self.settings.margins['bottom'],
                leftMargin=self.settings.margins['left'],
                rightMargin=self.settings.margins['right']
            )
            
            # Configurar metadatos
            if metadata:
                doc.title = metadata.title
                doc.author = metadata.author
                doc.subject = metadata.subject
                doc.creator = metadata.creator
            
            # Construir documento
            doc.build(content, onFirstPage=self._add_page_elements,
                     onLaterPages=self._add_page_elements)
            
            logger.info(f"PDF generado: {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Error generando PDF: {e}")
            raise RenderError(f"Error generando documento: {e}")
    
    def _add_page_elements(self, canvas_obj, doc):
        """Añade elementos de página (header, footer, etc.)."""
        if self.settings.include_header:
            self._add_header(canvas_obj, doc)
        
        if self.settings.include_footer:
            self._add_footer(canvas_obj, doc)
        
        if self.settings.watermark_text:
            self._add_watermark(canvas_obj, doc)
        
        if self.settings.logo_path and os.path.exists(self.settings.logo_path):
            self._add_logo(canvas_obj, doc)
    
    def _add_header(self, canvas_obj, doc):
        """Añade header a la página."""
        canvas_obj.saveState()
        
        # Línea superior
        canvas_obj.setStrokeColor(self.colors['primary'])
        canvas_obj.setLineWidth(2)
        canvas_obj.line(
            self.settings.margins['left'],
            doc.height + self.settings.margins['bottom'] + 1.5*cm,
            doc.width + self.settings.margins['left'],
            doc.height + self.settings.margins['bottom'] + 1.5*cm
        )
        
        canvas_obj.restoreState()
    
    def _add_footer(self, canvas_obj, doc):
        """Añade footer a la página."""
        canvas_obj.saveState()
        
        # Línea inferior
        canvas_obj.setStrokeColor(self.colors['light'])
        canvas_obj.setLineWidth(1)
        canvas_obj.line(
            self.settings.margins['left'],
            self.settings.margins['bottom'] - 0.5*cm,
            doc.width + self.settings.margins['left'],
            self.settings.margins['bottom'] - 0.5*cm
        )
        
        # Información del footer
        canvas_obj.setFont('Helvetica', 8)
        canvas_obj.setFillColor(self.colors['dark'])
        
        # Fecha de generación
        footer_text = f"Generado el {datetime.now().strftime('%d/%m/%Y %H:%M')}"
        canvas_obj.drawString(
            self.settings.margins['left'],
            self.settings.margins['bottom'] - 0.8*cm,
            footer_text
        )
        
        # Número de página
        if self.settings.include_page_numbers:
            page_text = f"Página {doc.page}"
            canvas_obj.drawRightString(
                doc.width + self.settings.margins['left'],
                self.settings.margins['bottom'] - 0.8*cm,
                page_text
            )
        
        canvas_obj.restoreState()
    
    def _add_watermark(self, canvas_obj, doc):
        """Añade watermark al documento."""
        canvas_obj.saveState()
        
        canvas_obj.setFillColor(self.colors['light'])
        canvas_obj.setFillAlpha(PDF_CONFIG['watermark_opacity'])
        canvas_obj.setFont('Helvetica-Bold', 50)
        
        # Rotar y centrar watermark
        canvas_obj.translate(doc.width/2, doc.height/2)
        canvas_obj.rotate(45)
        
        text_width = canvas_obj.stringWidth(self.settings.watermark_text, 'Helvetica-Bold', 50)
        canvas_obj.drawCentredText(0, 0, self.settings.watermark_text)
        
        canvas_obj.restoreState()
    
    def _add_logo(self, canvas_obj, doc):
        """Añade logo al documento."""
        try:
            canvas_obj.saveState()
            
            # Calcular posición del logo (esquina superior derecha)
            logo_x = doc.width + self.settings.margins['left'] - PDF_CONFIG['logo_max_width']
            logo_y = doc.height + self.settings.margins['bottom'] + 0.5*cm
            
            canvas_obj.drawImage(
                self.settings.logo_path,
                logo_x, logo_y,
                width=PDF_CONFIG['logo_max_width'],
                height=PDF_CONFIG['logo_max_height'],
                preserveAspectRatio=True
            )
            
            canvas_obj.restoreState()
            
        except Exception as e:
            logger.warning(f"Error añadiendo logo: {e}")

# ==============================================================================
# GENERADORES ESPECÍFICOS PARA EMPRENDIMIENTO
# ==============================================================================

def generate_entrepreneur_report(entrepreneur_data: dict[str, Any], 
                               output_path: Optional[str] = None) -> str:
    """
    Genera reporte completo de emprendedor.
    
    Args:
        entrepreneur_data: Datos del emprendedor
        output_path: Ruta de salida (opcional)
        
    Returns:
        Ruta del archivo generado
        
    Examples:
        >>> entrepreneur = {
        ...     'name': 'Juan Pérez',
        ...     'email': 'juan@startup.com',
        ...     'company_name': 'TechStart',
        ...     'business_sector': 'Tecnología',
        ...     'projects': [...]
        ... }
        >>> pdf_path = generate_entrepreneur_report(entrepreneur)
    """
    if not REPORTLAB_AVAILABLE:
        raise PDFError("ReportLab no está disponible")
    
    # Configurar salida
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_emprendedor_{entrepreneur_data.get('id', 'unknown')}_{timestamp}.pdf"
        output_path = os.path.join(PDF_CONFIG['output_dir'], filename)
    
    # Metadatos
    metadata = PDFMetadata(
        title=f"Reporte de Emprendedor - {entrepreneur_data.get('name', 'N/A')}",
        subject="Reporte detallado de emprendedor",
        keywords=['emprendedor', 'reporte', 'ecosistema']
    )
    
    # Crear contenido
    content = []
    styles = getSampleStyleSheet()
    
    # Título principal
    content.append(Paragraph(
        f"Reporte de Emprendedor",
        TEXT_STYLES['title']
    ))
    content.append(Spacer(1, 20))
    
    # Información personal
    content.append(Paragraph("Información Personal", TEXT_STYLES['heading1']))
    
    personal_data = [
        ['Nombre:', entrepreneur_data.get('name', 'N/A')],
        ['Email:', entrepreneur_data.get('email', 'N/A')],
        ['Teléfono:', entrepreneur_data.get('phone', 'N/A')],
        ['Ciudad:', entrepreneur_data.get('city', 'N/A')],
        ['País:', entrepreneur_data.get('country', 'Colombia')],
    ]
    
    personal_table = Table(personal_data, colWidths=[4*cm, 10*cm])
    personal_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), ECOSYSTEM_COLORS['light']),
        ('TEXTCOLOR', (0, 0), (-1, -1), ECOSYSTEM_COLORS['dark']),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, ECOSYSTEM_COLORS['light']]),
        ('GRID', (0, 0), (-1, -1), 1, ECOSYSTEM_COLORS['light'])
    ]))
    
    content.append(personal_table)
    content.append(Spacer(1, 20))
    
    # Información empresarial
    content.append(Paragraph("Información Empresarial", TEXT_STYLES['heading1']))
    
    business_data = [
        ['Empresa:', entrepreneur_data.get('company_name', 'N/A')],
        ['Sector:', entrepreneur_data.get('business_sector', 'N/A')],
        ['Experiencia:', f"{entrepreneur_data.get('experience_years', 0)} años"],
        ['Educación:', entrepreneur_data.get('education_level', 'N/A')],
        ['LinkedIn:', entrepreneur_data.get('linkedin_url', 'N/A')],
        ['Website:', entrepreneur_data.get('website_url', 'N/A')],
    ]
    
    business_table = Table(business_data, colWidths=[4*cm, 10*cm])
    business_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), ECOSYSTEM_COLORS['light']),
        ('TEXTCOLOR', (0, 0), (-1, -1), ECOSYSTEM_COLORS['dark']),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 0), (-1, -1), [colors.white, ECOSYSTEM_COLORS['light']]),
        ('GRID', (0, 0), (-1, -1), 1, ECOSYSTEM_COLORS['light'])
    ]))
    
    content.append(business_table)
    content.append(Spacer(1, 20))
    
    # Descripción
    if entrepreneur_data.get('description'):
        content.append(Paragraph("Descripción", TEXT_STYLES['heading1']))
        content.append(Paragraph(entrepreneur_data['description'], TEXT_STYLES['normal']))
        content.append(Spacer(1, 20))
    
    # Proyectos
    projects = entrepreneur_data.get('projects', [])
    if projects:
        content.append(Paragraph("Proyectos", TEXT_STYLES['heading1']))
        
        for i, project in enumerate(projects, 1):
            content.append(Paragraph(f"{i}. {project.get('name', 'Proyecto sin nombre')}", 
                                   TEXT_STYLES['heading2']))
            
            if project.get('description'):
                content.append(Paragraph(project['description'], TEXT_STYLES['normal']))
            
            project_details = [
                ['Sector:', project.get('business_sector', 'N/A')],
                ['Etapa:', project.get('stage', 'N/A')],
                ['Presupuesto:', f"${project.get('budget', 0):,.0f} {project.get('currency', 'COP')}"],
                ['Estado:', project.get('status', 'N/A')]
            ]
            
            project_table = Table(project_details, colWidths=[3*cm, 8*cm])
            project_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), ECOSYSTEM_COLORS['accent']),
                ('TEXTCOLOR', (0, 0), (-1, -1), ECOSYSTEM_COLORS['dark']),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('GRID', (0, 0), (-1, -1), 1, ECOSYSTEM_COLORS['light'])
            ]))
            
            content.append(project_table)
            content.append(Spacer(1, 15))
    
    # Generar PDF
    generator = PDFGenerator()
    return generator.generate_document(content, output_path, metadata)

def generate_business_plan(plan_data: dict[str, Any], 
                          output_path: Optional[str] = None) -> str:
    """
    Genera plan de negocio estructurado.
    
    Args:
        plan_data: Datos del plan de negocio
        output_path: Ruta de salida (opcional)
        
    Returns:
        Ruta del archivo generado
    """
    if not REPORTLAB_AVAILABLE:
        raise PDFError("ReportLab no está disponible")
    
    # Configurar salida
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"plan_negocio_{timestamp}.pdf"
        output_path = os.path.join(PDF_CONFIG['output_dir'], filename)
    
    # Metadatos
    metadata = PDFMetadata(
        title=f"Plan de Negocio - {plan_data.get('company_name', 'Empresa')}",
        subject="Plan de negocio detallado",
        keywords=['plan de negocio', 'emprendimiento', 'startup']
    )
    
    content = []
    
    # Portada
    content.append(Paragraph("PLAN DE NEGOCIO", TEXT_STYLES['title']))
    content.append(Spacer(1, 40))
    
    content.append(Paragraph(plan_data.get('company_name', 'Nombre de la Empresa'), 
                           TEXT_STYLES['heading1']))
    content.append(Spacer(1, 20))
    
    content.append(Paragraph(plan_data.get('business_sector', 'Sector'), 
                           TEXT_STYLES['heading2']))
    content.append(Spacer(1, 40))
    
    # Información del emprendedor
    if plan_data.get('entrepreneur_name'):
        content.append(Paragraph(f"Emprendedor: {plan_data['entrepreneur_name']}", 
                               TEXT_STYLES['normal']))
    
    content.append(Paragraph(f"Fecha: {datetime.now().strftime('%d de %B de %Y')}", 
                           TEXT_STYLES['normal']))
    
    content.append(PageBreak())
    
    # Índice (opcional - requiere configuración adicional)
    content.append(Paragraph("Índice", TEXT_STYLES['heading1']))
    
    toc_data = [
        ['1. Resumen Ejecutivo', '3'],
        ['2. Descripción del Negocio', '4'],
        ['3. Análisis de Mercado', '5'],
        ['4. Organización y Gestión', '6'],
        ['5. Productos o Servicios', '7'],
        ['6. Marketing y Ventas', '8'],
        ['7. Proyecciones Financieras', '9'],
        ['8. Apéndices', '10']
    ]
    
    toc_table = Table(toc_data, colWidths=[12*cm, 2*cm])
    toc_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
    ]))
    
    content.append(toc_table)
    content.append(PageBreak())
    
    # 1. Resumen Ejecutivo
    content.append(Paragraph("1. Resumen Ejecutivo", TEXT_STYLES['heading1']))
    content.append(Paragraph(
        plan_data.get('executive_summary', 'Resumen ejecutivo del plan de negocio...'),
        TEXT_STYLES['normal']
    ))
    content.append(Spacer(1, 20))
    
    # 2. Descripción del Negocio
    content.append(Paragraph("2. Descripción del Negocio", TEXT_STYLES['heading1']))
    
    content.append(Paragraph("2.1 Visión", TEXT_STYLES['heading2']))
    content.append(Paragraph(
        plan_data.get('vision', 'Declaración de visión de la empresa...'),
        TEXT_STYLES['normal']
    ))
    
    content.append(Paragraph("2.2 Misión", TEXT_STYLES['heading2']))
    content.append(Paragraph(
        plan_data.get('mission', 'Declaración de misión de la empresa...'),
        TEXT_STYLES['normal']
    ))
    
    content.append(Paragraph("2.3 Objetivos", TEXT_STYLES['heading2']))
    objectives = plan_data.get('objectives', [])
    if objectives:
        for i, objective in enumerate(objectives, 1):
            content.append(Paragraph(f"{i}. {objective}", TEXT_STYLES['normal']))
    else:
        content.append(Paragraph("Objetivos de la empresa...", TEXT_STYLES['normal']))
    
    content.append(Spacer(1, 20))
    
    # 3. Análisis de Mercado
    content.append(Paragraph("3. Análisis de Mercado", TEXT_STYLES['heading1']))
    content.append(Paragraph(
        plan_data.get('market_analysis', 'Análisis detallado del mercado objetivo...'),
        TEXT_STYLES['normal']
    ))
    
    # Mercado objetivo
    if plan_data.get('target_market'):
        content.append(Paragraph("3.1 Mercado Objetivo", TEXT_STYLES['heading2']))
        content.append(Paragraph(plan_data['target_market'], TEXT_STYLES['normal']))
    
    content.append(Spacer(1, 20))
    
    # 4. Productos o Servicios
    content.append(Paragraph("4. Productos o Servicios", TEXT_STYLES['heading1']))
    content.append(Paragraph(
        plan_data.get('products_services', 'Descripción de productos y servicios...'),
        TEXT_STYLES['normal']
    ))
    
    content.append(Spacer(1, 20))
    
    # 5. Proyecciones Financieras
    content.append(Paragraph("5. Proyecciones Financieras", TEXT_STYLES['heading1']))
    
    financial_data = plan_data.get('financial_projections', {})
    if financial_data:
        # Crear tabla de proyecciones
        years = financial_data.get('years', ['Año 1', 'Año 2', 'Año 3'])
        revenues = financial_data.get('revenues', [0, 0, 0])
        expenses = financial_data.get('expenses', [0, 0, 0])
        profits = [r - e for r, e in zip(revenues, expenses)]
        
        financial_table_data = [
            ['Concepto'] + years,
            ['Ingresos'] + [f"${r:,.0f}" for r in revenues],
            ['Gastos'] + [f"${e:,.0f}" for e in expenses],
            ['Utilidad'] + [f"${p:,.0f}" for p in profits]
        ]
        
        financial_table = Table(financial_table_data)
        financial_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), ECOSYSTEM_COLORS['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('BACKGROUND', (0, 1), (0, -1), ECOSYSTEM_COLORS['light']),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, ECOSYSTEM_COLORS['dark'])
        ]))
        
        content.append(financial_table)
    else:
        content.append(Paragraph("Proyecciones financieras a desarrollar...", 
                               TEXT_STYLES['normal']))
    
    # Generar PDF
    generator = PDFGenerator()
    return generator.generate_document(content, output_path, metadata)

def generate_certificate(participant_name: str,
                        program_name: str,
                        completion_date: Union[str, date],
                        output_path: Optional[str] = None,
                        certificate_type: str = "participación") -> str:
    """
    Genera certificado de participación o completación.
    
    Args:
        participant_name: Nombre del participante
        program_name: Nombre del programa
        completion_date: Fecha de completación
        output_path: Ruta de salida (opcional)
        certificate_type: Tipo de certificado
        
    Returns:
        Ruta del archivo generado
        
    Examples:
        >>> certificate_path = generate_certificate(
        ...     "Juan Pérez",
        ...     "Programa de Aceleración TechStart 2024",
        ...     "2024-12-13"
        ... )
    """
    if not REPORTLAB_AVAILABLE:
        raise PDFError("ReportLab no está disponible")
    
    # Configurar salida
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe_name = participant_name.replace(' ', '_').replace('/', '_')
        filename = f"certificado_{safe_name}_{timestamp}.pdf"
        output_path = os.path.join(PDF_CONFIG['output_dir'], filename)
    
    # Configurar página en orientación horizontal
    settings = PDFSettings(
        page_size=A4,
        orientation=PageOrientation.LANDSCAPE,
        include_header=False,
        include_footer=False,
        include_page_numbers=False
    )
    
    # Metadatos
    metadata = PDFMetadata(
        title=f"Certificado - {participant_name}",
        subject=f"Certificado de {certificate_type}",
        keywords=['certificado', 'emprendimiento', 'programa']
    )
    
    # Crear contenido
    content = []
    
    # Configurar estilos específicos para certificado
    certificate_title_style = ParagraphStyle(
        'CertificateTitle',
        parent=TEXT_STYLES['title'],
        fontSize=24,
        textColor=ECOSYSTEM_COLORS['primary'],
        alignment=1,  # Centrado
        spaceAfter=30
    )
    
    certificate_subtitle_style = ParagraphStyle(
        'CertificateSubtitle',
        parent=TEXT_STYLES['heading1'],
        fontSize=18,
        textColor=ECOSYSTEM_COLORS['dark'],
        alignment=1,
        spaceAfter=20
    )
    
    certificate_name_style = ParagraphStyle(
        'CertificateName',
        parent=TEXT_STYLES['heading1'],
        fontSize=20,
        textColor=ECOSYSTEM_COLORS['secondary'],
        alignment=1,
        spaceAfter=30,
        fontName='Helvetica-Bold'
    )
    
    certificate_body_style = ParagraphStyle(
        'CertificateBody',
        parent=TEXT_STYLES['normal'],
        fontSize=14,
        textColor=ECOSYSTEM_COLORS['dark'],
        alignment=1,
        spaceAfter=20
    )
    
    # Espaciado superior
    content.append(Spacer(1, 60))
    
    # Título del certificado
    content.append(Paragraph("CERTIFICADO", certificate_title_style))
    
    # Subtítulo
    tipo_texto = {
        "participación": "de Participación",
        "completación": "de Completación",
        "excelencia": "de Excelencia",
        "logro": "de Logro"
    }.get(certificate_type, "de Participación")
    
    content.append(Paragraph(tipo_texto, certificate_subtitle_style))
    
    # Texto principal
    content.append(Paragraph("Se otorga el presente certificado a:", certificate_body_style))
    
    # Nombre del participante
    content.append(Paragraph(participant_name.upper(), certificate_name_style))
    
    # Descripción del programa
    program_text = f"Por su {certificate_type} en el programa:"
    content.append(Paragraph(program_text, certificate_body_style))
    
    content.append(Paragraph(f"<b>{program_name}</b>", certificate_body_style))
    
    # Fecha
    if isinstance(completion_date, str):
        try:
            completion_date = datetime.strptime(completion_date, '%Y-%m-%d').date()
        except ValueError:
            pass
    
    if isinstance(completion_date, date):
        date_text = completion_date.strftime('%d de %B de %Y')
    else:
        date_text = str(completion_date)
    
    content.append(Spacer(1, 40))
    content.append(Paragraph(f"Otorgado el {date_text}", certificate_body_style))
    
    # Espaciado para firmas
    content.append(Spacer(1, 60))
    
    # Crear tabla para firmas
    signature_data = [
        ['_' * 30, '_' * 30],
        ['Director del Programa', 'Coordinador Académico'],
        ['Ecosistema de Emprendimiento', 'Ecosistema de Emprendimiento']
    ]
    
    signature_table = Table(signature_data, colWidths=[8*cm, 8*cm])
    signature_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('TEXTCOLOR', (0, 1), (-1, -1), ECOSYSTEM_COLORS['dark']),
        ('TOPPADDING', (0, 1), (-1, 1), 10),
        ('BOTTOMPADDING', (0, 2), (-1, 2), 5),
    ]))
    
    content.append(signature_table)
    
    # Generar PDF
    generator = PDFGenerator(settings)
    return generator.generate_document(content, output_path, metadata)

def generate_invoice(invoice_data: dict[str, Any], 
                    output_path: Optional[str] = None) -> str:
    """
    Genera factura o presupuesto.
    
    Args:
        invoice_data: Datos de la factura
        output_path: Ruta de salida (opcional)
        
    Returns:
        Ruta del archivo generado
    """
    if not REPORTLAB_AVAILABLE:
        raise PDFError("ReportLab no está disponible")
    
    # Configurar salida
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        invoice_number = invoice_data.get('invoice_number', 'FACT001')
        filename = f"factura_{invoice_number}_{timestamp}.pdf"
        output_path = os.path.join(PDF_CONFIG['output_dir'], filename)
    
    # Metadatos
    metadata = PDFMetadata(
        title=f"Factura {invoice_data.get('invoice_number', '')}",
        subject="Factura de servicios",
        keywords=['factura', 'servicios', 'emprendimiento']
    )
    
    content = []
    
    # Header con información de la empresa
    company_info = [
        [Paragraph("<b>ECOSISTEMA DE EMPRENDIMIENTO</b>", TEXT_STYLES['heading1']), ''],
        ['NIT: 900.123.456-7', ''],
        ['Dirección: Calle 123 #45-67', ''],
        ['Bogotá, Colombia', ''],
        ['Tel: +57 (1) 234-5678', ''],
        ['email@ecosistema.com', '']
    ]
    
    # Información de la factura (lado derecho)
    invoice_info = [
        ['', Paragraph(f"<b>FACTURA #{invoice_data.get('invoice_number', 'FACT001')}</b>", 
                      TEXT_STYLES['heading2'])],
        ['', f"Fecha: {invoice_data.get('date', datetime.now().strftime('%d/%m/%Y'))}"],
        ['', f"Vencimiento: {invoice_data.get('due_date', 'N/A')}"],
        ['', f"Estado: {invoice_data.get('status', 'Pendiente')}"],
        ['', ''],
        ['', '']
    ]
    
    # Combinar información
    header_data = []
    for i in range(len(company_info)):
        row = [company_info[i][0], invoice_info[i][1]]
        header_data.append(row)
    
    header_table = Table(header_data, colWidths=[10*cm, 8*cm])
    header_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (0, -1), 'LEFT'),
        ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    content.append(header_table)
    content.append(Spacer(1, 30))
    
    # Información del cliente
    content.append(Paragraph("FACTURAR A:", TEXT_STYLES['heading2']))
    
    client_data = [
        ['Cliente:', invoice_data.get('client_name', 'N/A')],
        ['Documento:', invoice_data.get('client_document', 'N/A')],
        ['Dirección:', invoice_data.get('client_address', 'N/A')],
        ['Email:', invoice_data.get('client_email', 'N/A')],
        ['Teléfono:', invoice_data.get('client_phone', 'N/A')],
    ]
    
    client_table = Table(client_data, colWidths=[3*cm, 10*cm])
    client_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), ECOSYSTEM_COLORS['light']),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, ECOSYSTEM_COLORS['light'])
    ]))
    
    content.append(client_table)
    content.append(Spacer(1, 30))
    
    # Detalles de la factura
    content.append(Paragraph("DETALLES:", TEXT_STYLES['heading2']))
    
    # Cabecera de la tabla de items
    items_data = [
        ['Descripción', 'Cantidad', 'Precio Unitario', 'Total']
    ]
    
    # Items de la factura
    items = invoice_data.get('items', [])
    subtotal = 0
    
    for item in items:
        description = item.get('description', 'Servicio')
        quantity = item.get('quantity', 1)
        unit_price = item.get('unit_price', 0)
        total = quantity * unit_price
        subtotal += total
        
        items_data.append([
            description,
            str(quantity),
            f"${unit_price:,.0f}",
            f"${total:,.0f}"
        ])
    
    # Calcular impuestos y total
    tax_rate = invoice_data.get('tax_rate', 0.19)  # IVA 19%
    tax_amount = subtotal * tax_rate
    total_amount = subtotal + tax_amount
    
    # Agregar filas de totales
    items_data.extend([
        ['', '', 'Subtotal:', f"${subtotal:,.0f}"],
        ['', '', f'IVA ({tax_rate*100:.0f}%):', f"${tax_amount:,.0f}"],
        ['', '', 'TOTAL:', f"${total_amount:,.0f}"]
    ])
    
    items_table = Table(items_data, colWidths=[8*cm, 2*cm, 3*cm, 3*cm])
    items_table.setStyle(TableStyle([
        # Header
        ('BACKGROUND', (0, 0), (-1, 0), ECOSYSTEM_COLORS['primary']),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        
        # Body
        ('FONTNAME', (0, 1), (-1, -4), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 1), (0, -1), 'LEFT'),
        
        # Totals section
        ('BACKGROUND', (-3, -3), (-1, -1), ECOSYSTEM_COLORS['light']),
        ('FONTNAME', (-2, -1), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (-2, -1), (-1, -1), 11),
        
        # Grid
        ('GRID', (0, 0), (-1, -4), 1, ECOSYSTEM_COLORS['dark']),
        ('LINEBELOW', (0, -4), (-1, -4), 2, ECOSYSTEM_COLORS['dark']),
    ]))
    
    content.append(items_table)
    content.append(Spacer(1, 30))
    
    # Términos y condiciones
    if invoice_data.get('terms'):
        content.append(Paragraph("TÉRMINOS Y CONDICIONES:", TEXT_STYLES['heading2']))
        content.append(Paragraph(invoice_data['terms'], TEXT_STYLES['small']))
        content.append(Spacer(1, 20))
    
    # Información de pago
    if invoice_data.get('payment_info'):
        content.append(Paragraph("INFORMACIÓN DE PAGO:", TEXT_STYLES['heading2']))
        content.append(Paragraph(invoice_data['payment_info'], TEXT_STYLES['normal']))
    
    # Generar PDF
    generator = PDFGenerator()
    return generator.generate_document(content, output_path, metadata)

def generate_mentorship_report(mentorship_data: dict[str, Any], 
                             output_path: Optional[str] = None) -> str:
    """
    Genera reporte de sesión de mentoría.
    
    Args:
        mentorship_data: Datos de la mentoría
        output_path: Ruta de salida (opcional)
        
    Returns:
        Ruta del archivo generado
    """
    if not REPORTLAB_AVAILABLE:
        raise PDFError("ReportLab no está disponible")
    
    # Configurar salida
    if not output_path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"reporte_mentoria_{timestamp}.pdf"
        output_path = os.path.join(PDF_CONFIG['output_dir'], filename)
    
    # Metadatos
    metadata = PDFMetadata(
        title="Reporte de Mentoría",
        subject="Sesión de mentoría",
        keywords=['mentoría', 'sesión', 'emprendimiento']
    )
    
    content = []
    
    # Título
    content.append(Paragraph("REPORTE DE MENTORÍA", TEXT_STYLES['title']))
    content.append(Spacer(1, 20))
    
    # Información general
    general_data = [
        ['Fecha:', mentorship_data.get('date', 'N/A')],
        ['Duración:', f"{mentorship_data.get('duration', 0)} minutos"],
        ['Mentor:', mentorship_data.get('mentor_name', 'N/A')],
        ['Emprendedor:', mentorship_data.get('entrepreneur_name', 'N/A')],
        ['Empresa:', mentorship_data.get('company_name', 'N/A')],
        ['Tipo de sesión:', mentorship_data.get('session_type', 'Regular')]
    ]
    
    general_table = Table(general_data, colWidths=[4*cm, 10*cm])
    general_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, -1), ECOSYSTEM_COLORS['light']),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, ECOSYSTEM_COLORS['light'])
    ]))
    
    content.append(general_table)
    content.append(Spacer(1, 20))
    
    # Objetivos de la sesión
    content.append(Paragraph("Objetivos de la Sesión", TEXT_STYLES['heading1']))
    objectives = mentorship_data.get('objectives', [])
    if objectives:
        for i, objective in enumerate(objectives, 1):
            content.append(Paragraph(f"{i}. {objective}", TEXT_STYLES['normal']))
    else:
        content.append(Paragraph("No se definieron objetivos específicos.", TEXT_STYLES['normal']))
    
    content.append(Spacer(1, 15))
    
    # Temas tratados
    content.append(Paragraph("Temas Tratados", TEXT_STYLES['heading1']))
    topics = mentorship_data.get('topics_discussed', 'No se registraron temas específicos.')
    content.append(Paragraph(topics, TEXT_STYLES['normal']))
    content.append(Spacer(1, 15))
    
    # Recomendaciones
    content.append(Paragraph("Recomendaciones", TEXT_STYLES['heading1']))
    recommendations = mentorship_data.get('recommendations', 'No se registraron recomendaciones específicas.')
    content.append(Paragraph(recommendations, TEXT_STYLES['normal']))
    content.append(Spacer(1, 15))
    
    # Próximos pasos
    content.append(Paragraph("Próximos Pasos", TEXT_STYLES['heading1']))
    next_steps = mentorship_data.get('next_steps', [])
    if next_steps:
        for i, step in enumerate(next_steps, 1):
            content.append(Paragraph(f"{i}. {step}", TEXT_STYLES['normal']))
    else:
        content.append(Paragraph("No se definieron próximos pasos específicos.", TEXT_STYLES['normal']))
    
    content.append(Spacer(1, 15))
    
    # Evaluación
    if mentorship_data.get('evaluation'):
        content.append(Paragraph("Evaluación", TEXT_STYLES['heading1']))
        
        eval_data = mentorship_data['evaluation']
        evaluation_items = [
            ['Aspecto', 'Calificación', 'Comentarios'],
            ['Claridad de objetivos', str(eval_data.get('clarity', 'N/A')), eval_data.get('clarity_comments', '')],
            ['Utilidad del contenido', str(eval_data.get('usefulness', 'N/A')), eval_data.get('usefulness_comments', '')],
            ['Satisfacción general', str(eval_data.get('satisfaction', 'N/A')), eval_data.get('satisfaction_comments', '')]
        ]
        
        eval_table = Table(evaluation_items, colWidths=[5*cm, 3*cm, 6*cm])
        eval_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), ECOSYSTEM_COLORS['primary']),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('GRID', (0, 0), (-1, -1), 1, ECOSYSTEM_COLORS['dark'])
        ]))
        
        content.append(eval_table)
        content.append(Spacer(1, 15))
    
    # Firma del mentor
    content.append(Spacer(1, 30))
    content.append(Paragraph("_" * 40, TEXT_STYLES['normal']))
    content.append(Paragraph(f"Firma del Mentor: {mentorship_data.get('mentor_name', 'N/A')}", 
                           TEXT_STYLES['normal']))
    
    # Generar PDF
    generator = PDFGenerator()
    return generator.generate_document(content, output_path, metadata)

# ==============================================================================
# UTILIDADES DE GRÁFICOS Y VISUALIZACIONES
# ==============================================================================

def create_business_chart(data: dict[str, Any], chart_type: str = 'bar') -> Drawing:
    """
    Crea gráfico para documentos de negocio.
    
    Args:
        data: Datos del gráfico
        chart_type: Tipo de gráfico (bar, pie, line)
        
    Returns:
        Drawing object para incluir en PDF
    """
    if not REPORTLAB_AVAILABLE:
        raise PDFError("ReportLab no está disponible")
    
    drawing = Drawing(400, 200)
    
    if chart_type == 'bar':
        chart = VerticalBarChart()
        chart.x = 50
        chart.y = 50
        chart.height = 125
        chart.width = 300
        
        chart.data = [data.get('values', [10, 20, 30, 40])]
        chart.categoryAxis.categoryNames = data.get('labels', ['A', 'B', 'C', 'D'])
        
        chart.bars[0].fillColor = ECOSYSTEM_COLORS['primary']
        chart.valueAxis.valueMin = 0
        chart.valueAxis.valueMax = max(data.get('values', [40])) * 1.1
        
        drawing.add(chart)
    
    elif chart_type == 'pie':
        chart = Pie()
        chart.x = 150
        chart.y = 65
        chart.width = 100
        chart.height = 100
        
        chart.data = data.get('values', [10, 20, 30, 40])
        chart.labels = data.get('labels', ['A', 'B', 'C', 'D'])
        
        # Colores para el pie chart
        colors_list = [
            ECOSYSTEM_COLORS['primary'],
            ECOSYSTEM_COLORS['secondary'],
            ECOSYSTEM_COLORS['accent'],
            ECOSYSTEM_COLORS['success']
        ]
        chart.slices.fillColor = colors_list[0]
        for i, color in enumerate(colors_list[:len(chart.data)]):
            chart.slices[i].fillColor = color
        
        drawing.add(chart)
    
    return drawing

def add_qr_code(content: str, size: float = 2*cm) -> Image:
    """
    Genera código QR para incluir en PDF.
    
    Args:
        content: Contenido del QR
        size: Tamaño del QR
        
    Returns:
        Image object para PDF
    """
    if not QRCODE_AVAILABLE:
        raise PDFError("qrcode library no está disponible")
    
    # Generar QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(content)
    qr.make(fit=True)
    
    # Crear imagen
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # Convertir a formato compatible con ReportLab
    buffer = io.BytesIO()
    qr_img.save(buffer, format='PNG')
    buffer.seek(0)
    
    return Image(buffer, width=size, height=size)

# ==============================================================================
# UTILIDADES DE MANIPULACIÓN DE PDF
# ==============================================================================

def merge_pdfs(pdf_paths: list[str], output_path: str) -> str:
    """
    Une múltiples PDFs en uno solo.
    
    Args:
        pdf_paths: Lista de rutas de PDFs a unir
        output_path: Ruta del PDF resultante
        
    Returns:
        Ruta del archivo generado
    """
    try:
        from PyPDF2 import PdfMerger
        
        merger = PdfMerger()
        
        for pdf_path in pdf_paths:
            if os.path.exists(pdf_path):
                merger.append(pdf_path)
            else:
                logger.warning(f"PDF no encontrado: {pdf_path}")
        
        merger.write(output_path)
        merger.close()
        
        logger.info(f"PDFs unidos en: {output_path}")
        return output_path
        
    except ImportError:
        logger.error("PyPDF2 no está disponible para unir PDFs")
        raise PDFError("PyPDF2 requerido para unir PDFs")
    except Exception as e:
        logger.error(f"Error uniendo PDFs: {e}")
        raise PDFError(f"Error uniendo PDFs: {e}")

def split_pdf(pdf_path: str, output_dir: str, pages_per_file: int = 1) -> list[str]:
    """
    Divide un PDF en múltiples archivos.
    
    Args:
        pdf_path: Ruta del PDF a dividir
        output_dir: Directorio de salida
        pages_per_file: Páginas por archivo
        
    Returns:
        Lista de rutas de archivos generados
    """
    try:
        from PyPDF2 import PdfReader, PdfWriter
        
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        
        output_files = []
        base_name = os.path.splitext(os.path.basename(pdf_path))[0]
        
        for start_page in range(0, total_pages, pages_per_file):
            writer = PdfWriter()
            end_page = min(start_page + pages_per_file, total_pages)
            
            for page_num in range(start_page, end_page):
                writer.add_page(reader.pages[page_num])
            
            output_filename = f"{base_name}_part_{start_page + 1}-{end_page}.pdf"
            output_path = os.path.join(output_dir, output_filename)
            
            with open(output_path, 'wb') as output_file:
                writer.write(output_file)
            
            output_files.append(output_path)
        
        logger.info(f"PDF dividido en {len(output_files)} archivos")
        return output_files
        
    except ImportError:
        logger.error("PyPDF2 no está disponible para dividir PDFs")
        raise PDFError("PyPDF2 requerido para dividir PDFs")
    except Exception as e:
        logger.error(f"Error dividiendo PDF: {e}")
        raise PDFError(f"Error dividiendo PDF: {e}")

def add_watermark_to_pdf(pdf_path: str, watermark_text: str, 
                        output_path: str) -> str:
    """
    Añade watermark a PDF existente.
    
    Args:
        pdf_path: Ruta del PDF original
        watermark_text: Texto del watermark
        output_path: Ruta del PDF con watermark
        
    Returns:
        Ruta del archivo generado
    """
    try:
        from PyPDF2 import PdfReader, PdfWriter
        
        # Crear watermark
        watermark_buffer = io.BytesIO()
        
        c = canvas.Canvas(watermark_buffer, pagesize=A4)
        c.setFillColor(colors.grey)
        c.setFillAlpha(0.3)
        c.setFont("Helvetica-Bold", 50)
        
        # Rotar y centrar watermark
        c.translate(A4[0]/2, A4[1]/2)
        c.rotate(45)
        
        text_width = c.stringWidth(watermark_text, "Helvetica-Bold", 50)
        c.drawString(-text_width/2, 0, watermark_text)
        c.save()
        
        watermark_buffer.seek(0)
        watermark_reader = PdfReader(watermark_buffer)
        watermark_page = watermark_reader.pages[0]
        
        # Aplicar watermark al PDF original
        reader = PdfReader(pdf_path)
        writer = PdfWriter()
        
        for page in reader.pages:
            page.merge_page(watermark_page)
            writer.add_page(page)
        
        with open(output_path, 'wb') as output_file:
            writer.write(output_file)
        
        logger.info(f"Watermark añadido: {output_path}")
        return output_path
        
    except ImportError:
        logger.error("PyPDF2 no está disponible para watermarks")
        raise PDFError("PyPDF2 requerido para watermarks")
    except Exception as e:
        logger.error(f"Error añadiendo watermark: {e}")
        raise PDFError(f"Error añadiendo watermark: {e}")

# ==============================================================================
# FUNCIONES DE UTILIDAD Y CONFIGURACIÓN
# ==============================================================================

def configure_pdf_settings(**kwargs):
    """Configura opciones globales de PDF."""
    PDF_CONFIG.update(kwargs)
    logger.info("Configuración de PDF actualizada")

def get_pdf_info() -> dict[str, Any]:
    """Obtiene información sobre capacidades de PDF."""
    return {
        'reportlab_available': REPORTLAB_AVAILABLE,
        'matplotlib_available': MATPLOTLIB_AVAILABLE,
        'pil_available': PIL_AVAILABLE,
        'qrcode_available': QRCODE_AVAILABLE,
        'supported_formats': ['PDF'],
        'supported_charts': ['bar', 'pie', 'line'] if REPORTLAB_AVAILABLE else [],
        'config': PDF_CONFIG.copy()
    }

def validate_pdf_dependencies():
    """Valida dependencias para generación de PDF."""
    missing_deps = []
    
    if not REPORTLAB_AVAILABLE:
        missing_deps.append('reportlab')
    
    if missing_deps:
        logger.warning(f"Dependencias faltantes para PDF: {missing_deps}")
        return False
    
    return True

# Validar dependencias al importar
if not validate_pdf_dependencies():
    logger.warning("Funcionalidad PDF limitada - instala 'reportlab' para funcionalidad completa")

# Crear directorio de salida
try:
    output_dir = Path(PDF_CONFIG['output_dir'])
    output_dir.mkdir(exist_ok=True)
    logger.info(f"Directorio de PDFs configurado: {output_dir}")
except Exception as e:
    logger.warning(f"No se pudo crear directorio de PDFs: {e}")

logger.info("Módulo de utilidades PDF inicializado")