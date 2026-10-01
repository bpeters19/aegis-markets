# Aegis Markets

![CI](https://github.com/bpeters19/aegis-markets/actions/workflows/ci.yml/badge.svg)

Modular trading infrastructure platform: market data -> strategy -> risk -> OMS -> paper execution -> portfolio.

## Status
Week 1: FastAPI service with health and readiness probes, pooled PostgreSQL 18 connection, Alembic migrations, and CI running unit and integration tests against a real database.

## Stack
Python 3.13, FastAPI, SQLAlchemy 2.0, PostgreSQL 18, Alembic, pytest, GitHub Actions.

## Local setup
1. Install PostgreSQL 18 and create an `aegis` user and database.
2. `cd backend`, create a virtual environment, and run `pip install -r requirements.txt`.
3. Copy `backend/.env.example` to `backend/.env` and set your password.
4. `alembic upgrade head`
5. `uvicorn app.main:app --reload`, then open http://127.0.0.1:8000/docs
6. Run tests with `pytest -v` (unit tests only: `pytest -m "not integration"`).
