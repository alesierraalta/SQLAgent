# T-005 — Configuración segura (localhost bind + CORS)

## Implementado
- Backend sigue el perímetro local por defecto:
  - `WEB_API_HOST` default `127.0.0.1` (ver `src/api/__main__.py`).
  - `WEB_API_PORT` default `8000` (ver `src/api/__main__.py`).
- CORS configurado en `src/api/app.py` con `CORSMiddleware`.
  - Env var: `WEB_ALLOWED_ORIGINS` (CSV).
  - Default: `http://localhost:3000`.
  - Seguridad: si `WEB_ALLOWED_ORIGINS` incluye `*`, se ignora y se fuerza lista explícita.
  - `allow_credentials=False`.
  - `allow_methods=["GET","POST","OPTIONS"]`, `allow_headers=["*"]`, `max_age=600`.

## Cómo cambiarlo (sin romper seguridad)
- Para permitir otros origins locales:
  - `WEB_ALLOWED_ORIGINS="http://localhost:3000,http://127.0.0.1:3000"`
- Para cambiar host/puerto del API:
  - `WEB_API_HOST=127.0.0.1 WEB_API_PORT=8000 python -m src.api`

## Nota
- Abrir el API a red (0.0.0.0) queda fuera del MVP y debe hacerse conscientemente con configuración explícita.