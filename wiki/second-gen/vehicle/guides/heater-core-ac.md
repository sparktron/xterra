# Heater and A/C problems: no heat, blower speeds, door actuators

[Guides](index.md) · [Reference home](../index.md) · Related: [Coolant drain and refill](coolant-flush.md), [Air and cabin filters](air-fuel-filters.md), [Fuse and relay maps](fuse-relay-map.md)

## Quick diagnosis

| Symptom | Most likely cause | Go to | Source |
|---|---|---|---|
| Heater blows cold **at idle** but warms up with engine speed; gurgling behind the dash | Low coolant: air circulating through the heater core | [No heat at idle](#no-heat-at-idle-check-the-coolant-the-right-way) | [S1][S2] |
| Blower works only on the highest speed | Blower resistor card (older trucks) | [Blower speeds](#blower-speeds-the-resistor-card-or-variable-blower-control) | [S3] |
| Blower works on some speeds only, or the A/C light or compressor only works on speed 1 | Blower resistor card | [Blower speeds](#blower-speeds-the-resistor-card-or-variable-blower-control) | [S4] |
| Blower dead or surging on all speeds | Blower relay, motor, or resistor card. Several owners' fixes turned out to be the card | [Blower speeds](#blower-speeds-the-resistor-card-or-variable-blower-control) | [S4] |
| Air comes out the wrong vents, or won't switch modes | Mode door motor (actuator) | [Door actuators](#door-actuators-mode-air-mix-intake) | [S5] |
| Temperature won't follow the dial, or switches from cold to hot on its own | The air mix door motor, which sets temperature, or the control panel. The owner's thread didn't record a fix [Unverified] | [Door actuators](#door-actuators-mode-air-mix-intake) | [S5][S6] |
| Recirc button does nothing | Intake door motor | [Door actuators](#door-actuators-mode-air-mix-intake) | [S5] |
| Milky or oily coolant, or pink ATF | Possibly a failed radiator cooler | [SMOD](smod.md) | |

## No heat at idle: check the coolant the right way

The coolant reservoir is part of the pressurized circuit, not an overflow bottle. Coolant flows through it whenever the engine runs, and it separates out air. **If its level drops below the outlet, air is pulled into the system and goes through the heater core**, giving cold air at idle and gurgling [S1][S2].

- **Check the level with the engine cold and running.** With the engine off the level reads about 1.5 in higher, which can hide a low system [S1][S2].
- In one owner's tests, removing 2 qt from a full system was enough to make the heater go cold at idle and the coolant run hotter under light load. Topping up fixed it [S2].
- **To top up:** with the engine cool, fill the radiator to the bottom of its neck and the reservoir to MAX. Drive at least 5 miles warm, then let it cool. Start it, top the reservoir to MAX while running, and repeat the next day until it stays at MAX [S2].
- The system purges air on its own once it has enough coolant. If you keep adding coolant, find the leak: one owner's radiator tank gasket leaked only when cold. Or replace the reservoir cap, which should hold about 16 psi [S2]. Nissan's specification is 98-118 kPa (14-17 psi) [S7].

For a full drain and refill, see [Coolant drain and refill](coolant-flush.md).

## Blower speeds: the resistor card (or variable blower control)

On older trucks the blower speeds come from a **resistor card** on the heater housing under the glove box. It's a common failure [S3][S4].

1. Find the card under the glove box, on a white connector [S3].
2. Remove its two screws; one owner found they take a 7/32 in hex [S3][S4].
3. Unplug the card, fit the new one, and refit the screws. It takes about 5 minutes [S3].

The new card gets just as hot as the old one; that's normal for a resistor [S4]. A dealer quoted one owner 2 hours' labor [S3], and a shop wanted to replace another owner's $220 fan switch. The card fixed both [S3][S4].

The 2013 manual's manual A/C uses a **variable blower control** on the heater unit instead. It controls the blower motor stepless from the front air control [S5].

The blower motor relay is in the under-hood fuse and relay box, next to the washer bottle [S4].

## Door actuators: mode, air mix, intake

Three small motors move the doors in the heater box [S5]:

- **Mode door motor:** vent, bi-level, foot, foot/defrost and defrost [S5].
- **Air mix door motor:** temperature. It has a position sensor (PBR) that the controls read [S5].
- **Intake door motor:** fresh air or recirculation [S5].

Each motor reverses direction according to which of its two wires gets power. The control panel reads the door position back from the motor's built-in position resistor [S5]. One owner replaced his 2015's mode door actuator in about 20 minutes; the door had jammed, with no clicking beforehand [S8].

## A/C system specifications

| Item | Value | Source |
|---|---|---|
| Refrigerant | HFC-134a (R-134a), 0.70 ± 0.05 kg (1.54 ± 0.11 lb) | [S9] |
| Compressor oil | Nissan A/C System Oil Type R (DH-PR), 180 mL (6.1 fl oz) | [S9] |
| Specification label | under the hood; check it for your truck | [S9] |

Refrigerant work needs recovery equipment; leave it to a shop unless you have it [Unverified].

## Sources

Web sources accessed 2026-10-20.

- [S1] jeff_redx, "How-to: No Heat, Check This First", thenewx.org, 2010-11-03. Read from the Internet Archive copy. https://www.thenewx.org/threads/how-to-no-heat-check-this-first.35941/
- [S2] jeff_redx, "How-to: Correct (and More) Problems if Heater Blows Cold at Idle or No Heat", thenewx.org, 2011-01-24. Read from the Internet Archive copy. https://www.thenewx.org/threads/how-to-correct-and-more-problems-if-heater-blows-cold-at-idle-or-no-heat.38466/
- [S3] Bbear94, "How-to: Replace Blower Resistor Card", thenewx.org, 2011-09-12. Read from the Internet Archive copy. https://www.thenewx.org/threads/how-to-replace-blower-resistor-card.45923/
- [S4] jedge99, Squished, Talldiver14 and HunterME, "How-to: Air Conditioner Fix - PBR", thenewx.org, 2013-12-22 to 2015-05-31. https://www.thenewx.org/threads/how-to-air-conditioner-fix-pbr.30207/
- [S5] Nissan, 2013 Xterra Service Manual, section HAC (Heater and Air Conditioning Control System), manual A/C: mode door motor (pp. HAC-19 to HAC-22), air mix door motor (pp. HAC-23 to HAC-26), intake door motor (pp. HAC-27 to HAC-28), blower motor and variable blower control (pp. HAC-29 to HAC-33). Revision January 2013. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FHAC.pdf
- [S6] Magger, "Climate Control Issue - A/C Spontaneously Changes to Heat", xterranation.org, 2019-05-01. https://www.xterranation.org/index.php?threads/climate-control-issue-a-c-spontaneously-changes-to-heat.8750/
- [S7] Nissan, 2013 Xterra Service Manual, section CO, service data (p. CO-30). https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FCO.pdf
- [S8] Tenlayer, "Mode Door Actuator Replacement on a 2015 Xterra", thenewx.org, 2021-09-03. https://www.thenewx.org/threads/mode-door-actuator-replacement-on-a-2015-xterra.282964/
- [S9] Nissan, 2013 Xterra Service Manual, section MA, "Fluids and Lubricants" (p. MA-13). https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FMA.pdf
