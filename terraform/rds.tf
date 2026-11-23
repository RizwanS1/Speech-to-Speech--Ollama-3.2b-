resource "aws_db_subnet_group" "speech" {
  name       = "speech-db-subnets"
  subnet_ids = [aws_subnet.public_a.id, aws_subnet.public_b.id]
}

resource "aws_db_instance" "postgres" {
  identifier             = "speech-postgres"
  allocated_storage      = 20
  engine                 = "postgres"
  engine_version         = "16"
  instance_class         = "db.t3.micro"
  db_name                = var.database_name
  username               = "speech"
  password               = var.database_password
  db_subnet_group_name   = aws_db_subnet_group.speech.name
  vpc_security_group_ids = [aws_security_group.speech.id]
  publicly_accessible    = true
  skip_final_snapshot    = true
  deletion_protection    = false
  apply_immediately      = true
}
