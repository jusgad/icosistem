"""
Email template model for the entrepreneurship ecosystem.
Manages email templates with HTML and text content for the ecosystem.
"""

from sqlalchemy import Column, String, Text, Boolean
from app.extensions import db
from .base import CompleteBaseModel


class EmailTemplate(CompleteBaseModel):
    """
    Model for email templates in the entrepreneurship ecosystem.
    
    This model handles:
    - HTML and text versions of email templates
    - Template variables and personalization
    - Category-based organization
    - Template versioning and activation status
    - Usage tracking and analytics
    """
    
    __tablename__ = 'email_templates'
    
    # Template identification
    name = Column(String(100), nullable=False, unique=True, index=True,
                 doc="Unique template name identifier")
    display_name = Column(String(200), nullable=True,
                         doc="User-friendly display name")
    description = Column(Text, nullable=True,
                        doc="Template description and usage notes")
    
    # Template content
    subject = Column(String(500), nullable=False,
                    doc="Email subject line (can contain variables)")
    html_content = Column(Text, nullable=False,
                         doc="HTML version of the template")
    text_content = Column(Text, nullable=True,
                         doc="Plain text version of the template")
    
    # Template organization
    category = Column(String(100), nullable=True, index=True,
                     doc="Template category (welcome, notification, marketing, etc.)")
    template_type = Column(String(50), nullable=False, index=True,
                          doc="Type of template (transactional, marketing, system)")
    
    # Template configuration
    is_active = Column(Boolean, default=True, index=True,
                      doc="Whether template is active and available for use")
    is_system = Column(Boolean, default=False,
                      doc="Whether this is a system template (cannot be deleted)")
    
    # Template variables and personalization
    variables = Column(db.JSON, default=list,
                      doc="List of available template variables")
    default_data = Column(db.JSON, default=dict,
                         doc="Default values for template variables")
    
    # Usage and analytics
    usage_count = Column(db.Integer, default=0,
                        doc="Number of times template has been used")
    last_used_at = Column(db.DateTime, nullable=True,
                         doc="Timestamp of last usage")
    
    # Template metadata
    tags = Column(db.JSON, default=list,
                 doc="Tags for template organization and search")
    version = Column(String(20), default='1.0',
                    doc="Template version")
    
    def __repr__(self):
        return f"<EmailTemplate(name='{self.name}', type='{self.template_type}', active={self.is_active})>"
    
    def __str__(self):
        return f"Template: {self.display_name or self.name}"
    
    @property
    def has_text_version(self):
        """Check if template has a text version."""
        return bool(self.text_content and self.text_content.strip())
    
    @property
    def variable_count(self):
        """Get count of template variables."""
        return len(self.variables) if self.variables else 0
    
    @property
    def is_ready(self):
        """Check if template is ready for use."""
        return (self.is_active and 
                self.subject and 
                self.html_content and
                not self.subject.strip() == '' and
                not self.html_content.strip() == '')
    
    def increment_usage(self):
        """Increment usage count and update last used timestamp."""
        from datetime import datetime, timezone
        
        self.usage_count += 1
        self.last_used_at = datetime.now(timezone.utc)
        
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
    
    def add_variable(self, variable_name, description=None, default_value=None):
        """Add a variable to the template."""
        if not self.variables:
            self.variables = []
        
        # Check if variable already exists
        for var in self.variables:
            if isinstance(var, dict) and var.get('name') == variable_name:
                return  # Variable already exists
        
        variable_info = {'name': variable_name}
        if description:
            variable_info['description'] = description
        if default_value is not None:
            variable_info['default'] = default_value
        
        self.variables.append(variable_info)
        
        # Update default data if provided
        if default_value is not None:
            if not self.default_data:
                self.default_data = {}
            self.default_data[variable_name] = default_value
        
        # Mark as modified for SQLAlchemy
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(self, 'variables')
        flag_modified(self, 'default_data')
    
    def remove_variable(self, variable_name):
        """Remove a variable from the template."""
        if not self.variables:
            return
        
        # Remove from variables list
        self.variables = [
            var for var in self.variables
            if not (isinstance(var, dict) and var.get('name') == variable_name) and var != variable_name
        ]
        
        # Remove from default data
        if self.default_data and variable_name in self.default_data:
            del self.default_data[variable_name]
        
        # Mark as modified for SQLAlchemy
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(self, 'variables')
        flag_modified(self, 'default_data')
    
    def get_variable_names(self):
        """Get list of variable names."""
        if not self.variables:
            return []
        
        names = []
        for var in self.variables:
            if isinstance(var, dict):
                names.append(var.get('name'))
            else:
                names.append(str(var))
        
        return [name for name in names if name]
    
    def validate_template_data(self, template_data):
        """Validate that all required variables are provided."""
        variable_names = self.get_variable_names()
        missing_vars = []
        
        for var_name in variable_names:
            if var_name not in template_data:
                # Check if there's a default value
                if not (self.default_data and var_name in self.default_data):
                    missing_vars.append(var_name)
        
        return missing_vars
    
    def get_merged_data(self, template_data):
        """Merge template data with defaults."""
        merged_data = {}
        
        # Start with defaults
        if self.default_data:
            merged_data.update(self.default_data)
        
        # Override with provided data
        if template_data:
            merged_data.update(template_data)
        
        return merged_data
    
    @classmethod
    def get_by_name(cls, name):
        """Get template by name."""
        return cls.query.filter_by(name=name, is_active=True).first()
    
    @classmethod
    def get_by_category(cls, category):
        """Get templates by category."""
        return cls.query.filter_by(category=category, is_active=True).all()
    
    @classmethod
    def get_active_templates(cls):
        """Get all active templates."""
        return cls.query.filter_by(is_active=True).all()
    
    @classmethod
    def search_templates(cls, query_text, category=None):
        """Search templates by name or description."""
        query = cls.query.filter(cls.is_active == True)
        
        if category:
            query = query.filter(cls.category == category)
        
        if query_text:
            search_filter = db.or_(
                cls.name.ilike(f'%{query_text}%'),
                cls.display_name.ilike(f'%{query_text}%'),
                cls.description.ilike(f'%{query_text}%')
            )
            query = query.filter(search_filter)
        
        return query.all()
    
    # Maintain backward compatibility with old 'content' field
    @property
    def content(self):
        """Backward compatibility property for content field."""
        return self.html_content
    
    @content.setter
    def content(self, value):
        """Backward compatibility setter for content field."""
        self.html_content = value

# Export
__all__ = ['EmailTemplate']