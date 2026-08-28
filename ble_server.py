import asyncio
import json
import logging
from datetime import datetime, timezone

from bless import BlessServer, BlessGATTCharacteristic, GATTCharacteristicProperties, GATTAttributePermissions
from supabase import create_client, Client

# -----------------------------------------
#  Logging setup
# -----------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
log = logging.getLogger(__name__)

# -----------------------------------------
#  Supabase config (keys come from .env — see config.py)
# -----------------------------------------
from config import SUPABASE_URL, SUPABASE_SERVICE_KEY

supabase: Client = create_client(SUPABASE_URL, SUPABASE_SERVICE_KEY)
log.info("[Supabase] Client created")

# -----------------------------------------
#  BLE config
# -----------------------------------------
SERVICE_UUID = "12345678-1234-1234-1234-123456789abc"
CHAR_UUID    = "abcdefab-cdef-abcd-efab-cdefabcdefab"

# -----------------------------------------
#  Buffer — collects BLE chunks into one message
#  BLE splits large payloads into 512-byte chunks,
#  so we reassemble them here before parsing JSON.
# -----------------------------------------
_buffer = ""


def handle_chunk(chunk: str):
    """
    Appends incoming BLE chunk to buffer.
    Tries to parse buffer as JSON after each chunk.
    When JSON is complete -> dispatch -> clear buffer.
    """
    global _buffer
    _buffer += chunk

    try:
        payload = json.loads(_buffer)
        # JSON is complete
        log.info(f"[BLE] Full message received | type={payload.get('type', 'unknown')}")
        _buffer = ""
        dispatch(payload)

    except json.JSONDecodeError:
        # JSON not complete yet — wait for next chunk
        log.debug(f"[BLE] Buffering chunk | total so far: {len(_buffer)} chars")


def dispatch(payload: dict):
    """Routes a complete message to the correct handler."""
    msg_type = payload.get("type", "unknown")
    data     = payload.get("data", {})

    if msg_type == "ping":
        log.info("[BLE] Ping received — connection OK")

    elif msg_type == "session":
        save_session(data)
        _write_shared_state("child", {
            "child_id": data.get("child_id", ""),
            "parent_id": data.get("parent_id", "")
        })
        zones = data.get("zones_visited", {})
        zone = list(zones.keys())[0] if zones else "home"
        _write_shared_state("zone", {"zone": zone})

    elif msg_type == "zone_event":
        _write_shared_state("zone", data)
        log.info(f"[Zone] child={data.get('child_id','?')} "
                 f"zone={data.get('zone','?')} "
                 f"action={data.get('action','?')}")

    elif msg_type == "child_id":
        _write_shared_state("child", data)
        log.info(f"[RFID] Child identified: {data.get('id', 'unknown')}")

    else:
        log.warning(f"[BLE] Unknown message type: {msg_type}")


def save_session(data: dict):
    """
    Saves a play session to Supabase table: sessions
    Expected fields:
      child_id, parent_id, start_time, end_time,
      total_minutes, activities, zones_visited,
      mood, focus_level, stars_earned
    """
    try:
        # Add start_time if missing
        if "start_time" not in data:
            data["start_time"] = datetime.now(timezone.utc).isoformat()

        # Remove 'id' — Supabase generates it automatically
        data.pop("id", None)

        result = supabase.table("sessions").insert(data).execute()

        if result.data:
            session_id = result.data[0].get("id", "N/A")
            log.info(f"[Supabase] Session saved OK | id={session_id}")
        else:
            log.error(f"[Supabase] Session save failed | response={result}")

    except Exception as e:
        log.error(f"[Supabase] Error saving session: {e}")


# -----------------------------------------
#  BLE callbacks
# -----------------------------------------
def read_request(characteristic: BlessGATTCharacteristic, **kwargs):
    return characteristic.value


def write_request(characteristic: BlessGATTCharacteristic, value: any, **kwargs):
    characteristic.value = value
    try:
        chunk = value.decode("utf-8")
        handle_chunk(chunk)
    except Exception as e:
        log.error(f"[BLE] Error decoding chunk: {e}")


# -----------------------------------------
#  Supabase connectivity test
# -----------------------------------------
def test_supabase():
    try:
        supabase.table("sessions").select("id").limit(1).execute()
        log.info("[Supabase] Connection OK — sessions table is accessible")
        return True
    except Exception as e:
        log.error(f"[Supabase] Connection FAILED: {e}")
        log.error("[Supabase] Make sure the 'sessions' table exists in your project")
        return False


# -----------------------------------------
#  Main
# -----------------------------------------
async def main():
    log.info("=" * 50)
    log.info("  Al-Faseelah World — BLE + Supabase Server")
    log.info("=" * 50)

    if not test_supabase():
        log.warning("[!] Supabase unreachable — BLE will run but saves will fail")

    server = BlessServer(name="Al-Faseelah-001")
    server.read_request_func  = read_request
    server.write_request_func = write_request

    await server.add_new_service(SERVICE_UUID)

    char_flags = (
        GATTCharacteristicProperties.read  |
        GATTCharacteristicProperties.write |
        GATTCharacteristicProperties.notify
    )
    permissions = (
        GATTAttributePermissions.readable |
        GATTAttributePermissions.writeable
    )

    await server.add_new_characteristic(
        SERVICE_UUID, CHAR_UUID, char_flags, None, permissions
    )

    await server.start()

    log.info("[BLE] Al-Faseelah-001 is advertising — waiting for app...")
    log.info(f"[BLE] Service UUID : {SERVICE_UUID}")
    log.info(f"[BLE] Char UUID    : {CHAR_UUID}")
    log.info("-" * 50)

    await asyncio.sleep(999999)


import json as _json

def _write_shared_state(key: str, value: dict):
    try:
        path = "/tmp/alfaseelah_state.json"
        try:
            with open(path, "r") as f:
                state = _json.load(f)
        except:
            state = {}
        state[key] = value
        with open(path, "w") as f:
            _json.dump(state, f)
    except Exception as e:
        log.error(f"[State] Write error: {e}")

asyncio.run(main())
