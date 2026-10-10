resource "aws_ecr_repository" "app" {
  name                 = var.project
  image_tag_mutability = "IMMUTABLE" # тег не можна перезаписати: хеш коміту = один образ
  force_delete         = true        # дозволяє destroy, навіть якщо в репо є образи

  image_scanning_configuration {
    scan_on_push = true # AWS перевіряє образ на відомі вразливості
  }
}
