# «Инклюзивный конструктор» — Back End

### Стек

Python 3.12, FastAPI, SQLModel/SQLAlchemy, PostgreSQL, Redis, Pydantic, maxapi, Uvicorn

Инструменты: Docker, PyCharm

---

### Зависимости

Все зависимости указаны в файле `requirements.txt`.

Устанавливаются командой:

```shell
pip install --no-cache-dir -r requirements.txt
```

---

### Конфигурация

Переменные окружения хранятся в ".env":
Для запуска

```environment
BOT_TOKEN=...
```

---

### Локальный запуск (без Docker)

```shell
python main.py
```

---

### Используемые сервисы

Проект работает вместе с PostgreSQL и Redis, инициализируемыми через "docker-compose.yml".

```yaml
services:
  bot:
    build: .
    environment:
      BOT_TOKEN: ${BOT_TOKEN}
      REDIS_URL: redis://redis:6379
      DATABASE_URL: postgresql://postgres:postgres@postgres:5432/max-hackaton
    ports:
      - "8080:8080"
    depends_on:
      - postgres
      - redis
    networks:
      - default

  postgres:
    image: postgres:15
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
      POSTGRES_DB: max-hackaton
    volumes:
      - postgres_data:/var/lib/postgresql/data
    networks:
      - default

  redis:
    image: redis:7
    volumes:
      - redis_data:/data
    networks:
      - default

volumes:
  postgres_data:
  redis_data:
```

---

### Локальный запуск через Docker

Сборка и запуск проекта:

```shell
docker compose up --build
```

API будет доступно на:

```http://localhost:8080```

Документация API:

```http://localhost:8080/docs```

---