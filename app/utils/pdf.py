# app/utils/pdf.py

import os
import uuid
from datetime import datetime
from flask import current_app, render_template, url_for
import pdfkit
from weasyprint import HTML, CSS
from io import BytesIO
import base64
import logging
import tempfile
from xhtml2pdf import pisa
from app.utils.formatters import format_date, format_currency

logger = logging.getLogger(__name__)

class PDFGenerator:
    """Clase para generar documentos PDF."""

    def __init__(self, use_weasyprint=True):
        """
        Inicializa el generador de PDF.
        
        Args:
            use_weasyprint (bool): Si es True, usa WeasyPrint, si es False, usa wkhtmltopdf
        """
        self.use_weasyprint = use_weasyprint
        
    def generate_from_template(self, template_path, output_path=None, **context):
        """
        Genera un PDF a partir de una plantilla HTML.
        
        Args:
            template_path (str): Ruta de la plantilla HTML
            output_path (str): Ruta donde guardar el PDF generado (opcional)
            **context: Variables de contexto para la plantilla
            
        Returns:
            bytes/str: Contenido del PDF en bytes o ruta del archivo según output_path
        """
        try:
            # Renderizar plantilla HTML con contexto
            html_content = render_template(template_path, **context)
            
            # Generar PDF según el motor seleccionado
            if self.use_weasyprint:
                return self._generate_with_weasyprint(html_content, output_path)
            else:
                return self._generate_with_wkhtmltopdf(html_content, output_path)
        except Exception as e:
            logger.error(f"Error al generar PDF desde plantilla: {str(e)}")
            raise

    def _generate_with_weasyprint(self, html_content, output_path=None):
        """
        Genera un PDF usando WeasyPrint.
        
        Args:
            html_content (str): Contenido HTML
            output_path (str): Ruta donde guardar el PDF (opcional)
            
        Returns:
            bytes/str: Contenido del PDF en bytes o ruta del archivo según output_path
        """
        try:
            # Configurar CSS
            css_files = [
                os.path.join(current_app.static_folder, 'css/bootstrap.min.css'),
                os.path.join(current_app.static_folder, 'css/pdf.css')
            ]
            
            # Generar el PDF
            html = HTML(string=html_content, base_url=current_app.config['BASE_URL'])
            css = [CSS(filename=css_file) for css_file in css_files if os.path.exists(css_file)]
            
            if output_path:
                # Guardar el PDF en la ruta especificada
                html.write_pdf(output_path, stylesheets=css)
                return output_path
            else:
                # Devolver el contenido del PDF en bytes
                return html.write_pdf(stylesheets=css)
        except Exception as e:
            logger.error(f"Error en WeasyPrint: {str(e)}")
            raise

    def _generate_with_wkhtmltopdf(self, html_content, output_path=None):
        """
        Genera un PDF usando wkhtmltopdf.
        
        Args:
            html_content (str): Contenido HTML
            output_path (str): Ruta donde guardar el PDF (opcional)
            
        Returns:
            bytes/str: Contenido del PDF en bytes o ruta del archivo según output_path
        """
        try:
            # Configurar opciones para wkhtmltopdf
            options = {
                'page-size': 'Letter',
                'margin-top': '0.75in',
                'margin-right': '0.75in',
                'margin-bottom': '0.75in',
                'margin-left': '0.75in',
                'encoding': 'UTF-8',
                'enable-local-file-access': None
            }
            
            # Si hay path de configuración en la app, usarlo
            if current_app.config.get('WKHTMLTOPDF_PATH'):
                config = pdfkit.configuration(wkhtmltopdf=current_app.config['WKHTMLTOPDF_PATH'])
                
                if output_path:
                    # Guardar el PDF en la ruta especificada
                    pdfkit.from_string(html_content, output_path, options=options, configuration=config)
                    return output_path
                else:
                    # Devolver el contenido del PDF en bytes
                    return pdfkit.from_string(html_content, False, options=options, configuration=config)
            else:
                if output_path:
                    # Guardar el PDF en la ruta especificada
                    pdfkit.from_string(html_content, output_path, options=options)
                    return output_path
                else:
                    # Devolver el contenido del PDF en bytes
                    return pdfkit.from_string(html_content, False, options=options)
        except Exception as e:
            logger.error(f"Error en wkhtmltopdf: {str(e)}")
            raise

    def _generate_with_xhtml2pdf(self, html_content, output_path=None):
        """
        Genera un PDF usando xhtml2pdf (alternativa si los otros métodos fallan).
        
        Args:
            html_content (str): Contenido HTML
            output_path (str): Ruta donde guardar el PDF (opcional)
            
        Returns:
            bytes/str: Contenido del PDF en bytes o ruta del archivo según output_path
        """
        try:
            if output_path:
                # Guardar el PDF en un archivo
                with open(output_path, "wb") as output_file:
                    pisa.CreatePDF(html_content, dest=output_file)
                return output_path
            else:
                # Devolver el contenido del PDF en bytes
                result = BytesIO()
                pisa.CreatePDF(html_content, dest=result)
                return result.getvalue()
        except Exception as e:
            logger.error(f"Error en xhtml2pdf: {str(e)}")
            raise


def generate_pdf(template_path, output_path=None, **context):
    """
    Función auxiliar para generar un PDF a partir de una plantilla.
    
    Args:
        template_path (str): Ruta de la plantilla HTML
        output_path (str): Ruta donde guardar el PDF generado (opcional)
        **context: Variables de contexto para la plantilla
        
    Returns:
        bytes/str: Contenido del PDF en bytes o ruta del archivo según output_path
    """
    generator = PDFGenerator(use_weasyprint=current_app.config.get('USE_WEASYPRINT', True))
    return generator.generate_from_template(template_path, output_path, **context)


def generate_report_pdf(report_type, data, user=None, output_path=None):
    """
    Genera un PDF de reporte basado en el tipo y datos proporcionados.
    
    Args:
        report_type (str): Tipo de reporte ('entrepreneur_progress', 'ally_hours', etc.)
        data (dict): Datos para incluir en el reporte
        user (User): Usuario que genera el reporte (opcional)
        output_path (str): Ruta donde guardar el PDF (opcional)
        
    Returns:
        bytes/str: Contenido del PDF en bytes o ruta del archivo según output_path
    """
    # Mapeo de tipos de reporte a plantillas
    report_templates = {
        'entrepreneur_progress': 'reports/entrepreneur_progress.html',
        'ally_hours': 'reports/ally_hours.html',
        'impact_summary': 'reports/impact_summary.html',
        'client_report': 'reports/client_report.html'
    }
    
    # Verificar si el tipo de reporte es válido
    if report_type not in report_templates:
        raise ValueError(f"Tipo de reporte no válido: {report_type}")
    
    # Preparar contexto para la plantilla
    context = {
        'data': data,
        'user': user,
        'generated_at': datetime.now(),
        'report_type': report_type,
        'company_name': current_app.config.get('COMPANY_NAME', 'Emprendimiento App')
    }
    
    # Generar el PDF con la plantilla correspondiente
    return generate_pdf(report_templates[report_type], output_path, **context)


def generate_certificate_pdf(certificate_type, recipient, **context):
    """
    Genera un certificado en PDF.
    
    Args:
        certificate_type (str): Tipo de certificado ('completion', 'achievement', etc.)
        recipient (dict): Información del destinatario
        **context: Variables adicionales para la plantilla
        
    Returns:
        bytes: Contenido del PDF en bytes
    """
    # Mapeo de tipos de certificado a plantillas
    certificate_templates = {
        'completion': 'certificates/completion.html',
        'achievement': 'certificates/achievement.html',
        'participation': 'certificates/participation.html'
    }
    
    # Verificar si el tipo de certificado es válido
    if certificate_type not in certificate_templates:
        raise ValueError(f"Tipo de certificado no válido: {certificate_type}")
    
    # Generar nombre de archivo único
    filename = f"certificado_{certificate_type}_{uuid.uuid4().hex}.pdf"
    output_path = os.path.join(
        current_app.config['UPLOAD_FOLDER'], 
        'certificates', 
        filename
    )
    
    # Asegurar que el directorio existe
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    
    # Preparar contexto para la plantilla
    template_context = {
        'recipient': recipient,
        'certificate_type': certificate_type,
        'issue_date': datetime.now(),
        'certificate_id': uuid.uuid4().hex[:8].upper(),
        'company_name': current_app.config.get('COMPANY_NAME', 'Emprendimiento App'),
        'company_logo_url': url_for('static', filename='images/logo.png'),
        'signature_url': url_for('static', filename='images/signature.png')
    }
    
    # Agregar contexto adicional
    template_context.update(context)
    
    # Generar el PDF
    generate_pdf(certificate_templates[certificate_type], output_path, **template_context)
    
    # Devolver ruta relativa para acceder al certificado
    return filename


def merge_pdfs(pdf_files, output_path):
    """
    Combina múltiples archivos PDF en uno solo.
    
    Args:
        pdf_files (list): Lista de rutas de archivos PDF a combinar
        output_path (str): Ruta donde guardar el PDF resultante
        
    Returns:
        str: Ruta del archivo PDF resultante
    """
    try:
        from PyPDF2 import PdfMerger
        
        merger = PdfMerger()
        
        # Agregar cada archivo PDF al merger
        for pdf_file in pdf_files:
            merger.append(pdf_file)
        
        # Guardar el PDF combinado
        merger.write(output_path)
        merger.close()
        
        return output_path
    except Exception as e:
        logger.error(f"Error al combinar PDFs: {str(e)}")
        raise


def html_to_pdf_string(html_content):
    """
    Convierte contenido HTML a un string base64 para embeber en una página.
    
    Args:
        html_content (str): Contenido HTML a convertir
        
    Returns:
        str: String base64 del PDF
    """
    try:
        # Generar PDF
        generator = PDFGenerator(use_weasyprint=True)
        pdf_bytes = generator._generate_with_weasyprint(html_content)
        
        # Convertir a base64
        base64_pdf = base64.b64encode(pdf_bytes).decode('utf-8')
        return f"data:application/pdf;base64,{base64_pdf}"
    except Exception as e:
        logger.error(f"Error al convertir HTML a PDF base64: {str(e)}")
        raise


def create_invoice_pdf(invoice_data, output_path=None):
    """
    Crea un PDF de factura a partir de los datos proporcionados.
    
    Args:
        invoice_data (dict): Datos de la factura
        output_path (str): Ruta donde guardar el PDF (opcional)
        
    Returns:
        bytes/str: Contenido del PDF en bytes o ruta del archivo
    """
    # Preparar contexto para la plantilla
    context = {
        'invoice': invoice_data,
        'company': {
            'name': current_app.config.get('COMPANY_NAME', 'Emprendimiento App'),
            'address': current_app.config.get('COMPANY_ADDRESS', ''),
            'phone': current_app.config.get('COMPANY_PHONE', ''),
            'email': current_app.config.get('COMPANY_EMAIL', ''),
            'tax_id': current_app.config.get('COMPANY_TAX_ID', '')
        },
        'format_date': format_date,
        'format_currency': format_currency
    }
    
    # Generar el PDF
    return generate_pdf('invoices/invoice.html', output_path, **context)