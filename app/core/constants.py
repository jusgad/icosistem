"""
Constants for the entrepreneurship ecosystem.
"""

# User roles
ADMIN_ROLE = 'admin'
ENTREPRENEUR_ROLE = 'entrepreneur' 
ALLY_ROLE = 'ally'
CLIENT_ROLE = 'client'

VALID_ROLES = [ADMIN_ROLE, ENTREPRENEUR_ROLE, ALLY_ROLE, CLIENT_ROLE]

USER_ROLES = {
    ADMIN_ROLE: {'name': 'Administrador', 'permissions': ['all']},
    ENTREPRENEUR_ROLE: {'name': 'Emprendedor', 'permissions': ['create_project', 'manage_own_projects']},
    ALLY_ROLE: {'name': 'Aliado/Mentor', 'permissions': ['mentor', 'view_entrepreneurs']},
    CLIENT_ROLE: {'name': 'Cliente', 'permissions': ['view_directory', 'generate_reports']}
}

# Timezone
TIMEZONE_BOGOTA = 'America/Bogota'

# Project statuses
PROJECT_STATUSES = [
    'idea', 'validation', 'development', 'launch', 
    'growth', 'scale', 'exit', 'paused', 'cancelled'
]