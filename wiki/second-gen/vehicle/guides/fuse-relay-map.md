# Fuse boxes, relays and the IPDM

[Guides](index.md) · [Reference home](../index.md) · Related: [Electrical faults and battery drain](electrical-faults.md), [Lighting and aux power](lighting-aux-power.md), [Recalls](../recalls.md)

## Where the boxes are (2013 manual)

| Box | Location | Source |
|---|---|---|
| **IPDM E/R** (intelligent power distribution module, engine room): fuses and relays it controls electronically | Engine bay, driver's side, next to the ECM and the battery | [S1] |
| **Fuse and fusible link box**: the battery's main fusible links | Engine bay, next to the IPDM | [S1] |
| **Fuse and relay box** | Engine bay, beside the IPDM, near the washer bottle | [S1][S4] |
| **Fuse block (J/B)**: interior fuses | Passenger side of the instrument panel, at the lower right, behind the trim | [S1] |
| Body control module (BCM) | Behind the center of the dash | [S1] |
| Differential lock control unit (E-Lock trucks) | Left of the steering column | [S1] |
| Transfer control unit (4WD) | Low on the driver's side of the dash | [S1] |

**The circuit map for each box is printed on the inside of its lid** [Unverified]. Nissan's manual maps every fuse to its circuits in the power supply routing wiring diagrams (pp. PG-8 to PG-26) [S1].

## IPDM E/R fuses (2013 manual)

The IPDM's fuses carry an "F" number on the module, which differs from the fuse number in the wiring diagrams [S1].

| On the IPDM | Wiring diagram no. | Rating | Source |
|---|---|---|---|
| F1 | 46 | 15 A | [S1] |
| F2 | 47 | 15 A | [S1] |
| F3 | 45 | 10 A | [S1] |
| F4 | 32 | 10 A | [S1] |
| F5 | 43 | 15 A | [S1] |
| F6 | 39 | 30 A | [S1] |
| F7 | 37 | 10 A | [S1] |
| F8 | 42 | 10 A | [S1] |
| F9 | 36 | 10 A | [S1] |
| F10 | 56 | 20 A | [S1] |
| F11 | 40 | 15 A | [S1] |
| F12 | 41 | 15 A | [S1] |
| F13 | 35 | 10 A | [S1] |
| F14 | 34 | 10 A | [S1] |
| F15 | 55 | 15 A | [S1] |
| F16 | 38 | 10 A | [S1] |
| F17 | 54 | 15 A | [S1] |
| F18 | 48 | 15 A | [S1] |
| F19 | 49 | 10 A | [S1] |
| F20 | 50 | 10 A | [S1] |
| F21 | 51 | 10 A | [S1] |
| F22 | (empty) | | [S1] |
| F23 | 52 | 20 A | [S1] |
| F24 | 53 | 20 A | [S1] |

The IPDM also holds the rear window defogger relay, the cooling fan low and high relays, and the ignition relay [S1].

**Battery-powered fuses and links, from the 2013 manual's routing diagram** [S2]:

- The fusible link box on the battery holds a 140 A main link plus 80 A, 100 A, 80 A, 80 A and 60 A links that feed the rest of the system [S2].
- **Power socket:** a 20 A fuse (no. 26) [S2].
- **Trailer tow:** among others, a 15 A fuse (no. 60) shared with the BCM, and a 30 A link (M) [S2].
- **Part-time 4WD system:** two 10 A fuses (nos. 57 and 58) [S2].

## The IPDM ECM relay recall (2005-2006)

On 2005-2006 trucks, NHTSA campaign **10V517000**: the ECM relay inside the IPDM could build up silicon oxide on its contacts and cause **stalling**, and dealers replaced the relay [S3]. It's worth checking first on an early truck that stalls [S5].

**Temporary roadside fix from an owner:** swap the ECM relay with the identical fog light relay in the IPDM, to get home. The relays have four blades and must go back facing the same way. Don't drive on it long; get the part replaced [S6].

**Replacing the whole IPDM** (one owner, 20-45 minutes) [S6]:

1. Disconnect the battery, negative first, then positive [S6].
2. Remove the IPDM's black top cover and release its two clips. Push in each connector lock with a small screwdriver and unplug all seven connectors [S6].
3. Lift the board out upside down and fit the new one [S6].
4. Reconnect the seven plugs and the battery, and test drive [S6].

## Testing a relay

Many Nissan relays are the same part. Swapping a suspect relay with an identical one that controls something else is a quick test; one owner swapped the blower motor relay this way [S4]. Swapping the ECM and fog light relays is the IPDM version of the same test [S6].

## Battery (2013 manual)

| Item | Value | Source |
|---|---|---|
| Battery | group GR35, at least 60 Ah (20 h rate), 550 cold-cranking amps at -18°C (0°F) | [S1] |
| Battery terminal nuts | 3.4 N·m (30 in-lb) | [S1] |
| Battery hold-down clamp nuts | 3.92 N·m (35 in-lb) | [S1] |

Disconnect the **negative first** and connect the **positive first**. Before disconnecting, turn the ignition off and wait at least three minutes [S1]. Some systems need resetting after the battery has been disconnected [S1].

## Sources

Web sources accessed 2026-10-20.

- [S1] Nissan, 2013 Xterra Service Manual, section PG (Power Supply, Ground and Circuit Elements): electrical units location (pp. PG-60 to PG-62), fuse block J/B, fuse and fusible link box, fuse and relay box (pp. PG-68 to PG-70), IPDM E/R terminal arrangement (p. PG-71), battery removal and service data (pp. PG-72 to PG-73), power supply routing circuit diagrams (pp. PG-8 to PG-26). Revision January 2013. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FPG.pdf
- [S2] Nissan, 2013 Xterra Service Manual, section PG, "Wiring Diagram - Battery Power Supply" (p. PG-8). https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FPG.pdf
- [S3] NHTSA recalls API, Nissan Xterra model years 2005 and 2006 (campaign 10V517000, IPDM ECM relay), as summarized on this wiki's [Recalls](../recalls.md) page. https://api.nhtsa.gov/recalls/recallsByVehicle?make=nissan&model=xterra&modelYear=2005
- [S4] jedge99, "How-to: Air Conditioner Fix - PBR", thenewx.org, 2013-12-22. https://www.thenewx.org/threads/how-to-air-conditioner-fix-pbr.30207/
- [S5] Amazingracer, "How-to: Replace Crankshaft Position Sensor", thenewx.org, 2015-01-24. https://www.thenewx.org/threads/how-to-replace-crankshaft-position-sensor.138498/
- [S6] xmedicG, "How-to: IPDM E/R Replacement (now with a temporary relay swap)", thenewx.org, 2010-06-11. Read from the Internet Archive copy. https://www.thenewx.org/threads/how-to-ipdm-er-replacement-now-with-a-temporary-relay-swap.29652/
