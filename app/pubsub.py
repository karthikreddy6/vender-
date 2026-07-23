import asyncio
import json
import asyncpg
from app.config import settings

class PostgresEventBridge:
    def __init__(self):
        self.listener_task = None
        self._conn = None
        self._is_running = False

    async def start(self, sse_broadcast_callback):
        """Starts the background PostgreSQL listener."""
        if self._is_running:
            return
        self._is_running = True
        self.listener_task = asyncio.create_task(self._listener_loop(sse_broadcast_callback))

    async def stop(self):
        """Stops the background PostgreSQL listener."""
        self._is_running = False
        if self.listener_task:
            self.listener_task.cancel()
            try:
                await self.listener_task
            except asyncio.CancelledError:
                pass
            self.listener_task = None
        if self._conn:
            try:
                await self._conn.close()
            except Exception:
                pass
            self._conn = None

    async def _listener_loop(self, sse_broadcast_callback):
        # Translate postgresql+asyncpg:// to postgresql:// for asyncpg connection DSN
        dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        while self._is_running:
            try:
                self._conn = await asyncpg.connect(dsn)
                
                async def handle_notification(connection, pid, channel, payload):
                    try:
                        event_data = json.loads(payload)
                        # We run the callback on the running event loop
                        asyncio.create_task(sse_broadcast_callback(event_data))
                    except Exception as e:
                        print(f"[Bridge Error] Failed to handle notification: {e}")
                
                await self._conn.add_listener("onfood_events", handle_notification)
                print("[Bridge] Connected to PostgreSQL LISTEN channel 'onfood_events'")
                
                # Keep loop alive as long as connected
                while self._is_running:
                    # Ping or sleep. If connection is lost, read will throw and break the loop
                    await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                if self._is_running:
                    print(f"[Bridge Warning] Listener disconnected, retrying in 5s: {e}")
                    await asyncio.sleep(5)

    async def notify(self, event_type: str, data: dict):
        """Sends a notification payload to the database channel."""
        dsn = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://")
        conn = None
        try:
            conn = await asyncpg.connect(dsn)
            payload = json.dumps({"event": event_type, "data": data})
            # Escape single quotes in json payload for sql execution
            safe_payload = payload.replace("'", "''")
            await conn.execute(f"NOTIFY onfood_events, '{safe_payload}'")
        except Exception as e:
            print(f"[Bridge Error] Failed to send NOTIFY: {e}")
        finally:
            if conn:
                await conn.close()

# Global event bridge instance
event_bridge = PostgresEventBridge()
