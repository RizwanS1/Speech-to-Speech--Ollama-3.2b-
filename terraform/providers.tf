terraform {
  required_version = ">= 1.5.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0, < 6.0"
    }
  }
}

provider "aws" {
  region                      = var.aws_region
  access_key                  = "test"
  secret_key                  = "test"
  skip_credentials_validation = true
  skip_metadata_api_check     = true
  skip_requesting_account_id  = true
  s3_use_path_style           = true

  endpoints {
    s3          = var.floci_endpoint
    rds         = var.floci_endpoint
    elasticache = var.floci_endpoint
    ecr         = var.floci_endpoint
    ecs         = var.floci_endpoint
    iam         = var.floci_endpoint
    ec2         = var.floci_endpoint
    logs        = var.floci_endpoint
  }
}
