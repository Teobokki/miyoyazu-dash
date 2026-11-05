"""MIYOYAZU DASH graphics: FIREOUT-style wrap lighting, filmic grade (no bloom), Miyoyazu figure.
©2026 EX Inc./HYPERION DIGITAL ©2026"""
import math, random
from panda3d.core import (Shader, NodePath, Vec3, Vec4, TransparencyAttrib, Texture, PNMImage, SamplerState)
from fs_geom import MB

VERT = """#version 120
uniform mat4 p3d_ModelViewProjectionMatrix;
uniform mat4 p3d_ModelMatrix;
attribute vec4 p3d_Vertex;
attribute vec3 p3d_Normal;
attribute vec4 p3d_Color;
varying vec3 wpos;
varying vec3 wnrm;
varying vec4 vcol;
void main() {
  gl_Position = p3d_ModelViewProjectionMatrix * p3d_Vertex;
  wpos = (p3d_ModelMatrix * p3d_Vertex).xyz;
  wnrm = normalize((p3d_ModelMatrix * vec4(p3d_Normal, 0.0)).xyz);
  vcol = p3d_Color;
}"""

FRAG = """#version 120
uniform vec3 sundir;
uniform vec3 suncol;
uniform vec3 skytop;
uniform vec3 skybot;
uniform vec3 fogcol;
uniform float fogden;
uniform vec3 campos;
uniform float gvar;
uniform float gloss;
uniform float sheen;
uniform vec4 tint;
uniform vec4 p3d_ColorScale;
varying vec3 wpos;
varying vec3 wnrm;
varying vec4 vcol;
float h3(vec3 c) { return fract(sin(dot(c, vec3(12.9898, 78.233, 37.719))) * 43758.5453); }
void main() {
  vec4 base = vcol * tint;
  if (gvar > 0.0) {
    float n = h3(floor(wpos * 0.5));
    base.rgb *= mix(0.85, 1.12, n);
  }
  vec3 N = normalize(wnrm);
  vec3 V = normalize(campos - wpos);
  if (dot(N, V) < 0.0) N = -N;
  vec3 L = normalize(sundir);
  float ndl = max(dot(N, L), 0.0);
  float wrap = max((dot(N, L) + 0.4) / 1.4, 0.0);
  vec3 hemi = mix(skybot, skytop, N.z * 0.5 + 0.5);
  vec3 col = base.rgb * (hemi + suncol * mix(ndl, wrap, sheen));
  vec3 H = normalize(L + V);
  col += suncol * pow(max(dot(N, H), 0.0), mix(12.0, 48.0, gloss)) * gloss * 0.4;
  col *= p3d_ColorScale.rgb;
  float vd = length(campos - wpos);
  float f = 1.0 - exp(-fogden * fogden * vd * vd);
  col = mix(col, fogcol, clamp(f, 0.0, 0.75));
  gl_FragColor = vec4(col, base.a * p3d_ColorScale.a);
}"""
GV = """#version 120
attribute vec4 p3d_Vertex; attribute vec2 p3d_MultiTexCoord0;
varying vec2 uv; void main() { gl_Position = p3d_Vertex; uv = p3d_MultiTexCoord0; }"""
GF = """#version 120
uniform sampler2D scene; uniform float gtime; uniform float grain; uniform float warm;
varying vec2 uv;
void main() {
  vec3 c = clamp(texture2D(scene, uv).rgb, 0.0, 1.0);
  c = mix(c, c * c * (3.0 - 2.0 * c), 0.34);
  float l = dot(c, vec3(0.2126, 0.7152, 0.0722));
  c += vec3(-0.016, 0.004, 0.022) * (1.0 - l) * (1.0 - l) + vec3(0.036, 0.016, -0.026) * l * l * warm;
  c = mix(vec3(l), c, 0.94);
  vec2 d = (uv - 0.5) * vec2(1.0, 0.8); c *= mix(0.68, 1.0, smoothstep(0.8, 0.25, length(d)));
  float n = fract(sin(dot(floor(gl_FragCoord.xy) + vec2(gtime * 137.0, gtime * 61.0), vec2(12.9898, 78.233))) * 43758.5453);
  c += (n - 0.5) * grain * (0.6 + 0.4 * (1.0 - l));
  gl_FragColor = vec4(clamp(c, 0.0, 1.0), 1.0);
}"""

_sh = {}  # vert/frag cache


def shader():
    if "s" not in _sh:
        _sh["s"] = Shader.make(Shader.SL_GLSL, VERT, FRAG)
    return _sh["s"]


def grade_shader():
    if "g" not in _sh:
        _sh["g"] = Shader.make(Shader.SL_GLSL, GV, GF)
    return _sh["g"]


def setup_render(root, campos):
    root.set_shader(shader())
    for k, v in (("gvar", 0.0), ("sheen", 0.4), ("gloss", 0.28), ("tint", Vec4(1, 1, 1, 1)),
                 ("campos", campos),
                 ("sundir", Vec3(0.45, -0.35, 0.72)), ("suncol", Vec3(1.2, 1.04, 0.84)),
                 ("skytop", Vec3(0.56, 0.60, 0.68)), ("skybot", Vec3(0.50, 0.42, 0.32)),
                 ("fogcol", Vec3(0.76, 0.70, 0.60)), ("fogden", 0.0035)):
        root.set_shader_input(k, v)


LIGHTS = {
    "ruins": ((0.55, -0.4, 0.55), (1.15, 1.0, 0.88), (0.50, 0.54, 0.62), (0.42, 0.38, 0.32), (0.70, 0.68, 0.64), 0.0032, (0.95, 0.95, 1.0)),
    "park": ((0.4, -0.3, 0.75), (1.25, 1.12, 0.92), (0.55, 0.62, 0.72), (0.45, 0.50, 0.35), (0.72, 0.78, 0.70), 0.0040, (1, 1, 1)),
    "neon": ((0.2, 0.5, 0.7), (0.55, 0.45, 0.95), (0.12, 0.10, 0.22), (0.08, 0.06, 0.12), (0.08, 0.06, 0.14), 0.0065, (0.6, 0.4, 0.9)),
    "autumn": ((0.7, -0.35, 0.35), (1.35, 0.85, 0.45), (0.55, 0.45, 0.40), (0.50, 0.35, 0.22), (0.75, 0.55, 0.35), 0.0055, (1.0, 0.8, 0.55)),
    "winter": ((0.35, -0.55, 0.55), (1.05, 1.1, 1.2), (0.62, 0.68, 0.78), (0.55, 0.58, 0.62), (0.78, 0.82, 0.88), 0.0050, (0.9, 0.95, 1.05)),
    "spring": ((0.45, -0.25, 0.7), (1.2, 1.05, 0.95), (0.58, 0.62, 0.75), (0.55, 0.48, 0.55), (0.80, 0.72, 0.78), 0.0042, (1.05, 0.9, 1.0)),
}


def set_light(root, tod, base):
    s, sc, st, sb, fc, fd, et = LIGHTS[tod]
    root.set_shader_input("envtint", Vec3(*et))
    root.set_shader_input("sundir", Vec3(*s)); root.set_shader_input("suncol", Vec3(*sc))
    root.set_shader_input("skytop", Vec3(*st)); root.set_shader_input("skybot", Vec3(*sb))
    root.set_shader_input("fogcol", Vec3(*fc)); root.set_shader_input("fogden", fd)
    base.set_background_color(*fc, 1)


def _sv(mb, p, n, c, t=(0, 0)):
    mb.v.append((p[0], p[1], p[2], n[0], n[1], n[2], c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0, t[0], t[1]))
    return len(mb.v) - 1


def ellipsoid(mb, cx, cy, cz, rx, ry, rz, col, seg=12, ring=8, zmin=-1.0, zmax=1.0):
    rows = []
    for i in range(ring + 1):
        t = zmin + (zmax - zmin) * i / ring; ph = math.asin(max(-1, min(1, t)))
        r = []
        for j in range(seg + 1):
            a = 2 * math.pi * j / seg
            nx, ny, nz = math.cos(ph) * math.cos(a), math.cos(ph) * math.sin(a), math.sin(ph)
            n = (nx / rx, ny / ry, nz / rz); l = math.sqrt(sum(k * k for k in n)) or 1
            r.append(_sv(mb, (cx + rx * nx, cy + ry * ny, cz + rz * nz), (n[0] / l, n[1] / l, n[2] / l), col, (j / seg, i / ring)))
        rows.append(r)
    for i in range(ring):
        for j in range(seg):
            a, b, c, d = rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]
            mb.t.append((a, b, c)); mb.t.append((a, c, d))


def cyl(mb, x, y, z, r, l, col, axis="z", seg=10, caps=True, r2=None):
    r2 = r if r2 is None else r2
    def P(a, t, rr):
        u, v = rr * math.cos(a), rr * math.sin(a)
        return {"y": (x + u, y + t, z + v), "x": (x + t, y + u, z + v), "z": (x + u, y + v, z + t)}[axis]
    def Nn(a):
        u, v = math.cos(a), math.sin(a)
        return {"y": (u, 0, v), "x": (0, u, v), "z": (u, v, 0)}[axis]
    for j in range(seg):
        a0, a1 = 2 * math.pi * j / seg, 2 * math.pi * (j + 1) / seg
        i0 = _sv(mb, P(a0, 0, r), Nn(a0), col); i1 = _sv(mb, P(a1, 0, r), Nn(a1), col)
        i2 = _sv(mb, P(a1, l, r2), Nn(a1), col); i3 = _sv(mb, P(a0, l, r2), Nn(a0), col)
        mb.t.append((i0, i1, i2)); mb.t.append((i0, i2, i3))
        if caps:
            ax = {"y": (0, 1, 0), "x": (1, 0, 0), "z": (0, 0, 1)}[axis]
            c0 = _sv(mb, P(0, l, 0), ax, col); e0 = _sv(mb, P(a0, l, r2), ax, col); e1 = _sv(mb, P(a1, l, r2), ax, col); mb.t.append((c0, e0, e1))
            na = tuple(-k for k in ax)
            c1 = _sv(mb, P(0, 0, 0), na, col); f0 = _sv(mb, P(a0, 0, r), na, col); f1 = _sv(mb, P(a1, 0, r), na, col); mb.t.append((c1, f1, f0))


def node(mb, parent, name=None, gloss=0.25, tex=None, gvar=0.0):
    n = mb.node(); n.reparent_to(parent); n.set_name(name or mb.name)
    n.set_shader_input("gloss", gloss); n.set_shader_input("gvar", gvar)
    if tex is not None:
        n.set_texture(tex, 1)
    return n


def make_envmap():
    n = 128; img = PNMImage(n, n, 3)
    for j in range(n):
        for i in range(n):
            v = j / (n - 1); sky = (0.55 + 0.2 * v, 0.60 + 0.15 * v, 0.72 + 0.1 * v)
            gnd = (0.35, 0.32, 0.28)
            t = 1.0 / (1.0 + math.exp(-(v - 0.45) * 18))
            r = sky[0] * t + gnd[0] * (1 - t); g = sky[1] * t + gnd[1] * (1 - t); b = sky[2] * t + gnd[2] * (1 - t)
            img.set_xel(i, j, r, g, b)
    t = Texture("env"); t.load(img); t.set_wrap_u(SamplerState.WM_repeat); t.set_wrap_v(SamplerState.WM_clamp); return t


# --------------------------------------------------------------- Miyoyazu (stylized red/black dress)
SKIN = (0.88, 0.72, 0.62, 1)
HAIR = (0.08, 0.07, 0.09, 1)
DRESS_BLK = (0.08, 0.07, 0.09, 1)
DRESS_RED = (0.55, 0.08, 0.10, 1)
RED_SLV = (0.62, 0.10, 0.12, 1)
LACE = (0.25, 0.06, 0.08, 1)


def build_miyoyazu(parent, scale=1.0):
    """Stylized ~1.65 m figure in dark red/black gothic dress. Faces +Y. Not photoreal."""
    root = parent.attach_new_node("miyoyazu"); root.set_scale(scale)
    # legs under skirt (mostly hidden)
    for sd in (-1, 1):
        hip = root.attach_new_node("hip"); hip.set_pos(0.09 * sd, 0, 0.78)
        mb = MB("leg"); mb.box(-0.06, -0.06, -0.72, 0.06, 0.07, 0.0, (0.12, 0.1, 0.1, 1)); node(mb, hip, gloss=0.15)
        mb = MB("shoe"); mb.box(-0.055, -0.04, -0.78, 0.055, 0.12, -0.68, DRESS_BLK); node(mb, hip, gloss=0.45)
    # skirt (voluminous)
    sk = root.attach_new_node("skirt"); sk.set_z(0.78)
    mb = MB("skirt")
    # layered flared skirt
    for layer, (z0, z1, r0, r1, col) in enumerate([
        (0.0, 0.08, 0.22, 0.28, DRESS_BLK),
        (-0.55, 0.0, 0.32, 0.22, DRESS_BLK),
        (-0.72, -0.55, 0.36, 0.32, DRESS_RED),
    ]):
        segs = 14
        for j in range(segs):
            a0, a1 = 2 * math.pi * j / segs, 2 * math.pi * (j + 1) / segs
            def P(a, z, rr):
                return (rr * math.cos(a), rr * math.sin(a) * 0.85, z)
            p0 = P(a0, z0, r0); p1 = P(a1, z0, r0); p2 = P(a1, z1, r1); p3 = P(a0, z1, r1)
            nx, ny = math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2)
            mb.quad(p0, p1, p2, p3, col)
    node(mb, sk, gloss=0.35)
    # torso / bodice
    up = root.attach_new_node("upper"); up.set_z(0.86)
    mb = MB("bodice")
    mb.box(-0.15, -0.10, 0.0, 0.15, 0.10, 0.38, DRESS_BLK)  # black outer
    mb.box(-0.08, 0.10, 0.05, 0.08, 0.115, 0.36, DRESS_RED)  # red center panel
    # lace lines
    for z in (0.10, 0.18, 0.26, 0.34):
        mb.box(-0.02, 0.112, z, 0.02, 0.118, z + 0.03, LACE)
    mb.box(-0.16, -0.11, 0.36, 0.16, 0.11, 0.42, DRESS_BLK)  # ruffled neckline
    node(mb, up, gloss=0.3)
    # arms + red puffy sleeves
    arms = []
    for sd in (-1, 1):
        sh = up.attach_new_node("shoulder"); sh.set_pos(0.18 * sd, 0, 0.32)
        mb = MB("puff")
        ellipsoid(mb, 0, 0, 0, 0.10, 0.10, 0.12, RED_SLV, seg=10, ring=6)
        node(mb, sh, gloss=0.35)
        arm = sh.attach_new_node("arm"); arm.set_z(-0.08)
        mb = MB("fore"); cyl(mb, 0, 0, -0.28, 0.045, 0.28, DRESS_BLK, axis="z", caps=False, r2=0.04)
        mb.box(-0.05, -0.05, -0.32, 0.05, 0.05, -0.26, DRESS_BLK)  # cuff
        node(mb, arm, gloss=0.25)
        mb = MB("hand"); ellipsoid(mb, 0, 0, -0.36, 0.04, 0.035, 0.05, SKIN, seg=8, ring=5); node(mb, arm, gloss=0.2)
        arms.append(sh)
    # head
    head = up.attach_new_node("head"); head.set_z(0.52)
    mb = MB("neck"); cyl(mb, 0, 0, -0.12, 0.045, 0.1, SKIN, axis="z", caps=False)
    ellipsoid(mb, 0, 0.01, 0.02, 0.095, 0.105, 0.118, SKIN)
    mb.box(-0.015, 0.095, -0.01, 0.015, 0.12, 0.02, SKIN)  # nose
    node(mb, head, gloss=0.22)
    mb = MB("eyes")
    for sd in (-1, 1):
        ellipsoid(mb, 0.035 * sd, 0.09, 0.025, 0.016, 0.007, 0.008, (0.08, 0.06, 0.05, 1), seg=6, ring=4)
    node(mb, head, gloss=0.1)
    # short chin-length bob
    mb = MB("hair")
    ellipsoid(mb, 0, -0.01, 0.06, 0.11, 0.12, 0.11, HAIR, seg=12, ring=8, zmin=-0.15, zmax=1.0)
    # side bangs / chin length
    for sd in (-1, 1):
        ellipsoid(mb, 0.09 * sd, 0.02, -0.02, 0.04, 0.05, 0.08, HAIR, seg=8, ring=5)
    ellipsoid(mb, 0, -0.08, 0.0, 0.09, 0.04, 0.09, HAIR, seg=8, ring=5)  # back
    node(mb, head, gloss=0.15)
    root.set_python_tag("arms", arms)
    root.set_python_tag("skirt", sk)
    root.set_python_tag("head", head)
    return root


def build_coin(parent, col=(1.0, 0.82, 0.22, 1)):
    root = parent.attach_new_node("coin")
    mb = MB("coin")
    # flat disc facing camera-ish (spin in Y)
    seg = 16
    for j in range(seg):
        a0, a1 = 2 * math.pi * j / seg, 2 * math.pi * (j + 1) / seg
        x0, z0 = 0.22 * math.cos(a0), 0.22 * math.sin(a0)
        x1, z1 = 0.22 * math.cos(a1), 0.22 * math.sin(a1)
        mb.quad((x0, -0.03, z0), (x1, -0.03, z1), (x1, 0.03, z1), (x0, 0.03, z0), col)
        mb.quad((0, 0.03, 0), (x0, 0.03, z0), (x1, 0.03, z1), (0, 0.03, 0), (1.0, 0.9, 0.35, 1))
        mb.quad((0, -0.03, 0), (x1, -0.03, z1), (x0, -0.03, z0), (0, -0.03, 0), (0.85, 0.7, 0.2, 1))
    node(mb, root, gloss=0.85)
    return root


def build_goal(parent):
    root = parent.attach_new_node("goal")
    mb = MB("arch")
    STONE = (0.55, 0.52, 0.48, 1); GOLD = (0.95, 0.78, 0.3, 1)
    mb.box(-1.2, -0.3, 0, -0.85, 0.3, 3.2, STONE)
    mb.box(0.85, -0.3, 0, 1.2, 0.3, 3.2, STONE)
    mb.box(-1.2, -0.35, 3.0, 1.2, 0.35, 3.5, STONE)
    mb.box(-0.9, -0.2, 3.2, 0.9, 0.2, 3.45, GOLD)
    node(mb, root, gloss=0.4, gvar=0.3)
    return root


def build_platform(parent, x0, y0, z0, x1, y1, z1, col, gvar=0.5):
    mb = MB("plat"); mb.box(x0, y0, z0, x1, y1, z1, col, bottom=True)
    return node(mb, parent, gloss=0.2, gvar=gvar)
