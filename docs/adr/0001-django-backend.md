# 0001 · Django + DRF for the backend

**Context.** The original brief suggested FastAPI. The owner asked for Django "so that the
backend is secure": the platform handles accounts, payments and personal media, and needs
mature authentication, an admin, migrations and well-trodden security defaults.

**Decision.** Django 5.2 LTS with Django REST Framework, drf-spectacular for the OpenAPI schema,
django-allauth (headless) for authentication and MFA, Celery for background work. Long-lived
Server-Sent Events are served by async Django views under uvicorn (ASGI).

**Consequences.** Security features (CSRF, sessions, password hashing, ORM parameterisation,
clickjacking and HSTS settings) come from the framework rather than custom code. Model inference
never runs inside Django (see 0008), so the synchronous ORM is not a bottleneck. LTS support
runs until April 2028.
