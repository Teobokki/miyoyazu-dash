"""Procedural geometry helpers (batched quads / boxes into GeomNodes)."""
import math
import array
from panda3d.core import (GeomVertexFormat, GeomVertexArrayFormat, GeomVertexData, Geom, GeomTriangles, GeomNode, NodePath, InternalName)

_af = GeomVertexArrayFormat()
_af.add_column(InternalName.get_vertex(), 3, Geom.NT_float32, Geom.C_point)
_af.add_column(InternalName.get_normal(), 3, Geom.NT_float32, Geom.C_normal)
_af.add_column(InternalName.get_color(), 4, Geom.NT_float32, Geom.C_color)
_af.add_column(InternalName.get_texcoord(), 2, Geom.NT_float32, Geom.C_texcoord)
FMT = GeomVertexFormat.register_format(GeomVertexFormat(_af))


class MB:
    """Mesh builder: collect triangles, emit one GeomNode."""
    def __init__(self, name="mb"):
        self.name = name
        self.v = []      # (x,y,z, nx,ny,nz, r,g,b,a, u,v)
        self.t = []

    def __len__(self):
        return len(self.t)

    def quad(self, p0, p1, p2, p3, col=(1, 1, 1, 1), uv=((0, 0), (1, 0), (1, 1), (0, 1)), n=None):
        if n is None:
            ax, ay, az = p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2]
            bx, by, bz = p3[0] - p0[0], p3[1] - p0[1], p3[2] - p0[2]
            nx, ny, nz = ay * bz - az * by, az * bx - ax * bz, ax * by - ay * bx
            l = math.sqrt(nx * nx + ny * ny + nz * nz) or 1.0
            n = (nx / l, ny / l, nz / l)
        b = len(self.v)
        cols = col if isinstance(col[0], (tuple, list)) else (col, col, col, col)
        for p, c, t in zip((p0, p1, p2, p3), cols, uv):
            self.v.append((p[0], p[1], p[2], n[0], n[1], n[2], c[0], c[1], c[2], c[3] if len(c) > 3 else 1.0, t[0], t[1]))
        self.t.append((b, b + 1, b + 2)); self.t.append((b, b + 2, b + 3))

    def box(self, x0, y0, z0, x1, y1, z1, col=(1, 1, 1, 1), top=True, bottom=False, uvs=None, colside=None):
        cs = colside or col
        # sides (facing out)
        self.quad((x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1), cs, uvs("s", x1 - x0, z1 - z0) if uvs else ((0, 0), (1, 0), (1, 1), (0, 1)))
        self.quad((x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1), cs, uvs("e", y1 - y0, z1 - z0) if uvs else ((0, 0), (1, 0), (1, 1), (0, 1)))
        self.quad((x1, y1, z0), (x0, y1, z0), (x0, y1, z1), (x1, y1, z1), cs, uvs("n", x1 - x0, z1 - z0) if uvs else ((0, 0), (1, 0), (1, 1), (0, 1)))
        self.quad((x0, y1, z0), (x0, y0, z0), (x0, y0, z1), (x0, y1, z1), cs, uvs("w", y1 - y0, z1 - z0) if uvs else ((0, 0), (1, 0), (1, 1), (0, 1)))
        if top:
            self.quad((x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1), col)
        if bottom:
            self.quad((x0, y1, z0), (x1, y1, z0), (x1, y0, z0), (x0, y0, z0), col)

    def obox(self, cx, cy, z0, hl, hw, z1, ang, col):
        """oriented box (heading ang radians) around (cx,cy)."""
        c, s = math.cos(ang), math.sin(ang)
        def P(a, b, z):
            return (cx + a * c - b * s, cy + a * s + b * c, z)
        pts = [(-hw, -hl), (hw, -hl), (hw, hl), (-hw, hl)]
        for i in range(4):
            a, b = pts[i], pts[(i + 1) % 4]
            self.quad(P(*a, z0), P(*b, z0), P(*b, z1), P(*a, z1), col)
        self.quad(P(*pts[0], z1), P(*pts[1], z1), P(*pts[2], z1), P(*pts[3], z1), col)

    def node(self):
        vd = GeomVertexData(self.name, FMT, Geom.UH_static)
        vd.unclean_set_num_rows(len(self.v))
        buf = array.array("f", [c for x in self.v for c in x])
        mv = memoryview(vd.modify_array(0)).cast("B")
        mv[:] = buf.tobytes()
        tr = GeomTriangles(Geom.UH_static)
        tr.set_index_type(Geom.NT_uint32)
        idx = array.array("I", [i for t in self.t for i in t])
        ta = tr.modify_vertices(); ta.unclean_set_num_rows(len(idx))
        memoryview(ta).cast("B")[:] = idx.tobytes()
        g = Geom(vd); g.add_primitive(tr)
        gn = GeomNode(self.name); gn.add_geom(g)
        return NodePath(gn)
