# 📚 API Reference

## Base URL
- Development: `http://localhost:8000/api/v1`
- Production: `https://api.jira-qa.company.com/api/v1`

## Authentication

### POST /auth/login
```json
Request: {"email": "user@example.com", "password": "password"}
Response: {"access_token": "...", "refresh_token": "...", "token_type": "bearer", "expires_in": 1800}
```

### POST /auth/register
```json
Request: {"email": "user@example.com", "password": "password", "name": "User", "role": "qa"}
Response: {"id": "uuid", "email": "...", "name": "...", "role": "qa", "is_active": true}
```

### POST /auth/refresh
```json
Request: {"refresh_token": "..."}
Response: {"access_token": "...", "refresh_token": "...", "token_type": "bearer"}
```

## Jira Operations

### GET /jira/story/{issue_id}
Fetch a Jira story by ID.
```json
Response: {"key": "PROJ-123", "summary": "...", "description": "...", "status": "..."}
```

### GET /jira/search?jql={query}&max_results={n}
Search stories using JQL.

### POST /jira/publish
```json
Request: {
  "issue_id": "PROJ-123",
  "acceptance_criteria": {...},
  "test_suite": {...},
  "publish_mode": "subtask"
}
```

## Generation

### POST /generate/acceptance-criteria
```json
Request: {"issue_id": "PROJ-123", "context": "...", "max_scenarios": 5, "llm_provider": "gemini"}
Response: {"success": true, "acceptance_criteria": {...}, "gherkin_text": "..."}
```

### POST /generate/test-scenarios
```json
Request: {"issue_id": "PROJ-123", "include_negative": true, "include_edge_cases": true}
Response: {"success": true, "test_suite": {...}}
```

### POST /generate/full-pipeline
```json
Request: {"issue_id": "PROJ-123", "auto_publish": true, "generate_tests": true}
Response: {"success": true, "story": {...}, "acceptance_criteria": {...}, "test_suite": {...}}
```

## Error Codes
- 400: Bad Request
- 401: Unauthorized
- 403: Forbidden
- 404: Not Found
- 429: Rate Limit Exceeded
- 500: Internal Server Error
