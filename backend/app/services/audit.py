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

    @staticmethod
    async def list_logs(
        skip: int = 0,
        limit: int = 50,
        action: Optional[str] = None,
        status: Optional[str] = None
    ):
        """Retrieve audit logs with filtering and pagination"""
        try:
            from sqlalchemy import select, desc
            async with get_db_context() as db:
                query = select(AuditLog).order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
                
                if action:
                    query = query.filter(AuditLog.action == action)
                if status:
                    query = query.filter(AuditLog.status == status)
                    
                result = await db.execute(query)
                return result.scalars().all()
        except Exception as e:
            logger.error(f"Failed to fetch audit logs: {e}")
            return []

audit_service = AuditService()
