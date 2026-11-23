output "frontend_url" {
  description = "Floci URL for the hosted frontend."
  value       = "${var.s3_endpoint}/${var.bucket_name}/index.html"
}
