import os
import socket
import time
import asyncio
import asyncpg
import subprocess
from urllib.parse import urlparse

async def verify_and_stamp_db(db_url: str):
    # Normalize dialect for asyncpg
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
        
    try:
        conn = await asyncpg.connect(db_url)
        try:
            # Check if key application tables already exist
            tables_to_check = ['users', 'menu_items', 'orders']
            existing_tables = []
            for table in tables_to_check:
                exists = await conn.fetchval(
                    "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = $1)",
                    table
                )
                if exists:
                    existing_tables.append(table)
            
            # Check if alembic_version table exists
            alembic_exists = await conn.fetchval(
                "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_schema = 'public' AND table_name = 'alembic_version')"
            )
            
            has_version = False
            if alembic_exists:
                version_count = await conn.fetchval("SELECT COUNT(*) FROM alembic_version")
                if version_count > 0:
                    has_version = True
            
            print(f"Database check: existing key tables = {existing_tables}, alembic_version exists = {alembic_exists}, has version = {has_version}")
            
            if existing_tables and (not alembic_exists or not has_version):
                print("Database tables already exist, but no alembic version was found. Stamping database to 'head' to prevent failing migration.")
                result = subprocess.run(["alembic", "stamp", "head"], capture_output=True, text=True)
                if result.returncode == 0:
                    print("Successfully stamped database to head.")
                else:
                    print(f"Warning: Failed to stamp database: {result.stderr}")
            else:
                print("Database is clean or already tracked by Alembic. Proceeding with regular migrations.")
        finally:
            await conn.close()
    except Exception as e:
        print(f"Error checking database table status: {e}")

def wait_for_db():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("DATABASE_URL is not set. Skipping wait.")
        return

    # Normalize dialect for port checking
    check_url = db_url
    if check_url.startswith("postgresql+asyncpg://"):
        check_url = check_url.replace("postgresql+asyncpg://", "postgresql://")
    
    try:
        parsed = urlparse(check_url)
        host = parsed.hostname
        port = parsed.port or 5432
        
        if not host:
            print("Could not parse hostname from DATABASE_URL. Skipping wait.")
            return

        print(f"Waiting for database at {host}:{port}...")
        for _ in range(60):
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                    s.settimeout(1.0)
                    s.connect((host, port))
                    print("Database is up and reachable!")
                    # Check table status and stamp if needed
                    asyncio.run(verify_and_stamp_db(db_url))
                    return
            except Exception:
                time.sleep(1)
        print("Database connection check timed out. Attempting to proceed anyway.")
    except Exception as e:
        print(f"Error parsing database URL: {e}. Proceeding.")

if __name__ == "__main__":
    wait_for_db()
