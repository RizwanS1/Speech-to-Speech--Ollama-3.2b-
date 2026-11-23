module "frontend" {
  source = "./floci"

  providers = {
    aws = aws
  }

  s3_endpoint = var.floci_endpoint
  bucket_name = var.frontend_bucket
  aws_region  = var.aws_region
}
