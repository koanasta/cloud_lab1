# RDS вимагає підмережі мінімум у двох зонах — даємо обидві приватні
resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-db"
  subnet_ids = aws_subnet.private[*].id
}

resource "aws_db_instance" "main" {
  identifier        = "${var.project}-db"
  engine            = "postgres"
  engine_version    = "16"
  instance_class    = "db.t4g.micro" # найменший, входить у Free Tier
  allocated_storage = 20

  db_name  = "notes"
  username = "notes"
  # Пароль генерує AWS і кладе в Secrets Manager. Його немає ні в коді, ні в tfvars
  manage_master_user_password = true

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.db.id]
  publicly_accessible    = false # жодної публічної адреси

  multi_az                = false # навчальний проєкт, економимо
  backup_retention_period = 1     # бекапи увімкнені → є point-in-time recovery
  skip_final_snapshot     = true  # щоб destroy не залишав знімок, який коштує грошей
  deletion_protection     = false
}
