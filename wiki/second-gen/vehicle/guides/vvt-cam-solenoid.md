# Variable valve timing (VVT) solenoids and codes P0011, P0021, P0075, P0081

[Guides](index.md) · [Reference home](../index.md) · Related: [Engine trouble codes](dtc-reference-vq40de.md), [Sensors](sensors.md), [Timing chain](timing-chain-replacement.md)

The VQ40DE varies **intake** cam timing with oil pressure. The ECM pulses an "intake valve timing control solenoid valve" on each bank, using signals from the crank and cam sensors, coolant temperature and vehicle speed. That advances the intake cam for low and mid-range torque [S1].

| Code | Meaning | Source |
|---|---|---|
| P0011 (bank 1) / P0021 (bank 2) | Intake valve timing control performance: actual cam angle doesn't match target | [S1] |
| P0075 (bank 1) / P0081 (bank 2) | Intake valve timing solenoid valve circuit | [S1] |

Bank 1 is the passenger side and bank 2 the driver's side [S2]. In fail-safe mode the ECM stops driving the solenoid, so valve timing stops changing [S1].

**If P0011/P0021 appears together with P0075/P0081, diagnose the circuit code first** [S1].

## Nissan's diagnosis for P0011 / P0021

1. **Oil pressure:** start the engine and check that the oil pressure warning lamp goes out. If not, check oil pressure first [S1]. Low or dirty oil is a common cause. One owner's P0011 after a timing chain job cleared with an oil change [S3].
2. **Solenoid test:** unplug it and measure the resistance across its two terminals: **7.0-7.7 Ω at 20°C (68°F)**, with no continuity from either terminal to ground. Then remove it and briefly apply 12 V across the terminals; the plunger should move. **Never apply 12 V for 5 seconds or more**, or the coil can be damaged [S1].
3. Check the crankshaft and camshaft position sensors [S1].
4. Check the signal plate at the rear of the intake camshaft for debris or chips [S1].
5. If the timing chain has been worked on, check that it's installed correctly [S1].
6. Check the lubrication circuit for blockage [S1].

Possible causes Nissan lists: the crank sensor, cam sensor, VVT solenoid, debris on the cam signal pickup, timing chain installation, and foreign matter in the VVT oil groove [S1].

**Reference values with a scan tool** (warm engine, in P or N, A/C off, no load): cam advance "INT/V TIM" is -5° to 5° at idle and about 0° to 30° at 2,000 rpm. Solenoid duty "INT/V SOL" is 0-2% at idle and about 0-50% at 2,000 rpm [S1].

## Replacing a VVT solenoid

- **Driver's side (LH):** unplug it, remove its bolts, and pull it out of the front of the rocker cover area [S4].
- **Passenger side (RH):** remove the upper intake plenum first; see [Spark plugs and the intake plenum](spark-plugs.md#passenger-side-rh-bank-plenum-off-first) [S4].
- **Always use a new O-ring, oiled with clean engine oil** [S4].

## Sources

Web sources accessed 2026-10-20.

- [S1] Nissan, 2007 Xterra Service Manual, section EC (Engine Control System), "DTC P0011, P0021 IVT Control": description, data monitor reference values, diagnosis logic, diagnostic procedure and component inspection (pp. EC-161 to EC-164); DTC index (pp. EC-9 to EC-12). Revision September 2006. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2007%2Fec.pdf
- [S2] Nissan, 2007 Xterra Service Manual, section EC, cylinder number and bank layout (p. EC-20); 2013 section EM, "No. 1 cylinder (engine front side of RH bank)" (p. EM-18). https://www.nicoclub.com/service-manual?fsm=Xterra%2F2007%2Fec.pdf
- [S3] deadpilot, reply in "How-to: Change Timing Chain - PBR", thenewx.org, 2012-02-28. https://www.thenewx.org/threads/how-to-change-timing-chain-pbr.47728/
- [S4] Nissan, 2013 Xterra Service Manual, section EM (Engine Mechanical), "Intake Valve Timing Control" solenoid valve removal and installation (p. EM-50). Revision January 2013. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FEM.pdf
