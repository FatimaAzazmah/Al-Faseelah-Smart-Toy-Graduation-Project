#!/usr/bin/env python3
"""
sensor_controller.py - Al-Faseelah World

Bridges the reed-switch sensors to the AI layer. Tracks WHERE the
child currently is (which zone, which piece) so the AI can:
  - know the child's live location at any moment
  - react when they touch a new piece
  - check whether they actually moved to a zone Faseelah told them to
  - build the conversation around the zone they're standing in, not
    just the single piece they touched

Usage:
    from sensor_controller import SensorController

    sc = SensorController()
    sc.start()

    while True:
        touch = sc.wait_for_touch(timeout=0.5)
        if touch:
            print(touch["key"], touch["zone_name_ar"])
        # sc.current_zone / sc.current_piece always reflect live state
"""
import queue
import time
from gpiozero import Button
from content_manager import sb as supabase

FORBIDDEN_PINS = {0, 1, 14, 15}
BOUNCE_TIME = 0.15
RETOUCH_SECONDS = 8.0


class SensorController:
    def __init__(self):
        self.events = queue.Queue()
        self.buttons = []
        self.pin_to_piece = {}
        self._last_touch = {}

        # live state - this is what the AI reads to know "where is the child"
        self.current_piece = None      # full piece dict, or None
        self.current_zone_id = None
        self.current_zone_name_ar = None
        self.last_touch_time = None

        self.active_dynamic_zone_id = None
        self._zones_by_id = {}

    # ---------- setup ----------

    def get_active_dynamic_zone_id(self):
        res = (
            supabase.table("zones")
            .select("id")
            .eq("is_dynamic", True)
            .eq("is_active", True)
            .execute()
        )
        rows = res.data or []
        return rows[0]["id"] if rows else None

    def load_pieces(self):
        zones_res = supabase.table("zones").select("id, name_ar, name_en, is_dynamic").execute()
        zones = zones_res.data or []
        self._zones_by_id = {z["id"]: z for z in zones}

        self.active_dynamic_zone_id = self.get_active_dynamic_zone_id()
        fixed_zone_ids = [z["id"] for z in zones if not z["is_dynamic"]]

        zone_ids_to_load = list(fixed_zone_ids)
        if self.active_dynamic_zone_id is not None:
            zone_ids_to_load.append(self.active_dynamic_zone_id)

        res = (
            supabase.table("pieces")
            .select("*")
            .in_("zone_id", zone_ids_to_load)
            .not_.is_("sensor_pin", "null")
            .execute()
        )
        rows = res.data or []

        loaded, skipped = [], []
        for p in rows:
            pin = p.get("sensor_pin")
            try:
                pin = int(pin)
            except (TypeError, ValueError):
                skipped.append((p.get("key"), pin, "not a number"))
                continue
            if pin in FORBIDDEN_PINS:
                skipped.append((p.get("key"), pin, "forbidden pin!"))
                continue
            self.pin_to_piece[pin] = p
            loaded.append((p.get("key"), pin))
        return loaded, skipped

    def start(self):
        loaded, skipped = self.load_pieces()
        print(f"[SENSORS] Active dynamic zone id: {self.active_dynamic_zone_id}")
        print(f"[SENSORS] Loading {len(loaded)} pieces...")
        for key, pin in sorted(loaded, key=lambda x: x[1]):
            print(f"  GPIO {pin:>2} -> {key}")
        for key, pin, why in skipped:
            print(f"  [SKIP] {key} (pin={pin}): {why}")

        for pin, piece in self.pin_to_piece.items():
            try:
                btn = Button(pin, pull_up=True, bounce_time=BOUNCE_TIME)
            except Exception as e:
                print(f"  [ERROR] GPIO {pin} ({piece.get('key')}): {e}")
                continue
            btn.when_pressed = self._make_handler(piece)
            self.buttons.append(btn)

        print(f"[SENSORS] Watching {len(self.buttons)} sensors. Ready!")

    # ---------- live tracking ----------

    def _make_handler(self, piece):
        def handler():
            key = piece.get("key")
            now = time.time()
            if now - self._last_touch.get(key, 0) < RETOUCH_SECONDS:
                return
            self._last_touch[key] = now

            # update live location state
            self.current_piece = piece
            self.current_zone_id = piece.get("zone_id")
            zone = self._zones_by_id.get(self.current_zone_id, {})
            self.current_zone_name_ar = zone.get("name_ar")
            self.last_touch_time = now

            self.events.put(piece)
        return handler

    def wait_for_touch(self, timeout=0.5):
        """Blocks up to `timeout` seconds for the next touch event.
        Returns the piece dict, or None if nothing happened."""
        try:
            return self.events.get(timeout=timeout)
        except queue.Empty:
            return None

    def is_child_in_zone(self, zone_name_ar):
        """Check if the child's last known location matches a zone name.
        Useful for: 'Faseelah told them to go to the mosque - did they?'"""
        if self.current_zone_name_ar is None:
            return False
        return self.current_zone_name_ar.strip() == zone_name_ar.strip()

    def get_location_summary(self):
        """A small dict the AI prompt layer can drop straight into context."""
        if self.current_piece is None:
            return {
                "zone_name_ar": None,
                "piece_key": None,
                "seconds_since_last_touch": None,
            }
        return {
            "zone_name_ar": self.current_zone_name_ar,
            "piece_key": self.current_piece.get("key"),
            "piece_name_ar": self.current_piece.get("name_ar"),
            "seconds_since_last_touch": time.time() - self.last_touch_time,
        }

    def drain(self):
        while not self.events.empty():
            try:
                self.events.get_nowait()
            except queue.Empty:
                break

    def close(self):
        for b in self.buttons:
            b.close()


if __name__ == "__main__":
    # self-test: shows live location tracking as pieces are touched
    sc = SensorController()
    sc.start()
    print("\nTouch pieces with the magnet... (Ctrl+C to exit)\n")
    try:
        while True:
            touch = sc.wait_for_touch(timeout=1.0)
            if touch:
                print(f"[TOUCH] {touch.get('key')}  zone={sc.current_zone_name_ar}")
                print(f"        location_summary = {sc.get_location_summary()}")
    except KeyboardInterrupt:
        print("\nBye!")
    finally:
        sc.close()
