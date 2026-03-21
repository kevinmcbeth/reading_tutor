# Reading Tutor — Hosted (AWS) Setup Guide

This guide walks through deploying the reading tutor to AWS using the included Terraform and Kubernetes configurations. The hosted version uses AWS-managed services for the database, cache, and CDN, with EKS for GPU workloads.

## Architecture Overview

```
                   ┌─────────────┐
                   │  CloudFront │
                   │    (CDN)    │
                   └──────┬──────┘
              ┌───────────┼───────────┐
              │           │           │
         /assets/*     /api/*       /*
              │           │           │
        ┌─────▼───┐  ┌────▼────┐  ┌──▼──────┐
        │ S3      │  │  ALB    │  │ S3      │
        │ Assets  │  │         │  │ Frontend│
        └─────────┘  └────┬────┘  └─────────┘
                          │
                   ┌──────▼──────┐
                   │ ECS Fargate │
                   │  API (x2)   │
                   │  Worker (x1)│
                   └──────┬──────┘
              ┌───────────┼───────────┐
              │           │           │
        ┌─────▼───┐  ┌───▼────┐  ┌──▼──────┐
        │ RDS     │  │ Redis  │  │  EKS    │
        │ Postgres│  │ (Elast │  │  GPU    │
        │         │  │  iCach)│  │  Nodes  │
        └─────────┘  └────────┘  └─────────┘
                                      │
                               ┌──────┴──────┐
                               │  ComfyUI    │
                               │  TTS Server │
                               └─────────────┘
```

| Service | AWS Resource | Size |
|---------|-------------|------|
| API | ECS Fargate | 0.5 vCPU / 1 GB (x2 tasks) |
| Worker | ECS Fargate Spot | 1 vCPU / 2 GB (x1 task) |
| Database | RDS PostgreSQL 16 | db.t4g.micro |
| Cache | ElastiCache Redis 7 | cache.t4g.micro |
| GPU (images) | EKS g5.xlarge spot | Scales 0–4 nodes |
| GPU (TTS) | EKS g5.xlarge spot | Shared with images |
| CDN | CloudFront | PriceClass_100 |
| Storage | S3 | Two buckets (assets + frontend) |
| LLM | AWS Bedrock | Claude 3.5 Haiku |

Estimated cost: ~$166/month for 10 users (GPU nodes scale to zero when idle).

## Prerequisites

- **AWS account** with permissions for VPC, ECS, EKS, RDS, ElastiCache, S3, CloudFront, ACM, Secrets Manager, Bedrock, and IAM
- **AWS CLI v2** configured (`aws configure`)
- **Terraform** >= 1.0
- **Docker** (for building container images)
- **kubectl** (for managing EKS GPU services)
- **A domain name** — either a DuckDNS subdomain or a custom domain

### Enable Bedrock model access

The hosted version uses AWS Bedrock for story generation instead of Ollama. You must enable model access before deploying:

1. Go to the [AWS Bedrock console](https://console.aws.amazon.com/bedrock/)
2. Navigate to **Model access** in the left sidebar
3. Request access to **Anthropic > Claude 3.5 Haiku**
4. Wait for approval (usually instant)

## Step 1: Configure Terraform Variables

```bash
cd deploy/terraform
cp terraform.tfvars.example terraform.tfvars
```

Edit `terraform.tfvars`:

```hcl
aws_region        = "us-east-1"
project_name      = "reading-tutor"
domain_name       = "reading-tutor.yourdomain.com"  # or reading-tutor.duckdns.org
db_instance_class = "db.t4g.micro"
redis_node_type   = "cache.t4g.micro"
eks_node_max      = 4
budget_limit      = "300"
```

| Variable | Description |
|----------|-------------|
| `aws_region` | AWS region (must support Bedrock and g5 instances) |
| `domain_name` | Your domain — CloudFront and ACM certs are tied to this |
| `db_instance_class` | RDS size — `db.t4g.micro` is sufficient for small deployments |
| `redis_node_type` | ElastiCache size — `cache.t4g.micro` handles the job queue fine |
| `eks_node_max` | Max GPU nodes Karpenter can spin up |
| `budget_limit` | Monthly spend alert threshold (USD) |

## Step 2: Deploy Infrastructure

```bash
cd deploy/terraform

# Initialize Terraform providers
terraform init

# Review the plan
terraform plan

# Apply (creates ~40 resources, takes 15–20 minutes)
terraform apply
```

Save the outputs — you'll need them for the next steps:

```bash
terraform output
```

Key outputs:
- `cloudfront_domain` — your CDN URL
- `ecr_api_url` / `ecr_worker_url` — container registry URLs
- `eks_cluster_name` — for kubectl configuration
- `s3_frontend_bucket` — for deploying the frontend
- `s3_assets_bucket` — for asset storage
- `efs_file_system_id` — for GPU model storage

## Step 3: Validate the SSL Certificate

Terraform creates an ACM certificate for your domain but DNS validation must be completed manually.

### For DuckDNS domains

DuckDNS does not support arbitrary DNS records, so you'll need to use an alternative validation method or switch to a custom domain with Route 53.

### For custom domains (Route 53 or other DNS)

1. Check the ACM console for the CNAME validation records
2. Add them to your DNS provider
3. Wait for validation (can take up to 30 minutes)
4. Point your domain to the CloudFront distribution domain from `terraform output cloudfront_domain`

## Step 4: Build and Push Container Images

Authenticate Docker with ECR:

```bash
AWS_ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(terraform output -raw aws_region 2>/dev/null || echo "us-east-1")

aws ecr get-login-password --region $AWS_REGION | \
  docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com
```

Build and push the API and worker images from the project root:

```bash
cd /path/to/reading_tutor

# API image
ECR_API=$(cd deploy/terraform && terraform output -raw ecr_api_url)
docker build -t $ECR_API:latest -f Dockerfile .
docker push $ECR_API:latest

# Worker image
ECR_WORKER=$(cd deploy/terraform && terraform output -raw ecr_worker_url)
docker build -t $ECR_WORKER:latest -f Dockerfile.worker .
docker push $ECR_WORKER:latest
```

Force a new deployment so ECS picks up the images:

```bash
CLUSTER="reading-tutor-cluster"
aws ecs update-service --cluster $CLUSTER --service reading-tutor-api --force-new-deployment
aws ecs update-service --cluster $CLUSTER --service reading-tutor-worker --force-new-deployment
```

## Step 5: Deploy the Frontend

Build the frontend and upload to S3:

```bash
cd frontend

# Set the API base URL to your domain
echo "VITE_API_URL=https://your-domain.com" > .env.production

npm install
npm run build

# Upload to S3
S3_FRONTEND=$(cd ../deploy/terraform && terraform output -raw s3_frontend_bucket)
aws s3 sync dist/ s3://$S3_FRONTEND/ --delete

# Invalidate CloudFront cache
CF_DIST_ID=$(aws cloudfront list-distributions \
  --query "DistributionList.Items[?contains(Aliases.Items, 'your-domain.com')].Id" \
  --output text)
aws cloudfront create-invalidation --distribution-id $CF_DIST_ID --paths "/*"
```

## Step 6: Deploy GPU Services to EKS

### Configure kubectl

```bash
EKS_CLUSTER=$(cd deploy/terraform && terraform output -raw eks_cluster_name)
aws eks update-kubeconfig --name $EKS_CLUSTER --region us-east-1
```

### Build and push GPU service images

```bash
# ComfyUI
cd gpu-services/comfyui
docker build -t $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/reading-tutor-comfyui:latest .
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/reading-tutor-comfyui:latest

# TTS Server
cd ../tts-server
docker build -t $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/reading-tutor-tts:latest .
docker push $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/reading-tutor-tts:latest
```

### Upload models to EFS

The GPU services load models from EFS. You'll need to upload the required model files:

- **ComfyUI**: `DreamShaperXL_Turbo_v2_1.safetensors` → `/models/` on EFS
- **TTS**: `reference_voice.wav` → `/models/` on EFS

One approach is to create a temporary pod that mounts the EFS volume, then `kubectl cp` the files in.

### Apply Kubernetes manifests

Edit the manifests to replace placeholder values:

```bash
cd deploy/k8s

# Update image references in the deployment files
sed -i "s|REPLACE_WITH_COMFYUI_IMAGE|$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/reading-tutor-comfyui:latest|" comfyui-deployment.yaml
sed -i "s|REPLACE_WITH_TTS_IMAGE|$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/reading-tutor-tts:latest|" tts-deployment.yaml

# Update Karpenter node class with your role and security group names
# (get these from terraform output or the AWS console)
sed -i "s|REPLACE_WITH_KARPENTER_NODE_ROLE_NAME|reading-tutor-karpenter-node|" karpenter-nodepool.yaml
sed -i "s|REPLACE_WITH_EKS_NODES_SG_NAME|reading-tutor-eks-nodes|" karpenter-nodepool.yaml

# Update the EFS file system ID
EFS_ID=$(cd ../terraform && terraform output -raw efs_file_system_id)
sed -i "s|REPLACE_WITH_EFS_ID|$EFS_ID|" efs-pv.yaml
```

Apply everything:

```bash
kubectl apply -f namespace.yaml
kubectl apply -f efs-pv.yaml
kubectl apply -f karpenter-nodepool.yaml
kubectl apply -f comfyui-deployment.yaml
kubectl apply -f comfyui-service.yaml
kubectl apply -f tts-deployment.yaml
kubectl apply -f tts-service.yaml
```

Verify the GPU pods are running:

```bash
kubectl get pods -n gpu
kubectl logs -n gpu deployment/comfyui
kubectl logs -n gpu deployment/tts
```

GPU nodes are provisioned on-demand by Karpenter — expect a 2–5 minute wait on first deployment while a g5 spot instance launches.

## Step 7: Verify the Deployment

### Check ECS services

```bash
aws ecs describe-services --cluster reading-tutor-cluster \
  --services reading-tutor-api reading-tutor-worker \
  --query "services[*].{name:serviceName,status:status,running:runningCount,desired:desiredCount}"
```

### Check the API health

```bash
curl https://your-domain.com/api/health
```

### Check CloudWatch logs

```bash
# API logs
aws logs tail /ecs/reading-tutor-api --follow

# Worker logs
aws logs tail /ecs/reading-tutor-worker --follow
```

### Visit the app

Open `https://your-domain.com` in a browser. You should see the reading tutor login page.

## Updating the Deployment

### Backend changes (API or worker)

Rebuild and push the Docker images, then force a new ECS deployment:

```bash
# From project root
docker build -t $ECR_API:latest -f Dockerfile .
docker push $ECR_API:latest
aws ecs update-service --cluster reading-tutor-cluster --service reading-tutor-api --force-new-deployment

docker build -t $ECR_WORKER:latest -f Dockerfile.worker .
docker push $ECR_WORKER:latest
aws ecs update-service --cluster reading-tutor-cluster --service reading-tutor-worker --force-new-deployment
```

### Frontend changes

```bash
cd frontend
npm run build
aws s3 sync dist/ s3://$S3_FRONTEND/ --delete
aws cloudfront create-invalidation --distribution-id $CF_DIST_ID --paths "/*"
```

### Infrastructure changes

```bash
cd deploy/terraform
terraform plan   # Review changes
terraform apply  # Apply changes
```

## Cost Optimization Details

The Terraform configuration includes several cost-saving measures:

- **No NAT gateway** — ECS tasks run in public subnets with public IPs (saves ~$35/month)
- **Fargate Spot** for the worker — background jobs tolerate interruption (saves ~$31/month)
- **t4g.micro instances** for RDS and ElastiCache — ARM-based, cheapest tier
- **Karpenter scale-to-zero** — GPU nodes shut down after 5 minutes of inactivity
- **g5.xlarge spot instances** — ~60% cheaper than on-demand GPU
- **S3 VPC Gateway Endpoint** — free data transfer between ECS and S3
- **CloudFront PriceClass_100** — US/Europe edge locations only
- **Budget alert** at $300/month (configurable)

## Tearing Down

To remove all AWS resources:

```bash
# Empty S3 buckets first (required before Terraform can delete them)
aws s3 rm s3://$(terraform output -raw s3_assets_bucket) --recursive
aws s3 rm s3://$(terraform output -raw s3_frontend_bucket) --recursive

# Remove K8s resources
kubectl delete -f deploy/k8s/

# Destroy infrastructure
cd deploy/terraform
terraform destroy
```

## Troubleshooting

### ECS tasks keep restarting

Check the CloudWatch logs for the failing service:

```bash
aws logs tail /ecs/reading-tutor-api --since 30m
```

Common causes:
- Database not ready yet (RDS can take 5–10 minutes to provision)
- Missing environment variables
- ECR image not pushed

### GPU pods stuck in Pending

Karpenter needs to provision a spot instance. Check Karpenter logs:

```bash
kubectl logs -n karpenter -l app.kubernetes.io/name=karpenter
```

If spot capacity is unavailable in your region, edit `karpenter-nodepool.yaml` to allow `on-demand` instances or try a different AZ.

### ACM certificate stuck validating

Ensure the DNS CNAME records are correctly set. For DuckDNS, you may need to use a custom domain with Route 53 instead, as DuckDNS has limited DNS record support.

### Story generation jobs not completing

1. Verify the worker is running: `aws ecs describe-services --cluster reading-tutor-cluster --services reading-tutor-worker`
2. Check worker logs: `aws logs tail /ecs/reading-tutor-worker --follow`
3. Verify GPU services are reachable from the worker (they communicate via Kubernetes internal DNS: `comfyui.gpu.svc.cluster.local:8188` and `tts.gpu.svc.cluster.local:8080`)
4. Confirm Bedrock model access is enabled in the AWS console
