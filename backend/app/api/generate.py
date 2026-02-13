"""
Generation API Endpoints
AI-powered acceptance criteria and test scenario generation
"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from loguru import logger

from app.api.deps import (
    get_current_user,
    get_generator_service,
    check_rate_limit
)
from app.services.generator import QAGeneratorService
from app.models.schemas import (
    GenerateAcceptanceCriteriaRequest,
    GenerateAcceptanceCriteriaResponse,
    GenerateTestScenariosRequest,
    GenerateTestScenariosResponse,
    FullPipelineRequest,
    FullPipelineResponse,
    LLMProvider,
)
from app.llm.factory import LLMFactory


router = APIRouter(prefix="/generate", tags=["Generation"])


@router.post(
    "/acceptance-criteria",
    response_model=GenerateAcceptanceCriteriaResponse
)
async def generate_acceptance_criteria(
    request: GenerateAcceptanceCriteriaRequest,
    service: QAGeneratorService = Depends(get_generator_service),
    current_user = Depends(get_current_user),
    _: None = Depends(check_rate_limit)
):
    """
    Generate acceptance criteria in Gherkin format
    
    - **issue_id**: Jira issue ID to fetch story from (optional)
    - **story_text**: Raw user story text if not using Jira (optional)
    - **story_title**: Story title if providing raw text (optional)
    - **context**: Additional business context (optional)
    - **llm_provider**: Override default LLM provider (optional)
    - **max_scenarios**: Maximum scenarios to generate (1-20, default: 5)
    
    Either `issue_id` or `story_text` must be provided.
    
    Returns Gherkin-formatted acceptance criteria with scenarios.
    """
    if not request.issue_id and not request.story_text:
        raise HTTPException(
            status_code=400,
            detail="Either issue_id or story_text must be provided"
        )
    request.user_id = current_user.sub
    
    try:
        result = await service.generate_acceptance_criteria(request)
        
        logger.info(
            f"User {current_user.email} generated AC for "
            f"{result.story_key} ({len(result.acceptance_criteria.scenarios)} scenarios)"
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/test-scenarios",
    response_model=GenerateTestScenariosResponse
)
async def generate_test_scenarios(
    request: GenerateTestScenariosRequest,
    service: QAGeneratorService = Depends(get_generator_service),
    current_user = Depends(get_current_user),
    _: None = Depends(check_rate_limit)
):
    """
    Generate test scenarios from acceptance criteria
    
    - **issue_id**: Jira issue ID (optional, will generate AC first)
    - **acceptance_criteria**: Previously generated criteria (optional)
    - **llm_provider**: Override default LLM provider (optional)
    - **include_negative**: Include negative test cases (default: true)
    - **include_edge_cases**: Include edge case tests (default: true)
    - **max_scenarios_per_criteria**: Max scenarios per AC (1-10, default: 3)
    
    Either `issue_id` or `acceptance_criteria` must be provided.
    
    Returns test scenarios linked to acceptance criteria.
    """
    if not request.issue_id and not request.acceptance_criteria:
        raise HTTPException(
            status_code=400,
            detail="Either issue_id or acceptance_criteria must be provided"
        )
    
    try:
        result = await service.generate_test_scenarios(request)
        
        logger.info(
            f"User {current_user.email} generated tests for "
            f"{result.story_key} ({result.test_suite.total_scenarios} scenarios)"
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Generation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post(
    "/full-pipeline",
    response_model=FullPipelineResponse
)
async def run_full_pipeline(
    request: FullPipelineRequest,
    service: QAGeneratorService = Depends(get_generator_service),
    current_user = Depends(get_current_user),
    _: None = Depends(check_rate_limit)
):
    """
    Run the complete QA generation pipeline
    
    This endpoint performs the entire workflow:
    1. Fetch user story from Jira
    2. Generate acceptance criteria (Gherkin)
    3. Generate test scenarios
    4. Publish everything to Jira (if auto_publish is true)
    
    - **issue_id**: Jira issue ID (required)
    - **llm_provider**: Override default LLM provider (optional)
    - **auto_publish**: Automatically publish to Jira (default: true)
    - **publish_mode**: How to publish (subtask, comment, etc.)
    - **generate_tests**: Also generate test scenarios (default: true)
    
    Returns complete results including story, criteria, tests, and publish status.
    """
    request.user_id = current_user.sub

    try:
        result = await service.run_full_pipeline(request)
        
        logger.info(
            f"User {current_user.email} ran full pipeline for "
            f"{request.issue_id} ({result.total_processing_time_seconds:.2f}s)"
        )
        
        return result
        
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"Pipeline failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/push-to-git")
async def push_to_git(
    request: dict,
    current_user = Depends(get_current_user),
    _: None = Depends(check_rate_limit)
):
    """
    Push generated Playwright test files to Git repository
    
    - **issue_id**: Jira issue key (required)
    - **test_suite**: Test suite with scenarios containing playwright_code (required)
    
    This endpoint:
    1. Writes test files to the local workspace
    2. Commits and pushes them to the configured Git repository
    
    Returns push result with commit hash and branch info.
    """
    from app.agents.gitops import GitOpsAgent
    
    issue_id = request.get("issue_id")
    test_suite = request.get("test_suite")
    provider = request.get("provider", "github")
    
    if not issue_id:
        raise HTTPException(status_code=400, detail="issue_id is required")
    if not test_suite or not test_suite.get("scenarios"):
        raise HTTPException(status_code=400, detail="test_suite with scenarios is required")
    
    scenarios = test_suite.get("scenarios", [])
    
    # Filter scenarios that have playwright_code
    pushable = [
        {
            "id": s.get("id", "TS-000"),
            "title": s.get("title", "untitled"),
            "playwright_code": s.get("playwright_code", ""),
            "review_score": s.get("review_score"),
        }
        for s in scenarios
        if s.get("playwright_code") and not s.get("playwright_code", "").startswith("// ⚠️")
    ]
    
    if not pushable:
        # If no code in request, try to find local files
        gitops = GitOpsAgent()
        story_dir = gitops.workspace_base / issue_id.lower().replace("-", "_")
        if story_dir.exists():
            for spec_file in story_dir.glob("*.spec.ts"):
                pushable.append({
                    "id": spec_file.name.split("_")[0],
                    "title": spec_file.name.split("_")[1].replace(".spec.ts", ""),
                    "playwright_code": "local_file", # placeholder to signify we have files
                })

    if not pushable:
        raise HTTPException(
            status_code=400,
            detail="No scenarios with valid Playwright code to push"
        )
    
    gitops = GitOpsAgent()
    
    try:
        # Step 1: Write test files (only if we have real code in request)
        files_created = []
        real_code_scenarios = [s for s in pushable if s["playwright_code"] != "local_file"]
        
        if real_code_scenarios:
            write_result = await gitops.write_test_files(
                story_key=issue_id,
                scenarios=real_code_scenarios
            )
            if not write_result["success"]:
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to write test files: {write_result.get('errors', [])}"
                )
            files_created = write_result["files_created"]
        else:
            # Assume files are already there if no code sent
            files_created = [{"filename": f.name} for f in (gitops.workspace_base / issue_id.lower().replace("-", "_")).glob("*.spec.ts")]

        # Step 2: Git commit & push
        push_result = await gitops.git_commit_and_push(
            story_key=issue_id,
            files_created=files_created,
            provider=provider
        )
        
        logger.info(
            f"User {current_user.email} pushed {len(files_created)} test files "
            f"for {issue_id} to {provider}"
        )
        
        if not push_result["success"]:
            raise HTTPException(
                status_code=500,
                detail=push_result.get("error", "Unknown Git push error")
            )
            
        return {
            "success": True,
            "issue_id": issue_id,
            "provider": provider,
            "files_pushed": push_result["files_pushed"],
            "branch": push_result["branch"],
            "commit_hash": push_result.get("commit_hash"),
            "repo_url": push_result.get("repo_url")
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Push to {provider} failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agentic-pipeline")
async def run_agentic_pipeline(
    request: FullPipelineRequest,
    background_tasks: BackgroundTasks,
    current_user = Depends(get_current_user),
    _: None = Depends(check_rate_limit)
):
    """
    Run the full **Multi-Agent Agentic Pipeline** 🤖
    
    This is the advanced version of the pipeline that uses multiple AI agents:
    
    1. **Orchestrator Agent** — Coordinates the entire workflow
    2. **GherkinGenerator Agent** — Generates acceptance criteria
    3. **TestGenerator Agent** — Creates test scenarios
    4. **AutomationEngineer Agent** — Writes Playwright code
    5. **CodeReviewer Agent** — Reviews code quality (AI-powered)
    6. **GitOps Agent** — Creates test files + Git push
    7. **Jira Publisher** — Publishes results to Jira
    
    - **issue_id**: Jira issue ID (required)
    - **auto_publish**: Auto-publish to Jira (default: true)
    - **llm_provider**: Override default LLM provider (optional)
    
    The pipeline runs in the **background** and returns immediately.
    """
    from app.agents.orchestrator import OrchestratorAgent
    from app.core.config import settings
    
    async def _run_pipeline():
        orchestrator = OrchestratorAgent(
            llm_provider=request.llm_provider.value if request.llm_provider else None
        )
        try:
            result = await orchestrator.run_full_agentic_pipeline(
                issue_id=request.issue_id,
                user_id=current_user.sub,
                auto_publish=request.auto_publish,
                auto_push_git=getattr(settings, 'git_auto_push', False),
            )
            return result
        finally:
            await orchestrator.jira_client.close()
    
    background_tasks.add_task(_run_pipeline)
    
    logger.info(
        f"User {current_user.email} started agentic pipeline for {request.issue_id}"
    )
    
    return {
        "status": "accepted",
        "message": f"Agentic pipeline started for {request.issue_id}",
        "issue_id": request.issue_id,
        "pipeline_type": "agentic_multi_agent",
        "agents": [
            "Orchestrator",
            "GherkinGenerator",
            "TestGenerator",
            "AutomationEngineer",
            "CodeReviewer",
            "GitOps"
        ]
    }


@router.post("/agentic-pipeline-sync")
async def run_agentic_pipeline_sync(
    request: FullPipelineRequest,
    current_user = Depends(get_current_user),
    _: None = Depends(check_rate_limit)
):
    """
    Run the full **Multi-Agent Agentic Pipeline** synchronously.
    
    This is used for immediate feedback in the UI to display generated code before pushing.
    """
    from app.agents.orchestrator import OrchestratorAgent
    from app.core.config import settings
    
    orchestrator = OrchestratorAgent(
        llm_provider=request.llm_provider.value if request.llm_provider else None
    )
    try:
        result = await orchestrator.run_full_agentic_pipeline(
            issue_id=request.issue_id,
            user_id=current_user.sub,
            auto_publish=request.auto_publish,
            auto_push_git=False, # We'll push manually from the UI
        )
        return result
    finally:
        await orchestrator.jira_client.close()


@router.get("/providers")
async def get_available_providers(
    current_user = Depends(get_current_user)
):
    """
    Get available LLM providers
    
    Returns list of configured and available LLM providers.
    """
    available = LLMFactory.get_available_providers()
    
    return {
        "available_providers": available,
        "supported_providers": ["gemini", "claude", "openai"],
        "default_provider": LLMFactory._get_default_config("gemini").model
    }


@router.get("/health")
async def check_llm_health():
    """
    Check health of LLM providers
    
    Returns health status for all configured providers.
    """
    try:
        health = await LLMFactory.health_check_all()
        return {"status": "ok", "providers": health}
    except Exception as e:
        return {"status": "error", "error": str(e)}

