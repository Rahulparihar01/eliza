"""
Settings Service

Service for managing system-wide settings.
"""
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models.system_settings import SystemSetting, SettingType
from src.core.logging import get_logger, LogCategory

logger = get_logger(__name__, category=LogCategory.SYSTEM)


class SettingsService:
    """Service for managing system settings."""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_setting(self, key: str) -> Optional[SystemSetting]:
        """Get a setting by key."""
        return self.db.query(SystemSetting).filter(
            SystemSetting.setting_key == key
        ).first()
    
    def get_setting_value(self, key: str, default: Any = None) -> Any:
        """
        Get a setting's typed value.
        
        Args:
            key: Setting key
            default: Default value if setting not found
            
        Returns:
            Typed value based on setting_type, or default if not found
        """
        setting = self.get_setting(key)
        if not setting:
            logger.debug(f"Setting not found: {key}, using default: {default}")
            return default
        
        return setting.parsed_value
    
    def get_all_settings(self, public_only: bool = False) -> List[SystemSetting]:
        """
        Get all settings.
        
        Args:
            public_only: If True, only return public settings
        """
        query = self.db.query(SystemSetting)
        if public_only:
            query = query.filter(SystemSetting.is_public == True)
        return query.all()
    
    def set_setting(
        self,
        key: str,
        value: Any,
        setting_type: str = SettingType.STRING.value,
        description: Optional[str] = None,
        is_public: bool = False
    ) -> SystemSetting:
        """
        Create or update a setting.
        
        Args:
            key: Setting key
            value: Setting value (will be typed based on setting_type)
            setting_type: Type of setting (string, integer, boolean, json)
            description: Human-readable description
            is_public: Whether non-admins can read this setting
        """
        setting = self.get_setting(key)
        
        # Convert value to string representation based on type
        if value is None:
            string_value = None
        elif setting_type == SettingType.JSON.value:
            import json
            string_value = json.dumps(value)
        elif setting_type == SettingType.BOOLEAN.value:
            string_value = str(bool(value)).lower()
        elif setting_type == SettingType.INTEGER.value:
            string_value = str(int(value))
        else:  # STRING or default
            string_value = str(value)
        
        if setting:
            # Update existing
            setting.setting_value = string_value
            setting.setting_type = setting_type
            if description is not None:
                setting.description = description
            if is_public is not None:
                setting.is_public = is_public
            logger.info(f"Updated setting: {key}")
        else:
            # Create new
            setting = SystemSetting(
                setting_key=key,
                setting_value=string_value,
                setting_type=setting_type,
                description=description,
                is_public=is_public
            )
            self.db.add(setting)
            logger.info(f"Created setting: {key}")
        
        self.db.commit()
        self.db.refresh(setting)
        return setting
    
    def delete_setting(self, key: str) -> bool:
        """
        Delete a setting.
        
        Returns:
            True if deleted, False if not found
        """
        setting = self.get_setting(key)
        if setting:
            self.db.delete(setting)
            self.db.commit()
            logger.info(f"Deleted setting: {key}")
            return True
        return False
    
    def get_default_company_hr_dataset(self) -> str:
        """
        Get the default company for HR data queries.
        
        Returns:
            Company ID string, defaults to 'caylent' if not configured
        """
        return self.get_setting_value("default_company_hr_dataset", "caylent")
    
    def set_default_company_hr_dataset(self, company_id: str) -> SystemSetting:
        """
        Set the default company for HR data queries.
        
        Args:
            company_id: Company ID to set as default
        """
        return self.set_setting(
            key="default_company_hr_dataset",
            value=company_id,
            setting_type=SettingType.STRING.value,
            description="Default company for HR data queries when not explicitly specified",
            is_public=False
        )
    
    def get_vector_search_similarity_threshold(self) -> float:
        """
        Get the similarity threshold for vector searches.
        
        Returns:
            Threshold value (0.0-1.0), defaults to 0.5
        """
        return float(self.get_setting_value("vector_search_similarity_threshold", 0.5))
    
    def set_vector_search_similarity_threshold(self, threshold: float) -> SystemSetting:
        """
        Set the similarity threshold for vector searches.
        
        Args:
            threshold: Minimum similarity score (0.0-1.0) for results
        """
        if not 0.0 <= threshold <= 1.0:
            raise ValueError("Threshold must be between 0.0 and 1.0")
        
        return self.set_setting(
            key="vector_search_similarity_threshold",
            value=threshold,
            setting_type=SettingType.FLOAT.value,
            description="Minimum similarity score (0.0-1.0) for document search results",
            is_public=False
        )
    
    def get_vector_search_result_limit(self) -> int:
        """
        Get the maximum number of results for vector searches.
        
        Returns:
            Maximum number of results (k), defaults to 10
        """
        return int(self.get_setting_value("vector_search_result_limit", 10))
    
    def set_vector_search_result_limit(self, limit: int) -> SystemSetting:
        """
        Set the maximum number of results for vector searches.
        
        Args:
            limit: Maximum number of results to return (k value)
        """
        if limit < 1 or limit > 100:
            raise ValueError("Limit must be between 1 and 100")
        
        return self.set_setting(
            key="vector_search_result_limit",
            value=limit,
            setting_type=SettingType.INTEGER.value,
            description="Maximum number of document chunks to return from vector search (k value)",
            is_public=False
        )


# Convenience function for getting default company (used throughout app)
def get_default_company_hr_dataset(db: Session) -> str:
    """
    Get the default company HR dataset.
    
    This is a convenience function that can be used throughout the application.
    """
    service = SettingsService(db)
    return service.get_default_company_hr_dataset()

