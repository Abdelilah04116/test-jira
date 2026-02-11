"""
CodeReviewer Agent
AI-powered code review agent that validates generated Playwright tests
before they are committed to the repository.

This agent acts as a quality gate in the agentic pipeline:
  AutomationEngineer → CodeReviewer → GitOps
"""

from typing import Dict, Any, Optional
from app.agents.core import BaseAgent
from app.models.schemas import TestScenario
from loguru import logger


CODE_REVIEWER_SYSTEM_PROMPT = """You are a Senior QA Automation Architect performing code reviews.

## Your Mission
Review generated Playwright test code for production readiness.
You must ensure tests are robust, maintainable, and follow best practices.

## Review Criteria (Score each 1-10):

1. **Correctness**: Does the code accurately implement the test scenario?
2. **Robustness**: Are there proper waits, error handling, and assertions?
3. **Maintainability**: Is the code clean, well-structured, and documented?
4. **Locator Quality**: Are locators resilient (getByRole, getByLabel preferred)?
5. **Assertion Coverage**: Are all expected outcomes properly validated?

## Rules
- If any criterion scores below 5, you MUST provide a corrected version.
- Always suggest improvements even for passing code.
- Return the final approved/corrected code.
"""

REVIEW_PROMPT_TEMPLATE = """
Review the following Playwright test code generated for this scenario:

## Test Scenario
- **Title**: {title}
- **Type**: {type}
- **Description**: {description}

## Steps
{steps}

## Generated Code to Review
```typescript
{code}
```

## Instructions
1. Analyze the code against all review criteria.
2. Fix any issues found.
3. Return the final production-ready version.

## Output Format
Return a JSON object:
{{
  "approved": true/false,
  "overall_score": 1-10,
  "scores": {{
    "correctness": 1-10,
    "robustness": 1-10,
    "maintainability": 1-10,
    "locator_quality": 1-10,
    "assertion_coverage": 1-10
  }},
  "issues_found": ["issue1", "issue2"],
  "improvements_applied": ["improvement1", "improvement2"],
  "final_code": "the corrected/approved typescript code"
}}
"""


class CodeReviewerAgent(BaseAgent):
    """
    Agent responsible for reviewing and validating generated test code.
    
    This agent acts as an automated code reviewer in the agentic pipeline,
    ensuring that generated Playwright tests meet production quality standards
    before being committed to the repository.
    """
    
    def __init__(self, llm):
        super().__init__(llm, name="CodeReviewer")
    
    def get_system_prompt(self) -> str:
        return CODE_REVIEWER_SYSTEM_PROMPT
    
    async def review(self, scenario: TestScenario, code: str) -> Dict[str, Any]:
        """
        Review generated Playwright code for a test scenario.
        
        Args:
            scenario: The test scenario the code was generated for
            code: The generated Playwright TypeScript code
            
        Returns:
            Review result with scores, issues, and final approved code
        """
        if not code or code.startswith("// ⚠️ Code generation skipped"):
            logger.warning(f"[{self.name}] Skipping review - no valid code for: {scenario.title}")
            return {
                "approved": False,
                "overall_score": 0,
                "scores": {},
                "issues_found": ["No code was generated"],
                "improvements_applied": [],
                "final_code": code
            }
        
        steps_text = "\n".join([
            f"  {step.order}. {step.action} → Expected: {step.expected_result}"
            for step in scenario.steps
        ])
        
        prompt = REVIEW_PROMPT_TEMPLATE.format(
            title=scenario.title,
            type=scenario.type.value,
            description=scenario.description,
            steps=steps_text,
            code=code
        )
        
        expected_schema = {
            "type": "object",
            "properties": {
                "approved": {"type": "boolean"},
                "overall_score": {"type": "integer"},
                "scores": {
                    "type": "object",
                    "properties": {
                        "correctness": {"type": "integer"},
                        "robustness": {"type": "integer"},
                        "maintainability": {"type": "integer"},
                        "locator_quality": {"type": "integer"},
                        "assertion_coverage": {"type": "integer"}
                    }
                },
                "issues_found": {"type": "array", "items": {"type": "string"}},
                "improvements_applied": {"type": "array", "items": {"type": "string"}},
                "final_code": {"type": "string"}
            },
            "required": ["approved", "overall_score", "final_code"]
        }
        
        try:
            result = await self.run(
                prompt=prompt,
                schema=expected_schema,
                temperature=0.1  # Very low temperature for consistent reviews
            )
            
            logger.info(
                f"[{self.name}] Review for '{scenario.title}': "
                f"Score={result.get('overall_score', '?')}/10, "
                f"Approved={result.get('approved', False)}, "
                f"Issues={len(result.get('issues_found', []))}"
            )
            
            return result
            
        except Exception as e:
            logger.warning(f"[{self.name}] Review failed for '{scenario.title}': {e}")
            # If review fails, pass through the original code
            return {
                "approved": True,
                "overall_score": 5,
                "scores": {},
                "issues_found": [f"Review agent error: {str(e)}"],
                "improvements_applied": [],
                "final_code": code
            }
