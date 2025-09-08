"""
Email tracking model for the entrepreneurship ecosystem.
Handles detailed tracking of email opens, clicks, and user interactions.
"""

from sqlalchemy import Column, String, Text, Integer, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.extensions import db
from .base import CompleteBaseModel


class EmailTracking(CompleteBaseModel):
    """
    Model for detailed email interaction tracking.
    
    This model tracks:
    - Email opens with timestamps and user agent
    - Link clicks with URLs and interaction data
    - User engagement patterns
    - Geographic and device information
    - Multiple interactions per email
    """
    
    __tablename__ = 'email_tracking'
    
    # Tracking identification
    tracking_id = Column(String(255), nullable=False, unique=True, index=True,
                        doc="Unique tracking identifier for the email")
    message_id = Column(String(255), nullable=True, index=True,
                       doc="Associated message ID from email provider")
    
    # Email and recipient information
    recipient_email = Column(String(255), nullable=False, index=True,
                           doc="Email address of the recipient")
    recipient_name = Column(String(255), nullable=True,
                          doc="Name of the recipient")
    
    # Email associations
    email_log_id = Column(db.String(36), ForeignKey('email_logs.id'), nullable=True,
                         doc="Associated email log record")
    campaign_id = Column(db.String(36), nullable=True, index=True,
                        doc="Associated campaign ID")
    template_id = Column(db.String(36), nullable=True, index=True,
                        doc="Associated template ID")
    user_id = Column(db.String(36), nullable=True, index=True,
                    doc="Associated user ID")
    
    # Open tracking
    opened_at = Column(DateTime, nullable=True, index=True,
                      doc="Timestamp of first email open")
    last_opened_at = Column(DateTime, nullable=True,
                          doc="Timestamp of most recent email open")
    open_count = Column(Integer, default=0,
                       doc="Total number of times email was opened")
    
    # Click tracking
    clicked_at = Column(DateTime, nullable=True, index=True,
                       doc="Timestamp of first link click")
    last_clicked_at = Column(DateTime, nullable=True,
                           doc="Timestamp of most recent link click")
    click_count = Column(Integer, default=0,
                        doc="Total number of link clicks")
    clicked_urls = Column(db.JSON, default=list,
                         doc="List of all URLs clicked")
    
    # Device and browser information
    user_agent = Column(Text, nullable=True,
                       doc="User agent string from first open")
    browser = Column(String(100), nullable=True,
                    doc="Browser information")
    device_type = Column(String(50), nullable=True,
                        doc="Device type (desktop, mobile, tablet)")
    operating_system = Column(String(100), nullable=True,
                             doc="Operating system information")
    
    # Geographic information
    ip_address = Column(String(45), nullable=True,
                       doc="IP address of the recipient")
    country = Column(String(100), nullable=True,
                    doc="Country based on IP geolocation")
    city = Column(String(100), nullable=True,
                 doc="City based on IP geolocation")
    
    # Interaction metadata
    interaction_data = Column(db.JSON, default=dict,
                            doc="Additional interaction data and analytics")
    
    # Relationships
    email_log = relationship("EmailLog", backref="tracking_records")
    
    def __repr__(self):
        return f"<EmailTracking(email='{self.recipient_email}', opens={self.open_count}, clicks={self.click_count})>"
    
    def __str__(self):
        return f"Tracking for {self.recipient_email}"
    
    @property
    def is_opened(self):
        """Check if email has been opened."""
        return self.opened_at is not None
    
    @property
    def is_clicked(self):
        """Check if any links have been clicked."""
        return self.clicked_at is not None
    
    @property
    def engagement_score(self):
        """Calculate simple engagement score based on opens and clicks."""
        score = 0
        if self.is_opened:
            score += 10
        if self.is_clicked:
            score += 20
        
        # Bonus for multiple interactions
        score += min(self.open_count - 1, 5) * 2  # Up to 5 bonus points for multiple opens
        score += min(self.click_count - 1, 10) * 5  # Up to 50 bonus points for multiple clicks
        
        return min(score, 100)  # Cap at 100
    
    @property
    def unique_clicked_urls_count(self):
        """Get count of unique URLs clicked."""
        return len(set(self.clicked_urls)) if self.clicked_urls else 0
    
    def add_open(self, user_agent=None, ip_address=None, **kwargs):
        """Record an email open event."""
        from datetime import datetime, timezone
        
        now = datetime.now(timezone.utc)
        
        if not self.opened_at:
            self.opened_at = now
            if user_agent:
                self.user_agent = user_agent
                self._parse_user_agent(user_agent)
            if ip_address:
                self.ip_address = ip_address
        
        self.last_opened_at = now
        self.open_count += 1
        
        # Update interaction data
        if not self.interaction_data:
            self.interaction_data = {}
        
        self.interaction_data.setdefault('opens', []).append({
            'timestamp': now.isoformat(),
            'user_agent': user_agent,
            'ip_address': ip_address,
            **kwargs
        })
    
    def add_click(self, url, user_agent=None, ip_address=None, **kwargs):
        """Record a link click event."""
        from datetime import datetime
        
        now = datetime.now(timezone.utc)
        
        if not self.clicked_at:
            self.clicked_at = now
        
        self.last_clicked_at = now
        self.click_count += 1
        
        # Add URL to clicked URLs list
        if not self.clicked_urls:
            self.clicked_urls = []
        self.clicked_urls.append(url)
        
        # Update interaction data
        if not self.interaction_data:
            self.interaction_data = {}
        
        self.interaction_data.setdefault('clicks', []).append({
            'timestamp': now.isoformat(),
            'url': url,
            'user_agent': user_agent,
            'ip_address': ip_address,
            **kwargs
        })
    
    def _parse_user_agent(self, user_agent):
        """Parse user agent to extract browser and device information."""
        if not user_agent:
            return
        
        # Simple user agent parsing (in production, consider using user-agents library)
        user_agent_lower = user_agent.lower()
        
        # Browser detection
        if 'chrome' in user_agent_lower:
            self.browser = 'Chrome'
        elif 'firefox' in user_agent_lower:
            self.browser = 'Firefox'
        elif 'safari' in user_agent_lower and 'chrome' not in user_agent_lower:
            self.browser = 'Safari'
        elif 'edge' in user_agent_lower:
            self.browser = 'Edge'
        elif 'opera' in user_agent_lower:
            self.browser = 'Opera'
        
        # Device type detection
        if 'mobile' in user_agent_lower or 'android' in user_agent_lower:
            self.device_type = 'mobile'
        elif 'tablet' in user_agent_lower or 'ipad' in user_agent_lower:
            self.device_type = 'tablet'
        else:
            self.device_type = 'desktop'
        
        # OS detection
        if 'windows' in user_agent_lower:
            self.operating_system = 'Windows'
        elif 'macintosh' in user_agent_lower or 'mac os' in user_agent_lower:
            self.operating_system = 'macOS'
        elif 'linux' in user_agent_lower:
            self.operating_system = 'Linux'
        elif 'android' in user_agent_lower:
            self.operating_system = 'Android'
        elif 'iphone' in user_agent_lower or 'ipad' in user_agent_lower:
            self.operating_system = 'iOS'
    
    @classmethod
    def get_by_tracking_id(cls, tracking_id):
        """Get tracking record by tracking ID."""
        return cls.query.filter_by(tracking_id=tracking_id).first()
    
    @classmethod
    def get_campaign_engagement(cls, campaign_id):
        """Get engagement statistics for a campaign."""
        from sqlalchemy import func
        
        stats = cls.query.filter_by(campaign_id=campaign_id).with_entities(
            func.count(cls.id).label('total_tracked'),
            func.count(cls.opened_at).label('unique_opens'),
            func.count(cls.clicked_at).label('unique_clicks'),
            func.sum(cls.open_count).label('total_opens'),
            func.sum(cls.click_count).label('total_clicks'),
            func.avg(cls.open_count).label('avg_opens_per_recipient'),
            func.avg(cls.click_count).label('avg_clicks_per_recipient')
        ).first()
        
        return {
            'total_tracked': stats.total_tracked or 0,
            'unique_opens': stats.unique_opens or 0,
            'unique_clicks': stats.unique_clicks or 0,
            'total_opens': stats.total_opens or 0,
            'total_clicks': stats.total_clicks or 0,
            'avg_opens_per_recipient': float(stats.avg_opens_per_recipient or 0),
            'avg_clicks_per_recipient': float(stats.avg_clicks_per_recipient or 0)
        }


# Export
__all__ = ['EmailTracking']