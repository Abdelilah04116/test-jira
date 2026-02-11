"""
Generic and Multi-Platform Webhook Handlers
Supports Azure DevOps, GitHub, and other triggers.
"""

from typing import Any, Dict
from fastapi import APIRouter, BackgroundTasks, Body, Header, HTTPException
from loguru import logger

from app.agents.orchestrator import OrchestratorAgent
from app.core.config import settings

router = APIRouter(prefix="/webhooks", tags=["Webhooks"])


async def run_pipeline_task(platform: str, issue_id: str):
    """Run the agentic pipeline in the background."""
    logger.info(f"🚀 [{platform}] Webhook received — Starting Pipeline for {issue_id}")
    orchestrator = OrchestratorAgent()
    try:
        # The OrchestratorAgent already handles Jira vs ADO detection via issue_id format
        # but we can be explicit here if needed.
        result = await orchestrator.run_full_agentic_pipeline(
            issue_id=issue_id,
            user_id=f"webhook-{platform.lower()}",
            auto_publish=True,
            auto_push_git=settings.git_auto_push
        )
        logger.info(f"✅ [{platform}] Pipeline finished for {issue_id}: success={result.get('success')}")
    except Exception as e:
        logger.error(f"❌ [{platform}] Pipeline task failed: {e}")
    finally:
        await orchestrator.jira_client.close()
        await orchestrator.az_client.close()


@router.post("/azure-devops")
async def handle_azure_devops_webhook(
    background_tasks: BackgroundTasks,
    payload: Dict[str, Any] = Body(...)
):
    """
    Handle Azure DevOps Service Hooks
    Trigger: Work item created
    """
    try:
        event_type = payload.get("eventType")
        resource = payload.get("resource", {})
        
        # We look for workitem.created
        if event_type == "workitem.created":
            work_item_id = str(resource.get("id"))
            if work_item_id:
                # ADO IDs are numeric, we can prefix with ADO- for the orchestrator
                background_tasks.add_task(run_pipeline_task, "AzureDevOps", work_item_id)
                return {"status": "accepted", "id": work_item_id}
        
        return {"status": "ignored", "event": event_type}
    except Exception as e:
        logger.error(f"Error processing ADO webhook: {e}")
        return {"status": "error", "message": str(e)}


@router.post("/github")
async def handle_github_webhook(
    background_tasks: BackgroundTasks,
    x_github_event: str = Header(None),
    payload: Dict[str, Any] = Body(...)
):
    """
    Handle GitHub Webhooks
    Trigger: Issues created (optional use case)
    """
    try:
        if x_github_event == "issues":
            action = payload.get("action")
            if action == "opened":
                issue_number = str(payload.get("issue", {}).get("number"))
                background_tasks.add_task(run_pipeline_task, "GitHub", issue_number)
                return {"status": "accepted", "id": issue_number}
        
        return {"status": "ignored", "event": x_github_event}
    except Exception as e:
        logger.error(f"Error processing GitHub webhook: {e}")
        return {"status": "error", "message": str(e)}
