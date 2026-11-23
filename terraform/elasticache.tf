resource "aws_elasticache_subnet_group" "speech" {
  name       = "speech-redis-subnets"
  subnet_ids = [aws_subnet.public_a.id, aws_subnet.public_b.id]
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id         = "speech-redis"
  engine             = "redis"
  node_type          = "cache.t3.micro"
  num_cache_nodes    = 1
  port               = 6379
  subnet_group_name  = aws_elasticache_subnet_group.speech.name
  security_group_ids = [aws_security_group.speech.id]
}
