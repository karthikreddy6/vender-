# OnFood — PostgreSQL Database Configuration & Setup Guide

This guide details how to configure, run, and maintain the PostgreSQL database for the OnFood application.

---

## 1. Running PostgreSQL via Docker Compose (Recommended)

A `docker-compose.yml` file is provided in the project root. This is the easiest way to launch the database with the correct configurations.

### Prerequisites:
* [Docker Desktop](https://www.docker.com/products/docker-desktop/) must be installed and running.

### How to Start the DB:
Open your terminal in the project root folder and run:
```bash
docker compose up -d
```

### What this does:
* Starts a PostgreSQL 16 container named `onfood-postgres`.
* Automatically sets the username to `postgres` and password to `postgres`.
* Creates a default database named `onfood`.
* Maps port `5432` of the container to port `5432` of your computer.
* Sets up a persistent volume (`postgres_data`) so your data is not lost when the container stops.

### How to Stop the DB:
```bash
docker compose down
```

---

## 2. Native PostgreSQL Installation Setup (Alternative)

If you prefer to run PostgreSQL natively on your Windows OS (without Docker):

### Step 1: Install PostgreSQL
1. Download and run the installer from the [PostgreSQL Official Website](https://www.postgresql.org/download/windows/).
2. During installation:
   * Keep the default port as `5432` (or `5433` if 5432 is taken).
   * Set the password for the superuser `postgres`. We recommend using `postgres` for local development.

### Step 2: Create the Database
1. Open **pgAdmin** or run the following command in SQL Shell (`psql`):
   ```sql
   CREATE DATABASE onfood;
   ```
2. Verify that the database is created successfully.

---

## 3. Server Configuration Setup

Once PostgreSQL is running, update your server connection settings.

### `.env` File Setup
Create or update the `.env` file in the server root folder:

```ini
# Database Connection URL Format:
# postgresql+asyncpg://<username>:<password>@<host>:<port>/<database_name>
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/onfood

# JWT Authentication Config
JWT_SECRET=super_secret_key_for_development_purposes
JWT_ISSUER=onfood
```

> 💡 **Note:** If your PostgreSQL is running on port `5433` (like your native installation), update the port in `.env` to `5433`.

---

## 4. Initializing the Database (Migrations)

Whenever you setup the database for the first time or pull schema updates, run the database migrations:

```bash
# 1. Activate your Python virtual environment
.venv\Scripts\activate

# 2. Apply all migration files to set up tables
alembic upgrade head
```

---

## 5. Cleaning & Reseeding the Database

If you want to clear out old test orders and repopulate fresh categories and menu items for development, you can use the helper script:

```bash
python reseed_db.py
```
This script safely deletes existing cart items, orders, categories, and menu items in the correct order to respect foreign key constraints, then recreates them.
