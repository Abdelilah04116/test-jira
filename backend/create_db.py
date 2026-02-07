"""
Script de création de la base de données et des tables.
Utilise une connexion directe asyncpg qui correspond EXACTEMENT aux modèles SQLAlchemy.
"""
import asyncio
import asyncpg
from passlib.context import CryptContext

# Configuration du hash de mot de passe
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

CREATE_TABLES_SQL = """
-- Les colonnes UUID nécessitent parfois l'extension pgcrypto pour gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Drop existing tables to avoid conflicts
DROP TABLE IF EXISTS audit_logs CASCADE;
DROP TABLE IF EXISTS jira_configurations CASCADE;
DROP TABLE IF EXISTS llm_configurations CASCADE;
DROP TABLE IF EXISTS generation_history CASCADE;
DROP TABLE IF EXISTS configurations CASCADE;
DROP TABLE IF EXISTS users CASCADE;

-- Users table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    name VARCHAR(100) NOT NULL,
    role VARCHAR(50) NOT NULL DEFAULT 'QA',
    is_active BOOLEAN DEFAULT TRUE,
    jira_api_token_encrypted TEXT,
    gemini_api_key_encrypted TEXT,
    claude_api_key_encrypted TEXT,
    openai_api_key_encrypted TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITHOUT TIME ZONE
);

-- Generation history table
CREATE TABLE generation_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    jira_issue_key VARCHAR(50) NOT NULL,
    jira_issue_summary VARCHAR(500),
    jira_project_key VARCHAR(20),
    llm_provider VARCHAR(20) NOT NULL,
    llm_model VARCHAR(50),
    acceptance_criteria_json JSONB,
    gherkin_text TEXT,
    test_scenarios_json JSONB,
    published_to_jira BOOLEAN DEFAULT FALSE,
    jira_publish_mode VARCHAR(20),
    jira_subtasks_created JSONB,
    processing_time_seconds FLOAT,
    acceptance_criteria_count INTEGER DEFAULT 0,
    test_scenarios_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Jira Configuration table
CREATE TABLE jira_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    jira_url VARCHAR(255) NOT NULL,
    jira_email VARCHAR(255) NOT NULL,
    jira_api_token_encrypted TEXT NOT NULL,
    acceptance_criteria_field VARCHAR(100) DEFAULT 'description',
    test_scenarios_mode VARCHAR(20) DEFAULT 'subtask',
    test_case_issue_type VARCHAR(50) DEFAULT 'Sub-task',
    default_project_key VARCHAR(20),
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- LLM Configuration table
CREATE TABLE llm_configurations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Audit Log table
CREATE TABLE audit_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action VARCHAR(100) NOT NULL,
    resource_type VARCHAR(50),
    resource_id VARCHAR(100),
    details JSONB,
    ip_address VARCHAR(45),
    user_agent VARCHAR(500),
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    created_at TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_gen_history_user ON generation_history(user_id);
CREATE INDEX idx_gen_history_issue ON generation_history(jira_issue_key);
CREATE INDEX idx_audit_user ON audit_logs(user_id);
CREATE INDEX idx_audit_action ON audit_logs(action);
"""

async def setup_database():
    print("=" * 60)
    print("🔥 Setup Complet de la Base de Données PostgreSQL 🔥")
    print("=" * 60)
    
    # 1. Connexion à postgres pour créer la base
    try:
        conn = await asyncpg.connect(user='postgres', password='1234', database='postgres', host='127.0.0.1')
        try:
            await conn.execute('CREATE DATABASE ai_qa_saas')
            print("✅ Base 'ai_qa_saas' créée.")
        except asyncpg.DuplicateDatabaseError:
            print("ℹ️ Base 'ai_qa_saas' existe déjà.")
        finally:
            await conn.close()
    except Exception as e:
        print(f"❌ Erreur connexion initiale : {e}")
        return

    # 2. Création des tables
    print("\n🛠️ Création des tables selon le schéma SQLAlchemy...")
    try:
        conn = await asyncpg.connect(user='postgres', password='1234', database='ai_qa_saas', host='127.0.0.1')
        await conn.execute(CREATE_TABLES_SQL)
        print("✅ Schéma créé avec succès !")
        
        # 3. Création de l'utilisateur admin par défaut
        print("\n👤 Création de l'utilisateur admin par défaut...")
        email = "admin@example.com"
        password = "admin1234"
        hashed_password = pwd_context.hash(password)
        
        await conn.execute('''
            INSERT INTO users (email, hashed_password, name, role, is_active)
            VALUES ($1, $2, $3, $4, $5)
        ''', email, hashed_password, 'Directeur Admin', 'admin', True)
        
        print(f"✅ Utilisateur {email} créé (Mot de passe: {password})")
        
        await conn.close()
    except Exception as e:
        print(f"❌ Erreur lors du setup : {e}")
        return

    print("\n" + "=" * 60)
    print("🚀 BASE DE DONNÉES PRÊTE ! Relancez uvicorn.")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(setup_database())
