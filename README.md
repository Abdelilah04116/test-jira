# Jira QA AI Generator

> **Réalisé par :** AI Engineer ABDELILAH OURTI  

[![Email](https://img.shields.io/badge/Email-Contact-red)](mailto:abdelilahourti@gmail.com)
[![LinkedIn](https://img.shields.io/badge/LinkedIn-Connect-blue)](https://www.linkedin.com/in/abdelilah-ourti-a529412a8)
[![GitHub](https://img.shields.io/badge/GitHub-Profile-black)](https://github.com/abdelilah04116)
[![Portfolio](https://img.shields.io/badge/Portfolio-Visit-orange)](https://abdelilah04116.github.io/)

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109+-green.svg)](https://fastapi.tiangolo.com)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

## Description

Application IA d'entreprise qui génère automatiquement des **critères d'acceptation Gherkin** et des **scénarios de test** à partir de User Stories Jira, avec publication automatique dans Jira.

## Fonctionnalités

- **Récupération automatique** des User Stories depuis Jira
- **Génération de critères d'acceptation** au format Gherkin (Given/When/Then)
- **Génération de scénarios de test** (positifs, négatifs, edge cases)
- **Publication automatique dans Jira** (champs, commentaires, sous-tâches)
- **Multi-LLM** : Gemini, Claude, OpenAI (interchangeable)
- **Sécurité Enterprise** : JWT, OAuth2, gestion des rôles
- **Docker-ready** avec CI/CD complet

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React/Next.js)                  │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                     API GATEWAY (Nginx/Traefik)                  │
└─────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────┐
│                        FASTAPI BACKEND                           │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ Auth/JWT    │  │ Rate Limit  │  │ Request Validation      │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │                    BUSINESS LOGIC                            ││
│  │  ┌───────────────┐  ┌───────────────┐  ┌────────────────┐   ││
│  │  │ Jira Service  │  │ LLM Service   │  │ Generator Svc  │   ││
│  │  └───────────────┘  └───────────────┘  └────────────────┘   ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────┘
          │                    │                    │
          ▼                    ▼                    ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│   JIRA API      │  │   LLM APIs      │  │   PostgreSQL    │
│   (REST/Cloud)  │  │ Gemini/Claude/  │  │   (Metadata)    │
│                 │  │ OpenAI          │  │                 │
└─────────────────┘  └─────────────────┘  └─────────────────┘
```

## Quick Start

### Prérequis

- Python 3.11+
- Docker & Docker Compose
- Compte Jira avec API Token
- API Key pour au moins un LLM (Gemini/Claude/OpenAI)

### Installation

```bash
# Cloner le repository
git clone https://github.com/your-org/jira-qa-ai-generator.git
cd jira-qa-ai-generator

# Créer l'environnement
cp .env.example .env
# Éditer .env avec vos credentials

# Lancer avec Docker
docker-compose up -d

# OU installation manuelle
# 1. Backend
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload

# 2. Frontend
cd ../frontend
npm install
npm run dev
```

### Configuration

```env
# .env
JIRA_URL=https://your-instance.atlassian.net
JIRA_EMAIL=your-email@company.com
JIRA_API_TOKEN=your-jira-api-token

# LLM Provider (gemini, claude, openai)
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-gemini-key
CLAUDE_API_KEY=your-claude-key
OPENAI_API_KEY=your-openai-key

# Security
JWT_SECRET_KEY=your-super-secret-key
JWT_ALGORITHM=HS256
```

## API Endpoints

| Méthode | Endpoint | Description |
|---------|----------|-------------|
| `POST` | `/api/v1/auth/login` | Authentification |
| `GET` | `/api/v1/jira/story/{issue_id}` | Récupérer une User Story |
| `POST` | `/api/v1/generate/acceptance-criteria` | Générer critères Gherkin |
| `POST` | `/api/v1/generate/test-scenarios` | Générer scénarios de test |
| `POST` | `/api/v1/jira/publish` | Publier dans Jira |
| `POST` | `/api/v1/generate/full-pipeline` | Pipeline complet |

## Documentation

- [Guide d'installation](docs/INSTALLATION.md)
- [Guide d'utilisation](docs/USER_GUIDE.md)
- [Architecture technique](docs/ARCHITECTURE.md)
- [Guide d'exploitation](docs/OPERATIONS.md)
- [API Reference](docs/API_REFERENCE.md)

## Tests

```bash
cd backend
pytest tests/ -v --cov=app
```

## Déploiement

### Docker Compose (Dev/Staging)
```bash
docker-compose -f docker-compose.yml up -d
```

### Kubernetes (Production)
```bash
kubectl apply -f kubernetes/
```

## Sécurité

- Authentification JWT avec refresh tokens
- Chiffrement des API keys en base
- Rate limiting par utilisateur
- Validation stricte des entrées
- Logs d'audit complets

## Realiser avec Abdelilah Ourti 


