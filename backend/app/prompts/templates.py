"""
AI Prompts for QA Generation
Centralized prompt templates for consistent AI output
"""

# =============================================================================
# SYSTEM PROMPTS
# =============================================================================

SYSTEM_PROMPT_QA_EXPERT = """You are an expert Quality Assurance professional with deep expertise in:
- Behavior-Driven Development (BDD)
- Gherkin syntax and best practices
- Test case design techniques
- Requirements analysis
- Software testing methodologies

Your role is to analyze user stories and generate comprehensive, testable acceptance criteria and test scenarios.

Guidelines:
1. Be precise and unambiguous
2. Focus on testability
3. Cover all functional requirements
4. Include edge cases when relevant
5. Use standard BDD terminology
6. Ensure traceability between requirements and tests
"""

SYSTEM_PROMPT_GHERKIN_GENERATOR = """You are a Gherkin expert. You write clear, concise, and testable acceptance criteria using the Gherkin syntax.

Rules for writing Gherkin:
1. Use "Given" for preconditions and initial context
2. Use "When" for actions or events
3. Use "Then" for expected outcomes and assertions
4. Use "And" and "But" for additional steps in the same category
5. Keep scenarios focused on a single behavior
6. Use concrete examples instead of abstract descriptions
7. Avoid conjunctions (and, or) in step definitions
8. Use Scenario Outline with Examples for data-driven scenarios
9. Include relevant tags for categorization
"""

SYSTEM_PROMPT_TEST_GENERATOR = """You are a senior test engineer specializing in functional testing.

Your expertise includes:
- Designing comprehensive test cases
- Identifying edge cases and boundary conditions
- Creating positive and negative test scenarios
- Ensuring test coverage
- Writing clear, reproducible test steps

Focus on practical, executable tests that verify the system behavior matches requirements.
"""

# =============================================================================
# ACCEPTANCE CRITERIA PROMPTS
# =============================================================================

PROMPT_GENERATE_ACCEPTANCE_CRITERIA = """Analyze the following User Story and generate comprehensive acceptance criteria in Gherkin format.

## User Story Information

**Title:** {story_title}

**Description:**
{story_description}

**Additional Context:**
{context}

## Instructions

1. Identify the key behaviors and requirements from the user story
2. Create Gherkin scenarios that cover:
   - Main success path (happy path)
   - Alternative flows
   - Error handling scenarios
   - Edge cases specific to the functionality

3. For each scenario:
   - Write a clear, descriptive title
   - Define preconditions in "Given" steps
   - Describe the action in "When" steps
   - Specify expected outcomes in "Then" steps
   - Add relevant tags (@functional, @smoke, @regression, etc.)

4. Use Scenario Outline for data-driven scenarios when applicable

## Output Format

Respond with a JSON object containing the acceptance criteria:

```json
{{
  "feature_name": "Feature name derived from the story",
  "background": {{
    "given": ["shared precondition step 1", "shared precondition step 2"]
  }},
  "scenarios": [
    {{
      "id": "AC-001",
      "title": "Scenario title describing the behavior",
      "given": ["precondition 1", "precondition 2"],
      "when": ["action 1"],
      "then": ["expected result 1", "expected result 2"],
      "tags": ["functional", "positive"],
      "examples": null
    }},
    {{
      "id": "AC-002",
      "title": "Scenario Outline title",
      "given": ["user has <role>"],
      "when": ["user performs <action>"],
      "then": ["result is <expected_result>"],
      "tags": ["data-driven"],
      "examples": {{
        "role": ["admin", "user", "guest"],
        "action": ["view", "edit", "delete"],
        "expected_result": ["success", "partial", "denied"]
      }}
    }}
  ]
}}
```

Generate maximum {max_scenarios} scenarios that provide comprehensive coverage.
Focus on quality over quantity.
"""

PROMPT_REFINE_ACCEPTANCE_CRITERIA = """Review and refine the following acceptance criteria for the user story.

## User Story
**Title:** {story_title}
**Description:** {story_description}

## Current Acceptance Criteria
{current_criteria}

## Instructions

1. Check for completeness - are all requirements covered?
2. Check for clarity - are all steps unambiguous?
3. Check for testability - can each step be verified?
4. Identify any missing scenarios
5. Improve wording where needed

Return the refined criteria in the same JSON format.
"""

# =============================================================================
# TEST SCENARIO PROMPTS
# =============================================================================

PROMPT_GENERATE_TEST_SCENARIOS = """Generate test scenarios based on the following acceptance criteria.

## Story: {story_key} - {story_title}

## Acceptance Criteria (Gherkin)

{acceptance_criteria_gherkin}

## Instructions

Create concise test cases. For each acceptance criterion, generate up to {max_scenarios_per_criteria} test scenarios total.

Keep descriptions short (1-2 sentences max).
Keep step actions and expected results brief.

## Output Format

Return a JSON object with the following structure:
{{
  "suite_name": "Test Suite for {story_key}",
  "scenarios": [
    {{
      "id": "TS-001",
      "title": "Short test title",
      "description": "Brief description",
      "type": "positive",
      "priority": "High",
      "preconditions": ["Precondition 1"],
      "steps": [
        {{
          "order": 1,
          "action": "Action to perform",
          "expected_result": "Expected outcome",
          "test_data": null
        }}
      ],
      "acceptance_criteria_ref": "AC-001",
      "tags": ["smoke"],
      "estimated_duration_minutes": 5
    }}
  ]
}}

Generate a mix of positive ({include_positive}), negative ({include_negative}), and edge case ({include_edge_cases}) tests.
Keep the total number of scenarios between 3 and 6 for manageability.
"""

PROMPT_GENERATE_TEST_DATA = """Generate appropriate test data for the following test scenario.

## Test Scenario
{test_scenario}

## Context
{context}

## Instructions

Create realistic test data that covers:
1. Valid data for positive testing
2. Invalid data for negative testing
3. Boundary values
4. Edge case data

Return as JSON:
```json
{{
  "valid_data": {{
    "field1": "value1",
    "field2": "value2"
  }},
  "invalid_data": [
    {{
      "field1": "invalid_value",
      "expected_error": "Error message"
    }}
  ],
  "boundary_data": [
    {{
      "field1": "min_value",
      "description": "Minimum allowed value"
    }}
  ]
}}
```
"""

PROMPT_GENERATE_PLAYWRIGHT_CODE = """Generate a Playwright (TypeScript) test script for the following test scenario.

## Test Scenario
Title: {title}
Description: {description}
Type: {type}

Steps:
{steps}

## Instructions
1. Use Playwright with TypeScript.
2. Use 'test' and 'expect' from '@playwright/test'.
3. Write a complete, runnable test file content (imports + test block).
4. Use robust locators (getByRole, getByPlaceholder, etc.) wherever possible, avoiding Fragile XPaths.
5. Add comments explaining each step.
6. The test should be resilient and follow best practices.

## Output Format
Return a JSON object:
{{
  "code": "full typescript code here"
}}
"""

# =============================================================================
# SCHEMA DEFINITIONS
# =============================================================================

ACCEPTANCE_CRITERIA_SCHEMA = {
    "type": "object",
    "required": ["feature_name", "scenarios"],
    "properties": {
        "feature_name": {"type": "string"},
        "background": {
            "type": "object",
            "properties": {
                "given": {"type": "array", "items": {"type": "string"}}
            }
        },
        "scenarios": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "title", "given", "when", "then"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "given": {"type": "array", "items": {"type": "string"}},
                    "when": {"type": "array", "items": {"type": "string"}},
                    "then": {"type": "array", "items": {"type": "string"}},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "examples": {"type": ["object", "null"]}
                }
            }
        }
    }
}

TEST_SCENARIOS_SCHEMA = {
    "type": "object",
    "required": ["suite_name", "scenarios"],
    "properties": {
        "suite_name": {"type": "string"},
        "scenarios": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["id", "title", "description", "type", "steps", "acceptance_criteria_ref"],
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "description": {"type": "string"},
                    "type": {"type": "string", "enum": ["positive", "negative", "edge_case"]},
                    "priority": {"type": "string"},
                    "preconditions": {"type": "array", "items": {"type": "string"}},
                    "steps": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "required": ["order", "action", "expected_result"],
                            "properties": {
                                "order": {"type": "integer"},
                                "action": {"type": "string"},
                                "expected_result": {"type": "string"},
                                "test_data": {"type": ["string", "null"]}
                            }
                        }
                    },
                    "acceptance_criteria_ref": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "estimated_duration_minutes": {"type": "integer"}
                }
            }
        }
    }
}
