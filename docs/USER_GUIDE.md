# 📖 Guide d'Utilisation

## Introduction

Ce guide vous accompagne dans l'utilisation de l'application **Jira QA AI Generator** pour automatiser la génération de critères d'acceptation et de scénarios de test.

## Prérequis

Avant de commencer, assurez-vous d'avoir :

- ✅ Un compte utilisateur créé dans l'application
- ✅ Accès à votre instance Jira
- ✅ Des User Stories dans Jira prêtes à être traitées

## Connexion

### Via l'API

```bash
# Obtenir un token d'accès
curl -X POST "https://api.jira-qa.company.com/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "votre.email@company.com",
    "password": "votre_mot_de_passe"
  }'
```

**Réponse:**
```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIs...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIs...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Utilisation du token

Incluez le token dans toutes les requêtes :

```bash
curl -X GET "https://api.jira-qa.company.com/api/v1/jira/story/PROJ-123" \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIs..."
```

## Cas d'usage

### 1. Récupérer une User Story

```bash
GET /api/v1/jira/story/{issue_id}
```

**Exemple:**
```bash
curl -X GET "https://api.jira-qa.company.com/api/v1/jira/story/PROJ-123" \
  -H "Authorization: Bearer $TOKEN"
```

**Réponse:**
```json
{
  "id": "10001",
  "key": "PROJ-123",
  "summary": "En tant qu'utilisateur, je veux me connecter avec mon email",
  "description": "L'utilisateur doit pouvoir se connecter à l'application...",
  "issue_type": "Story",
  "status": "In Progress",
  "project_key": "PROJ",
  "labels": ["auth", "mvp"]
}
```

### 2. Générer des Critères d'Acceptation

```bash
POST /api/v1/generate/acceptance-criteria
```

**Corps de la requête:**
```json
{
  "issue_id": "PROJ-123",
  "context": "Application bancaire avec authentification 2FA",
  "llm_provider": "gemini",
  "max_scenarios": 5
}
```

**Exemple complet:**
```bash
curl -X POST "https://api.jira-qa.company.com/api/v1/generate/acceptance-criteria" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "issue_id": "PROJ-123",
    "max_scenarios": 5
  }'
```

**Réponse:**
```json
{
  "success": true,
  "story_key": "PROJ-123",
  "acceptance_criteria": {
    "feature_name": "User Authentication",
    "scenarios": [
      {
        "id": "AC-001",
        "title": "Successful login with valid credentials",
        "given": ["the user is on the login page", "the user has a valid account"],
        "when": ["the user enters valid email", "the user enters valid password", "the user clicks login"],
        "then": ["the user is redirected to the dashboard", "a welcome message is displayed"],
        "tags": ["positive", "smoke"]
      }
    ]
  },
  "gherkin_text": "Feature: User Authentication\n\n  Scenario: Successful login...",
  "processing_time_seconds": 3.45
}
```

### 3. Générer des Scénarios de Test

```bash
POST /api/v1/generate/test-scenarios
```

**Corps de la requête:**
```json
{
  "issue_id": "PROJ-123",
  "include_negative": true,
  "include_edge_cases": true,
  "max_scenarios_per_criteria": 3
}
```

**Exemple:**
```bash
curl -X POST "https://api.jira-qa.company.com/api/v1/generate/test-scenarios" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "issue_id": "PROJ-123",
    "include_negative": true,
    "include_edge_cases": true
  }'
```

**Réponse:**
```json
{
  "success": true,
  "story_key": "PROJ-123",
  "test_suite": {
    "suite_name": "Test Suite for PROJ-123",
    "scenarios": [
      {
        "id": "TS-001",
        "title": "Verify login with valid credentials",
        "type": "positive",
        "priority": "High",
        "steps": [
          {
            "order": 1,
            "action": "Navigate to login page",
            "expected_result": "Login form is displayed"
          }
        ],
        "acceptance_criteria_ref": "AC-001"
      }
    ],
    "total_scenarios": 12,
    "positive_count": 5,
    "negative_count": 4,
    "edge_case_count": 3
  }
}
```

### 4. Publier dans Jira

```bash
POST /api/v1/jira/publish
```

**Corps de la requête:**
```json
{
  "issue_id": "PROJ-123",
  "acceptance_criteria": {...},
  "test_suite": {...},
  "publish_mode": "subtask"
}
```

**Modes disponibles:**
| Mode | Description |
|------|-------------|
| `subtask` | Crée une sous-tâche par scénario de test |
| `comment` | Ajoute un commentaire structuré |
| `description` | Enrichit la description de l'issue |
| `custom_field` | Met à jour un champ personnalisé |

**Exemple:**
```bash
curl -X POST "https://api.jira-qa.company.com/api/v1/jira/publish" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "issue_id": "PROJ-123",
    "acceptance_criteria": {...},
    "test_suite": {...},
    "publish_mode": "subtask"
  }'
```

**Réponse:**
```json
{
  "success": true,
  "issue_key": "PROJ-123",
  "acceptance_criteria_published": true,
  "acceptance_criteria_location": "description",
  "test_scenarios_published": true,
  "created_subtasks": [
    {"key": "PROJ-124", "title": "[TEST] Login with valid credentials"},
    {"key": "PROJ-125", "title": "[TEST] Login with invalid password"},
    {"key": "PROJ-126", "title": "[TEST] Login with empty fields"}
  ],
  "jira_link": "https://your-instance.atlassian.net/browse/PROJ-123"
}
```

### 5. Pipeline Complet (Recommandé)

Pour exécuter tout le workflow en une seule requête :

```bash
POST /api/v1/generate/full-pipeline
```

**Corps de la requête:**
```json
{
  "issue_id": "PROJ-123",
  "llm_provider": "gemini",
  "auto_publish": true,
  "publish_mode": "subtask",
  "generate_tests": true
}
```

**Exemple:**
```bash
curl -X POST "https://api.jira-qa.company.com/api/v1/generate/full-pipeline" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "issue_id": "PROJ-123",
    "auto_publish": true
  }'
```

**Ce que fait le pipeline:**
1. 📥 Récupère la User Story depuis Jira
2. 📝 Génère les critères d'acceptation (Gherkin)
3. 🧪 Génère les scénarios de test
4. 📤 Publie automatiquement dans Jira

### 6. Pipeline Multi-Agent Agentique (Avancé) 🤖

Il utilise une architecture multi-agent pour non seulement générer du contenu, mais aussi le réviser, le valider et l'intégrer dans votre code.

**Agents activés :**
1.  **Orchestrator Agent** 🧠 : Coordonne tout le workflow et gère la télémétrie.
2.  **GherkinGenerator Agent** 📝 : Analyse la story et génère les critères (Gherkin).
3.  **TestGenerator Agent** 🧪 : Planifie la stratégie de test.
4.  **AutomationEngineer Agent** 💻 : Écrit le code Playwright (TypeScript).
5.  **CodeReviewer Agent** 🔍 : (IA) Révision du code, vérification de la robustesse.
6.  **GitOps Agent** 🚀 : Crée les fichiers `.spec.ts` et les pousse dans Git.
7.  **JiraPublisher** 📤 : Synchronise tout avec Jira.

**Configuration requise (`.env`) :**

```bash
GIT_REPO_URL=https://github.com/votre-org/votre-repo-tests.git
GIT_TOKEN=votre_personal_access_token
GIT_AUTO_PUSH=true
```


## Choix du LLM

L'application supporte plusieurs modèles d'IA :

| Provider | Modèle | Recommandé pour |
|----------|--------|-----------------|
| `gemini` | gemini-1.5-pro | Usage général (rapide) |
| `claude` | claude-3-5-sonnet | Analyses complexes |
| `openai` | gpt-4-turbo | Qualité maximale |

**Spécifier le provider:**
```json
{
  "issue_id": "PROJ-123",
  "llm_provider": "claude"
}
```

## Format Gherkin

Les critères d'acceptation sont générés au format BDD Gherkin standard :

```gherkin
Feature: User Authentication

  Background:
    Given the application is running
    And the database is initialized

  @positive @smoke
  Scenario: Successful login with valid credentials
    Given the user is on the login page
    And the user has a valid account
    When the user enters email "user@example.com"
    And the user enters password "SecurePass123"
    And the user clicks the login button
    Then the user should be redirected to the dashboard
    And a welcome message should be displayed

  @negative
  Scenario: Failed login with invalid password
    Given the user is on the login page
    When the user enters email "user@example.com"
    And the user enters password "WrongPassword"
    And the user clicks the login button
    Then an error message "Invalid credentials" should be displayed
    And the user should remain on the login page
```

## Bonnes Pratiques

### 1. User Stories de qualité

Pour de meilleurs résultats, assurez-vous que vos User Stories contiennent :

✅ Un titre clair et descriptif
✅ Une description détaillée avec le contexte métier
✅ Les critères d'acceptation initiaux (si existants)
✅ Les contraintes techniques connues

### 2. Contexte additionnel

Fournissez du contexte pour améliorer la pertinence :

```json
{
  "issue_id": "PROJ-123",
  "context": "Application bancaire avec conformité PCI-DSS. L'authentification doit supporter 2FA par SMS et TOTP."
}
```

### 3. Révision des résultats

Après génération, passez en revue :
- La pertinence des scénarios
- La couverture fonctionnelle
- La clarté des étapes
- Les cas manquants spécifiques à votre contexte

### 4. Itération

N'hésitez pas à regénérer avec différents paramètres si le résultat initial n'est pas satisfaisant.

## Dépannage

### Token expiré

```json
{
  "detail": "Invalid or expired token"
}
```
**Solution:** Utilisez le refresh token ou reconnectez-vous.

### Issue non trouvée

```json
{
  "error": "Issue PROJ-123 not found"
}
```
**Solution:** Vérifiez l'ID de l'issue et vos permissions Jira.

### Rate limit dépassé

```json
{
  "detail": "Rate limit exceeded. Please try again later."
}
```
**Solution:** Attendez quelques secondes avant de réessayer.

## Support

Pour toute question ou problème :
- 📧 Email: support@company.com
- 📝 Jira: Créez un ticket dans le projet SUPPORT
- 📚 Documentation API: `/docs` (en mode développement)
