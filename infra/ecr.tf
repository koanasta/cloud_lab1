resource "aws_ecr_repository" "app" {
  name                 = var.project
  image_tag_mutability = "IMMUTABLE" 
  force_delete         = true        

  image_scanning_configuration {
    scan_on_push = true
  }
}
