# 🏭 Guide d'Exploitation Enterprise

## Déploiement

### Docker Compose (Staging)
```bash
docker-compose up -d
docker-compose logs -f backend
```

### Kubernetes (Production)
```bash
kubectl apply -f kubernetes/
kubectl get pods -n jira-qa-ai
kubectl rollout status deployment/jira-qa-backend -n jira-qa-ai
```

### Rolling Update
```bash
kubectl set image deployment/jira-qa-backend \
  backend=ghcr.io/your-org/jira-qa-ai:v1.2.0 -n jira-qa-ai
kubectl rollout undo deployment/jira-qa-backend -n jira-qa-ai  # Rollback
```

## Monitoring

### Health Checks
```bash
curl https://api.jira-qa.company.com/health
curl https://api.jira-qa.company.com/api/v1/health
```

### Alertes Recommandées
| Alerte | Condition | Sévérité |
|--------|-----------|----------|
| HighErrorRate | error_rate > 5% sur 5min | Critical |
| HighLatency | p99 > 10s sur 5min | Warning |
| DatabaseDown | pg_up = 0 | Critical |

## Scaling

### HPA Configuration
- Min: 2 pods, Max: 10 pods
- CPU target: 70%
- Memory target: 80%

## Backup

```bash
# Backup PostgreSQL
pg_dump -h localhost -U postgres -d jira_qa_ai > backup_$(date +%Y%m%d).sql
```

## Incident Response

### Rollback
```bash
kubectl rollout undo deployment/jira-qa-backend -n jira-qa-ai
```

### Rotation des Secrets
```bash
kubectl create secret generic jira-qa-secrets --from-literal=JWT_SECRET_KEY="new-key" --dry-run=client -o yaml | kubectl apply -f -
kubectl rollout restart deployment/jira-qa-backend -n jira-qa-ai
```
