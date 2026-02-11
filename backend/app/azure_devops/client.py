"""
Azure DevOps Integration Client
REST API client for Azure DevOps Boards and Repos
"""

import base64
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from loguru import logger

from app.core.config import settings
from app.models.schemas import (
    JiraStory,
    AcceptanceCriteria,
    TestSuite,
)


class AzureDevOpsClient:
    """
    Azure DevOps REST API client for fetching and updating work items
    """
    
    def __init__(
        self,
        org: Optional[str] = None,
        project: Optional[str] = None,
        pat: Optional[str] = None
    ):
        """
        Initialize Azure DevOps client
        
        Args:
            org: Azure DevOps organization name
            project: Project name
            pat: Personal Access Token
        """
        self.org = org or settings.azure_devops_org
        self.project = project or settings.azure_devops_project
        self.pat = pat or settings.azure_devops_pat
        
        # Azure DevOps uses basic auth with empty username and PAT as password
        if self.pat:
            auth_str = f":{self.pat}"
            encoded_auth = base64.b64encode(auth_str.encode()).decode()
            self.headers = {
                "Authorization": f"Basic {encoded_auth}",
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
        else:
            self.headers = {}
            
        self.base_url = f"https://dev.azure.com/{self.org}/{self.project}/_apis"
        self.http = httpx.AsyncClient(
            headers=self.headers,
            timeout=30.0
        )
    
    async def close(self):
        """Close HTTP client"""
        await self.http.aclose()
    
    async def get_work_item(self, work_item_id: str) -> JiraStory:
        """
        Fetch an Azure DevOps work item by ID
        
        Note: We reuse the JiraStory model for compatibility with the existing pipeline
        Mapping:
          - ID -> id
          - System.Title -> summary
          - System.Description -> description
          - Microsoft.VSTS.Common.AcceptanceCriteria -> acceptance_criteria (custom mapping)
        """
        if not self.org or not self.project:
            raise ValueError("Azure DevOps Organization and Project must be configured")
            
        url = f"{self.base_url}/wit/workitems/{work_item_id}?api-version=7.1"
        
        try:
            response = await self.http.get(url)
            response.raise_for_status()
            data = response.json()
            
            fields = data.get("fields", {})
            
            # Extract fields
            summary = fields.get("System.Title", "")
            description = fields.get("System.Description", "")
            ac_raw = fields.get(settings.azure_devops_ac_field, "")
            
            # If description is empty but AC is not, use AC as part of description if needed
            # For our pipeline, we map it to JiraStory
            
            created_at = fields.get("System.CreatedDate")
            updated_at = fields.get("System.ChangedDate")
            
            if created_at:
                created_at = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            if updated_at:
                updated_at = datetime.fromisoformat(updated_at.replace('Z', '+00:00'))
                
            return JiraStory(
                id=str(work_item_id),
                key=f"ADO-{work_item_id}",
                summary=summary,
                description=description,
                issue_type=fields.get("System.WorkItemType", "Work Item"),
                status=fields.get("System.State", "Unknown"),
                project_key=self.project,
                assignee=fields.get("System.AssignedTo", {}).get("displayName"),
                reporter=fields.get("System.CreatedBy", {}).get("displayName"),
                labels=fields.get("System.Tags", "").split("; ") if fields.get("System.Tags") else [],
                components=[],
                priority=str(fields.get("Microsoft.VSTS.Common.Priority", "")),
                created_at=created_at,
                updated_at=updated_at,
                custom_fields={
                    "acceptance_criteria": ac_raw
                }
            )
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                raise ValueError(f"Work Item {work_item_id} not found")
            raise RuntimeError(f"Failed to fetch Azure DevOps work item: {e}")
            
    async def publish_to_work_item(
        self,
        work_item_id: str,
        acceptance_criteria: Optional[str] = None,
        test_suite_desc: Optional[str] = None
    ) -> bool:
        """
        Update a work item with generated data
        """
        url = f"{self.base_url}/wit/workitems/{work_item_id}?api-version=7.1"
        
        patch_operations = []
        
        if acceptance_criteria:
            patch_operations.append({
                "op": "add",
                "path": f"/fields/{settings.azure_devops_ac_field}",
                "value": acceptance_criteria
            })
            
        if test_suite_desc:
            # Append to description or specific field
            patch_operations.append({
                "op": "add",
                "path": f"/fields/{settings.azure_devops_desc_field}",
                "value": test_suite_desc
            })
            
        if not patch_operations:
            return True
            
        try:
            # Azure DevOps requires Content-Type: application/json-patch+json
            headers = self.headers.copy()
            headers["Content-Type"] = "application/json-patch+json"
            
            response = await self.http.patch(url, json=patch_operations, headers=headers)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to update Azure DevOps work item: {e}")
            return False
