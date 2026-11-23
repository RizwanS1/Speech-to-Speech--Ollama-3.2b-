variable "floci_endpoint" {
  description = "Base endpoint for the local Floci AWS emulator."
  type        = string
  default     = "http://localhost:4566"
}

variable "aws_region" {
  description = "AWS region used by Floci resources."
  type        = string
  default     = "us-east-1"
}

variable "frontend_bucket" {
  description = "S3 bucket name for the frontend."
  type        = string
  default     = "speech-frontend"
}

variable "database_name" {
  description = "PostgreSQL database name."
  type        = string
  default     = "speech"
}

variable "database_password" {
  description = "Password for the Floci PostgreSQL instance."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.database_password) >= 12
    error_message = "database_password must be at least 12 characters."
  }
}

variable "jwt_secret_key" {
  description = "JWT signing secret used by the FastAPI container."
  type        = string
  sensitive   = true

  validation {
    condition     = length(var.jwt_secret_key) >= 32
    error_message = "jwt_secret_key must be at least 32 characters."
  }
}

variable "backend_image_tag" {
  description = "Tag for the backend image stored in Floci ECR."
  type        = string
  default     = "latest"
}

variable "redis_container_ip" {
  description = "Docker bridge IP of Floci's ElastiCache container, resolved by deploy_floci.ps1."
  type        = string
  default     = ""
}

variable "ollama_url" {
  description = "URL used by the ECS task to reach Ollama on the Windows host."
  type        = string
  default     = "http://host.docker.internal:11434"
}

variable "ollama_model" {
  description = "Model name exposed by the native Ollama server."
  type        = string
  default     = "llama3.2"

  validation {
    condition     = length(trimspace(var.ollama_model)) > 0
    error_message = "ollama_model must not be empty."
  }
}
