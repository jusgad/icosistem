"""
Servicio de almacenamiento para la aplicación de emprendimiento.
Proporciona funcionalidades para gestionar el almacenamiento de archivos,
con soporte para almacenamiento local y en la nube.
"""

import os
import uuid
import shutil
from datetime import datetime
from werkzeug.utils import secure_filename
from flask import current_app, url_for
import boto3
from botocore.exceptions import ClientError
import google.cloud.storage as gcs
import mimetypes

class StorageService:
    """
    Servicio para gestionar el almacenamiento de archivos.
    Soporta almacenamiento local, Amazon S3 y Google Cloud Storage.
    """
    
    STORAGE_LOCAL = 'local'
    STORAGE_S3 = 's3'
    STORAGE_GCS = 'gcs'
    
    def __init__(self):
        """Inicializa el servicio de almacenamiento."""
        self.storage_type = current_app.config.get('STORAGE_TYPE', self.STORAGE_LOCAL)
        self.upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
        self.s3_bucket = current_app.config.get('S3_BUCKET')
        self.gcs_bucket = current_app.config.get('GCS_BUCKET')
        
        # Crear directorio local si no existe y si estamos usando almacenamiento local
        if self.storage_type == self.STORAGE_LOCAL:
            os.makedirs(os.path.join(current_app.root_path, self.upload_folder), exist_ok=True)
        
        # Inicializar clientes para servicios en la nube si corresponde
        self.s3_client = None
        self.gcs_client = None
        
        if self.storage_type == self.STORAGE_S3:
            self.s3_client = boto3.client(
                's3',
                aws_access_key_id=current_app.config.get('AWS_ACCESS_KEY'),
                aws_secret_access_key=current_app.config.get('AWS_SECRET_KEY'),
                region_name=current_app.config.get('AWS_REGION')
            )
        elif self.storage_type == self.STORAGE_GCS:
            self.gcs_client = gcs.Client()
            
    def save_file(self, file, subfolder='general', allowed_extensions=None, max_size=10*1024*1024):
        """
        Guarda un archivo en el almacenamiento.
        
        Args:
            file: Objeto de archivo (de request.files)
            subfolder: Subcarpeta para organizar los archivos
            allowed_extensions: Lista de extensiones permitidas
            max_size: Tamaño máximo permitido en bytes
            
        Returns:
            dict: Información del archivo guardado o None si hay error
        """
        if not file:
            current_app.logger.error("No se proporcionó ningún archivo")
            return None
            
        # Verificar el tamaño del archivo
        if file.content_length and file.content_length > max_size:
            current_app.logger.error(f"Archivo demasiado grande: {file.content_length} bytes")
            return None
            
        # Obtener y verificar la extensión
        filename = secure_filename(file.filename)
        extension = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
        
        if allowed_extensions and extension not in allowed_extensions:
            current_app.logger.error(f"Extensión no permitida: {extension}")
            return None
            
        # Generar un nombre de archivo único
        unique_filename = f"{uuid.uuid4().hex}_{int(datetime.now().timestamp())}"
        if extension:
            unique_filename = f"{unique_filename}.{extension}"
            
        # Determinar el mime type
        mime_type = file.content_type or mimetypes.guess_type(filename)[0] or 'application/octet-stream'
        
        # Guardar el archivo según el tipo de almacenamiento
        if self.storage_type == self.STORAGE_LOCAL:
            return self._save_local(file, unique_filename, subfolder, mime_type, filename)
        elif self.storage_type == self.STORAGE_S3:
            return self._save_s3(file, unique_filename, subfolder, mime_type, filename)
        elif self.storage_type == self.STORAGE_GCS:
            return self._save_gcs(file, unique_filename, subfolder, mime_type, filename)
        else:
            current_app.logger.error(f"Tipo de almacenamiento no soportado: {self.storage_type}")
            return None
            
    def _save_local(self, file, unique_filename, subfolder, mime_type, original_filename):
        """Guarda un archivo en el almacenamiento local."""
        try:
            # Crear subcarpeta si no existe
            folder_path = os.path.join(current_app.root_path, self.upload_folder, subfolder)
            os.makedirs(folder_path, exist_ok=True)
            
            # Ruta completa del archivo
            file_path = os.path.join(folder_path, unique_filename)
            
            # Guardar el archivo
            file.save(file_path)
            
            # Generar URL para acceder al archivo
            file_url = url_for('static', 
                               filename=f"{self.upload_folder}/{subfolder}/{unique_filename}", 
                               _external=True)
            
            # Retornar información del archivo
            return {
                'filename': unique_filename,
                'original_filename': original_filename,
                'mime_type': mime_type,
                'size': os.path.getsize(file_path),
                'path': f"{self.upload_folder}/{subfolder}/{unique_filename}",
                'url': file_url,
                'storage_type': self.STORAGE_LOCAL
            }
            
        except Exception as e:
            current_app.logger.error(f"Error al guardar archivo local: {str(e)}")
            return None
            
    def _save_s3(self, file, unique_filename, subfolder, mime_type, original_filename):
        """Guarda un archivo en Amazon S3."""
        try:
            # Clave del objeto en S3
            object_key = f"{subfolder}/{unique_filename}"
            
            # Subir archivo a S3
            self.s3_client.upload_fileobj(
                file,
                self.s3_bucket,
                object_key,
                ExtraArgs={
                    'ContentType': mime_type
                }
            )
            
            # Obtener tamaño del archivo
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            # Generar URL para acceder al archivo
            if current_app.config.get('S3_PUBLIC', False):
                file_url = f"https://{self.s3_bucket}.s3.amazonaws.com/{object_key}"
            else:
                file_url = self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.s3_bucket, 'Key': object_key},
                    ExpiresIn=3600  # URL válida por 1 hora
                )
            
            # Retornar información del archivo
            return {
                'filename': unique_filename,
                'original_filename': original_filename,
                'mime_type': mime_type,
                'size': file_size,
                'path': object_key,
                'url': file_url,
                'storage_type': self.STORAGE_S3
            }
            
        except Exception as e:
            current_app.logger.error(f"Error al guardar archivo en S3: {str(e)}")
            return None
            
    def _save_gcs(self, file, unique_filename, subfolder, mime_type, original_filename):
        """Guarda un archivo en Google Cloud Storage."""
        try:
            # Obtener el bucket
            bucket = self.gcs_client.bucket(self.gcs_bucket)
            
            # Nombre del blob (objeto)
            blob_name = f"{subfolder}/{unique_filename}"
            
            # Crear un nuevo blob
            blob = bucket.blob(blob_name)
            
            # Establecer el tipo de contenido
            blob.content_type = mime_type
            
            # Subir desde el archivo
            blob.upload_from_file(file)
            
            # Obtener tamaño del archivo
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            # Generar URL para acceder al archivo
            if current_app.config.get('GCS_PUBLIC', False):
                file_url = f"https://storage.googleapis.com/{self.gcs_bucket}/{blob_name}"
            else:
                file_url = blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.timedelta(hours=1),
                    method="GET"
                )
            
            # Retornar información del archivo
            return {
                'filename': unique_filename,
                'original_filename': original_filename,
                'mime_type': mime_type,
                'size': file_size,
                'path': blob_name,
                'url': file_url,
                'storage_type': self.STORAGE_GCS
            }
            
        except Exception as e:
            current_app.logger.error(f"Error al guardar archivo en GCS: {str(e)}")
            return None
            
    def get_file_url(self, file_info, expires_in=3600):
        """
        Genera una URL para acceder a un archivo.
        
        Args:
            file_info: Diccionario con información del archivo
            expires_in: Tiempo de expiración en segundos para URLs temporales
            
        Returns:
            str: URL del archivo o None si hay error
        """
        try:
            storage_type = file_info.get('storage_type')
            file_path = file_info.get('path')
            
            if not storage_type or not file_path:
                return None
                
            if storage_type == self.STORAGE_LOCAL:
                return url_for('static', filename=file_path, _external=True)
                
            elif storage_type == self.STORAGE_S3:
                return self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.s3_bucket, 'Key': file_path},
                    ExpiresIn=expires_in
                )
                
            elif storage_type == self.STORAGE_GCS:
                bucket = self.gcs_client.bucket(self.gcs_bucket)
                blob = bucket.blob(file_path)
                return blob.generate_signed_url(
                    version="v4",
                    expiration=datetime.timedelta(seconds=expires_in),
                    method="GET"
                )
                
            return None
            
        except Exception as e:
            current_app.logger.error(f"Error al generar URL de archivo: {str(e)}")
            return None
            
    def delete_file(self, file_info):
        """
        Elimina un archivo del almacenamiento.
        
        Args:
            file_info: Diccionario con información del archivo
            
        Returns:
            bool: True si se eliminó correctamente, False en caso contrario
        """
        try:
            storage_type = file_info.get('storage_type')
            file_path = file_info.get('path')
            
            if not storage_type or not file_path:
                return False
                
            if storage_type == self.STORAGE_LOCAL:
                full_path = os.path.join(current_app.root_path, file_path)
                if os.path.exists(full_path):
                    os.remove(full_path)
                return True
                
            elif storage_type == self.STORAGE_S3:
                self.s3_client.delete_object(
                    Bucket=self.s3_bucket,
                    Key=file_path
                )
                return True
                
            elif storage_type == self.STORAGE_GCS:
                bucket = self.gcs_client.bucket(self.gcs_bucket)
                blob = bucket.blob(file_path)
                blob.delete()
                return True
                
            return False
            
        except Exception as e:
            current_app.logger.error(f"Error al eliminar archivo: {str(e)}")
            return False
            
    def copy_file(self, file_info, new_subfolder):
        """
        Copia un archivo a una nueva ubicación.
        
        Args:
            file_info: Diccionario con información del archivo
            new_subfolder: Nueva subcarpeta de destino
            
        Returns:
            dict: Información del nuevo archivo o None si hay error
        """
        try:
            storage_type = file_info.get('storage_type')
            file_path = file_info.get('path')
            filename = file_info.get('filename')
            mime_type = file_info.get('mime_type')
            original_filename = file_info.get('original_filename')
            
            if not all([storage_type, file_path, filename]):
                return None
                
            new_path = f"{new_subfolder}/{filename}"
            
            if storage_type == self.STORAGE_LOCAL:
                src_path = os.path.join(current_app.root_path, file_path)
                dst_dir = os.path.join(current_app.root_path, self.upload_folder, new_subfolder)
                os.makedirs(dst_dir, exist_ok=True)
                dst_path = os.path.join(dst_dir, filename)
                shutil.copy2(src_path, dst_path)
                
                return {
                    'filename': filename,
                    'original_filename': original_filename,
                    'mime_type': mime_type,
                    'size': os.path.getsize(dst_path),
                    'path': f"{self.upload_folder}/{new_path}",
                    'url': url_for('static', filename=f"{self.upload_folder}/{new_path}", _external=True),
                    'storage_type': self.STORAGE_LOCAL
                }
                
            elif storage_type == self.STORAGE_S3:
                self.s3_client.copy_object(
                    CopySource={'Bucket': self.s3_bucket, 'Key': file_path},
                    Bucket=self.s3_bucket,
                    Key=new_path
                )
                
                if current_app.config.get('S3_PUBLIC', False):
                    file_url = f"https://{self.s3_bucket}.s3.amazonaws.com/{new_path}"
                else:
                    file_url = self.s3_client.generate_presigned_url(
                        'get_object',
                        Params={'Bucket': self.s3_bucket, 'Key': new_path},
                        ExpiresIn=3600
                    )
                
                # Obtener metadatos del objeto
                response = self.s3_client.head_object(Bucket=self.s3_bucket, Key=new_path)
                size = response.get('ContentLength', 0)
                
                return {
                    'filename': filename,
                    'original_filename': original_filename,
                    'mime_type': mime_type,
                    'size': size,
                    'path': new_path,
                    'url': file_url,
                    'storage_type': self.STORAGE_S3
                }
                
            elif storage_type == self.STORAGE_GCS:
                bucket = self.gcs_client.bucket(self.gcs_bucket)
                source_blob = bucket.blob(file_path)
                new_blob = bucket.blob(new_path)
                
                # Copiar blob
                bucket.copy_blob(source_blob, bucket, new_path)
                
                # Establecer el tipo de contenido
                new_blob.content_type = mime_type
                new_blob.patch()
                
                # Generar URL
                if current_app.config.get('GCS_PUBLIC', False):
                    file_url = f"https://storage.googleapis.com/{self.gcs_bucket}/{new_path}"
                else:
                    file_url = new_blob.generate_signed_url(
                        version="v4",
                        expiration=datetime.timedelta(hours=1),
                        method="GET"
                    )
                
                return {
                    'filename': filename,
                    'original_filename': original_filename,
                    'mime_type': mime_type,
                    'size': new_blob.size,
                    'path': new_path,
                    'url': file_url,
                    'storage_type': self.STORAGE_GCS
                }
            
            return None
            
        except Exception as e:
            current_app.logger.error(f"Error al copiar archivo: {str(e)}")
            return None

# Crear una instancia global del servicio
storage_service = StorageService()