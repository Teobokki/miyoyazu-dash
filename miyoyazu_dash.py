"""MIYOYAZU DASH  v1.0.2
3D platformer: run, jump, collect coins, clear ~60 stages as Miyoyazu.
©2026 EX Inc./HYPERION DIGITAL ©2026"""
import os, sys, json, math, random, time, threading, traceback
VERSION = "1.0.2"
HERE = getattr(sys, "_MEIPASS", os.path.dirname(os.path.abspath(__file__)))
def A(*p):
    from panda3d.core import Filename
    return Filename.from_os_specific(os.path.join(HERE, "assets", *p)).get_fullpath()
if os.name == "nt":
    PROFDIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), "EX Inc", "MIYOYAZU DASH")
else:
    PROFDIR = os.path.join(os.path.expanduser("~"), ".miyoyazu-dash")
os.makedirs(PROFDIR, exist_ok=True)
LOG = os.path.join(PROFDIR, "md_log.txt")
def log(m):
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + str(m) + "\n")
    except Exception:
        pass

import ssl
def _fallback_ssl():
    c = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    try:
        import certifi; c.load_verify_locations(cafile=certifi.where())
    except Exception:
        c.load_default_certs()
    for st in ("ROOT", "CA") if hasattr(ssl, "enum_certificates") else ():
        try:
            for der, enc, tr in ssl.enum_certificates(st):
                if enc == "x509_asn" and (tr is True or "1.3.6.1.5.5.7.3.1" in tr):
                    try: c.load_verify_locations(cadata=der)
                    except Exception: pass
        except Exception: pass
    return c
try: _SSL_FB = _fallback_ssl()
except Exception: _SSL_FB = None
try:
    import truststore; truststore.inject_into_ssl(); _SSL_TS = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
except Exception: _SSL_TS = None
def _ssl_contexts():
    return [c for c in (_SSL_TS, _SSL_FB) if c is not None] or [ssl.create_default_context()]

DEFAULT = dict(cleared={}, best={}, coins_bank=0, lives_bonus=0,
               settings=dict(gfx="EX HD", vol=0.8, fullscreen=False, sens=1.0, auto_cam=True))
def load_profile():
    p = json.loads(json.dumps(DEFAULT))
    try:
        with open(os.path.join(PROFDIR, "profile.json"), encoding="utf-8") as f:
            q = json.load(f)
        s = q.pop("settings", {}); p.update(q); p["settings"].update(s)
    except Exception: pass
    return p

PROFILE = load_profile(); ST = PROFILE["settings"]; TEST = os.environ.get("MD_TEST", "")

def _win_size():
    w, h = 1280, 720
    if os.name == "nt":
        try:
            import ctypes
            try: ctypes.windll.shcore.SetProcessDpiAwareness(2)
            except Exception: ctypes.windll.user32.SetProcessDPIAware()
            class RECT(ctypes.Structure):
                _fields_ = [("l", ctypes.c_long), ("t", ctypes.c_long), ("r", ctypes.c_long), ("b", ctypes.c_long)]
            rc = RECT()
            if ctypes.windll.user32.SystemParametersInfoW(0x30, 0, ctypes.byref(rc), 0):
                aw, ah = rc.r - rc.l, rc.b - rc.t - 40
                k = min(0.92 * aw / 16, 0.92 * ah / 9, 100)
                w, h = max(800, int(k * 16)) // 2 * 2, max(450, int(k * 9)) // 2 * 2
        except Exception: pass
    e = os.environ.get("MD_WIN")
    if e: w, h = (int(v) for v in e.lower().split("x"))
    return w, h
WIN_W, WIN_H = _win_size()

from panda3d.core import loadPrcFileData
loadPrcFileData("", "window-title MIYOYAZU DASH\nwin-size %d %d\nsync-video %d\nframebuffer-multisample 0\ndepth-bits 24\ntextures-power-2 none\n"
                "texture-minfilter linear-mipmap-linear\ntexture-magfilter linear\ntexture-anisotropic-degree %d\naudio-library-name p3openal_audio\n"
                "icon-filename %s\ndefault-model-extension .bam\nnotify-level-display error\nshow-frame-rate-meter 0\n"
                % (WIN_W, WIN_H, 0 if TEST else 1, 16 if ST.get("gfx") == "RTX" else 8, A("icon.ico")))
if os.environ.get("MD_NOAUDIO"): loadPrcFileData("", "audio-library-name null")

from panda3d.core import (Filename, Texture, Shader, FrameBufferProperties, WindowProperties, TextNode,
                          TransparencyAttrib, Vec3, Vec4, AmbientLight, DirectionalLight, CardMaker)
from direct.showbase.ShowBase import ShowBase
from direct.gui.OnscreenText import OnscreenText
from direct.gui.OnscreenImage import OnscreenImage
from direct.gui.DirectGui import DirectFrame, DirectButton, DGG
import md_gfx as G
import md_world as W
import md_play as P

# Romantic menu palette
ROSE = (0.86, 0.55, 0.62, 1)
ROSE_DIM = (0.70, 0.40, 0.48, 1)
GOLD = (0.92, 0.78, 0.48, 1)
GOLD_SOFT = (0.95, 0.88, 0.70, 1)
CREAM = (0.96, 0.93, 0.90, 1)
INK = (0.16, 0.10, 0.12, 1)
PANEL = (0.10, 0.07, 0.09, 0.72)


class App(ShowBase):
    def __init__(self):
        ShowBase.__init__(self)
        self.disableMouse()
        props = WindowProperties(); props.setCursorHidden(False); self.win.requestProperties(props)
        try:
            self.font = self.loader.loadFont(A("ui_font.ttf")); self.font.set_pixels_per_unit(64)
        except Exception:
            self.font = None
        try:
            self.fontp = self.loader.loadFont(A("ui_plain.ttf")); self.fontp.set_pixels_per_unit(48)
        except Exception:
            self.fontp = self.font
        self.settings = ST
        self.profile = PROFILE
        self.gtime = 0.0
        self.ui = None
        self.session = None
        self.paused = False
        self.keys = set(); self.pressed_keys = set()
        self.mouse_dx = self.mouse_dy = 0.0
        self._mx = self._my = 0.0
        self.sounds = {}; self.sidx = {}
        self.upd_text = None
        self.world_i = 0
        self.envmap = G.make_envmap()
        self.world_root = self.render.attach_new_node("world")
        G.setup_render(self.world_root, Vec3(0, -8, 4))
        self.world_root.set_shader_input("envmap", self.envmap)
        self._lights()
        self.set_background_color(0.55, 0.58, 0.64, 1)
        self.setup_grade()
        self.load_sounds()
        self.set_volume()
        for k in ("w", "a", "s", "d", "space", "escape", "shift", "lshift", "rshift",
                  "arrow_up", "arrow_down", "arrow_left", "arrow_right", "enter", "return"):
            self.accept(k, self._kd, [k]); self.accept(k + "-up", self._ku, [k])
        self.accept("c", self.toggle_auto_cam)
        self.accept("wheel_up", self._wheel, [1]); self.accept("wheel_down", self._wheel, [-1])
        self.taskMgr.add(self._tick, "tick")
        threading.Thread(target=self.check_update, daemon=True).start()
        if TEST:
            self.taskMgr.doMethodLater(0.05, self.autotest_start, "at")
        else:
            self.main_menu()  # instant menu — no press-start gate

    def _lights(self):
        al = AmbientLight("al"); al.set_color(Vec4(0.35, 0.32, 0.36, 1))
        self.render.set_light(self.render.attach_new_node(al))
        dl = DirectionalLight("sun"); dl.set_color(Vec4(1.15, 1.05, 0.95, 1))
        # Shadow maps often fail on Wine/Xvfb and paint the scene black — keep off; our GLSL uses hemi+wrap instead.
        dlnp = self.render.attach_new_node(dl); dlnp.set_hpr(40, -55, 0)
        self.render.set_light(dlnp); self.sun = dlnp

    def setup_grade(self):
        """Filmic warmth lives in the mesh shader. Soft film grain is a 2D overlay —
        FilterManager offscreen buffers often go black on Wine/Xvfb, so we avoid them."""
        self.fm = None; self.gq = None; self.grain = None
        try:
            from panda3d.core import PNMImage, Texture, SamplerState, CardMaker, TransparencyAttrib, TextureStage
            n = 256; img = PNMImage(n, n, 4)
            import random as _r
            rnd = _r.Random(7)
            for j in range(n):
                for i in range(n):
                    v = rnd.random()
                    img.set_xel_a(i, j, v, v, v, 0.05 if self.settings.get("gfx") == "RTX" else 0.035)
            tex = Texture("grain"); tex.load(img)
            tex.set_wrap_u(SamplerState.WM_repeat); tex.set_wrap_v(SamplerState.WM_repeat)
            cm = CardMaker("grain"); cm.set_frame(-1, 1, -1, 1)
            g = self.render2d.attach_new_node(cm.generate())
            g.set_texture(tex); g.set_transparency(TransparencyAttrib.M_alpha)
            g.set_bin("fixed", 60); g.set_depth_test(False); g.set_depth_write(False)
            g.set_tex_scale(TextureStage.get_default(), 7, 7)
            self.grain = g
        except Exception as e:
            log("grain off: %r" % e)

    def load_sounds(self):
        for k in ("jump", "djump", "dash", "collect", "land", "goal", "hurt", "click", "wonder"):
            try:
                self.sounds[k] = [self.loader.load_sfx(A("sfx", k + ".wav")) for _ in range(3)]
            except Exception as e:
                log("sfx %s: %r" % (k, e)); self.sounds[k] = []
        self.music = {}; self.music_cur = None
        for k in ("menu", "stage", "clear"):
            try:
                m = self.loader.load_music(A("music", k + ".wav"))
                m.set_loop(k != "clear"); m.set_volume(0.55)
                self.music[k] = m
            except Exception as e:
                log("music %s: %r" % (k, e))

    def set_volume(self):
        try: self.sfxManagerList[0].set_volume(self.settings.get("vol", 0.8))
        except Exception: pass
        try:
            v = float(self.settings.get("vol", 0.8)) * 0.55
            for m in self.music.values(): m.set_volume(v)
        except Exception: pass

    def play_music(self, k):
        """Retro stage/menu loops — square/pulse 90s vibe, not cutesy."""
        if os.environ.get("MD_NOAUDIO"): return
        m = self.music.get(k)
        if not m: return
        cur = self.music_cur
        try:
            if cur is m and m.status() == 1: return
        except Exception: pass
        try:
            if cur: cur.stop()
        except Exception: pass
        try:
            m.set_time(0); m.play(); self.music_cur = m
        except Exception as e:
            log("play_music %s: %r" % (k, e))

    def stop_music(self):
        try:
            if self.music_cur: self.music_cur.stop()
        except Exception: pass
        self.music_cur = None

    def sfx(self, k, vol=1.0, rate=1.0):
        pool = self.sounds.get(k) or []
        if not pool: return
        i = self.sidx.get(k, 0); self.sidx[k] = (i + 1) % len(pool); s = pool[i]
        try:
            s.stop(); s.set_volume(min(1, vol)); s.set_play_rate(rate); s.play()
        except Exception: pass

    def save_profile(self):
        try:
            with open(os.path.join(PROFDIR, "profile.json"), "w", encoding="utf-8") as f:
                json.dump(self.profile, f, indent=2)
        except Exception as e:
            log("save: %r" % e)

    def _kd(self, k):
        self.keys.add(k); self.pressed_keys.add(k)
        if k == "escape":
            if self.session and not self.paused: self.pause_menu()
            elif self.paused: self.resume()
            elif self.ui: pass

    def _ku(self, k):
        self.keys.discard(k)

    def _wheel(self, d):
        pass

    def down(self, *ks):
        return any(k in self.keys for k in ks)

    def pressed(self, *ks):
        for k in ks:
            if k in self.pressed_keys:
                return True
        return False

    def _tick(self, task):
        dt = globalClock.get_dt()
        self.gtime += dt
        if getattr(self, "grain", None):
            try:
                from panda3d.core import TextureStage
                self.grain.set_tex_offset(TextureStage.get_default(), (self.gtime * 0.02) % 1, (self.gtime * 0.013) % 1)
            except Exception: pass
        # mouse delta
        if self.mouseWatcherNode.has_mouse() and self.session and not self.paused:
            m = self.mouseWatcherNode.get_mouse()
            # relative: recenter each frame when in play
            cx = 0.0; props = WindowProperties(); props.setCursorHidden(True)
            # use accumulated from center
            dx = m.get_x(); dy = m.get_y()
            sens = 220.0 * float(self.settings.get("sens", 1.0))
            self.mouse_dx = dx * sens; self.mouse_dy = dy * sens
            self.win.movePointer(0, self.win.getXSize() // 2, self.win.getYSize() // 2)
        else:
            self.mouse_dx = self.mouse_dy = 0.0
            props = WindowProperties(); props.setCursorHidden(False); self.win.requestProperties(props)
        if self.session and not self.paused:
            self.session.update(dt)
        self.pressed_keys.clear()
        return task.cont

    # ---------- update check
    def check_update(self):
        try:
            import urllib.request
            u = "https://raw.githubusercontent.com/Teobokki/miyoyazu-dash/main/latest.json"
            j = None
            for c in _ssl_contexts():
                try:
                    with urllib.request.urlopen(u, timeout=6, context=c) as r:
                        j = json.loads(r.read().decode()); break
                except Exception as e:
                    if "CERTIFICATE_VERIFY_FAILED" not in str(e) and "chain policy" not in str(e).lower():
                        raise
                    log("update check: certificate not trusted (%s)" % e)
            if j is None: return
            if tuple(int(x) for x in j["version"].split(".")) > tuple(int(x) for x in VERSION.split(".")):
                self.upd_text = "UPDATE AVAILABLE: v%s  —  get it in HYPERION DIGITAL EX" % j["version"]
        except Exception:
            pass

    # ---------- UI helpers
    def clear_ui(self):
        if self.ui: self.ui.remove_node()
        self.ui = None

    def new_ui(self, poster=True, dim=0.55):
        self.clear_ui()
        self.ui = self.aspect2d.attach_new_node("ui")
        if poster:
            ar = self.getAspectRatio()
            # cover fills left / full behind
            im = OnscreenImage(image=A("menu_bg.jpg"), parent=self.ui, scale=(1.05, 1, 1.05), pos=(-ar * 0.15, 0, 0))
            im.set_transparency(TransparencyAttrib.M_alpha)
            DirectFrame(parent=self.ui, frameColor=(0.06, 0.04, 0.05, dim), frameSize=(-ar, ar, -1, 1), relief=None)
        return self.ui

    def label(self, parent, text, pos, scale=0.06, fg=GOLD_SOFT, font=None, align=TextNode.A_center):
        return OnscreenText(parent=parent, text=text, pos=pos, scale=scale, fg=fg,
                            align=align, font=font or self.font, shadow=(0.08, 0.04, 0.06, 0.75))

    def btn(self, parent, text, fn, pos, w=0.55, h=0.055, scale=0.042):
        if len(pos) == 2: pos = (pos[0], 0, pos[1])
        b = DirectButton(parent=parent, text=text, scale=scale, pos=pos,
                         pad=(0.4, 0.35), frameColor=(PANEL, (0.22, 0.12, 0.14, 0.9), ROSE_DIM, PANEL),
                         text_fg=CREAM, text_font=self.font, relief=DGG.FLAT,
                         command=lambda: (self.sfx("click"), fn()),
                         frameSize=(-w / scale / 2, w / scale / 2, -h / scale / 2 * 1.1, h / scale / 2 * 1.1),
                         text_scale=1.0, text_pos=(0, -0.25), borderWidth=(0.02, 0.02))
        # soft rose underline accent
        DirectFrame(parent=b, frameColor=ROSE, frameSize=(-w / scale / 2, w / scale / 2, -h / scale / 2 * 1.1 - 0.08, -h / scale / 2 * 1.1), relief=None)
        return b

    # ---------- menus (instant — no press-start)
    def main_menu(self):
        self.paused = False
        if self.session:
            self.session.destroy(); self.session = None
        self.play_music("menu")
        ui = self.new_ui(poster=True, dim=0.38)
        ar = self.getAspectRatio()
        # modern clean right column over the 3D-style cover
        x = min(0.55, ar - 0.85)
        panel = DirectFrame(parent=ui, frameColor=(0.07, 0.05, 0.06, 0.55),
                            frameSize=(x - 0.42, x + 0.48, -0.62, 0.72), relief=None)
        DirectFrame(parent=panel, frameColor=ROSE, frameSize=(x - 0.42, x - 0.412, -0.62, 0.72), relief=None)
        self.label(ui, "MIYOYAZU DASH", (x, 0.55), scale=0.078, fg=GOLD)
        self.label(ui, "3D PLATFORMER", (x, 0.45), scale=0.028, fg=ROSE, font=self.fontp)
        DirectFrame(parent=ui, frameColor=GOLD, frameSize=(x - 0.22, x + 0.22, 0.415, 0.420), relief=None)
        y = 0.22
        for label, fn in (("PLAY", self.world_select), ("STAGES", self.world_select),
                          ("SETTINGS", self.settings_menu), ("QUIT", self.userExit)):
            self.btn(ui, label, fn, (x, y), w=0.48, h=0.048, scale=0.038); y -= 0.105
        self.label(ui, "©2026 EX Inc./HYPERION DIGITAL ©2026", (0, -0.92), scale=0.026, fg=(0.7, 0.55, 0.58, 0.75), font=self.fontp)
        if self.upd_text:
            self.label(ui, self.upd_text, (0, -0.82), scale=0.028, fg=GOLD, font=self.fontp)

    def world_select(self):
        ui = self.new_ui(poster=True, dim=0.55)
        self.label(ui, "CHOOSE A WORLD", (0, 0.82), scale=0.07, fg=GOLD)
        self.label(ui, "six worlds  ·  ten stages each  ·  sixty in all", (0, 0.72), scale=0.032, fg=ROSE, font=self.fontp)
        for i, w in enumerate(W.WORLDS):
            row, col = divmod(i, 3)
            x = -0.7 + col * 0.7; y = 0.35 - row * 0.38
            cleared = sum(1 for s in range(1, 11) if str(i * 10 + s) in self.profile.get("cleared", {}))
            frame = DirectFrame(parent=ui, frameColor=PANEL, frameSize=(-0.28, 0.28, -0.12, 0.12), pos=(x, 0, y), relief=None)
            DirectFrame(parent=frame, frameColor=ROSE, frameSize=(-0.28, 0.28, 0.11, 0.12), relief=None)
            self.label(frame, w["name"], (0, 0.04), scale=0.038, fg=GOLD_SOFT)
            self.label(frame, "%d / 10 cleared" % cleared, (0, -0.04), scale=0.028, fg=CREAM, font=self.fontp)
            DirectButton(parent=frame, text="OPEN", scale=0.032, pos=(0, 0, -0.09), pad=(0.3, 0.2),
                         frameColor=(PANEL, ROSE_DIM, ROSE, PANEL), text_fg=CREAM, text_font=self.font,
                         relief=DGG.FLAT, command=lambda wi=i: (self.sfx("click"), self.stage_select(wi)))
        self.btn(ui, "BACK", self.main_menu, (0, -0.78), w=0.35)

    def stage_select(self, world_i):
        self.world_i = world_i
        w = W.WORLDS[world_i]
        ui = self.new_ui(poster=True, dim=0.6)
        self.label(ui, w["name"], (0, 0.88), scale=0.07, fg=GOLD)
        self.label(ui, w["tagline"], (0, 0.78), scale=0.03, fg=ROSE, font=self.fontp)
        for si in range(10):
            sid = world_i * 10 + si + 1
            meta = W.stage_meta(sid)
            row, col = divmod(si, 5)
            x = -1.05 + col * 0.52; y = 0.45 - row * 0.42
            cleared = self.profile.get("cleared", {}).get(str(sid))
            # unlock: stage 1 always, else previous cleared or any previous in world
            unlocked = si == 0 or str(sid - 1) in self.profile.get("cleared", {}) or bool(cleared)
            # for playtesting / first ship: unlock all in world if any progress, else first 3
            if world_i == 0 and si < 3: unlocked = True
            if any(str(world_i * 10 + k) in self.profile.get("cleared", {}) for k in range(1, 11)):
                unlocked = True
            fc = PANEL if unlocked else (0.08, 0.06, 0.07, 0.5)
            frame = DirectFrame(parent=ui, frameColor=fc, frameSize=(-0.22, 0.22, -0.14, 0.14), pos=(x, 0, y), relief=None)
            DirectFrame(parent=frame, frameColor=GOLD if cleared else ROSE, frameSize=(-0.22, 0.22, 0.13, 0.14), relief=None)
            self.label(frame, "%02d" % (si + 1), (0, 0.05), scale=0.055, fg=GOLD if unlocked else (0.4, 0.3, 0.32, 1))
            sub = meta["wonder_name"] or "dash"
            self.label(frame, sub[:14], (0, -0.03), scale=0.022, fg=ROSE if unlocked else (0.35, 0.25, 0.28, 1), font=self.fontp)
            if cleared:
                self.label(frame, "RANK %s" % cleared.get("rank", "+"), (0, -0.09), scale=0.025, fg=GOLD, font=self.fontp)
            if unlocked:
                DirectButton(parent=frame, text="", scale=1, pos=(0, 0, 0),
                             frameSize=(-0.22, 0.22, -0.14, 0.14), frameColor=(0, 0, 0, 0), relief=DGG.FLAT,
                             command=lambda s=sid: (self.sfx("click"), self.start_stage(s)))
        self.btn(ui, "BACK", self.world_select, (0, -0.85), w=0.35)

    def settings_menu(self, back=None):
        back = back or self.main_menu
        ui = self.new_ui(poster=True, dim=0.6)
        self.label(ui, "SETTINGS", (0, 0.7), scale=0.07, fg=GOLD)
        gfx = self.settings.get("gfx", "EX HD")
        self.label(ui, "Graphics: %s" % gfx, (0, 0.4), scale=0.045, fg=CREAM, font=self.fontp)
        def cycle_gfx():
            self.settings["gfx"] = "RTX" if self.settings.get("gfx") != "RTX" else "EX HD"
            self.profile["settings"] = self.settings; self.save_profile(); self.settings_menu(back)
        self.btn(ui, "TOGGLE RTX / EX HD", cycle_gfx, (0, 0.25), w=0.7)
        self.label(ui, "Volume: %d%%" % int(self.settings.get("vol", 0.8) * 100), (0, 0.05), scale=0.04, fg=CREAM, font=self.fontp)
        def vol(d):
            self.settings["vol"] = max(0, min(1, self.settings.get("vol", 0.8) + d))
            self.set_volume(); self.profile["settings"] = self.settings; self.save_profile(); self.settings_menu(back)
        self.btn(ui, "VOLUME −", lambda: vol(-0.1), (-0.35, -0.1), w=0.35)
        self.btn(ui, "VOLUME +", lambda: vol(0.1), (0.35, -0.1), w=0.35)
        def chk():
            self.upd_text = None; self.check_update(); self.settings_menu(back)
        self.btn(ui, "CHECK FOR UPDATES", chk, (0, -0.35), w=0.7)
        if self.upd_text:
            self.label(ui, self.upd_text, (0, -0.5), scale=0.03, fg=GOLD, font=self.fontp)
        self.btn(ui, "BACK", back, (0, -0.75), w=0.35)

    def pause_menu(self):
        self.paused = True
        props = WindowProperties(); props.setCursorHidden(False); self.win.requestProperties(props)
        ui = self.new_ui(poster=False, dim=0)
        DirectFrame(parent=ui, frameColor=(0.06, 0.04, 0.05, 0.7),
                    frameSize=(-self.getAspectRatio(), self.getAspectRatio(), -1, 1), relief=None)
        self.label(ui, "PAUSED", (0, 0.35), scale=0.08, fg=GOLD)
        self.btn(ui, "RESUME", self.resume, (0, 0.1))
        self.btn(ui, "RESTART STAGE", lambda: self.start_stage(self.session.meta["id"]), (0, -0.05))
        self.btn(ui, "STAGE SELECT", lambda: (self.session and self.session.destroy(), setattr(self, "session", None), self.stage_select(self.world_i)), (0, -0.2))
        self.btn(ui, "MAIN MENU", self.main_menu, (0, -0.35))

    def toggle_auto_cam(self):
        on = not bool(self.settings.get("auto_cam", True))
        self.settings["auto_cam"] = on
        try: self.save_profile()
        except Exception: pass
        s = self.session
        if s:
            s.auto_cam = on; s.cam_manual_t = 0.0
            s.banner = "AUTO CAMERA  " + ("ON" if on else "OFF"); s.banner_t = 1.2

    def resume(self):
        self.paused = False
        self.clear_ui()

    # ---------- gameplay
    def start_stage(self, sid):
        self.clear_ui()
        self.paused = False
        if self.session:
            self.session.destroy()
        self.play_music("stage")
        meta = W.stage_meta(sid)
        self.session = P.Session(self, sid, lives=3)
        self.session.world.root.reparent_to(self.world_root)
        for np in (self.world_root, self.session.world.root, self.session.player.np):
            if os.environ.get("MD_SIMPLE"):
                np.clear_shader()
            else:
                G.setup_render(np, Vec3(0, -5, 3))
                np.set_shader_input("envmap", self.envmap)
                G.set_light(np, meta["light"], self)
        # ensure camera looks at spawn on frame 0
        try:
            self.session._update_camera(0.016)
        except Exception as e:
            log("cam: %r" % e)

    def on_stage_clear(self, sid, coins, t, rank):
        self.profile.setdefault("cleared", {})[str(sid)] = dict(coins=coins, time=t, rank=rank)
        bank = self.profile.get("coins_bank", 0) + coins
        self.profile["coins_bank"] = bank
        best = self.profile.setdefault("best", {})
        prev = best.get(str(sid))
        if not prev or t < prev.get("time", 1e9):
            best[str(sid)] = dict(coins=coins, time=t, rank=rank)
        self.save_profile()
        self.taskMgr.doMethodLater(2.8, self._after_clear, "ac", extraArgs=[sid])

    def _after_clear(self, sid):
        # next stage or select
        nxt = sid + 1
        if nxt <= 60 and (sid % 10) != 0:
            self.play_music("stage"); self.start_stage(nxt)
        else:
            if self.session: self.session.destroy(); self.session = None
            self.play_music("menu"); self.stage_select((sid - 1) // 10)
        return None

    def on_stage_fail(self):
        if self.session:
            sid = self.session.meta["id"]
            self.session.destroy(); self.session = None
            self.play_music("menu"); self.stage_select((sid - 1) // 10)

    # ---------- autotest / screenshots
    def autotest_start(self, task):
        spec = TEST.split(":")
        self.shots_dir = os.environ.get("MD_SHOTS", os.path.join(PROFDIR, "shots"))
        os.makedirs(self.shots_dir, exist_ok=True)
        self.at = dict(name=spec[0], t=0.0,
                       shots=[float(v) for v in os.environ.get("MD_AT", "2,5,9").split(",")],
                       end=float(os.environ.get("MD_END", "14")))
        n = spec[0]
        if n in ("main", "title"): self.main_menu()
        elif n == "worlds": self.world_select()
        elif n == "stages": self.stage_select(int(spec[1]) if len(spec) > 1 else 0)
        elif n == "settings": self.settings_menu()
        elif n.startswith("s") and n[1:].isdigit():
            self.start_stage(int(n[1:]))
        elif n == "play":
            self.start_stage(int(spec[1]) if len(spec) > 1 else 1)
        else:
            self.main_menu()
        self.taskMgr.add(self.autotest_tick, "att")
        return task.done

    def autotest_tick(self, task):
        at = self.at; at["t"] = task.time
        # simple autopilot during play
        if self.session and not self.session.clear and not self.session.fail:
            s = self.session; p = s.player
            # hold W toward goal, jump periodically
            self.keys.add("w")
            if int(task.time * 2) % 5 == 0:
                self.pressed_keys.add("space")
            if int(task.time * 3) % 7 == 0:
                self.pressed_keys.add("shift")
            # MD_STRAFE: hold D too so the auto camera has to swing into the turn
            if os.environ.get("MD_STRAFE") and 2.0 < task.time < 2.0 + float(os.environ.get("MD_STRAFE")):
                self.keys.add("d")
            else:
                self.keys.discard("d")
            # steer camera toward goal
            if s.world.goal and not (os.environ.get("MD_STRAFE") and task.time < 2.0 + float(os.environ.get("MD_STRAFE")) + 1.5):
                gx, gy, gz = s.world.goal
                want = math.degrees(math.atan2(-(gx - p.x), (gy - p.y)))
                s.cam_yaw += _ang_wrap(want - s.cam_yaw) * 0.05
        if at["shots"] and task.time >= at["shots"][0]:
            at["shots"].pop(0)
            fn = os.path.join(self.shots_dir, "%s_%02d.png" % (at["name"], int(task.time)))
            self.win.save_screenshot(Filename.from_os_specific(fn)); log("shot %s" % fn)
        if task.time >= at["end"]:
            self.save_profile(); self.userExit()
        return task.cont


def _ang_wrap(a):
    while a > 180: a -= 360
    while a < -180: a += 360
    return a


def main():
    try:
        App().run()
    except SystemExit:
        pass
    except Exception:
        log(traceback.format_exc())
        if getattr(sys, "frozen", False): os._exit(1)
        raise

if __name__ == "__main__":
    main()
