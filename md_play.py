"""MIYOYAZU DASH session: third-person platforming, coins, wonders, romantic HUD.
©2026 EX Inc./HYPERION DIGITAL ©2026"""
import math, random, time
from panda3d.core import Vec3, TransparencyAttrib, TextNode, CardMaker
from direct.gui.OnscreenText import OnscreenText
from direct.gui.DirectGui import DirectFrame
import md_gfx as G
import md_world as W

# Romantic HUD palette — soft rose / champagne gold, no glow
ROSE = (0.86, 0.55, 0.62, 1)
ROSE_DIM = (0.72, 0.42, 0.50, 1)
GOLD = (0.92, 0.78, 0.48, 1)
GOLD_SOFT = (0.95, 0.88, 0.70, 1)
CREAM = (0.96, 0.93, 0.90, 1)
INK = (0.18, 0.12, 0.14, 1)
PANEL = (0.12, 0.08, 0.10, 0.55)
PANEL_EDGE = (0.78, 0.55, 0.58, 0.85)
HEART = (0.90, 0.40, 0.48, 1)


def _ang_wrap(a):
    while a > 180: a -= 360
    while a < -180: a += 360
    return a


class Player:
    def __init__(self):
        self.x = self.y = 0.0
        self.z = 1.2
        self.vx = self.vy = self.vz = 0.0
        self.h = 0.0
        self.on_ground = False
        self.jumps = 0
        self.dash_cd = 0.0
        self.dash_t = 0.0
        self.invuln = 0.0
        self.scale = 1.0
        self.grinding = False
        self.rail_t = 0.0
        self.rail = None
        self.np = None
        self.facing = 0.0

    def reset(self, spawn, scale=1.0):
        self.x, self.y, self.z = spawn[0], spawn[1], spawn[2]
        self.vx = self.vy = self.vz = 0.0
        self.on_ground = False
        self.jumps = 0
        self.dash_cd = 0.0
        self.dash_t = 0.0
        self.invuln = 0.0
        self.scale = scale
        self.grinding = False
        self.rail = None
        if self.np:
            self.np.set_scale(scale)
            self.np.set_pos(self.x, self.y, self.z)


class Session:
    def __init__(self, app, stage_id, lives=3):
        self.app = app
        self.meta = W.stage_meta(stage_id)
        self.world = W.StageWorld(app, self.meta)
        self.player = Player()
        self.player.np = G.build_miyoyazu(app.render)
        if not __import__("os").environ.get("MD_SIMPLE"):
            G.setup_render(self.player.np, Vec3(0, 0, 2))
            self.player.np.set_shader_input("envmap", app.envmap)
        scale = 1.55 if self.meta["wonder"] == "giant" else 1.0
        self.player.reset(self.world.spawn, scale=scale)
        self.lives = lives
        self.coins = 0
        self.coins_total = len(self.world.coins)
        self.time = 0.0
        self.clear = False
        self.fail = False
        self.rank = ""
        self.wonder_t = 0.0
        self.wonder_on = False
        self.banner = ""
        self.banner_t = 0.0
        self.cam_yaw = 180.0
        self.cam_pitch = -18.0
        self.cam_pos = None
        self.shake = 0.0
        # AUTO CAMERA state
        self.auto_cam = bool(app.settings.get("auto_cam", True))
        self.cam_manual_t = 0.0
        self.cam_idle_t = 0.0
        self.cam_dist = None
        self.cam_look = None
        self.cam_lead = [0.0, 0.0]
        self.cam_air_z = None
        self.time_scale = 0.55 if self.meta["wonder"] == "slow" else 1.0
        self.grav = 22.0
        if self.meta["wonder"] == "lowgrav":
            self.grav = 12.0
        if self.meta["wonder"] == "flip":
            self.grav = -14.0  # soft upward pull after jump apex handled in update
        self.flip_phase = 0.0
        self.hud = Hud(app, self)
        # seed third-person camera behind spawn so first frames are not black/empty
        self.cam_yaw = 180.0; self.cam_pitch = -16.0
        self.cam_pos = [self.player.x, self.player.y - 5.5, self.player.z + 2.2]
        self._update_camera(0.016)
        self._announce()

    def _announce(self):
        m = self.meta
        self.banner = m["name"]
        self.banner_t = 2.4
        if m["wonder_name"]:
            self.app.taskMgr.doMethodLater(2.2, self._announce_wonder, "aw")

    def _announce_wonder(self, task):
        self.banner = self.meta["wonder_name"]
        self.banner_t = 2.6
        self.app.sfx("wonder")
        self.wonder_on = True
        return task.done

    def destroy(self):
        self.hud.destroy()
        if self.player.np:
            self.player.np.remove_node()
        self.world.clear()

    def input(self):
        a = self.app
        return dict(
            w=a.down("w", "arrow_up"), s=a.down("s", "arrow_down"),
            a=a.down("a", "arrow_left"), d=a.down("d", "arrow_right"),
            jump=a.pressed("space"), dash=a.pressed("shift") or a.pressed("lshift") or a.pressed("rshift"),
            lookx=a.mouse_dx, looky=a.mouse_dy,
        )

    def update(self, dt):
        if self.clear or self.fail:
            self.hud.update(dt)
            return
        ts = self.time_scale
        d = dt * ts
        self.time += d
        self.banner_t = max(0, self.banner_t - dt)
        p = self.player
        inp = self.input() if not self.app.paused else dict(w=0, s=0, a=0, d=0, jump=0, dash=0, lookx=0, looky=0)

        # camera look: optional manual mouse look; auto camera takes back over after a short hold
        if abs(inp["lookx"]) > 0.8 or abs(inp["looky"]) > 0.8:
            self.cam_manual_t = 1.4
        self.cam_yaw = _ang_wrap(self.cam_yaw - inp["lookx"] * 0.12)
        self.cam_pitch = max(-55, min(10, self.cam_pitch - inp["looky"] * 0.10))

        # movement relative to camera yaw (A=left D=right)
        fy = math.radians(self.cam_yaw)
        fx, fyv = -math.sin(fy), math.cos(fy)
        rx, ry = fyv, -fx  # right vector
        mx = my = 0.0
        if inp["w"]: mx += fx; my += fyv
        if inp["s"]: mx -= fx; my -= fyv
        if inp["a"]: mx -= rx; my -= ry   # A = left
        if inp["d"]: mx += rx; my += ry   # D = right
        ml = math.hypot(mx, my)
        if ml > 1e-4:
            mx /= ml; my /= ml
            p.facing = math.degrees(math.atan2(-mx, my))

        speed = 9.5
        if self.meta["wonder"] == "boost":
            speed = 12.5
        if self.meta["wonder"] == "giant":
            speed = 11.0
        if p.dash_t > 0:
            speed = 22.0

        # grind rails
        if p.grinding and p.rail:
            (a, b) = p.rail
            p.rail_t += d * 8.0 / max(0.5, math.dist(a, b))
            if p.rail_t >= 1.0:
                p.grinding = False; p.rail = None
                p.vx, p.vy = (b[0] - a[0]), (b[1] - a[1])
                L = math.hypot(p.vx, p.vy) or 1
                p.vx *= 10 / L; p.vy *= 10 / L
                p.vz = 4.0
            else:
                t = p.rail_t
                p.x = a[0] + (b[0] - a[0]) * t
                p.y = a[1] + (b[1] - a[1]) * t
                p.z = a[2] + (b[2] - a[2]) * t + 0.35
                if inp["jump"]:
                    p.grinding = False; p.rail = None; p.vz = 11.0; p.jumps = 1
                    self.app.sfx("jump")
        else:
            # accel / friction
            if p.on_ground:
                p.vx = mx * speed
                p.vy = my * speed
            else:
                p.vx += mx * speed * 2.2 * d
                p.vy += my * speed * 2.2 * d
                sp = math.hypot(p.vx, p.vy)
                cap = speed * 1.15
                if sp > cap:
                    p.vx *= cap / sp; p.vy *= cap / sp

            # jump / double jump
            if inp["jump"]:
                if p.on_ground:
                    p.vz = 11.2; p.on_ground = False; p.jumps = 1
                    self.app.sfx("jump")
                elif p.jumps < 2:
                    p.vz = 10.0; p.jumps = 2
                    self.app.sfx("djump")

            # dash
            p.dash_cd = max(0, p.dash_cd - d)
            p.dash_t = max(0, p.dash_t - d)
            if inp["dash"] and p.dash_cd <= 0:
                dx, dy = mx, my
                if math.hypot(dx, dy) < 1e-4:
                    r = math.radians(p.facing); dx, dy = -math.sin(r), math.cos(r)
                p.vx, p.vy = dx * 24, dy * 24
                p.dash_t = 0.18
                p.dash_cd = 0.85 if self.meta["wonder"] != "boost" else 0.35
                if not p.on_ground:
                    p.vz = max(p.vz, 2.0)
                self.app.sfx("dash")

            # gravity (flip wonder: gentle reverse after leaving ground for a bit)
            g = self.grav
            if self.meta["wonder"] == "flip":
                self.flip_phase += d
                # oscillating soft gravity for a dreamy invert feel
                g = 18.0 * math.cos(self.flip_phase * 0.7)
            p.vz -= g * d
            p.vz = max(-32, min(24, p.vz))

            # integrate
            p.x += p.vx * d
            p.y += p.vy * d
            p.z += p.vz * d

            # side collide
            p.x, p.y = self.world.collide_sides(p.x, p.y, p.z, rad=0.28 * p.scale, height=1.5 * p.scale)

            # ground
            feet = p.z
            h = self.world.height_at(p.x, p.y, feet, rad=0.28 * p.scale, max_step=0.6 * p.scale)
            was = p.on_ground
            if h is not None and p.vz <= 0.05:
                p.z = h; p.vz = 0; p.on_ground = True; p.jumps = 0
                if not was:
                    self.app.sfx("land", vol=0.5)
            else:
                p.on_ground = False

            # try mount rail
            if p.on_ground or p.vz < 2:
                for a, b in self.world.rails:
                    # distance to segment in XY
                    ax, ay, az = a; bx, by, bz = b
                    abx, aby = bx - ax, by - ay
                    t = 0
                    den = abx * abx + aby * aby
                    if den > 1e-6:
                        t = max(0, min(1, ((p.x - ax) * abx + (p.y - ay) * aby) / den))
                    qx, qy, qz = ax + abx * t, ay + aby * t, az + (bz - az) * t
                    if math.hypot(p.x - qx, p.y - qy) < 0.55 and abs(p.z - qz) < 0.7:
                        p.grinding = True; p.rail = (a, b); p.rail_t = t
                        p.vx = p.vy = p.vz = 0
                        break

        # coins
        for c in self.world.coins:
            if c["taken"]:
                continue
            if (p.x - c["x"]) ** 2 + (p.y - c["y"]) ** 2 + (p.z + 0.8 - c["z"]) ** 2 < (0.7 * p.scale) ** 2:
                c["taken"] = True
                c["np"].hide()
                self.coins += 1
                self.app.sfx("collect")

        # spin coins
        for c in self.world.coins:
            if not c["taken"]:
                c["np"].set_h(self.time * 120)
                c["np"].set_z(c["z"] + math.sin(self.time * 3 + c["x"]) * 0.08)

        # hazards / fall
        p.invuln = max(0, p.invuln - d)
        if self.world.in_hazard(p.x, p.y, p.z) and p.invuln <= 0:
            self._hurt()

        # goal
        if self.world.near_goal(p.x, p.y, p.z + 0.8):
            self._clear()

        # animate figure lightly
        if p.np:
            p.np.set_pos(p.x, p.y, p.z)
            p.np.set_h(p.facing)
            p.np.set_scale(p.scale)
            # bob skirt / sway
            sk = p.np.get_python_tag("skirt")
            if sk:
                sk.set_r(math.sin(self.time * (10 if math.hypot(p.vx, p.vy) > 1 else 2)) * (6 if not p.on_ground else 3))
            arms = p.np.get_python_tag("arms") or []
            for i, arm in enumerate(arms):
                arm.set_p(math.sin(self.time * 8 + i) * (18 if math.hypot(p.vx, p.vy) > 1 else 4))
            if p.invuln > 0 and int(self.time * 20) % 2 == 0:
                p.np.set_color_scale(1, 0.7, 0.75, 0.55)
            else:
                p.np.set_color_scale(1, 1, 1, 1)

        self._update_camera(dt)
        self.hud.update(dt)

    def _hurt(self):
        p = self.player
        self.app.sfx("hurt")
        self.lives -= 1
        self.shake = 0.5
        if self.lives < 0:
            self.fail = True
            self.banner = "STAGE FAILED"
            self.banner_t = 3.0
            self.app.taskMgr.doMethodLater(2.0, lambda t: self.app.on_stage_fail(), "fail")
            return
        p.reset(self.world.spawn, scale=p.scale)
        p.invuln = 1.5
        self.banner = "RETRY"
        self.banner_t = 1.2

    def _clear(self):
        if self.clear:
            return
        self.clear = True
        self.app.sfx("goal")
        try: self.app.play_music("clear")
        except Exception: pass
        # rank by time + coins
        t = self.time
        ratio = self.coins / max(1, self.coins_total)
        par = 45 + self.meta["index"] * 6 + self.meta["world"] * 3
        if t < par * 0.7 and ratio > 0.85:
            self.rank = "S"
        elif t < par and ratio > 0.6:
            self.rank = "A"
        elif t < par * 1.35:
            self.rank = "B"
        else:
            self.rank = "C"
        self.banner = "STAGE CLEAR  ·  RANK %s" % self.rank
        self.banner_t = 4.0
        self.app.on_stage_clear(self.meta["id"], self.coins, self.time, self.rank)

    # ---------------------------------------------------------------- AUTO CAMERA
    def _ground_below(self, x, y, z):
        """Highest solid top at/below z under (x, y), or None."""
        best = None
        for x0, y0, z0, x1, y1, z1 in self.world.boxes:
            if x0 <= x <= x1 and y0 <= y <= y1 and z1 <= z + 0.1:
                if best is None or z1 > best:
                    best = z1
        return best

    def _cam_ray_hit(self, ax, ay, az, bx, by, bz):
        """Fraction t in [0,1] along A->B where the segment first enters a solid box (slab test)."""
        dx, dy, dz = bx - ax, by - ay, bz - az
        tmin_all = 1.0
        for x0, y0, z0, x1, y1, z1 in self.world.boxes:
            t0, t1 = 0.0, 1.0
            ok = True
            for o, d, lo, hi in ((ax, dx, x0, x1), (ay, dy, y0, y1), (az, dz, z0, z1)):
                if abs(d) < 1e-9:
                    if o < lo or o > hi:
                        ok = False; break
                else:
                    ta, tb = (lo - o) / d, (hi - o) / d
                    if ta > tb: ta, tb = tb, ta
                    t0 = max(t0, ta); t1 = min(t1, tb)
                    if t0 > t1:
                        ok = False; break
            if ok and t0 > 0.02 and t0 < tmin_all:
                tmin_all = t0
        return tmin_all

    def _auto_camera(self, dt):
        """Automatic third-person framing: swing behind the run direction, lead into turns,
        tilt to show landings on jumps, ease back behind Miyoyazu when idle."""
        p = self.player
        if self.cam_manual_t > 0:
            self.cam_manual_t = max(0.0, self.cam_manual_t - dt)
            return
        sp = math.hypot(p.vx, p.vy)
        if p.grinding and p.rail:
            (a, b) = p.rail
            hx, hy, sp = b[0] - a[0], b[1] - a[1], 8.0
        else:
            hx, hy = p.vx, p.vy
        if sp > 1.2:
            self.cam_idle_t = 0.0
            want = math.degrees(math.atan2(-hx, hy))
            diff = _ang_wrap(want - self.cam_yaw)
            # do not whip around when backing toward the camera; swing harder into sideways turns
            if abs(diff) > 150:
                rate = 0.0
            else:
                side = abs(math.sin(math.radians(diff)))
                rate = (0.9 + 1.6 * side) * min(1.0, sp / 9.5)
                if p.dash_t > 0:
                    rate *= 1.6
                if not p.on_ground:
                    rate *= 0.55  # steadier in the air so jumps stay readable
            self.cam_yaw = _ang_wrap(self.cam_yaw + diff * min(1.0, rate * dt))
        else:
            # idle: after a beat, drift back behind where Miyoyazu faces
            self.cam_idle_t += dt
            if self.cam_idle_t > 0.9:
                diff = _ang_wrap(p.facing - self.cam_yaw)
                if abs(diff) < 160:
                    self.cam_yaw = _ang_wrap(self.cam_yaw + diff * min(1.0, 1.2 * dt))
        # auto pitch: neutral run, look down into falls / gaps, a little up on a rising jump
        want_p = -16.0
        if not p.on_ground and not p.grinding:
            if p.vz < -2:
                want_p = -16.0 - min(16.0, (-p.vz - 2) * 1.4)
            elif p.vz > 4:
                want_p = -11.0
        if p.dash_t > 0:
            want_p = -12.0
        self.cam_pitch += (want_p - self.cam_pitch) * min(1.0, dt * 2.2)

    def _update_camera(self, dt):
        """FIREOUT SHINE style third-person / over-shoulder follow with AUTO CAMERA."""
        a = self.app
        p = self.player
        if self.auto_cam:
            self._auto_camera(dt)
        self.shake = max(0, self.shake - dt * 2)
        sh = (random.uniform(-1, 1) * self.shake * 0.2, random.uniform(-1, 1) * self.shake * 0.2)
        dist, hgt = 5.2, 2.15
        if self.meta["wonder"] == "giant":
            dist, hgt = 7.5, 3.2
        sp = math.hypot(p.vx, p.vy)
        # pull out a little with speed / dash, tighten when idle
        dist += min(1.1, sp * 0.07) + (0.9 if p.dash_t > 0 else 0.0)
        r = math.radians(self.cam_yaw)
        fx, fy = -math.sin(r), math.cos(r)
        # slight over-shoulder offset to the right
        ox, oy = fy * 0.55, -fx * 0.55
        # look-ahead: lead the frame along velocity so turns and jump arcs open up in front
        lead_x, lead_y = p.vx * 0.22, p.vy * 0.22
        ll = math.hypot(lead_x, lead_y)
        if ll > 2.6:
            lead_x *= 2.6 / ll; lead_y *= 2.6 / ll
        kl = min(1.0, dt * 3.5)
        self.cam_lead[0] += (lead_x - self.cam_lead[0]) * kl
        self.cam_lead[1] += (lead_y - self.cam_lead[1]) * kl
        # vertical framing: in the air, aim between Miyoyazu and the predicted landing
        look_z = p.z + 1.15 * p.scale
        if not p.on_ground and not p.grinding and p.vz < 0:
            g = self._ground_below(p.x + p.vx * 0.45, p.y + p.vy * 0.45, p.z)
            if g is not None:
                look_z = max(g + 0.9, look_z - min(2.2, (p.z - g) * 0.45))
        if self.cam_air_z is None:
            self.cam_air_z = look_z
        self.cam_air_z += (look_z - self.cam_air_z) * min(1.0, dt * 5)
        piv_x, piv_y, piv_z = p.x + self.cam_lead[0] * 0.5, p.y + self.cam_lead[1] * 0.5, self.cam_air_z
        pr = math.radians(self.cam_pitch)
        tx = piv_x - fx * dist * math.cos(pr) * 1.0 + ox
        ty = piv_y - fy * dist * math.cos(pr) * 1.0 + oy
        tz = p.z + hgt + (-math.sin(pr) - 0.276) * dist * 0.55
        # soft collision: pull in toward Miyoyazu when a wall/platform blocks the view
        if self.auto_cam:
            hx0, hy0, hz0 = p.x, p.y, p.z + 1.2 * p.scale
            t = self._cam_ray_hit(hx0, hy0, hz0, tx, ty, tz)
            if t < 1.0:
                full = math.dist((hx0, hy0, hz0), (tx, ty, tz))
                keep = max(1.3, full * t - 0.35) / max(1e-3, full)
                tx = hx0 + (tx - hx0) * keep
                ty = hy0 + (ty - hy0) * keep
                tz = hz0 + (tz - hz0) * keep + (1.0 - keep) * 0.8  # lift a touch over the blocker
        if self.cam_pos is None or math.dist(self.cam_pos, (tx, ty, tz)) > 12.0:
            self.cam_pos = [tx, ty, tz]  # respawn / teleport: cut, don't swoop
            self.cam_air_z = look_z; piv_z = look_z
        # pull in fast when blocked, ease back out slowly
        cur = math.dist((p.x, p.y), (self.cam_pos[0], self.cam_pos[1]))
        nxt = math.dist((p.x, p.y), (tx, ty))
        k = min(1, dt * (11 if nxt < cur - 0.2 else 6))
        self.cam_pos[0] += (tx - self.cam_pos[0]) * k
        self.cam_pos[1] += (ty - self.cam_pos[1]) * k
        self.cam_pos[2] += (tz - self.cam_pos[2]) * k
        cam = a.camera
        cam.set_pos(self.cam_pos[0] + sh[0], self.cam_pos[1] + sh[1], self.cam_pos[2])
        cam.look_at(piv_x + fx * 2.2 + self.cam_lead[0] * 0.6 + ox * 0.3,
                    piv_y + fy * 2.2 + self.cam_lead[1] * 0.6 + oy * 0.3, piv_z)
        fov = 62 + (8 if p.dash_t > 0 else 0) + min(3.0, sp * 0.2)
        a.camLens.set_fov(fov)
        # update shader campos
        a.world_root.set_shader_input("campos", cam.get_pos())
        if p.np:
            p.np.set_shader_input("campos", cam.get_pos())


class Hud:
    """Romantic rose/gold gameplay HUD — soft panels, elegant type, no bloom."""

    def __init__(self, app, session):
        self.app = app
        self.s = session
        self.root = app.aspect2d.attach_new_node("hud")
        f, fp = app.font, app.fontp
        # top-left: lives in a soft rose frame
        self.life_frame = DirectFrame(parent=self.root, frameColor=PANEL, frameSize=(0.04, 0.72, -0.12, 0.08),
                                      pos=(-app.getAspectRatio() + 0.08, 0, 0.88), relief=None)
        DirectFrame(parent=self.life_frame, frameColor=PANEL_EDGE, frameSize=(0.04, 0.72, 0.075, 0.082), relief=None)
        DirectFrame(parent=self.life_frame, frameColor=PANEL_EDGE, frameSize=(0.04, 0.72, -0.12, -0.113), relief=None)
        self.lives_t = OnscreenText(parent=self.life_frame, text="", pos=(0.12, -0.04), scale=0.048,
                                    fg=ROSE, align=TextNode.A_left, font=f, shadow=(0.1, 0.05, 0.08, 0.65))
        # top-center: stage name ribbon
        self.stage_t = OnscreenText(parent=self.root, text=session.meta["name"], pos=(0, 0.90), scale=0.042,
                                    fg=GOLD_SOFT, font=f, shadow=(0.1, 0.06, 0.08, 0.7))
        self.wonder_t = OnscreenText(parent=self.root, text=session.meta["wonder_name"] or "", pos=(0, 0.84), scale=0.032,
                                     fg=ROSE, font=fp, shadow=(0.1, 0.05, 0.08, 0.6))
        # top-right: coins + timer framed
        ar = app.getAspectRatio()
        self.stat_frame = DirectFrame(parent=self.root, frameColor=PANEL, frameSize=(-0.72, -0.04, -0.16, 0.08),
                                      pos=(ar - 0.08, 0, 0.88), relief=None)
        DirectFrame(parent=self.stat_frame, frameColor=PANEL_EDGE, frameSize=(-0.72, -0.04, 0.075, 0.082), relief=None)
        DirectFrame(parent=self.stat_frame, frameColor=PANEL_EDGE, frameSize=(-0.72, -0.04, -0.16, -0.113), relief=None)
        self.coin_t = OnscreenText(parent=self.stat_frame, text="", pos=(-0.12, -0.01), scale=0.045,
                                   fg=GOLD, align=TextNode.A_right, font=f, shadow=(0.1, 0.06, 0.05, 0.65))
        self.time_t = OnscreenText(parent=self.stat_frame, text="", pos=(-0.12, -0.08), scale=0.038,
                                   fg=CREAM, align=TextNode.A_right, font=fp, shadow=(0.1, 0.06, 0.08, 0.65))
        # banner
        self.ban = OnscreenText(parent=self.root, text="", pos=(0, 0.25), scale=0.08,
                                fg=GOLD, font=f, shadow=(0.12, 0.06, 0.08, 0.85))
        self.bansub = OnscreenText(parent=self.root, text="", pos=(0, 0.16), scale=0.038,
                                   fg=ROSE, font=fp, shadow=(0.1, 0.05, 0.08, 0.75))
        # bottom hint
        self.hint = OnscreenText(parent=self.root, text="WASD move  ·  Space jump  ·  Shift dash  ·  AUTO CAMERA (mouse to peek)  ·  C toggle",
                                 pos=(0, -0.92), scale=0.028, fg=(0.85, 0.7, 0.72, 0.7), font=fp)

    def destroy(self):
        if self.root:
            self.root.remove_node()
        self.root = None

    def update(self, dt):
        s = self.s
        n = max(0, s.lives + 1)
        self.lives_t.setText(("LIVES   " + " ".join(["I"] * n)) if n else "LIVES   -")
        self.lives_t.setFg(ROSE if s.lives > 0 else HEART)
        self.coin_t.setText("COINS  %d / %d" % (s.coins, s.coins_total))
        m, sec = divmod(int(s.time), 60)
        self.time_t.setText("TIME  %d:%02d" % (m, sec))
        if s.banner_t > 0:
            self.ban.setText(s.banner)
            self.ban.show()
            if s.clear:
                self.bansub.setText("%d coins  ·  %.1fs" % (s.coins, s.time)); self.bansub.show()
            else:
                self.bansub.hide()
        else:
            self.ban.hide(); self.bansub.hide()
