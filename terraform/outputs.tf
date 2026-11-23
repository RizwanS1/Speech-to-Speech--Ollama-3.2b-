output "frontend_url" {
  description = "Floci S3 static frontend URL."
  value       = module.frontend.frontend_url
}

output "backend_url" {
  description = "Local reverse proxy to the Floci ECS FastAPI task."
  value       = "http://127.0.0.1:8001"
}

output "rds_endpoint" {
  description = "Floci PostgreSQL endpoint."
  value       = aws_db_instance.postgres.endpoint
}

output "elasticache_endpoint" {
  description = "Floci Redis endpoint."
  value       = "${var.redis_container_ip != "" ? var.redis_container_ip : aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.port}"
}

output "ecr_repository_url" {
  description = "Floci ECR repository URL for the FastAPI image."
  value       = aws_ecr_repository.speech_backend.repository_url
}

output "ecr_docker_push_url" {
  description = "Local Docker registry URL used to push images into Floci."
  value       = "localhost:5100/speech-backend"
}
