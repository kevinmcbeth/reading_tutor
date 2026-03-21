# Changelog

All notable changes to this project will be automatically documented here.

## [Unreleased]

### CI/CD

- add git-cliff changelog generation on push to main

### Documentation

- update changelog [skip ci] by @github-actions[bot]

### Features

- add F&P Guided Reading levelled story generation script

## [Unreleased] — 2026-03-21

### AWS Cloud Migration

Migrate from single-machine deployment to AWS. All services are dual-mode — local dev continues to work unchanged via env vars.

#### Application Code

**New services:**
- `backend/services/bedrock_client.py` — Amazon Bedrock client for Claude Haiku text generation with exponential backoff on throttling
- `backend/services/storage_service.py` — Dual-mode storage abstraction (`save_file`, `get_url`, `file_exists`) supporting local filesystem and S3
- `backend/services/tts_client.py` — HTTP client for remote F5-TTS microservice on EKS

**Modified:**
- `backend/config.py` — Added AWS settings: `LLM_BACKEND` (ollama/bedrock), `STORAGE_BACKEND` (local/s3), `TTS_BACKEND` (local/remote), `BEDROCK_MODEL_ID`, `AWS_REGION`, `S3_BUCKET`, `CLOUDFRONT_DOMAIN`, `TTS_URL`
- `backend/services/story_pipeline.py` — Pipeline now selects LLM backend at runtime, uploads assets to S3 in cloud mode, calls remote TTS service. GPU management (systemctl, Ollama model swapping) only runs in local mode
- `backend/endpoints/assets.py` — Returns 302 redirects to CloudFront URLs in S3 mode; serves files locally otherwise
- `backend/requirements.txt` — Added `boto3`

#### Containerization

- `Dockerfile` — API container (python:3.11-slim, uvicorn with 2 workers)
- `Dockerfile.worker` — arq worker container
- `gpu-services/comfyui/Dockerfile` — CUDA 12.1 + ComfyUI with EFS model mount
- `gpu-services/tts-server/` — FastAPI microservice wrapping F5-TTS (Dockerfile + main.py)

#### Terraform Infrastructure (`deploy/terraform/`)

| File | Resources |
|---|---|
| `networking.tf` | VPC (10.0.0.0/16), 2 AZs, public + DB subnets, no NAT gateway, S3 VPC endpoint, 5 security groups |
| `database.tf` | RDS PostgreSQL 16 (db.t4g.micro, single-AZ), ElastiCache Redis (cache.t4g.micro), Secrets Manager |
| `ecs.tf` | ECR repos, Fargate cluster, API service (2 tasks, 0.5 vCPU/1GB), Worker (Fargate Spot, 1 vCPU/2GB), ALB with HTTPS |
| `storage.tf` | S3 buckets (assets + frontend), CloudFront (3 origins: frontend, assets, API), ACM certificate |
| `eks.tf` | EKS 1.29, Karpenter (scale 0→N, 5-min consolidation), NVIDIA device plugin, EFS (10GB) + CSI driver, IRSA |
| `monitoring.tf` | AWS Budgets alert at $300/mo |
| `variables.tf` | Region, domain, instance sizes, budget threshold |
| `outputs.tf` | CloudFront domain, ALB DNS, RDS/Redis endpoints, EKS cluster name, ECR URLs |

#### Kubernetes Manifests (`deploy/k8s/`)

- `namespace.yaml` — `gpu` namespace
- `efs-pv.yaml` — EFS PersistentVolume + PVC + StorageClass
- `comfyui-deployment.yaml` / `comfyui-service.yaml` — ComfyUI GPU pod (ClusterIP :8188)
- `tts-deployment.yaml` / `tts-service.yaml` — TTS GPU pod (ClusterIP :8080)
- `karpenter-nodepool.yaml` — g5.xlarge spot instances, GPU taint, max 4 nodes

#### Cost Optimizations (10-user tier, ~$166/mo)

- No NAT gateway (public subnets + security groups) — saves $35/mo
- Fargate Spot for worker — saves ~$31/mo
- db.t4g.micro instead of t4g.small — saves $13/mo
- Karpenter scale-to-zero — GPU nodes cost $0 when idle
- g5.xlarge spot — 60% cheaper than on-demand
- S3 VPC Gateway Endpoint — free data transfer to S3

#### Backward Compatibility

Local development is fully preserved. Default config values match the existing single-machine setup:
```
LLM_BACKEND=ollama
STORAGE_BACKEND=local
TTS_BACKEND=local
```
