from __future__ import with_statement

import logging
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# Este es el objeto de configuración de Alembic, que proporciona
# acceso a los valores dentro del archivo .ini en uso.
config = context.config

# Interpreta el archivo de configuración para el registro de Python.
# Esta línea básicamente configura los registradores.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')

# Agrega el objeto MetaData de tu modelo aquí
# para soporte de 'autogeneración'
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
from flask import current_app
config.set_main_option(
    'sqlalchemy.url',
    str(current_app.extensions['migrate'].db.engine.url).replace('%', '%%'))
target_metadata = current_app.extensions['migrate'].db.metadata

# Otros valores de la configuración, definidos por las necesidades de env.py,
# pueden ser adquiridos:
# mi_opcion_importante = config.get_main_option("mi_opcion_importante")
# ... etc.


def run_migrations_offline():
    """Ejecuta las migraciones en modo 'offline'.

    Esto configura el contexto con solo una URL
    y no un Engine, aunque un Engine también es aceptable
    aquí. Al omitir la creación del Engine,
    ni siquiera necesitamos que un DBAPI esté disponible.

    Las llamadas a context.execute() aquí emiten la cadena dada
    a la salida del script.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Ejecuta las migraciones en modo 'online'.

    En este escenario necesitamos crear un Engine
    y asociar una conexión con el contexto.
    """

    # Esta función de retorno se usa para evitar que se genere una auto-migración
    # cuando no hay cambios en el esquema
    # referencia: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No se detectaron cambios en el esquema.')

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix='sqlalchemy.',
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            process_revision_directives=process_revision_directives,
            **current_app.extensions['migrate'].configure_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()