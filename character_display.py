#!/usr/bin/env python3
"""
Al-Faseelah World — Character Display v3
=========================================
800x480 | Pygame | Raspberry Pi

Fix v3: All images aligned to the same bounding box → no body shift during talking.

API:
    char = CharacterDisplay()
    char.set_expression("happy")
    char.start_talking()
    char.stop_talking()
    char.run()
"""

import pygame
import sys
import os
import time
import queue
import random
from collections import deque

try:
    from PIL import Image
    import numpy as np
    HAS_PIL = True
except ImportError:
    HAS_PIL = False
    print("[WARN] Install: pip install Pillow numpy")

# ─────────────────────────────────────────────────────────────
SCREEN_W   = 800
SCREEN_H   = 480
FPS        = 60
FADE_SPEED      = 255   # normal expression transitions
TALK_FADE_SPEED = 255  # talking mouth frames  (~2 frames at 60fps)       # alpha per frame
TALK_SPEED = 0.11   # seconds per mouth frame
BLINK_DUR  = [0.05, 0.08, 0.05]
AUTO_BLINK = (3.5, 6.5)
BG_TOLE    = 38       # background removal tolerance
ALIGN_PAD  = 10       # padding around character when aligning

CHAR_SIZE  = (360, 360)
CHAR_X     = (SCREEN_W - CHAR_SIZE[0]) // 2
CHAR_Y     = (SCREEN_H - CHAR_SIZE[1]) // 2 - 10

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
IMG_DIR    = os.path.join(BASE_DIR, "images")
BG_PATH    = os.path.join(IMG_DIR, "background.png")

EXPRESSIONS = {
    "neutral":       "netural.jpg",
    "sad":           "sad.jpg",
    "happy":         "happy.jpg",
    "excited":       "excited.jpg",
    "surprised":     "surprised.jpg",
    "sleeping":      "sleeping.jpg",
    "encouraging":   "encouraging.jpg",
    "listening":     "listening.jpg",
    "blink_half":    "blink_half.jpg",
    "blink_closed":  "blink_closed.jpg",
    "talking_small": "taking_small.jpg",
    "talking_wide":  "talking_wide.jpg",
}

KEY_MAP = {
    pygame.K_1: ("expr", "neutral"),
    pygame.K_2: ("expr", "happy"),
    pygame.K_3: ("expr", "excited"),
    pygame.K_4: ("expr", "surprised"),
    pygame.K_5: ("expr", "sad"),
    pygame.K_6: ("expr", "sleeping"),
    pygame.K_7: ("expr", "encouraging"),
    pygame.K_8: ("expr", "listening"),
    pygame.K_t: ("toggle_talk", None),
    pygame.K_b: ("blink", None),
    pygame.K_ESCAPE: ("quit", None),
    pygame.K_q:      ("quit", None),
}
# ─────────────────────────────────────────────────────────────


class CharacterDisplay:

    def __init__(self, fullscreen=None):
        pygame.init()
        pygame.display.set_caption("Al-Faseelah World")
        pygame.mouse.set_visible(False)

        if fullscreen is None:
            fullscreen = self._is_raspberry_pi()

        flags = pygame.FULLSCREEN | pygame.NOFRAME if fullscreen else 0
        self.screen  = pygame.display.set_mode((SCREEN_W, SCREEN_H), flags)
        self.clock   = pygame.time.Clock()
        self.running = True
        self._q      = queue.Queue()

        self.bg     = self._load_background()
        print("[INFO] Loading & aligning character images...")
        self.images = self._load_images()   # all images aligned to neutral

        # Crossfade
        self._cur        = "neutral"
        self._nxt        = None
        self._alpha      = 255
        self._instant    = False
        self._fade_speed = FADE_SPEED

        # Talk
        self._talking    = False
        self._talk_phase = 0
        self._talk_timer = 0.0

        # Blink
        self._bseq   = []
        self._bidx   = 0
        self._btimer = 0.0
        self._ab_timer = random.uniform(*AUTO_BLINK)

        print("[INFO] Ready.  Keys: 1-8 / T=talk / B=blink / ESC=quit")

    # ── Public API ──────────────────────────────────────────

    def set_expression(self, name: str):
        self._q.put(("set_expr", name))

    def start_talking(self):
        self._q.put(("start_talk", None))

    def stop_talking(self):
        self._q.put(("stop_talk", None))

    def trigger_blink(self):
        self._q.put(("blink", None))

    def quit(self):
        self._q.put(("quit", None))

    # ── Main loop ───────────────────────────────────────────

    def run(self):
        prev = time.perf_counter()
        while self.running:
            now = time.perf_counter()
            dt  = min(now - prev, 0.05)
            prev = now
            self._events()
            self._process_q()
            self._update(dt)
            self._draw()
            pygame.display.flip()
            self.clock.tick(FPS)
        pygame.quit()

    # ── Events ──────────────────────────────────────────────

    def _events(self):
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                self.running = False
            elif ev.type == pygame.KEYDOWN:
                a = KEY_MAP.get(ev.key)
                if not a: continue
                cmd, val = a
                if   cmd == "quit":        self.running = False
                elif cmd == "expr":        self._talking = False; self._q.put(("set_expr", val))
                elif cmd == "toggle_talk": self._q.put(("stop_talk" if self._talking else "start_talk", None))
                elif cmd == "blink":       self._q.put(("blink", None))

    # ── Queue ───────────────────────────────────────────────

    def _process_q(self):
        while True:
            try: cmd, val = self._q.get_nowait()
            except queue.Empty: break
            if   cmd == "set_expr":   self._fade_to(val, instant=False)
            elif cmd == "start_talk": self._talking = True;  self._talk_phase = 0; self._talk_timer = 0.0
            elif cmd == "stop_talk":  self._talking = False; self._fade_to(self._base(), instant=False)
            elif cmd == "blink":      self._start_blink()
            elif cmd == "quit":       self.running = False

    # ── Update ──────────────────────────────────────────────

    def _update(self, dt):
        # Fade
        if self._nxt is not None:
            if self._instant:
                self._cur = self._nxt; self._nxt = None; self._alpha = 255; self._instant = False
            else:
                self._alpha -= self._fade_speed
                if self._alpha <= 0:
                    self._cur = self._nxt; self._nxt = None; self._alpha = 255; self._fade_speed = FADE_SPEED

        # Talk — INSTANT switch (no crossfade = no body ghosting)
        if self._talking:
            self._talk_timer += dt
            if self._talk_timer >= TALK_SPEED:
                self._talk_timer  = 0.0
                self._talk_phase  = 1 - self._talk_phase
                expr = "talking_wide" if self._talk_phase else "talking_small"
                self._fade_to(expr, instant=True)

        # Blink — also instant
        if self._bseq:
            self._btimer += dt
            if self._btimer >= self._bseq[self._bidx][1]:
                self._btimer = 0.0; self._bidx += 1
                if self._bidx >= len(self._bseq):
                    self._bseq = []; self._bidx = 0
                else:
                    self._fade_to(self._bseq[self._bidx][0], instant=True)

        # Auto-blink
        if not self._talking and not self._bseq:
            if self._cur not in ("sleeping", "surprised", "blink_half", "blink_closed"):
                self._ab_timer -= dt
                if self._ab_timer <= 0:
                    self._ab_timer = random.uniform(*AUTO_BLINK)
                    self._start_blink()

    # ── Draw ────────────────────────────────────────────────

    def _draw(self):
        if self.bg:
            self.screen.blit(self.bg, (0, 0))
        else:
            self.screen.fill((220, 240, 235))

        cur = self.images[self._cur]

        # Crossfade only for non-instant transitions
        if self._nxt and self._nxt in self.images and not self._instant:
            nxt = self.images[self._nxt]
            a   = max(0, self._alpha)
            tmp = cur.copy();  tmp.set_alpha(a)
            self.screen.blit(tmp, (CHAR_X, CHAR_Y))
            tmp2 = nxt.copy(); tmp2.set_alpha(255 - a)
            self.screen.blit(tmp2, (CHAR_X, CHAR_Y))
        else:
            self.screen.blit(cur, (CHAR_X, CHAR_Y))

    # ── Helpers ─────────────────────────────────────────────

    def _fade_to(self, expr, instant=False, speed=None):
        if expr not in self.images: return
        if expr == self._cur and self._nxt is None: return
        self._nxt        = expr
        self._alpha      = 255
        self._instant    = instant
        self._fade_speed = speed if speed else FADE_SPEED

    def _base(self):
        if self._cur in ("talking_small","talking_wide","blink_half","blink_closed"):
            return "neutral"
        return self._cur

    def _start_blink(self):
        if self._bseq: return
        base = self._base()
        d = BLINK_DUR
        self._bseq  = [(base,d[0]),("blink_half",d[1]),
                       ("blink_closed",d[0]),("blink_half",d[1]),(base,0.0)]
        self._bidx  = 0; self._btimer = 0.0
        self._fade_to(base, instant=True)

    # ── Image loading ────────────────────────────────────────

    def _load_background(self):
        if not os.path.exists(BG_PATH):
            print(f"[WARN] background.png not found"); return None
        try:
            bg = pygame.image.load(BG_PATH).convert()
            bg = pygame.transform.smoothscale(bg, (SCREEN_W, SCREEN_H))
            print("[OK]  Background loaded."); return bg
        except Exception as e:
            print(f"[ERR] Background: {e}"); return None

    def _load_images(self):
        cache_dir = os.path.join(BASE_DIR, "images_cache")
        if os.path.exists(cache_dir):
            print("[INFO] Loading from cache...")
            images = {}
            for name in EXPRESSIONS:
                path = os.path.join(cache_dir, f"{name}.png")
                try:
                    surf = pygame.image.load(path).convert_alpha()
                    images[name] = surf
                    print(f"  [OK]  {name}")
                except Exception as e:
                    print(f"  [ERR] {name}: {e}")
                    s = pygame.Surface(CHAR_SIZE, pygame.SRCALPHA)
                    s.fill((120,200,120,180))
                    images[name] = s
            return images


        # ── Step 1: remove bg from all images ───────────────
        pil_imgs = {}
        for name, fname in EXPRESSIONS.items():
            path = os.path.join(IMG_DIR, fname)
            try:
                pil_imgs[name] = self._remove_bg(path)
            except Exception as e:
                print(f"  [ERR] remove_bg {name}: {e}")
                pil_imgs[name] = Image.new("RGBA", CHAR_SIZE, (120,200,120,200))

        # ── Step 2: find reference bbox from neutral ─────────
        ref_bbox = self._find_bbox(pil_imgs["neutral"])
        if ref_bbox is None:
            # If neutral detection fails, just scale everything
            ref_bbox = (ALIGN_PAD, ALIGN_PAD,
                        CHAR_SIZE[0]-ALIGN_PAD, CHAR_SIZE[1]-ALIGN_PAD)
        print(f"  [INFO] Reference bbox: {ref_bbox}")

        # ── Step 3: align every image to ref bbox ────────────
        images = {}
        for name, pil in pil_imgs.items():
            try:
                src_bbox = self._find_bbox(pil)
                if src_bbox is None:
                    aligned = pil.resize(CHAR_SIZE, Image.LANCZOS)
                else:
                    aligned = self._align_to_ref(pil, src_bbox, ref_bbox)
                surf = self._pil_to_pygame(aligned)
                images[name] = surf
                print(f"  [OK]  {name}")
            except Exception as e:
                print(f"  [ERR] align {name}: {e}")
                s = pygame.Surface(CHAR_SIZE, pygame.SRCALPHA)
                s.fill((120,200,120,180)); images[name] = s
        return images

    # ── PIL helpers ──────────────────────────────────────────

    def _remove_bg(self, path):
        """Remove cream/white background using edge-seeded flood fill."""
        img  = Image.open(path).convert("RGBA")
        data = np.array(img, dtype=np.uint8)
        h, w = data.shape[:2]

        corners = np.vstack([
            data[:8,  :8,  :3].reshape(-1,3),
            data[:8,  w-8:, :3].reshape(-1,3),
            data[h-8:, :8,  :3].reshape(-1,3),
            data[h-8:, w-8:, :3].reshape(-1,3),
        ])
        bg   = np.median(corners, axis=0)
        diff = np.abs(data[:,:,:3].astype(np.int16) - bg).sum(axis=2)
        is_bg = diff < (BG_TOLE * 3)

        visited  = np.zeros((h, w), dtype=bool)
        frontier = deque()
        for x in range(w):
            if is_bg[0,x]   and not visited[0,x]:   visited[0,x]=True;   frontier.append((0,x))
            if is_bg[h-1,x] and not visited[h-1,x]: visited[h-1,x]=True; frontier.append((h-1,x))
        for y in range(h):
            if is_bg[y,0]   and not visited[y,0]:   visited[y,0]=True;   frontier.append((y,0))
            if is_bg[y,w-1] and not visited[y,w-1]: visited[y,w-1]=True; frontier.append((y,w-1))
        while frontier:
            r,c = frontier.popleft()
            for dr,dc in ((1,0),(-1,0),(0,1),(0,-1)):
                nr,nc = r+dr, c+dc
                if 0<=nr<h and 0<=nc<w and not visited[nr,nc] and is_bg[nr,nc]:
                    visited[nr,nc]=True; frontier.append((nr,nc))

        result = data.copy(); result[visited, 3] = 0
        return Image.fromarray(result)

    def _find_bbox(self, pil_img, pad=ALIGN_PAD):
        """Find bounding box of visible (non-transparent) pixels."""
        arr   = np.array(pil_img.resize(CHAR_SIZE))
        alpha = arr[:,:,3]
        vis   = alpha > 30
        rows  = np.where(vis.any(axis=1))[0]
        cols  = np.where(vis.any(axis=0))[0]
        if len(rows) < 5 or len(cols) < 5:
            return None
        return (
            max(0, int(cols[0]) - pad),
            max(0, int(rows[0]) - pad),
            min(CHAR_SIZE[0], int(cols[-1]) + pad),
            min(CHAR_SIZE[1], int(rows[-1]) + pad),
        )

    def _align_to_ref(self, pil_img, src_bbox, ref_bbox):
        """
        Crop the character from src_bbox, rescale it to fit ref_bbox,
        and place it on a transparent CHAR_SIZE canvas.
        Result: character at the exact same size and position across all images.
        """
        x1,y1,x2,y2   = src_bbox
        rx1,ry1,rx2,ry2 = ref_bbox

        # Crop character from original (at CHAR_SIZE scale)
        resized = pil_img.resize(CHAR_SIZE, Image.LANCZOS)
        char    = resized.crop((x1, y1, x2, y2))

        # Scale to exactly fit the reference bounding box
        target_w = rx2 - rx1
        target_h = ry2 - ry1
        char_fit = char.resize((target_w, target_h), Image.LANCZOS)

        # Place on blank canvas
        canvas = Image.new("RGBA", CHAR_SIZE, (0, 0, 0, 0))
        canvas.paste(char_fit, (rx1, ry1), char_fit)
        return canvas

    @staticmethod
    def _pil_to_pygame(pil_img):
        return pygame.image.fromstring(
            pil_img.tobytes(), pil_img.size, pil_img.mode).convert_alpha()

    @staticmethod
    def _is_raspberry_pi():
        try:
            with open("/proc/device-tree/model") as f:
                return "Raspberry" in f.read()
        except Exception:
            return False


# ─────────────────────────────────────────────────────────────
if __name__ == "__main__":
    char = CharacterDisplay()
    char.run()
