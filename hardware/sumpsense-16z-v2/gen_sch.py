"""Lesbarer KiCad-Schaltplan zur handgepflegten Platine.

  python3 gen_sch.py

Netze und Pads kommen aus sumpsense-16z-v2.kicad_pcb, die Symbole aus der
KiCad-10-Bibliothek (nur das ESP32-H2-MINI-1 ist ein eigenes Symbol, die Bibliothek hat
keins). Die Anordnung ist nach Funktionsblöcken: Versorgung, Ventil, Modul,
EN, USB/Flash, Stufen. Verbindungen über Versorgungssymbole und
beschriftete Netze, kurze Strecken als Leitung.
"""

import os
import re
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sumpsense-16z-v2.kicad_sch")
PCB = os.path.join(HERE, "sumpsense-16z-v2.kicad_pcb")
PROJECT = "sumpsense-16z-v2"
LIBDIRS = [
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "KiCad", "10.0", "share", "kicad", "symbols"),
    os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), "KiCad", "10.0", "share", "kicad", "symbols"),
    "/usr/share/kicad/symbols",
    os.path.expanduser("~/.local/share/kicad/squashfs-root/usr/share/kicad/symbols"),
]
NS = "wasserstand-zigbee-sch"
GLOBAL_NAMES = False
POWER = {"GND": "power:GND", "+3V3": "power:+3V3", "+5V": "power:+5V", "PWR_FLAG": "power:PWR_FLAG"}


def uid(text):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{NS}:{text}"))


ROOT = uid("root")


# ---------------------------------------------------------------- S-Ausdrücke
def block(s, start):
    d, instr = 0, False
    for k in range(start, len(s)):
        c = s[k]
        if instr:
            if c == '"' and s[k - 1] != "\\":
                instr = False
            continue
        if c == '"':
            instr = True
        elif c == "(":
            d += 1
        elif c == ")":
            d -= 1
            if d == 0:
                return k + 1
    raise ValueError("unbalanciert")


def top_blocks(s, head):
    i = 0
    while True:
        i = s.find(head, i)
        if i < 0:
            return
        e = block(s, i)
        yield s[i:e]
        i = e


# ---------------------------------------------------------------- Bibliothek
def libdir():
    for d in LIBDIRS:
        if os.path.isfile(os.path.join(d, "Device.kicad_sym")):
            return d
    raise SystemExit("KiCad-Symbolbibliothek nicht gefunden")


_libcache = {}


def lib_text(lib):
    if lib not in _libcache:
        _libcache[lib] = open(os.path.join(libdir(), lib + ".kicad_sym"), encoding="utf-8").read()
    return _libcache[lib]


def raw_symbol(lib, name):
    s = lib_text(lib)
    i = s.index(f'\n\t(symbol "{name}"') + 1
    return s[i:block(s, i)]


def flat_symbol(lib_id):
    """Symbol aus der Bibliothek, 'extends' aufgelöst, Name mit Bibliothek."""
    lib, name = lib_id.split(":")
    t = raw_symbol(lib, name)
    m = re.search(r'\(extends "([^"]+)"\)', t)
    if m:
        parent = raw_symbol(lib, m.group(1))
        props = re.findall(r'\(property "[^"]+".*?\n\t\t\)', t, re.S)
        body = parent
        for p in props:
            key = re.match(r'\(property "([^"]+)"', p).group(1)
            body = re.sub(r'\(property "%s".*?\n\t\t\)' % re.escape(key), lambda _m: p, body, count=1, flags=re.S)
        body = body.replace(f'(symbol "{m.group(1)}_', f'(symbol "{name}_')
        t = body.replace(f'(symbol "{m.group(1)}"', f'(symbol "{name}"', 1)
    t = t.replace(f'(symbol "{name}"', f'(symbol "{lib_id}"', 1)
    return t


PIN_RE = re.compile(r'\(pin (\w+) (\w+)\s*\(at ([-\d.]+) ([-\d.]+) ([-\d.]+)\)\s*\(length ([-\d.]+)\)'
                    r'(?:(?!\(pin ).)*?\(name "([^"]*)"(?:(?!\(pin ).)*?\(number "([^"]*)"', re.S)


def pins_of(symtext):
    """Pinnummer -> (x, y, winkel) in Bibliothekskoordinaten (y nach oben)."""
    return {p[7]: (float(p[2]), float(p[3]), float(p[4])) for p in PIN_RE.findall(symtext)}


# ---------------------------------------------------------------- eigenes Modul-Symbol
MOD_LEFT = [  # (pin, name, typ) von oben nach unten, None = Lücke
    ("3", "3V3", "power_in"), ("15", "VBAT", "passive"), ("8", "EN", "input"), None,
    ("27", "IO27/USB_D+", "bidirectional"), ("26", "IO26/USB_D-", "bidirectional"),
]
MOD_RIGHT = [
    ("9", "IO0"), ("10", "IO1"), ("5", "IO2"), ("6", "IO3"), ("18", "IO4"), ("19", "IO5"), None,
    ("22", "IO8"), ("23", "IO9"), ("20", "IO10"), ("21", "IO11"), ("16", "IO12"), ("12", "IO13"), ("13", "IO14"), None,
    ("24", "IO22"), ("30", "IO23/RXD0"), ("31", "IO24/TXD0"), ("25", "IO25"),
]
MOD_GND = ["1", "2", "11", "14"] + [str(n) for n in range(36, 54)]
MOD_NC = ["4", "7", "17", "28", "29", "32", "33", "34", "35"]


def h2_symbol():
    rows = max(len(MOD_LEFT), len(MOD_RIGHT))
    top = (rows - 1) / 2 * 2.54
    w = 17.78
    pins = []

    def pin(num, name, x, y, ang, etype, hide=False):
        hid = " (hide yes)" if hide else ""
        pins.append(
            f'\t\t\t(pin {etype} line (at {x:.2f} {y:.2f} {ang}) (length 2.54){hid}\n'
            f'\t\t\t\t(name "{name}" (effects (font (size 1.27 1.27))))\n'
            f'\t\t\t\t(number "{num}" (effects (font (size 1.27 1.27))))\n\t\t\t)')

    for i, e in enumerate(MOD_LEFT):
        if e:
            pin(e[0], e[1], -w - 2.54, top - i * 2.54, 0, e[2])
    for i, e in enumerate(MOD_RIGHT):
        if e:
            pin(e[0], e[1], w + 2.54, top - i * 2.54, 180, "bidirectional")
    for k, n in enumerate(MOD_GND):                 # gestapelt, nur der erste sichtbar
        pin(n, "GND", 0, -top - 5.08, 90, "power_in", hide=k > 0)
    for k, n in enumerate(MOD_NC):
        pin(n, "NC", -w + 2.54 + 1.27 * k, -top - 2.54, 90, "no_connect", hide=True)
    body = (f'\t\t\t(rectangle (start {-w:.2f} {top + 2.54:.2f}) (end {w:.2f} {-top - 2.54:.2f})\n'
            '\t\t\t\t(stroke (width 0.254) (type default)) (fill (type background)))')
    return (
        '\t\t(symbol "zig:ESP32-H2-MINI-1"\n'
        '\t\t\t(pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
        f'\t\t\t(property "Reference" "U" (at {-w:.2f} {top + 3.81:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
        f'\t\t\t(property "Value" "ESP32-H2-MINI-1" (at {w:.2f} {top + 3.81:.2f} 0) (effects (font (size 1.27 1.27)) (justify right)))\n'
        '\t\t\t(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        '\t\t\t(property "Datasheet" "https://documentation.espressif.com/esp32-h2-mini-1_mini-1u_datasheet_en.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        '\t\t\t(property "Description" "ESP32-H2-MINI-1(-H4S): Modul mit 32-MHz-Quarz und PCB-Antenne" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        '\t\t\t(symbol "ESP32-H2-MINI-1_0_1"\n' + body + '\n\t\t\t)\n'
        '\t\t\t(symbol "ESP32-H2-MINI-1_1_1"\n' + "\n".join(pins) + '\n\t\t\t)\n'
        '\t\t\t(embedded_fonts no)\n\t\t)')


# ---------------------------------------------------------------- Platine lesen
def pcb_parts():
    s = open(PCB, encoding="utf-8").read()
    parts = {}
    for blk in top_blocks(s, "\t(footprint "):
        lib = re.match(r'\t?\(footprint "([^"]+)"', blk).group(1)
        ref = re.search(r'\(property "Reference" "([^"]+)"', blk).group(1)
        val = re.search(r'\(property "Value" "([^"]*)"', blk).group(1)
        nets = {}
        for m in re.finditer(r'\(pad "([^"]*)"(.*?)\(uuid', blk, re.S):
            n = re.search(r'\(net (?:\d+ )?"([^"]*)"\)', m.group(2))
            if m.group(1) and n:
                nets.setdefault(m.group(1), n.group(1).lstrip("/"))
        parts[ref] = (lib, val, nets)
    return parts


# ---------------------------------------------------------------- Zeichnen
class Sheet:
    def __init__(self, parts):
        self.parts = parts
        self.libs = {}
        self.pins = {}
        self.items = []
        self.placed = {}
        self.npwr = 0
        self.used_nets = set()

    def lib(self, lib_id):
        if lib_id not in self.libs:
            t = h2_symbol() if lib_id == "zig:ESP32-H2-MINI-1" else "\t\t" + flat_symbol(lib_id).replace("\n\t", "\n\t\t")
            self.libs[lib_id] = t
            self.pins[lib_id] = pins_of(t)
        return self.pins[lib_id]

    @staticmethod
    def rot(x, y, r):
        # Bibliothek (y oben) -> Blatt (y unten), dann Drehung gegen den Uhrzeigersinn
        x, y = x, -y
        return {0: (x, y), 90: (y, -x), 180: (-x, -y), 270: (-y, x)}[r]

    def place(self, ref, lib_id, x, y, rot=0, value=None, ref_off=None, val_off=None, hide_value=False, fa=None):
        pins = self.lib(lib_id)
        lib, val, nets = self.parts.get(ref, ("", "", {}))
        value = value or val
        conn = {}
        for num, (px, py, pa) in pins.items():
            dx, dy = self.rot(px, py, rot)
            # Richtung vom Anschluss zum Körper, umgedreht = nach außen
            import math
            vx, vy = math.cos(math.radians(pa)), math.sin(math.radians(pa))
            ox, oy = self.rot(-vx, -vy, rot)
            conn[num] = (round(x + dx, 2), round(y + dy, 2), round(ox), round(oy))
        self.placed[ref] = (lib_id, conn, nets)
        if fa is None:
            fa = 90 if rot in (90, 270) else 0
        rx, ry = ref_off or (2.54, -1.27)
        vx_, vy_ = val_off or (2.54, 1.27)
        self.items.append(
            f'\t(symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} {rot}) (unit 1) (exclude_from_sim no) '
            f'(in_bom {"no" if ref.startswith("J") or ref == "MH1" else "yes"}) (on_board yes) (dnp no) (uuid "{uid(ref)}")\n'
            f'\t\t(property "Reference" "{ref}" (at {x + rx:.2f} {y + ry:.2f} {fa}) (effects (font (size 1.27 1.27)) (justify left)))\n'
            f'\t\t(property "Value" "{value}" (at {x + vx_:.2f} {y + vy_:.2f} {fa}) (effects (font (size 1.27 1.27)) (justify left)'
            f'{" (hide yes)" if hide_value else ""}))\n'
            f'\t\t(property "Footprint" "{lib}" (at {x:.2f} {y:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            + "".join(f'\t\t(pin "{n}" (uuid "{uid(ref + "p" + n)}"))\n' for n in pins)
            + f'\t\t(instances (project "{PROJECT}" (path "/{ROOT}" (reference "{ref}") (unit 1))))\n\t)')
        return conn

    def wire(self, *pts):
        for (x1, y1), (x2, y2) in zip(pts, pts[1:]):
            if (x1, y1) == (x2, y2):
                continue
            self.items.append(f'\t(wire (pts (xy {x1:.2f} {y1:.2f}) (xy {x2:.2f} {y2:.2f})) '
                              f'(stroke (width 0) (type default)) (uuid "{uid(f"w{x1},{y1},{x2},{y2}")}"))')

    def junction(self, x, y):
        self.items.append(f'\t(junction (at {x:.2f} {y:.2f}) (diameter 0) (color 0 0 0 0) (uuid "{uid(f"j{x},{y}")}"))')

    def power(self, net, x, y):
        self.npwr += 1
        lib_id = POWER[net]
        self.lib(lib_id)
        ref = f"#PWR{self.npwr:03d}"
        off = 3.81 if net == "GND" else -3.81
        self.items.append(
            f'\t(symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid(ref)}")\n'
            f'\t\t(property "Reference" "{ref}" (at {x:.2f} {y + off:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            f'\t\t(property "Value" "{net}" (at {x:.2f} {y + off * 0.85:.2f} 0) (effects (font (size 1.27 1.27))))\n'
            f'\t\t(pin "1" (uuid "{uid(ref + "p")}"))\n'
            f'\t\t(instances (project "{PROJECT}" (path "/{ROOT}" (reference "{ref}") (unit 1))))\n\t)')

    def pflag(self, x, y, rot=0):
        """PWR_FLAG direkt an einer Leitung: sagt dem ERC, dass das Netz gespeist ist."""
        self.npwr += 1
        ref = f"#FLG{self.npwr:03d}"
        self.lib("power:PWR_FLAG")
        self.items.append(
            f'\t(symbol (lib_id "power:PWR_FLAG") (at {x:.2f} {y:.2f} {rot}) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid(ref)}")\n'
            f'\t\t(property "Reference" "{ref}" (at {x:.2f} {y - 1.9:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            f'\t\t(property "Value" "PWR_FLAG" (at {x:.2f} {y - 3.81:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            f'\t\t(pin "1" (uuid "{uid(ref + "p")}"))\n'
            f'\t\t(instances (project "{PROJECT}" (path "/{ROOT}" (reference "{ref}") (unit 1))))\n\t)')

    def flag(self, net, x, y):
        """PWR_FLAG mit Versorgungssymbol: sagt dem ERC, dass das Netz gespeist ist."""
        self.npwr += 1
        ref = f"#FLG{self.npwr:03d}"
        self.lib("power:PWR_FLAG")
        self.items.append(
            f'\t(symbol (lib_id "power:PWR_FLAG") (at {x:.2f} {y:.2f} 0) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid "{uid(ref)}")\n'
            f'\t\t(property "Reference" "{ref}" (at {x:.2f} {y - 1.9:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
            f'\t\t(property "Value" "PWR_FLAG" (at {x:.2f} {y - 3.81:.2f} 0) (effects (font (size 1.27 1.27))))\n'
            f'\t\t(pin "1" (uuid "{uid(ref + "p")}"))\n'
            f'\t\t(instances (project "{PROJECT}" (path "/{ROOT}" (reference "{ref}") (unit 1))))\n\t)')
        self.wire((x, y), (x + 7.62, y))
        self.power(net, x + 7.62, y)

    def netname(self, net, x, y, vertical=False):
        """Netzname direkt an der Leitung."""
        self.used_nets.add(net)
        ang = 90 if vertical else 0
        if GLOBAL_NAMES:
            self.items.append(
                f'\t(global_label "{net}" (shape passive) (at {x:.2f} {y:.2f} {ang}) (fields_autoplaced yes) '
                f'(effects (font (size 1.0 1.0)) (justify left)) (uuid "{uid(f"n{net}{x},{y}")}")\n'
                f'\t\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x:.2f} {y:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n\t)')
        else:
            self.items.append(
                f'\t(label "{net}" (at {x:.2f} {y:.2f} {ang}) (fields_autoplaced yes) '
                f'(effects (font (size 1.27 1.27)) (justify left bottom)) (uuid "{uid(f"n{net}{x},{y}")}"))')

    def label(self, net, x, y, ox, oy):
        ang = {(1, 0): 0, (-1, 0): 180, (0, -1): 90, (0, 1): 270}[(ox, oy)]
        just = "left" if ang in (0, 90) else "right"
        self.used_nets.add(net)
        self.items.append(
            f'\t(global_label "{net}" (shape passive) (at {x:.2f} {y:.2f} {ang}) (fields_autoplaced yes) '
            f'(effects (font (size 1.27 1.27)) (justify {just})) (uuid "{uid(f"l{net}{x},{y}")}")\n'
            f'\t\t(property "Intersheetrefs" "${{INTERSHEET_REFS}}" (at {x:.2f} {y:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n\t)')

    def net_of(self, ref, pin):
        return self.placed[ref][2].get(pin, "")

    def pt(self, ref, pin):
        return self.placed[ref][1][pin]

    def tie(self, ref, pin, length=2.54, net=None, as_label=False):
        """Stummel nach außen, daran Versorgungssymbol oder Netzname."""
        x, y, ox, oy = self.pt(ref, pin)
        net = net or self.net_of(ref, pin)
        if not net:
            return
        ex, ey = x + ox * length, y + oy * length
        self.wire((x, y), (ex, ey))
        if net in POWER and not as_label:
            want = 1 if net == "GND" else -1   # GND nach unten, Versorgung nach oben
            if oy != want:
                ex2, ey2 = ex, ey + want * 2.54
                self.wire((ex, ey), (ex2, ey2))
                ex, ey = ex2, ey2
            self.power(net, ex, ey)
        else:
            self.label(net, ex, ey, ox, oy)

    def noconnect(self, x, y):
        self.items.append(f'\t(no_connect (at {x:.2f} {y:.2f}) (uuid "{uid(f"nc{x},{y}")}"))')

    def text(self, s, x, y, size=2.0, bold=True):
        self.items.append(f'\t(text "{s}" (exclude_from_sim no) (at {x:.2f} {y:.2f} 0) '
                          f'(effects (font (size {size} {size}){" (bold yes)" if bold else ""}) (justify left)) '
                          f'(uuid "{uid("t" + s + str(x))}"))')

    def frame(self, x1, y1, x2, y2, title):
        self.items.append(f'\t(rectangle (start {x1:.2f} {y1:.2f}) (end {x2:.2f} {y2:.2f}) '
                          f'(stroke (width 0) (type dash)) (fill (type none)) (uuid "{uid(f"r{x1},{y1}")}"))')
        self.text(title, x1 + 2.54, y1 + 3.81)


def build(sh):
    """Ein zusammenhängendes Schaltbild: ESP32-H2-MINI-1 in der Mitte, alles per Leitung angeschlossen.

    Links oben die Versorgung (J1 -> XC6206 -> 3,3-V-Schiene ans Modul), links das Ventil,
    EN-Beschaltung und USB, rechts der Fächer GPIO -> 100k -> Elektrode.
    Quarz und Antenne sitzen im Modul.
    """
    W, J, N = sh.wire, sh.junction, sh.netname

    def gnd(ref, pin, length=2.54):
        sh.tie(ref, pin, length)

    # ------------------------------------------------ Modul
    X0, Y0 = 200.66, 119.38
    u = sh.place("U1", "zig:ESP32-H2-MINI-1", X0, Y0, 0, ref_off=(-17.78, -26.67), val_off=(7.62, -26.67))
    xl, xr = u["3"][0], u["9"][0]
    assert (xl, xr) == (180.34, 220.98), (xl, xr)
    gnd("U1", "1")
    sh.noconnect(*u["15"][:2])

    # ------------------------------------------------ Versorgung 5 V -> 3,3 V
    sh.place("J1", "Connector:Conn_01x03_Pin", 30.48, 40.64, 270, ref_off=(-6.35, -3.81), val_off=(1.27, -3.81))
    j1 = {p: sh.pt("J1", p)[:2] for p in "123"}
    assert j1 == {"1": (33.02, 45.72), "2": (30.48, 45.72), "3": (27.94, 45.72)}, j1
    W(j1["1"], (33.02, 48.26), (33.02, 50.8))
    sh.power("GND", 33.02, 50.8)
    sh.pflag(33.02, 48.26, 270)
    YB = 60.96                      # Höhe der 5-V- und 3,3-V-Leitung
    sh.place("C3", "Device:C", 48.26, YB + 3.81, 0)
    gnd("C3", "2")
    u2 = sh.place("U2", "Regulator_Linear:XC6206PxxxMR", 71.12, YB, 0, ref_off=(-5.08, -6.35), val_off=(-5.08, -4.32))
    gnd("U2", "1")
    W(j1["2"], (30.48, YB), (38.1, YB), (43.18, YB), (48.26, YB), u2["3"][:2])
    sh.pflag(43.18, YB)
    J(43.18, YB)
    J(30.48, YB); J(38.1, YB); J(48.26, YB)
    sh.power("+5V", 38.1, YB)
    # Freilaufdiode und Ventil-Anschluss
    sh.place("D1", "Device:D_Schottky", 30.48, 76.2, 270, ref_off=(-6.35, -1.27), val_off=(-6.35, 1.27))
    d1 = {p: sh.pt("D1", p)[:2] for p in "12"}
    assert d1 == {"1": (30.48, 72.39), "2": (30.48, 80.01)}, d1
    W((30.48, YB), d1["1"])
    YD = 83.82
    sh.place("Q1", "Transistor_FET:Q_NMOS_GSD", 48.26, 88.9, 0, ref_off=(5.08, -1.27), val_off=(5.08, 1.27))
    q = {p: sh.pt("Q1", p)[:2] for p in "123"}
    assert q == {"1": (43.18, 88.9), "2": (50.8, 93.98), "3": (50.8, 83.82)}, q
    W(j1["3"], (27.94, YD), (30.48, YD), q["3"])
    W(d1["2"], (30.48, YD))
    J(30.48, YD)
    N("DRAIN", 35.56, YD)
    sh.power("GND", *q["2"])
    # Gate: vom GPIO0 über das Modul nach links, unter Q1 durch, R23 nach GND
    YG = 88.9
    W(u["9"][:2], (223.52, u["9"][1]), (223.52, YG), (60.96, YG), (60.96, 101.6), (38.1, 101.6), (38.1, YG), q["1"])
    sh.place("R23", "Device:R", 38.1, 105.41, 0, ref_off=(-6.35, -1.27), val_off=(-6.35, 1.27))
    J(38.1, 101.6)
    gnd("R23", "2")
    N("GATE", 101.6, YG)
    # 3,3 V: U2 -> C4 -> Modul (Pin 3)
    XR = 172.72                     # Versorgungsschiene am Modul
    taps = [u2["2"][:2], (96.52, YB), (101.6, YB), (127.0, YB), (XR, YB)]

    W(*taps)
    for t in taps[1:-1]:
        J(*t)
    sh.power("+3V3", 96.52, YB)
    sh.place("C4", "Device:C", 101.6, YB + 3.81, 0)
    gnd("C4", "2")
    W((XR, YB), (XR, u["3"][1]), u["3"][:2])

    # ------------------------------------------------ EN: R19 nach 3,3 V, C6 nach GND (Einschaltverzögerung)
    ye = u["8"][1]
    XEN = 160.02
    W(u["8"][:2], (XEN, ye))
    J(XEN, ye)
    sh.place("R19", "Device:R", XEN, ye - 3.81, 0, ref_off=(-6.35, -1.27), val_off=(-6.35, 1.27))
    sh.power("+3V3", *sh.pt("R19", "1")[:2])
    sh.place("C6", "Device:C", XEN, ye + 3.81, 0, ref_off=(-6.35, -1.27), val_off=(-6.35, 1.27))
    gnd("C6", "2")
    N("EN", 165.1, ye)

    # ------------------------------------------------ USB (Lötpads J3 auf der Unterseite)
    YU = 193.04
    sh.place("J3", "Connector:Conn_01x02_Pin", 157.48, YU, 0, ref_off=(-2.54, -2.54), val_off=(-7.62, 5.08))
    W(u["27"][:2], (175.26, u["27"][1]), (175.26, YU), sh.pt("J3", "1")[:2])
    W(u["26"][:2], (177.8, u["26"][1]), (177.8, YU + 2.54), sh.pt("J3", "2")[:2])
    N("USB_P", 163.83, YU)
    N("USB_N", 163.83, YU + 2.54)

    # ------------------------------------------------ Fächer GPIO -> 100k -> Elektrode
    order = ["10", "5", "6", "18", "19", "22", "23", "20", "21", "16", "12", "13", "24", "30", "31", "25"]
    nets = {p: sh.net_of("U1", p) for p in order}
    rref = {}
    for k in range(1, 17):
        rref[sh.parts[f"R{k}"][2]["1"]] = (f"R{k}", f"E{k}", sh.parts[f"R{k}"][2]["2"])
    gap_before = {"IO8": 12.7, "IO9": 12.7, "IO10": 15.24}
    t, y = {}, 71.12
    for i, p in enumerate(order):
        if i:
            y += gap_before.get(nets[p], 5.08)
        t[p] = round(y, 2)
    up = [p for p in order if t[p] < u[p][1] - 0.01]
    down = [p for p in order if t[p] > u[p][1] + 0.01][::-1]
    tx = {}
    for k, p in enumerate(up):
        tx[p] = 226.06 + 2.54 * k
    for k, p in enumerate(down):
        tx[p] = 226.06 + 2.54 * k
    XJ, XRES, XE = 248.92, 260.35, 271.78
    for p in order:
        net = nets[p]
        r, e, enet = rref[net]
        x, yp = u[p][:2]
        if p in tx:
            W((x, yp), (tx[p], yp), (tx[p], t[p]), (XRES - 3.81, t[p]))
        else:
            W((x, yp), (XRES - 3.81, t[p]))
        sh.place(r, "Device:R", XRES, t[p], 90, ref_off=(-1.9, -1.9), val_off=(0, 0), hide_value=True)
        assert sh.pt(r, "1")[:2] == (XRES - 3.81, t[p]), (r, sh.pt(r, "1"))
        W(sh.pt(r, "2")[:2], (XE, t[p]))
        sh.place(e, "Connector:TestPoint", XE, t[p], 0, ref_off=(1.27, -2.54), val_off=(1.27, -3.3), hide_value=True)
        N(net, XJ + 0.6, t[p])
        N(enet, XRES + 4.6, t[p])
        if net in ("IO8", "IO9"):
            pr = "R17" if net == "IO8" else "R18"
            sh.place(pr, "Device:R", XJ, t[p] - 3.81, 180, ref_off=(-5.08, -0.6), val_off=(-5.08, 1.3))
            assert sh.pt(pr, "1")[:2] == (XJ, t[p]), sh.pt(pr, "1")
            J(XJ, t[p])
            sh.power("+3V3", *sh.pt(pr, "2")[:2])
        if net == "IO9":
            # JP1 PAIR: zwei Lötpads auf der Unterseite (zig:pair_pads)
            sh.place("JP1", "Connector_Generic:Conn_01x02", XJ + 5.08, t[p] + 10.16, 0, ref_off=(-5.08, -2.54), val_off=(-5.08, 3.81))
            pio = "1" if sh.net_of("JP1", "1") == "IO9" else "2"
            pgnd = "2" if pio == "1" else "1"
            pi, pg = sh.pt("JP1", pio)[:2], sh.pt("JP1", pgnd)[:2]
            W((XJ, t[p]), (XJ, pi[1]), pi)
            sh.power("GND", *pg)

    # ------------------------------------------------ Hinweise, Mechanik
    notes = [
        "J1: 5 V an Pin 5V, Magnetventil zwischen 5V und VLV. Q1 schaltet nach GND, D1 = Freilaufdiode, R23 hält das Gate aus.",
        "U2 XC6206: 200 mA; das Modul zieht beim Senden bis 140 mA. C4 10 uF am Modul. EN: R19 10k / C6 1 uF (Einschaltverzögerung).",
        "U1 ESP32-H2-MINI-1-H4S: 32-MHz-Quarz und PCB-Antenne im Modul. VBAT bleibt offen (im Modul an 3V3). Antennenende an der Platinenkante, darunter kein Kupfer.",
        "R1-R16 je 100k in Serie zu den Elektroden. E1 an der Linie MAX, E16 an der Spitze. GPIO-Zuordnung der v2 siehe Netznamen.",
        "J3 (D+, D-) und JP1 PAIR sind Lötpads auf der Unterseite unter dem Modul. JP1 kurzschließen = GPIO9 auf GND: 6 s = neu pairen, 12 s = Werksreset, beim Einschalten = Download.",
    ]
    for i, n in enumerate(notes):
        sh.text(n, 20.32, 215.9 + i * 3.81, 1.27, False)
    sh.place("MH1", "Mechanical:MountingHole", 25.4, 205.74, 0, ref_off=(3.81, -1.27), val_off=(3.81, 1.27))


def main():
    sh = Sheet(pcb_parts())
    build(sh)
    libs = "\n".join(sh.libs[k] for k in sorted(sh.libs))
    text = (
        "(kicad_sch\n\t(version 20250114)\n\t(generator \"gen_sch\")\n\t(generator_version \"10.0\")\n"
        f'\t(uuid "{ROOT}")\n\t(paper "A3")\n'
        "\t(title_block\n\t\t(title \"SumpSense-16z-v2\")\n\t\t(rev \"2\")\n"
        "\t\t(comment 1 \"ESP32-H2-MINI-1, 16 Stufen, Ventil. Netze aus der Platine\")\n\t)\n"
        f"\t(lib_symbols\n{libs}\n\t)\n"
        + "\n".join(sh.items)
        + f'\n\t(sheet_instances\n\t\t(path "/" (page "1"))\n\t)\n\t(embedded_fonts no)\n)\n'
    )
    open(OUT, "w", encoding="utf-8").write(text)
    # Projektbibliothek "zig" mit dem ESP32-H2-Symbol, damit KiCad es findet
    sym = h2_symbol().replace('(symbol "zig:ESP32-H2"', '(symbol "ESP32-H2"').replace("\n\t\t", "\n\t")
    open(os.path.join(HERE, "zig.kicad_sym"), "w", encoding="utf-8").write(
        '(kicad_symbol_lib\n\t(version 20241209)\n\t(generator "gen_sch")\n\t(generator_version "10.0")\n'
        + sym.lstrip() + "\n)\n")
    open(os.path.join(HERE, "sym-lib-table"), "w", encoding="utf-8").write(
        '(sym_lib_table\n\t(version 7)\n\t(lib (name "zig") (type "KiCad") '
        '(uri "${KIPRJMOD}/zig.kicad_sym") (options "") (descr "Eigene Symbole"))\n)\n')
    print(OUT, "Symbole", len(sh.placed), "Netze mit Namen", len(sh.used_nets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
