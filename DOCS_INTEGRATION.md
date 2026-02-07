# Documentation d'Intégration Backend

Cette documentation détaille les points de terminaison (endpoints) de l'API FastAPI utilisés par l'interface frontend pour la gestion des pipelines QA et de l'intégration Jira.

## 1. Authentification
L'interface utilise une authentification par porteur (Bearer Token).
- **Endpoint** : `/api/v1/auth/login`
- **Refresh** : `/api/v1/auth/refresh`
- **Intercepteur Frontend** : Configuré dans `src/lib/api.ts`. Il attache automatiquement le `access_token` stocké dans le `localStorage` à chaque requête.

## 2. Génération de Critères d'Acceptation & Scénarios
Le moteur de traitement principal est accessible via les endpoints suivants :

### Analyse complète (Pipeline)
- **POST** `/api/v1/generate/full-pipeline`
- **Payload** :
  ```json
  {
    "issue_id": "PROJ-123",
    "auto_publish": true,
    "generate_tests": true
  }
  ```
- **Usage** : Utilisé par la page `PipelinePage` lors du lancement d'une analyse via un identifiant Jira.

### Analyse manuelle
- **POST** `/api/v1/generate/acceptance-criteria`
- **Payload** :
  ```json
  {
    "story_text": "En tant qu'utilisateur, je souhaite...",
    "story_title": "Titre de la story",
    "max_scenarios": 5
  }
  ```
- **Usage** : Utilisé pour les entrées manuelles (Text Libre).

## 3. Configuration Jira
- **POST** `/api/v1/jira/config` : Mise à jour des paramètres de connexion (URL, Email, Token).
- **GET** `/api/v1/jira/health` : Test de la connexion avec l'instance Atlassian.

## 4. Configuration du Moteur de Traitement (Processing Engine)
- **GET** `/api/v1/generate/providers` : Liste les modules de traitement disponibles (masqués dans l'UI sous des noms génériques).
- **POST** `/api/v1/generate/config` : Ajuste les paramètres de sensibilité (température) et les buffers.

---

# Guide d'Exploitation Utilisateur - Enterprise QA Connector

Ce guide explique comment utiliser l'interface professionnelle pour gérer vos flux QA Jira.

## 1. Configuration Initiale
Avant de lancer des analyses, assurez-vous que votre instance Jira est connectée :
1. Allez dans **Configuration > Jira Integration**.
2. Renseignez l'URL de votre instance, votre email et votre jeton API Atlassian.
3. Cliquez sur **Test Connection** pour valider.

## 2. Lancement d'une Analyse de Besoins
Pour générer des critères d'acceptation et des scénarios de test :
1. Cliquez sur **New Analysis** dans la barre latérale.
2. Choisissez le mode d'entrée :
   - **Jira Issue** : Saisissez l'ID de la Story (ex: PROJ-123).
   - **Manual Entry** : Copiez-collez directement les spécifications métier.
3. Cliquez sur **Start Analysis**.

## 3. Revue et Validation
Une fois l'analyse terminée, vous disposez de deux colonnes :
- **Acceptance Criteria** : Formattés en Gherkin (`Given/When/Then`).
- **Validation Suite** : Liste des cas de tests identifiés (smoke tests, cas limites, sécurité).

## 4. Synchronisation Jira
Après revue des résultats :
- Cliquez sur **Sync with Jira** pour publier automatiquement les scénarios dans le ticket d'origine.
- Les artifacts sont également sauvegardés dans l'**Analysis Repository** pour une consultation ultérieure.

## 5. Meilleures Pratiques
- **Précision** : Plus la description manuelle est précise, plus les critères d'acceptation seront pertinents.
- **Sécurité** : Utilisez "Strict Logic" dans les réglages du moteur pour des tests critiques, ou "Comprehensive Coverage" pour des explorations de fonctionnalités plus larges.
