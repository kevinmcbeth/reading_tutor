variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Project name used for resource naming"
  type        = string
  default     = "reading-tutor"
}

variable "domain_name" {
  description = "Domain name for the application (e.g. reading-tutor.duckdns.org)"
  type        = string
}

variable "db_instance_class" {
  description = "RDS instance class"
  type        = string
  default     = "db.t4g.micro"
}

variable "redis_node_type" {
  description = "ElastiCache node type"
  type        = string
  default     = "cache.t4g.micro"
}

variable "eks_node_max" {
  description = "Maximum number of EKS GPU nodes"
  type        = number
  default     = 4
}

variable "budget_limit" {
  description = "Monthly budget alert threshold in USD"
  type        = string
  default     = "300"
}

variable "api_image" {
  description = "ECR image URI for the API service"
  type        = string
  default     = ""
}

variable "worker_image" {
  description = "ECR image URI for the worker service"
  type        = string
  default     = ""
}
