"""Kapazitiver Wasserstandsensor, 14 mm breit, für Rohr-Innendurchmesser 14,5 mm.

Einzige Quelle für Schaltung und Lage. Platine: python3 gen_pcb.py

Koordinaten: x = 0 am Stecker (trocken, oben), wächst zur Spitze (nass).
y = 0 .. BOARD_W quer zur Länge. Alle Bauteile auf der Oberseite.

Schaltung = Seeed Grove Water Level Sensor (10 cm), Eagle 9.2.2:
zwei ATtiny1616. Pin → Elektrode folgt der Originalplatine. Segmentabstand 5 mm.
PA3 von U1 liegt an GND, PA3 von U2 an VCC. Eine spätere Firmware kann daran
0x78 und 0x77 unterscheiden. Die Seeed-Werksfirmware liest PA3 nicht.

Querschnitt Rohr: Breite 14 mm ist eine Sehne in 14,5 mm. Bauteilseite zeigt
in den größeren Kreisabschnitt (siehe tube_clearance()).
"""

from dataclasses import dataclass, field

BOARD_W = 14.0
THICKNESS = 1.6
TUBE_ID = 14.5

N = 20
PITCH = 5.0
ELEC_ALONG = 3.4          # Elektrode in x (Original 3,0 mm bei 20 mm Breite)
ELEC_Y0 = 1.05
ELEC_Y1 = 13.55
LANE0 = 1.55              # y der untersten Sense-Bahn (E01)
LANE1 = 12.85

CLEARANCE = 0.15
TRACE = 0.20
VIA_SIZE = 0.45
VIA_DRILL = 0.20

# Elektronikblock 0,7 mm zum Stecker. Zusammen mit der wegfallenden Stirn: Länge 138 mm.
HEAD = -0.7
# Signalkontakte. Gehäuse und Öffnung liegen in -x, an der trockenen Kante.
CONN = (9.55, 7.0)
# 1×4 Durchkontaktierung unter dem Stecker, Raster 2,54 mm, Bohrung 1,0 mm.
HDR_X = 12.20
HDR_Y = 3.19              # Pin 1 = GND, dann VCC, U1, U2
U1_POS = (26.2 + HEAD, 4.85)
U2_POS = (26.2 + HEAD, 10.95)
RES_X_EVEN = 30.55 + HEAD
RES_X_ODD = 32.30 + HEAD
VIA_X = 34.20 + HEAD
ELEC0_X = 40.0 + HEAD

# Rohrclip: ein M2,5-Loch (y=7). Zweites Loch (Richtung U2) → Routing-Umbau. mount/clip.scad
MOUNT_Y = 7.0
MOUNT_X = 20.5 + HEAD
MOUNT_DRILL = 2.7
MOUNT_PAD = 3.2
# Router/Abstand: Bohrkante + Regelabstand + halbe Bahn (VCC-Stamm 0,30 mm).
MOUNT_BLOCK_R = MOUNT_DRILL / 2 + CLEARANCE + 0.30 / 2
# VCC-Querstrang zwischen den Chips, unterhalb MH1 mit Reserve.
VCC_U2_BUS_Y = MOUNT_Y + MOUNT_DRILL / 2 + 0.30 / 2 + 0.45
# Altname für Clip-Export
MOUNT_X1 = MOUNT_X


def lane_y(i: int) -> float:
    return LANE0 + i * (LANE1 - LANE0) / (N - 1)


def elec_x(i: int) -> float:
    return ELEC0_X + i * PITCH


def board_length() -> float:
    return elec_x(N - 1) + ELEC_ALONG / 2 + 2.0


def tube_clearance() -> tuple[float, float]:
    """Freie Höhe über/unter der Platinenoberfläche, Platine mittig auf der Sehne.

    Rückgabe: (große Seite, kleine Seite) in mm. Bauteile gehören auf die große Seite.
    """
    import math
    r = TUBE_ID / 2
    d = math.sqrt(r * r - (BOARD_W / 2) ** 2)
    half_t = THICKNESS / 2
    return (r + d - half_t, r - d - half_t)


# VQFN-20 3×3 mm, 0,4 mm Raster. Pin 1 = oben links der linken Flanke, gegen den Uhrzeigersinn
# (Draufsicht, +x zur Spitze, +y nach rechts). Entspricht Datasheet ATtiny1616 20-Pin VQFN.
PIN = {
    "PA2": 1, "PA3": 2, "GND": 3, "VDD": 4, "PA4": 5,
    "PA5": 6, "PA6": 7, "PA7": 8, "PB5": 9, "PB4": 10,
    "PB3": 11, "PB2": 12, "PB1": 13, "PB0": 14, "PC0": 15,
    "PC1": 16, "PC2": 17, "PC3": 18, "PA0": 19, "PA1": 20,
    "EP": 21,
}


def qfn_local(pin: int) -> tuple[float, float, float, float]:
    """(x, y, Breite, Höhe) relativ zur Chipmitte. Padmittelpunkt."""
    span = 1.45
    pw, pl = 0.22, 0.70
    xs = (-0.8, -0.4, 0.0, 0.4, 0.8)
    if 1 <= pin <= 5:
        return (xs[pin - 1], -span, pw, pl)
    if 6 <= pin <= 10:
        return (span, xs[pin - 6], pl, pw)
    if 11 <= pin <= 15:
        return (xs[4 - (pin - 11)], span, pw, pl)
    if 16 <= pin <= 20:
        return (-span, xs[4 - (pin - 16)], pl, pw)
    if pin == 21:
        return (0.0, 0.0, 1.65, 1.65)
    raise KeyError(pin)


# Elektrode 1 = am nächsten am Stecker (trocken), 20 = Spitze (zuerst nass).
# Widerstands-Refs wie auf der Seeed-Platine.
SENSORS = [
    (1, "U1", "PA4", "R5"),
    (2, "U1", "PA5", "R6"),
    (3, "U1", "PA6", "R7"),
    (4, "U1", "PA7", "R8"),
    (5, "U1", "PB5", "R12"),
    (6, "U1", "PB4", "R11"),
    (7, "U1", "PB1", "R10"),
    (8, "U1", "PB0", "R9"),
    (9, "U1", "PC0", "R16"),
    (10, "U1", "PC3", "R13"),
    (11, "U1", "PC2", "R14"),
    (12, "U1", "PC1", "R15"),
    (13, "U2", "PA4", "R23"),
    (14, "U2", "PA5", "R24"),
    (15, "U2", "PA6", "R25"),
    (16, "U2", "PA7", "R26"),
    (17, "U2", "PB5", "R30"),
    (18, "U2", "PB4", "R29"),
    (19, "U2", "PB1", "R28"),
    (20, "U2", "PB0", "R27"),
]


@dataclass
class Pad:
    name: str
    x: float
    y: float
    w: float
    h: float
    net: str
    mask: bool = True
    paste: bool = True


@dataclass
class Part:
    ref: str
    value: str
    kind: str
    x: float
    y: float
    pads: list = field(default_factory=list)


def _r(ref, value, x, y, n1, n2) -> Part:
    return Part(ref, value, "r0402", x, y, [
        Pad("1", -0.46, 0.0, 0.50, 0.50, n1),
        Pad("2", 0.46, 0.0, 0.50, 0.50, n2),
    ])


def _c(ref, value, x, y, n1, n2) -> Part:
    return Part(ref, value, "c0402", x, y, [
        Pad("1", -0.46, 0.0, 0.50, 0.50, n1),
        Pad("2", 0.46, 0.0, 0.50, 0.50, n2),
    ])


def _qfn(ref, x, y, nets: dict) -> Part:
    pads = []
    for name, num in PIN.items():
        lx, ly, w, h = qfn_local(num)
        pads.append(Pad(str(num), lx, ly, w, h, nets.get(name, "")))
    return Part(ref, "ATtiny1616", "qfn", x, y, pads)


def _grove(x, y) -> Part:
    # Ursprung = Mitte der Signalkontakte. Öffnung in -x (trockene Kante), wie HW4-SMD-2.0-90D auf der Seeed-Platine.
    spec = [
        ("1", 0.0, -3.0, 2.74, 1.01, "SCL"),
        ("2", 0.0, -1.0, 2.74, 1.01, "SDA"),
        ("3", 0.0, 1.0, 2.74, 1.01, "VCC"),
        ("4", 0.0, 3.0, 2.74, 1.01, "GND"),
        ("SS1", -7.4, -5.4, 3.0, 1.5, "GND"),
        ("SS2", -7.4, 5.4, 3.0, 1.5, "GND"),
    ]
    return Part("J1", "Grove", "grove", x, y, [Pad(*s[:5], s[5]) for s in spec])


def _mount_hole(ref: str, x: float) -> Part:
    return Part(ref, "M2.5", "mount", x, MOUNT_Y, [
        Pad("", 0.0, 0.0, MOUNT_PAD, MOUNT_PAD, "", paste=False, mask=True),
    ])


def _hdr() -> Part:
    """Vier Löcher, Raster 2,54 mm. Pin 1 GND, 2 VCC, 3 UPDI von U1, 4 UPDI von U2."""
    pitch = 2.54
    spec = [("1", "GND"), ("2", "VCC"), ("3", "UPDI_U1"), ("4", "UPDI_U2")]
    return Part("J3", "UPDI", "hdr", HDR_X, HDR_Y, [
        Pad(name, 0.0, i * pitch, 1.6, 1.6, net, paste=False)
        for i, (name, net) in enumerate(spec)
    ])


def _electrode(i: int) -> Part:
    net = f"E{i + 1:02d}"
    h = ELEC_Y1 - ELEC_Y0
    return Part(f"E{i + 1}", net, "electrode", elec_x(i), (ELEC_Y0 + ELEC_Y1) / 2, [
        Pad("1", 0.0, 0.0, ELEC_ALONG, h, net, mask=False, paste=False),
    ])


def _mcu_nets(which: str) -> dict:
    nets = {
        "GND": "GND", "EP": "GND", "VDD": "VCC",
        "PA0": "UPDI_U1" if which == "U1" else "UPDI_U2",
        "PA1": "SDA", "PA2": "SCL",
        "PA3": "GND" if which == "U1" else "VCC",
    }
    for elec, mcu, pin, _ref in SENSORS:
        if mcu == which:
            nets[pin] = f"{which}_{pin}"
    return nets


def build_parts() -> list[Part]:
    u1x, u1y = U1_POS
    u2x, u2y = U2_POS
    h = HEAD
    parts = [
        _hdr(),
        _grove(*CONN),
        _qfn("U1", u1x, u1y, _mcu_nets("U1")),
        _qfn("U2", u2x, u2y, _mcu_nets("U2")),
        # I2C-Pullups, einmal für den Bus. PA1/PA2 liegen direkt auf SDA/SCL.
        _r("R1", "4.7k", 15.6 + h, 4.6, "SCL", "VCC"),
        _r("R2", "4.7k", 15.6 + h, 6.6, "SDA", "VCC"),
        # Abblockung am Rand, unter der ersten Sense-Bahn. Nicht neben U1: dort fällt PA4.
        _c("C1", "100nF", 28.3 + h, 1.05, "GND", "VCC"),
        _c("C2", "4.7uF", 32.5 + h, 1.05, "GND", "VCC"),
        # Neben dem U2-Bus, nicht zwischen den Chips: dort ist die Flucht von U1 Pin 11–15.
        _c("C3", "100nF", 16.8 + h, 9.35, "GND", "VCC"),
        _c("C4", "4.7uF", 19.4 + h, 9.35, "GND", "VCC"),
    ]
    for elec, mcu, pin, ref in SENSORS:
        i = elec - 1
        parts.append(_r(ref, "1k", RES_X_EVEN if i % 2 == 0 else RES_X_ODD, lane_y(i),
                        f"{mcu}_{pin}", f"E{elec:02d}"))
    for i in range(N):
        parts.append(_electrode(i))
    parts.append(_mount_hole("MH1", MOUNT_X))
    return parts


PARTS = build_parts()


def elec_nets() -> set[str]:
    return {f"E{i:02d}" for i in range(1, N + 1)}
