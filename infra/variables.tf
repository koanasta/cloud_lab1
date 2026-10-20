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


variable "github_oidc_sub_prefix" {
  description = "Префікс sub з OIDC-токена GitHub для цього репозиторію"
  type        = string
}

variable "image_tag" {
  description = "Тег образу для першого запуску; далі образ оновлює CI"
  type        = string
  default     = "bootstrap"
}

variable "alert_email" {
  description = "Пошта, куди CloudWatch надсилатиме алерти"
  type        = string
}
