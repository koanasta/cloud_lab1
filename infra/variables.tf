variable "region" {
  type    = string
  default = "eu-central-1"
}

variable "project" {
  description = "Префікс для імен усіх ресурсів"
  type        = string
  default     = "notes"
}

variable "github_repo" {
  description = "Репозиторій у форматі логін/назва, якому дозволено деплоїти"
  type        = string
}

variable "image_tag" {
  description = "Тег образу для першого запуску; далі образ оновлює CI"
  type        = string
  default     = "bootstrap"
}
