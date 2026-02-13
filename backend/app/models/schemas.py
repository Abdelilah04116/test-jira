"""
Pydantic Schemas for API Request/Response
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field, EmailStr


# =============================================================================
# Enums
# =============================================================================

class LLMProvider(str, Enum):
    """Supported LLM providers"""
    GEMINI = "gemini"
    CLAUDE = "claude"
    OPENAI = "openai"


class UserRole(str, Enum):
    """User roles for authorization"""
    ADMIN = "admin"
    QA = "qa"
    PO = "po"  # Product Owner
    DEVELOPER = "developer"


class TestScenarioType(str, Enum):
    """Types of test scenarios"""
    POSITIVE = "positive"
    NEGATIVE = "negative"
    EDGE_CASE = "edge_case"
    SECURITY = "security"
    PERFORMANCE = "performance"
    DATA_DRIVEN = "data-driven"


class JiraPublishMode(str, Enum):
    """How to publish to Jira"""
    SUBTASK = "subtask"
    COMMENT = "comment"
    CUSTOM_FIELD = "custom_field"
    DESCRIPTION = "description"
    ENVIRONMENT = "environment"
    XRAY = "xray"
    ZEPHYR = "zephyr"


# =============================================================================
# Authentication Schemas
# =============================================================================

class Token(BaseModel):
    """JWT Token response"""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class TokenRefresh(BaseModel):
    """Token refresh request"""
    refresh_token: str


class UserLogin(BaseModel):
    """User login request"""
    email: EmailStr
    password: str


class UserCreate(BaseModel):
    """User creation request"""
    email: str = Field(..., description="User email")
    password: str = Field(..., min_length=4, max_length=128)
    name: str = Field(..., min_length=2, max_length=100)
    role: str = "qa"


class UserResponse(BaseModel):
    """User response (without sensitive data)"""
    id: str
    email: str
    name: str
    role: str
    is_active: bool
    created_at: datetime
    
    model_config = {"from_attributes": True}


# =============================================================================
# Jira Schemas
# =============================================================================

class JiraCredentials(BaseModel):
    """Jira connection credentials"""
    url: str = Field(..., description="Jira instance URL")
    email: str = Field(..., description="Jira user email")
    api_token: str = Field(..., description="Jira API token")


class JiraStoryRequest(BaseModel):
    """Request to fetch a Jira story"""
    issue_id: str = Field(..., min_length=3, max_length=30, pattern="^[A-Z0-9]+-[0-9]+$", description="Jira issue ID (e.g., PROJ-123)")
    

class JiraStory(BaseModel):
    """Jira User Story data"""
    id: str = Field(..., description="Issue ID")
    key: str = Field(..., description="Issue key (e.g., PROJ-123)")
    summary: str = Field(..., description="Issue title/summary")
    description: Optional[str] = Field(None, description="Issue description")
    issue_type: str = Field(..., description="Issue type")
    status: str = Field(..., description="Current status")
    project_key: str = Field(..., description="Project key")
    assignee: Optional[str] = Field(None, description="Assignee name")
    reporter: Optional[str] = Field(None, description="Reporter name")
    labels: List[str] = Field(default_factory=list)
    components: List[str] = Field(default_factory=list)
    priority: Optional[str] = Field(None, description="Priority level")
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    custom_fields: Dict[str, Any] = Field(default_factory=dict)


# =============================================================================
# Acceptance Criteria Schemas
# =============================================================================

class GherkinScenario(BaseModel):
    """Single Gherkin scenario"""
    id: str = Field(..., description="Unique scenario ID")
    title: str = Field(..., description="Scenario title")
    given: List[str] = Field(..., description="Given steps (preconditions)")
    when: List[str] = Field(..., description="When steps (actions)")
    then: List[str] = Field(..., description="Then steps (expected results)")
    tags: List[str] = Field(default_factory=list)
    examples: Optional[Dict[str, List[Any]]] = Field(
        None, 
        description="Scenario Outline examples"
    )
    
    def to_gherkin_text(self) -> str:
        """Convert to Gherkin text format"""
        lines = []
        
        if self.tags:
            lines.append(" ".join(f"@{tag}" for tag in self.tags))
        
        lines.append(f"Scenario: {self.title}")
        
        for step in self.given:
            lines.append(f"  Given {step}")
        
        for step in self.when:
            lines.append(f"  When {step}")
        
        for step in self.then:
            lines.append(f"  Then {step}")
        
        if self.examples:
            lines.append("")
            lines.append("  Examples:")
            headers = list(self.examples.keys())
            lines.append("    | " + " | ".join(headers) + " |")
            
            num_rows = len(self.examples[headers[0]]) if headers else 0
            for i in range(num_rows):
                row = [str(self.examples[h][i]) for h in headers]
                lines.append("    | " + " | ".join(row) + " |")
        
        return "\n".join(lines)


class AcceptanceCriteria(BaseModel):
    """Full acceptance criteria for a story"""
    story_key: str = Field(..., description="Related Jira story key")
    feature_name: str = Field(..., description="Feature name for Gherkin")
    background: Optional[Dict[str, List[str]]] = Field(
        None,
        description="Background steps (given steps shared by all scenarios)"
    )
    scenarios: List[GherkinScenario] = Field(
        ...,
        description="List of Gherkin scenarios"
    )
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    llm_provider: str = Field(..., description="LLM used for generation")
    
    def to_gherkin_text(self) -> str:
        """Convert to full Gherkin feature file format"""
        lines = [f"Feature: {self.feature_name}"]
        lines.append("")
        
        if self.background:
            lines.append("  Background:")
            for step in self.background.get("given", []):
                lines.append(f"    Given {step}")
            lines.append("")
        
        for scenario in self.scenarios:
            lines.append("  " + scenario.to_gherkin_text().replace("\n", "\n  "))
            lines.append("")
        
        return "\n".join(lines)


class GenerateAcceptanceCriteriaRequest(BaseModel):
    """Request to generate acceptance criteria"""
    user_id: Optional[Any] = None # Added for backend tracking
    issue_id: Optional[str] = Field(
        None, 
        description="Jira issue ID to fetch story from"
    )
    story_text: Optional[str] = Field(
        None,
        description="Raw user story text (if not using Jira)"
    )
    story_title: Optional[str] = Field(
        None,
        description="Story title (if providing raw text)"
    )
    context: Optional[str] = Field(
        None,
        description="Additional business context"
    )
    llm_provider: Optional[LLMProvider] = Field(
        None,
        description="Override default LLM provider"
    )
    max_scenarios: int = Field(
        default=5,
        ge=1,
        le=20,
        description="Maximum number of scenarios to generate"
    )


class GenerateAcceptanceCriteriaResponse(BaseModel):
    """Response with generated acceptance criteria"""
    success: bool
    story_key: str
    acceptance_criteria: AcceptanceCriteria
    gherkin_text: str
    published_to_jira: bool = False
    jira_update_url: Optional[str] = None
    processing_time_seconds: float


# =============================================================================
# Test Scenario Schemas
# =============================================================================

class TestStep(BaseModel):
    """Single test step"""
    order: int = Field(..., description="Step order number")
    action: str = Field(..., description="Action to perform")
    expected_result: str = Field(..., description="Expected result")
    test_data: Optional[str] = Field(None, description="Test data to use")


class TestScenario(BaseModel):
    """Complete test scenario"""
    id: str = Field(..., description="Unique test ID")
    title: str = Field(..., description="Test scenario title")
    description: str = Field(..., description="Test description")
    type: TestScenarioType = Field(..., description="Type of test")
    priority: str = Field(default="Medium", description="Test priority")
    preconditions: List[str] = Field(default_factory=list)
    steps: List[TestStep] = Field(..., description="Test steps")
    acceptance_criteria_ref: str = Field(
        ...,
        description="Reference to linked acceptance criteria scenario"
    )
    tags: List[str] = Field(default_factory=list)
    estimated_duration_minutes: int = Field(default=5)
    playwright_code: Optional[str] = Field(None, description="Generated Playwright test code")


class TestSuite(BaseModel):
    """Collection of test scenarios for a story"""
    story_key: str = Field(..., description="Related Jira story key")
    suite_name: str = Field(..., description="Test suite name")
    scenarios: List[TestScenario] = Field(..., description="Test scenarios")
    total_scenarios: int = Field(default=0)
    positive_count: int = Field(default=0)
    negative_count: int = Field(default=0)
    edge_case_count: int = Field(default=0)
    generated_at: datetime = Field(default_factory=datetime.utcnow)
    llm_provider: str = Field(..., description="LLM used for generation")
    
    def model_post_init(self, __context):
        """Calculate counts after initialization"""
        self.total_scenarios = len(self.scenarios)
        self.positive_count = sum(
            1 for s in self.scenarios if s.type == TestScenarioType.POSITIVE
        )
        self.negative_count = sum(
            1 for s in self.scenarios if s.type == TestScenarioType.NEGATIVE
        )
        self.edge_case_count = sum(
            1 for s in self.scenarios if s.type == TestScenarioType.EDGE_CASE
        )


class GenerateTestScenariosRequest(BaseModel):
    """Request to generate test scenarios"""
    issue_id: Optional[str] = Field(
        None,
        description="Jira issue ID"
    )
    acceptance_criteria: Optional[AcceptanceCriteria] = Field(
        None,
        description="Previously generated acceptance criteria"
    )
    llm_provider: Optional[LLMProvider] = Field(
        None,
        description="Override default LLM provider"
    )
    include_negative: bool = Field(
        default=True,
        description="Include negative test cases"
    )
    include_edge_cases: bool = Field(
        default=True,
        description="Include edge case tests"
    )
    max_scenarios_per_criteria: int = Field(
        default=3,
        ge=1,
        le=10
    )


class GenerateTestScenariosResponse(BaseModel):
    """Response with generated test scenarios"""
    success: bool
    story_key: str
    test_suite: TestSuite
    published_to_jira: bool = False
    jira_subtasks_created: List[str] = Field(default_factory=list)
    processing_time_seconds: float


# =============================================================================
# Jira Publish Schemas
# =============================================================================

class JiraPublishRequest(BaseModel):
    """Request to publish to Jira"""
    issue_id: str = Field(..., description="Target Jira issue ID")
    acceptance_criteria: Optional[AcceptanceCriteria] = None
    test_suite: Optional[TestSuite] = None
    publish_mode: JiraPublishMode = Field(
        default=JiraPublishMode.SUBTASK,
        description="How to publish test scenarios to Jira"
    )
    ac_publish_mode: JiraPublishMode = Field(
        default=JiraPublishMode.ENVIRONMENT,
        description="How to publish acceptance criteria to Jira (environment, description, comment)"
    )
    custom_field_id: Optional[str] = Field(
        None,
        description="Custom field ID for acceptance criteria"
    )


class JiraPublishResponse(BaseModel):
    """Response from Jira publish operation"""
    success: bool
    issue_key: str
    acceptance_criteria_published: bool = False
    acceptance_criteria_location: Optional[str] = None
    test_scenarios_published: bool = False
    created_subtasks: List[Dict[str, str]] = Field(default_factory=list)
    jira_link: str
    message: str


class JiraConfigRequest(BaseModel):
    """Jira configuration request"""
    url: str = Field(..., description="Jira instance URL")
    email: str = Field(..., description="Jira user email")
    api_token: str = Field(..., description="Jira API token")
    project_key: Optional[str] = Field(None, description="Default project key")

class JiraConfigResponse(BaseModel):
    """Jira configuration response"""
    url: str
    email: str
    project_key: Optional[str]
    is_active: bool
    updated_at: datetime

    class Config:
        from_attributes = True


# =============================================================================
# Full Pipeline Schemas
# =============================================================================

class FullPipelineRequest(BaseModel):
    """Request for complete pipeline execution"""
    user_id: Optional[Any] = None # Added for backend tracking
    issue_id: str = Field(..., min_length=3, max_length=30, pattern="^[A-Z0-9]+-[0-9]+$", description="Jira issue ID")
    llm_provider: Optional[LLMProvider] = None
    auto_publish: bool = Field(
        default=True,
        description="Automatically publish to Jira"
    )
    publish_mode: JiraPublishMode = Field(
        default=JiraPublishMode.SUBTASK
    )
    generate_tests: bool = Field(
        default=True,
        description="Also generate test scenarios"
    )


class FullPipelineResponse(BaseModel):
    """Response from full pipeline execution"""
    success: bool
    story: JiraStory
    acceptance_criteria: AcceptanceCriteria
    gherkin_text: str
    test_suite: Optional[TestSuite] = None
    jira_publish_result: Optional[JiraPublishResponse] = None
    total_processing_time_seconds: float
    steps_completed: List[str]


# =============================================================================
# Error Schemas
# =============================================================================

class ErrorResponse(BaseModel):
    """Standard error response"""
    error: str
    detail: Optional[str] = None
    code: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ValidationErrorDetail(BaseModel):
    """Validation error detail"""
    loc: List[str]
    msg: str
    type: str


class ValidationErrorResponse(BaseModel):
    """Validation error response"""
    error: str = "Validation Error"
    details: List[ValidationErrorDetail]
    code: str = "VALIDATION_ERROR"
