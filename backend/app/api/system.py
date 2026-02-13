"""
System and Audit API Endpoints
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from app.api.deps import get_current_user, require_role
from app.services.audit import audit_service
from app.models.schemas import UserRole
import pydantic
from uuid import UUID
from datetime import datetime

router = APIRouter(prefix="/system", tags=["System"])

class AuditLogSchema(pydantic.BaseModel):
    id: UUID
    action: str
    actor: Optional[str] = "System"
    resource_type: Optional[str]
    resource_id: Optional[str]
    status: str
    created_at: datetime
    ip_address: Optional[str]
    
    class Config:
        from_attributes = True

@router.get("/audit", response_model=List[AuditLogSchema])
async def get_audit_logs(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    action: Optional[str] = None,
    status: Optional[str] = None,
    current_user = Depends(get_current_user)
):
    """
    Fetch system audit logs (Temporary bypass for debugging)
    """
    from sqlalchemy import select, desc
    from app.models.database import AuditLog, User
    from app.core.database import get_db_context
    from fastapi import HTTPException
    from loguru import logger
    
    try:
        async with get_db_context() as db:
            query = select(AuditLog, User.name).outerjoin(User, AuditLog.user_id == User.id).order_by(desc(AuditLog.created_at)).offset(skip).limit(limit)
            
            if action:
                query = query.filter(AuditLog.action == action)
            if status:
                query = query.filter(AuditLog.status == status)
                
            result = await db.execute(query)
            rows = result.all()
            
            logger.debug(f"Audit lookup returned {len(rows)} rows")
            
            logs = []
            for row in rows:
                log_obj = row[0]
                user_name = row[1]
                
                log_dict = {
                    "id": log_obj.id,
                    "action": log_obj.action,
                    "actor": user_name or "System Orchestrator",
                    "resource_type": log_obj.resource_type,
                    "resource_id": log_obj.resource_id,
                    "status": log_obj.status,
                    "created_at": log_obj.created_at,
                    "ip_address": log_obj.ip_address
                }
                logs.append(log_dict)
                
        return logs
    except Exception as e:
        logger.exception(f"Error fetching audit logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))
