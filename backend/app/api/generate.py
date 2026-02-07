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
