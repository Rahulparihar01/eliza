"""
Tenant Theme Model

Stores tenant-specific theme/branding configuration for white-label customization.
Each tenant can customize their brand colors which apply across the entire UI.
"""

from sqlalchemy import Column, String, ForeignKey
from src.models.database import BaseModel


class TenantTheme(BaseModel):
    """
    Tenant-specific theme/branding configuration.
    
    Stores brand colors that are applied as CSS custom properties
    to customize the look and feel of the Eliza Forge platform.
    """
    
    __tablename__ = "tenant_themes"
    __table_args__ = ({'extend_existing': True},)
    
    # Multi-tenant - one theme per tenant
    customer_id = Column(
        String(100), 
        ForeignKey("customers.customer_id", ondelete="CASCADE"), 
        nullable=False, 
        unique=True, 
        index=True
    )
    
    # Brand colors (hex format: #RRGGBB)
    # Defaults are Eliza Forge palette
    primary_color = Column(String(7), nullable=False, default='#c9506b')
    primary_light_color = Column(String(7), nullable=False, default='#e8a598')
    accent_color = Column(String(7), nullable=False, default='#f5c4a1')
    text_color = Column(String(7), nullable=False, default='#5c4a5a')
    
    # Preset name (null if custom colors)
    # Valid presets: 'eliza-forge', 'ocean-blue', 'forest-green', 'royal-purple'
    preset_name = Column(String(50), default='eliza-forge')
    
    def __repr__(self):
        return f"<TenantTheme(customer_id='{self.customer_id}', preset='{self.preset_name}')>"
