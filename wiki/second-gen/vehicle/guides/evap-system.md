# EVAP system faults: gas cap, vent valve and canister (P0440-P0456)

[Guides](index.md) · [Reference home](../index.md) · Related: [Engine trouble codes](dtc-reference-vq40de.md), [Fuel pump and sender](fuel-pump.md)

The EVAP system stores fuel vapor from the tank in a charcoal **canister**, and the engine burns it later through the **purge solenoid** on the intake plenum. A **vent control valve** on the canister lets fresh air in, and closes so the ECM can leak-test the system [S1]. On the Xterra the canister sits under the rear of the truck behind the left (driver's) rear wheel, where road dust gets into the vent valve and canister. That's the usual cause of vent valve codes [S2][S3][S4].

## Codes

| Code | Nissan's description | Most common fix | Source |
|---|---|---|---|
| P0455 / P0456 / P0442 | EVAP gross / very small / small leak | The fuel cap, then hoses and the purge valve | [S1][S2][S5] |
| P0447 / P0448 | EVAP canister vent control valve | **Dust-clogged vent valve and canister**: clean them and add a filtered breather | [S1][S3][S4] |
| P0441, P0443-P0445 | Purge flow / purge volume control solenoid | The purge solenoid on the intake plenum | [S1][S5] |
| P0451-P0453 | EVAP control system pressure sensor | The sensor on the canister; check its connector after any cleaning | [S1][S3] |

## Step 1: the fuel cap

- Make sure it's tight. A worn cap is the cheapest fix and owners report it works for leak codes [S2][S3].
- Nissan's cap has a vacuum relief valve that should open at 15.3-20.0 kPa (2.22-2.90 psi) of pressure and at a vacuum of 3.3-6.0 kPa (0.48-0.87 psi) [S1].
- **Use a genuine Nissan cap.** Nissan says the wrong cap can turn the check engine light on [S1].
- For P0448, a new cap seemed to fix one owner's truck until the code came back a week and a half later, after driving a gravel road [S3].

## Step 2: clean the vent valve and canister (P0447 / P0448)

1. Drop the spare tire for access [S4].
2. Remove the canister with the vent valve and pressure sensor still attached. Nissan's manual removes the vent valve by **turning it counterclockwise**, and says always fit a new O-ring [S1].
3. **Blow the dust out** of the vent valve and every canister port with compressed air until no more dust comes out. One owner got "a sand storm" out of his [S3][S4].
4. Test the vent valve: soak it with WD-40, blow it out, repeat, then put 12 V across it and listen for it clicking. If it works, reuse it; a new one cost one owner $100-200 [S3][S4].
5. Nissan's canister check: block port B and blow into port A, and air should flow freely out of port C. With vacuum on port B, vacuum should appear at ports A and C. With A and B blocked, port C should hold pressure [S1].
6. **Water-logged canister?** Nissan replaces a canister that weighs more than 2.0 kg (4.4 lb) with its valve and sensor attached, or that drains water. It then checks the hose from the canister to the frame for clogging [S1].
7. Reinstall everything and re-plug the pressure sensor firmly. One owner got P0452 after cleaning, which he suspected was a connector not fully clipped in [S3].

**Stop it coming back:** fit a filter to the vent valve's fresh-air inlet, or run a hose from the inlet up into the driver's-side taillight cavity, like a diff breather. One owner's filtered setup had run almost five years, needing just one blow-out [S3][S4]. Some later trucks have an extra Nissan dust box in the vent line, Nissan's own attempt at a fix [S4].

## Leak testing (Nissan's method)

Nissan pressurizes the system through the EVAP service port with a leak detector. **Never use compressed air or a high-pressure pump, and never exceed 4.12 kPa (0.6 psi)**, with the engine off [S1].

## Sources

Web sources accessed 2026-10-20.

- [S1] Nissan, 2007 Xterra Service Manual, section EC (Engine Control System): evaporative emission system component inspection, removal and installation, leak detection (pp. EC-34 to EC-37), on-board refueling vapor recovery diagnosis (pp. EC-39 to EC-41), DTC index (pp. EC-9 to EC-12). Revision September 2006. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2007%2Fec.pdf
- [S2] txelen and findinghope5608, replies in "2005+ Xterra OBD-II Codes", thenewx.org, 2007 and 2021. https://www.thenewx.org/threads/2005-xterra-obd-ii-codes.2393/
- [S3] maillet282, Steadyhigh, civicjoe and others, "Code P0448 - Evaporative Emission Control System Vent Control Circuit Close", xterranation.org, 2014-12-21 to 2016-04-12. https://www.xterranation.org/index.php?threads/code-p0448-evaporative-emission-control-system-vent-control-circuit-close.6274/
- [S4] Donovan Rankin, outback97 and IM1RU, "2007 0448 evap code", xterranation.org, 2021-01-22. https://www.xterranation.org/index.php?threads/2007-0448-evap-code.9890/
- [S5] Razzmaniac, "*putt putt* noise from EVAP area", xterranation.org, 2014-04-27 (P0455 fixed by replacing the purge valve). https://www.xterranation.org/index.php?threads/putt-putt-noise-from-evap-area.5215/
