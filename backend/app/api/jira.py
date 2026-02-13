"""
Jira API Endpoints
Jira integration and story management
"""

from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Body, BackgroundTasks
from loguru import logger

from app.api.deps import (
    get_current_user,
    get_jira_client,
    check_rate_limit,
    require_role
)
from app.jira.client import JiraClient
from app.models.schemas import (
    JiraStory,
    JiraPublishRequest,
    JiraPublishResponse,
    FullPipelineRequest,
    JiraPublishMode,
    LLMProvider
)
from app.services.generator import QAGeneratorService, get_qa_generator_service
from app.models.schemas import JiraConfigRequest, JiraConfigResponse
from app.core.database import get_db
from app.models.database import JiraConfiguration
from app.core.security import encrypt_api_key
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select


router = APIRouter(prefix="/jira", tags=["Jira"])


@router.get("/story/{issue_id}", response_model=JiraStory)
async def get_story(
    issue_id: str,
    jira: JiraClient = Depends(get_jira_client),
    current_user = Depends(get_current_user),
    _: None = Depends(check_rate_limit)
):
    """
    Fetch a user story from Jira
    
    - **issue_id**: Jira issue ID or key (e.g., "PROJ-123")
    
    Returns complete story details including title, description, and metadata.
    """
    try:
        story = await jira.get_issue(issue_id)
        logger.info(f"User {current_user.email} fetched story: {issue_id}")
        return story
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to fetch story {issue_id}: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch story: {e}")


@router.get("/search", response_model=List[JiraStory])
async def search_stories(
    jql: str = Query(..., description="JQL query string"),
    max_results: int = Query(default=50, le=100),
    jira: JiraClient = Depends(get_jira_client),
    current_user = Depends(get_current_user),
    _: None = Depends(check_rate_limit)
):
    """
    Search Jira issues using JQL
    
    - **jql**: JQL query string (e.g., "project = PROJ AND type = Story")
    - **max_results**: Maximum number of results (max 100)
    
    Returns list of matching stories.
    """
    try:
        stories = await jira.search_issues(jql, max_results=max_results)
        logger.info(
            f"User {current_user.email} searched stories: {jql} "
            f"({len(stories)} results)"
        )
        return stories
    except Exception as e:
        logger.error(f"Search failed: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@router.post("/publish", response_model=JiraPublishResponse)
async def publish_to_jira(
    request: JiraPublishRequest,
    jira: JiraClient = Depends(get_jira_client),
    current_user = Depends(get_current_user),
    _: None = Depends(check_rate_limit)
):
    """
    Publish generated content to Jira
    
    - **issue_id**: Target Jira issue ID
    - **acceptance_criteria**: Generated acceptance criteria to publish
    - **test_suite**: Generated test scenarios to publish
    - **publish_mode**: How to publish (subtask, comment, custom_field, description)
    
    This endpoint publishes both acceptance criteria and test scenarios to the
    specified Jira issue according to the selected mode.
    """
    service = QAGeneratorService(jira_client=jira)
    
    try:
        result = await service.publish_to_jira(request)
        logger.info(
            f"User {current_user.email} published to Jira: {request.issue_id} "
            f"(AC: {result.acceptance_criteria_published}, "
            f"Tests: {result.test_scenarios_published})"
        )
        return result
    except Exception as e:
        logger.error(f"Publish failed: {e}")
        raise HTTPException(status_code=500, detail=f"Publish failed: {e}")


@router.get("/validate")
async def validate_connection(
    jira: JiraClient = Depends(get_jira_client),
    current_user = Depends(get_current_user)
):
    """
    Validate Jira connection
    
    Returns connection status and current user info from Jira.
    """
    try:
        is_valid = await jira.validate_connection()
        return {
            "connected": is_valid,
            "url": jira.url,
            "email": jira.email
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }

@router.get("/config", response_model=Optional[JiraConfigResponse])
async def get_jira_config(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(["admin", "qa"]))
):
    """Get current Jira configuration"""
    result = await db.execute(select(JiraConfiguration).order_by(JiraConfiguration.updated_at.desc()))
    config = result.scalars().first()
    
    if not config:
        # Fallback to settings
        from app.core.config import settings
        from datetime import datetime
        return {
            "url": settings.jira_url,
            "email": settings.jira_email,
            "project_key": settings.jira_project_key,
            "is_active": True,
            "updated_at": datetime.utcnow()
        }
        
    return {
        "url": config.jira_url,
        "email": config.jira_email,
        "project_key": config.default_project_key,
        "is_active": config.is_active,
        "updated_at": config.updated_at
    }

@router.post("/config", response_model=JiraConfigResponse)
async def update_jira_config(
    request: JiraConfigRequest,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(require_role(["admin"]))
):
    """Update Jira configuration (Admin only)"""
    encrypted_token = encrypt_api_key(request.api_token)
    
    # Check if we have an existing config
    result = await db.execute(select(JiraConfiguration))
    config = result.scalars().first()
    
    if config:
        config.jira_url = request.url
        config.jira_email = request.email
        config.jira_api_token_encrypted = encrypted_token
        config.default_project_key = request.project_key
    else:
        config = JiraConfiguration(
            jira_url=request.url,
            jira_email=request.email,
            jira_api_token_encrypted=encrypted_token,
            default_project_key=request.project_key
        )
        db.add(config)
    
    # Commit is handled by get_db dependency if it's yielding
    # But wait, our get_db in deps.py is a generator.
    # Actually, let's just use it.
    
    await db.commit()
    await db.refresh(config)
    
    return {
        "url": config.jira_url,
        "email": config.jira_email,
        "project_key": config.default_project_key,
        "is_active": config.is_active,
        "updated_at": config.updated_at
    }


@router.get("/issue-types/{project_key}")
async def get_issue_types(
    project_key: str,
    jira: JiraClient = Depends(get_jira_client),
    current_user = Depends(get_current_user)
):
    """
    Get available issue types for a project
    
    - **project_key**: Jira project key (e.g., "PROJ")
    
    Returns list of issue types available in the project.
    """
    try:
        types = await jira.get_issue_types(project_key)
        return {"project_key": project_key, "issue_types": types}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/custom-fields")
async def get_custom_fields(
    jira: JiraClient = Depends(get_jira_client),
    current_user = Depends(require_role(["admin"]))
):
    """
    Get all custom fields (Admin only)
    
    Returns list of custom field IDs and names for configuration.
    """
    try:
        fields = await jira.get_custom_fields()
        return {"custom_fields": fields}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


async def process_webhook_background(issue_id: str, issue_key: str):
    """
    Background task to process webhook event via the Orchestrator Agent.
    
    This triggers the full multi-agent agentic pipeline:
      1. Fetch Story → 2. Generate AC → 3. Generate Tests
      4. AutomationEngineer → 5. CodeReviewer → 6. GitOps → 7. Jira Publish
    """
    from app.agents.orchestrator import OrchestratorAgent
    from app.core.config import settings
    
    logger.info(f"🚀 Webhook received — Starting Agentic Pipeline for {issue_key}")
    
    try:
        orchestrator = OrchestratorAgent()
        
        result = await orchestrator.run_full_agentic_pipeline(
            issue_id=issue_key,
            user_id="system-webhook",
            auto_publish=True,
            auto_push_git=getattr(settings, 'git_auto_push', False),
            publish_mode=JiraPublishMode.SUBTASK,
        )
        
        await orchestrator.jira_client.close()
        
        if result.get("success"):
            logger.info(
                f"✅ Agentic Pipeline completed for {issue_key} "
                f"in {result.get('total_processing_time_seconds', 0):.2f}s — "
                f"Files: {len(result.get('git_result', {}).get('files_created', []))}, "
                f"Reviews: {len(result.get('code_reviews', []))}"
            )
        else:
            logger.warning(f"⚠️ Agentic Pipeline partially failed for {issue_key}")
        
    except Exception as e:
        logger.error(f"❌ Agentic Pipeline failed for {issue_key}: {e}")


@router.post("/webhook")
async def handle_jira_webhook(
    background_tasks: BackgroundTasks,
    payload: Dict[str, Any] = Body(...)
):
    """
    Handle incoming Jira webhooks
    
    Triggered when an issue is created.
    """
    try:
        from app.core.database import get_db_context
        from app.models.database import JiraConfiguration
        from sqlalchemy import select

        event = payload.get("webhookEvent")
        
        # We only care about issue_created
        if event != "jira:issue_created":
            return {"status": "ignored", "reason": f"Event {event} not handled"}
        
        issue = payload.get("issue", {})
        fields = issue.get("fields", {})
        
        issue_key = issue.get("key")
        issue_id = issue.get("id")
        issue_type = fields.get("issuetype", {}).get("name")
        project_key_received = fields.get("project", {}).get("key")
        
        if not issue_key:
            return {"status": "ignored", "reason": "No issue key found"}

        # Fetch Default Project Key from Config
        target_project_key = settings.jira_project_key
        async with get_db_context() as db:
            result = await db.execute(select(JiraConfiguration).order_by(JiraConfiguration.updated_at.desc()))
            db_config = result.scalars().first()
            if db_config and db_config.default_project_key:
                target_project_key = db_config.default_project_key

        # Filter by Project Key if target exists
        if target_project_key and project_key_received != target_project_key:
            logger.info(f"Ignoring webhook for {issue_key}: Project {project_key_received} != {target_project_key}")
            return {"status": "ignored", "reason": f"Project {project_key_received} not monitored"}
            
        # Filter for Stories only (or configure as needed)
        if issue_type != "Story":
            logger.info(f"Ignoring webhook for issue {issue_key}: Type is {issue_type}, expected Story")
            return {"status": "ignored", "reason": f"Type {issue_type} not supported"}
            
        logger.info(f"Received webhook for new story: {issue_key} in project {project_key_received}. Triggering pipeline.")
        
        # Trigger background task
        background_tasks.add_task(process_webhook_background, issue_id, issue_key)
        
        return {"status": "accepted", "message": f"Pipeline triggered for {issue_key}"}
        
    except Exception as e:
        logger.error(f"Webhook error: {e}")
        raise HTTPException(status_code=500, detail="Webhook processing failed")
