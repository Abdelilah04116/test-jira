"""
Pipeline Orchestrator Agent
Central coordinator of the multi-agent QA pipeline.

This is the "brain" of the agentic system. It coordinates:
  1. Story Fetching
  2. Acceptance Criteria Generation (GherkinGenerator Agent)
  3. Test Scenario Generation (TestGenerator Agent)  
  4. Playwright Code Generation (AutomationEngineer Agent)
  5. Code Review (CodeReviewer Agent)
  6. File Writing & Git Push (GitOps Agent)
  7. Jira Publishing

Architecture:
┌──────────────────────────────────────────────────────────────────┐
│                    ORCHESTRATOR AGENT                            │
│                                                                  │
│  ┌─────────┐   ┌──────────┐   ┌───────────────┐                │
│  │  Fetch   │──▶│ Generate │──▶│ Generate Test │                │
│  │  Story   │   │    AC    │   │  Scenarios    │                │
│  └─────────┘   └──────────┘   └───────┬───────┘                │
│                                        │                         │
│                                        ▼                         │
│                               ┌───────────────┐                 │
│                               │ Automation    │                 │
│                               │ Engineer Agent│                 │
│                               └───────┬───────┘                 │
│                                        │                         │
│                                        ▼                         │
│                               ┌───────────────┐                 │
│                               │ CodeReviewer  │                 │
│                               │ Agent         │                 │
│                               └───────┬───────┘                 │
│                                        │                         │
│                              ┌─────────┴──────────┐             │
│                              ▼                     ▼             │
│                     ┌──────────────┐      ┌──────────────┐      │
│                     │ GitOps Agent │      │ Jira Publish │      │
│                     │ (Files+Push) │      │ (Subtasks)   │      │
│                     └──────────────┘      └──────────────┘      │
└──────────────────────────────────────────────────────────────────┘
"""

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger
from fastapi.encoders import jsonable_encoder

from app.core.config import settings
from app.core.database import get_db_context
from app.llm.factory import get_llm_client
from app.jira.client import JiraClient
from app.azure_devops.client import AzureDevOpsClient
from app.agents.automation_engineer import AutomationEngineerAgent
from app.agents.code_reviewer import CodeReviewerAgent
from app.agents.gitops import GitOpsAgent
from app.models.database import GenerationHistory
from app.models.schemas import (
    FullPipelineRequest,
    FullPipelineResponse,
    GenerateAcceptanceCriteriaRequest,
    GenerateTestScenariosRequest,
    JiraPublishRequest,
    JiraPublishMode,
)
from app.services.generator import QAGeneratorService


class PipelineStep:
    """Represents a single step in the orchestrated pipeline."""
    
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description
        self.status = "pending"  # pending, running, completed, failed, skipped
        self.start_time = None
        self.end_time = None
        self.result = None
        self.error = None
    
    def start(self):
        self.status = "running"
        self.start_time = time.time()
        logger.info(f"🔄 [{self.name}] {self.description}...")
    
    def complete(self, result: Any = None):
        self.status = "completed"
        self.end_time = time.time()
        self.result = result
        duration = self.end_time - self.start_time
        logger.info(f"✅ [{self.name}] Completed in {duration:.2f}s")
    
    def fail(self, error: str):
        self.status = "failed"
        self.end_time = time.time()
        self.error = error
        logger.error(f"❌ [{self.name}] Failed: {error}")
    
    def skip(self, reason: str):
        self.status = "skipped"
        self.error = reason
        logger.info(f"⏭️ [{self.name}] Skipped: {reason}")
    
    @property
    def duration(self) -> float:
        if self.start_time and self.end_time:
            return self.end_time - self.start_time
        return 0.0
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "duration_seconds": round(self.duration, 2),
            "error": self.error
        }


class OrchestratorAgent:
    """
    Master orchestrator that coordinates the full multi-agent pipeline.
    Supports both Jira and Azure DevOps.
    """
    
    def __init__(
        self,
        jira_client: Optional[JiraClient] = None,
        az_client: Optional[AzureDevOpsClient] = None,
        llm_provider: Optional[str] = None,
    ):
        self.jira_client = jira_client or JiraClient()
        self.az_client = az_client or AzureDevOpsClient()
        self.llm_provider = llm_provider or settings.llm_provider
        self.qa_service = QAGeneratorService(
            jira_client=self.jira_client,
            llm_provider=self.llm_provider
        )
        self.steps: List[PipelineStep] = []
    
    def _get_llm(self):
        return get_llm_client(provider=self.llm_provider)
    
    async def run_full_agentic_pipeline(
        self,
        issue_id: str,
        user_id: str = "system",
        auto_publish: bool = True,
        auto_push_git: bool = True,
        publish_mode: JiraPublishMode = JiraPublishMode.SUBTASK,
    ) -> Dict[str, Any]:
        """
        Execute the full multi-agent pipeline.
        
        This is the main entry point for the automated agentic workflow.
        
        Args:
            issue_id: Jira issue key (e.g., "PROJ-123")
            user_id: User or system identifier
            auto_publish: Whether to publish results to Jira
            auto_push_git: Whether to push test files to Git
            publish_mode: How to publish to Jira
            
        Returns:
            Complete pipeline result with all artifacts and telemetry
        """
        pipeline_start = time.time()
        self.steps = []
        
        logger.info("=" * 70)
        logger.info(f"🚀 AGENTIC PIPELINE STARTED for {issue_id}")
        logger.info(f"   User: {user_id}")
        logger.info(f"   LLM: {self.llm_provider}")
        logger.info(f"   Auto-publish: {auto_publish}")
        logger.info(f"   Auto-push Git: {auto_push_git}")
        logger.info("=" * 70)
        
        pipeline_result = {
            "success": False,
            "issue_id": issue_id,
            "user_id": user_id,
            "pipeline_type": "agentic_multi_agent",
            "llm_provider": self.llm_provider,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "story": None,
            "acceptance_criteria": None,
            "gherkin_text": None,
            "test_suite": None,
            "code_reviews": [],
            "git_result": None,
            "jira_publish_result": None,
            "steps": [],
            "total_processing_time_seconds": 0,
            "agents_used": [
                "Orchestrator",
                "GherkinGenerator",
                "TestGenerator",
                "AutomationEngineer",
                "CodeReviewer",
                "GitOps"
            ]
        }
        
        try:
            # ═══════════════════════════════════════════════════════════════════
            # STEP 1: Fetch Story from Jira or Azure DevOps
            # ═══════════════════════════════════════════════════════════════════
            is_ado = issue_id.isdigit() or issue_id.startswith("ADO-")
            clean_id = issue_id.replace("ADO-", "") if is_ado else issue_id
            
            platform_name = "Azure DevOps" if is_ado else "Jira"
            step1 = PipelineStep("fetch_story", f"Fetching user story from {platform_name}")
            self.steps.append(step1)
            step1.start()
            
            if is_ado:
                story = await self.az_client.get_work_item(clean_id)
            else:
                story = await self.qa_service.fetch_story(issue_id)
                
            pipeline_result["story"] = jsonable_encoder(story)
            step1.complete({"key": story.key, "summary": story.summary, "platform": platform_name})
            
            # ═══════════════════════════════════════════════════════════════════
            # STEP 2: Generate Acceptance Criteria
            # ═══════════════════════════════════════════════════════════════════
            step2 = PipelineStep("generate_ac", "Generating acceptance criteria (Gherkin)")
            self.steps.append(step2)
            step2.start()
            
            ac_response = await self.qa_service.generate_acceptance_criteria(
                GenerateAcceptanceCriteriaRequest(
                    issue_id=issue_id,
                    user_id=user_id
                )
            )
            acceptance_criteria = ac_response.acceptance_criteria
            pipeline_result["acceptance_criteria"] = jsonable_encoder(acceptance_criteria)
            pipeline_result["gherkin_text"] = ac_response.gherkin_text
            step2.complete({
                "scenarios_count": len(acceptance_criteria.scenarios),
                "feature": acceptance_criteria.feature_name
            })
            
            # ═══════════════════════════════════════════════════════════════════
            # STEP 3: Generate Test Scenarios + Playwright Code
            # ═══════════════════════════════════════════════════════════════════
            step3 = PipelineStep("generate_tests", "Generating test scenarios + Playwright code")
            self.steps.append(step3)
            step3.start()
            
            ts_response = await self.qa_service.generate_test_scenarios(
                GenerateTestScenariosRequest(
                    acceptance_criteria=acceptance_criteria,
                    user_id=user_id
                )
            )
            test_suite = ts_response.test_suite
            pipeline_result["test_suite"] = jsonable_encoder(test_suite)
            step3.complete({
                "total_scenarios": test_suite.total_scenarios,
                "positive": test_suite.positive_count,
                "negative": test_suite.negative_count
            })
            
            # ═══════════════════════════════════════════════════════════════════
            # STEP 4: Code Review (CodeReviewer Agent)
            # ═══════════════════════════════════════════════════════════════════
            step4 = PipelineStep("code_review", "AI Code Review (CodeReviewer Agent)")
            self.steps.append(step4)
            step4.start()
            
            llm = self._get_llm()
            reviewer = CodeReviewerAgent(llm)
            
            review_tasks = []
            for scenario in test_suite.scenarios:
                if scenario.playwright_code and not scenario.playwright_code.startswith("// ⚠️"):
                    review_tasks.append(
                        reviewer.review(scenario, scenario.playwright_code)
                    )
            
            reviews = []
            if review_tasks:
                reviews = await asyncio.gather(*review_tasks, return_exceptions=True)
            
            # Apply reviewed code back to scenarios
            review_idx = 0
            code_reviews_summary = []
            for scenario in test_suite.scenarios:
                if scenario.playwright_code and not scenario.playwright_code.startswith("// ⚠️"):
                    if review_idx < len(reviews) and not isinstance(reviews[review_idx], Exception):
                        review = reviews[review_idx]
                        # Replace code with reviewed version
                        final_code = review.get("final_code", scenario.playwright_code)
                        if final_code:
                            scenario.playwright_code = final_code
                        
                        code_reviews_summary.append({
                            "scenario_id": scenario.id,
                            "title": scenario.title,
                            "approved": review.get("approved", True),
                            "score": review.get("overall_score", 0),
                            "issues": review.get("issues_found", []),
                            "improvements": review.get("improvements_applied", [])
                        })
                    review_idx += 1
            
            pipeline_result["code_reviews"] = code_reviews_summary
            avg_score = (
                sum(r.get("score", 0) for r in code_reviews_summary) / len(code_reviews_summary)
                if code_reviews_summary else 0
            )
            step4.complete({
                "reviews_completed": len(code_reviews_summary),
                "average_score": round(avg_score, 1)
            })
            
            # ═══════════════════════════════════════════════════════════════════
            # STEP 5: Generate Test Files (GitOps Agent)
            # ═══════════════════════════════════════════════════════════════════
            step5 = PipelineStep("gitops_write", "Writing test files (GitOps Agent)")
            self.steps.append(step5)
            step5.start()
            
            gitops = GitOpsAgent()
            
            scenarios_data = []
            for scenario in test_suite.scenarios:
                review_info = next(
                    (r for r in code_reviews_summary if r["scenario_id"] == scenario.id),
                    None
                )
                scenarios_data.append({
                    "id": scenario.id,
                    "title": scenario.title,
                    "playwright_code": scenario.playwright_code,
                    "review_score": review_info.get("score") if review_info else None
                })
            
            write_result = await gitops.write_test_files(
                story_key=issue_id,
                scenarios=scenarios_data
            )
            
            step5.complete({
                "files_created": len(write_result.get("files_created", [])),
                "directory": write_result.get("directory", "")
            })
            
            # ═══════════════════════════════════════════════════════════════════
            # STEP 6: Git Commit & Push (GitOps Agent)
            # ═══════════════════════════════════════════════════════════════════
            if auto_push_git and getattr(settings, 'git_repo_url', None):
                step6 = PipelineStep("gitops_push", "Git commit & push (GitOps Agent)")
                self.steps.append(step6)
                step6.start()
                
                git_result = await gitops.git_commit_and_push(
                    story_key=issue_id,
                    files_created=write_result.get("files_created", [])
                )
                pipeline_result["git_result"] = git_result
                
                if git_result.get("success"):
                    step6.complete({
                        "branch": git_result.get("branch"),
                        "commit": git_result.get("commit_hash", "")[:8]
                    })
                else:
                    step6.fail(git_result.get("error", "Unknown error"))
            else:
                step6 = PipelineStep("gitops_push", "Git push (skipped)")
                self.steps.append(step6)
                step6.skip("No GIT_REPO_URL configured or auto_push_git=False")
                pipeline_result["git_result"] = write_result
            
            # ═══════════════════════════════════════════════════════════════════
            # STEP 7: Publish to Jira or Azure DevOps
            # ═══════════════════════════════════════════════════════════════════
            if auto_publish:
                step7 = PipelineStep("publish_results", f"Publishing to {platform_name}")
                self.steps.append(step7)
                step7.start()
                
                if is_ado:
                    # Format test suite for Azure DevOps description
                    ts_summary = f"<h3>Test Suite Generated</h3><ul>"
                    for ts in test_suite.scenarios:
                        ts_summary += f"<li><b>{ts.id}</b>: {ts.title} ({ts.priority})</li>"
                    ts_summary += "</ul>"
                    
                    publish_success = await self.az_client.publish_to_work_item(
                        work_item_id=clean_id,
                        acceptance_criteria=pipeline_result["gherkin_text"],
                        test_suite_desc=ts_summary
                    )
                    pipeline_result["jira_publish_result"] = {"success": publish_success, "platform": "Azure DevOps"}
                    step7.complete({"published": publish_success})
                else:
                    publish_result = await self.qa_service.publish_to_jira(
                        JiraPublishRequest(
                            issue_id=issue_id,
                            acceptance_criteria=acceptance_criteria,
                            test_suite=test_suite,
                            publish_mode=publish_mode
                        )
                    )
                    pipeline_result["jira_publish_result"] = jsonable_encoder(publish_result)
                    step7.complete({
                        "ac_published": publish_result.acceptance_criteria_published,
                        "subtasks_created": len(publish_result.created_subtasks)
                    })
            
            # ═══════════════════════════════════════════════════════════════════
            # FINALIZE
            # ═══════════════════════════════════════════════════════════════════
            pipeline_result["success"] = True
            
        except Exception as e:
            logger.error(f"❌ PIPELINE FAILED for {issue_id}: {e}")
            # Mark current step as failed if applicable
            for step in reversed(self.steps):
                if step.status == "running":
                    step.fail(str(e))
                    break
        
        finally:
            total_time = time.time() - pipeline_start
            pipeline_result["total_processing_time_seconds"] = round(total_time, 2)
            pipeline_result["completed_at"] = datetime.now(timezone.utc).isoformat()
            pipeline_result["steps"] = [s.to_dict() for s in self.steps]
            
            # Save to database
            await self._save_pipeline_history(pipeline_result)
            
            # Log summary
            logger.info("=" * 70)
            logger.info(f"{'✅' if pipeline_result['success'] else '❌'} PIPELINE {'COMPLETED' if pipeline_result['success'] else 'FAILED'} for {issue_id}")
            logger.info(f"   Total time: {total_time:.2f}s")
            logger.info(f"   Steps:")
            for step in self.steps:
                icon = {"completed": "✅", "failed": "❌", "skipped": "⏭️"}.get(step.status, "❓")
                logger.info(f"     {icon} {step.name}: {step.status} ({step.duration:.2f}s)")
            logger.info("=" * 70)
        
        return pipeline_result
    
    async def _save_pipeline_history(self, result: Dict):
        """Save pipeline execution history to database."""
        try:
            async with get_db_context() as db:
                history = GenerationHistory(
                    user_id=result.get("user_id"),
                    jira_issue_key=result.get("issue_id"),
                    jira_issue_summary=result.get("story", {}).get("summary", "") if result.get("story") else "",
                    llm_provider=result.get("llm_provider", "unknown"),
                    acceptance_criteria_json=result.get("acceptance_criteria"),
                    gherkin_text=result.get("gherkin_text", ""),
                    test_scenarios_json=result.get("test_suite"),
                    processing_time_seconds=result.get("total_processing_time_seconds", 0),
                    acceptance_criteria_count=len(
                        result.get("acceptance_criteria", {}).get("scenarios", [])
                    ) if result.get("acceptance_criteria") else 0,
                    test_scenarios_count=len(
                        result.get("test_suite", {}).get("scenarios", [])
                    ) if result.get("test_suite") else 0,
                    published_to_jira=result.get("jira_publish_result", {}).get("success", False) if result.get("jira_publish_result") else False,
                    jira_publish_mode=JiraPublishMode.SUBTASK.value,
                )
                db.add(history)
        except Exception as e:
            logger.warning(f"Failed to save pipeline history: {e}")
