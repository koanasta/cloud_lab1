# Notes API — Cloud Lab 1

REST API для нотаток на FastAPI і PostgreSQL, розгорнутий в AWS через Terraform. Нотатки можна переглядати, додавати і видаляти через просту HTML-сторінку або через API.

- Застосунок: http://notes-alb-135144386.eu-central-1.elb.amazonaws.com
- Swagger UI: http://notes-alb-135144386.eu-central-1.elb.amazonaws.com/docs

## Архітектура

```
Користувач
   │ HTTP :80
   ▼
ALB (публічні підмережі, 2 зони)
   │ :8000, тільки від SG балансувальника
   ▼
ECS Fargate (приватні підмережі)
   │ :5432, тільки від SG застосунку
   ▼
RDS PostgreSQL (приватні підмережі, без публічної адреси)
```

- Образи зберігаються в ECR
- Пароль бази генерує RDS і зберігає в Secrets Manager, ECS передає його в контейнер як змінну `DB_PASSWORD`
- Приватні підмережі ходять в інтернет через NAT Gateway
- Логи і метрики в CloudWatch
- Регіон eu-central-1

## Ендпоінти

| Метод | Шлях | Опис |
|---|---|---|
| GET | `/` | HTML-сторінка |
| GET | `/health` | перевірка стану для ALB |
| GET | `/notes` | список нотаток |
| POST | `/notes` | створити нотатку, тіло `{"text": "..."}` |
| DELETE | `/notes/{id}` | видалити нотатку |
| GET | `/debug/error` | завжди повертає 500, для перевірки алерту |

## Структура проєкту

```
app/main.py              застосунок FastAPI
app/static/index.html    HTML-сторінка
Dockerfile               образ застосунку
compose.yaml             локальний запуск разом з PostgreSQL
.env.example             приклад змінних для compose
infra/                   Terraform
  providers.tf           провайдер AWS
  variables.tf           змінні
  network.tf             VPC, підмережі, NAT, security groups
  ecr.tf                 реєстр образів
  rds.tf                 база PostgreSQL
  alb.tf                 балансувальник
  ecs.tf                 кластер, task definition, сервіс, логи
  github_oidc.tf         роль для GitHub Actions через OIDC
  monitoring.tf          алерти, SNS, дашборд
  outputs.tf             адреса застосунку, дашборда, ECR, ролі
.github/workflows/deploy.yml   CI/CD
```

## Локальний запуск

```
cp .env.example .env
docker compose up --build
```

У `.env` треба вписати пароль бази. Застосунок відкривається на http://localhost:8000

## Розгортання в AWS

```
cd infra
cp terraform.tfvars.example terraform.tfvars
terraform init
terraform apply
```

У `terraform.tfvars` вказуються репозиторій GitHub, `sub` з OIDC-токена і пошта для алертів. Після `apply` у GitHub треба задати змінну репозиторію `AWS_ROLE_ARN` зі значенням `github_actions_role_arn` і запустити workflow Deploy.

Видалити все: `terraform destroy`

## CI/CD

Після push у `main` GitHub Actions:

1. отримує тимчасовий доступ до AWS через OIDC, без збережених ключів
2. збирає Docker-образ з тегом = хеш коміту
3. пушить його в ECR
4. реєструє нову версію task definition і оновлює сервіс ECS

## Бонуси

**Моніторинг (CloudWatch)**

- Дашборд `notes`: запити і помилки ALB, час відповіді p95, CPU і пам'ять контейнера, CPU і з'єднання бази, стан алертів, останні логи
- Алерти з листом на пошту через SNS:
  - `notes-5xx` — більше 5 помилок 5xx за 5 хвилин
  - `notes-no-healthy-targets` — немає жодної здорової копії застосунку 2 хвилини
  - `notes-ecs-cpu-high` — CPU контейнера вище 80% протягом 10 хвилин
- Логи контейнера в log group `/ecs/notes`

Перевірка: кілька разів відкрити `/debug/error`, протягом 5 хвилин приходить лист ALARM.

**Документація API**

Swagger UI на `/docs`, опис OpenAPI на `/openapi.json`.
