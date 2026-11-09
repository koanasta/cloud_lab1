# Навантажувальний тест

Потрібен k6: `winget install GrafanaLabs.k6`

Запуск з кореня репозиторію однією командою:

```
k6 run -e BASE_URL=http://<адреса ALB> -e USERS=40 -e RESULT=cache-on loadtest/notes.js
```

| Змінна | За замовчуванням | Що означає |
|---|---|---|
| `BASE_URL` | `http://localhost:8000` | адреса сервісу, береться з `terraform output public_url` |
| `USERS` | `40` | N — кількість віртуальних користувачів на сталому навантаженні |
| `RAMP_UP` | `2m30s` | наростання від 0 до N |
| `STEADY` | `5m` | стале навантаження |
| `RAMP_DOWN` | `2m` | спад до 0 |
| `RESULT` | `run` | назва файлу з підсумком у `loadtest/results/` |
| `ASYNC` | — | `1` — записи через чергу: `Prefer: respond-async` + `Idempotency-Key`, очікується `202` |

Одна ітерація користувача: 1 запис `POST /notes`, потім 9 читань: 4 × `GET /notes`, `GET /notes/{id}` щойно створеної нотатки, 3 × `GET /notes/{id}` випадкових нотаток зі списку, `GET /authors/{author}`. Після ітерації пауза 1 секунда.

Підсумок друкується в консоль і зберігається в `loadtest/results/<RESULT>.json`.
