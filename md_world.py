"""MIYOYAZU DASH stages: 6 worlds x 10 stages = 60. Procedural layouts, EX Inc. original themes.
©2026 EX Inc./HYPERION DIGITAL ©2026"""
import math, random
from panda3d.core import NodePath, Vec3
import md_gfx as G

WORLDS = [
    dict(id="ruins", name="STONE RUINS", light="ruins",
         tagline="Broken stairs and ancient stone — match the cover path.",
         col_ground=(0.52, 0.48, 0.42, 1), col_plat=(0.58, 0.54, 0.48, 1),
         col_accent=(0.40, 0.38, 0.34, 1), fog_hint="overcast ruins"),
    dict(id="park", name="HIKARI PARK", light="park",
         tagline="Tokyo-adjacent green park paths and low walls.",
         col_ground=(0.35, 0.48, 0.28, 1), col_plat=(0.55, 0.52, 0.45, 1),
         col_accent=(0.25, 0.45, 0.22, 1), fog_hint="daylight park"),
    dict(id="neon", name="NEON PATH", light="neon",
         tagline="Night neon walkways and floating pads.",
         col_ground=(0.12, 0.10, 0.18, 1), col_plat=(0.25, 0.18, 0.40, 1),
         col_accent=(0.70, 0.20, 0.55, 1), fog_hint="neon night"),
    dict(id="autumn", name="AUTUMN GARDEN", light="autumn",
         tagline="Fallen leaves, wooden decks, warm cliffs.",
         col_ground=(0.45, 0.32, 0.18, 1), col_plat=(0.55, 0.38, 0.22, 1),
         col_accent=(0.70, 0.35, 0.15, 1), fog_hint="autumn haze"),
    dict(id="winter", name="WINTER CLIFF", light="winter",
         tagline="Icy ledges and wind-bitten stone.",
         col_ground=(0.72, 0.76, 0.82, 1), col_plat=(0.62, 0.66, 0.72, 1),
         col_accent=(0.85, 0.88, 0.92, 1), fog_hint="cold air"),
    dict(id="spring", name="SPRING BLOSSOM", light="spring",
         tagline="Petal paths and soft pink stone bridges.",
         col_ground=(0.55, 0.48, 0.50, 1), col_plat=(0.72, 0.58, 0.62, 1),
         col_accent=(0.90, 0.55, 0.65, 1), fog_hint="petal mist"),
]

# wonder twists — EX Inc. original names, no franchise terms
WONDERS = {
    None: None,
    "flip": "SKY FLIP",       # gravity toward ceiling briefly / inverted jump feel via updraft
    "giant": "GIANT STEP",    # player scale up
    "slow": "TIME VEIL",      # time slow
    "boost": "RUSH WIND",     # permanent dash refill / faster run
    "lowgrav": "LIGHT FALL",  # lower gravity
}


def stage_id(world_i, stage_i):
    return world_i * 10 + stage_i + 1  # 1..60


def stage_meta(sid):
    """sid 1..60"""
    wi = (sid - 1) // 10
    si = (sid - 1) % 10
    w = WORLDS[wi]
    # wonder on stages 3,6,9 of each world (and boss-ish 10)
    wonder = None
    if si == 2: wonder = "slow"
    elif si == 5: wonder = "giant"
    elif si == 8: wonder = "lowgrav"
    elif si == 9: wonder = ["flip", "boost", "slow"][wi % 3]
    name = "%s %02d" % (w["name"], si + 1)
    return dict(id=sid, world=wi, index=si, world_id=w["id"], world_name=w["name"],
                name=name, wonder=wonder, wonder_name=WONDERS.get(wonder),
                light=w["light"], cols=w)


def all_stages():
    return [stage_meta(i) for i in range(1, 61)]


class StageWorld:
    """Built geometry + collision AABBs for one stage."""

    def __init__(self, app, meta):
        self.app = app
        self.meta = meta
        self.root = app.render.attach_new_node("stage")
        self.boxes = []   # (x0,y0,z0,x1,y1,z1) solid
        self.coins = []   # dict x,y,z,np, taken
        self.hazards = [] # (x0,y0,z0,x1,y1,z1)
        self.goal = None  # (x,y,z)
        self.spawn = (0, 0, 1.2)
        self.rails = []   # optional grind segments [(x0,y0,z0),(x1,y1,z1)]
        self._build()

    def clear(self):
        if self.root:
            self.root.remove_node()
        self.root = None

    def _add_box(self, x0, y0, z0, x1, y1, z1, col, solid=True, gvar=0.45):
        if x1 < x0: x0, x1 = x1, x0
        if y1 < y0: y0, y1 = y1, y0
        if z1 < z0: z0, z1 = z1, z0
        G.build_platform(self.root, x0, y0, z0, x1, y1, z1, col, gvar=gvar)
        if solid:
            self.boxes.append((x0, y0, z0, x1, y1, z1))

    def _coin(self, x, y, z):
        np = G.build_coin(self.root)
        np.set_pos(x, y, z)
        self.coins.append(dict(x=x, y=y, z=z, np=np, taken=False))

    def _build(self):
        m = self.meta
        rnd = random.Random(1000 + m["id"] * 97)
        cols = m["cols"]
        cg, cp, ca = cols["col_ground"], cols["col_plat"], cols["col_accent"]
        wi, si = m["world"], m["index"]

        # Classic challenge ramp across 60 stages (world*10 + stage):
        # early = learn jump/dash; mid = gap + height reads; late = tight plats, long gaps, wonder pressure.
        prog = wi * 10 + si                         # 0..59
        length = 50 + prog * 2.2 + si * 4           # longer runs later
        gap_chance = min(0.72, 0.10 + prog * 0.009 + si * 0.02)
        gap_min = 0.9 + prog * 0.035                # must dash/double-jump later
        gap_span = 1.0 + prog * 0.045
        plat_h_var = 0.55 + prog * 0.028
        plat_w_base = max(1.15, 2.6 - prog * 0.022) # narrower platforms
        plat_d_base = max(1.1, 2.4 - prog * 0.018)
        coin_density = 0.50 + min(0.25, prog * 0.004)
        n_plats = 12 + si * 2 + wi * 2 + prog // 8
        hazard_gap = 1.55 + prog * 0.012            # fall death under shorter gaps later

        # starting plaza (always fair)
        self._add_box(-4, -3, -0.4, 4, 4, 0.0, cg, gvar=0.6)
        self.spawn = (0.0, 0.0, 1.1)

        # decorative backdrop for ruins world 0 — stepped stone like the cover
        if wi == 0:
            self._add_box(-9, -3, 0, -5.5, 12, 5 + si * 0.4, ca, solid=False, gvar=0.35)
            self._add_box(5.5, -3, 0, 9, 12, 4.5 + si * 0.3, ca, solid=False, gvar=0.35)
            for k, h in enumerate((2.0, 3.2, 4.0, 3.0, 2.4)):
                self._add_box(-5.5 + k * 0.7, -2.5, 0, -4.8 + k * 0.7, -1.8, h, ca, solid=False, gvar=0.3)
            # arch door hint at start
            self._add_box(-1.6, 2.2, 0, -1.15, 2.9, 3.2, ca, solid=False)
            self._add_box(1.15, 2.2, 0, 1.6, 2.9, 3.2, ca, solid=False)
            self._add_box(-1.6, 2.2, 3.0, 1.6, 2.9, 3.55, ca, solid=False)
            self._add_box(-0.9, 2.35, 0.2, 0.9, 2.75, 2.9, (0.35, 0.25, 0.18, 1), solid=False)

        y = 4.0
        z_floor = 0.0
        lane = 0.0
        for i in range(n_plats):
            # platform size shrinks with progress; late stages need precise landings
            pw = plat_w_base + rnd.random() * (1.4 - prog * 0.012)
            pd = plat_d_base + rnd.random() * (1.6 - prog * 0.010)
            pw = max(1.05, pw); pd = max(0.95, pd)
            # height change — more frequent and taller later
            if rnd.random() < (0.45 + prog * 0.006):
                z_floor = max(0.0, z_floor + rnd.uniform(-plat_h_var, plat_h_var * (1.15 + prog * 0.01)))
            # lateral shift / zigzag — harder reads mid-late
            if rnd.random() < (0.35 + prog * 0.005):
                lane = max(-6.0, min(6.0, lane + rnd.uniform(-2.2 - prog * 0.02, 2.2 + prog * 0.02)))
            # gap: early forgiving, late requires double-jump or dash
            if rnd.random() < gap_chance:
                gap = gap_min + rnd.random() * gap_span
                # every few plats, a "crux" gap
                if i > 0 and i % max(3, 8 - wi) == 0:
                    gap += 0.55 + prog * 0.02
            else:
                gap = 0.35 + rnd.random() * 0.35
            y += gap
            x0, x1 = lane - pw / 2, lane + pw / 2
            y0, y1 = y, y + pd
            thick = 0.45 if wi != 4 else 0.35
            self._add_box(x0, y0, z_floor - thick, x1, y1, z_floor, cp, gvar=0.5)
            # stone lip for readable edges
            lip = 0.08
            self._add_box(x0 - lip, y0 - lip, z_floor, x1 + lip, y1 + lip, z_floor + 0.06, ca, gvar=0.35)

            # coins on platform
            ncoins = 1 + (1 if rnd.random() < coin_density else 0) + (1 if rnd.random() < 0.25 else 0)
            for c in range(ncoins):
                cx = lane + rnd.uniform(-pw * 0.35, pw * 0.35)
                cy = y + pd * (0.25 + 0.5 * c / max(1, ncoins - 1))
                cz = z_floor + 0.55 + (0.4 if c == 1 and rnd.random() < 0.4 else 0)
                self._coin(cx, cy, cz)

            # occasional stepping stone / floating pad
            if rnd.random() < min(0.62, 0.28 + prog * 0.005):
                sy = y1 + 0.8 + rnd.random() * 1.2
                sz = z_floor + rnd.uniform(0.8, 1.8)
                sw = 1.1 + rnd.random() * 0.6
                self._add_box(lane - sw / 2, sy, sz - 0.3, lane + sw / 2, sy + 1.2, sz, ca, gvar=0.4)
                self._coin(lane, sy + 0.6, sz + 0.5)

            # neon floating rings of pads
            if wi == 2 and rnd.random() < 0.3:
                for k in range(3):
                    a = k * 2.1
                    fx = lane + math.cos(a) * 2.2
                    fy = y + pd * 0.5 + math.sin(a) * 0.5
                    fz = z_floor + 1.2 + k * 0.4
                    self._add_box(fx - 0.6, fy - 0.6, fz - 0.25, fx + 0.6, fy + 0.6, fz, cols["col_accent"], gvar=0.2)

            # hazard pits (kill volumes below gaps) — marked as hazards under the gap
            if gap > hazard_gap:
                self.hazards.append((lane - 7, y - gap + 0.15, -8, lane + 7, y - 0.15, -1.5))

            # grind rail on some park/winter stages
            if wi in (1, 4) and rnd.random() < max(0.06, 0.24 - prog * 0.002):
                rx0, ry0 = lane - pw * 0.4, y + 0.2
                rx1, ry1 = lane + pw * 0.4, y + pd - 0.2
                rz = z_floor + 0.15
                self.rails.append(((rx0, ry0, rz), (rx1, ry1, rz)))
                # thin rail mesh
                G.build_platform(self.root, rx0 - 0.05, ry0, rz, rx1 + 0.05, ry1, rz + 0.08, (0.7, 0.7, 0.75, 1), gvar=0.1)

            y = y1

        # final stretch + goal
        y += 1.5
        fin_w = max(2.2, 3.5 - prog * 0.015)
        self._add_box(-fin_w, y, z_floor - 0.4, fin_w, y + 6, z_floor, cg, gvar=0.55)
        for c in range(5):
            self._coin((-1.5 + c * 0.75), y + 2.5, z_floor + 0.6)
        gx, gy, gz = 0.0, y + 4.5, z_floor
        gn = G.build_goal(self.root)
        gn.set_pos(gx, gy, gz)
        self.goal = (gx, gy, gz + 1.5)

        # far ground + sky plates (readable 3D depth, not an empty black void)
        void_col = (0.10, 0.09, 0.14, 1) if wi == 2 else (0.22, 0.20, 0.18, 1)
        G.build_platform(self.root, -50, -20, -10, 50, y + 40, -9.5, void_col, gvar=0.15)
        # sky dome-ish large inverted box (unlit look via bright colour)
        sky = {
            0: (0.62, 0.66, 0.74, 1), 1: (0.55, 0.70, 0.85, 1), 2: (0.08, 0.06, 0.16, 1),
            3: (0.75, 0.55, 0.40, 1), 4: (0.70, 0.78, 0.88, 1), 5: (0.78, 0.68, 0.78, 1),
        }[wi]
        G.build_platform(self.root, -80, -40, 28, 80, y + 60, 30, sky, gvar=0.0)
        # back wall for depth
        G.build_platform(self.root, -30, y + 20, -2, 30, y + 22, 18, cols["col_accent"], gvar=0.25)

        # tree / blossom accents (simple columns)
        if wi in (1, 3, 5):
            for _ in range(6 + si):
                tx = rnd.uniform(-10, 10)
                ty = rnd.uniform(0, y)
                mb_col = (0.35, 0.22, 0.12, 1) if wi != 5 else (0.45, 0.35, 0.30, 1)
                leaf = (0.25, 0.55, 0.2, 1) if wi == 1 else ((0.75, 0.35, 0.15, 1) if wi == 3 else (0.95, 0.65, 0.75, 1))
                G.build_platform(self.root, tx - 0.15, ty - 0.15, 0, tx + 0.15, ty + 0.15, 2.2, mb_col, gvar=0.2)
                G.build_platform(self.root, tx - 0.7, ty - 0.7, 2.0, tx + 0.7, ty + 0.7, 3.0, leaf, gvar=0.15)

    def height_at(self, x, y, z, rad=0.28, max_step=0.55):
        """Top surface under feet if any; else None."""
        best = None
        for x0, y0, z0, x1, y1, z1 in self.boxes:
            if x + rad < x0 or x - rad > x1 or y + rad < y0 or y - rad > y1:
                continue
            if z1 <= z + 0.08 and z1 >= z - max_step - 0.15:
                if best is None or z1 > best:
                    best = z1
        return best

    def collide_sides(self, x, y, z, rad=0.28, height=1.4):
        """Push out of solid boxes horizontally."""
        for x0, y0, z0, x1, y1, z1 in self.boxes:
            if z + 0.1 >= z1 or z + height <= z0:
                continue
            # overlap test expanded by rad
            if x + rad <= x0 or x - rad >= x1 or y + rad <= y0 or y - rad >= y1:
                continue
            # push along smallest penetration
            pen = [
                (x + rad - x0, -1, 0),   # push -X (hit +side of box from right? wait)
                (x1 - (x - rad), 1, 0),
                (y + rad - y0, 0, -1),
                (y1 - (y - rad), 0, 1),
            ]
            # correct: if overlapping, push out by min penetration
            px_l = (x + rad) - x0   # how much we're past left face -> push left (-)
            px_r = x1 - (x - rad)
            py_b = (y + rad) - y0
            py_t = y1 - (y - rad)
            opts = [(px_l, -px_l, 0), (px_r, px_r, 0), (py_b, 0, -py_b), (py_t, 0, py_t)]
            opts = [o for o in opts if o[0] > 0]
            if not opts:
                continue
            opts.sort(key=lambda o: o[0])
            _, dx, dy = opts[0]
            # only push if penetration is small (not fully inside tall stack)
            if opts[0][0] < rad * 2.2:
                x += dx; y += dy
        return x, y

    def in_hazard(self, x, y, z):
        for x0, y0, z0, x1, y1, z1 in self.hazards:
            if x0 <= x <= x1 and y0 <= y <= y1 and z0 <= z <= z1:
                return True
        if z < -6:
            return True
        return False

    def near_goal(self, x, y, z, r=1.6):
        if not self.goal:
            return False
        gx, gy, gz = self.goal
        return (x - gx) ** 2 + (y - gy) ** 2 + (z - gz) ** 2 < r * r
