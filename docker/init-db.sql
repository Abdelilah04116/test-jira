-- =============================================================================
-- Jira QA AI Generator - Database Initialization
-- =============================================================================

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Create enum types
DO $$ BEGIN
    CREATE TYPE user_role AS ENUM ('admin', 'qa', 'po', 'developer');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TYPE test_scenario_type AS ENUM ('positive', 'negative', 'edge_case', 'security', 'performance');
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    role user_role DEFAULT 'qa',
    is_active BOOLEAN DEFAULT true,
    jira_api_token_encrypted TEXT,
    gemini_api_key_encrypted TEXT,
    claude_api_key_encrypted TEXT,
    openai_api_key_encrypted TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- Generation history table
CREATE TABLE IF NOT EXISTS generation_history (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    jira_issue_key VARCHAR(50) NOT NULL,
    jira_issue_summary VARCHAR(500),
    jira_project_key VARCHAR(20),
    llm_provider VARCHAR(20) NOT NULL,
    llm_model VARCHAR(50),
    acceptance_criteria_json JSONB,
    gherkin_text TEXT,
    test_scenarios_json JSONB,
    published_to_jira BOOLEAN DEFAULT false,
    jira_publish_mode VARCHAR(20),
    jira_subtasks_created JSONB,
    processing_time_seconds FLOAT,
    acceptance_criteria_count INTEGER DEFAULT 0,
    test_scenarios_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Jira configurations table
CREATE TABLE IF NOT EXISTS jira_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    jira_url VARCHAR(255) NOT NULL,
    jira_email VARCHAR(255) NOT NULL,
    jira_api_token_encrypted TEXT NOT NULL,
    acceptance_criteria_field VARCHAR(100) DEFAULT 'description',
    test_scenarios_mode VARCHAR(20) DEFAULT 'subtask',
    test_case_issue_type VARCHAR(50) DEFAULT 'Sub-task',
    default_project_key VARCHAR(20),
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- LLM configurations table
CREATE TABLE IF NOT EXISTS llm_configurations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    default_provider VARCHAR(20) DEFAULT 'gemini',
    gemini_model VARCHAR(50) DEFAULT 'gemini-1.5-pro',
    claude_model VARCHAR(50) DEFAULT 'claude-3-5-sonnet-20241022',
    openai_model VARCHAR(50) DEFAULT 'gpt-4-turbo-preview',
    temperature FLOAT DEFAULT 0.3,
    max_tokens INTEGER DEFAULT 4096,
    gemini_api_key_encrypted TEXT,
    claude_api_key_encrypted TEXT,
    openai_api_key_encrypted TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Audit logs table
CREATE TABLE IF NOT EXISTS audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details JSONB,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);
CREATE INDEX IF NOT EXISTS idx_generation_history_user ON generation_history(user_id);
CREATE INDEX IF NOT EXISTS idx_generation_history_jira_key ON generation_history(jira_issue_key);
CREATE INDEX IF NOT EXISTS idx_generation_history_created ON generation_history(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_audit_logs_created ON audit_logs(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_audit_logs_action ON audit_logs(action);

-- Update timestamp function
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Apply update trigger to tables
DO $$ BEGIN
    CREATE TRIGGER update_users_updated_at
        BEFORE UPDATE ON users
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TRIGGER update_jira_configurations_updated_at
        BEFORE UPDATE ON jira_configurations
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

DO $$ BEGIN
    CREATE TRIGGER update_llm_configurations_updated_at
        BEFORE UPDATE ON llm_configurations
        FOR EACH ROW
        EXECUTE FUNCTION update_updated_at_column();
EXCEPTION
    WHEN duplicate_object THEN null;
END $$;

-- Insert default admin user (password: admin123)
-- In production, change this password immediately!
INSERT INTO users (email, hashed_password, name, role, is_active)
VALUES (
    'admin@example.com',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/X4.H.6.dLNqVEhkGC',
    'Administrator',
    'admin',
    true
) ON CONFLICT (email) DO NOTHING;

-- Grant permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres;
