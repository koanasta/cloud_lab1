terraform {
  required_version = ">= 1.6"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.80"
    }
  }
}

provider "aws" {
  region = var.region
  # цей тег додасться до всіх ресурсів — легко знайти в консолі
  default_tags {
    tags = { Project = "cloud-lab1" }
  }
}
