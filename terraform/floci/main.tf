terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = ">= 5.0, < 6.0"
    }
  }
}

locals {
  static_directory = "${path.module}/../../assistant/server/static"
  static_files     = fileset(local.static_directory, "**")
  content_types = {
    ".css"  = "text/css"
    ".html" = "text/html"
    ".ico"  = "image/x-icon"
    ".js"   = "application/javascript"
    ".json" = "application/json"
    ".svg"  = "image/svg+xml"
    ".txt"  = "text/plain"
  }
  uncached_files = toset(["index.html", "config.js"])
}

resource "aws_s3_bucket" "frontend" {
  bucket = var.bucket_name
}

resource "aws_s3_bucket_website_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  index_document {
    suffix = "index.html"
  }
}

resource "aws_s3_object" "frontend_files" {
  for_each = local.static_files

  bucket        = aws_s3_bucket.frontend.id
  key           = each.value
  source        = "${local.static_directory}/${each.value}"
  etag          = filemd5("${local.static_directory}/${each.value}")
  content_type  = lookup(local.content_types, lower(regex("\\.[^.]+$", each.value)), "application/octet-stream")
  cache_control = contains(local.uncached_files, each.value) ? "no-cache, no-store, must-revalidate" : null
}
