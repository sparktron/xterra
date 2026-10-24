# Electrical faults: warning lights, grounds, flicker and battery drain

[Guides](index.md) · [Reference home](../index.md) · Related: [Fuse boxes, relays and the IPDM](fuse-relay-map.md), [Throttle body cleaning and idle relearn](throttle-body-idle-relearn.md), [Sensors](sensors.md)

## ABS, BRAKE, VDC OFF and SLIP lights all on together

This combination usually means the ABS/VDC unit has logged a fault and shut VDC down. Read the codes with a scan tool that reads ABS (C-codes) [S1][S2].

- **C1163 "ST ANGL SEN SAFE":** the steering angle sensor is in safe mode. The fix is Nissan's **steering angle sensor neutral position adjustment** [S1].
- **When Nissan requires that adjustment:** after battery disconnection, a wheel alignment, removing or replacing steering or suspension parts, removing or replacing the steering angle sensor, or replacing the ABS unit. It isn't needed after tire changes or rotations [S1].
- **Nissan says it can't be done without its CONSULT tool.** Center the wheels, then run "ST ANGLE SENSOR ADJUSTMENT" under WORK SUPPORT [S1]. Some aftermarket scan tools offer the same function [Unverified].
- One owner's lights came on after hitting a curb, with C1163 and C1140 (ABS actuator relay) [S2]. An alignment alone didn't clear them [S2]. That fits the manual, since the reset has to follow the alignment [S1].
- **C1140 "ACTUATOR RLY":** the ABS actuator relay or its circuit [S1].
- After clearing the codes, the VDC OFF lamp should go out. If it doesn't, Nissan runs the ABS unit's self-diagnosis [S1].

## Flickering dash lights, the radio resetting, random lights

When the dash lights flicker, the radio resets, warning lights blink and the idle dips, suspect the **battery cables and grounds first** [S3]:

1. Check the battery terminals for corrosion and tightness. Nissan's terminal nut torque is 3.4 N·m (30 in-lb) [S3][S4].
2. The main body and chassis grounds both run from the short negative battery cable, about 18 in long. Check both ends of that cable [S3].
3. Check the fusible links on the positive cable [S3].
4. On early trucks, the IPDM is a known stalling cause; see the IPDM relay recall in [Fuse boxes, relays and the IPDM](fuse-relay-map.md#the-ipdm-ecm-relay-recall-2005-2006) [S3][S5].
5. The FSM's PG section maps every ground point. Use it to work outward from the battery [S3][S4].

In one owner's case, a new battery didn't fix it, and the 4WD, ABS, parking brake, VDC and SLIP lights flashed while the speedometer dropped out. That pointed to a loose connection behind the dash [S3].

## Parasitic battery drain

The general method, not from a Nissan source:

1. Fully charge the battery, close the doors, latch the hood switch closed, and let the truck sit until the modules go to sleep (often 10-30 minutes). [Unverified]
2. Put an ammeter in series with the negative cable. A healthy truck asleep draws only tens of milliamps. [Unverified]
3. Pull fuses one at a time (or measure the voltage drop across each fuse) until the current drops. That fuse's circuit holds the drain; see [Fuse boxes, relays and the IPDM](fuse-relay-map.md). [Unverified]
4. Common add-on culprits are accessories wired to constant power. Wire them through a relay switched by ignition or by a fused accessory feed; see [Lighting, aux fuse blocks and dual batteries](lighting-aux-power.md). [Unverified]

## After any battery disconnect

Nissan says some electronic systems need resetting after the negative terminal has been disconnected [S4]. Expect to:

- reset the **steering angle sensor** (above) if VDC or SLIP lights come on [S1];
- possibly do the **throttle and idle relearn** if the idle is unstable; see [Throttle body cleaning and idle relearn](throttle-body-idle-relearn.md) [S6];
- reset the clock, radio presets and power windows [S7].

## Sources

Web sources accessed 2026-10-20.

- [S1] Nissan, 2013 Xterra Service Manual, section BRC (Brake Control System): adjustment of steering angle sensor neutral position (pp. BRC-12 to BRC-13), C1140 actuator relay (pp. BRC-58 to BRC-59), C1163 steering angle sensor safe mode (p. BRC-69). Revision January 2013. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FBRC.pdf
- [S2] TeXas-Hooligan, "ABS BRAKE VDC SLIP Lights all 'ON'", thenewx.org, 2019-04-16. https://www.thenewx.org/threads/abs-brake-vdc-slip-lights-all-on.283005/
- [S3] impeerical, Lowcountry idn and others, "Electrical Issues, ECM or Bad Ground?", thenewx.org, 2022-02-11. https://www.thenewx.org/threads/electrical-issues-ecm-or-bad-ground.284270/
- [S4] Nissan, 2013 Xterra Service Manual, section PG (Power Supply, Ground and Circuit Elements): ground circuit (pp. PG-27 to PG-36), battery removal and installation (p. PG-72). https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FPG.pdf
- [S5] NHTSA recalls API, Nissan Xterra model year 2005 (campaign 10V517000, IPDM ECM relay). https://api.nhtsa.gov/recalls/recallsByVehicle?make=nissan&model=xterra&modelYear=2005
- [S6] Nissan, 2007 Xterra Service Manual, section EC (Engine Control System), basic service procedures (pp. EC-78 to EC-80). https://www.nicoclub.com/service-manual?fsm=Xterra%2F2007%2Fec.pdf
- [S7] Nissan North America, Technical Service Bulletin NTB09-128 (service procedure steps 9-10: radio presets and initializing power windows and clock after a battery disconnect), 2009-11-16. https://australiancar.reviews/_pdfs/Nissan_Navara_D40_NTB09-128.pdf
