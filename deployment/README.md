# Bank Marketing Prediction API - Deployment Guide

## Overview
This directory contains deployment artifacts for the Bank Marketing Term Deposit Prediction API, including:
- FastAPI application
- Docker containerization
- Monitoring setup (Prometheus + Grafana)
- CI/CD configuration
- Kubernetes manifests (optional)

---

## Quick Start

### Local Development

1. **Install dependencies**:
```bash
pip install -r requirements.txt
```

2. **Run the API**:
```bash
python app.py
```

3. **Access the API**:
- API: http://localhost:8000
- Docs: http://localhost:8000/docs
- Health: http://localhost:8000/health

### Docker Deployment

1. **Build the image**:
```bash
docker build -t bank-marketing-api:latest .
```

2. **Run the container**:
```bash
docker run -d \
  -p 8000:8000 \
  -v $(pwd)/../models:/app/models:ro \
  --name bank-api \
  bank-marketing-api:latest
```

3. **Check logs**:
```bash
docker logs -f bank-api
```

### Docker Compose (Full Stack)

1. **Start all services**:
```bash
docker-compose up -d
```

2. **Access services**:
- API: http://localhost:8000
- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000 (admin/admin)

3. **Stop services**:
```bash
docker-compose down
```

---

## API Endpoints

### 1. Root
- **URL**: `GET /`
- **Description**: API information and available endpoints

### 2. Health Check
- **URL**: `GET /health`
- **Description**: Health status of the API
- **Response**:
```json
{
  "status": "healthy",
  "timestamp": "2025-01-01T12:00:00",
  "models": {
    "xgboost": "loaded",
    "lightgbm": "loaded"
  }
}
```

### 3. List Models
- **URL**: `GET /models`
- **Description**: List available models
- **Response**:
```json
{
  "available_models": ["xgboost", "lightgbm", "random_forest"],
  "default_model": "xgboost"
}
```

### 4. Single Prediction
- **URL**: `POST /predict`
- **Query Params**: `model_name` (optional, default: xgboost)
- **Request Body**:
```json
{
  "age": 45,
  "job": "management",
  "marital": "married",
  "education": "tertiary",
  "default": "no",
  "balance": 2500.0,
  "housing": "yes",
  "loan": "no",
  "contact": "cellular",
  "day": 15,
  "month": "may",
  "duration": 300,
  "campaign": 2,
  "pdays": 999,
  "previous": 0,
  "poutcome": "unknown"
}
```
- **Response**:
```json
{
  "prediction": "yes",
  "probability": 0.72,
  "model": "xgboost",
  "timestamp": "2025-01-01T12:00:00",
  "version": "1.0.0"
}
```

### 5. Batch Prediction
- **URL**: `POST /batch_predict`
- **Query Params**: `model_name` (optional)
- **Request Body**:
```json
{
  "instances": [
    { /* instance 1 */ },
    { /* instance 2 */ }
  ]
}
```

### 6. Metrics
- **URL**: `GET /metrics`
- **Description**: Prometheus metrics for monitoring

---

## Monitoring

### Prometheus Metrics

The API exposes the following metrics:

1. **predictions_total**: Total number of predictions
   - Labels: `model_name`, `prediction`

2. **prediction_latency_seconds**: Prediction latency histogram
   - Labels: `model_name`

3. **prediction_errors_total**: Total prediction errors
   - Labels: `error_type`

### Accessing Metrics

- **Prometheus UI**: http://localhost:9090
  - Query examples:
    - `rate(predictions_total[5m])` - Prediction rate
    - `histogram_quantile(0.95, prediction_latency_seconds)` - P95 latency

- **Grafana UI**: http://localhost:3000
  - Default credentials: admin/admin
  - Import dashboard from `grafana/dashboards/`

---

## Production Deployment

### Kubernetes Deployment

1. **Create namespace**:
```bash
kubectl create namespace bank-marketing
```

2. **Deploy application**:
```bash
kubectl apply -f k8s/ -n bank-marketing
```

3. **Check status**:
```bash
kubectl get pods -n bank-marketing
kubectl get svc -n bank-marketing
```

4. **Access API**:
```bash
kubectl port-forward svc/bank-marketing-api 8000:80 -n bank-marketing
```

### AWS Deployment (ECS/EKS)

#### Using ECS:

1. **Push image to ECR**:
```bash
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.us-east-1.amazonaws.com
docker tag bank-marketing-api:latest <account-id>.dkr.ecr.us-east-1.amazonaws.com/bank-marketing-api:latest
docker push <account-id>.dkr.ecr.us-east-1.amazonaws.com/bank-marketing-api:latest
```

2. **Create ECS task definition**:
- Use `aws/ecs-task-definition.json`

3. **Create ECS service**:
```bash
aws ecs create-service \
  --cluster bank-marketing-cluster \
  --service-name bank-marketing-api \
  --task-definition bank-marketing-api:1 \
  --desired-count 2 \
  --launch-type FARGATE
```

### Azure Deployment (AKS)

1. **Push to ACR**:
```bash
az acr login --name <registry-name>
docker tag bank-marketing-api:latest <registry-name>.azurecr.io/bank-marketing-api:latest
docker push <registry-name>.azurecr.io/bank-marketing-api:latest
```

2. **Deploy to AKS**:
```bash
kubectl apply -f k8s/ -n bank-marketing
```

---

## CI/CD Pipeline

### GitHub Actions

The repository includes a GitHub Actions workflow (`.github/workflows/deploy.yml`) that:
1. Runs tests on pull requests
2. Builds Docker image on merge to main
3. Pushes to container registry
4. Deploys to staging/production

### Workflow Triggers:
- **Pull Request**: Run tests and linting
- **Push to main**: Build and deploy to staging
- **Release tag**: Deploy to production

### Required Secrets:
- `DOCKER_USERNAME`: Docker Hub username
- `DOCKER_PASSWORD`: Docker Hub password
- `AWS_ACCESS_KEY_ID`: AWS access key
- `AWS_SECRET_ACCESS_KEY`: AWS secret key
- `KUBE_CONFIG`: Kubernetes config (base64 encoded)

---

## Model Versioning

### Strategy
- **Semantic versioning**: MAJOR.MINOR.PATCH
- **Model registry**: MLflow or DVC for model versioning
- **A/B testing**: Deploy multiple model versions simultaneously

### Model Update Process

1. **Train new model**:
```bash
python scripts/train.py --config config/model_xgb.yaml
```

2. **Evaluate new model**:
```bash
python scripts/evaluate.py --model-path models/xgboost_v2.pkl
```

3. **Register in MLflow**:
```python
import mlflow
mlflow.log_model(model, "xgboost_v2")
```

4. **Update deployment**:
```bash
# Update model path in deployment
kubectl set image deployment/bank-marketing-api \
  api=bank-marketing-api:v2 -n bank-marketing
```

5. **Monitor performance**:
- Check prediction metrics
- Compare with previous version
- Rollback if needed

---

## Monitoring and Alerting

### Key Metrics to Monitor

1. **Application Metrics**:
   - Prediction throughput (requests/sec)
   - Prediction latency (P50, P95, P99)
   - Error rate
   - Model version distribution

2. **Infrastructure Metrics**:
   - CPU utilization
   - Memory usage
   - Network I/O
   - Disk usage

3. **Business Metrics**:
   - Prediction distribution (yes/no ratio)
   - Average probability scores
   - Model confidence

### Alert Rules

Example Prometheus alerts (`monitoring/alerts.yml`):

```yaml
groups:
  - name: prediction_api_alerts
    rules:
      - alert: HighErrorRate
        expr: rate(prediction_errors_total[5m]) > 0.05
        for: 5m
        annotations:
          summary: "High error rate detected"
          
      - alert: HighLatency
        expr: histogram_quantile(0.95, prediction_latency_seconds) > 1.0
        for: 5m
        annotations:
          summary: "High prediction latency"
```

---

## Model Drift Detection

### Monitoring Strategy

1. **Input Data Drift**:
   - Monitor feature distributions
   - Compare with training data
   - Alert on significant changes

2. **Prediction Drift**:
   - Track prediction distribution
   - Monitor average probabilities
   - Compare across time periods

3. **Performance Drift**:
   - Track actual outcomes (when available)
   - Calculate online metrics
   - Compare with offline validation

### Implementation

See `monitoring/drift_detector.py` for implementation example.

---

## Scaling Considerations

### Horizontal Scaling

**Kubernetes**:
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: bank-marketing-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: bank-marketing-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 70
```

### Load Balancing

- **AWS**: Application Load Balancer (ALB)
- **Azure**: Azure Load Balancer
- **Kubernetes**: Service with LoadBalancer type

### Caching

Consider Redis for caching:
- Frequent predictions
- Model metadata
- Feature engineering results

---

## Security

### Best Practices

1. **API Security**:
   - Add authentication (JWT, OAuth)
   - Rate limiting
   - Input validation
   - HTTPS only

2. **Container Security**:
   - Non-root user
   - Minimal base image
   - No secrets in image
   - Regular security scans

3. **Network Security**:
   - Network policies in K8s
   - VPC/Subnet isolation
   - Security groups
   - WAF for public endpoints

### Example: Add API Key Authentication

```python
from fastapi import Security, HTTPException
from fastapi.security import APIKeyHeader

API_KEY = os.getenv("API_KEY")
api_key_header = APIKeyHeader(name="X-API-Key")

async def verify_api_key(api_key: str = Security(api_key_header)):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API Key")
    return api_key
```

---

## Troubleshooting

### Common Issues

**1. Models not loading**:
```bash
# Check models directory
ls -la /app/models

# Check file permissions
chmod -R 755 models/

# Check logs
docker logs bank-api
```

**2. High memory usage**:
- Reduce batch size
- Use model compression
- Increase memory limits

**3. Slow predictions**:
- Check model complexity
- Enable model optimization
- Use GPU if available
- Implement caching

**4. Connection refused**:
```bash
# Check if service is running
docker ps

# Check port mapping
docker port bank-api

# Check firewall rules
```

---

## Performance Optimization

### Tips

1. **Model Optimization**:
   - Use ONNX runtime
   - Quantization
   - Pruning

2. **Application Optimization**:
   - Async processing
   - Connection pooling
   - Batch predictions

3. **Infrastructure**:
   - Use CDN for static assets
   - Enable caching
   - Optimize container image size

---

## Support and Contact

- **Technical Issues**: Open GitHub issue
- **Security Issues**: Contact security@bank.com
- **Feature Requests**: GitHub discussions

---

## License

MIT License - See LICENSE file for details

---

## Changelog

### Version 1.0.0 (2025-01-01)
- Initial production release
- XGBoost, LightGBM, Random Forest models
- Prometheus monitoring
- Docker deployment
- API documentation

---

**Last Updated**: 2025-01-01  
**Maintainers**: ML Team  
**Documentation Version**: 1.0.0
