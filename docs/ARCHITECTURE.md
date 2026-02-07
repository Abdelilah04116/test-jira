# 📐 Architecture Technique

## Vue d'ensemble

L'application **Jira QA AI Generator** est une solution enterprise-grade pour la génération automatique de critères d'acceptation et de scénarios de test à partir de User Stories Jira.

## Diagramme d'Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              CLIENTS                                         │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │ Web Browser  │  │ API Client   │  │ CI/CD        │  │ CLI Tool     │     │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘     │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         INFRASTRUCTURE LAYER                                 │
│  ┌──────────────────────────────────────────────────────────────────────┐   │
│  │                     Load Balancer / Ingress                           │   │
│  │                    (Nginx / Kubernetes Ingress)                       │   │
│  └──────────────────────────────────┬───────────────────────────────────┘   │
│                                     │                                        │
│  ┌──────────────────────────────────▼───────────────────────────────────┐   │
│  │                     API Gateway (Rate Limiting, SSL)                  │   │
│  └──────────────────────────────────┬───────────────────────────────────┘   │
└─────────────────────────────────────┼───────────────────────────────────────┘
                                      │
                                      ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          APPLICATION LAYER                                   │
│                                                                              │
│  ┌────────────────────────────────────────────────────────────────────────┐ │
│  │                         FastAPI Backend                                 │ │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                  │ │
│  │  │ Auth Module  │  │ Rate Limiter │  │ Validators   │                  │ │
│  │  │ (JWT/OAuth2) │  │ (Redis)      │  │ (Pydantic)   │                  │ │
│  │  └──────────────┘  └──────────────┘  └──────────────┘                  │ │
│  │                                                                         │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │                      API ENDPOINTS                                │  │ │
│  │  │  /api/v1/auth/*      Authentication & Authorization              │  │ │
│  │  │  /api/v1/jira/*      Jira Integration                            │  │ │
│  │  │  /api/v1/generate/*  AI Generation                               │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  │                                                                         │ │
│  │  ┌──────────────────────────────────────────────────────────────────┐  │ │
│  │  │                    BUSINESS LOGIC LAYER                           │  │ │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐   │  │ │
│  │  │  │ QA Generator    │  │ Jira Service    │  │ LLM Service     │   │  │ │
│  │  │  │ Service         │  │                 │  │                 │   │  │ │
│  │  │  └─────────────────┘  └─────────────────┘  └─────────────────┘   │  │ │
│  │  └──────────────────────────────────────────────────────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────┬───────────────────────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          │                           │                           │
          ▼                           ▼                           ▼
┌─────────────────────┐  ┌──────────────────────┐  ┌─────────────────────────┐
│   DATA LAYER        │  │   EXTERNAL SERVICES  │  │   PERSISTENCE LAYER     │
│                     │  │                      │  │                         │
│  ┌───────────────┐  │  │  ┌────────────────┐  │  │  ┌─────────────────┐   │
│  │  PostgreSQL   │  │  │  │   Jira REST    │  │  │  │     Redis       │   │
│  │  (Main DB)    │  │  │  │   API          │  │  │  │   (Cache)       │   │
│  └───────────────┘  │  │  └────────────────┘  │  │  └─────────────────┘   │
│                     │  │                      │  │                         │
│  Tables:            │  │  ┌────────────────┐  │  │  Usage:                │
│  - users            │  │  │ LLM APIs:      │  │  │  - Rate limiting       │
│  - generation_hist  │  │  │ - Gemini       │  │  │  - Session cache       │
│  - jira_configs     │  │  │ - Claude       │  │  │  - Token blacklist     │
│  - llm_configs      │  │  │ - OpenAI       │  │  │                         │
│  - audit_logs       │  │  └────────────────┘  │  │                         │
└─────────────────────┘  └──────────────────────┘  └─────────────────────────┘
```

## Composants Principaux

### 1. API Layer (FastAPI)

**Responsabilités:**
- Exposition des endpoints REST
- Validation des requêtes (Pydantic)
- Authentification/Autorisation (JWT)
- Rate limiting
- Logging et monitoring

**Endpoints:**

| Groupe | Endpoint | Description |
|--------|----------|-------------|
| Auth | `POST /auth/login` | Authentification utilisateur |
| Auth | `POST /auth/register` | Création de compte |
| Auth | `POST /auth/refresh` | Refresh token |
| Jira | `GET /jira/story/{id}` | Récupérer une User Story |
| Jira | `GET /jira/search` | Recherche JQL |
| Jira | `POST /jira/publish` | Publier dans Jira |
| Generate | `POST /generate/acceptance-criteria` | Générer critères Gherkin |
| Generate | `POST /generate/test-scenarios` | Générer scénarios de test |
| Generate | `POST /generate/full-pipeline` | Pipeline complet |

### 2. Business Logic Layer

#### QAGeneratorService

```python
class QAGeneratorService:
    """Service principal orchestrant le workflow de génération"""
    
    async def fetch_story(issue_id: str) -> JiraStory
    async def generate_acceptance_criteria(request) -> AcceptanceCriteria
    async def generate_test_scenarios(request) -> TestSuite
    async def publish_to_jira(request) -> JiraPublishResponse
    async def run_full_pipeline(request) -> FullPipelineResponse
```

#### LLM Factory (Pattern Factory)

```python
class LLMFactory:
    """Factory pour créer des clients LLM de manière agnostique"""
    
    @classmethod
    def create(provider: str, api_key: str) -> BaseLLMClient
```

**Providers supportés:**
- **Gemini** (Google): `gemini-1.5-pro`, `gemini-1.5-flash`
- **Claude** (Anthropic): `claude-3-5-sonnet`, `claude-3-opus`
- **OpenAI**: `gpt-4-turbo`, `gpt-4o`

### 3. Jira Integration Layer

#### JiraClient

```python
class JiraClient:
    """Client REST pour l'API Jira"""
    
    # Lecture
    async def get_issue(issue_id: str) -> JiraStory
    async def search_issues(jql: str) -> List[JiraStory]
    
    # Écriture
    async def update_description(issue_id, content)
    async def add_comment(issue_id, body)
    async def create_subtask(parent_key, summary, description)
    async def update_custom_field(issue_id, field_id, value)
    
    # Publication haut niveau
    async def publish_acceptance_criteria(issue_id, criteria, mode)
    async def publish_test_scenarios(issue_id, test_suite, mode)
```

**Modes de publication:**
- `DESCRIPTION`: Ajout dans la description de l'issue
- `COMMENT`: Ajout comme commentaire
- `SUBTASK`: Création de sous-tâches (pour les tests)
- `CUSTOM_FIELD`: Mise à jour d'un champ personnalisé
- `XRAY`: Intégration Xray for Jira
- `ZEPHYR`: Intégration Zephyr Scale

### 4. Data Layer

#### Modèles de données (PostgreSQL)

```sql
-- Utilisateurs et authentification
users (id, email, hashed_password, name, role, is_active, ...)

-- Historique des générations
generation_history (id, user_id, jira_issue_key, llm_provider, 
                   acceptance_criteria_json, test_scenarios_json, ...)

-- Configurations
jira_configurations (id, jira_url, acceptance_criteria_field, ...)
llm_configurations (id, default_provider, gemini_model, ...)

-- Audit
audit_logs (id, user_id, action, resource_type, details, ...)
```

## Flux de Données

### Pipeline Complet

```
1. [Client] POST /api/v1/generate/full-pipeline
              │
              ▼
2. [Auth] Validation JWT Token
              │
              ▼
3. [Rate Limit] Vérification quota
              │
              ▼
4. [Jira Client] GET /rest/api/3/issue/{id}
              │
              ▼
5. [LLM Client] POST (Gemini/Claude/OpenAI)
              │  Prompt: acceptance-criteria
              ▼
6. [Parser] JSON → AcceptanceCriteria
              │
              ▼
7. [LLM Client] POST (Gemini/Claude/OpenAI)
              │  Prompt: test-scenarios
              ▼
8. [Parser] JSON → TestSuite
              │
              ▼
9. [Jira Client] PUT/POST (publish)
              │
              ▼
10. [Response] FullPipelineResponse
```

## Sécurité

### Couches de sécurité

1. **Transport**: TLS 1.2+ (HTTPS)
2. **Authentification**: JWT avec refresh tokens
3. **Autorisation**: RBAC (Admin, QA, PO, Developer)
4. **Rate Limiting**: Par IP et par utilisateur
5. **Validation**: Pydantic schemas stricts
6. **Chiffrement**: API keys chiffrées en base (Fernet)
7. **Audit**: Logging complet des actions

### Gestion des secrets

```
┌─────────────────────────────────────────────────┐
│              Secret Management                   │
├─────────────────────────────────────────────────┤
│ Development: .env file (non commité)            │
│ Staging: Docker secrets / Vault                 │
│ Production: Kubernetes secrets / Vault          │
└─────────────────────────────────────────────────┘
```

## Scalabilité

### Horizontal Scaling

```
                    ┌─────────────────┐
                    │  Load Balancer  │
                    └────────┬────────┘
           ┌─────────────────┼─────────────────┐
           ▼                 ▼                 ▼
    ┌─────────────┐   ┌─────────────┐   ┌─────────────┐
    │ Backend #1  │   │ Backend #2  │   │ Backend #3  │
    └─────────────┘   └─────────────┘   └─────────────┘
           │                 │                 │
           └─────────────────┼─────────────────┘
                             ▼
    ┌─────────────────────────────────────────────────┐
    │              Shared Services                     │
    │  ┌───────────┐  ┌───────────┐  ┌───────────┐   │
    │  │ PostgreSQL│  │   Redis   │  │   S3/GCS  │   │
    │  │ (Primary) │  │ (Cluster) │  │  (Logs)   │   │
    │  └───────────┘  └───────────┘  └───────────┘   │
    └─────────────────────────────────────────────────┘
```

### Auto-scaling (Kubernetes)

```yaml
HorizontalPodAutoscaler:
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - cpu: 70%
    - memory: 80%
```

## Monitoring & Observabilité

### Stack de monitoring

| Composant | Usage |
|-----------|-------|
| Prometheus | Métriques applicatives |
| Grafana | Dashboards & alertes |
| Loguru | Logging structuré |
| Sentry | Error tracking |
| Jaeger | Distributed tracing |

### Métriques clés

```
# Endpoints
http_requests_total
http_request_duration_seconds_bucket

# LLM
llm_requests_total{provider="gemini|claude|openai"}
llm_request_duration_seconds
llm_tokens_used_total

# Jira
jira_requests_total{operation="read|write"}
jira_publish_success_total

# Business
acceptance_criteria_generated_total
test_scenarios_generated_total
full_pipeline_duration_seconds
```

## Environnements

| Environnement | URL | Usage |
|---------------|-----|-------|
| Development | localhost:8000 | Dev local |
| Staging | staging.jira-qa.internal | Tests d'intégration |
| Production | api.jira-qa.company.com | Production |

## Technologies utilisées

| Catégorie | Technologie | Version |
|-----------|-------------|---------|
| Framework | FastAPI | 0.109+ |
| Runtime | Python | 3.11+ |
| Database | PostgreSQL | 15+ |
| Cache | Redis | 7+ |
| Container | Docker | 24+ |
| Orchestration | Kubernetes | 1.28+ |
| CI/CD | GitHub Actions | - |
| Monitoring | Prometheus + Grafana | - |
