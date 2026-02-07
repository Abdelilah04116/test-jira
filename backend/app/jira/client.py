"""
Jira Integration Client
REST API client for Jira Cloud/Server
"""

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

import httpx
from jira import JIRA, JIRAError
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.models.schemas import (
    JiraStory,
    AcceptanceCriteria,
    TestSuite,
    JiraPublishMode,
)


class JiraClient:
    """
    Jira REST API client for fetching and updating issues
    """
    
    def __init__(
        self,
        url: Optional[str] = None,
        email: Optional[str] = None,
        api_token: Optional[str] = None
    ):
        """
        Initialize Jira client
        
        Args:
            url: Jira instance URL
            email: Jira user email
            api_token: Jira API token
        """
        self.url = url or settings.jira_url
        self.email = email or settings.jira_email
        self.api_token = api_token or settings.jira_api_token
        
        # Initialize JIRA client lazily to avoid connection errors on startup
        try:
            self.jira = JIRA(
                server=self.url,
                basic_auth=(self.email, self.api_token),
                get_server_info=False,  # Don't connect immediately
                options={
                    "verify": True,
                    "max_retries": 3
                }
            )
        except Exception as e:
            # If initialization fails (e.g. bad URL format), we log it
            # but don't crash the whole app
            from loguru import logger
            logger.error(f"Failed to initialize Jira client: {e}")
            self.jira = None
        
        # HTTP client for direct API calls
        self.http = httpx.AsyncClient(
            base_url=self.url,
            auth=(self.email, self.api_token),
            headers={"Accept": "application/json"},
            timeout=30.0
        )
        
        # Cache for custom field ID
        self._automation_field_id = None
    
    async def close(self):
        """Close HTTP client"""
        await self.http.aclose()
    
    # =========================================================================
    # Fetch Operations
    # =========================================================================
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def get_issue(self, issue_id: str) -> JiraStory:
        """
        Fetch a Jira issue by ID or key
        
        Args:
            issue_id: Issue ID or key (e.g., "PROJ-123")
        
        Returns:
            JiraStory with issue details
        
        Raises:
            JIRAError: If issue not found or access denied
        """
        try:
            # Fetch issue with expand for more fields
            issue = self.jira.issue(
                issue_id,
                expand="renderedFields,names,changelog"
            )
            
            # Extract fields
            fields = issue.fields
            
            # Parse dates
            created_at = None
            updated_at = None
            if hasattr(fields, 'created') and fields.created:
                created_at = datetime.fromisoformat(
                    fields.created.replace('Z', '+00:00')
                )
            if hasattr(fields, 'updated') and fields.updated:
                updated_at = datetime.fromisoformat(
                    fields.updated.replace('Z', '+00:00')
                )
            
            # Build custom fields dict
            custom_fields = {}
            for field in self.jira.fields():
                field_id = field.get('id', '')
                if field_id.startswith('customfield_'):
                    value = getattr(fields, field_id, None)
                    if value is not None:
                        custom_fields[field_id] = value
            
            return JiraStory(
                id=issue.id,
                key=issue.key,
                summary=fields.summary or "",
                description=fields.description or "",
                issue_type=fields.issuetype.name if fields.issuetype else "Unknown",
                status=fields.status.name if fields.status else "Unknown",
                project_key=fields.project.key if fields.project else "",
                assignee=fields.assignee.displayName if fields.assignee else None,
                reporter=fields.reporter.displayName if fields.reporter else None,
                labels=fields.labels or [],
                components=[c.name for c in (fields.components or [])],
                priority=fields.priority.name if fields.priority else None,
                created_at=created_at,
                updated_at=updated_at,
                custom_fields=custom_fields
            )
            
        except JIRAError as e:
            if e.status_code == 404:
                raise ValueError(f"Issue {issue_id} not found")
            elif e.status_code == 403:
                raise PermissionError(f"Access denied to issue {issue_id}")
            else:
                raise RuntimeError(f"Failed to fetch issue: {e.text}")
    
    async def search_issues(
        self,
        jql: str,
        max_results: int = 50,
        fields: Optional[List[str]] = None
    ) -> List[JiraStory]:
        """
        Search issues using JQL
        
        Args:
            jql: JQL query string
            max_results: Maximum results to return
            fields: Fields to include
        
        Returns:
            List of JiraStory objects
        """
        default_fields = [
            "summary", "description", "issuetype", "status",
            "project", "assignee", "reporter", "labels",
            "components", "priority", "created", "updated"
        ]
        
        issues = self.jira.search_issues(
            jql,
            maxResults=max_results,
            fields=fields or default_fields
        )
        
        stories = []
        for issue in issues:
            story = await self.get_issue(issue.key)
            stories.append(story)
        
        return stories
    
    # =========================================================================
    # Publish Operations
    # =========================================================================
    
    async def update_description(
        self,
        issue_id: str,
        content: str,
        prepend: bool = False
    ) -> bool:
        """
        Update issue description
        
        Args:
            issue_id: Issue key
            content: New content
            prepend: If True, prepend to existing description
        
        Returns:
            True if successful
        """
        try:
            issue = self.jira.issue(issue_id)
            
            if prepend and issue.fields.description:
                new_description = f"{content}\n\n---\n\n{issue.fields.description}"
            else:
                new_description = content
            
            issue.update(description=new_description)
            return True
            
        except JIRAError as e:
            raise RuntimeError(f"Failed to update description: {e.text}")
    
    async def add_comment(
        self,
        issue_id: str,
        comment_body: str
    ) -> str:
        """
        Add a comment to an issue
        
        Args:
            issue_id: Issue key
            comment_body: Comment content
        
        Returns:
            Comment ID
        """
        try:
            comment = self.jira.add_comment(issue_id, comment_body)
            return comment.id
            
        except JIRAError as e:
            raise RuntimeError(f"Failed to add comment: {e.text}")
    
    async def update_custom_field(
        self,
        issue_id: str,
        field_id: str,
        value: Any
    ) -> bool:
        """
        Update a custom field
        
        Args:
            issue_id: Issue key
            field_id: Custom field ID (e.g., "customfield_10001")
            value: New value
        
        Returns:
            True if successful
        """
        try:
            issue = self.jira.issue(issue_id)
            issue.update(fields={field_id: value})
            return True
            
        except JIRAError as e:
            raise RuntimeError(f"Failed to update custom field: {e.text}")
    
    async def update_environment_field(
        self,
        issue_id: str,
        value: str
    ) -> bool:
        """
        Update the Environment field of an issue
        
        Args:
            issue_id: Issue key
            value: New environment value (text content)
        
        Returns:
            True if successful
        """
        try:
            issue = self.jira.issue(issue_id)
            issue.update(fields={"environment": value})
            return True
            
        except JIRAError as e:
            raise RuntimeError(f"Failed to update environment field: {e.text}")
    
    async def create_subtask(
        self,
        parent_key: str,
        summary: str,
        description: str,
        issue_type: Optional[str] = None,
        extra_fields: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        Create a subtask under a parent issue
        
        Args:
            parent_key: Parent issue key
            summary: Subtask summary
            description: Subtask description
            issue_type: Issue type name (default: Sub-task)
        
        Returns:
            Created subtask key
        """
        try:
            # Get parent issue for project info
            parent = self.jira.issue(parent_key)
            project_key = parent.fields.project.key
            
            # Determine issue type
            subtask_type = issue_type or settings.jira_test_case_issue_type
            
            # Create subtask
            issue_fields = {
                "project": project_key,
                "parent": {"key": parent_key},
                "issuetype": {"name": subtask_type},
                "summary": summary,
                "description": description
            }
            
            # Merge extra fields if provided
            if extra_fields:
                issue_fields.update(extra_fields)
            
            subtask = self.jira.create_issue(fields=issue_fields)
            
            return subtask.key
            
        except JIRAError as e:
            raise RuntimeError(f"Failed to create subtask: {e.text}")
    
    async def create_linked_issue(
        self,
        project_key: str,
        issue_type: str,
        summary: str,
        description: str,
        link_to: str,
        link_type: str = "Tests"
    ) -> str:
        """
        Create an issue and link it to another issue
        
        Args:
            project_key: Project key
            issue_type: Issue type
            summary: Issue summary
            description: Issue description
            link_to: Issue key to link to
            link_type: Link type name
        
        Returns:
            Created issue key
        """
        try:
            # Create issue
            new_issue = self.jira.create_issue(
                project=project_key,
                issuetype={"name": issue_type},
                summary=summary,
                description=description
            )
            
            # Create link
            self.jira.create_issue_link(
                type=link_type,
                inwardIssue=new_issue.key,
                outwardIssue=link_to
            )
            
            return new_issue.key
            
        except JIRAError as e:
            raise RuntimeError(f"Failed to create linked issue: {e.text}")
    
    # =========================================================================
    # High-level Publish Methods
    # =========================================================================
    
    async def publish_acceptance_criteria(
        self,
        issue_id: str,
        criteria: AcceptanceCriteria,
        mode: JiraPublishMode = JiraPublishMode.DESCRIPTION
    ) -> Dict[str, Any]:
        """
        Publish acceptance criteria to Jira
        
        Args:
            issue_id: Issue key
            criteria: Acceptance criteria to publish
            mode: How to publish (description, comment, custom_field)
        
        Returns:
            Result dictionary with publication details
        """
        gherkin_text = criteria.to_gherkin_text()
        
        # Format for Jira
        formatted_content = f"""
h2. Acceptance Criteria (Generated)

{{code:language=gherkin}}
{gherkin_text}
{{code}}

_Generated at {criteria.generated_at.isoformat()} using {criteria.llm_provider}_
"""
        
        result = {
            "success": False,
            "mode": mode.value,
            "location": None
        }
        
        try:
            if mode == JiraPublishMode.DESCRIPTION:
                await self.update_description(
                    issue_id, 
                    formatted_content, 
                    prepend=True
                )
                result["location"] = "description"
                
            elif mode == JiraPublishMode.COMMENT:
                comment_id = await self.add_comment(issue_id, formatted_content)
                result["location"] = f"comment:{comment_id}"
                
            elif mode == JiraPublishMode.CUSTOM_FIELD:
                field_id = settings.jira_acceptance_criteria_field
                await self.update_custom_field(issue_id, field_id, gherkin_text)
                result["location"] = f"field:{field_id}"
            
            elif mode == JiraPublishMode.ENVIRONMENT:
                # Publish to the Environment field
                await self.update_environment_field(issue_id, gherkin_text)
                result["location"] = "environment"
            
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
        
        return result
    
    async def publish_test_scenarios(
        self,
        issue_id: str,
        test_suite: TestSuite,
        mode: JiraPublishMode = JiraPublishMode.SUBTASK
    ) -> Dict[str, Any]:
        """
        Publish test scenarios to Jira
        
        Args:
            issue_id: Issue key
            test_suite: Test scenarios to publish
            mode: How to publish (subtask, comment, xray, zephyr)
        
        Returns:
            Result dictionary with publication details
        """
        result = {
            "success": False,
            "mode": mode.value,
            "created_issues": [],
            "comments": []
        }
        
        try:
            if mode == JiraPublishMode.SUBTASK:
                # Create a subtask for each test scenario
                for scenario in test_suite.scenarios:
                    # Format description
                    description = self._format_test_scenario_description(scenario)
                    
                    has_code = hasattr(scenario, 'playwright_code') and scenario.playwright_code
                    
                    if has_code:
                        # Append code to description
                        description += "\n\nh3. Automation Script (Playwright)\n{code:typescript}\n"
                        description += scenario.playwright_code
                        description += "\n{code}"
                    
                    subtask_key = await self.create_subtask(
                        parent_key=issue_id,
                        summary=f"[TEST] {scenario.title}",
                        description=description
                    )
                    
                    # Transition to 'Automation Script' status if possible
                    # User indicated 'Automation Script' is a status in the Kanban board
                    await self.transition_issue(subtask_key, "Automation Script")
                    
                    result["created_issues"].append({
                        "key": subtask_key,
                        "test_id": scenario.id,
                        "title": scenario.title,
                        "status": "Automation Script"
                    })
                
            elif mode == JiraPublishMode.COMMENT:
                # Create a single comment with all test scenarios
                comment_body = self._format_test_suite_comment(test_suite)
                comment_id = await self.add_comment(issue_id, comment_body)
                result["comments"].append(comment_id)
            
            result["success"] = True
            
        except Exception as e:
            result["error"] = str(e)
        
        return result

    async def transition_issue(self, issue_key: str, status_name: str) -> bool:
        """
        Transition an issue to a new status
        
        Args:
            issue_key: Issue key
            status_name: Target status name (e.g. "Automation Script", "Done")
            
        Returns:
            True if successful
        """
        try:
            # Check available transitions
            transitions = self.jira.transitions(issue_key)
            target_transition_id = None
            
            # Case-insensitive search for transition
            status_lower = status_name.lower()
            
            for t in transitions:
                t_name = t.get('name', '').lower()
                t_to_name = t.get('to', {}).get('name', '').lower()
                
                # Check match on transition name OR target status name
                if t_name == status_lower or t_to_name == status_lower:
                    target_transition_id = t['id']
                    break
            
            if target_transition_id:
                self.jira.transition_issue(issue_key, target_transition_id)
                return True
            else:
                from loguru import logger
                available = [f"{t.get('name')}->{t.get('to', {}).get('name')}" for t in transitions]
                logger.warning(f"Could not find transition to '{status_name}' for {issue_key}. Available: {available}")
                return False
                
        except JIRAError as e:
            from loguru import logger
            logger.error(f"Failed to transition issue {issue_key}: {e.text}")
            return False
    
    def _format_test_scenario_description(self, scenario) -> str:
        """Format test scenario for Jira description"""
        lines = [
            f"h3. {scenario.title}",
            "",
            f"*Type:* {scenario.type.value}",
            f"*Priority:* {scenario.priority}",
            f"*Linked to:* {scenario.acceptance_criteria_ref}",
            f"*Est. Duration:* {scenario.estimated_duration_minutes} minutes",
            "",
            "h4. Description",
            scenario.description,
            "",
        ]
        
        if scenario.preconditions:
            lines.extend([
                "h4. Preconditions",
                "",
            ])
            for pre in scenario.preconditions:
                lines.append(f"* {pre}")
            lines.append("")
        
        lines.extend([
            "h4. Test Steps",
            "",
            "||Step||Action||Expected Result||Test Data||",
        ])
        
        for step in scenario.steps:
            data = step.test_data or "-"
            lines.append(
                f"|{step.order}|{step.action}|{step.expected_result}|{data}|"
            )
        


        if scenario.tags:
            lines.extend([
                "",
                f"*Tags:* {', '.join(scenario.tags)}"
            ])
        
        return "\n".join(lines)
    
    def _format_test_suite_comment(self, test_suite: TestSuite) -> str:
        """Format entire test suite as a comment"""
        lines = [
            f"h2. Test Scenarios for {test_suite.story_key}",
            "",
            f"*Total Scenarios:* {test_suite.total_scenarios}",
            f"*Positive:* {test_suite.positive_count}",
            f"*Negative:* {test_suite.negative_count}",
            f"*Edge Cases:* {test_suite.edge_case_count}",
            "",
            "---",
            "",
        ]
        
        for scenario in test_suite.scenarios:
            lines.append(self._format_test_scenario_description(scenario))
            lines.append("")
            lines.append("---")
            lines.append("")
        
        lines.append(
            f"_Generated at {test_suite.generated_at.isoformat()} "
            f"using {test_suite.llm_provider}_"
        )
        
        return "\n".join(lines)
    
    # =========================================================================
    # Utility Methods
    # =========================================================================
    
    async def get_issue_types(self, project_key: str) -> List[Dict[str, str]]:
        """Get available issue types for a project"""
        project = self.jira.project(project_key)
        return [
            {"id": it.id, "name": it.name}
            for it in project.issueTypes
        ]
    
    async def get_custom_fields(self) -> List[Dict[str, str]]:
        """Get all custom fields"""
        fields = self.jira.fields()
        return [
            {"id": f["id"], "name": f["name"]}
            for f in fields
            if f["id"].startswith("customfield_")
        ]
    
    async def validate_connection(self) -> bool:
        """Test the Jira connection"""
        try:
            self.jira.myself()
            return True
        except Exception:
            return False

    async def get_or_create_automation_field(self) -> Optional[str]:
        """
        Finds or creates the 'Automation Script' custom field.
        Returns the field ID (e.g., 'customfield_10045').
        """
        if self._automation_field_id:
            return self._automation_field_id
            
        try:
            # 1. Search existing fields
            fields = self.jira.fields()
            
            # Direct match check first
            for field in fields:
                if field['name'] == "Automation Script":
                    self._automation_field_id = field['id']
                    return field['id']

            # Case-insensitive check
            from loguru import logger
            normalized_target = "automation script"
            
            potential_matches = []
            for field in fields:
                field_name_lower = field['name'].lower().strip()
                
                if field_name_lower == normalized_target:
                    logger.info(f"Found 'Automation Script' field with different casing: '{field['name']}' ({field['id']})")
                    self._automation_field_id = field['id']
                    return field['id']
                
                if "automation" in field_name_lower and "script" in field_name_lower:
                    potential_matches.append(f"{field['name']} ({field['id']})")

            # If we get here, we didn't find it. Log helpful info before trying to create.
            if potential_matches:
                logger.warning(f"Exact 'Automation Script' not found. Similar fields: {', '.join(potential_matches)}")
            else:
                # Log count and first few to verify we are fetching fields
                logger.warning(f"Automation Script field not found. Total fields visible: {len(fields)}")

            # 2. Create if not found
            # Using raw POST request because jira-python might not wrap field creation easily
            response = await self.http.post("/rest/api/3/field", json={
                "name": "Automation Script",
                "description": "Generated Playwright automation code",
                "type": "com.atlassian.jira.plugin.system.customfieldtypes:textarea",
                "searcherKey": "com.atlassian.jira.plugin.system.customfieldtypes:textsearcher"
            })
            
            if response.status_code == 201:
                data = response.json()
                self._automation_field_id = data['id']
                return data['id']
            else:
                from loguru import logger
                logger.warning(f"Could not create custom field: {response.text}")
                return None
                
        except Exception as e:
            from loguru import logger
            logger.error(f"Error handling automation field: {e}")
            return None
