"""Zigbee-Wasserstand, 14 mm breit, 16 Stufen.

Zweite Platine. Die I2C-Platine unter wasserstand-14mm bleibt unberührt.
Quelle für Bauteile, Netze und Lage. Platine: python3 gen_pcb.py

Koordinaten: x = 0 am trockenen Ende (Antenne), wächst zur nassen Spitze.
y = 0 .. BOARD_W. Bauteile auf der Oberseite.

Antenne: TI DN007 / SWRU120D, Inverted-F, 25,58 × 7,5 mm.
Polygon aus dem KiCad-Modul PCB_IF_ANT_2.4G (tommag/kicad-lib), das die
DN007-Maße abbildet. Auf dieser Breite liegt die Speiseleitung neben der
7,5-mm-Antenne; die Espressif-Freihaltezone von 15 mm passt nicht.

Chip: ESP32-H2, QFN32 4×4 mm, 0,4 mm Raster. Padlagen aus dem
Espressif-Footprint QFN32_0P4_4_E2P8 (Pin 1 oben an der linken Flanke,
gegen den Uhrzeigersinn). Drehung so, dass ANT (Pin 32) zur Antenne zeigt.
"""

from dataclasses import dataclass, field

BOARD_W = 14.0
THICKNESS = 1.6
TUBE_ID = 14.5

N = 16
PITCH = 5.0
ELEC_ALONG = 3.4
ELEC_Y0 = 1.05
ELEC_Y1 = 13.55

CLEARANCE = 0.15
TRACE = 0.20
VIA_SIZE = 0.45
VIA_DRILL = 0.20

# TI-IFA, lokaler Ursprung = untere linke Ecke des Strahlers (y = Leiterplattenkante).
ANT_X0 = 0.50
ANT_Y0 = 0.30
# Speisepad im DN007-Modul, lokal.
FEED_LOCAL = (10.87, 7.08)
# Offenes Ende und Oberkante des Kupfers, lokal.
ANT_L = 25.58
ANT_H = 7.48

# Unterseite ohne Kupfer: Strahler und das offene Ende.
# y bis 8,15 lässt darüber die HF-Leitung (Mitte 9,4) auf Masse.
KEEPOUT = (
    (0.0, 0.0, ANT_X0 + ANT_L + 1.2, 8.15),
)

# 50-Ω-Mikrostreifen auf 1,6 mm wäre ~2,9 mm und passt neben der Antenne nicht.
# 2,2 mm liegt über der Masse ab y = 8,15, Abstand zur Antenne bleibt > 0,2 mm.
RF_W = 2.20
RF_Y = 9.40

CX = 33.0
CY = 10.8

MOUNT_X = 70.0
MOUNT_Y = 7.0
MOUNT_DRILL = 2.7
MOUNT_PAD = 3.2

RES_X = 78.0
ELEC0_X = 94.0
HOLE = 1.40
HOLE_DRILL = 1.0

# Sieben Bahnen unter dem Clip-Loch, neun darüber.
# Loch y=7 blockiert etwa 5,3..8,7. Flash-Leiste sitzt dazwischen, bei y=4,9.
LOW_LANES = tuple(1.35 + i * 0.42 for i in range(7))      # 1,35 .. 3,87
HIGH_LANES = tuple(9.45 + i * 0.36 for i in range(9))     # 9,45 .. 12,33


def board_length() -> float:
    return ELEC0_X + (N - 1) * PITCH + ELEC_ALONG / 2 + 2.0


def elec_x(i: int) -> float:
    return ELEC0_X + i * PITCH


def feed_xy() -> tuple[float, float]:
    return (ANT_X0 + FEED_LOCAL[0], ANT_Y0 + FEED_LOCAL[1])


def antenna_poly() -> list[tuple[float, float]]:
    """DN007-Umriss, in Platinenkoordinaten. Quelle: SWRU120D via PCB_IF_ANT_2.4G."""
    local = [
        (10.64, 4.82), (10.64, 7.48), (11.10, 7.48), (11.10, 4.62),
        (10.19, 3.72), (10.19, 3.01), (9.18, 3.01), (9.18, 1.21),
        (25.58, 1.21), (25.58, 0.00), (0.00, 0.00), (0.00, 6.17),
        (6.83, 6.17), (6.83, 7.22), (8.18, 7.22), (8.18, 6.23),
        (8.98, 6.23), (8.98, 7.22), (10.19, 7.22), (10.19, 4.88),
        (2.19, 4.88), (2.19, 2.22), (7.98, 2.22), (7.98, 3.01),
        (6.98, 3.01), (6.98, 4.22), (10.05, 4.22), (10.64, 4.82),
    ]
    return [(ANT_X0 + x, ANT_Y0 + y) for x, y in local]


# Pinmitte im Footprint: x nach rechts, y nach oben, Pin 1 oben links.
# (lx, ly, sx, sy), sx/sy = Padkanten in lokal x/y.
_Y8 = (1.40, 1.00, 0.60, 0.20, -0.20, -0.60, -1.00, -1.40)
_X8 = (-1.40, -1.00, -0.60, -0.20, 0.20, 0.60, 1.00, 1.40)
PIN_LOCAL = {}
for pin, ly in zip(range(1, 9), _Y8):
    PIN_LOCAL[pin] = (-1.975, ly, 0.55, 0.20)
for pin, lx in zip(range(9, 17), _X8):
    PIN_LOCAL[pin] = (lx, -1.975, 0.20, 0.55)
for pin, ly in zip(range(17, 25), (-1.40, -1.00, -0.60, -0.20, 0.20, 0.60, 1.00, 1.40)):
    PIN_LOCAL[pin] = (1.975, ly, 0.55, 0.20)
for pin, lx in zip(range(25, 33), (1.40, 1.00, 0.60, 0.20, -0.20, -0.60, -1.00, -1.40)):
    PIN_LOCAL[pin] = (lx, 1.975, 0.20, 0.55)

# Netz je Pin. Leere GPIO-Namen werden beim Zuordnen der Stufen gesetzt.
PIN_NET = {
    1: "VCC3", 2: "VCC3",
    3: "IO0", 4: "IO1", 5: "IO2", 6: "IO3", 7: "IO4", 8: "IO5",
    9: "VCC3",
    10: "IO8", 11: "IO9", 12: "IO10", 13: "IO11", 14: "IO12", 15: "IO13", 16: "IO14",
    17: "VCC3",   # CHIP_EN direkt an 3,3 V
    18: "VCC3", 19: "VCC3", 20: "VCC3",
    21: "GATE",
    22: "IO23", 23: "IO24", 24: "IO25",
    25: "USB_N", 26: "USB_P",
    27: "VCC3",
    28: "XTAL_N", 29: "XTAL_PIN",
    30: "VCC3", 31: "VCC3",
    32: "ANT_PIN",
}

# Stufe 1 = kleinste Bahn-y. Reihenfolge so, dass die Flucht sich nicht kreuzt.
LANE_GPIO = (
    "IO0", "IO1", "IO2", "IO3", "IO4", "IO5", "IO8",
    "IO9", "IO10", "IO11", "IO12", "IO13", "IO14",
    "IO25", "IO24", "IO23",
)
LANES = LOW_LANES + HIGH_LANES


def lane_y(i: int) -> float:
    return LANES[i]


def chip_pad(pin: int) -> tuple[float, float, float, float]:
    """(x, y, Breite in x, Höhe in y) des Pads auf der Platine."""
    lx, ly, sx, sy = PIN_LOCAL[pin]
    # Drehung: lokal +y (ANT-Kante) zeigt nach Platinen -x.
    # (lx, ly) -> (CX - ly, CY + lx). Kanten: sx liegt auf lokal x = Platinen-y.
    return (CX - ly, CY + lx, sy, sx)


def in_keepout(x: float, y: float) -> bool:
    for x0, y0, x1, y1 in KEEPOUT:
        if x0 <= x <= x1 and y0 <= y <= y1:
            return True
    return False


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


def _r(ref, value, x, y, n1, n2, along="x") -> Part:
    if along == "x":
        pads = [
            Pad("1", -0.46, 0.0, 0.50, 0.50, n1),
            Pad("2", 0.46, 0.0, 0.50, 0.50, n2),
        ]
    else:
        pads = [
            Pad("1", 0.0, -0.46, 0.50, 0.50, n1),
            Pad("2", 0.0, 0.46, 0.50, 0.50, n2),
        ]
    return Part(ref, value, "r0402", x, y, pads)


def _c(ref, value, x, y, n1, n2, kind="c0402") -> Part:
    span, pw, ph = (0.46, 0.50, 0.50) if kind == "c0402" else (0.95, 1.00, 1.30)
    return Part(ref, value, kind, x, y, [
        Pad("1", -span, 0.0, pw, ph, n1),
        Pad("2", span, 0.0, pw, ph, n2),
    ])


def _mcu() -> Part:
    pads = []
    for pin, net in PIN_NET.items():
        # Pad relativ zur Chipmitte, vor der Drehung, dann gedreht ablegen.
        lx, ly, sx, sy = PIN_LOCAL[pin]
        # Welt minus Chipmitte, mit derselben Drehung wie chip_pad.
        rx, ry, bw, bh = chip_pad(pin)
        pads.append(Pad(str(pin), rx - CX, ry - CY, bw, bh, net))
    pads.append(Pad("33", 0.0, 0.0, 2.60, 2.60, "GND"))
    return Part("U1", "ESP32-H2", "qfn32", CX, CY, pads)


def _sot223() -> Part:
    """AMS1117-3.3. Leads nach -x, Tab nach +x. Pin 1 GND, 2 VOUT, 3 VIN, Tab VOUT."""
    return Part("U2", "AMS1117-3.3", "sot223", 52.0, 7.4, [
        Pad("1", -1.70, -2.30, 2.00, 1.05, "GND"),
        Pad("2", -1.70, 0.00, 2.00, 1.05, "VOUT"),
        Pad("3", -1.70, 2.30, 2.00, 1.05, "V5"),
        Pad("4", 1.85, 0.00, 2.20, 3.40, "VOUT"),
    ])


def _sot23() -> Part:
    """AO3400A: 1 Gate, 2 Source, 3 Drain."""
    return Part("Q1", "AO3400A", "sot23", 58.8, 6.4, [
        Pad("1", -0.95, -0.95, 0.90, 0.60, "GATE"),
        Pad("2", -0.95, 0.95, 0.90, 0.60, "GND"),
        Pad("3", 0.95, 0.00, 0.90, 0.70, "DRAIN"),
    ])


def _sod123() -> Part:
    """Kathode (Pin 2, Strich) an +5 V, Anode an Drain."""
    return Part("D1", "SS14", "sod123", 62.4, 6.4, [
        Pad("1", -1.40, 0.0, 0.80, 0.70, "DRAIN"),
        Pad("2", 1.40, 0.0, 0.80, 0.70, "V5"),
    ])


def _crystal() -> Part:
    """3225-4. Pads 1 und 3 = Quarz, 2 und 4 = GND (KiCad-Standard)."""
    return Part("Y1", "32MHz", "xtal3225", 43.2, 6.90, [
        Pad("1", -1.10, -0.70, 1.00, 0.85, "XTAL_P"),
        Pad("2", 1.10, -0.70, 1.00, 0.85, "GND"),
        Pad("3", 1.10, 0.70, 1.00, 0.85, "XTAL_N"),
        Pad("4", -1.10, 0.70, 1.00, 0.85, "GND"),
    ])


def _holes_y(ref, x, y0, nets, labels) -> Part:
    """Löcher in y, Raster 2,54."""
    pads = [
        Pad(str(i + 1), 0.0, i * 2.54, HOLE, HOLE, net)
        for i, net in enumerate(nets)
    ]
    part = Part(ref, " ".join(labels), "hdr", x, y0, pads)
    part.labels = labels  # type: ignore[attr-defined]
    return part


def _holes_x(ref, x0, y, nets, labels) -> Part:
    """Löcher in x, Raster 2,54. Flash-Leiste."""
    pads = [
        Pad(str(i + 1), i * 2.54, 0.0, HOLE, HOLE, net)
        for i, net in enumerate(nets)
    ]
    part = Part(ref, " ".join(labels), "hdr", x0, y, pads)
    part.labels = labels  # type: ignore[attr-defined]
    # Beschriftung zur Kante, nicht in den Quarz hinein.
    part.label_dy = -1.05  # type: ignore[attr-defined]
    return part


def _mount() -> Part:
    return Part("MH1", "M2.5", "mount", MOUNT_X, MOUNT_Y, [
        Pad("", 0.0, 0.0, MOUNT_PAD, MOUNT_PAD, "", paste=False, mask=True),
    ])


def _electrode(i: int) -> Part:
    net = f"E{i + 1:02d}"
    h = ELEC_Y1 - ELEC_Y0
    return Part(f"E{i + 1}", net, "electrode", elec_x(i), (ELEC_Y0 + ELEC_Y1) / 2, [
        Pad("1", 0.0, 0.0, ELEC_ALONG, h, net, mask=False, paste=False),
    ])


def build_parts() -> list[Part]:
    parts = [
        _mcu(),
        _crystal(),
        _sot223(),
        _sot23(),
        _sod123(),
        _c("C1", "12pF", 40.6, 6.20, "GND", "XTAL_P"),
        _c("C2", "12pF", 46.5, 7.60, "XTAL_N", "GND"),
        # Pad 1 zeigt zur Antenne, Pad 2 zum Chip.
        _r("R20", "0R", 29.85, 10.60, "XTAL_P", "XTAL_PIN"),
        _r("R21", "0R", 28.15, RF_Y, "RF", "ANT_PIN"),
        _c("C3", "10uF", 46.6, 11.05, "V5", "GND", kind="c0805"),
        _c("C4", "10uF", 57.2, 10.5, "VCC3", "GND", kind="c0805"),
        _r("R22", "1R", 54.2, 10.2, "VOUT", "VCC3"),
        _c("C5", "100nF", 37.1, 7.55, "VCC3", "GND"),
        _c("C6", "100nF", 38.9, 7.55, "VCC3", "GND"),
        _r("R17", "10k", 36.2, 8.70, "IO8", "VCC3", along="y"),
        _r("R18", "10k", 37.6, 8.70, "IO9", "VCC3", along="y"),
        _r("R23", "100k", 58.8, 4.15, "GATE", "GND", along="y"),
        _holes_y("J1", 56.2, 4.90, ("V5", "GND"), ("5V", "GND")),
        _holes_y("J2", 66.2, 4.90, ("V5", "DRAIN"), ("5V", "VLV")),
        _holes_x("J3", 38.6, 4.85, ("GND", "USB_P", "USB_N", "IO9"),
                 ("GND", "D+", "D-", "BOOT")),
    ]

    for i, gpio in enumerate(LANE_GPIO):
        y = lane_y(i)
        x = RES_X + (0.0 if i % 2 == 0 else 1.80)
        parts.append(_r(f"R{i + 1}", "100k", x, y, gpio, f"E{i + 1:02d}"))
    for i in range(N):
        parts.append(_electrode(i))
    parts.append(_mount())
    parts.append(Part(
        "A1", "DN007", "feed", *feed_xy(),
        [Pad("1", 0.0, 0.0, 0.50, 0.90, "RF")],
    ))
    return parts


PARTS = build_parts()


def elec_nets() -> set[str]:
    return {f"E{i:02d}" for i in range(1, N + 1)}
