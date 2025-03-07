"""
Servicio de Email para la aplicación de emprendimiento.
Proporciona funcionalidades para enviar correos electrónicos usando SMTP o servicios externos.
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from flask import current_app, render_template
from threading import Thread

from app.extensions import mail
from app.utils.formatters import format_datetime

class EmailService:
    """Clase para manejar el envío de correos electrónicos en la aplicación."""
    
    @staticmethod
    def send_async_email(app, msg):
        """Envía un email de forma asíncrona."""
        with app.app_context():
            mail.send(msg)
    
    @classmethod
    def send_email(cls, recipients, subject, template, **kwargs):
        """
        Envía un correo electrónico basado en una plantilla.
        
        Args:
            recipients: Lista de destinatarios o un solo destinatario
            subject: Asunto del correo
            template: Nombre de la plantilla (sin extensión)
            **kwargs: Variables para la plantilla
        """
        app = current_app._get_current_object()
        
        # Aseguramos que recipients sea una lista
        if isinstance(recipients, str):
            recipients = [recipients]
            
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = ", ".join(recipients)
        
        # Renderizar plantillas HTML y texto plano
        html_body = render_template(f'email/{template}.html', **kwargs)
        text_body = render_template(f'email/{template}.txt', **kwargs)
        
        # Adjuntar partes al mensaje
        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # Enviar email de forma asíncrona
        Thread(target=cls.send_async_email, args=(app, msg)).start()
        
        return True
    
    @classmethod
    def send_welcome_email(cls, user):
        """Envía un correo de bienvenida al usuario."""
        return cls.send_email(
            recipients=user.email,
            subject="Bienvenido a la Plataforma de Emprendimiento",
            template="welcome",
            user=user
        )
    
    @classmethod
    def send_ally_assignment_notification(cls, entrepreneur, ally):
        """Notifica a un emprendedor que se le ha asignado un aliado."""
        return cls.send_email(
            recipients=entrepreneur.email, 
            subject="Se te ha asignado un aliado para tu emprendimiento",
            template="ally_assigned",
            entrepreneur=entrepreneur,
            ally=ally
        )
    
    @classmethod
    def send_entrepreneur_assignment_notification(cls, ally, entrepreneur):
        """Notifica a un aliado que se le ha asignado un emprendedor."""
        return cls.send_email(
            recipients=ally.email,
            subject="Se te ha asignado un nuevo emprendedor",
            template="entrepreneur_assigned",
            ally=ally,
            entrepreneur=entrepreneur
        )
    
    @classmethod
    def send_meeting_invitation(cls, meeting, participant):
        """Envía una invitación a una reunión."""
        return cls.send_email(
            recipients=participant.email,
            subject=f"Invitación: {meeting.title}",
            template="meeting_invitation",
            meeting=meeting,
            participant=participant,
            formatted_date=format_datetime(meeting.start_time)
        )
        
    @classmethod
    def send_task_notification(cls, task, user):
        """Notifica a un usuario sobre una nueva tarea o actualización."""
        return cls.send_email(
            recipients=user.email,
            subject=f"Tarea: {task.title}",
            template="task_notification",
            task=task,
            user=user,
            due_date=format_datetime(task.due_date) if task.due_date else "Sin fecha límite"
        )
    
    @classmethod
    def send_document_shared_notification(cls, document, recipient):
        """Notifica a un usuario que se ha compartido un documento con él."""
        return cls.send_email(
            recipients=recipient.email,
            subject=f"Documento compartido: {document.title}",
            template="document_shared",
            document=document,
            recipient=recipient,
            sender=document.owner
        )
    
    @classmethod
    def send_password_reset(cls, user, reset_token):
        """Envía un correo con instrucciones para restablecer contraseña."""
        return cls.send_email(
            recipients=user.email,
            subject="Restablecimiento de contraseña",
            template="password_reset",
            user=user,
            reset_token=reset_token
        )
    
    @classmethod
    def send_report_email(cls, user, report_data, report_file=None):
        """Envía un reporte por correo electrónico."""
        app = current_app._get_current_object()
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"Reporte: {report_data['title']}"
        msg['From'] = app.config['MAIL_DEFAULT_SENDER']
        msg['To'] = user.email
        
        # Renderizar plantillas
        html_body = render_template('email/report.html', **report_data)
        text_body = render_template('email/report.txt', **report_data)
        
        part1 = MIMEText(text_body, 'plain')
        part2 = MIMEText(html_body, 'html')
        msg.attach(part1)
        msg.attach(part2)
        
        # Adjuntar archivo si existe
        if report_file:
            attachment = MIMEApplication(report_file.read(), Name=report_file.filename)
            attachment['Content-Disposition'] = f'attachment; filename="{report_file.filename}"'
            msg.attach(attachment)
        
        # Enviar email de forma asíncrona
        Thread(target=cls.send_async_email, args=(app, msg)).start()
        
        return True