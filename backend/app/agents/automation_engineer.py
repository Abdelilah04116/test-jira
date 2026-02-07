from typing import Dict, Any
from app.agents.core import BaseAgent
from app.models.schemas import TestScenario

PLAYWRIGHT_SYSTEM_PROMPT = """You are an Expert QA Automation Engineer specialized in Playwright and TypeScript.
Your goal is to write robust, maintainable, and production-grade test automation scripts.

## Core Principles:
1. **Robust Locators**: PRIORITIZE user-facing locators (`getByRole`, `getByLabel`, `getByText`) over CSS or XPath.
   - ❌ BAD: `page.locator('.submit-btn')`
   - ✅ GOOD: `page.getByRole('button', { name: 'Submit' })`

2. **AAA Pattern**: Structure tests with Arrange, Act, Assert comments.

3. **Explicit Expectations**: Use web-first assertions that wait automatically.
   - ✅ GOOD: `await expect(page.getByText('Success')).toBeVisible()`

4. **TypeScript Best Practices**: Use strict typing where possible.

5. **Isolation**: Tests should be independent.
"""

PROMPT_TEMPLATE = """
Generate a standalone Playwright (TypeScript) test file for this specific scenario:

## Scenario Info
- **Title**: {title}
- **Type**: {type}
- **Description**: {description}

## Gherkin Steps
{steps}

## Requirements
- Put the test inside a `test('...', async ({{ page }}) => {{ ... }})` block.
- Assume `page` is already navigating to the base URL if "Given" step implies being on a page.
- Map the Gherkin steps to Playwright actions.
- Add comments linking back to the step being executed.

## Output Format
Return a JSON object with a single field: `code` containing the string of the TypeScript code.
"""

class AutomationEngineerAgent(BaseAgent):
    """Agent responsible for generating automation code"""
    
    def __init__(self, llm):
        super().__init__(llm, name="AutomationEngineer")

    def get_system_prompt(self) -> str:
        return PLAYWRIGHT_SYSTEM_PROMPT

    async def generate_code(self, scenario: TestScenario) -> str:
        """Generates Playwright code for a scenario"""
        
        # Format steps for the prompt
        steps_text = "\n".join([
            f"- {step.action} (Expect: {step.expected_result})" 
            for step in scenario.steps
        ])
        
        prompt = PROMPT_TEMPLATE.format(
            title=scenario.title,
            type=scenario.type.value,
            description=scenario.description,
            steps=steps_text
        )
        
        expected_schema = {
            "type": "object",
            "properties": {
                "code": {"type": "string"}
            },
            "required": ["code"]
        }
        
        try:
            result = await self.run(
                prompt=prompt,
                schema=expected_schema,
                temperature=0.2 # Low temperature for code
            )
            return result.get("code", "// Code generation failed")
            
        except Exception as e:
            from loguru import logger
            logger.warning(f"Automation generation failed for {scenario.title}: {e}")
            return f"""// ⚠️ Code generation skipped due to API error
// Error: {str(e)}
// 
// Please try again later or verify your API quotas.
/*
Scenario: {scenario.title}
{steps_text}
*/"""
