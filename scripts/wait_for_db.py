import os
import socket
import time
from urllib.parse import urlparse

def wait_for_db():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        print("DATABASE_URL is not set. Skipping wait.")
        return

    # Normalize dialect for parsing
    if db_url.startswith("postgresql+asyncpg://"):
        db_url = db_url.replace("postgresql+asyncpg://", "postgresql://")
    
    try:
        parsed = urlparse(db_url)
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
                    return
            except Exception:
                time.sleep(1)
        print("Database connection check timed out. Attempting to proceed anyway.")
    except Exception as e:
        print(f"Error parsing database URL: {e}. Proceeding.")

if __name__ == "__main__":
    wait_for_db()
