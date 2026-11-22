"""Draws turtle's recorded lines, fills, dots and text into a PNG, in pure Python: no window, no
libraries, nothing outside Lasso's sandbox. Drawn at twice the size and scaled down, for smooth edges.
Text uses the outlines of a font macOS already has (Arial), read from its file."""
import math, os, struct, zlib

SCALE = 2

class Canvas:
    def __init__(self, width, height, background):
        self.w, self.h = width * SCALE, height * SCALE
        self.width, self.height = width, height
        bg = bytes(int(round(c * 255)) for c in background)
        self.px = bytearray(bg * (self.w * self.h))

    def to_px(self, x, y):
        return ((x + self.width / 2) * SCALE, (self.height / 2 - y) * SCALE)

    def fill(self, contours, color):
        """Fills polygons (lists of pixel points), nonzero winding, sampled at pixel centres."""
        edges = []
        ymin, ymax = self.h, -1
        for pts in contours:
            n = len(pts)
            for i in range(n):
                (x0, y0), (x1, y1) = pts[i], pts[(i + 1) % n]
                if y0 == y1:
                    continue
                d = 1 if y1 > y0 else -1
                if y0 > y1:
                    x0, y0, x1, y1 = x1, y1, x0, y0
                edges.append((y0, y1, x0, (x1 - x0) / (y1 - y0), d))
                ymin, ymax = min(ymin, y0), max(ymax, y1)
        if not edges:
            return
        c = bytes(int(round(v * 255)) for v in color)
        for row in range(max(0, int(ymin)), min(self.h, int(math.ceil(ymax)) + 1)):
            y = row + 0.5
            hits = sorted((x0 + (y - y0) * slope, d) for y0, y1, x0, slope, d in edges if y0 <= y < y1)
            wind = 0
            for i in range(len(hits) - 1):
                wind += hits[i][1]
                if wind:
                    a = max(0, int(math.ceil(hits[i][0] - 0.5)))
                    b = min(self.w, int(math.ceil(hits[i + 1][0] - 0.5)))
                    if b > a:
                        start = (row * self.w + a) * 3
                        self.px[start:start + (b - a) * 3] = c * (b - a)

    def disc(self, cx, cy, radius, color):
        n = max(12, min(64, int(radius * 1.5)))
        self.fill([[(cx + radius * math.cos(2 * math.pi * i / n), cy + radius * math.sin(2 * math.pi * i / n)) for i in range(n)]], color)

    def polyline(self, points, color, width):
        """A line through turtle points, with round joins and ends."""
        pts = [self.to_px(x, y) for x, y in points]
        half = max(0.5, width * SCALE / 2)
        quads = []
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            dx, dy = x1 - x0, y1 - y0
            length = math.hypot(dx, dy)
            if length == 0:
                continue
            nx, ny = -dy / length * half, dx / length * half
            quads.append([(x0 + nx, y0 + ny), (x1 + nx, y1 + ny), (x1 - nx, y1 - ny), (x0 - nx, y0 - ny)])
        # One fill for all of it: overlaps don't double up, and it's much faster than one per segment.
        if half > 1.2:
            n = 12
            for x, y in pts:
                quads.append([(x + half * math.cos(2 * math.pi * i / n), y + half * math.sin(2 * math.pi * i / n)) for i in range(n)])
        # Each quad's winding must agree for nonzero to union them: orient all counterclockwise.
        oriented = []
        for q in quads:
            area = sum(q[i][0] * q[(i + 1) % len(q)][1] - q[(i + 1) % len(q)][0] * q[i][1] for i in range(len(q)))
            oriented.append(q if area > 0 else q[::-1])
        if oriented:
            self.fill(oriented, color)

    def png(self, path):
        w, h, s = self.width, self.height, SCALE
        rows = []
        src = self.px
        for y in range(h):
            r0, r1 = (y * s) * self.w * 3, (y * s + 1) * self.w * 3
            a, b = src[r0:r0 + self.w * 3], src[r1:r1 + self.w * 3]
            out = bytearray(w * 3)
            for x in range(w):
                i = x * 6
                out[x * 3] = (a[i] + a[i + 3] + b[i] + b[i + 3]) >> 2
                out[x * 3 + 1] = (a[i + 1] + a[i + 4] + b[i + 1] + b[i + 4]) >> 2
                out[x * 3 + 2] = (a[i + 2] + a[i + 5] + b[i + 2] + b[i + 5]) >> 2
            rows.append(b"\x00" + bytes(out))
        def chunk(kind, data):
            return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)
        with open(path, "wb") as f:
            f.write(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
                    + chunk(b"IDAT", zlib.compress(b"".join(rows), 6)) + chunk(b"IEND", b""))

class Font:
    """Just enough TrueType to draw text: cmap (format 4), loca, glyf, hmtx."""
    PATHS = ["/System/Library/Fonts/Supplemental/Arial.ttf", "/Library/Fonts/Arial.ttf",
             "/System/Library/Fonts/Supplemental/Verdana.ttf"]
    BOLD = ["/System/Library/Fonts/Supplemental/Arial Bold.ttf", "/Library/Fonts/Arial Bold.ttf"]

    def __init__(self, bold=False):
        self.data = None
        for p in (self.BOLD if bold else []) + self.PATHS:
            try:
                with open(p, "rb") as f:
                    self.data = f.read()
                break
            except OSError:
                continue
        if not self.data:
            return
        d = self.data
        self.tables = {}
        for i in range(struct.unpack(">H", d[4:6])[0]):
            tag, _, offset, length = struct.unpack(">4sIII", d[12 + 16 * i:28 + 16 * i])
            self.tables[tag.decode("latin-1")] = offset
        head = self.tables["head"]
        self.units = struct.unpack(">H", d[head + 18:head + 20])[0]
        self.long_loca = struct.unpack(">h", d[head + 50:head + 52])[0] == 1
        hhea = self.tables["hhea"]
        self.metrics = struct.unpack(">H", d[hhea + 34:hhea + 36])[0]
        self.cmap = self._cmap()

    def _cmap(self):
        d, base = self.data, self.tables["cmap"]
        out = {}
        for i in range(struct.unpack(">H", d[base + 2:base + 4])[0]):
            platform, encoding, offset = struct.unpack(">HHI", d[base + 4 + 8 * i:base + 12 + 8 * i])
            t = base + offset
            if struct.unpack(">H", d[t:t + 2])[0] != 4 or platform not in (0, 3):
                continue
            segs = struct.unpack(">H", d[t + 6:t + 8])[0] // 2
            ends = struct.unpack(f">{segs}H", d[t + 14:t + 14 + segs * 2])
            starts = struct.unpack(f">{segs}H", d[t + 16 + segs * 2:t + 16 + segs * 4])
            deltas = struct.unpack(f">{segs}h", d[t + 16 + segs * 4:t + 16 + segs * 6])
            ro = t + 16 + segs * 6
            offsets = struct.unpack(f">{segs}H", d[ro:ro + segs * 2])
            for s in range(segs):
                for code in range(starts[s], min(ends[s], 0x24FF) + 1):
                    if offsets[s] == 0:
                        g = (code + deltas[s]) & 0xFFFF
                    else:
                        at = ro + s * 2 + offsets[s] + (code - starts[s]) * 2
                        g = struct.unpack(">H", d[at:at + 2])[0]
                        g = (g + deltas[s]) & 0xFFFF if g else 0
                    out[code] = g
            break
        return out

    def advance(self, glyph):
        h = self.tables["hmtx"]
        i = min(glyph, self.metrics - 1)
        return struct.unpack(">H", self.data[h + 4 * i:h + 4 * i + 2])[0]

    def outline(self, glyph):
        d, loca = self.data, self.tables["loca"]
        if self.long_loca:
            a, b = struct.unpack(">II", d[loca + glyph * 4:loca + glyph * 4 + 8])
        else:
            a, b = (v * 2 for v in struct.unpack(">HH", d[loca + glyph * 2:loca + glyph * 2 + 4]))
        if a == b:
            return []
        g = self.tables["glyf"] + a
        count = struct.unpack(">h", d[g:g + 2])[0]
        if count < 0:  # composite: draw its parts at their offsets
            contours, p = [], g + 10
            while True:
                flags, part = struct.unpack(">HH", d[p:p + 4]); p += 4
                if flags & 1:
                    dx, dy = struct.unpack(">hh", d[p:p + 4]); p += 4
                else:
                    dx, dy = struct.unpack(">bb", d[p:p + 2]); p += 2
                if flags & 8: p += 2
                elif flags & 0x40: p += 4
                elif flags & 0x80: p += 8
                contours += [[(x + dx, y + dy) for x, y in c] for c in self.outline(part)]
                if not flags & 0x20:
                    return contours
        ends = struct.unpack(f">{count}H", d[g + 10:g + 10 + 2 * count])
        p = g + 10 + 2 * count
        p += 2 + struct.unpack(">H", d[p:p + 2])[0]
        n = ends[-1] + 1
        flags = []
        while len(flags) < n:
            f = d[p]; p += 1
            flags.append(f)
            if f & 8:
                flags += [f] * d[p]; p += 1
        def coords(short, same):
            vals, v = [], 0
            nonlocal p
            for f in flags[:n]:
                if f & short:
                    step = d[p]; p += 1
                    v += step if f & same else -step
                elif not f & same:
                    v += struct.unpack(">h", d[p:p + 2])[0]; p += 2
                vals.append(v)
            return vals
        xs, ys = coords(2, 16), coords(4, 32)
        contours, start = [], 0
        for end in ends:
            pts = [(xs[i], ys[i], flags[i] & 1) for i in range(start, end + 1)]
            start = end + 1
            contours.append(self._flatten(pts))
        return contours

    @staticmethod
    def _flatten(pts):
        """Quadratic TrueType contour to straight segments."""
        if not pts:
            return []
        if not pts[0][2]:
            last = pts[-1]
            start = last if last[2] else ((last[0] + pts[0][0]) / 2, (last[1] + pts[0][1]) / 2, 1)
            pts = [start] + pts
        out, prev, ctrl = [(pts[0][0], pts[0][1])], pts[0], None
        for x, y, on in pts[1:] + [pts[0]]:
            if on:
                if ctrl:
                    for t in (0.25, 0.5, 0.75, 1.0):
                        u = 1 - t
                        out.append((u * u * prev[0] + 2 * u * t * ctrl[0] + t * t * x, u * u * prev[1] + 2 * u * t * ctrl[1] + t * t * y))
                else:
                    out.append((x, y))
                prev, ctrl = (x, y), None
            else:
                if ctrl:
                    mid = ((ctrl[0] + x) / 2, (ctrl[1] + y) / 2)
                    for t in (0.25, 0.5, 0.75, 1.0):
                        u = 1 - t
                        out.append((u * u * prev[0] + 2 * u * t * ctrl[0] + t * t * mid[0], u * u * prev[1] + 2 * u * t * ctrl[1] + t * t * mid[1]))
                    prev = mid
                ctrl = (x, y)
        return out

    def text(self, canvas, x, y, text, size, align, color):
        if not self.data:
            return
        scale = size / self.units
        # A character the font doesn't have (an emoji) is left out, not drawn as a box.
        glyphs = [g for g in (self.cmap.get(ord(ch), 0) for ch in text) if g]
        width = sum(self.advance(g) for g in glyphs) * scale
        x -= width / 2 if align == "center" else width if align == "right" else 0
        contours = []
        for g in glyphs:
            for c in self.outline(g):
                contours.append([canvas.to_px(x + px * scale, y + py * scale) for px, py in c])
            x += self.advance(g) * scale
        canvas.fill(contours, color)

def render(items, width, height, background, path):
    canvas = Canvas(width, height, background)
    fonts = {}
    for item in items:
        kind = item[0]
        if kind == "line" and len(item[1]) > 1:
            canvas.polyline(item[1], item[2], item[3])
        elif kind == "fill" and len(item[1]) > 2:
            canvas.fill([[canvas.to_px(x, y) for x, y in item[1]]], item[2])
        elif kind == "dot":
            cx, cy = canvas.to_px(*item[1])
            canvas.disc(cx, cy, item[2] * SCALE / 2, item[3])
        elif kind == "text":
            bold = len(item) > 6 and item[6]
            if bold not in fonts:
                fonts[bold] = Font(bold)
            fonts[bold].text(canvas, item[1][0], item[1][1], item[2], item[4] * 1.33, item[3], item[5])
    canvas.png(path)
