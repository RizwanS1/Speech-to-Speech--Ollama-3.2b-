variable "s3_endpoint" {
  description = "Floci S3 API endpoint."
  type        = string
  default     = "http://localhost:4566"
}

variable "bucket_name" {
  description = "Name of the S3 bucket that hosts the frontend."
  type        = string
  default     = "speech-frontend"
}

variable "aws_region" {
  description = "AWS region required by the provider; Floci ignores it for local S3."
  type        = string
  default     = "us-east-1"
}
