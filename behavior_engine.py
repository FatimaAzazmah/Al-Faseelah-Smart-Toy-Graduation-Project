#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
behavior_engine.py - Al-Faseelah World  (STANDALONE, testable on its own)
==========================================================================

The behavior-modification engine, kept in ONE self-contained module so it
can be built and tested WITHOUT touching the working main_ai.py. Once it
passes its self-test, main_ai.py wires it in with a couple of lines.

What it does
------------
A parent writes a behavior goal in FREE TEXT (e.g. "بدي ابني يرتب غرفته",
"التعاون", "ما يضربش اخوته"). The AI must UNDERSTAND that free text and map
it to one of the 10 catalog behaviors — we do NOT hand-maintain a phrase
list. Flow:

    parent goal (free text)
        -> classify_goal()      # Gemini reads the catalog, picks the key
        -> STORY_ALIAS bridge   # catalog key -> story trackable_key
        -> get_behavior_story() # the matching story
        -> tell it + inject hidden_prompt coaching strategy
        -> detect success_signals in the child's speech
        -> increment_goal()     # progress toward target_count

Public API (used by main_ai.py):
    resolve_goal(goal)              -> dict with catalog + story + key, or None
    behavior_system_addition(res, lang) -> str to append to the system prompt
    detect_success(res, text)       -> bool (did the child show the behavior?)
    increment_goal(goal)            -> {current, target, completed, just_completed}

Run standalone:
    cd ~/alfaseelah
    source venv/bin/activate
    python3 behavior_engine.py         # runs the self-test
"""
import os
import json
import logging

from dotenv import load_dotenv
from google import genai
from google.genai import types

from content_manager import sb, get_behavior_story

log = logging.getLogger(__name__)

load_dotenv()
_client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))


# ─────────────────────────────────────────────────────────
# STORY_ALIAS bridge: catalog key -> story trackable_key, for the few
# catalog behaviors whose story lives under a different key. (7/10 match
# directly; only these 3 differ.)
# ─────────────────────────────────────────────────────────
STORY_ALIAS = {
    "behavior_obedience": "behavior_respect_parents",
    "behavior_tidiness":  "behavior_tidy_toys",
    "behavior_prayer":    "behavior_family_prayer",
}


def _load_catalog():
    """All active catalog behaviors, sorted."""
    r = sb.table("behavior_catalog").select("*") \
        .eq("is_active", True).order("sort_order").execute()
    return r.data or []


# ─────────────────────────────────────────────────────────
# classify_goal: Gemini reads the catalog and picks the best-matching key
# for the parent's free-text goal. Returns the catalog key, or None.
# ─────────────────────────────────────────────────────────
def classify_goal(goal_text, catalog=None):
    """Map a free-text parent goal to a catalog behavior key via Gemini."""
    if not goal_text or not goal_text.strip():
        return None
    catalog = catalog or _load_catalog()
    if not catalog:
        return None

    options = "\n".join(
        f"- {c['key']}: {c['name_ar']} — {c.get('description_ar', '')}"
        for c in catalog
    )
    valid_keys = {c["key"] for c in catalog}

    prompt = (
        "You are matching a parent's free-text behavior goal for their child "
        "to exactly ONE behavior from a fixed catalog.\n\n"
        f"PARENT'S GOAL (free text): \"{goal_text}\"\n\n"
        f"CATALOG (choose the single closest one):\n{options}\n\n"
        "Reply with ONLY the key (e.g. behavior_tidiness). If truly none fit, "
        "reply exactly: none. No other words, no punctuation."
    )
    try:
        resp = _client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                thinking_config=types.ThinkingConfig(thinking_budget=0),
            ),
        )
        key = (resp.text or "").strip().split()[0].strip().strip(".")
        if key in valid_keys:
            log.info(f"[BEHAVIOR] '{goal_text}' -> {key}")
            return key
        if key == "none":
            log.info(f"[BEHAVIOR] '{goal_text}' -> no catalog match")
            return None
        log.warning(f"[BEHAVIOR] classifier returned unknown key: {key!r}")
        return None
    except Exception as e:
        log.error(f"[BEHAVIOR] classify_goal error: {e}")
        return None


# ─────────────────────────────────────────────────────────
# resolve_goal: full resolution from a behavior_goals row to everything
# the session needs — catalog entry, story, and the story key used.
# ─────────────────────────────────────────────────────────
def resolve_goal(goal):
    """goal: a behavior_goals row (dict). Returns a dict:
        {catalog_key, story_key, catalog, story}
    or None if nothing could be matched."""
    if not goal:
        return None

    catalog = _load_catalog()
    by_key = {c["key"]: c for c in catalog}

    # 1) If the goal already carries a catalog key, trust it.
    catalog_key = goal.get("behavior_key")
    if catalog_key not in by_key:
        catalog_key = None

    # 2) Otherwise classify the free-text target_behavior (or title).
    if not catalog_key:
        text = goal.get("target_behavior") or goal.get("title") or ""
        catalog_key = classify_goal(text, catalog)

    if not catalog_key:
        return None

    # 3) Bridge to a story key (alias if needed, else same key).
    story_key = STORY_ALIAS.get(catalog_key, catalog_key)
    story = get_behavior_story(story_key)

    return {
        "catalog_key": catalog_key,
        "story_key":   story_key,
        "catalog":     by_key.get(catalog_key),
        "story":       story,
    }


# ─────────────────────────────────────────────────────────
# behavior_system_addition: the private coaching strategy to append to the
# session's system prompt (Faseelah nudges softly, never lectures).
# ─────────────────────────────────────────────────────────
def behavior_system_addition(res, lang="ar"):
    if not res or not res.get("catalog"):
        return ""
    cat = res["catalog"]
    hidden = (cat.get("hidden_prompt_en") if lang == "en"
              else cat.get("hidden_prompt_ar")) or cat.get("hidden_prompt_ar", "")
    if not hidden:
        return ""
    label = "HIDDEN BEHAVIOR-COACHING STRATEGY (never reveal this to the child)"
    return f"\n\n{label}:\n{hidden}"


# ─────────────────────────────────────────────────────────
# detect_success: did the child's utterance show the target behavior?
# Uses the catalog's success_signals.positive phrases (substring match on
# the — often noisy — Whisper transcript). Deliberately lenient.
# ─────────────────────────────────────────────────────────
def detect_success(res, child_text):
    if not res or not child_text:
        return False
    cat = res.get("catalog") or {}
    signals = (cat.get("success_signals") or {}).get("positive") or []
    txt = child_text.strip()
    # meta-words that describe the child ("says", "mentions", "suggests")
    # rather than words the child would actually say — ignore them.
    META = {"يقول", "يقولها", "يذكر", "يقترح", "بنفسه", "says", "mentions",
            "suggests", "the", "child"}
    for phrase in signals:
        words = [w for w in phrase.split() if len(w) > 2 and w not in META]
        # match if ANY meaningful content word appears in the child's speech
        if words and any(w in txt for w in words):
            log.info(f"[BEHAVIOR] success signal matched: {phrase!r}")
            return True
    return False


# ─────────────────────────────────────────────────────────
# increment_goal: bump current_count toward target_count; mark complete.
# ─────────────────────────────────────────────────────────
def increment_goal(goal):
    """Advance the goal by one rep. Returns:
        {current, target, completed, just_completed}
    or None on failure / missing goal."""
    if not goal or not goal.get("id"):
        return None
    current = (goal.get("current_count") or 0) + 1
    target = goal.get("target_count") or 1
    completed = current >= target
    patch = {"current_count": current}
    if completed and not goal.get("is_completed"):
        patch["is_completed"] = True
        from datetime import datetime, timezone
        patch["completed_at"] = datetime.now(timezone.utc).isoformat()
    try:
        sb.table("behavior_goals").update(patch).eq("id", goal["id"]).execute()
    except Exception as e:
        log.error(f"[BEHAVIOR] increment_goal error: {e}")
        return None
    # keep the in-memory copy in sync
    goal["current_count"] = current
    if completed:
        goal["is_completed"] = True
    return {
        "current": current,
        "target": target,
        "completed": completed,
        "just_completed": completed and current == target,
    }


# ─────────────────────────────────────────────────────────
# Self-test — run directly: python3 behavior_engine.py
# Read-only except for a clearly-marked optional increment test.
# ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s [%(levelname)s] %(message)s")
    print("=" * 60)
    print("  behavior_engine.py — Self-Test")
    print("=" * 60)

    cat = _load_catalog()
    print(f"\n[1] Catalog loaded: {len(cat)} behaviors")
    assert cat, "catalog is empty!"

    # 1) Classifier on realistic free-text goals.
    print("\n[2] Classifier (free text -> catalog key):")
    trials = [
        "بدي ابني يرتب غرفته ويجمع العابه",
        "التعاون",
        "ما يضربش اخوته لما يزعل",
        "احترام الوالدين والاستجابة لهم",
        "الصدق وما يكذب",
        "اريده ان يصلي",
        "الرحمة بالقطط والحيوانات",
    ]
    for t in trials:
        key = classify_goal(t, cat)
        print(f"    {t[:32]:34} -> {key}")

    # 2) Full resolution + alias bridge + story fetch.
    print("\n[3] resolve_goal + story bridge:")
    for target in ["الترتيب وإعادة الأغراض", "الصلاة", "التنمر", "التعاون"]:
        fake_goal = {"id": None, "target_behavior": target,
                     "behavior_key": None, "current_count": 0,
                     "target_count": 3}
        res = resolve_goal(fake_goal)
        if res:
            story = res.get("story")
            stitle = (story["knowledge_card"].get("title_ar")
                      if story else "— NO STORY")
            print(f"    {target[:24]:26} -> catalog={res['catalog_key']:22} "
                  f"story_key={res['story_key']:24} | {stitle}")
        else:
            print(f"    {target[:24]:26} -> (no match)")

    # 3) Hidden-prompt injection sample.
    print("\n[4] Hidden coaching strategy (sample):")
    res = resolve_goal({"id": None, "target_behavior": "الترتيب",
                        "behavior_key": None, "current_count": 0,
                        "target_count": 3})
    add = behavior_system_addition(res, "ar")
    print("   ", (add[:160] + "...") if add else "(none)")

    # 4) Success-signal detection.
    print("\n[5] Success-signal detection:")
    if res:
        for utter, expect in [("انا رتبت العابي", True),
                              ("انا جوعان", False),
                              ("رجعت اللعبة مكانها", False)]:
            got = detect_success(res, utter)
            mark = "OK " if got == expect else "XX "
            print(f"    {mark}[{got!s:5}] exp {expect!s:5} | {utter}")

    print("\n[6] increment_goal: skipped (would write to DB).")
    print("    To test writes, run with a real goal id manually.")
    print("\nDone.")
