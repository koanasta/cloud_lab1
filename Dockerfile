# 1. Базовий образ із ЗАФІКСОВАНОЮ версією (не latest)
FROM python:3.12.7-slim-bookworm

# 2. Робоча папка всередині образу
WORKDIR /app

# не створювати .pyc і одразу виводити логи (важливо для CloudWatch)
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# 3. СПОЧАТКУ тільки список залежностей і їх встановлення — окремий шар,
#    який кешується, поки requirements.txt не зміниться
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. ПОТІМ код — змінюється часто, але попередній шар береться з кешу
COPY app/ ./app/

# 5. Створюємо звичайного користувача і працюємо від нього, не від root
RUN useradd --create-home --uid 10001 appuser
USER appuser

# 6. Документуємо порт і задаємо команду запуску
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
