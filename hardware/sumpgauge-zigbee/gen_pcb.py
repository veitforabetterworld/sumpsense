"""Erzeugt wasserstand-zigbee.kicad_pcb und preview/ aus design.py.

Kein KiCad nötig. Kopf und Sense-Bahnen sind fest geroutet.
Antennen-Sperrzone und Abstände werden geprüft.

  python3 gen_pcb.py
"""

import heapq
import math
import os
import uuid
from collections import defaultdict

import design as D

HERE = os.path.dirname(os.path.abspath(__file__))
PCB_PATH = os.path.join(HERE, "wasserstand-zigbee.kicad_pcb")
PREVIEW = os.path.join(HERE, "preview")


def uid():
    return str(uuid.uuid4())


class Via:
    def __init__(self, x, y, net, size=None, drill=None):
        self.x, self.y, self.net = x, y, net
        self.size = D.VIA_SIZE if size is None else size
        self.drill = D.VIA_DRILL if drill is None else drill


class Track:
    def __init__(self, x1, y1, x2, y2, width, layer, net):
        self.x1, self.y1, self.x2, self.y2 = x1, y1, x2, y2
        self.width, self.layer, self.net = width, layer, net


def sexp_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"')


def world_pads():
    out = []
    for part in D.PARTS:
        for pad in part.pads:
            if not pad.net:
                continue
            out.append((part, pad, part.x + pad.x, part.y + pad.y))
    return out


def find_pad(ref, name=None, net=None):
    for part, pad, x, y in world_pads():
        if part.ref != ref:
            continue
        if name is not None and pad.name != name:
            continue
        if net is not None and pad.net != net:
            continue
        return part, pad, x, y
    raise KeyError((ref, name, net))


def poly(tracks, pts, width, layer, net):
    for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
        if abs(x1 - x2) < 1e-6 and abs(y1 - y2) < 1e-6:
            continue
        tracks.append(Track(x1, y1, x2, y2, width, layer, net))


def pin_of(net: str) -> int:
    for pin, name in D.PIN_NET.items():
        if name == net:
            return pin
    raise KeyError(net)


def side_of(pin: int) -> str:
    if pin <= 8:
        return "low"      # Platinen -y
    if pin <= 16:
        return "tip"      # Platinen +x
    if pin <= 24:
        return "high"     # Platinen +y
    return "ant"          # Platinen -x


# Flucht-Via an den 0,4-mm-Pins. 0,45 mm Via würde den Nachbarpin treffen.
ESC_SIZE = 0.25
ESC_DRILL = 0.15
CELL = 0.15
LAYER = {"F.Cu": 0, "B.Cu": 1}


def _esc(vias, tracks, x, y, net):
    vias.append(Via(x, y, net, ESC_SIZE, ESC_DRILL))


def route_sense(vias, tracks):
    """GPIO → Unterseite → Vorwiderstand → Elektrode. Bahnen kreuzen sich nicht."""
    tip_high = D.LANE_GPIO[7:13]
    # Oberste drei: links = tiefste Bahn = höchste Flucht, Abstieg ganz links.
    # So kreuzt keine Senkrechte die Nachbarspur.
    # Abstieg hinter den Vorwiderständen, sonst kreuzt die Gate-Bahn die Senkrechten.
    high_escape = {
        0: (13.80, 86.2),
        1: (13.48, 85.1),
        2: (13.16, 84.0),
    }
    for i, gpio in enumerate(D.LANE_GPIO):
        pin = pin_of(gpio)
        y = D.lane_y(i)
        _part, _pad, rx, ry = find_pad(f"R{i + 1}", "1")
        _part, _pad, r2x, r2y = find_pad(f"R{i + 1}", "2")
        _part, epad, ex, _ey = find_pad(f"E{i + 1}", "1")
        x, py, _bw, _bh = D.chip_pad(pin)
        if i >= 13:
            travel, drop = high_escape[i - 13]
            poly(tracks, [(x, py), (x, travel), (drop, travel)], 0.08, "F.Cu", gpio)
            vias.append(Via(drop, travel, gpio, ESC_SIZE, ESC_DRILL))
            poly(tracks, [(drop, travel), (drop, y), (rx, ry)], 0.15, "B.Cu", gpio)
            _esc(vias, tracks, rx, ry, gpio)
        elif gpio in tip_high:
            order = tip_high.index(gpio)
            vx = x + 0.62 + order * 0.60
            poly(tracks, [(x, py), (vx, py)], 0.15, "F.Cu", gpio)
            _esc(vias, tracks, vx, py, gpio)
            poly(tracks, [(vx, py), (vx, y), (rx, ry)], 0.16, "B.Cu", gpio)
            _esc(vias, tracks, rx, ry, gpio)
        elif i == 6:
            vx = x + 0.18
            poly(tracks, [(x, py), (vx, py)], 0.15, "F.Cu", gpio)
            _esc(vias, tracks, vx, py, gpio)
            poly(tracks, [(vx, py), (vx, y), (rx, ry)], 0.16, "B.Cu", gpio)
            _esc(vias, tracks, rx, ry, gpio)
        else:
            vy = py - 0.55
            poly(tracks, [(x, py), (x, vy)], 0.15, "F.Cu", gpio)
            _esc(vias, tracks, x, vy, gpio)
            poly(tracks, [(x, vy), (x, y), (rx, ry)], 0.16, "B.Cu", gpio)
            _esc(vias, tracks, rx, ry, gpio)
        poly(tracks, [(r2x, r2y), (ex, y)], 0.20, "F.Cu", epad.net)


def route_fixed(vias, tracks):
    """HF-Leitung, die beiden 0-Ω-Brücken am Chip, EP-Vias, Masse-Nähte."""
    fx, fy = D.feed_xy()
    _p, _pad, rf_x, rf_y = find_pad("R21", "1")
    _p, _pad, ant_x, ant_y = find_pad("R21", "2")
    pin_x, pin_y, _w, _h = D.chip_pad(pin_of("ANT_PIN"))
    # Breite Bahn endet vor dem 0-Ω, sonst überdeckt der Abschluss das ANT-Pad.
    end_x = rf_x - 0.70
    poly(tracks, [(fx, fy), (fx, D.RF_Y), (end_x, D.RF_Y)], D.RF_W, "F.Cu", "RF")
    poly(tracks, [(end_x, D.RF_Y), (rf_x, rf_y)], 0.22, "F.Cu", "RF")
    poly(tracks, [(ant_x, ant_y), (pin_x, pin_y)], 0.22, "F.Cu", "ANT_PIN")
    xt_x, xt_y, _w, _h = D.chip_pad(pin_of("XTAL_PIN"))
    _p, _pad, r_x, r_y = find_pad("R20", "2")
    poly(tracks, [(xt_x, xt_y), (r_x, r_y)], 0.15, "F.Cu", "XTAL_PIN")
    for dx, dy in ((-0.75, -0.75), (0.75, -0.75), (-0.75, 0.75), (0.75, 0.75)):
        vias.append(Via(D.CX + dx, D.CY + dy, "GND"))
    for x in (14.0, 18.0, 22.0, 26.0):
        vias.append(Via(x, 12.55, "GND"))
    # Gate passt oben nicht zwischen Pad und den drei Fluchtspuren.
    # Via unter dem Pad, Unterseite über den Bahnen, Abstieg vor den Drop-Vias.
    gx, gy, _w, _h = D.chip_pad(pin_of("GATE"))
    _p, _pad, qg, qgy = find_pad("Q1", "1")
    _p, _pad, pg, pgy = find_pad("R23", "1")
    poly(tracks, [(gx, gy), (gx, 12.40)], 0.15, "F.Cu", "GATE")
    vias.append(Via(gx, 12.40, "GATE", ESC_SIZE, ESC_DRILL))
    # Links an den Sense-Bahnen vorbei, IO8 auf der Oberseite queren.
    poly(tracks, [(gx, 12.40), (30.6, 12.40), (30.6, 7.85)], 0.18, "B.Cu", "GATE")
    vias.append(Via(30.6, 7.85, "GATE", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(30.6, 7.85), (35.55, 7.85)], 0.18, "F.Cu", "GATE")
    vias.append(Via(35.55, 7.85, "GATE", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(35.55, 7.85), (qg, 7.85), (qg, qgy)], 0.18, "B.Cu", "GATE")
    vias.append(Via(qg, qgy, "GATE", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(qg, qgy), (qg, pgy), (pg, pgy)], 0.18, "F.Cu", "GATE")


def _cell(x, y):
    return int(round(x / CELL)), int(round(y / CELL))


def _paint_disk(into, layer, x, y, radius):
    n = int(radius / CELL) + 1
    i0, j0 = _cell(x, y)
    r2 = radius * radius
    layers = (0, 1) if layer is None else (layer,)
    for di in range(-n, n + 1):
        for dj in range(-n, n + 1):
            if (di * CELL) ** 2 + (dj * CELL) ** 2 <= r2:
                for lv in layers:
                    into.add((lv, i0 + di, j0 + dj))


def _paint_seg(into, layer, x1, y1, x2, y2, radius):
    steps = int(math.hypot(x2 - x1, y2 - y1) / (CELL * 0.5)) + 1
    for s in range(steps + 1):
        t = s / steps
        _paint_disk(into, layer, x1 + (x2 - x1) * t, y1 + (y2 - y1) * t, radius)


def _paint_rect(into, layer, cx, cy, w, h, extra):
    x0, x1 = cx - w / 2 - extra, cx + w / 2 + extra
    y0, y1 = cy - h / 2 - extra, cy + h / 2 + extra
    i0, i1 = _cell(x0, y0)[0], _cell(x1, y1)[0]
    j0, j1 = _cell(x0, y0)[1], _cell(x1, y1)[1]
    layers = (0, 1) if layer is None else (layer,)
    for i in range(min(i0, i1), max(i0, i1) + 1):
        for j in range(min(j0, j1), max(j0, j1) + 1):
            px, py = i * CELL, j * CELL
            dx = max(abs(px - cx) - w / 2, 0.0)
            dy = max(abs(py - cy) - h / 2, 0.0)
            if dx * dx + dy * dy <= extra * extra + 1e-9:
                for lv in layers:
                    into.add((lv, i, j))


def _pad_cells(x, y, w, h, both):
    cells = {}
    i0, j0 = _cell(x - w / 2, y - h / 2)
    i1, j1 = _cell(x + w / 2, y + h / 2)
    layers = (0, 1) if both else (0,)
    for i in range(min(i0, i1), max(i0, i1) + 1):
        for j in range(min(j0, j1), max(j0, j1) + 1):
            px, py = i * CELL, j * CELL
            if abs(px - x) <= w / 2 + 1e-6 and abs(py - y) <= h / 2 + 1e-6:
                for lv in layers:
                    cells[(lv, i, j)] = (x, y)
    if not cells:
        i, j = _cell(x, y)
        for lv in layers:
            cells[(lv, i, j)] = (x, y)
    return cells


def _net_width(net: str) -> float:
    return {"V5": 0.40, "DRAIN": 0.40, "VOUT": 0.30, "VCC3": 0.25, "GND": 0.25}.get(net, 0.18)


def _blocked_for(net, width, tracks, vias, pads):
    gap = 0.22 + width / 2
    blocked = set()
    for t in tracks:
        if t.net == net or not t.net:
            continue
        _paint_seg(blocked, LAYER[t.layer], t.x1, t.y1, t.x2, t.y2, t.width / 2 + gap)
    for v in vias:
        if v.net == net or not v.net:
            continue
        _paint_disk(blocked, None, v.x, v.y, v.size / 2 + gap)
    for part, pad, x, y in pads:
        if not pad.net or pad.net == net or part.kind == "electrode":
            continue
        both = part.kind in ("hdr", "mount")
        _paint_rect(blocked, None if both else 0, x, y, pad.w, pad.h, gap)
    # Sperrzone, Bohrung, Quarz-Unterseite, Rand.
    kx0, ky0, kx1, ky1 = D.KEEPOUT[0]
    _paint_rect(blocked, None, (kx0 + kx1) / 2, (ky0 + ky1) / 2, kx1 - kx0, ky1 - ky0, 0.0)
    _paint_disk(blocked, None, D.MOUNT_X, D.MOUNT_Y, D.MOUNT_DRILL / 2 + 0.20)
    crystal = next(p for p in D.PARTS if p.ref == "Y1")
    _paint_rect(blocked, 1, crystal.x, crystal.y, 1.6, 1.3, 0.0)
    length = D.board_length()
    for i in range(int(length / CELL) + 2):
        for j in range(int(D.BOARD_W / CELL) + 2):
            x, y = i * CELL, j * CELL
            if x < 0.30 or y < 0.28 or x > length - 0.30 or y > D.BOARD_W - 0.28:
                blocked.add((0, i, j))
                blocked.add((1, i, j))
    return blocked


def _dilate(blocked):
    extra = set()
    for lv, i, j in blocked:
        for di in (-1, 0, 1):
            for dj in (-1, 0, 1):
                extra.add((lv, i + di, j + dj))
    return blocked | extra


def _bfs(sources, goals, blocked, via_blocked):
    """goals: cell -> (pad_x, pad_y). Liefert den Weg inkl. Padmittelpunkt."""
    if not sources or not goals:
        return None
    start = {}
    heap = []
    for cell in sources:
        if cell in goals:
            px, py = goals[cell]
            return [cell, (cell[0], px, py)]
        heapq.heappush(heap, (0, 0, cell))
    seen = set(sources)
    parent = {}
    while heap:
        cost, vias_n, cell = heapq.heappop(heap)
        if cell in goals:
            path = [cell]
            while cell in parent:
                cell = parent[cell]
                path.append(cell)
            path.reverse()
            px, py = goals[path[-1]]
            path.append((path[-1][0],) + _cell(px, py) if False else (path[-1][0], px, py))
            # path cells are (layer, i, j) except the last, which is (layer, x, y) pad.
            return path
        lv, i, j = cell
        for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nxt = (lv, i + di, j + dj)
            if nxt in seen or (nxt in blocked and nxt not in goals):
                continue
            seen.add(nxt)
            parent[nxt] = cell
            heapq.heappush(heap, (cost + 1, vias_n, nxt))
        other = (1 - lv, i, j)
        if other not in seen and cell not in via_blocked and other not in via_blocked:
            seen.add(other)
            parent[other] = cell
            heapq.heappush(heap, (cost + 8, vias_n + 1, other))
    return None


def _commit_path(path, net, width, tracks, vias):
    """path: (layer, i, j) ... and a final (layer, x, y) pad center."""
    pts = []
    for item in path:
        if isinstance(item[1], float) or abs(item[1]) > 5 and not isinstance(item[1], int):
            pts.append((item[0], float(item[1]), float(item[2])))
        else:
            # cell index or pad coordinate. Pad center was stored as (layer, x, y)
            # with x not an int-like index. Distinguish: cell indices are ints.
            if isinstance(item[1], int):
                pts.append((item[0], item[1] * CELL, item[2] * CELL))
            else:
                pts.append((item[0], float(item[1]), float(item[2])))
    # Der Padmittelpunkt ist (layer, x, y) mit float. Oben schon behandelt, wenn int nur Zellen.
    # Pfad neu aufbauen, letzter Punkt explizit.
    pts = []
    last = path[-1]
    for item in path[:-1]:
        pts.append((item[0], item[1] * CELL, item[2] * CELL))
    pts.append((last[0], float(last[1]), float(last[2])))
    # Kolinear zusammenfassen.
    slim = [pts[0]]
    for p in pts[1:]:
        if (
            len(slim) >= 2
            and p[0] == slim[-1][0] == slim[-2][0]
            and abs((slim[-1][1] - slim[-2][1]) * (p[2] - slim[-2][2])
                    - (slim[-1][2] - slim[-2][2]) * (p[1] - slim[-2][1])) < 1e-6
        ):
            slim[-1] = p
        elif abs(p[1] - slim[-1][1]) < 1e-9 and abs(p[2] - slim[-1][2]) < 1e-9 and p[0] == slim[-1][0]:
            continue
        else:
            slim.append(p)
    for a, b in zip(slim, slim[1:]):
        if a[0] != b[0]:
            vias.append(Via(b[1], b[2], net))
        elif abs(a[1] - b[1]) > 1e-9 or abs(a[2] - b[2]) > 1e-9:
            tracks.append(Track(a[1], a[2], b[1], b[2], width, "F.Cu" if a[0] == 0 else "B.Cu", net))


def _reached_cells(net, tracks, vias, pads):
    cells = set()
    for t in tracks:
        if t.net != net:
            continue
        steps = int(math.hypot(t.x2 - t.x1, t.y2 - t.y1) / CELL) + 1
        lv = LAYER[t.layer]
        for s in range(steps + 1):
            u = s / steps
            cells.add((lv, *_cell(t.x1 + (t.x2 - t.x1) * u, t.y1 + (t.y2 - t.y1) * u)))
    for v in vias:
        if v.net == net:
            i, j = _cell(v.x, v.y)
            cells.add((0, i, j))
            cells.add((1, i, j))
    return cells


def route_maze(vias, tracks) -> list[str]:
    """Alles, was die festen Bahnen nicht verbinden. Zwei Lagen, Lee-Router."""
    pads = world_pads()
    by_net = defaultdict(list)
    for part, pad, x, y in pads:
        if not pad.net or part.kind in ("electrode", "mount"):
            continue
        both = part.kind == "hdr"
        by_net[pad.net].append((part, pad, x, y, both))
    order = ["XTAL_P", "XTAL_N", "USB_P", "USB_N", "IO8", "IO9", "GATE",
             "VOUT", "VCC3", "V5", "DRAIN", "GND"]
    nets = [n for n in order if n in by_net]
    nets += [n for n in by_net if n not in nets and not n.startswith("E")]
    failed = []
    for net in nets:
        width = _net_width(net)
        for attempt, use_w in enumerate((width, 0.15)):
            err = _route_one(net, use_w, vias, tracks, pads, by_net[net])
            if not err:
                break
            if attempt == 1:
                failed.append(err)
    return failed


def _route_one(net, width, vias, tracks, pads, items) -> str:
    reached = _reached_cells(net, tracks, vias, pads)
    pending = []
    for part, pad, x, y, both in items:
        cells = _pad_cells(x, y, pad.w, pad.h, both)
        if reached & cells.keys():
            reached |= cells.keys()
            continue
        pending.append((cells, (x, y)))
    if not pending:
        return ""
    if not reached:
        cells, _xy = pending.pop(0)
        reached |= cells.keys()
    blocked = _blocked_for(net, width, tracks, vias, pads)
    via_blocked = _dilate(blocked)
    guard = 0
    while pending and guard < 40:
        guard += 1
        goals = {}
        owners = []
        for cells, xy in pending:
            for c, _pad in cells.items():
                goals[c] = xy
            owners.append((cells, xy))
        path = _bfs(reached, goals, blocked, via_blocked)
        if path is None:
            where = ", ".join(f"({xy[0]:.2f},{xy[1]:.2f})" for _c, xy in pending[:6])
            return f"Netz {net} offen, noch {len(pending)} Pads, Breite {width:.2f}: {where}"
        _commit_path(path, net, width, tracks, vias)
        walked = {item for item in path[:-1] if isinstance(item[1], int)}
        still = []
        for cells, xy in pending:
            if cells.keys() & (reached | walked):
                reached |= cells.keys()
            else:
                still.append((cells, xy))
        reached |= walked
        pending = still
        blocked = _blocked_for(net, width, tracks, vias, pads)
        via_blocked = _dilate(blocked)
    if pending:
        return f"Netz {net} unvollständig ({len(pending)})"
    return ""


def route_stuck(vias, tracks):
    """3,3 V der oberen Kante: unten nach links, die Sense-Senkrechten oben queren, an C4."""
    for pin in (17, 18, 19, 20):
        x, y, _w, _h = D.chip_pad(pin)
        poly(tracks, [(x, y), (x, 12.32)], 0.12, "F.Cu", "VCC3")
        vias.append(Via(x, 12.32, "VCC3", ESC_SIZE, ESC_DRILL))
        poly(tracks, [(x, 12.32), (x, 12.75)], 0.12, "B.Cu", "VCC3")
    poly(tracks, [(34.40, 12.75), (29.90, 12.75), (29.90, 7.05)], 0.15, "B.Cu", "VCC3")
    for pin in (1, 2, 27):
        px, py, _w, _h = D.chip_pad(pin)
        poly(tracks, [(px, py), (29.90, py)], 0.15, "F.Cu", "VCC3")
        vias.append(Via(29.90, py, "VCC3", ESC_SIZE, ESC_DRILL))
    vias.append(Via(29.90, 7.05, "VCC3", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(29.90, 7.05), (36.80, 7.05), (36.80, 8.35)], 0.15, "F.Cu", "VCC3")
    vias.append(Via(36.80, 8.35, "VCC3", ESC_SIZE, ESC_DRILL))
    _p, _pad, c4x, c4y = find_pad("C4", "1")
    poly(tracks, [(36.80, 8.35), (c4x, 8.35)], 0.15, "B.Cu", "VCC3")
    vias.append(Via(c4x, 8.35, "VCC3", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(c4x, 8.35), (c4x, c4y)], 0.20, "F.Cu", "VCC3")

    # D+ links am Quarz vorbei ins Loch. D− über dem Quarz in die Lücke vor BOOT.
    for net, xrail, yhop in (("USB_P", 29.40, 6.25), ("USB_N", 28.90, 7.45)):
        x, y, _w, _h = D.chip_pad(pin_of(net))
        poly(tracks, [(x, y), (xrail, y)], 0.15, "F.Cu", net)
        vias.append(Via(xrail, y, net, ESC_SIZE, ESC_DRILL))
        poly(tracks, [(xrail, y), (xrail, yhop)], 0.15, "B.Cu", net)
        vias.append(Via(xrail, yhop, net, ESC_SIZE, ESC_DRILL))
    _p, _pad, dpx, dpy = find_pad("J3", "2")
    poly(tracks, [(29.40, 6.25), (36.20, 6.25)], 0.15, "F.Cu", "USB_P")
    vias.append(Via(36.20, 6.25, "USB_P", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(36.20, 6.25), (39.87, 6.25), (39.87, dpy), (dpx, dpy)], 0.15, "B.Cu", "USB_P")
    _p, _pad, dnx, dny = find_pad("J3", "3")
    poly(tracks, [(28.90, 7.45), (36.20, 7.45)], 0.15, "F.Cu", "USB_N")
    vias.append(Via(36.20, 7.45, "USB_N", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(36.20, 7.45), (40.50, 7.45)], 0.15, "B.Cu", "USB_N")
    vias.append(Via(40.50, 7.45, "USB_N", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(40.50, 7.45), (40.50, 9.05), (43.20, 9.05), (43.20, dny), (dnx, dny)], 0.15, "F.Cu", "USB_N")

    # C3-GND an den LDO. C5-GND links an das EP.
    _p, _pad, g3x, g3y = find_pad("C3", "2")
    _p, _pad, ugx, ugy = find_pad("U2", "1")
    poly(tracks, [(g3x, g3y), (48.70, g3y), (48.70, ugy), (ugx, ugy)], 0.20, "F.Cu", "GND")
    _p, _pad, g5x, g5y = find_pad("C5", "2")
    poly(tracks, [(g5x, g5y), (g5x, 5.85), (28.40, 5.85)], 0.15, "F.Cu", "GND")
    vias.append(Via(28.40, 5.85, "GND", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(28.40, 5.85), (28.40, 8.25)], 0.15, "B.Cu", "GND")
    # EP und Stich-Vias verbindet der Router. Hier endet die GND-Schiene.
    # Quarz-Lastkondensatoren direkt an die Quarzpads.
    _p, _pad, y1x, y1y = find_pad("Y1", "1")
    _p, _pad, c1x, c1y = find_pad("C1", "2")
    poly(tracks, [(y1x, y1y), (c1x, c1y)], 0.15, "F.Cu", "XTAL_P")
    _p, _pad, y3x, y3y = find_pad("Y1", "3")
    _p, _pad, c2x, c2y = find_pad("C2", "1")
    poly(tracks, [(y3x, y3y), (c2x, c2y)], 0.15, "F.Cu", "XTAL_N")
    # XTAL_N vom Chip: links an den Schienen vorbei, die Sense-Senkrechten oben queren.
    nx, ny, _w, _h = D.chip_pad(pin_of("XTAL_N"))
    poly(tracks, [(nx, ny), (30.24, ny)], 0.12, "F.Cu", "XTAL_N")
    vias.append(Via(30.24, ny, "XTAL_N", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(30.24, ny), (30.24, 6.65)], 0.12, "B.Cu", "XTAL_N")
    vias.append(Via(30.24, 6.65, "XTAL_N", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(30.24, 6.65), (37.20, 6.65), (37.20, 8.70)], 0.15, "F.Cu", "XTAL_N")
    vias.append(Via(37.20, 8.70, "XTAL_N", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(37.20, 8.70), (y3x, 8.70)], 0.15, "B.Cu", "XTAL_N")
    vias.append(Via(y3x, 8.70, "XTAL_N", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(y3x, 8.70), (y3x, y3y)], 0.15, "F.Cu", "XTAL_N")
    # Die beiden Massepads des Quarzes, unter dem D−-Abgang durch.
    _p, _pad, g4x, g4y = find_pad("Y1", "4")
    _p, _pad, g2x, g2y = find_pad("Y1", "2")
    poly(tracks, [(g4x, g4y), (g4x, 7.20)], 0.15, "F.Cu", "GND")
    vias.append(Via(g4x, 7.20, "GND", ESC_SIZE, ESC_DRILL))
    poly(tracks, [(g4x, 7.20), (g4x, 6.90), (g2x, 6.90), (g2x, g2y)], 0.15, "B.Cu", "GND")
    vias.append(Via(g2x, g2y, "GND", ESC_SIZE, ESC_DRILL))


def route_all(vias, tracks) -> list[str]:
    route_sense(vias, tracks)
    route_fixed(vias, tracks)
    route_stuck(vias, tracks)
    return route_maze(vias, tracks)


# ---------------------------------------------------------------- Prüfungen

def _pt_seg(px, py, ax, ay, bx, by):
    vx, vy = bx - ax, by - ay
    length = vx * vx + vy * vy
    if length < 1e-9:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * vx + (py - ay) * vy) / length))
    return math.hypot(px - (ax + t * vx), py - (ay + t * vy))


def _seg_dist(a, b):
    ax, ay, bx, by = a
    cx, cy, dx, dy = b
    rx, ry = bx - ax, by - ay
    sx, sy = dx - cx, dy - cy
    den = rx * sy - ry * sx
    if abs(den) > 1e-9:
        t = ((cx - ax) * sy - (cy - ay) * sx) / den
        u = ((cx - ax) * ry - (cy - ay) * rx) / den
        if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
            return 0.0
    return min(
        _pt_seg(ax, ay, cx, cy, dx, dy),
        _pt_seg(bx, by, cx, cy, dx, dy),
        _pt_seg(cx, cy, ax, ay, bx, by),
        _pt_seg(dx, dy, ax, ay, bx, by),
    )


def seg_hits_rect(x1, y1, x2, y2, rect) -> bool:
    rx0, ry0, rx1, ry1 = rect
    if (rx0 <= x1 <= rx1 and ry0 <= y1 <= ry1) or (rx0 <= x2 <= rx1 and ry0 <= y2 <= ry1):
        return True
    # Kante schneidet das Rechteck: Abstand der Strecke zu einem Innenpunkt ist kein guter Test.
    # Schneidet eine Rechteckkante.
    edges = (
        (rx0, ry0, rx1, ry0), (rx1, ry0, rx1, ry1),
        (rx1, ry1, rx0, ry1), (rx0, ry1, rx0, ry0),
    )
    return any(_seg_dist((x1, y1, x2, y2), edge) < 1e-6 for edge in edges)


def check_keepout(tracks, vias, pads) -> list[str]:
    hits = []
    allowed = {"RF"}
    for t in tracks:
        if t.net in allowed:
            continue
        for rect in D.KEEPOUT:
            if seg_hits_rect(t.x1, t.y1, t.x2, t.y2, rect):
                hits.append(f"Bahn {t.net} in Sperrzone ({t.x1:.2f},{t.y1:.2f})-({t.x2:.2f},{t.y2:.2f})")
                break
    for v in vias:
        if v.net in allowed:
            continue
        if D.in_keepout(v.x, v.y):
            hits.append(f"Via {v.net} in Sperrzone ({v.x:.2f},{v.y:.2f})")
    for part, pad, x, y in pads:
        if pad.net in allowed or part.kind in ("electrode", "feed"):
            continue
        if D.in_keepout(x, y):
            hits.append(f"Pad {part.ref}.{pad.name} {pad.net} in Sperrzone ({x:.2f},{y:.2f})")
    return hits


def check_clearance(tracks, vias) -> list[str]:
    hits = []
    items = [(t.net, t.layer, (t.x1, t.y1, t.x2, t.y2), t.width) for t in tracks]
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            if a[0] == b[0] or a[1] != b[1] or not a[0] or not b[0]:
                continue
            gap = _seg_dist(a[2], b[2]) - a[3] / 2 - b[3] / 2
            if gap < D.CLEARANCE - 0.02:
                hits.append(
                    f"Abstand {gap:.3f} {a[0]}/{b[0]} {a[1]} "
                    f"({a[2][0]:.2f},{a[2][1]:.2f})-({a[2][2]:.2f},{a[2][3]:.2f})"
                )
                if len(hits) > 24:
                    return hits
    for v in vias:
        for net, layer, seg, width in items:
            if net == v.net or not net:
                continue
            gap = _pt_seg(v.x, v.y, *seg) - v.size / 2 - width / 2
            if gap < D.CLEARANCE - 0.02:
                hits.append(
                    f"Via {v.net} ({v.x:.2f},{v.y:.2f}) an {net}: {gap:.3f}"
                )
                if len(hits) > 24:
                    return hits
    return hits


def check_mount(tracks, vias) -> list[str]:
    r = D.MOUNT_DRILL / 2
    hits = []
    for t in tracks:
        gap = _pt_seg(D.MOUNT_X, D.MOUNT_Y, t.x1, t.y1, t.x2, t.y2) - r - t.width / 2
        if gap < D.CLEARANCE - 0.02:
            hits.append(f"MH1 Bahn {t.net} {gap:.3f}")
    for v in vias:
        gap = math.hypot(v.x - D.MOUNT_X, v.y - D.MOUNT_Y) - r - v.size / 2
        if gap < D.CLEARANCE - 0.02:
            hits.append(f"MH1 Via {v.net} {gap:.3f}")
    return hits[:12]


def check_bounds(tracks, vias, pads) -> list[str]:
    L = D.board_length()
    hits = []
    margin = 0.10

    def bad(x, y, what):
        if x < margin or y < margin or x > L - margin or y > D.BOARD_W - margin:
            hits.append(f"außerhalb {what} ({x:.2f},{y:.2f})")

    for t in tracks:
        bad(t.x1, t.y1, t.net)
        bad(t.x2, t.y2, t.net)
    for v in vias:
        bad(v.x, v.y, "via " + v.net)
    for part, pad, x, y in pads:
        if part.kind == "electrode":
            continue
        bad(x, y, part.ref)
    return hits[:12]


def _hits_rect(x1, y1, x2, y2, cx, cy, hw, hh) -> bool:
    """Strecke schneidet das achsenparallele Rechteck um (cx, cy)."""
    def inside(x, y):
        return abs(x - cx) <= hw and abs(y - cy) <= hh

    if inside(x1, y1) or inside(x2, y2):
        return True
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in (
        (-dx, x1 - (cx - hw)), (dx, (cx + hw) - x1),
        (-dy, y1 - (cy - hh)), (dy, (cy + hh) - y1),
    ):
        if abs(p) < 1e-12:
            if q < 0:
                return False
            continue
        r = q / p
        if p < 0:
            if r > t1:
                return False
            t0 = max(t0, r)
        else:
            if r < t0:
                return False
            t1 = min(t1, r)
    return t0 <= t1


def _in_gnd_zone(x, y, radius, length) -> bool:
    """Punkt (mit Kupferradius) liegt in einer der beiden GND-Flächen unten."""
    _x0, _y0, x1, y1 = D.KEEPOUT[0]
    rects = (
        (0.4, y1 + 0.15, length - 0.4, D.BOARD_W - 0.25),
        (x1 + 0.3, 0.25, length - 0.4, y1 + 0.05),
    )
    for xa, ya, xb, yb in rects:
        if xa - radius <= x <= xb + radius and ya - radius <= y <= yb + radius:
            return True
    return False


def check_open(pads, vias, tracks) -> list[str]:
    """Pad ohne Kupfer, oder zwei Inseln im selben Netz."""
    parent: dict = {}

    def find(key):
        parent.setdefault(key, key)
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    groups = defaultdict(list)
    for i, t in enumerate(tracks):
        if t.net:
            groups[t.net].append(i)
            find(("t", i))
    for net, ids in groups.items():
        for a in range(len(ids)):
            ta = tracks[ids[a]]
            for b in range(a + 1, len(ids)):
                tb = tracks[ids[b]]
                if ta.layer != tb.layer:
                    continue
                touch = (ta.width + tb.width) / 2 + 0.02
                if (
                    _pt_seg(ta.x1, ta.y1, tb.x1, tb.y1, tb.x2, tb.y2) <= touch
                    or _pt_seg(ta.x2, ta.y2, tb.x1, tb.y1, tb.x2, tb.y2) <= touch
                    or _pt_seg(tb.x1, tb.y1, ta.x1, ta.y1, ta.x2, ta.y2) <= touch
                    or _pt_seg(tb.x2, tb.y2, ta.x1, ta.y1, ta.x2, ta.y2) <= touch
                ):
                    union(("t", ids[a]), ("t", ids[b]))
    for vi, v in enumerate(vias):
        if not v.net:
            continue
        find(("v", vi))
        for i in groups.get(v.net, ()):
            t = tracks[i]
            if _pt_seg(v.x, v.y, t.x1, t.y1, t.x2, t.y2) <= v.size / 2 + t.width / 2 + 0.02:
                union(("v", vi), ("t", i))

    # Das Pad selbst leitet: Bahnen, die nur das Pad berühren, sind verbunden.
    for part, pad, x, y in pads:
        if not pad.net:
            continue
        layers = ("F.Cu", "B.Cu") if part.kind == "hdr" else ("F.Cu",)
        hitters = []
        for i, t in enumerate(tracks):
            if t.net != pad.net or t.layer not in layers:
                continue
            if _hits_rect(
                t.x1, t.y1, t.x2, t.y2, x, y,
                pad.w / 2 + t.width / 2, pad.h / 2 + t.width / 2,
            ):
                hitters.append(("t", i))
        for vi, v in enumerate(vias):
            if v.net == pad.net and abs(v.x - x) <= pad.w / 2 and abs(v.y - y) <= pad.h / 2:
                hitters.append(("v", vi))
        for other in hitters[1:]:
            union(hitters[0], other)

    # Unterseiten-Massefläche verbindet GND-Vias und GND-Bahnen, die in ihr liegen.
    L = D.board_length()
    zone = ("zone", "GND")
    for vi, v in enumerate(vias):
        if v.net == "GND" and _in_gnd_zone(v.x, v.y, v.size / 2, L):
            union(zone, ("v", vi))
    for i, t in enumerate(tracks):
        if t.net != "GND" or t.layer != "B.Cu":
            continue
        if _in_gnd_zone(t.x1, t.y1, t.width / 2, L) or _in_gnd_zone(t.x2, t.y2, t.width / 2, L):
            union(zone, ("t", i))

    by = defaultdict(list)
    for part, pad, x, y in pads:
        if pad.net:
            by[pad.net].append((part, pad, x, y))
    hits = []
    for net, group in by.items():
        if len(group) < 2:
            continue
        roots = []
        for part, pad, x, y in group:
            layers = ("F.Cu", "B.Cu") if part.kind == "hdr" else ("F.Cu",)
            root = None
            for i, t in enumerate(tracks):
                if t.net != net or t.layer not in layers:
                    continue
                # Rechteck um die halbe Bahnbreite erweitert, sonst verfehlt der Enddeckel das Pad.
                if _hits_rect(
                    t.x1, t.y1, t.x2, t.y2, x, y,
                    pad.w / 2 + t.width / 2, pad.h / 2 + t.width / 2,
                ):
                    root = find(("t", i))
                    break
            if root is None:
                for vi, v in enumerate(vias):
                    if v.net == net and abs(v.x - x) <= pad.w / 2 and abs(v.y - y) <= pad.h / 2:
                        root = find(("v", vi))
                        break
            roots.append((f"{part.ref}.{pad.name}", root))
        missing = [name for name, root in roots if root is None]
        comps = {root for _, root in roots if root is not None}
        if missing or len(comps) > 1:
            where = ", ".join(missing) if missing else f"{len(comps)} Inseln"
            hits.append(f"Netz {net} offen: {where}")
    return hits


# ---------------------------------------------------------------- Ausgabe

def emit_pcb(tracks, vias):
    L = D.board_length()
    lines = [
        "(kicad_pcb",
        "\t(version 20260206)",
        '\t(generator "wasserstand_zigbee")',
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
    chamfer = 1.0
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
    water = D.ELEC0_X - D.ELEC_ALONG / 2 - 0.8
    lines.append(
        f'\t(gr_line (start {water:.3f} 0.4) (end {water:.3f} {D.BOARD_W - 0.4:.3f}) '
        f'(stroke (width 0.15) (type default)) (layer "F.SilkS") (uuid "{uid()}"))'
    )
    lines.append(
        f'\t(gr_text "MAX" (at {water - 1.3:.3f} 7 90) (layer "F.SilkS") (uuid "{uid()}") '
        f'(effects (font (size 0.7 0.7) (thickness 0.1))))'
    )
    lines.append(
        f'\t(gr_text "ZIG-16" (at 20.0 13.2 0) (layer "F.SilkS") (uuid "{uid()}") '
        f'(effects (font (size 0.7 0.7) (thickness 0.1))))'
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
    with open(PCB_PATH, "w", encoding="utf-8") as f:
        f.write(text)


def fp_rect(x1, y1, x2, y2, layer):
    return (
        f'\t\t(fp_rect (start {x1:.3f} {y1:.3f}) (end {x2:.3f} {y2:.3f}) '
        f'(stroke (width 0.05) (type solid)) (fill no) (layer "{layer}") (uuid "{uid()}"))'
    )


def emit_fp(part: D.Part):
    attr = "through_hole" if part.kind in ("hdr", "mount") else "smd"
    if part.kind == "mount":
        attr = "through_hole board_only"
    lines = [
        f'\t(footprint "zig:{part.kind}"',
        '\t\t(layer "F.Cu")',
        f'\t\t(uuid "{uid()}")',
        f'\t\t(at {part.x:.4f} {part.y:.4f})',
        f"\t\t(attr {attr})",
        f'\t\t(property "Reference" "{part.ref}" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid "{uid()}") '
        f'(effects (font (size 0.5 0.5) (thickness 0.08))))',
        f'\t\t(property "Value" "{sexp_escape(part.value)}" (at 0 0 0) (layer "F.Fab") (hide yes) '
        f'(uuid "{uid()}") (effects (font (size 0.4 0.4) (thickness 0.06))))',
    ]
    if part.kind == "qfn32":
        lines.append(fp_rect(-2.0, -2.0, 2.0, 2.0, "F.Fab"))
        lines.append(fp_rect(-2.6, -2.6, 2.6, 2.6, "F.CrtYd"))
        lines.append(
            f'\t\t(fp_circle (center -2.3 -2.3) (end -2.05 -2.3) (stroke (width 0.12) (type solid)) '
            f'(fill yes) (layer "F.SilkS") (uuid "{uid()}"))'
        )
    elif part.kind == "hdr":
        labels = getattr(part, "labels", ())
        label_dy = getattr(part, "label_dy", 1.15)
        for pad, label in zip(part.pads, labels):
            lines.append(
                f'\t\t(fp_text user "{label}" (at {pad.x:.2f} {pad.y + label_dy:.2f} 0) (layer "F.SilkS") '
                f'(uuid "{uid()}") (effects (font (size 0.45 0.45) (thickness 0.08))))'
            )
    elif part.kind == "electrode":
        lines.append(
            f'\t\t(fp_text user "{part.ref[1:]}" (at 0 {-part.pads[0].h / 2 - 0.15:.3f}) (layer "F.SilkS") '
            f'(uuid "{uid()}") (effects (font (size 0.5 0.5) (thickness 0.08))))'
        )
    elif part.kind == "mount":
        lines.append(
            f'\t\t(fp_circle (center 0 0) (end {D.MOUNT_PAD / 2:.2f} 0) '
            f'(stroke (width 0.12) (type solid)) (fill no) (layer "F.SilkS") (uuid "{uid()}"))'
        )
    elif part.kind == "xtal3225":
        lines.append(fp_rect(-1.6, -1.25, 1.6, 1.25, "F.Fab"))
    elif part.kind == "sot223":
        lines.append(fp_rect(-3.2, -3.4, 3.3, 3.4, "F.Fab"))
    elif part.kind == "sot23":
        lines.append(fp_rect(-1.4, -1.3, 1.4, 1.3, "F.Fab"))
    for pad in part.pads:
        net = f' (net "{sexp_escape(pad.net)}")' if pad.net else ""
        if part.kind == "hdr":
            lines.append(
                f'\t\t(pad "{pad.name}" thru_hole circle (at {pad.x:.4f} {pad.y:.4f}) '
                f'(size {pad.w:.4f} {pad.h:.4f}) (drill {D.HOLE_DRILL:.2f}) (layers "*.Cu" "*.Mask"){net} '
                f'(uuid "{uid()}"))'
            )
            continue
        if part.kind == "mount":
            lines.append(
                f'\t\t(pad "" np_thru_hole circle (at 0 0) (size {pad.w:.4f} {pad.h:.4f}) '
                f'(drill {D.MOUNT_DRILL:.2f}) (layers "*.Cu" "*.Mask") (uuid "{uid()}"))'
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
            f'(size {pad.w:.4f} {pad.h:.4f}) (layers {layer_s}) (roundrect_rratio 0.15){net} '
            f'(uuid "{uid()}"))'
        )
    lines.append("\t\t(embedded_fonts no)")
    lines.append("\t)")
    return lines


def _zone(name, layer, net, pts):
    body = " ".join(f"(xy {x:.3f} {y:.3f})" for x, y in pts)
    return (
        "\t(zone\n"
        f'\t\t(net "{net}")\n'
        f'\t\t(uuid "{uid()}")\n'
        f'\t\t(name "{name}")\n'
        f'\t\t(layers "{layer}")\n'
        "\t\t(hatch edge 0.5)\n"
        "\t\t(priority 0)\n"
        "\t\t(connect_pads (clearance 0.20))\n"
        "\t\t(min_thickness 0.2)\n"
        "\t\t(fill (thermal_gap 0.20) (thermal_bridge_width 0.30) (island_removal_mode 1))\n"
        f"\t\t(polygon (pts {body}))\n"
        "\t)"
    )


def emit_zones(length):
    _x0, _y0, x1, y1 = D.KEEPOUT[0]
    # Masse nur unten, als Bezug der HF-Leitung. Oben im Korridor kein GND,
    # sonst wird der Streifen koplanar. Die Sperrzone bleibt ausgespart.
    gnd_b = [
        (0.4, y1 + 0.15),
        (length - 0.4, y1 + 0.15),
        (length - 0.4, D.BOARD_W - 0.25),
        (0.4, D.BOARD_W - 0.25),
    ]
    gnd_b2 = [
        (x1 + 0.3, 0.25),
        (length - 0.4, 0.25),
        (length - 0.4, y1 + 0.05),
        (x1 + 0.3, y1 + 0.05),
    ]
    ant = D.antenna_poly()
    return [
        _zone("GND-B-hi", "B.Cu", "GND", gnd_b),
        _zone("GND-B-tip", "B.Cu", "GND", gnd_b2),
        _zone("ANT", "F.Cu", "RF", ant),
    ]


def write_svg(tracks, vias, name, x0, x1, title):
    w, h = D.BOARD_W, x1 - x0
    sc = 22 if (x1 - x0) > 40 else 28
    margin = 16

    def px(y):
        return margin + y * sc

    def py(x):
        return margin + (x - x0) * sc

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w * sc + 2 * margin:.0f}" '
        f'height="{h * sc + 2 * margin:.0f}" viewBox="0 0 {w * sc + 2 * margin:.1f} {h * sc + 2 * margin:.1f}">',
        '<rect width="100%" height="100%" fill="#1b1d1a"/>',
        f'<text x="{margin}" y="13" fill="#ddd" font-size="11" font-family="sans-serif">{title}</text>',
    ]
    L = D.board_length()
    parts.append(
        f'<rect x="{px(0):.1f}" y="{py(max(x0, 0)):.1f}" width="{D.BOARD_W * sc:.1f}" '
        f'height="{(min(L, x1) - max(x0, 0)) * sc:.1f}" fill="#14301c" stroke="#8d8" stroke-width="1"/>'
    )
    poly = " ".join(f"{px(y):.1f},{py(x):.1f}" for x, y in D.antenna_poly())
    parts.append(f'<polygon points="{poly}" fill="#c9a227" opacity="0.85"/>')
    for part in D.PARTS:
        for pad in part.pads:
            x, y = part.x + pad.x, part.y + pad.y
            if not (x0 - 2 <= x <= x1 + 2):
                continue
            col = "#e8e2d4"
            if pad.net.startswith("E"):
                col = "#c45c26"
            elif pad.net == "GND":
                col = "#8a8f7a"
            elif pad.net == "RF":
                col = "#e0b040"
            parts.append(
                f'<rect x="{px(y - pad.h / 2):.2f}" y="{py(x - pad.w / 2):.2f}" '
                f'width="{pad.h * sc:.2f}" height="{pad.w * sc:.2f}" fill="{col}"/>'
            )
    for t in tracks:
        if max(t.x1, t.x2) < x0 - 1 or min(t.x1, t.x2) > x1 + 1:
            continue
        col = "#3a7bd5" if t.layer == "B.Cu" else "#e24b4b"
        parts.append(
            f'<line x1="{px(t.y1):.2f}" y1="{py(t.x1):.2f}" x2="{px(t.y2):.2f}" y2="{py(t.x2):.2f}" '
            f'stroke="{col}" stroke-width="{max(0.8, t.width * sc * 0.45):.2f}" stroke-linecap="round"/>'
        )
    for v in vias:
        if not (x0 - 1 <= v.x <= x1 + 1):
            continue
        parts.append(
            f'<circle cx="{px(v.y):.2f}" cy="{py(v.x):.2f}" r="{2.2}" fill="none" stroke="#9f9"/>'
        )
    for part in D.PARTS:
        if part.kind in ("electrode", "r0402") or not (x0 <= part.x <= x1):
            continue
        parts.append(
            f'<text x="{px(part.y) + 2:.1f}" y="{py(part.x):.1f}" fill="#fff" font-size="8" '
            f'font-family="sans-serif">{part.ref}</text>'
        )
    parts.append("</svg>")
    os.makedirs(PREVIEW, exist_ok=True)
    path = os.path.join(PREVIEW, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(parts))
    return path


def main() -> int:
    vias: list[Via] = []
    tracks: list[Track] = []
    problems = route_all(vias, tracks)
    pads = world_pads()
    problems += check_keepout(tracks, vias, pads)
    problems += check_clearance(tracks, vias)
    problems += check_mount(tracks, vias)
    problems += check_bounds(tracks, vias, pads)
    problems += check_open(pads, vias, tracks)
    emit_pcb(tracks, vias)
    L = D.board_length()
    write_svg(tracks, vias, "platine.svg", 0, L, f"Zigbee 16 Stufen, {L:.0f} mm")
    write_svg(tracks, vias, "kopf.svg", 0, D.RES_X + 4, "Kopf: Antenne, H2, Ventil")
    print(f"{PCB_PATH}  Länge {L:.1f} mm  Bahnen {len(tracks)}  Vias {len(vias)}")
    if problems:
        print(f"{len(problems)} Konflikte:")
        for line in problems[:30]:
            print(" ", line)
        return 1
    print("Sperrzone, Abstand, Bohrung, Netze: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
