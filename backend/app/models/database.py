"""
Database Models (SQLAlchemy ORM)
"""

import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum as SQLEnum,
    ForeignKey,
    String,
    Text,
    JSON,
    Integer,
    Float
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.core.database import Base
from app.models.schemas import UserRole, TestScenarioType


def generate_uuid():
    """Generate a new UUID"""
    return str(uuid.uuid4())


class User(Base):
    """User model for authentication and authorization"""
    __tablename__ = "users"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    name = Column(String(100), nullable=False)
    role = Column(SQLEnum(UserRole), default=UserRole.QA, nullable=False)
    is_active = Column(Boolean, default=True)
    
    # API Keys (encrypted)
    jira_api_token_encrypted = Column(Text, nullable=True)
    gemini_api_key_encrypted = Column(Text, nullable=True)
    claude_api_key_encrypted = Column(Text, nullable=True)
    openai_api_key_encrypted = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = Column(DateTime, nullable=True)
    
    # Relationships
    generations = relationship("GenerationHistory", back_populates="user")
    
    def __repr__(self):
        return f"<User {self.email}>"


class GenerationHistory(Base):
    """History of all generations for audit and traceability"""
    __tablename__ = "generation_history"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    
    # Jira Information
    jira_issue_key = Column(String(50), nullable=False, index=True)
    jira_issue_summary = Column(String(500), nullable=True)
    jira_project_key = Column(String(20), nullable=True)
    
    # Generation Details
    llm_provider = Column(String(20), nullable=False)
    llm_model = Column(String(50), nullable=True)
    
    # Generated Content (JSON storage)
    acceptance_criteria_json = Column(JSON, nullable=True)
    gherkin_text = Column(Text, nullable=True)
    test_scenarios_json = Column(JSON, nullable=True)
    
    # Publication Status
    published_to_jira = Column(Boolean, default=False)
    jira_publish_mode = Column(String(20), nullable=True)
    jira_subtasks_created = Column(JSON, nullable=True)  # List of subtask keys
    
    # Metrics
    processing_time_seconds = Column(Float, nullable=True)
    acceptance_criteria_count = Column(Integer, default=0)
    test_scenarios_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    user = relationship("User", back_populates="generations")
    
    def __repr__(self):
        return f"<GenerationHistory {self.jira_issue_key}>"


class JiraConfiguration(Base):
    """Jira configuration per user or team"""
    __tablename__ = "jira_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Connection
    jira_url = Column(String(255), nullable=False)
    jira_email = Column(String(255), nullable=False)
    jira_api_token_encrypted = Column(Text, nullable=False)
    
    # Field Mapping
    acceptance_criteria_field = Column(String(100), default="description")
    test_scenarios_mode = Column(String(20), default="subtask")
    test_case_issue_type = Column(String(50), default="Sub-task")
    
    # Defaults
    default_project_key = Column(String(20), nullable=True)
    
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<JiraConfiguration {self.jira_url}>"


class LLMConfiguration(Base):
    """LLM configuration per user"""
    __tablename__ = "llm_configurations"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    # Provider preference
    default_provider = Column(String(20), default="gemini")
    
    # Model preferences
    gemini_model = Column(String(50), default="gemini-1.5-pro")
    claude_model = Column(String(50), default="claude-3-5-sonnet-20241022")
    openai_model = Column(String(50), default="gpt-4-turbo-preview")
    
    # Parameters
    temperature = Column(Float, default=0.3)
    max_tokens = Column(Integer, default=4096)
    
    # API Keys (encrypted)
    gemini_api_key_encrypted = Column(Text, nullable=True)
    claude_api_key_encrypted = Column(Text, nullable=True)
    openai_api_key_encrypted = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<LLMConfiguration {self.default_provider}>"


class AuditLog(Base):
    """Audit log for compliance and debugging"""
    __tablename__ = "audit_logs"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    
    action = Column(String(100), nullable=False)
    resource_type = Column(String(50), nullable=True)
    resource_id = Column(String(100), nullable=True)
    
    details = Column(JSON, nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(String(500), nullable=True)
    
    status = Column(String(20), default="success")  # success, failure, error
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f"<AuditLog {self.action} @ {self.created_at}>"
