# -*- coding: utf-8 -*-
"""
story_flow.py
=============
Standalone module that manages: (1) variety in the content that gets told,
and (2) the logic for offering stories on request / gently — without
touching any behavior-coaching logic.

Usage: create one object and call it from dialogue_manager every turn.
Depends on no external library — stdlib only.

NOTE: This module is complete and self-tested but was not wired into the
final demo build of main_ai.py; it is kept as the next planned upgrade for
story variety across sessions.
"""

import random
import re
from collections import deque


# ---------------------------------------------------------------------------
# 1) Arabic text normalization — so Whisper output matches even when the
#    spelling/diacritics vary
# ---------------------------------------------------------------------------

_TASHKEEL = re.compile(r"[ً-ْٰ]")

def _normalize(text: str) -> str:
    """Normalize Arabic/English text so matching against it is easy."""
    if not text:
        return ""
    t = text.strip().lower()
    t = _TASHKEEL.sub("", t)                 # strip diacritics (tashkeel)
    t = re.sub(r"[إأآا]", "ا", t)            # unify alef variants
    t = t.replace("ى", "ي").replace("ة", "ه")  # unify yaa and taa marbuta
    t = t.replace("ؤ", "و").replace("ئ", "ي").replace("ء", "")
    t = re.sub(r"\s+", " ", t)
    return t


# Words/phrases that signal the child asked for a story
# (Levantine dialect + Modern Standard Arabic + English)
_STORY_TRIGGERS = [
    "قصه", "حكايه", "احكيلي", "احكي لي", "احكيلنا", "حكيلي", "قصلي",
    "بدي قصه", "بدنا قصه", "ودي قصه", "بحب قصه", "كمان قصه", "قصه تانيه",
    "حكايه تانيه", "بعد", "كمان وحده", "غير قصه",
    "story", "another story", "tell me a story", "read me", "one more",
]

def is_story_request(text: str) -> bool:
    """True if the child explicitly asked for a story."""
    norm = _normalize(text)
    return any(trg in norm for trg in _STORY_TRIGGERS)


# ---------------------------------------------------------------------------
# 2) Variety tracking — remember what each child has heard and cycle
#    through everything before repeating
# ---------------------------------------------------------------------------

class _VarietyTracker:
    def __init__(self, id_key="id"):
        self.id_key = id_key
        self._seen = {}        # child_id -> set(ids)
        self._last = {}        # child_id -> last id told (avoid immediate repeat)

    def _cid(self, child_id):
        return str(child_id) if child_id is not None else "_"

    def pick(self, pool, child_id=None, kind=None, zone=None, lang=None,
             kind_key="type", zone_key="zone", lang_key="language"):
        """
        Return a non-repeated content item from the pool.
        pool = the list of dicts already fetched from content_manager.
        Can be filtered by kind (story/challenge), zone, and language.
        """
        cid = self._cid(child_id)
        seen = self._seen.setdefault(cid, set())

        # optional filtering
        items = pool
        if kind is not None:
            items = [x for x in items if x.get(kind_key) == kind]
        if zone is not None:
            items = [x for x in items if x.get(zone_key) == zone]
        if lang is not None:
            items = [x for x in items if x.get(lang_key) == lang]

        if not items:
            return None

        fresh = [x for x in items if x.get(self.id_key) not in seen]

        # all stories exhausted -> start a new cycle, but skip the last one told
        if not fresh:
            seen.clear()
            last = self._last.get(cid)
            fresh = [x for x in items if x.get(self.id_key) != last] or items

        chosen = random.choice(fresh)
        seen.add(chosen.get(self.id_key))
        self._last[cid] = chosen.get(self.id_key)
        return chosen

    def reset(self, child_id=None):
        cid = self._cid(child_id)
        self._seen.pop(cid, None)
        self._last.pop(cid, None)


# ---------------------------------------------------------------------------
# 3) Main interface — ties everything together; called from dialogue_manager
# ---------------------------------------------------------------------------

class StoryFlow:
    def __init__(self, id_key="id",
                 min_turns_before_offer=2, offer_cooldown=5):
        """
        min_turns_before_offer : how many turns must pass before offering a
                                 story unprompted (so we don't open with one).
        offer_cooldown         : how many turns between one offer and the
                                 next (don't be pushy).
        """
        self.tracker = _VarietyTracker(id_key=id_key)
        self.min_turns_before_offer = min_turns_before_offer
        self.offer_cooldown = offer_cooldown
        self._turns = {}          # child_id -> turn count
        self._last_offer = {}     # child_id -> turn number of the last offer
        self._story_told = {}     # child_id -> has a story been told this session?

    def _cid(self, child_id):
        return str(child_id) if child_id is not None else "_"

    def tick(self, child_id=None):
        """Call once per turn (at the start or end of the loop) to count."""
        cid = self._cid(child_id)
        self._turns[cid] = self._turns.get(cid, 0) + 1

    def wants_story(self, text) -> bool:
        """Did the child explicitly ask for a story? (Always honored.)"""
        return is_story_request(text)

    def time_to_offer(self, child_id=None) -> bool:
        """
        Is it a good moment to gently offer a story? True when:
        - enough turns have passed since the session started (not turn one), and
        - we have not offered one recently (cooldown).
        """
        cid = self._cid(child_id)
        turns = self._turns.get(cid, 0)
        if turns < self.min_turns_before_offer:
            return False
        last = self._last_offer.get(cid, -999)
        if turns - last < self.offer_cooldown:
            return False
        self._last_offer[cid] = turns
        return True

    def next_story(self, pool, child_id=None, zone=None, lang=None):
        """Return the next (non-repeated) story. Call when wants_story=True."""
        story = self.tracker.pick(pool, child_id=child_id,
                                  kind="story", zone=zone, lang=lang)
        if story is not None:
            self._story_told[self._cid(child_id)] = True
        return story

    def next_content(self, pool, kind, child_id=None, zone=None, lang=None):
        """Generic version for any content kind (story / challenge) with the
        same variety guarantee."""
        return self.tracker.pick(pool, child_id=child_id,
                                 kind=kind, zone=zone, lang=lang)

    def reset_session(self, child_id=None):
        """Call when a new child logs in (RFID) so they start clean."""
        cid = self._cid(child_id)
        self.tracker.reset(child_id)
        self._turns.pop(cid, None)
        self._last_offer.pop(cid, None)
        self._story_told.pop(cid, None)


# ---------------------------------------------------------------------------
# Quick integration example for dialogue_manager (kept as a reference):
# ---------------------------------------------------------------------------
#
#   from story_flow import StoryFlow
#   flow = StoryFlow(id_key="id")          # once at startup
#
#   # when a new child logs in (RFID):
#   flow.reset_session(child_id)
#
#   # every turn, after getting the transcript from Whisper:
#   flow.tick(child_id)
#
#   if flow.wants_story(transcript):
#       story = flow.next_story(story_pool, child_id, zone=current_zone,
#                               lang=current_lang)
#       if story:
#           speak(story["..."])            # match your column name (title/body)
#   elif flow.time_to_offer(child_id):
#       speak("بتحب أحكيلك قصة حلوة؟")     # gentle offer, not a hard push
#   else:
#       # continue the normal (Gemini) conversation as-is
#       pass
#
# Notes:
# - story_pool = the same list returned by content_manager (list of dicts).
# - id_key / kind_key / zone_key / lang_key are configurable to match your
#   table columns.
# - Not a single line touches the behavior logic — variety and timing only.
