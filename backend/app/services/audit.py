from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.database import AuditLog
from app.core.database import get_db_context
from loguru import logger

class AuditService:
    @staticmethod
    async def log(
        action: str,
        user_id: Optional[Any] = None,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
        status: str = "success",
        error_message: Optional[str] = None
    ):
        """Create an audit log entry asynchronously"""
        try:
            async with get_db_context() as db:
                log_entry = AuditLog(
                    user_id=user_id,
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    details=details,
                    status=status,
                    error_message=error_message
                )
                db.add(log_entry)
                # get_db_context commits automatically
            logger.debug(f"Audit Logged: {action} by {user_id}")
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")

audit_service = AuditService()
