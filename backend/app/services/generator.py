"""
QA Generator Service
Core business logic for generating acceptance criteria and test scenarios
"""

import time
import asyncio
import uuid
from datetime import datetime, timezone
from fastapi import HTTPException
from fastapi.encoders import jsonable_encoder
from typing import Any, Dict, List, Optional

from loguru import logger

from app.core.config import settings
from app.llm.factory import get_llm_client
from app.llm.base import BaseLLMClient
from app.jira.client import JiraClient
from app.models.database import GenerationHistory
from app.core.database import get_db_context
from app.services.audit import audit_service
from app.models.schemas import (
    JiraStory,
    AcceptanceCriteria,
    GherkinScenario,
    TestSuite,
    TestScenario,
    TestStep,
    TestScenarioType,
    JiraPublishMode,
    LLMProvider,
    GenerateAcceptanceCriteriaRequest,
    GenerateAcceptanceCriteriaResponse,
    GenerateTestScenariosRequest,
    GenerateTestScenariosResponse,
    JiraPublishRequest,
    JiraPublishResponse,
    FullPipelineRequest,
    FullPipelineResponse,
)
from app.prompts.templates import (
    SYSTEM_PROMPT_GHERKIN_GENERATOR,
    SYSTEM_PROMPT_TEST_GENERATOR,
    PROMPT_GENERATE_ACCEPTANCE_CRITERIA,
    PROMPT_GENERATE_TEST_SCENARIOS,
    ACCEPTANCE_CRITERIA_SCHEMA,
    TEST_SCENARIOS_SCHEMA,
    PROMPT_GENERATE_PLAYWRIGHT_CODE,
)
from app.agents.automation_engineer import AutomationEngineerAgent


class QAGeneratorService:
    """
    Main service for QA generation workflow
    """
    
    def __init__(
        self,
        jira_client: Optional[JiraClient] = None,
        llm_provider: Optional[str] = None
    ):
        """
        Initialize the service
        
        Args:
            jira_client: Optional pre-configured Jira client
            llm_provider: Override for default LLM provider
        """
        self.jira_client = jira_client or JiraClient()
        self.default_llm_provider = llm_provider or settings.llm_provider
    
    def _get_llm_client(
        self, 
        provider: Optional[LLMProvider] = None
    ) -> BaseLLMClient:
        """Get LLM client for the specified or default provider"""
        provider_name = provider.value if provider else self.default_llm_provider
        return get_llm_client(provider=provider_name)
    
    # =========================================================================
    # Fetch Story
    # =========================================================================
    
    async def fetch_story(self, issue_id: str) -> JiraStory:
        """
        Fetch a user story from Jira
        
        Args:
            issue_id: Jira issue ID or key
        
        Returns:
            JiraStory with full details
        """
        logger.info(f"Fetching story: {issue_id}")
        story = await self.jira_client.get_issue(issue_id)
        logger.info(f"Fetched story: {story.key} - {story.summary}")
        return story
    
    # =========================================================================
    # Generate Acceptance Criteria
    # =========================================================================
    
    async def generate_acceptance_criteria(
        self,
        request: GenerateAcceptanceCriteriaRequest
    ) -> GenerateAcceptanceCriteriaResponse:
        """
        Generate acceptance criteria for a user story
        
        Args:
            request: Generation request with story details
        
        Returns:
            Response with generated Gherkin criteria
        """
        start_time = time.time()
        
        # Get story details
        if request.issue_id:
            story = await self.fetch_story(request.issue_id)
            story_key = story.key
            story_title = story.summary
            story_description = story.description or ""
        else:
            story_key = f"STORY-{uuid.uuid4().hex[:8].upper()}"
            story_title = request.story_title or "User Story"
            story_description = request.story_text or ""
        
        logger.info(f"Generating acceptance criteria for: {story_key}")
        
        # Prepare prompt
        prompt = PROMPT_GENERATE_ACCEPTANCE_CRITERIA.format(
            story_title=story_title,
            story_description=story_description,
            context=request.context or "No additional context provided.",
            max_scenarios=request.max_scenarios
        )
        
        # Get LLM client and generate
        llm = self._get_llm_client(request.llm_provider)
        
        try:
            result = await llm.generate_json(
                prompt=prompt,
                schema=ACCEPTANCE_CRITERIA_SCHEMA,
                system_prompt=SYSTEM_PROMPT_GHERKIN_GENERATOR
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise RuntimeError(f"Failed to generate acceptance criteria: {e}")
        
        # Parse result into AcceptanceCriteria
        scenarios = []
        for sc in result.get("scenarios", []):
            scenarios.append(GherkinScenario(
                id=sc.get("id", f"AC-{len(scenarios)+1:03d}"),
                title=sc.get("title", ""),
                given=sc.get("given", []),
                when=sc.get("when", []),
                then=sc.get("then", []),
                tags=sc.get("tags", []),
                examples=sc.get("examples")
            ))
        
        acceptance_criteria = AcceptanceCriteria(
            story_key=story_key,
            feature_name=result.get("feature_name", story_title),
            background=result.get("background"),
            scenarios=scenarios,
            generated_at=datetime.utcnow(),
            llm_provider=llm.provider_name
        )
        
        processing_time = time.time() - start_time
        logger.info(
            f"Generated {len(scenarios)} acceptance criteria scenarios "
            f"in {processing_time:.2f}s"
        )
        
        # Save to database
        try:
            async with get_db_context() as db:
                history = GenerationHistory(
                    user_id=request.user_id if hasattr(request, 'user_id') else None,
                    jira_issue_key=story_key,
                    jira_issue_summary=story_title,
                    llm_provider=llm.provider_name,
                    acceptance_criteria_json=result,
                    gherkin_text=acceptance_criteria.to_gherkin_text(),
                    processing_time_seconds=processing_time,
                    acceptance_criteria_count=len(scenarios)
                )
                db.add(history)
            
            await audit_service.log(
                action="generate_ac",
                user_id=request.user_id if hasattr(request, 'user_id') else None,
                resource_type="jira_issue",
                resource_id=story_key,
                details={"scenarios_count": len(scenarios)}
            )
        except Exception as e:
            logger.warning(f"Failed to save generation history: {e}")
        
        return GenerateAcceptanceCriteriaResponse(
            success=True,
            story_key=story_key,
            acceptance_criteria=acceptance_criteria,
            gherkin_text=acceptance_criteria.to_gherkin_text(),
            processing_time_seconds=processing_time
        )
    
    # =========================================================================
    # Generate Test Scenarios
    # =========================================================================
    
    async def generate_test_scenarios(
        self,
        request: GenerateTestScenariosRequest
    ) -> GenerateTestScenariosResponse:
        """
        Generate test scenarios based on acceptance criteria
        
        Args:
            request: Generation request with criteria
        
        Returns:
            Response with generated test scenarios
        """
        start_time = time.time()
        
        # Get or generate acceptance criteria
        if request.acceptance_criteria:
            criteria = request.acceptance_criteria
            story_key = criteria.story_key
        elif request.issue_id:
            # First generate acceptance criteria
            ac_response = await self.generate_acceptance_criteria(
                GenerateAcceptanceCriteriaRequest(
                    issue_id=request.issue_id,
                    llm_provider=request.llm_provider,
                    user_id=getattr(request, 'user_id', None)
                )
            )
            criteria = ac_response.acceptance_criteria
            story_key = criteria.story_key
        else:
            raise ValueError(
                "Either issue_id or acceptance_criteria must be provided"
            )
        
        logger.info(f"Generating test scenarios for: {story_key}")
        
        # Prepare prompt
        gherkin_text = criteria.to_gherkin_text()
        prompt = PROMPT_GENERATE_TEST_SCENARIOS.format(
            story_key=story_key,
            story_title=criteria.feature_name,
            acceptance_criteria_gherkin=gherkin_text,
            max_scenarios_per_criteria=request.max_scenarios_per_criteria,
            include_positive=request.include_negative,  # Always include positive
            include_negative=request.include_negative,
            include_edge_cases=request.include_edge_cases
        )
        
        # Get LLM client and generate
        llm = self._get_llm_client(request.llm_provider)
        
        try:
            result = await llm.generate_json(
                prompt=prompt,
                schema=TEST_SCENARIOS_SCHEMA,
                system_prompt=SYSTEM_PROMPT_TEST_GENERATOR
            )
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            raise RuntimeError(f"Failed to generate test scenarios: {e}")
        
        # Parse result into TestSuite
        scenarios = []
        for ts in result.get("scenarios", []):
            steps = []
            for step in ts.get("steps", []):
                steps.append(TestStep(
                    order=step.get("order", len(steps) + 1),
                    action=step.get("action", ""),
                    expected_result=step.get("expected_result", ""),
                    test_data=step.get("test_data")
                ))
            
            scenarios.append(TestScenario(
                id=ts.get("id", f"TS-{len(scenarios)+1:03d}"),
                title=ts.get("title", ""),
                description=ts.get("description", ""),
                type=TestScenarioType(ts.get("type", "positive")),
                priority=ts.get("priority", "Medium"),
                preconditions=ts.get("preconditions", []),
                steps=steps,
                acceptance_criteria_ref=ts.get("acceptance_criteria_ref", ""),
                tags=ts.get("tags", []),
                estimated_duration_minutes=ts.get("estimated_duration_minutes", 5)
            ))
            
        # Generate Playwright code sequentially to avoid rate limits
        logger.info(f"Generating Playwright code with AutomationEngineerAgent for {len(scenarios)} scenarios...")
        
        # Instantiate the specialist agent
        automation_agent = AutomationEngineerAgent(llm)
        
        for i, scenario in enumerate(scenarios):
            if i > 0:
                await asyncio.sleep(2)  # Delay between calls to avoid rate limits
            code = await automation_agent.generate_code(scenario)
            scenario.playwright_code = code
        
        test_suite = TestSuite(
            story_key=story_key,
            suite_name=result.get("suite_name", f"Test Suite for {story_key}"),
            scenarios=scenarios,
            generated_at=datetime.utcnow(),
            llm_provider=llm.provider_name
        )
        
        processing_time = time.time() - start_time
        logger.info(
            f"Generated {len(scenarios)} test scenarios "
            f"in {processing_time:.2f}s"
        )
        
        await audit_service.log(
            action="generate_test_scenarios",
            user_id=request.user_id if hasattr(request, 'user_id') else None,
            resource_type="test_suite",
            resource_id=story_key,
            details={"scenarios_count": len(scenarios)}
        )
        
        return GenerateTestScenariosResponse(
            success=True,
            story_key=story_key,
            test_suite=test_suite,
            processing_time_seconds=processing_time
        )
    
    # =========================================================================
    # Publish to Jira
    # =========================================================================
    
    async def publish_to_jira(
        self,
        request: JiraPublishRequest
    ) -> JiraPublishResponse:
        """
        Publish generated content to Jira
        
        Args:
            request: Publish request with content and mode
        
        Returns:
            Response with publication details
        """
        logger.info(f"Publishing to Jira: {request.issue_id}")
        
        results = {
            "ac_published": False,
            "ac_location": None,
            "tests_published": False,
            "subtasks": []
        }
        
        # Publish acceptance criteria
        if request.acceptance_criteria:
            ac_result = await self.jira_client.publish_acceptance_criteria(
                issue_id=request.issue_id,
                criteria=request.acceptance_criteria,
                mode=request.ac_publish_mode  # Use dedicated AC publish mode (defaults to environment)
            )
            results["ac_published"] = ac_result["success"]
            results["ac_location"] = ac_result.get("location")
            
            if not ac_result["success"]:
                logger.error(f"Failed to publish AC: {ac_result.get('error')}")
        
        # Publish test scenarios
        if request.test_suite:
            test_result = await self.jira_client.publish_test_scenarios(
                issue_id=request.issue_id,
                test_suite=request.test_suite,
                mode=request.publish_mode
            )
            results["tests_published"] = test_result["success"]
            results["subtasks"] = test_result.get("created_issues", [])
            
            if not test_result["success"]:
                logger.error(
                    f"Failed to publish tests: {test_result.get('error')}"
                )
        
        # Build response
        jira_link = f"{settings.jira_url}/browse/{request.issue_id}"
        
        success = results["ac_published"] or results["tests_published"]
        message_parts = []
        
        if results["ac_published"]:
            message_parts.append(
                f"Acceptance criteria published to {results['ac_location']}"
            )
        if results["tests_published"]:
            message_parts.append(
                f"{len(results['subtasks'])} test scenarios published"
            )
        
        await audit_service.log(
            action="jira_sync",
            resource_type="jira_issue",
            resource_id=request.issue_id,
            details={
                "ac_published": results["ac_published"],
                "tests_published": results["tests_published"],
                "subtasks_count": len(results["subtasks"])
            }
        )
        
        return JiraPublishResponse(
            success=success,
            issue_key=request.issue_id,
            acceptance_criteria_published=results["ac_published"],
            acceptance_criteria_location=results["ac_location"],
            test_scenarios_published=results["tests_published"],
            created_subtasks=results["subtasks"],
            jira_link=jira_link,
            message=" | ".join(message_parts) if message_parts else "No content published"
        )
    
    # =========================================================================
    # Full Pipeline
    # =========================================================================
    
    async def run_full_pipeline(
        self,
        request: FullPipelineRequest
    ) -> FullPipelineResponse:
        """
        Run the complete generation and publish pipeline
        
        Args:
            request: Full pipeline request
        
        Returns:
            Complete response with all generated content
        """
        start_time = time.time()
        steps_completed = []
        
        logger.info(f"Starting full pipeline for: {request.issue_id}")
        
        # Step 1: Fetch story
        story = await self.fetch_story(request.issue_id)
        steps_completed.append("fetch_story")
        
        # Step 2: Generate acceptance criteria
        ac_response = await self.generate_acceptance_criteria(
            GenerateAcceptanceCriteriaRequest(
                issue_id=request.issue_id,
                llm_provider=request.llm_provider,
                user_id=request.user_id
            )
        )
        acceptance_criteria = ac_response.acceptance_criteria
        steps_completed.append("generate_acceptance_criteria")
        
        # Step 3: Generate test scenarios (if enabled)
        test_suite = None
        if request.generate_tests:
            ts_response = await self.generate_test_scenarios(
                GenerateTestScenariosRequest(
                    acceptance_criteria=acceptance_criteria,
                    llm_provider=request.llm_provider,
                    user_id=request.user_id
                )
            )
            test_suite = ts_response.test_suite
            steps_completed.append("generate_test_scenarios")
        
        # Step 4: Publish to Jira (if enabled)
        publish_result = None
        if request.auto_publish:
            publish_result = await self.publish_to_jira(
                JiraPublishRequest(
                    issue_id=request.issue_id,
                    acceptance_criteria=acceptance_criteria,
                    test_suite=test_suite,
                    publish_mode=request.publish_mode
                )
            )
            steps_completed.append("publish_to_jira")
        
        total_time = time.time() - start_time
        logger.info(
            f"Full pipeline completed for {request.issue_id} "
            f"in {total_time:.2f}s"
        )
        
        # Save full pipeline history
        try:
            async with get_db_context() as db:
                history = GenerationHistory(
                    user_id=request.user_id if hasattr(request, 'user_id') else None,
                    jira_issue_key=request.issue_id,
                    jira_issue_summary=story.summary,
                    llm_provider=request.llm_provider.value if request.llm_provider else self.default_llm_provider,
                    acceptance_criteria_json=jsonable_encoder(acceptance_criteria),
                    gherkin_text=acceptance_criteria.to_gherkin_text(),
                    test_scenarios_json=jsonable_encoder(test_suite),
                    processing_time_seconds=total_time,
                    acceptance_criteria_count=len(acceptance_criteria.scenarios),
                    test_scenarios_count=len(test_suite.scenarios) if test_suite else 0,
                    published_to_jira=publish_result.success if publish_result else False,
                    jira_publish_mode=request.publish_mode.value if request.publish_mode else None
                )
                db.add(history)
            
            await audit_service.log(
                action="generate_full",
                user_id=request.user_id if hasattr(request, 'user_id') else None,
                resource_type="jira_issue",
                resource_id=request.issue_id,
                details={
                    "ac_count": len(acceptance_criteria.scenarios),
                    "test_count": len(test_suite.scenarios) if test_suite else 0,
                    "published": publish_result.success if publish_result else False
                }
            )
        except Exception as e:
            logger.warning(f"Failed to save pipeline history: {e}")
        
        return FullPipelineResponse(
            success=True,
            story=story,
            acceptance_criteria=acceptance_criteria,
            gherkin_text=acceptance_criteria.to_gherkin_text(),
            test_suite=test_suite,
            jira_publish_result=publish_result,
            total_processing_time_seconds=total_time,
            steps_completed=steps_completed
        )




# Service factory
def get_qa_generator_service(
    jira_client: Optional[JiraClient] = None
) -> QAGeneratorService:
    """Get a configured QA Generator service"""
    return QAGeneratorService(jira_client=jira_client)
