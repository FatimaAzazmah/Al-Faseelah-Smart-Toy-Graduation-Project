# -*- coding: utf-8 -*-
# Content Manager v2 — bridge between Faseelah and Supabase content
# Matched to the FINAL database schema (rfid_id, is_completed, saved content)
import os, random
from datetime import datetime, timezone
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()
sb = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

def get_piece_card(piece_key, difficulty=1, prefer_ids=None):
    """Knowledge card for a physical piece (e.g. 'elephant', 'kitchen').

    If prefer_ids is given (the child's parent-saved content ids) and one of
    this piece's cards is among them, that saved card is returned instead of
    a random one. Matters most for content-rich pieces like 'library' (55
    cards) and 'tech_lab' (21), where a random pick would rarely surface the
    specific card the parent saved.
    """
    r = sb.table("content").select("*, pieces!inner(key,name_ar,name_en)") \
        .eq("pieces.key", piece_key).eq("type", "learn") \
        .lte("difficulty", difficulty).eq("is_active", True).execute()
    if not r.data:
        return None
    if prefer_ids:
        favored = [c for c in r.data if c.get("id") in prefer_ids]
        if favored:
            return random.choice(favored)
    return random.choice(r.data)

def get_story(zone_key, behavior_key=None):
    """A story from a zone. Prefers behavior-matching story if key given."""
    r = sb.table("content").select("*, zones!inner(key)") \
        .eq("zones.key", zone_key).eq("type", "story").eq("is_active", True).execute()
    if not r.data:
        return None
    if behavior_key:
        m = [s for s in r.data if s.get("trackable_key") == behavior_key]
        if m:
            return random.choice(m)
    return random.choice(r.data)

def get_behavior_story(behavior_key):
    """A story targeting a specific behavior, from ANY zone."""
    r = sb.table("content").select("*").eq("type", "story") \
        .eq("trackable_key", behavior_key).eq("is_active", True).execute()
    return random.choice(r.data) if r.data else None

def get_challenge(zone_key):
    """A challenge from a zone."""
    r = sb.table("content").select("*, zones!inner(key)") \
        .eq("zones.key", zone_key).eq("type", "challenge") \
        .eq("is_active", True).execute()
    return random.choice(r.data) if r.data else None

def get_curriculum_item(trackable_key):
    """A specific unit: letter, number, surah, dua... by its key."""
    r = sb.table("content").select("*") \
        .eq("trackable_key", trackable_key).eq("is_active", True).execute()
    return r.data[0] if r.data else None

def get_active_dynamic_zone():
    """Which dynamic board is currently mounted (chosen from the app)."""
    r = sb.table("zones").select("*").eq("is_dynamic", True) \
        .eq("is_active", True).execute()
    return r.data[0] if r.data else None

def get_child_context(rfid_id):
    """Child + preferences + active goal + achievements + saved content."""
    child_r = sb.table("children").select("*").eq("rfid_id", rfid_id).execute()
    if not child_r.data:
        return None
    child = child_r.data[0]
    ctx = {"child": child, "preferences": None, "goal": None,
           "achieved": [], "saved_content_ids": []}

    pref = sb.table("parent_preferences").select("*") \
        .eq("child_id", child["id"]).execute()
    if pref.data:
        ctx["preferences"] = pref.data[0]

    goal = sb.table("behavior_goals").select("*") \
        .eq("child_id", child["id"]).eq("is_completed", False).execute()
    if goal.data:
        ctx["goal"] = goal.data[0]

    ach = sb.table("achievements").select("item_key") \
        .eq("child_id", child["id"]).execute()
    ctx["achieved"] = [a["item_key"] for a in ach.data]

    saved = sb.table("child_saved_content").select("content_id") \
        .eq("child_id", child["id"]).execute()
    ctx["saved_content_ids"] = [s["content_id"] for s in saved.data]
    return ctx


# ─────────────────────────────────────────────────────────
# Session reporting to parents (writes to the `sessions` table, which
# the Pearant parent app reads). Columns confirmed from the live schema:
#   child_id, parent_id, start_time, end_time, total_minutes,
#   activities (array), zones_visited (object), mood, focus_level,
#   stars_earned
# ─────────────────────────────────────────────────────────
def save_session_full(child_id, parent_id, start_time, end_time,
                      total_minutes, activities, zones_visited,
                      stars_earned=0, mood="happy", focus_level="high"):
    """Persist a finished play session so the parent sees a report in the app.

    activities    : list of dicts (one per piece the child engaged with)
    zones_visited : dict {zone_name: count}
    Returns the inserted row id, or None on failure.
    """
    if not child_id or not parent_id:
        print("[Supabase] save_session_full: missing child_id/parent_id — skipping")
        return None
    data = {
        "child_id":      child_id,
        "parent_id":     parent_id,
        "start_time":    start_time,
        "end_time":      end_time,
        "total_minutes": total_minutes,
        "activities":    activities,
        "zones_visited": zones_visited,
        "mood":          mood,
        "focus_level":   focus_level,
        "stars_earned":  stars_earned,
    }
    try:
        r = sb.table("sessions").insert(data).execute()
        if r.data:
            sid = r.data[0].get("id")
            print(f"[Supabase] Session saved | id={sid}")
            return sid
        print(f"[Supabase] Session save returned no data: {r}")
        return None
    except Exception as e:
        print(f"[Supabase] save_session_full error: {e}")
        return None


def upsert_session(session_id, child_id, parent_id, start_time, end_time,
                   total_minutes, activities, zones_visited,
                   stars_earned=0, mood="happy", focus_level="high"):
    """Create-or-update a session row incrementally.

    Pass session_id=None the first time -> inserts a new row and returns its
    id. Pass that id back on later calls -> updates the same row. This lets
    the game persist progress after every piece, so the parent report is
    safe even if the program is killed abruptly (the finally-block in a
    daemon thread is NOT guaranteed to run at interpreter shutdown).

    Returns the session id (new or existing), or None on failure.
    """
    if not child_id or not parent_id:
        print("[Supabase] upsert_session: missing child_id/parent_id — skipping")
        return None
    data = {
        "child_id":      child_id,
        "parent_id":     parent_id,
        "start_time":    start_time,
        "end_time":      end_time,
        "total_minutes": total_minutes,
        "activities":    activities,
        "zones_visited": zones_visited,
        "mood":          mood,
        "focus_level":   focus_level,
        "stars_earned":  stars_earned,
    }
    try:
        if session_id is None:
            r = sb.table("sessions").insert(data).execute()
            if r.data:
                sid = r.data[0].get("id")
                print(f"[Supabase] Session created | id={sid}")
                return sid
            print(f"[Supabase] Session insert returned no data: {r}")
            return None
        else:
            r = sb.table("sessions").update(data).eq("id", session_id).execute()
            print(f"[Supabase] Session updated | id={session_id} | "
                  f"{len(activities)} activity(ies)")
            return session_id
    except Exception as e:
        print(f"[Supabase] upsert_session error: {e}")
        return session_id  # keep whatever id we had


def save_child_content(child_id, content_id):
    """Save a piece of content the child liked to child_saved_content.
    Idempotent-ish: skips if the pair already exists. Columns confirmed:
    id, child_id, content_id, saved_at.
    """
    if not child_id or not content_id:
        return None
    try:
        existing = sb.table("child_saved_content").select("id") \
            .eq("child_id", child_id).eq("content_id", content_id).execute()
        if existing.data:
            print(f"[Supabase] content {content_id} already saved for child")
            return existing.data[0].get("id")
        data = {
            "child_id":  child_id,
            "content_id": content_id,
            "saved_at":  datetime.now(timezone.utc).isoformat(),
        }
        r = sb.table("child_saved_content").insert(data).execute()
        if r.data:
            print(f"[Supabase] Saved content {content_id} for child")
            return r.data[0].get("id")
        return None
    except Exception as e:
        print(f"[Supabase] save_child_content error: {e}")
        return None


# ---------- self-test ----------
if __name__ == "__main__":
    print("=== Content Manager v2 Self-Test ===")
    card = get_piece_card("elephant")
    print("[1] Elephant card:", "OK" if card else "MISSING")
    if card:
        print("    fact:", card["knowledge_card"]["facts_l1"][0]["ar"])
    story = get_behavior_story("behavior_honesty")
    print("[2] Honesty story:", story["knowledge_card"]["title_ar"] if story else "MISSING")
    ch = get_challenge("home")
    print("[3] Home challenge:", ch["knowledge_card"]["title_ar"] if ch else "MISSING")
    letter = get_curriculum_item("letter_noon")
    print("[4] Letter Noon:", "OK" if letter else "MISSING")
    dz = get_active_dynamic_zone()
    print("[5] Active dynamic board:", dz["name_ar"] if dz else "none set")
    kids = sb.table("children").select("name, rfid_id").execute()
    print("[6] Children in DB:", [(k["name"], k["rfid_id"]) for k in kids.data] or "none yet")
    print("Done!")
