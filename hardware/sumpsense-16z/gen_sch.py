"""Lesbarer KiCad-Schaltplan zur handgepflegten Platine.

  python3 gen_sch.py

Netze und Pads kommen aus sumpsense-16z.kicad_pcb, die Symbole aus der
KiCad-10-Bibliothek (nur der ESP32-H2 ist ein eigenes Symbol, die Bibliothek hat
keins). Die Anordnung ist nach Funktionsblöcken: Versorgung, Ventil, Mikrocontroller,
Quarz, Antenne, USB/Flash, Stufen. Verbindungen über Versorgungssymbole und
beschriftete Netze, kurze Strecken als Leitung.
"""

import os
import re
import uuid

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "sumpsense-16z.kicad_sch")
PCB = os.path.join(HERE, "sumpsense-16z.kicad_pcb")
PROJECT = "sumpsense-16z"
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


# ---------------------------------------------------------------- eigenes ESP32-H2-Symbol
H2_LEFT = [  # (pin, name) von oben nach unten, None = Lücke
    ("1", "VDD3P3"), ("2", "VDD3P3"), ("27", "VDD3P3"), ("30", "VDD3P3"), ("31", "VDD3P3"),
    ("9", "VDDPST1"), ("20", "VDDPST2"), ("18", "VBAT"), ("19", "VDDA_PMU"), ("17", "CHIP_EN"),
    None, ("29", "XTAL_P"), ("28", "XTAL_N"), None, ("32", "ANT"), None,
    ("26", "GPIO27/USB_D+"), ("25", "GPIO26/USB_D-"),
]
H2_RIGHT = [
    ("3", "GPIO0"), ("4", "GPIO1"), ("5", "GPIO2/MTMS"), ("6", "GPIO3/MTDO"), ("7", "GPIO4/MTCK"),
    ("8", "GPIO5/MTDI"), None, ("10", "GPIO8"), ("11", "GPIO9"), ("12", "GPIO10"), ("13", "GPIO11"),
    ("14", "GPIO12"), ("15", "GPIO13/XTAL_32K_P"), ("16", "GPIO14/XTAL_32K_N"), None,
    ("21", "GPIO22"), ("22", "GPIO23/U0RXD"), ("23", "GPIO24/U0TXD"), ("24", "GPIO25"),
]


def h2_symbol():
    rows = max(len(H2_LEFT), len(H2_RIGHT))
    top = (rows - 1) / 2 * 2.54
    w = 17.78
    pins = []

    def pin(num, name, x, y, ang, etype):
        pins.append(
            f'\t\t\t(pin {etype} line (at {x:.2f} {y:.2f} {ang}) (length 2.54)\n'
            f'\t\t\t\t(name "{name}" (effects (font (size 1.27 1.27))))\n'
            f'\t\t\t\t(number "{num}" (effects (font (size 1.27 1.27))))\n\t\t\t)')

    for i, e in enumerate(H2_LEFT):
        if e:
            num, name = e
            et = "power_in" if name.startswith(("VDD", "VBAT")) else ("input" if name == "CHIP_EN" else "bidirectional")
            pin(num, name, -w - 2.54, top - i * 2.54, 0, et)
    for i, e in enumerate(H2_RIGHT):
        if e:
            pin(e[0], e[1], w + 2.54, top - i * 2.54, 180, "bidirectional")
    pin("33", "GND", 0, -top - 5.08, 90, "power_in")
    body = (f'\t\t\t(rectangle (start {-w:.2f} {top + 2.54:.2f}) (end {w:.2f} {-top - 2.54:.2f})\n'
            '\t\t\t\t(stroke (width 0.254) (type default)) (fill (type background)))')
    return (
        '\t\t(symbol "zig:ESP32-H2"\n'
        '\t\t\t(pin_names (offset 1.016)) (exclude_from_sim no) (in_bom yes) (on_board yes)\n'
        f'\t\t\t(property "Reference" "U" (at {-w:.2f} {top + 3.81:.2f} 0) (effects (font (size 1.27 1.27)) (justify left)))\n'
        f'\t\t\t(property "Value" "ESP32-H2" (at {w:.2f} {top + 3.81:.2f} 0) (effects (font (size 1.27 1.27)) (justify right)))\n'
        '\t\t\t(property "Footprint" "" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        '\t\t\t(property "Datasheet" "https://www.espressif.com/sites/default/files/documentation/esp32-h2_datasheet_en.pdf" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        '\t\t\t(property "Description" "ESP32-H2, QFN32 4x4, Pinbelegung nach Datenblatt v1.3" (at 0 0 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        '\t\t\t(symbol "ESP32-H2_0_1"\n' + body + '\n\t\t\t)\n'
        '\t\t\t(symbol "ESP32-H2_1_1"\n' + "\n".join(pins) + '\n\t\t\t)\n'
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
            t = h2_symbol() if lib_id == "zig:ESP32-H2" else "\t\t" + flat_symbol(lib_id).replace("\n\t", "\n\t\t")
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

    def text(self, s, x, y, size=2.0, bold=True):
        self.items.append(f'\t(text "{s}" (exclude_from_sim no) (at {x:.2f} {y:.2f} 0) '
                          f'(effects (font (size {size} {size}){" (bold yes)" if bold else ""}) (justify left)) '
                          f'(uuid "{uid("t" + s + str(x))}"))')

    def frame(self, x1, y1, x2, y2, title):
        self.items.append(f'\t(rectangle (start {x1:.2f} {y1:.2f}) (end {x2:.2f} {y2:.2f}) '
                          f'(stroke (width 0) (type dash)) (fill (type none)) (uuid "{uid(f"r{x1},{y1}")}"))')
        self.text(title, x1 + 2.54, y1 + 3.81)


def build(sh):
    """Ein zusammenhängendes Schaltbild: ESP32-H2 in der Mitte, alles per Leitung angeschlossen.

    Links oben die Versorgung (J1 -> XC6206 -> 3,3-V-Schiene an den Chip), links das Ventil,
    links unten Quarz, Antenne und USB, rechts der Fächer GPIO -> 100k -> Elektrode.
    Masse über GND-Symbole, Netznamen stehen als Beschriftung an den Leitungen.
    """
    W, J, N = sh.wire, sh.junction, sh.netname

    def gnd(ref, pin, length=2.54):
        sh.tie(ref, pin, length)

    # ------------------------------------------------ Mikrocontroller
    X0, Y0 = 200.66, 119.38
    u = sh.place("U1", "zig:ESP32-H2", X0, Y0, 0, ref_off=(-17.78, -26.67), val_off=(7.62, -26.67))
    xl, xr = u["1"][0], u["3"][0]
    assert (xl, xr) == (180.34, 220.98), (xl, xr)
    gnd("U1", "33")

    # ------------------------------------------------ Versorgung 5 V -> 3,3 V
    sh.place("J1", "Connector:Conn_01x03_Pin", 30.48, 40.64, 270, ref_off=(-6.35, -3.81), val_off=(1.27, -3.81),
             )
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
    # Gate: vom GPIO0 über den Chip nach links, unter Q1 durch, R23 nach GND
    YG = 88.9
    W(u["3"][:2], (223.52, u["3"][1]), (223.52, YG), (60.96, YG), (60.96, 101.6), (38.1, 101.6), (38.1, YG), q["1"])
    sh.place("R23", "Device:R", 38.1, 105.41, 0, ref_off=(-6.35, -1.27), val_off=(-6.35, 1.27))
    J(38.1, 101.6)
    gnd("R23", "2")
    N("GATE", 101.6, YG)
    # 3,3 V
    sh.place("R22", "Device:R", 88.9, YB, 90, ref_off=(-3.81, -2.54), val_off=(0.64, -2.54))
    r22 = {p: sh.pt("R22", p)[:2] for p in "12"}
    assert r22 == {"1": (85.09, YB), "2": (92.71, YB)}, r22
    W(u2["2"][:2], r22["1"])
    N("VOUT", 79.38, YB)
    XR = 172.72                     # Versorgungsschiene am Chip
    taps = [r22["2"], (96.52, YB), (101.6, YB), (127.0, YB), (149.86, YB), (160.02, YB), (XR, YB)]
    sh.pflag(127.0, YB)
    W(*taps)
    for t in taps[1:-1]:
        J(*t)
    sh.power("+3V3", 96.52, YB)
    for ref, x in (("C4", 101.6), ("C5", 149.86), ("C6", 160.02)):
        sh.place(ref, "Device:C", x, YB + 3.81, 0)
        gnd(ref, "2")
    rail = ["1", "2", "27", "30", "31", "9", "20", "18", "19", "17"]
    ys = [u[p][1] for p in rail]
    W((XR, YB), *[(XR, y) for y in ys])
    for p in rail:
        W(u[p][:2], (XR, u[p][1]))
    for y in ys[:-1]:
        J(XR, y)

    # ------------------------------------------------ Quarz
    yxp, yxn = u["29"][1], u["28"][1]
    sh.place("R20", "Device:R", 165.1, yxp, 90, ref_off=(-3.81, -2.54), val_off=(0.64, -2.54))
    r20 = {p: sh.pt("R20", p)[:2] for p in "12"}
    W(u["29"][:2], r20["2"])
    N("XTAL_PIN", 169.55, yxp)
    YQ = 142.24
    sh.place("Y1", "Device:Crystal_GND24", 152.4, YQ, 0, ref_off=(-5.08, -4.45), val_off=(-0.64, -4.45))
    y1 = {p: sh.pt("Y1", p)[:2] for p in "123"}
    assert y1 == {"1": (148.59, YQ), "3": (156.21, YQ), "2": (152.4, 147.32)}, y1
    gnd("Y1", "2")
    W(r20["1"], (142.24, yxp), (142.24, YQ), y1["1"])
    W(u["28"][:2], (162.56, yxn), (162.56, YQ), y1["3"])
    N("XTAL_P", 146.05, yxp)
    N("XTAL_N", 166.37, yxn)
    for ref, x in (("C1", 142.24), ("C2", 162.56)):
        sh.place(ref, "Device:C", x, YQ + 3.81, 180, ref_off=(6.35, -1.27), val_off=(7.62, 1.27))
        J(x, YQ)
        gnd(ref, "1")

    # ------------------------------------------------ Antenne
    ya = u["32"][1]
    YA = 182.88
    W(u["32"][:2], (172.72, ya), (172.72, YA), (163.83, YA))
    sh.place("R21", "Device:R", 160.02, YA, 90, ref_off=(-3.81, -2.54), val_off=(0.64, -2.54))
    sh.place("A1", "Device:Antenna_Shield", 149.86, 165.1, 0, ref_off=(-8.89, -2.54), val_off=(-8.89, 0))
    a1 = {p: sh.pt("A1", p)[:2] for p in "12"}
    W((156.21, YA), (149.86, YA), a1["1"])
    gnd("A1", "2")
    N("ANT_PIN", 172.72, 160.0, vertical=True)
    N("RF", 149.86, 172.72, vertical=True)

    # ------------------------------------------------ USB
    YU = 193.04
    sh.place("J3", "Connector:Conn_01x02_Pin", 157.48, YU, 0, ref_off=(-2.54, -2.54), val_off=(-7.62, 5.08))
    W(u["26"][:2], (175.26, u["26"][1]), (175.26, YU), sh.pt("J3", "1")[:2])
    W(u["25"][:2], (177.8, u["25"][1]), (177.8, YU + 2.54), sh.pt("J3", "2")[:2])
    N("USB_P", 163.83, YU)
    N("USB_N", 163.83, YU + 2.54)

    # ------------------------------------------------ Fächer GPIO -> 100k -> Elektrode
    order = ["4", "5", "6", "7", "8", "10", "11", "12", "13", "14", "15", "16", "21", "22", "23", "24"]
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
            # SW1: Taster nach GND (Pairing im Betrieb, BOOT beim Einschalten)
            sh.place("SW1", "Switch:SW_Push", XJ + 5.08, t[p] + 10.16, 90, ref_off=(2.54, -1.27), val_off=(2.54, 1.27))
            a, c = sorted((sh.pt("SW1", k_)[:2] for k_ in "12"), key=lambda q: q[1])
            W((XJ, t[p]), (XJ, a[1] - 2.54), (a[0], a[1] - 2.54), a)
            sh.power("GND", *c)

    # ------------------------------------------------ Hinweise, Mechanik
    notes = [
        "J1: 5 V an Pin 5V, Magnetventil zwischen 5V und VLV. Q1 schaltet nach GND, D1 = Freilaufdiode, R23 hält das Gate aus.",
        "U2 XC6206: 200 mA; der H2 zieht beim Senden (+20 dBm) bis 140 mA. R22 = 0-Ohm-Brücke. CHIP_EN direkt an 3,3 V.",
        "Quarz 32 MHz: R20 = 0 Ohm (statt 24 nH), C1/C2 = 12 pF C0G. Antenne A1 = TI DN007 (Net-Tie RF/GND), R21 = 0 Ohm.",
        "R1-R16 je 100k in Serie zu den Elektroden. E1 an der Linie MAX, E16 an der Spitze.",
        "SW1: kurz = Zigbee-Pairing, 10 s = Werksreset. Beim Einschalten gedrückt: GPIO9 = 0, GPIO8 = 1 (R17) -> Download-Modus.",
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
        "\t(title_block\n\t\t(title \"SumpSense-16z\")\n\t\t(rev \"2\")\n"
        "\t\t(comment 1 \"ESP32-H2, 16 Stufen, Ventil. Netze aus der Platine\")\n\t)\n"
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
