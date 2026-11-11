"""Erzeugt wasserstand-14mm.kicad_pcb und preview/ aus design.py.

Kein KiCad nötig. Elektroden und die 20 Sense-Bahnen sind fest (Unterseite, eine Bahn je Segment).
Der Kopf (I2C, Versorgung, Serienwiderstände) wird auf einem 0,1-mm-Gitter geroutet.

  python3 gen_pcb.py
"""

import heapq
import math
import os
import uuid
from collections import defaultdict

import design as D

HERE = os.path.dirname(os.path.abspath(__file__))
PCB_PATH = os.path.join(HERE, "wasserstand-14mm.kicad_pcb")
PREVIEW = os.path.join(HERE, "preview")
MODEL_DIR = os.path.join(HERE, "3d")

CELL = 0.1
# Hindernis = halbe Bahn + Abstand, damit die Bahnmitte nicht in fremdes Kupfer läuft.
INFLATE = D.TRACE / 2 + D.CLEARANCE
ROUTE_X = D.VIA_X + 0.6


def uid():
    return str(uuid.uuid4())


class Via:
    def __init__(self, x, y, net):
        self.x, self.y, self.net = x, y, net
        self.size, self.drill = D.VIA_SIZE, D.VIA_DRILL


class Track:
    def __init__(self, x1, y1, x2, y2, width, layer, net):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.width, self.layer, self.net = width, layer, net


def world_pads():
    out = []
    for part in D.PARTS:
        for pad in part.pads:
            if not pad.net:
                continue
            out.append((part, pad, part.x + pad.x, part.y + pad.y))
    return out


def gnd_rails(tracks):
    """GND-Streifen an beiden Längskanten, Unterseite. Sense-Bahnen liegen dazwischen."""
    y0, y1 = 0.50, 13.75
    # Querbalken rechts der Programmierlöcher, sonst trifft er VCC.
    x0, x1 = 2.25, D.board_length() - 1.3
    w = 0.24
    tracks.append(Track(x0, y0, x1, y0, w, "B.Cu", "GND"))
    tracks.append(Track(x0, y1, x1, y1, w, "B.Cu", "GND"))
    tracks.append(Track(x0, y0, x0, y1, w, "B.Cu", "GND"))


def elec_bus(pads, vias, tracks):
    """Serienwiderstand Pad 2 → Via → Unterseite gerade → Via in der Elektrode."""
    by_net = defaultdict(list)
    for part, pad, x, y in pads:
        by_net[pad.net].append((part, pad, x, y))
    for i in range(D.N):
        net = f"E{i + 1:02d}"
        src = next((p for p in by_net[net] if p[0].kind == "r0402"), None)
        if src is None:
            raise SystemExit(f"{net}: kein Serienwiderstand")
        _part, _pad, x, y = src
        y = D.lane_y(i)
        vx, ex = D.VIA_X, D.elec_x(i)
        vias.append(Via(vx, y, net))
        vias.append(Via(ex, y, net))
        tracks.append(Track(x, y, vx, y, 0.15, "F.Cu", net))
        tracks.append(Track(vx, y, ex, y, D.TRACE, "B.Cu", net))


def _pad_xy(pads, ref, name=None, net=None):
    for part, pad, x, y in pads:
        if part.ref != ref:
            continue
        if name is not None and pad.name != name:
            continue
        if net is not None and pad.net != net:
            continue
        return (x, y)
    raise SystemExit(f"Pad fehlt: {ref} name={name} net={net}")


def _seg(tracks, a, b, width, net, layer="F.Cu"):
    if math.hypot(a[0] - b[0], a[1] - b[1]) < 0.02:
        return
    tracks.append(Track(a[0], a[1], b[0], b[1], width, layer, net))


def connect_vcc(pads, vias, tracks):
    """VCC-Stamm auf der Unterseite. Oberseite bleibt für die Sense-Flucht frei."""
    j = _pad_xy(pads, "J1", "3")
    r1 = _pad_xy(pads, "R1", net="VCC")
    r2 = _pad_xy(pads, "R2", net="VCC")
    c1 = _pad_xy(pads, "C1", net="VCC")
    c2 = _pad_xy(pads, "C2", net="VCC")
    c3 = _pad_xy(pads, "C3", net="VCC")
    c4 = _pad_xy(pads, "C4", net="VCC")
    u1 = _pad_xy(pads, "U1", "4")
    u2 = _pad_xy(pads, "U2", "4")
    hv = _pad_xy(pads, "J3", "2")
    pa3 = _pad_xy(pads, "U2", "2")
    bus_y = 2.35
    riser_x = 15.6 + D.HEAD
    w = 0.30

    def trunk(a, b):
        _seg(tracks, a, b, w, "VCC", "B.Cu")

    def tap(xy):
        vias.append(Via(*xy, "VCC"))

    # Grove-VCC links der Signalkontakte runter, Loch VCC rechts an den Löchern vorbei.
    side = (j[0] - 1.95, j[1])
    down = (side[0], bus_y + 0.25)
    _seg(tracks, j, side, 0.28, "VCC")
    _seg(tracks, side, down, 0.28, "VCC")
    tap(down)
    trunk(down, (down[0], bus_y))
    # Oberseite über die SCL/SDA-Riegel, Via erst unter ihnen.
    hop = (16.80, hv[1])
    low = (hop[0], bus_y + 0.25)
    _seg(tracks, hv, hop, 0.28, "VCC")
    _seg(tracks, hop, low, 0.28, "VCC")
    tap(low)
    trunk(low, (low[0], bus_y))
    trunk((down[0], bus_y), (c2[0], bus_y))
    trunk((riser_x, bus_y), (riser_x, D.VCC_U2_BUS_Y))
    for xy in (c1, c2):
        tap(xy)
        trunk(xy, (xy[0], bus_y))
    # Pullups und U2-Elkos links vom SCL-Riegel (y=3,4), nicht durch ihn durch.
    for xy in (r1, r2):
        tap(xy)
        trunk(xy, (riser_x, xy[1]))
    for xy in (c3, c4):
        tap(xy)
        trunk(xy, (xy[0], D.VCC_U2_BUS_Y))
    trunk((c4[0], D.VCC_U2_BUS_Y), (riser_x, D.VCC_U2_BUS_Y))
    # QFN-VDD: Pad zu schmal für eine Via. Kurzer Hals, Via daneben.
    for pin, out_y, join_y in ((u1, u1[1] - 0.95, bus_y), (u2, u2[1] - 0.65, D.VCC_U2_BUS_Y)):
        via_xy = (pin[0], out_y)
        _seg(tracks, pin, via_xy, 0.18, "VCC")
        tap(via_xy)
        trunk(via_xy, (via_xy[0], join_y))
    trunk((u2[0], D.VCC_U2_BUS_Y), (riser_x, D.VCC_U2_BUS_Y))
    # U2 PA3 = VCC, Adress-Strap. Neben dem VDD-Hals, nicht durch Pin 1.
    _seg(tracks, pa3, (pa3[0], D.VCC_U2_BUS_Y), 0.18, "VCC")
    tap((pa3[0], D.VCC_U2_BUS_Y))
    trunk((pa3[0], D.VCC_U2_BUS_Y), (u2[0], D.VCC_U2_BUS_Y))


def connect_mcu_io(pads, vias, tracks):
    """PA1/PA2 direkt auf SDA/SCL. PA0 jeweils an das eigene Loch. Kein Jumper."""
    r1 = _pad_xy(pads, "R1", "1")
    r2 = _pad_xy(pads, "R2", "1")
    u1_scl = _pad_xy(pads, "U1", "1")
    u2_scl = _pad_xy(pads, "U2", "1")
    u1_sda = _pad_xy(pads, "U1", "20")
    u2_sda = _pad_xy(pads, "U2", "20")
    u1_up = _pad_xy(pads, "U1", "19")
    u2_up = _pad_xy(pads, "U2", "19")
    h_u1 = _pad_xy(pads, "J3", "3")
    h_u2 = _pad_xy(pads, "J3", "4")
    H = D.HEAD

    # SCL auf der Unterseite bei y=3,40, rechts vom VCC-Steigleiter, dann hoch in R1.
    via_u1 = (u1_scl[0] - 0.6, u1_scl[1])
    _seg(tracks, u1_scl, via_u1, 0.2, "SCL")
    vias.append(Via(*via_u1, "SCL"))
    scl_up = (13.70, u1_scl[1])
    vias.append(Via(*scl_up, "SCL"))
    scl_cross = (15.45, u1_scl[1])
    _seg(tracks, via_u1, scl_cross, 0.2, "SCL", "B.Cu")
    vias.append(Via(*scl_cross, "SCL"))
    _seg(tracks, scl_cross, scl_up, 0.2, "SCL")
    _seg(tracks, scl_up, (r1[0], u1_scl[1]), 0.2, "SCL")
    _seg(tracks, (r1[0], u1_scl[1]), r1, 0.2, "SCL")
    # U2 auf demselben Riegel. Senkrecht an PC1 vorbei, Via erst darunter.
    dx, dx2 = 23.85 + H, 23.40 + H
    _seg(tracks, u2_scl, (dx, u2_scl[1]), 0.2, "SCL")
    _seg(tracks, (dx, u2_scl[1]), (dx, 6.50), 0.2, "SCL")
    _seg(tracks, (dx, 6.50), (dx2, 6.50), 0.2, "SCL")
    vias.append(Via(dx2, 6.50, "SCL"))
    _seg(tracks, (dx2, 6.50), (dx2, u1_scl[1]), 0.2, "SCL", "B.Cu")
    _seg(tracks, (dx2, u1_scl[1]), scl_cross, 0.2, "SCL", "B.Cu")

    # SDA. PC3 fällt bei x=20,4+HEAD auf der Oberseite, der VCC-Steigleiter bei x=14,2+HEAD.
    x_bus = 13.55
    a, b, c = 22.4 + H, 21.0 + H, 16.7 + H
    _seg(tracks, u1_sda, (a, u1_sda[1]), 0.2, "SDA")
    _seg(tracks, (a, u1_sda[1]), (a, 3.90), 0.2, "SDA")
    _seg(tracks, (a, 3.90), (b, 3.90), 0.2, "SDA")
    vias.append(Via(b, 3.90, "SDA"))
    _seg(tracks, (b, 3.90), (c, 3.90), 0.2, "SDA", "B.Cu")
    vias.append(Via(c, 3.90, "SDA"))
    _seg(tracks, (c, 3.90), (c, 5.20), 0.2, "SDA")
    _seg(tracks, (c, 5.20), (x_bus, 5.20), 0.2, "SDA")
    vias.append(Via(x_bus, 5.20, "SDA"))
    _seg(tracks, (x_bus, 5.20), (x_bus, r2[1]), 0.2, "SDA", "B.Cu")
    vias.append(Via(x_bus, r2[1], "SDA"))
    _seg(tracks, (x_bus, r2[1]), r2, 0.2, "SDA")
    # U2: über die GND-Vias von C3/C4, dann auf dieselbe Senkrechte.
    sx = 23.6 + H
    _seg(tracks, u2_sda, (sx, u2_sda[1]), 0.2, "SDA")
    vias.append(Via(sx, u2_sda[1], "SDA"))
    _seg(tracks, (sx, u2_sda[1]), (sx, 11.00), 0.2, "SDA", "B.Cu")
    _seg(tracks, (sx, 11.00), (x_bus, 11.00), 0.2, "SDA", "B.Cu")
    _seg(tracks, (x_bus, 11.00), (x_bus, r2[1]), 0.2, "SDA", "B.Cu")

    # UPDI. Jedes PA0 an sein Loch unter dem Stecker.
    lane = 7.55
    _seg(tracks, u1_up, (22.2 + H, u1_up[1]), 0.2, "UPDI_U1")
    _seg(tracks, (22.2 + H, u1_up[1]), (22.2 + H, 4.40), 0.2, "UPDI_U1")
    _seg(tracks, (22.2 + H, 4.40), (21.6 + H, 4.40), 0.2, "UPDI_U1")
    vias.append(Via(21.6 + H, 4.40, "UPDI_U1"))
    x_up = 18.10 + H
    _seg(tracks, (21.6 + H, 4.40), (x_up, 4.40), 0.2, "UPDI_U1", "B.Cu")
    _seg(tracks, (x_up, 4.40), (x_up, lane), 0.2, "UPDI_U1", "B.Cu")
    vias.append(Via(x_up, lane, "UPDI_U1"))
    door = (h_u1[0] + 1.15, h_u1[1])
    _seg(tracks, (x_up, lane), (door[0], lane), 0.2, "UPDI_U1")
    _seg(tracks, (door[0], lane), door, 0.2, "UPDI_U1")
    _seg(tracks, door, h_u1, 0.2, "UPDI_U1")

    _seg(tracks, u2_up, (24.10 + H, u2_up[1]), 0.2, "UPDI_U2")
    _seg(tracks, (24.10 + H, u2_up[1]), (24.10 + H, h_u2[1]), 0.2, "UPDI_U2")
    _seg(tracks, (24.10 + H, h_u2[1]), h_u2, 0.2, "UPDI_U2")


def is_sense(net):
    return net.startswith(("U1_", "U2_")) and not net.endswith(("PA0", "PA1", "PA2"))


def route_sense(pads, vias, tracks):
    """Sense fest verlegt, 0,15 mm. Kreuzungen nur zwischen Ober- und Unterseite.

    +x-Pins eines Chips bleiben in Pin-Reihenfolge, jede Bahn hat eine eigene
    Senkrechte. Pins, deren Ziel die Nachbarbahnen kreuzen müsste, gehen auf die Unterseite.
    """
    pin_at, res_at = {}, {}
    for part, pad, x, y in pads:
        if not is_sense(pad.net):
            continue
        if part.kind == "qfn":
            pin_at[pad.net] = (x, y)
        elif part.kind == "r0402" and pad.name == "1":
            res_at[pad.net] = (x, y)
    w = 0.15
    H = D.HEAD

    def front(net, pts):
        for a, b in zip(pts, pts[1:]):
            _seg(tracks, a, b, w, net)

    def back(net, pts):
        for a, b in zip(pts, pts[1:]):
            _seg(tracks, a, b, w, net, "B.Cu")

    def down(net, xy):
        vias.append(Via(*xy, net))

    # U1, Pins zur Spitze. Reihenfolge = Pin-y, Ziele liegen alle darunter und kreuzen nicht.
    for net, jx in (("U1_PA5", 28.25 + H), ("U1_PA6", 28.57 + H), ("U1_PA7", 28.89 + H),
                    ("U1_PB5", 29.21 + H), ("U1_PB4", 29.53 + H)):
        px, py = pin_at[net]
        rx, ry = res_at[net]
        front(net, [(px, py), (jx, py), (jx, ry), (rx, ry)])
    for net, jx in (("U2_PA5", 28.25 + H), ("U2_PA6", 28.57 + H), ("U2_PA7", 28.89 + H),
                    ("U2_PB5", 29.21 + H), ("U2_PB4", 29.53 + H)):
        px, py = pin_at[net]
        rx, ry = res_at[net]
        front(net, [(px, py), (jx, py), (jx, ry), (rx, ry)])

    # PA4 links neben der +x-Reihe, gerade auf die eigene Bahn.
    for net in ("U1_PA4", "U2_PA4"):
        px, py = pin_at[net]
        rx, ry = res_at[net]
        # 0,25 mm nach rechts, sonst klebt die Bahn an der VDD-Via.
        front(net, [(px, py), (px + 0.28, py), (px + 0.28, ry), (rx, ry)])

    # U1 rechte Flanke. PC1 liegt auf y=8,09. PC0 bleibt darunter.
    # PB0 steigt links von PB1 ab, beide Abstände an den EP-Vias vorbei.
    px, py = pin_at["U1_PC0"]
    rx, ry = res_at["U1_PC0"]
    front("U1_PC0", [(px, py), (px, 7.55), (29.00 + H, 7.55), (29.00 + H, ry), (rx, ry)])

    px, py = pin_at["U1_PB0"]
    rx, ry = res_at["U1_PB0"]
    front("U1_PB0", [(px, py), (px, 6.95), (27.90 + H, 6.95)])
    down("U1_PB0", (27.90 + H, 6.95))
    back("U1_PB0", [(27.90 + H, 6.95), (27.90 + H, ry), (rx, ry)])
    down("U1_PB0", (rx, ry))

    px, py = pin_at["U1_PB1"]
    rx, ry = res_at["U1_PB1"]
    front("U1_PB1", [(px, py), (px, 6.40), (27.15 + H, 6.40)])
    down("U1_PB1", (27.15 + H, 6.40))
    back("U1_PB1", [(27.15 + H, 6.40), (27.15 + H, ry), (rx, ry)])
    down("U1_PB1", (rx, ry))

    # U1 linke Flanke. PC1 oben herum. PC2 und PC3 auf der Unterseite, sonst kreuzen sie PC1.
    px, py = pin_at["U1_PC1"]
    rx, ry = res_at["U1_PC1"]
    front("U1_PC1", [(px, py), (24.20 + H, py), (24.20 + H, ry), (rx, ry)])

    px, py = pin_at["U1_PC2"]
    rx, ry = res_at["U1_PC2"]
    front("U1_PC2", [(px, py), (22.60 + H, py), (22.60 + H, 5.70)])
    down("U1_PC2", (22.60 + H, 5.70))
    back("U1_PC2", [(22.60 + H, 5.70), (22.60 + H, ry), (rx, ry)])
    down("U1_PC2", (rx, ry))

    px, py = pin_at["U1_PC3"]
    rx, ry = res_at["U1_PC3"]
    # Oberseite kreuzt SCL, Unterseite bleibt darunter und geht nach rechts, nicht durch den Steigleiter.
    front("U1_PC3", [(px, py), (px, 4.90), (20.40 + H, 4.90), (20.40 + H, 2.92)])
    down("U1_PC3", (20.40 + H, 2.92))
    back("U1_PC3", [(20.40 + H, 2.92), (32.35 + H, 2.92), (32.35 + H, ry), (rx, ry)])
    down("U1_PC3", (rx, ry))

    # U2 rechte Flanke, beide Ziele neben dem Pin. PB1 zuerst runter, PB0 danach.
    px, py = pin_at["U2_PB1"]
    rx, ry = res_at["U2_PB1"]
    front("U2_PB1", [(px, py), (px, 13.05), (28.20 + H, 13.05), (28.20 + H, ry), (rx, ry)])
    px, py = pin_at["U2_PB0"]
    rx, ry = res_at["U2_PB0"]
    front("U2_PB0", [(px, py), (px, 13.40), (28.70 + H, 13.40), (28.70 + H, ry), (rx, ry)])


def gnd_stubs(pads, vias, tracks):
    """Kurze GND-Brücke vom Pad zur Via, Via nicht mitten im 0402 (Lötzinn)."""
    for part, pad, x, y in pads:
        if pad.net != "GND":
            continue
        if part.kind == "qfn" and pad.name == "21":
            for sx in (-0.45, 0.45):
                for sy in (-0.45, 0.45):
                    vias.append(Via(x + sx, y + sy, "GND"))
            continue
        if part.kind == "qfn" and pad.name == "3":
            # Pin GND auf das Exposed Pad. +y zeigt bei beiden Chips zur Mitte.
            tracks.append(Track(x, y, x, y + 0.9, 0.22, "F.Cu", "GND"))
            continue
        if part.kind == "qfn" and pad.name == "2":
            # U1 PA3 an das benachbarte GND-Pad. Beide Netze sind GND.
            tracks.append(Track(x, y, x + 0.40, y, 0.18, "F.Cu", "GND"))
            continue
        if part.kind in ("c0402",):
            direction = -1 if y < D.BOARD_W / 2 else 1
            if part.ref in ("C3", "C4"):
                direction = 1
            # C1/C2 liegen am Rand. Via im Pad, kurzer Stich auf die GND-Schiene.
            if part.ref in ("C1", "C2"):
                vias.append(Via(x, y, "GND"))
                tracks.append(Track(x, y, x, 0.50, 0.24, "B.Cu", "GND"))
                continue
            vx, vy = x, y + direction * 0.75
            if 0.55 < vy < D.BOARD_W - 0.55:
                vias.append(Via(vx, vy, "GND"))
                tracks.append(Track(x, y, vx, vy, 0.25, "F.Cu", "GND"))
        if part.kind == "grove" and pad.name in ("SS1", "SS2", "4"):
            vias.append(Via(x, y, "GND"))


# ---------------------------------------------------------------- Router

def _idx_range():
    nx = int(ROUTE_X / CELL) + 2
    ny = int(D.BOARD_W / CELL) + 2
    return nx, ny


def _cell(x, y):
    return int(x / CELL), int(y / CELL)


def _center(ix, iy):
    return (ix + 0.5) * CELL, (iy + 0.5) * CELL


def build_block(pads, vias, tracks, skip_net=None):
    """skip_net: Pads/Bahnen/Vias dieses Netzes nicht sperren, damit der Router sie anfahren kann."""
    nx, ny = _idx_range()
    blocked = [bytearray(nx * ny), bytearray(nx * ny)]

    def mark(layer, ix, iy):
        if 0 <= ix < nx and 0 <= iy < ny:
            blocked[layer][iy * nx + ix] = 1

    def mark_disk(layers, x, y, r):
        ix0, iy0 = _cell(x - r, y - r)
        ix1, iy1 = _cell(x + r, y + r)
        for iy in range(iy0, iy1 + 1):
            for ix in range(ix0, ix1 + 1):
                cx, cy = _center(ix, iy)
                if (cx - x) ** 2 + (cy - y) ** 2 <= r * r:
                    for layer in layers:
                        mark(layer, ix, iy)

    def mark_rect(layer, x, y, w, h, inflate):
        ix0, iy0 = _cell(x - w / 2 - inflate, y - h / 2 - inflate)
        ix1, iy1 = _cell(x + w / 2 + inflate, y + h / 2 + inflate)
        for iy in range(iy0, iy1 + 1):
            for ix in range(ix0, ix1 + 1):
                cx, cy = _center(ix, iy)
                if abs(cx - x) <= w / 2 + inflate and abs(cy - y) <= h / 2 + inflate:
                    mark(layer, ix, iy)

    # Rand
    for iy in range(ny):
        for ix in range(nx):
            cx, cy = _center(ix, iy)
            if cx < 0.35 or cy < 0.35 or cy > D.BOARD_W - 0.35 or cx > D.VIA_X + 0.15:
                mark(0, ix, iy)
                mark(1, ix, iy)

    for part, pad, x, y in pads:
        if pad.net == skip_net:
            continue
        inflate = 0.18 if part.kind == "qfn" and pad.name != "21" else INFLATE
        mark_rect(0, x, y, pad.w, pad.h, inflate)
    for part in D.PARTS:
        if part.kind == "mount":
            mark_disk((0, 1), part.x, part.y, D.MOUNT_BLOCK_R)
    for v in vias:
        if v.net == skip_net:
            continue
        mark_disk((0, 1), v.x, v.y, v.size / 2 + D.CLEARANCE + D.TRACE / 2)
    for t in tracks:
        if t.net == skip_net:
            continue
        layer = 0 if t.layer == "F.Cu" else 1
        steps = max(1, int(math.hypot(t.x2 - t.x1, t.y2 - t.y1) / CELL))
        extra = D.TRACE / 2 if t.width > 0.22 else 0.0
        r = t.width / 2 + D.CLEARANCE + extra
        for s in range(steps + 1):
            a = s / steps
            mark_disk((layer,), t.x1 + (t.x2 - t.x1) * a, t.y1 + (t.y2 - t.y1) * a, r)
    return blocked, nx, ny


def cells_of_pad(pad_xy, pad, blocked, nx, ny, force=False):
    x, y = pad_xy
    ix0, iy0 = _cell(x - pad.w / 2, y - pad.h / 2)
    ix1, iy1 = _cell(x + pad.w / 2, y + pad.h / 2)
    found = []
    for iy in range(iy0, iy1 + 1):
        for ix in range(ix0, ix1 + 1):
            if not (0 <= ix < nx and 0 <= iy < ny):
                continue
            cx, cy = _center(ix, iy)
            if abs(cx - x) > pad.w / 2 or abs(cy - y) > pad.h / 2:
                continue
            # SMD-Pads liegen nur auf F.Cu. Unterseite unter dem Pad ist kein Anschluss.
            if blocked[0][iy * nx + ix] and not force:
                continue
            found.append((ix, iy, 0))
    return found


def route_net(net, pad_list, blocked, nx, ny):
    """Verbindet alle Pads des Netzes. pad_list: (pad, x, y). Gibt Tracks und Vias zurück."""
    remaining = list(pad_list)
    seed = remaining.pop(0)
    connected = cells_of_pad((seed[1], seed[2]), seed[0], blocked, nx, ny, force=True)
    # Start nur auf der Lage, die am Pad wirklich frei ist; force liefert sonst beide.
    connected = [c for c in connected if not blocked[c[2]][c[1] * nx + c[0]]] or connected
    tracks, vias = [], []
    if not connected:
        return [], [], len(pad_list)

    def astar(starts, goals):
        if not goals:
            return None
        goal_set = set(goals)
        gscore = {}
        parent = {}
        heap = []
        for s in starts:
            gscore[s] = 0.0
            parent[s] = None
            heapq.heappush(heap, (0.0, s))
        pops = 0
        while heap:
            _f, cur = heapq.heappop(heap)
            if _f > gscore.get(cur, 1e18) + 1e-9:
                continue
            pops += 1
            if pops > 250000:
                return None
            if cur in goal_set:
                path = []
                while cur is not None:
                    path.append(cur)
                    cur = parent[cur]
                path.reverse()
                return path
            ix, iy, layer = cur
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                n = (ix + dx, iy + dy, layer)
                if not (0 <= n[0] < nx and 0 <= n[1] < ny):
                    continue
                if blocked[layer][n[1] * nx + n[0]]:
                    continue
                ng = gscore[cur] + 1.0
                if ng < gscore.get(n, 1e18):
                    gscore[n] = ng
                    parent[n] = cur
                    heapq.heappush(heap, (ng, n))
            other = (ix, iy, 1 - layer)
            if via_room(ix, iy, blocked, nx, ny):
                ng = gscore[cur] + 8.0
                if ng < gscore.get(other, 1e18):
                    gscore[other] = ng
                    parent[other] = cur
                    heapq.heappush(heap, (ng, other))
        return None

    # Ziel-Pads der Reihe nach an das schon verbundene Kupfer.
    # Heuristik ohne Zielnähe: bei diesem kleinen Kopf reicht Dijkstra.
    while remaining:
        goals = []
        owner = {}
        for i, (pad, x, y) in enumerate(remaining):
            for c in cells_of_pad((x, y), pad, blocked, nx, ny, force=True):
                if blocked[c[2]][c[1] * nx + c[0]]:
                    continue
                goals.append(c)
                owner[c] = i
        if not goals:
            print("   kein Ziel", [(p.name, round(x, 2), round(y, 2)) for p, x, y in remaining[:6]])
            return tracks, vias, len(remaining)
        path = astar(connected, goals)
        if path is None:
            print("   fest", [(p.name, round(x, 2), round(y, 2)) for p, x, y in remaining[:6]])
            return tracks, vias, len(remaining)
        hit = owner.get(path[-1])
        if hit is None:
            return tracks, vias, len(remaining)
        pad, px, py = remaining.pop(hit)
        tracks.extend(path_to_tracks(path, net, (px, py)))
        # Vias dort, wo die Lage wechselt
        for a, b in zip(path, path[1:]):
            if a[2] != b[2] and (a[0], a[1]) == (b[0], b[1]):
                vx, vy = _center(a[0], a[1])
                vias.append(Via(vx, vy, net))
        for c in path:
            connected.append(c)
        for c in cells_of_pad((px, py), pad, blocked, nx, ny, force=True):
            if not blocked[c[2]][c[1] * nx + c[0]]:
                connected.append(c)
        # eigene Bahn für die nächsten Netze sperren
        paint_path(path, blocked, nx, ny)
    return tracks, vias, 0


def via_room(ix, iy, blocked, nx, ny):
    r = int((D.VIA_SIZE / 2 + D.CLEARANCE) / CELL)
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy > r * r:
                continue
            x, y = ix + dx, iy + dy
            if not (0 <= x < nx and 0 <= y < ny):
                return False
            if blocked[0][y * nx + x] or blocked[1][y * nx + x]:
                return False
    return True


def paint_path(path, blocked, nx, ny):
    # Nächste Bahnmitte mindestens Bahnbreite + Abstand entfernt.
    rad = (D.TRACE + D.CLEARANCE) / CELL
    r = math.ceil(rad)
    for ix, iy, layer in path:
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if dx * dx + dy * dy > rad * rad:
                    continue
                x, y = ix + dx, iy + dy
                if 0 <= x < nx and 0 <= y < ny:
                    blocked[layer][y * nx + x] = 1
        # Via-Sperre, wenn Nachbar die Lage wechselt, macht route_net über die Via selbst


def path_to_tracks(path, net, end_xy):
    pts = []
    for ix, iy, layer in path:
        x, y = _center(ix, iy)
        layer_name = "F.Cu" if layer == 0 else "B.Cu"
        if pts and pts[-1][2] == layer_name and abs(pts[-1][0] - x) < 1e-6 and abs(pts[-1][1] - y) < 1e-6:
            continue
        pts.append((x, y, layer_name))
    if not pts:
        return []
    pts[0] = (pts[0][0], pts[0][1], pts[0][2])
    # Ende auf die Padmitte ziehen, Lage beibehalten
    pts[-1] = (end_xy[0], end_xy[1], pts[-1][2])
    tracks = []
    for a, b in zip(pts, pts[1:]):
        if a[2] != b[2]:
            continue
        if abs(a[0] - b[0]) < 1e-4 and abs(a[1] - b[1]) < 1e-4:
            continue
        tracks.append(Track(a[0], a[1], b[0], b[1], D.TRACE, a[2], net))
    return tracks


def simplify(tracks):
    """Kolineare Stücke gleicher Lage und gleichen Netzes zusammenziehen."""
    changed = True
    guard = 0
    while changed and guard < 20:
        changed = False
        guard += 1
        used = [False] * len(tracks)
        out = []
        for i, t in enumerate(tracks):
            if used[i]:
                continue
            used[i] = True
            x1, y1, x2, y2 = t.x1, t.y1, t.x2, t.y2
            grew = True
            while grew:
                grew = False
                for j, u in enumerate(tracks):
                    if used[j] or u.net != t.net or u.layer != t.layer or abs(u.width - t.width) > 1e-6:
                        continue
                    if abs((x2 - x1) * (u.y2 - u.y1) - (y2 - y1) * (u.x2 - u.x1)) > 1e-3:
                        continue
                    ends = ((u.x1, u.y1), (u.x2, u.y2))
                    if math.hypot(ends[0][0] - x2, ends[0][1] - y2) < 0.02:
                        x2, y2 = ends[1]
                    elif math.hypot(ends[1][0] - x2, ends[1][1] - y2) < 0.02:
                        x2, y2 = ends[0]
                    elif math.hypot(ends[0][0] - x1, ends[0][1] - y1) < 0.02:
                        x1, y1 = ends[1]
                    elif math.hypot(ends[1][0] - x1, ends[1][1] - y1) < 0.02:
                        x1, y1 = ends[0]
                    else:
                        continue
                    used[j] = True
                    grew = True
                    changed = True
            out.append(Track(x1, y1, x2, y2, t.width, t.layer, t.net))
        tracks[:] = out
    return tracks


# ---------------------------------------------------------------- Prüfung

def point_rect(px, py, x, y, w, h):
    dx = max(abs(px - x) - w / 2, 0.0)
    dy = max(abs(py - y) - h / 2, 0.0)
    return math.hypot(dx, dy)


def seg_points(t, step=0.25):
    length = math.hypot(t.x2 - t.x1, t.y2 - t.y1)
    n = max(1, int(length / step))
    return [((1 - a) * t.x1 + a * t.x2, (1 - a) * t.y1 + a * t.y2) for a in (i / n for i in range(n + 1))]


def copper_gap(tracks, vias, pads):
    """Stichprobe, nur gleiche Lage. Unterseiten-Bahnen unter den Elektroden sind kein Kurzschluss."""
    worst = []
    front, back = [], []
    for part, pad, x, y in pads:
        if part.kind == "electrode":
            continue
        front.append((pad.net, x, y, min(pad.w, pad.h), part.ref + "." + pad.name))
    for v in vias:
        front.append((v.net, v.x, v.y, v.size, "via"))
        back.append((v.net, v.x, v.y, v.size, "via"))
    for t in tracks:
        bucket = front if t.layer == "F.Cu" else back
        for x, y in seg_points(t, 0.4):
            bucket.append((t.net, x, y, t.width, t.layer))

    def scan(bucket):
        hits = []
        for i, a in enumerate(bucket):
            for b in bucket[i + 1:]:
                if a[0] == b[0] or not a[0] or not b[0]:
                    continue
                dist = math.hypot(a[1] - b[1], a[2] - b[2]) - a[3] / 2 - b[3] / 2
                if dist < D.CLEARANCE - 0.03:
                    hits.append((dist, a[0], b[0], a[4], b[4], a[1], a[2]))
        hits.sort(key=lambda w: w[0])
        return hits

    worst = scan(front)[:8] + scan(back)[:4]
    worst.sort(key=lambda w: w[0])
    return worst[:10]


def pad_overlaps(pads):
    bad = []
    items = [(p.ref, pad.name, pad.net, x, y, pad.w, pad.h) for p, pad, x, y in pads]
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if a[0] == b[0] and a[2] == b[2]:
                continue
            gap_x = abs(a[3] - b[3]) - a[5] / 2 - b[5] / 2
            gap_y = abs(a[4] - b[4]) - a[6] / 2 - b[6] / 2
            if gap_x < -1e-6 and gap_y < -1e-6:
                bad.append((a[0], a[1], b[0], b[1]))
            elif min(gap_x, 0) + min(gap_y, 0) < 0 and gap_x < D.CLEARANCE and gap_y < D.CLEARANCE and gap_x >= -1e-3 and gap_y >= -1e-3:
                # Kantenabstand in der Trennachse
                sep = max(gap_x, gap_y)
                if sep < D.CLEARANCE - 0.01:
                    bad.append((a[0], a[1], b[0], b[1], round(sep, 3)))
    return bad


# ---------------------------------------------------------------- KiCad

def sexp_escape(s):
    return s.replace("\\", "\\\\").replace('"', '\\"')


def emit_pcb(tracks, vias):
    L = D.board_length()
    lines = [
        "(kicad_pcb",
        "\t(version 20260206)",
        '\t(generator "wasserstand_gen")',
        '\t(generator_version "1")',
        "\t(general",
        f"\t\t(thickness {D.THICKNESS})",
        "\t\t(legacy_teardrops no)",
        "\t)",
        '\t(paper "A3")',
        "\t(layers",
        '\t\t(0 "F.Cu" signal)',
        '\t\t(2 "B.Cu" signal)',
        '\t\t(9 "F.Adhes" user "F.Adhesive")',
        '\t\t(11 "B.Adhes" user "B.Adhesive")',
        '\t\t(13 "F.Paste" user)',
        '\t\t(15 "B.Paste" user)',
        '\t\t(5 "F.SilkS" user "F.Silkscreen")',
        '\t\t(7 "B.SilkS" user "B.Silkscreen")',
        '\t\t(1 "F.Mask" user)',
        '\t\t(3 "B.Mask" user)',
        '\t\t(25 "Edge.Cuts" user)',
        '\t\t(31 "F.CrtYd" user "F.Courtyard")',
        '\t\t(35 "F.Fab" user)',
        "\t)",
    ]
    for part in D.PARTS:
        lines.extend(emit_fp(part))
    chamfer = 1.2
    edge = [
        (0, 0, L - chamfer, 0),
        (L - chamfer, 0, L, chamfer),
        (L, chamfer, L, D.BOARD_W - chamfer),
        (L, D.BOARD_W - chamfer, L - chamfer, D.BOARD_W),
        (L - chamfer, D.BOARD_W, 0, D.BOARD_W),
        (0, D.BOARD_W, 0, 0),
    ]
    for x1, y1, x2, y2 in edge:
        lines.append(
            f'\t(gr_line (start {x1:.4f} {y1:.4f}) (end {x2:.4f} {y2:.4f}) '
            f'(stroke (width 0.1) (type default)) (layer "Edge.Cuts") (uuid "{uid()}"))'
        )
    water = D.ELEC0_X - D.ELEC_ALONG / 2 - 0.7
    lines.append(
        f'\t(gr_line (start {water:.3f} 0.4) (end {water:.3f} {D.BOARD_W - 0.4:.3f}) '
        f'(stroke (width 0.15) (type default)) (layer "F.SilkS") (uuid "{uid()}"))'
    )
    lines.append(
        f'\t(gr_text "MAX" (at {water - 1.2:.3f} 7 90) (layer "F.SilkS") (uuid "{uid()}") '
        f'(effects (font (size 0.7 0.7) (thickness 0.1))))'
    )
    lines.append(
        f'\t(gr_text "WLS-14" (at 20.0 13.15 0) (layer "F.SilkS") (uuid "{uid()}") '
        f'(effects (font (size 0.8 0.8) (thickness 0.12))))'
    )
    for t in tracks:
        lines.append(
            f'\t(segment (start {t.x1:.4f} {t.y1:.4f}) (end {t.x2:.4f} {t.y2:.4f}) '
            f'(width {t.width:.3f}) (layer "{t.layer}") (net "{sexp_escape(t.net)}") (uuid "{uid()}"))'
        )
    for v in vias:
        lines.append(
            f'\t(via (at {v.x:.4f} {v.y:.4f}) (size {v.size:.3f}) (drill {v.drill:.3f}) '
            f'(layers "F.Cu" "B.Cu") (net "{sexp_escape(v.net)}") (uuid "{uid()}"))'
        )
    lines.extend(emit_zones(L))
    lines.append(")")
    text = "\n".join(lines) + "\n"
    with open(PCB_PATH, "w") as f:
        f.write(text)


def emit_fp(part: D.Part):
    if part.kind == "mount":
        attr = "through_hole board_only"
    elif part.kind == "hdr":
        attr = "through_hole"
    else:
        attr = "smd"
    lines = [f'\t(footprint "wls:{part.kind}"', '\t\t(layer "F.Cu")', f'\t\t(uuid "{uid()}")',
             f'\t\t(at {part.x:.4f} {part.y:.4f})', f"\t\t(attr {attr})"]
    lines.append(
        f'\t\t(property "Reference" "{part.ref}" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "{uid()}") '
        f'(effects (font (size 0.5 0.5) (thickness 0.08))))'
    )
    lines.append(
        f'\t\t(property "Value" "{sexp_escape(part.value)}" (at 0 0 0) (layer "F.Fab") (hide yes) '
        f'(uuid "{uid()}") (effects (font (size 0.4 0.4) (thickness 0.06))))'
    )
    if part.kind == "qfn":
        lines.append(fp_rect(-1.5, -1.5, 1.5, 1.5, "F.Fab"))
        lines.append(fp_rect(-2.0, -2.0, 2.0, 2.0, "F.CrtYd"))
        lines.append(
            f'\t\t(fp_circle (center -1.85 -1.85) (end -1.65 -1.85) (stroke (width 0.1) (type solid)) '
            f'(fill yes) (layer "F.SilkS") (uuid "{uid()}"))'
        )
    elif part.kind == "grove":
        lines.append(fp_rect(-9.6, -6.1, 1.5, 6.1, "F.Fab"))
        lines.append(fp_rect(-10.0, -6.4, 1.8, 6.4, "F.CrtYd"))
    elif part.kind == "electrode":
        lines.append(
            f'\t\t(fp_text user "{part.ref[1:]}" (at 0 {-part.pads[0].h / 2 - 0.15:.3f}) (layer "F.SilkS") '
            f'(uuid "{uid()}") (effects (font (size 0.55 0.55) (thickness 0.08))))'
        )
    elif part.kind == "tpad":
        lines.append(
            f'\t\t(fp_text user "{sexp_escape(part.value)}" (at 0 0.9) (layer "F.SilkS") (uuid "{uid()}") '
            f'(effects (font (size 0.45 0.45) (thickness 0.07))))'
        )
    elif part.kind == "mount":
        lines.append(
            f'\t\t(fp_circle (center 0 0) (end {D.MOUNT_PAD / 2:.2f} 0) (stroke (width 0.12) (type solid)) '
            f'(fill no) (layer "F.SilkS") (uuid "{uid()}"))'
        )
    elif part.kind == "hdr":
        for pad in part.pads:
            label = {"GND": "GND", "VCC": "VCC", "UPDI_U1": "U1", "UPDI_U2": "U2"}[pad.net]
            lines.append(
                f'\t\t(fp_text user "{label}" (at 1.35 {pad.y:.2f} 270) (layer "F.SilkS") (uuid "{uid()}") '
                f'(effects (font (size 0.55 0.55) (thickness 0.08))))'
            )
    # Bibliotheks-QFN hat Pin 1 links. Unsere Pins liegen um 90° gedreht, Kanten bleiben deckungsgleich.
    models = {
        "qfn": ("UQFN-20-1EP_3x3mm_P0.4mm_EP1.85x1.85mm.step", 90),
        "r0402": ("R_0402_1005Metric.step", 0),
        "c0402": ("C_0402_1005Metric.step", 0),
        "grove": ("Grove_1x04.step", 0),
    }
    if part.kind in models:
        lines.append(fp_model(*models[part.kind]))
    for pad in part.pads:
        net = f' (net "{sexp_escape(pad.net)}")' if pad.net else ""
        if part.kind == "hdr":
            lines.append(
                f'\t\t(pad "{pad.name}" thru_hole circle (at {pad.x:.4f} {pad.y:.4f}) '
                f'(size {pad.w:.4f} {pad.h:.4f}) (drill 1.0) (layers "*.Cu" "*.Mask"){net} '
                f'(uuid "{uid()}"))'
            )
            continue
        if part.kind == "mount":
            lines.append(
                f'\t\t(pad "{pad.name}" np_thru_hole circle (at {pad.x:.4f} {pad.y:.4f}) '
                f'(size {pad.w:.4f} {pad.h:.4f}) (drill {D.MOUNT_DRILL:.2f}) '
                f'(layers "*.Cu" "*.Mask") (uuid "{uid()}"))'
            )
            continue
        layers = ["F.Cu"]
        if pad.mask:
            layers.append("F.Mask")
        if pad.paste:
            layers.append("F.Paste")
        layer_s = " ".join(f'"{x}"' for x in layers)
        lines.append(
            f'\t\t(pad "{pad.name}" smd roundrect (at {pad.x:.4f} {pad.y:.4f}) '
            f'(size {pad.w:.4f} {pad.h:.4f}) (layers {layer_s}) (roundrect_rratio 0.15){net} (uuid "{uid()}"))'
        )
    lines.append("\t\t(embedded_fonts no)")
    lines.append("\t)")
    return lines


def fp_model(filename, rz=0.0):
    """STEP neben der Platine. KiCad-Raytrace zeigt sonst nur Kupfer."""
    path = os.path.join(MODEL_DIR, filename).replace("\\", "/")
    return (
        f'\t\t(model "{path}"\n'
        "\t\t\t(offset (xyz 0 0 0))\n"
        "\t\t\t(scale (xyz 1 1 1))\n"
        f"\t\t\t(rotate (xyz 0 0 {rz:.0f}))\n"
        "\t\t)"
    )


def fp_rect(x1, y1, x2, y2, layer):
    return (
        f'\t\t(fp_rect (start {x1} {y1}) (end {x2} {y2}) (stroke (width 0.05) (type solid)) '
        f'(fill no) (layer "{layer}") (uuid "{uid()}"))'
    )


def emit_zones(length):
    """GND-Flächen. KiCad füllt sie beim Öffnen (B oder Zone → Fill)."""
    head = D.ELEC0_X - D.ELEC_ALONG / 2 - 0.4
    zones = [
        ("GND-B", "B.Cu", [(0.2, 0.2), (length - 0.2, 0.2), (length - 0.2, D.BOARD_W - 0.2), (0.2, D.BOARD_W - 0.2)]),
        ("GND-F", "F.Cu", [(0.2, 0.2), (head, 0.2), (head, D.BOARD_W - 0.2), (0.2, D.BOARD_W - 0.2)]),
    ]
    lines = []
    for name, layer, pts in zones:
        body = " ".join(f"(xy {x:.3f} {y:.3f})" for x, y in pts)
        lines.append(
            "\t(zone\n"
            f'\t\t(net "GND")\n'
            f'\t\t(uuid "{uid()}")\n'
            f'\t\t(name "{name}")\n'
            f'\t\t(layers "{layer}")\n'
            "\t\t(hatch edge 0.5)\n"
            "\t\t(priority 0)\n"
            "\t\t(connect_pads (clearance 0.25))\n"
            "\t\t(min_thickness 0.2)\n"
            "\t\t(fill (thermal_gap 0.25) (thermal_bridge_width 0.3) (island_removal_mode 1))\n"
            f"\t\t(polygon (pts {body}))\n"
            "\t)"
        )
    return lines


# ---------------------------------------------------------------- Vorschau

def write_svg(tracks, vias, name, x0, x1, title):
    # Bild: Stecker oben, Spitze unten. SVG-x = Platinen-y, SVG-y = Platinen-x.
    w, h = D.BOARD_W, x1 - x0
    sc = 28
    margin = 18

    def px(y):
        return margin + y * sc

    def py(x):
        return margin + (x - x0) * sc

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * sc + 2 * margin:.0f}" '
        f'height="{h * sc + 2 * margin:.0f}" viewBox="0 0 {w * sc + 2 * margin:.1f} {h * sc + 2 * margin:.1f}">',
        '<rect width="100%" height="100%" fill="#1b1d1a"/>',
        f'<text x="{margin}" y="14" fill="#ddd" font-size="11" font-family="sans-serif">{title}</text>',
    ]
    L = D.board_length()
    parts.append(
        f'<rect x="{px(0):.1f}" y="{py(max(x0, 0)):.1f}" width="{D.BOARD_W * sc:.1f}" '
        f'height="{(min(L, x1) - max(x0, 0)) * sc:.1f}" fill="#14301c" stroke="#8d8" stroke-width="1"/>'
    )
    for part in D.PARTS:
        for pad in part.pads:
            x, y = part.x + pad.x, part.y + pad.y
            if not (x0 - 2 <= x <= x1 + 2):
                continue
            col = "#c45c26" if pad.net.startswith("E") else "#d7c07a" if pad.net == "GND" else "#e8e2d4"
            if not pad.mask:
                col = "#b8732a"
            parts.append(
                f'<rect x="{px(y - pad.h / 2):.2f}" y="{py(x - pad.w / 2):.2f}" '
                f'width="{pad.h * sc:.2f}" height="{pad.w * sc:.2f}" fill="{col}" opacity="0.95"/>'
            )
    for t in tracks:
        if t.x1 < x0 - 1 and t.x2 < x0 - 1:
            continue
        if t.x1 > x1 + 1 and t.x2 > x1 + 1:
            continue
        col = "#3a7bd5" if t.layer == "B.Cu" else "#e24b4b"
        parts.append(
            f'<line x1="{px(t.y1):.2f}" y1="{py(t.x1):.2f}" x2="{px(t.y2):.2f}" y2="{py(t.x2):.2f}" '
            f'stroke="{col}" stroke-width="{max(1.2, t.width * sc):.2f}" stroke-linecap="round"/>'
        )
    for v in vias:
        if not (x0 - 1 <= v.x <= x1 + 1):
            continue
        parts.append(
            f'<circle cx="{px(v.y):.2f}" cy="{py(v.x):.2f}" r="{v.size / 2 * sc:.2f}" fill="none" stroke="#9f9" stroke-width="1"/>'
        )
    for part in D.PARTS:
        if part.kind == "electrode":
            continue
        if not (x0 <= part.x <= x1):
            continue
        parts.append(
            f'<text x="{px(part.y) + 3:.1f}" y="{py(part.x) - 2:.1f}" fill="#fff" font-size="8" '
            f'font-family="sans-serif">{part.ref}</text>'
        )
    parts.append("</svg>")
    path = os.path.join(PREVIEW, name)
    with open(path, "w") as f:
        f.write("\n".join(parts))
    return path


def route_all(pads, vias, tracks):
    groups = defaultdict(list)
    for part, pad, x, y in pads:
        if not pad.net or pad.net in D.elec_nets():
            continue
        # PA1/PA2 sind SCL/SDA, aber von Hand an den Pullup geführt.
        if pad.net in ("SCL", "SDA") and part.kind == "qfn":
            continue
        groups[pad.net].append((pad, x, y))
    def _rank(n):
        # Sense-Flucht vom QFN zuerst, sonst frisst VCC/I2C den Kanal unter den Chips.
        if n == "U1_PB0":
            return (0, 0)
        if n.endswith(("PA0", "PA1", "PA2")):
            return (1, 0)
        if n == "SDA":
            return (2, 5)
        if n in ("SCL", "UPDI", "UPDI_U1", "UPDI_U2"):
            return (3, 0)
        if n in ("GND", "VCC"):
            return (4, 0)
        return (2, 0)

    order = sorted(groups, key=_rank)
    failed = []
    for net in order:
        group = groups[net]
        if len(group) < 2 or net in ("VCC", "GND", "UPDI", "UPDI_U1", "UPDI_U2") or is_sense(net):
            continue
        blocked, nx, ny = build_block(pads, vias, tracks, skip_net=net)
        nt, nv, left = route_net(net, group, blocked, nx, ny)
        tracks.extend(nt)
        vias.extend(nv)
        if left:
            failed.append(net)
            print(f"  FAIL {net:10}  offen={left}  seg={len(nt)}")
        else:
            print(f"  ok   {net:10}  seg={len(nt):3}  via={len(nv)}")
    return failed


def _pt_seg(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    length = vx * vx + vy * vy
    if length < 1e-12:
        return math.hypot(px - ax, py - ay), (ax, ay)
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / length))
    qx, qy = ax + t * vx, ay + t * vy
    return math.hypot(px - qx, py - qy), (qx, qy)


def _seg_dist(a, b):
    """Kleinster Abstand zweier Strecken. Schnitt zählt als 0."""
    ax, ay, bx, by = a
    cx, cy, dx, dy = b
    rx, ry = bx - ax, by - ay
    sx, sy = dx - cx, dy - cy
    den = rx * sy - ry * sx
    if abs(den) > 1e-12:
        t = ((cx - ax) * sy - (cy - ay) * sx) / den
        u = ((cx - ax) * ry - (cy - ay) * rx) / den
        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
            return 0.0, (ax + t * rx, ay + t * ry)
    best_d, best = 1e9, (ax, ay)
    for px, py, seg in ((ax, ay, b), (bx, by, b), (cx, cy, a), (dx, dy, a)):
        d, pt = _pt_seg(px, py, *seg)
        if d < best_d:
            best_d, best = d, pt
    return best_d, best


def real_gaps(tracks, vias, pads):
    """Echter Kantenabstand, nicht nur Stichprobe. Elektrodenflächen ausgenommen."""
    hits = []
    items = []
    for t in tracks:
        items.append((t.net, t.layer, (t.x1, t.y1, t.x2, t.y2), t.width))
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if a[0] == b[0] or a[1] != b[1] or not a[0] or not b[0]:
                continue
            dist, pt = _seg_dist(a[2], b[2])
            gap = dist - a[3] / 2 - b[3] / 2
            if gap < D.CLEARANCE - 0.005:
                hits.append((gap, a[0], b[0], pt[0], pt[1]))
    for v in vias:
        for net, layer, seg, width in items:
            if net == v.net or not net:
                continue
            dist, pt = _seg_dist(seg, (v.x, v.y, v.x, v.y))
            gap = dist - v.size / 2 - width / 2
            if gap < D.CLEARANCE - 0.005:
                hits.append((gap, v.net, net, v.x, v.y))
    for part, pad, x, y in pads:
        if part.kind == "electrode" or not pad.net:
            continue
        for net, layer, seg, width in items:
            if layer != "F.Cu" or net == pad.net or not net:
                continue
            dist, pt = _seg_dist(seg, (x, y, x, y))
            # Abstand zur Padkante, achsparallel genähert über den Padmittelpunkt.
            gap = dist - min(pad.w, pad.h) / 2 - width / 2
            if gap < D.CLEARANCE - 0.02 and dist < max(pad.w, pad.h):
                hits.append((gap, pad.net, net, x, y))
    hits.sort(key=lambda h: h[0])
    return hits[:12]


def mount_holes() -> list[tuple[float, float]]:
    return [(p.x, p.y) for p in D.PARTS if p.kind == "mount"]


def mount_gaps(tracks, vias) -> tuple[list[tuple[float, str, str, float, float]], float | None]:
    """Abstand von Kupfer zur Bohrung MH* (Kante = MOUNT_DRILL/2)."""
    r = D.MOUNT_DRILL / 2
    hits = []
    worst = 1e9
    for mx, my in mount_holes():
        for v in vias:
            dist = math.hypot(v.x - mx, v.y - my)
            gap = dist - r - v.size / 2
            worst = min(worst, gap)
            if gap < D.CLEARANCE - 0.005:
                hits.append((gap, v.net, "MH", v.x, v.y))
        for t in tracks:
            dist, pt = _seg_dist(
                (t.x1, t.y1, t.x2, t.y2), (mx, my, mx, my),
            )
            gap = dist - r - t.width / 2
            worst = min(worst, gap)
            if gap < D.CLEARANCE - 0.005:
                hits.append((gap, t.net, "MH", pt[0], pt[1]))
    hits.sort(key=lambda h: h[0])
    return hits[:12], (worst if worst < 1e8 else None)


def tie_long_pads(pads, tracks):
    """Router endet auf dem Pad-Rand. Beim Grove-Pad liegt der Rand 1,4 mm von der Mitte."""
    for part, pad, x, y in pads:
        if part.kind != "grove" or pad.net in ("", "GND", "VCC"):
            continue
        best_d, best = 1e9, None
        for t in tracks:
            if t.net != pad.net or t.layer != "F.Cu":
                continue
            d, pt = _seg_dist((t.x1, t.y1, t.x2, t.y2), (x, y, x, y))
            if d < best_d:
                best_d, best = d, pt
        if best is not None and best_d > 0.05:
            _seg(tracks, (x, y), best, 0.25, pad.net)


def unconnected(pads, vias, tracks):
    """Pads eines Netzes, die das Kupfer nicht erreicht."""
    parent = {}

    def find(k):
        parent.setdefault(k, k)
        while parent[k] != k:
            parent[k] = parent[parent[k]]
            k = parent[k]
        return k

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    ends = defaultdict(list)
    for i, t in enumerate(tracks):
        ends[t.net].append((t.layer, t.x1, t.y1, i, 0))
        ends[t.net].append((t.layer, t.x2, t.y2, i, 1))
        union((t.net, i, 0), (t.net, i, 1))
    for net, pts in ends.items():
        net_tracks = [(i, t) for i, t in enumerate(tracks) if t.net == net]
        for i, t in net_tracks:
            for j, u in net_tracks:
                if i == j or t.layer != u.layer:
                    continue
                for px, py in ((t.x1, t.y1), (t.x2, t.y2)):
                    d, _ = _seg_dist((u.x1, u.y1, u.x2, u.y2), (px, py, px, py))
                    if d < 0.08:
                        union((net, i, 0), (net, j, 0))
                        break
        # Pad leitet. Bahnen, die nur das Pad berühren, sind verbunden.
        for part, pad, x, y in pads:
            if pad.net != net or part.kind == "electrode":
                continue
            hit = []
            for i, t in enumerate(tracks):
                if t.net != net or t.layer != "F.Cu":
                    continue
                _d, pt = _seg_dist((t.x1, t.y1, t.x2, t.y2), (x, y, x, y))
                if abs(pt[0] - x) <= pad.w / 2 + 0.02 and abs(pt[1] - y) <= pad.h / 2 + 0.02:
                    hit.append(i)
            for other in hit[1:]:
                union((net, hit[0], 0), (net, other, 0))
        for v in vias:
            if v.net != net:
                continue
            key = (net, "v", round(v.x, 3), round(v.y, 3))
            for i, t in enumerate(tracks):
                if t.net != net:
                    continue
                d, _ = _seg_dist((t.x1, t.y1, t.x2, t.y2), (v.x, v.y, v.x, v.y))
                if d < 0.18:
                    union(key, (net, i, 0))
    open_pads = []
    by_net = defaultdict(list)
    for part, pad, x, y in pads:
        if pad.net and part.kind != "electrode":
            by_net[pad.net].append((part.ref, pad.name, x, y))
    for net, group in by_net.items():
        if len(group) < 2 or net not in ends or net in ("GND", "VCC"):
            continue
        roots = []
        for ref, name, x, y in group:
            pw = next(p.w for part, p, px, py in pads if part.ref == ref and p.name == name)
            ph = next(p.h for part, p, px, py in pads if part.ref == ref and p.name == name)
            root = None
            for p in ends[net]:
                if abs(p[1] - x) <= pw / 2 + 0.08 and abs(p[2] - y) <= ph / 2 + 0.08:
                    root = find((net, p[3], p[4]))
                    break
            if root is None:
                for v in vias:
                    if v.net == net and abs(v.x - x) <= pw / 2 + 0.05 and abs(v.y - y) <= ph / 2 + 0.05:
                        root = find((net, "v", round(v.x, 3), round(v.y, 3)))
                        break
            roots.append(root)
        if any(r is None or r != roots[0] for r in roots):
            open_pads.append(net)
    return sorted(set(open_pads))


def main():
    os.makedirs(PREVIEW, exist_ok=True)
    pads = world_pads()
    vias, tracks = [], []
    elec_bus(pads, vias, tracks)
    gnd_stubs(pads, vias, tracks)
    gnd_rails(tracks)
    connect_vcc(pads, vias, tracks)
    connect_mcu_io(pads, vias, tracks)
    route_sense(pads, vias, tracks)
    overlaps = pad_overlaps(pads)
    print(f"Platine {D.BOARD_W:.1f} × {D.board_length():.1f} mm, {len(D.PARTS)} Bauteile")
    big, small = D.tube_clearance()
    print(f"Rohr {D.TUBE_ID} mm: frei über Bauteilseite {big:.2f} mm, Gegenseite {small:.2f} mm")
    if overlaps:
        print("Pad-Kollisionen:")
        for o in overlaps:
            print(" ", o)
    else:
        print("Pads: keine Überlappung")
    print("Route:")
    failed = route_all(pads, vias, tracks)
    tie_long_pads(pads, tracks)
    simplify(tracks)
    gaps = copper_gap(tracks, vias, pads)
    exact = real_gaps(tracks, vias, pads)
    mh, mh_min = mount_gaps(tracks, vias)
    opens = unconnected(pads, vias, tracks)
    emit_pcb(tracks, vias)
    head = write_svg(tracks, vias, "kopf.svg", 0, D.ELEC0_X + 4, "Kopf, Stecker oben. Rot oben, blau unten.")
    full = write_svg(tracks, vias, "platine.svg", 0, D.board_length(), "Gesamt. Rot oben, blau unten.")
    print(f"KiCad: {PCB_PATH}")
    print(f"Vorschau: {head}")
    print(f"         {full}")
    if failed:
        print("nicht geroutet:", ", ".join(failed))
    if exact:
        print(f"Abstand unter {D.CLEARANCE} mm:")
        for g in exact[:8]:
            print(f"  {g[0]:+.3f} mm  {g[1]} / {g[2]}  bei ({g[3]:.2f},{g[4]:.2f})")
    else:
        print("Abstand: alle Netze >= 0,15 mm")
    if mh:
        print(f"Bohrung MH: unter {D.CLEARANCE} mm:")
        for g in mh:
            print(f"  {g[0]:+.3f} mm  {g[1]} → {g[2]}  bei ({g[3]:.2f},{g[4]:.2f})")
    elif mh_min is not None:
        print(f"Bohrung MH: min. Kupferabstand {mh_min:.3f} mm")
    if opens:
        print("offen:", ", ".join(opens))
    if gaps and not exact:
        print(f"Stichprobe zusätzlich (< {D.CLEARANCE} mm):")
        for g in gaps[:4]:
            print(f"  {g[0]:+.3f} mm  {g[1]} / {g[2]}")
    return 1 if failed or overlaps or exact or mh or opens else 0


if __name__ == "__main__":
    raise SystemExit(main())
