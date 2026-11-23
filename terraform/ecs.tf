resource "aws_vpc" "speech" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "speech-vpc"
  }
}

resource "aws_internet_gateway" "speech" {
  vpc_id = aws_vpc.speech.id
}

resource "aws_subnet" "public_a" {
  vpc_id                  = aws_vpc.speech.id
  cidr_block              = "10.42.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true
}

resource "aws_subnet" "public_b" {
  vpc_id                  = aws_vpc.speech.id
  cidr_block              = "10.42.2.0/24"
  availability_zone       = "${var.aws_region}b"
  map_public_ip_on_launch = true
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.speech.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.speech.id
  }
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.public_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.public_b.id
  route_table_id = aws_route_table.public.id
}

resource "aws_security_group" "speech" {
  name        = "speech-stack"
  description = "Local Floci speech backend and data services"
  vpc_id      = aws_vpc.speech.id

  ingress {
    description = "FastAPI"
    from_port   = 8000
    to_port     = 8000
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "PostgreSQL within the VPC"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.speech.cidr_block]
  }

  ingress {
    description = "Redis within the VPC"
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.speech.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_cloudwatch_log_group" "speech_backend" {
  name              = "/ecs/speech-backend"
  retention_in_days = 7
}

resource "aws_iam_role" "ecs_task_execution" {
  name = "speech-backend-task-execution"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_ecr_repository" "speech_backend" {
  name                 = "speech-backend"
  image_tag_mutability = "MUTABLE"
}

resource "aws_ecs_cluster" "speech" {
  name = "speech-cluster"
}

resource "aws_ecs_task_definition" "speech_backend" {
  family                   = "speech-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn

  container_definitions = jsonencode([
    {
      name      = "speech-backend"
      image     = "localhost:5100/${aws_ecr_repository.speech_backend.name}:${var.backend_image_tag}"
      essential = true
      portMappings = [{
        containerPort = 8000
        hostPort      = 8000
        protocol      = "tcp"
      }]
      environment = [
        {
          name  = "DATABASE_URL"
          value = "postgresql+asyncpg://speech:${urlencode(var.database_password)}@${aws_db_instance.postgres.endpoint}/${var.database_name}"
        },
        {
          name  = "REDIS_URL"
          value = "redis://${var.redis_container_ip != "" ? var.redis_container_ip : aws_elasticache_cluster.redis.cache_nodes[0].address}:${aws_elasticache_cluster.redis.port}/0"
        },
        {
          name  = "OLLAMA_URL"
          value = var.ollama_url
        },
        {
          name  = "OLLAMA_MODEL"
          value = var.ollama_model
        },
        {
          name  = "CORS_ORIGINS"
          value = "${var.floci_endpoint},http://127.0.0.1:4566"
        },
        {
          name  = "JWT_SECRET_KEY"
          value = var.jwt_secret_key
        },
        {
          name  = "JWT_ALGORITHM"
          value = "HS256"
        },
        {
          name  = "ACCESS_TOKEN_EXPIRE_MINUTES"
          value = "30"
        },
        {
          name  = "VOSK_MODEL_PATH"
          value = "/app/models/vosk-model-small-en-us-0.15"
        }
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.speech_backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "backend"
        }
      }
      healthCheck = {
        command     = ["CMD-SHELL", "curl -fsS http://localhost:8000/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])
}

resource "aws_ecs_service" "speech_backend" {
  name            = "speech-backend"
  cluster         = aws_ecs_cluster.speech.id
  task_definition = aws_ecs_task_definition.speech_backend.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = [aws_subnet.public_a.id, aws_subnet.public_b.id]
    security_groups  = [aws_security_group.speech.id]
    assign_public_ip = true
  }

  depends_on = [
    aws_iam_role_policy_attachment.ecs_task_execution,
    aws_route_table_association.public_a,
    aws_route_table_association.public_b,
  ]
}
