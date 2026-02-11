"""
Application Configuration
Centralized configuration management using Pydantic Settings
"""

from functools import lru_cache
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    model_config = SettingsConfigDict(
        env_file=("../.env", ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # ==========================================================================
    # Application Settings
    # ==========================================================================
    app_name: str = Field(default="Jira QA AI Generator")
    app_env: str = Field(default="development")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")
    
    # ==========================================================================
    # Server Configuration
    # ==========================================================================
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000)
    workers: int = Field(default=4)
    reload: bool = Field(default=False)
    
    # ==========================================================================
    # Database
    # ==========================================================================
    database_url: str = Field(
        default="postgresql://user:password@localhost:5432/jira_qa_ai"
    )
    database_pool_size: int = Field(default=10)
    database_max_overflow: int = Field(default=20)
    
    # ==========================================================================
    # Redis
    # ==========================================================================
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_password: Optional[str] = Field(default=None)
    
    # ==========================================================================
    # Security & JWT
    # ==========================================================================
    jwt_secret_key: str = Field(default="change-me-in-production")
    jwt_algorithm: str = Field(default="HS256")
    jwt_access_token_expire_minutes: int = Field(default=30)
    jwt_refresh_token_expire_days: int = Field(default=7)
    encryption_key: str = Field(default="change-me-32-bytes-key-here====")
    
    # CORS
    cors_origins: str = Field(default="http://localhost:3000")
    
    @property
    def cors_origins_list(self) -> List[str]:
        """Parse CORS origins from comma-separated string"""
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    # ==========================================================================
    # Jira Configuration
    # ==========================================================================
    jira_url: str = Field(default="https://your-instance.atlassian.net")
    jira_email: str = Field(default="")
    jira_api_token: str = Field(default="")
    
    # Field mapping
    jira_acceptance_criteria_field: str = Field(default="description")
    jira_test_scenarios_mode: str = Field(default="subtask")  # subtask, comment, xray
    jira_test_case_issue_type: str = Field(default="Sub-task")
    jira_project_key: str = Field(default="PROJ")
    
    # ==========================================================================
    # LLM Configuration
    # ==========================================================================
    llm_provider: str = Field(default="gemini")  # gemini, claude, openai
    
    # Models
    llm_gemini_model: str = Field(default="gemini-3-flash-preview")
    llm_claude_model: str = Field(default="claude-3-5-sonnet-20241022")
    llm_openai_model: str = Field(default="gpt-4-turbo-preview")
    
    # API Keys
    gemini_api_key: Optional[str] = Field(default=None)
    claude_api_key: Optional[str] = Field(default=None)
    openai_api_key: Optional[str] = Field(default=None)
    
    # Parameters
    llm_temperature: float = Field(default=0.3)
    llm_max_tokens: int = Field(default=4096)
    llm_timeout_seconds: int = Field(default=60)
    
    @field_validator("llm_provider")
    @classmethod
    def validate_llm_provider(cls, v: str) -> str:
        """Validate LLM provider"""
        allowed = ["gemini", "claude", "openai"]
        if v.lower() not in allowed:
            raise ValueError(f"LLM provider must be one of: {allowed}")
        return v.lower()
    
    # ==========================================================================
    # Rate Limiting
    # ==========================================================================
    rate_limit_requests: int = Field(default=100)
    rate_limit_period: int = Field(default=60)
    
    # ==========================================================================
    # Monitoring
    # ==========================================================================
    sentry_dsn: Optional[str] = Field(default=None)
    prometheus_enabled: bool = Field(default=True)
    prometheus_port: int = Field(default=9090)
    
    # ==========================================================================
    # External Integrations
    # ==========================================================================
    xray_enabled: bool = Field(default=False)
    xray_client_id: Optional[str] = Field(default=None)
    xray_client_secret: Optional[str] = Field(default=None)
    
    zephyr_enabled: bool = Field(default=False)
    zephyr_api_token: Optional[str] = Field(default=None)
    
    slack_enabled: bool = Field(default=False)
    slack_webhook_url: Optional[str] = Field(default=None)
    
    # ==========================================================================
    # Git Repository (for GitOps Agent)
    # ==========================================================================
    git_repo_url: Optional[str] = Field(
        default=None,
        description="Git repository URL for pushing generated tests"
    )
    git_token: Optional[str] = Field(
        default=None,
        description="Git access token (PAT) for authentication"
    )
    git_tests_workspace: str = Field(
        default="generated_tests",
        description="Local workspace directory for generated test files"
    )
    git_tests_path: str = Field(
        default="tests/e2e/generated",
        description="Path within the repo where test files will be placed"
    )
    git_auto_push: bool = Field(
        default=False,
        description="Automatically push generated tests to Git"
    )
    
    # ==========================================================================
    # Azure DevOps Configuration
    # ==========================================================================
    azure_devops_url: str = Field(default="https://dev.azure.com")
    azure_devops_org: Optional[str] = Field(default=None)
    azure_devops_project: Optional[str] = Field(default=None)
    azure_devops_pat: Optional[str] = Field(default=None)
    
    # Azure DevOps Field Mapping
    azure_devops_ac_field: str = Field(default="Microsoft.VSTS.Common.AcceptanceCriteria")
    azure_devops_desc_field: str = Field(default="System.Description")
    
    # ==========================================================================
    # Feature Flags
    # ==========================================================================
    feature_auto_publish: bool = Field(default=True)
    feature_test_generation: bool = Field(default=True)
    feature_traceability: bool = Field(default=True)
    
    # ==========================================================================
    # Helper Properties
    # ==========================================================================
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.app_env.lower() == "production"
    
    @property
    def current_llm_model(self) -> str:
        """Get the current LLM model based on provider"""
        models = {
            "gemini": self.llm_gemini_model,
            "claude": self.llm_claude_model,
            "openai": self.llm_openai_model
        }
        return models.get(self.llm_provider, self.llm_gemini_model)
    
    @property
    def current_llm_api_key(self) -> Optional[str]:
        """Get the current LLM API key based on provider"""
        keys = {
            "gemini": self.gemini_api_key,
            "claude": self.claude_api_key,
            "openai": self.openai_api_key
        }
        return keys.get(self.llm_provider)


@lru_cache()
def get_settings() -> Settings:
    """
    Create cached settings instance.
    Using lru_cache ensures settings are loaded only once.
    """
    return Settings()


# Export settings instance for convenience
settings = get_settings()
