# `base.py` (Django settings)

## 🎯 Purpose

`horilla/settings/base.py` is the main settings file.
It configures:
- environment variable reading (including optional `.env`)
- `INSTALLED_APPS`, middleware, templates
- REST framework + JWT + throttling
- database configuration (supports `DATABASE_URL`)

## 🌍 Environment & configuration

The file uses `environ.Env(...)` to define expected variables with defaults:

- `DEBUG` (default `True`)
- `ENVIRONMENT` (default `"development"`)
- `SECRET_KEY` (default `"django-insecure-default-key"`)
- `ALLOWED_HOSTS` (default `["*"]`)
- `CSRF_TRUSTED_ORIGINS` (default `["http://localhost:8000"]`)

If a `.env` file exists under `BASE_DIR`, it loads it:
- `env.read_env(str(env_file), overwrite=True)`

So typical usage:
- set values in `.env` for local/dev
- or export environment variables in production

## 📦 Installed apps + middleware

`base.py` defines large lists:
- `INSTALLED_APPS`: core Django apps + third-party apps + Horilla apps
- `MIDDLEWARE`: security, session/auth, Horilla middlewares, locale, CSRF, messages, etc.

Note: `horilla/settings/horilla_apps.py` extends `INSTALLED_APPS` further .

## 🌐 Templates context processors

`TEMPLATES[0]["OPTIONS"]["context_processors"]` includes Horilla context processors, such as:
- `horilla.context_processors.menu_context_processor` (menus, floating menu, etc.)
- `horilla.context_processors.branding`
- `horilla.context_processors.recently_viewed_items`

This is why template variables like `floating_menu`, `main_section_menu`, etc. appear automatically.

## 🔌 REST Framework / JWT

The settings define:
- `DEFAULT_AUTHENTICATION_CLASSES` using `rest_framework_simplejwt.authentication.JWTAuthentication` plus session/basic auth
- `DEFAULT_PERMISSION_CLASSES` defaults to `IsAuthenticated`
- pagination + throttling rates
- `SIMPLE_JWT` header type configuration
- `SWAGGER_SETTINGS` auto schema class

## 🗄️ Database configuration

It supports two modes:
- If `DATABASE_URL` is set: uses `env.db()`
- Else: uses individual env vars with sqlite defaults (`DB_ENGINE`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`, etc.)

Also sets:
- `CONN_MAX_AGE` based on `DB_CONN_MAX_AGE` (default `60`)

## ✅ Override strategy

Do not edit `base.py` for deployment-specific changes.
Instead:
- put overrides in `horilla/settings/local_settings.py`
- keep `base.py` stable so upgrades are easier
