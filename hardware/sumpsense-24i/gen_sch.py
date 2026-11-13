"""Lesbarer KiCad-Schaltplan zur Platine SumpSense-24i (ein zusammenhängendes Schaltbild).

  python3 gen_sch.py

Bauteile, Pads und Netze kommen aus sumpsense-24i.kicad_pcb; die Platine ist die Quelle.
Symbole aus der KiCad-10-Bibliothek. Zeichenwerkzeuge (Symbol-Einbettung, Leitungen, Netznamen)
teilt sich das Skript mit ../sumpsense-16z/gen_sch.py.
"""

import importlib.util
import os

HERE = os.path.dirname(os.path.abspath(__file__))
_spec = importlib.util.spec_from_file_location("sch16", os.path.join(HERE, "..", "sumpsense-16z", "gen_sch.py"))
base = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(base)

base.PCB = os.path.join(HERE, "sumpsense-24i.kicad_pcb")
base.OUT = os.path.join(HERE, "sumpsense-24i.kicad_sch")
base.PROJECT = "sumpsense-24i"
base.NS = "sumpsense-24i-sch"
base.ROOT = base.uid("root")
base.POWER["VCC"] = "power:VCC"
G = 2.54


def _power_rot(self, net, x, y, rot):
    """Versorgungssymbol gedreht (90 = nach links für VCC, nach rechts für GND)."""
    self.npwr += 1
    lib_id = base.POWER[net]
    self.lib(lib_id)
    ref = f"#PWR{self.npwr:03d}"
    dx = {90: -3.3, 270: 3.3, 180: 0}[rot] * (1 if net != "GND" else -1)
    dy = 3.3 if rot == 180 else 0
    self.items.append(
        f'\t(symbol (lib_id "{lib_id}") (at {x:.2f} {y:.2f} {rot}) (unit 1) (exclude_from_sim no) (in_bom yes) (on_board yes) (dnp no) (uuid "{base.uid(ref)}")\n'
        f'\t\t(property "Reference" "{ref}" (at {x:.2f} {y:.2f} 0) (effects (font (size 1.27 1.27)) (hide yes)))\n'
        f'\t\t(property "Value" "{net}" (at {x + dx:.2f} {y + dy:.2f} 0) (effects (font (size 1.27 1.27))))\n'
        f'\t\t(pin "1" (uuid "{base.uid(ref + "p")}"))\n'
        f'\t\t(instances (project "{base.PROJECT}" (path "/{base.ROOT}" (reference "{ref}") (unit 1))))\n\t)')


base.Sheet.power_rot = _power_rot
MCU = "MCU_Microchip_ATtiny:ATtiny1616-M"


def fan(sh, pins, x_turn0, x_res, y_first, step, side):
    """Pins einer Chipseite auf Widerstände im Raster 'step' auffächern (ohne Kreuzung).

    pins: [(ref, pin)] von oben nach unten. side +1 = rechts, -1 = links.
    """
    targets = [round(y_first + i * step, 2) for i in range(len(pins))]
    rows = [(sh.pt(r, p)[:2], t, r, p) for (r, p), t in zip(pins, targets)]
    down = [r for r in rows if r[1] > r[0][1] + 0.01][::-1]
    up = [r for r in rows if r[1] < r[0][1] - 0.01]
    tx = {}
    for k, r in enumerate(down):
        tx[id(r)] = x_turn0 + side * G * k
    for k, r in enumerate(up):
        tx[id(r)] = x_turn0 + side * G * k
    out = []
    for r in rows:
        (x, y), t, ref, pin = r
        if id(r) in tx:
            sh.wire((x, y), (tx[id(r)], y), (tx[id(r)], t), (x_res, t))
        else:
            sh.wire((x, y), (x_res, t))
        out.append((t, sh.net_of(ref, pin)))
    return out


def stage(sh, rref, eref, net, enet, x_res, y, side):
    """Serienwiderstand + Elektrode an Zeile y, Leitung kommt von der Chipseite."""
    rot = 90 if side > 0 else 270
    sh.place(rref, "Device:R", x_res + side * 3.81, y, rot, ref_off=(side * 3.81 - 1.9, -1.9),
             val_off=(0, 0), fa=90, hide_value=True)
    p_chip = sh.pt(rref, "1")[:2]
    p_el = sh.pt(rref, "2")[:2]
    assert abs(p_chip[0] - x_res) < 0.02, (rref, p_chip, x_res)
    xe = p_el[0] + side * 10.16
    sh.wire(p_el, (xe, y))
    sh.place(eref, "Connector:TestPoint", xe, y, 0, ref_off=(1.27, -2.54), val_off=(1.27, -3.3), hide_value=True)
    sh.items[-1] = sh.items[-1].replace("(in_bom yes)", "(in_bom no)")
    sh.netname(net, x_res - side * 6.0 if side > 0 else x_res + 0.6, y)
    sh.netname(enet, p_el[0] + side * 1.3 if side > 0 else xe + 0.6, y)


def build(sh):
    W, J, N = sh.wire, sh.junction, sh.netname
    parts = sh.parts
    sense = {}                      # Chip-Netz -> (Rref, Eref, E-Netz)
    for ref, (lib, val, nets) in parts.items():
        if ref.startswith("R") and nets.get("2", "").startswith("E"):
            n = int(nets["2"][1:])
            sense[nets["1"]] = (ref, f"E{n}", nets["2"])

    # ------------------------------------------------ Chips
    X, Y1, Y2 = 119.38, 88.9, 195.58
    u1 = sh.place("U1", MCU, X, Y1, 0, ref_off=(-12.7, -24.13), val_off=(2.54, -24.13))
    u2 = sh.place("U2", MCU, X, Y2, 0, ref_off=(-12.7, -24.13), val_off=(2.54, -24.13))
    for u in ("U1", "U2"):
        x, y, _, _ = sh.pt(u, "3")
        W((x, y), (x, y + 2.54), (x, y + 5.08))
        sh.power("GND", x, y + 5.08)
        if u == "U1":
            J(x, y + 2.54)
            sh.pflag(x, y + 2.54, 270)
        x, y, _, _ = sh.pt(u, "4")
        W((x, y), (x, y - 2.54))
        sh.power("VCC", x, y - 2.54)
    # PA3: U1 an GND, U2 an VCC (Adressmerkmal)
    for u, n in (("U1", "GND"), ("U2", "VCC")):
        x, y, _, _ = sh.pt(u, "2")
        W((x, y), (x + 5.08, y))
        if n == "GND":
            W((x + 5.08, y), (x + 5.08, y + 2.54))
            sh.power("GND", x + 5.08, y + 2.54)
        else:
            sh.power_rot("VCC", x + 5.08, y, 270)
    # Abblockung je Chip links oben
    for u, c1, c2 in (("U1", "C1", "C2"), ("U2", "C3", "C4")):
        x, y, _, _ = sh.pt(u, "4")
        top = y - 2.54
        for c, dx in ((c1, -20.32), (c2, -30.48)):
            vpin = "2" if parts[c][2].get("2") == "VCC" else "1"
            sh.place(c, "Device:C", x + dx, top + 6.35, 180 if vpin == "2" else 0, ref_off=(2.54, -1.27), val_off=(2.54, 1.27))
            W(sh.pt(c, vpin)[:2], (x + dx, top))
            sh.tie(c, "1" if vpin == "2" else "2")
        W((x - 30.48, top), (x - 20.32, top), (x, top))
        J(x - 20.32, top)
        J(x, top)
        if u == "U1":
            sh.pflag(x - 30.48, top)

    # ------------------------------------------------ Fächer rechts (PA4..PB5) und links (PC0..PC3)
    XR, XL = 172.72, 66.04
    for u, y_first in (("U1", Y1 - 7.62), ("U2", Y2 - 7.62)):
        right = [p for p in ("5", "6", "7", "8", "14", "13", "10", "9") if sh.net_of(u, p) in sense]
        rows = fan(sh, [(u, p) for p in right], X + 17.78, XR, y_first, 5.08, +1)
        for y, net in rows:
            r, e, en = sense[net]
            stage(sh, r, e, net, en, XR, y, +1)
        left = [p for p in ("15", "16", "17", "18") if sh.net_of(u, p) in sense]
        if left:
            rows = fan(sh, [(u, p) for p in left], X - 17.78, XL, (Y1 if u == "U1" else Y2) + 5.08, 5.08, -1)
            for y, net in rows:
                r, e, en = sense[net]
                stage(sh, r, e, net, en, XL, y, -1)

    # ------------------------------------------------ Bus rechts: SCL, SDA, UPDI zu den sechs Löchern J1 (oben)
    XS, XD, XU1, XU2 = 309.88, 314.96, 320.04, 335.28
    xb = {("U1", "1"): XS, ("U1", "20"): XD, ("U1", "19"): XU1,
          ("U2", "1"): XS, ("U2", "20"): XD, ("U2", "19"): XU2}
    for (u, pin), x_end in xb.items():
        x, y, _, _ = sh.pt(u, pin)
        W((x, y), (x_end, y))
    px = sh.pt("U1", "1")[0]
    ys = [sh.pt(u, "1")[1] for u in ("U1", "U2")]
    yd = [sh.pt(u, "20")[1] for u in ("U1", "U2")]
    yu = [sh.pt(u, "19")[1] for u in ("U1", "U2")]
    for i in range(2):
        N("SCL", px + 2.54, ys[i]); N("SDA", px + 2.54, yd[i])
        N(f"UPDI_U{i + 1}", px + 2.54, yu[i])
    # J1: sechs Löcher, Pins zeigen nach links: 1 GND, 2 VCC, 3 SCL, 4 SDA, 5 UPDI U1, 6 UPDI U2
    sh.place("J1", "Connector_Generic:Conn_01x06", 350.52, 45.72, 0, ref_off=(-1.27, -8.89), val_off=(-1.27, 11.43), fa=0)
    j = {p: sh.pt("J1", p)[:2] for p in "123456"}
    x, y = j["1"]
    W((x, y), (x - 2.54, y))
    sh.power_rot("GND", x - 2.54, y, 270)
    x, y = j["2"]
    W((x, y), (x - 7.62, y))
    sh.power_rot("VCC", x - 7.62, y, 90)
    W(j["3"], (XS, j["3"][1]), (XS, ys[0]), (XS, ys[1]))
    W(j["4"], (XD, j["4"][1]), (XD, yd[0]), (XD, yd[1]))
    W(j["5"], (XU1, j["5"][1]), (XU1, yu[0]))
    W(j["6"], (XU2, j["6"][1]), (XU2, yu[1]))
    J(XS, ys[0]); J(XD, yd[0])
    # Pull-ups zwischen den Chips: R1 links an SCL, R2 rechts an SDA
    ym = 129.54
    sh.place("R1", "Device:R", XS - 7.62, ym, 270, ref_off=(-1.27, -2.54), val_off=(-1.27, 3.81), fa=90)
    W(sh.pt("R1", "1")[:2], (XS, ym)); J(XS, ym)
    sh.power_rot("VCC", *sh.pt("R1", "2")[:2], 90)
    sh.place("R2", "Device:R", XD + 7.62, ym + 5.08, 90, ref_off=(-1.27, -2.54), val_off=(-1.27, 3.81), fa=90)
    W(sh.pt("R2", "1")[:2], (XD, ym + 5.08)); J(XD, ym + 5.08)
    sh.power_rot("VCC", *sh.pt("R2", "2")[:2], 270)

    # ------------------------------------------------ freie Pins
    for u in ("U1", "U2"):
        lib_id, conn, nets = sh.placed[u]
        for pin, (x, y, _, _) in conn.items():
            if not nets.get(pin) or nets.get(pin, '').startswith('unconnected-'):
                sh.items.append(f'	(no_connect (at {x:.2f} {y:.2f}) (uuid "{base.uid("nc" + u + pin)}"))')

    # ------------------------------------------------ Mechanik, Hinweise
    sh.place("MH1", "Mechanical:MountingHole", 30.48, 254.0, 0, ref_off=(3.81, -1.27), val_off=(3.81, 1.27))
    notes = [
        "Zwei ATtiny1616 am I2C (Löcher J1). U1: 12 Stufen, Adresse 0x78 (PA3 an GND); U2: 12 Stufen, 0x77 (PA3 an VCC).",
        "R3-R26 je 1k in Serie zu den Elektroden. E1 direkt hinter der Linie MAX, E24 an der Spitze.",
        "J1 = sechs Löcher im 2,54-mm-Raster: GND, VCC, SCL, SDA quer, UPDI U1 und U2 an der Seite (Flashen je Chip einzeln).",
    ]
    for i, n in enumerate(notes):
        sh.text(n, 20.32, 266.7 + i * 3.81, 1.27, False)


def main():
    sh = base.Sheet(base.pcb_parts())
    build(sh)
    # Netz-Flags für den ERC an den Steckerleitungen
    libs = "\n".join(sh.libs[k] for k in sorted(sh.libs))
    text = (
        "(kicad_sch\n\t(version 20250114)\n\t(generator \"gen_sch\")\n\t(generator_version \"10.0\")\n"
        f'\t(uuid "{base.ROOT}")\n\t(paper "A3")\n'
        "\t(title_block\n\t\t(title \"SumpSense-24i\")\n\t\t(rev \"2\")\n"
        "\t\t(comment 1 \"2x ATtiny1616, 24 Stufen, I2C. Netze aus der Platine\")\n\t)\n"
        f"\t(lib_symbols\n{libs}\n\t)\n"
        + "\n".join(sh.items)
        + '\n\t(sheet_instances\n\t\t(path "/" (page "1"))\n\t)\n\t(embedded_fonts no)\n)\n'
    )
    open(base.OUT, "w", encoding="utf-8").write(text)
    print(base.OUT, "Symbole", len(sh.placed), "Netze mit Namen", len(sh.used_nets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
