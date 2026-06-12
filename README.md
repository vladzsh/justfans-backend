# JustFans Backend

Мини-CRM для чатеров: рабочее место чатера (список диалогов, переписка, PPV, realtime) и монитор тимлида (presence, нагрузка, просрочки ответов). Стек: Django ASGI (Daphne + Channels), PostgreSQL, Redis. Спецификация: [github.com/vladzsh/justfans-spec](https://github.com/vladzsh/justfans-spec).

---

## Деплой

Рабочее решение развёрнуто на Railway (backend + PostgreSQL + Redis + frontend-nginx):

**https://frontend-production-f3fd.up.railway.app**

Тестовые данные прогнаны сидером, учётки — в таблице выше. Чтобы проверить realtime в одиночку: войдите чатером и тимлидом в двух окнах и нажмите «Симулировать сообщение фана» в открытом диалоге.

---

## Запуск

```bash
git clone https://github.com/vladzsh/justfans-backend.git
cd justfans-backend
docker compose up --build
```

Приложение поднимается на **http://localhost:8080** (nginx). Миграции применяются автоматически при старте backend-контейнера.

После первого запуска прогоните сидер тестовых данных:

```bash
docker compose exec backend python manage.py seed
```

---

## Тестовые учётки

Пароль для всех: **demo1234**

| Логин      | Роль     | Отображаемое имя |
|------------|----------|-----------------|
| chatter1   | chatter  | Alice           |
| chatter2   | chatter  | Bob             |
| chatter3   | chatter  | Carol           |
| chatter4   | chatter  | Dave            |
| teamlead1  | teamlead | Team Lead       |

---

## Как проверить realtime в одиночку

В интерфейсе чатера откройте любой диалог и нажмите кнопку **«Симулировать сообщение фана»** — сообщение мгновенно появится в переписке и списке диалогов, а в мониторе тимлида возникнет ожидающий диалог.

Либо через curl:

```bash
# Войти и сохранить куки
curl -c cookies.txt -s -X POST http://localhost:8080/api/auth/login/ \
  -H "Content-Type: application/json" \
  -d '{"username": "chatter1", "password": "demo1234"}'

# Извлечь CSRF-токен из куки (требуется для POST)
CSRF=$(grep csrftoken cookies.txt | awk '{print $NF}')

# Симулировать сообщение фана в случайный диалог
curl -b cookies.txt -s -X POST http://localhost:8080/api/demo/fan-message/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -d '{}'

# В конкретный диалог с текстом
curl -b cookies.txt -s -X POST http://localhost:8080/api/demo/fan-message/ \
  -H "Content-Type: application/json" \
  -H "X-CSRFToken: $CSRF" \
  -d '{"conversation_id": 1, "text": "Hey, are you there?"}'
```

---

## Переменные окружения

Все переменные имеют дефолты для локального demo. Скопируйте `.env.example` → `.env` для кастомизации.

| Переменная               | Описание                                               | Дефолт                                             |
|--------------------------|--------------------------------------------------------|----------------------------------------------------|
| `DATABASE_URL`           | PostgreSQL connection string                           | `postgres://justfans:justfans@db:5432/justfans`    |
| `REDIS_URL`              | Redis connection string                                | `redis://redis:6379/0`                             |
| `DJANGO_SECRET_KEY`      | Секретный ключ Django                                  | `dev-secret-key-change-in-production`              |
| `DEBUG`                  | Режим отладки                                          | `True`                                             |
| `ALLOWED_HOSTS`          | Разрешённые хосты (запятая)                            | `*`                                                |
| `OVERDUE_SECONDS`        | Порог просрочки ответа чатера (сек)                    | `120`                                              |
| `PRESENCE_GRACE_SECONDS` | Время, после которого чатер считается offline (сек)    | `30`                                               |
| `HEARTBEAT_SECONDS`      | Интервал ping-heartbeat от фронтенда (сек)             | `10`                                               |
| `MESSAGES_PAGE_SIZE`     | Кол-во сообщений на странице истории                   | `30`                                               |
| `FRONTEND_CONTEXT`       | Путь/URL для сборки frontend-образа                    | `https://github.com/vladzsh/justfans-frontend.git` |
| `BACKEND_HOST`           | Hostname backend'а для nginx (Railway)                 | `backend`                                          |

---

## Тесты

```bash
# Внутри контейнера
docker compose exec backend pytest

# Локально (нужен Python 3.12 и venv)
cd justfans-backend
python -m pytest
```

---

## Архитектура

REST-эндпоинты (`/api/`) обслуживают историю сообщений, списки диалогов и снапшот монитора; WebSocket (`/ws/`) доставляет live-события: новые сообщения, присутствие чатеров, обновления монитора. nginx — единственный публичный вход, отдаёт SPA и проксирует `/api` и `/ws` на backend; сессионная авторизация работает без CORS-конфигурации, поскольку SPA и API — один origin.

Подробнее — в [репозитории спецификации](https://github.com/vladzsh/justfans-spec).
