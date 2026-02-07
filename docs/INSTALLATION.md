# 🔧 Guide d'Installation

## Prérequis

### Logiciels requis

| Logiciel | Version | Usage |
|----------|---------|-------|
| Python | 3.11+ | Backend runtime |
| Docker | 24+ | Containerisation |
| Docker Compose | 2.20+ | Orchestration locale |
| Git | 2.40+ | Gestion de versions |
| PostgreSQL | 15+ | Base de données (si sans Docker) |
| Redis | 7+ | Cache (si sans Docker) |

### Comptes et accès

- ✅ Compte Jira avec API Token
- ✅ Au moins une clé API LLM (Gemini, Claude, ou OpenAI)

## Installation Rapide (Docker)

### 1. Cloner le repository

```bash
git clone https://github.com/your-org/jira-qa-ai-generator.git
cd jira-qa-ai-generator
```

### 2. Configurer l'environnement

```bash
# Copier le fichier de configuration
cp .env.example .env

# Éditer avec vos credentials
notepad .env  # Windows
# ou
nano .env     # Linux/Mac
```

### 3. Configuration minimale (.env)

```env
# Jira (OBLIGATOIRE)
JIRA_URL=https://your-instance.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=votre-token-jira

# LLM - Au moins un (OBLIGATOIRE)
LLM_PROVIDER=gemini
GEMINI_API_KEY=votre-cle-gemini

# Sécurité
JWT_SECRET_KEY=une-cle-secrete-unique-et-longue
```

### 4. Lancer l'application

```bash
# Mode développement
docker-compose up -d

# Vérifier que tout fonctionne
docker-compose ps
docker-compose logs backend
```

### 5. Accéder à l'application

- **API**: http://localhost:8000
- **Documentation**: http://localhost:8000/docs
- **Health Check**: http://localhost:8000/health

## Installation Locale (Sans Docker)

### 1. Créer l'environnement Python

```bash
cd backend

# Créer l'environnement virtuel
python -m venv venv

# Activer l'environnement
# Windows
venv\Scripts\activate
# Linux/Mac
source venv/bin/activate

# Installer les dépendances
pip install -r requirements.txt
```

### 2. Configurer PostgreSQL

```sql
-- Créer la base de données
CREATE DATABASE jira_qa_ai;

-- Créer l'utilisateur
CREATE USER jira_qa_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE jira_qa_ai TO jira_qa_user;
```

### 3. Configurer Redis

```bash
# Windows: télécharger depuis https://redis.io/download
# Linux
sudo apt install redis-server
sudo systemctl start redis

# Mac
brew install redis
brew services start redis
```

### 4. Variables d'environnement

```bash
# Windows (PowerShell)
$env:DATABASE_URL="postgresql://jira_qa_user:your_password@localhost:5432/jira_qa_ai"
$env:REDIS_URL="redis://localhost:6379/0"
$env:JIRA_URL="https://your-instance.atlassian.net"
$env:JIRA_EMAIL="your-email@company.com"
$env:JIRA_API_TOKEN="your-token"
$env:GEMINI_API_KEY="your-key"
$env:JWT_SECRET_KEY="your-secret"

# Linux/Mac
export DATABASE_URL="postgresql://jira_qa_user:your_password@localhost:5432/jira_qa_ai"
export REDIS_URL="redis://localhost:6379/0"
# ... etc
```

### 5. Initialiser la base de données

```bash
# Appliquer les migrations (si Alembic configuré)
alembic upgrade head

# Ou exécuter le script SQL directement
psql -U jira_qa_user -d jira_qa_ai -f ../docker/init-db.sql
```

### 6. Lancer l'application

```bash
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## Configuration des API Keys

### Jira API Token

1. Connectez-vous à https://id.atlassian.com/manage-profile/security
2. Cliquez sur "Create API token"
3. Donnez un nom au token (ex: "QA AI Generator")
4. Copiez le token généré

### Google Gemini API Key

1. Accédez à https://aistudio.google.com/app/apikey
2. Cliquez sur "Create API Key"
3. Sélectionnez votre projet GCP
4. Copiez la clé

### Anthropic Claude API Key

1. Accédez à https://console.anthropic.com/
2. Allez dans Settings > API Keys
3. Cliquez sur "Create Key"
4. Copiez la clé

### OpenAI API Key

1. Accédez à https://platform.openai.com/api-keys
2. Cliquez sur "Create new secret key"
3. Copiez la clé

## Configuration Avancée

### Champs Jira personnalisés

```env
# Champ pour les critères d'acceptation
JIRA_ACCEPTANCE_CRITERIA_FIELD=customfield_10001

# Mode de publication des scénarios de test
JIRA_TEST_SCENARIOS_MODE=subtask  # ou comment, xray, zephyr

# Type d'issue pour les cas de test
JIRA_TEST_CASE_ISSUE_TYPE=Sub-task
```

### Paramètres LLM

```env
# Modèles spécifiques
LLM_GEMINI_MODEL=gemini-1.5-pro
LLM_CLAUDE_MODEL=claude-3-5-sonnet-20241022
LLM_OPENAI_MODEL=gpt-4-turbo-preview

# Paramètres de génération
LLM_TEMPERATURE=0.3
LLM_MAX_TOKENS=4096
LLM_TIMEOUT_SECONDS=60
```

### Rate Limiting

```env
# Limite par défaut
RATE_LIMIT_REQUESTS=100
RATE_LIMIT_PERIOD=60  # secondes
```

### Sécurité

```env
# JWT
JWT_SECRET_KEY=votre-cle-256-bits-minimum
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# CORS
CORS_ORIGINS=http://localhost:3000,https://app.company.com
```

## Vérification de l'installation

### 1. Test de santé

```bash
curl http://localhost:8000/health
# Réponse attendue: {"status":"healthy","timestamp":"..."}
```

### 2. Test d'authentification

```bash
# Créer un utilisateur (première fois)
curl -X POST "http://localhost:8000/api/v1/auth/register" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"AdminPass123","name":"Admin","role":"admin"}'

# Se connecter
curl -X POST "http://localhost:8000/api/v1/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@test.com","password":"AdminPass123"}'
```

### 3. Test de connexion Jira

```bash
curl -X GET "http://localhost:8000/api/v1/jira/validate" \
  -H "Authorization: Bearer YOUR_TOKEN"
```

### 4. Test de génération

```bash
curl -X POST "http://localhost:8000/api/v1/generate/acceptance-criteria" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"story_text":"En tant qu'\''utilisateur, je veux me connecter","story_title":"Login"}'
```

## Dépannage

### Erreur de connexion PostgreSQL

```
Connection refused (os error 111)
```

**Solutions:**
1. Vérifiez que PostgreSQL est démarré : `docker-compose ps` ou `systemctl status postgresql`
2. Vérifiez l'URL de connexion dans `.env`
3. Vérifiez les permissions de l'utilisateur

### Erreur de connexion Redis

```
Connection refused to redis://localhost:6379
```

**Solutions:**
1. Vérifiez que Redis est démarré
2. Vérifiez l'URL Redis dans `.env`

### Erreur Jira 401

```
JIRA authentication failed
```

**Solutions:**
1. Vérifiez votre email Jira
2. Régénérez votre API token
3. Vérifiez l'URL Jira (inclure https://)

### Erreur LLM

```
API key not valid
```

**Solutions:**
1. Vérifiez que la clé API est correcte
2. Vérifiez que le provider correspond à la clé
3. Vérifiez les quotas/limites de votre compte

## Prochaines étapes

- 📖 Consultez le [Guide d'utilisation](USER_GUIDE.md)
- 🔧 Consultez le [Guide d'exploitation](OPERATIONS.md)
- 📐 Consultez l'[Architecture](ARCHITECTURE.md)
