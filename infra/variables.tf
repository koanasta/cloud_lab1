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

variable "cache_enabled" {
  description = "Чи вмикати кеш Redis для GET /notes"
  type        = bool
  default     = true
}

variable "cache_ttl" {
  description = "Термін дії запису в кеші, секунди"
  type        = number
  default     = 30
}

variable "min_instances" {
  description = "Мінімальна кількість копій застосунку"
  type        = number
  default     = 1
}

variable "max_instances" {
  description = "Максимальна кількість копій застосунку"
  type        = number
  default     = 3
}

variable "cpu_target" {
  description = "Цільове середнє завантаження CPU для автомасштабування, %"
  type        = number
  default     = 60
}

variable "worker_max_instances" {
  description = "Максимальна кількість обробників черги"
  type        = number
  default     = 3
}

variable "queue_backlog_target" {
  description = "Цільова кількість повідомлень у черзі для масштабування обробника"
  type        = number
  default     = 20
}

variable "worker_delay_ms" {
  description = "Штучна затримка обробки одного повідомлення, мс"
  type        = number
  default     = 300
}

variable "schedule_enabled" {
  description = "Чи вмикати масштабування за розкладом"
  type        = bool
  default     = false
}

variable "day_min_instances" {
  description = "Мінімум копій удень, 08:00-22:00 за Києвом"
  type        = number
  default     = 2
}

variable "night_min_instances" {
  description = "Мінімум копій уночі, 22:00-08:00 за Києвом"
  type        = number
  default     = 1
}
