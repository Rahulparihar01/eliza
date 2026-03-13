"""System Settings Model

Stores system-wide configuration settings that can be managed by administrators.
"""
import enum
from sqlalchemy import Column, Integer, String, Text, Boolean, DateTime
from sqlalchemy.sql import func
from src.models.database import Base


class SettingType(str, enum.Enum):
    """Types of settings."""
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    JSON = "json"


class SystemSetting(Base):
    """System-wide configuration settings."""
    
    __tablename__ = 'system_settings'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    setting_key = Column(String(255), nullable=False, unique=True, index=True)
    setting_value = Column(Text, nullable=True)
    setting_type = Column(String(50), nullable=False, default='string')  # string, int, bool, json
    description = Column(Text, nullable=True)
    is_public = Column(Boolean, nullable=False, default=False)  # If true, can be read without auth
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
    
    def __repr__(self):
        return f"<SystemSetting(key='{self.setting_key}', value='{self.setting_value}')>"
    
    @property
    def parsed_value(self):
        """Return the setting value parsed according to its type."""
        if self.setting_value is None:
            return None
        
        if self.setting_type == 'integer' or self.setting_type == 'int':
            return int(self.setting_value)
        elif self.setting_type == 'boolean' or self.setting_type == 'bool':
            return self.setting_value.lower() in ('true', '1', 'yes')
        elif self.setting_type == 'json':
            import json
            return json.loads(self.setting_value)
        else:  # string or default
            return self.setting_value
