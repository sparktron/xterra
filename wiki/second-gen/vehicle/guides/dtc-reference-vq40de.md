# Engine trouble codes (VQ40DE): reading them, and what the common ones mean

[Guides](index.md) · [Reference home](../index.md) · Related: [Sensors](sensors.md), [EVAP system](evap-system.md), [VVT solenoids](vvt-cam-solenoid.md), [Throttle and idle relearn](throttle-body-idle-relearn.md)

## Reading codes

**With a reader:** any OBD-II scan tool plugged into the diagnostic connector under the dash reads the P-codes. Turn the ignition ON [S2]. ABS/VDC codes (C-codes) need a reader that covers the ABS unit; see [Electrical faults](electrical-faults.md#abs-brake-vdc-off-and-slip-lights-all-on-together) [S3]. If a reader shows "linking error" on every protocol, try another reader; in one case the reader itself was faulty [S2].

**Without a reader: Nissan's Diagnostic Test Mode II.** The check engine light (MIL) blinks out the stored codes [S1]. Time it with a clock [S1]:

1. With the accelerator fully released, turn the ignition ON (engine off) and wait 3 seconds [S1].
2. Within 5 seconds, fully press and release the accelerator 5 times [S1].
3. Wait 7 seconds, then press the accelerator fully and hold it about 10 seconds, until the MIL starts blinking [S1].
4. Release the pedal. The MIL now blinks the codes [S1].
   - Each code is 4 digits. The first digit flashes are long, 0.6 s on and 0.6 s off. The other digits are short flashes, 0.3 s on and 0.3 s off [S1].
   - There's a 1.0 s gap between digits and a 1.8 s gap between codes. Zero is 10 flashes and "A" is 11 [S1].
   - **0000 means no fault** [S1].
5. **To erase** while in this mode, hold the accelerator fully down for more than 10 seconds, release it, and confirm 0000 is shown [S1]. Diagnose before you erase [S1].

Disconnecting the battery also clears the codes within 24 hours, along with the freeze-frame and readiness data an inspection station may need [S1].

**Bank 1 is the passenger (right-hand) side, cylinders 1-3-5; bank 2 is the driver's side, cylinders 2-4-6.** Nissan's bank drawing puts cylinders 1, 3 and 5 in bank 1, and places cylinder 1 at the front of the RH bank [S1][S9]. One forum reply has the banks the other way round [S10]. The manual is right.

## Common codes and where to start

The code and description columns are from Nissan's DTC index [S1]. The "where to start" column is general diagnostic practice, plus owners' fixes where a source is cited. It is not Nissan's diagnostic procedure, which is on the EC page listed for each code [Unverified].

| Code | Nissan's description | Where to start | Source |
|---|---|---|---|
| P0011 / P0021 | Intake valve timing control, bank 1 / bank 2 | Oil level and condition first, then the VVT solenoid; see [VVT solenoids](vvt-cam-solenoid.md) | [S1][S6] |
| P0075 / P0081 | Intake valve timing solenoid circuit, bank 1 / 2 | Solenoid connector and wiring, then the solenoid | [S1] |
| P0101-P0103 | Mass air flow sensor or circuit | Air leaks after the MAF, the MAF connector, a dirty sensor | [S1][S7] |
| P0128 | Thermostat function | Thermostat stuck open; see [Water pump and thermostat](water-pump-thermostat.md) | [S1] |
| P0130-P0133, P0150-P0153 | A/F sensor 1, bank 1 / 2 (upstream) | Exhaust leaks, then the sensor; see [Sensors](sensors.md#airfuel-ratio-sensors) | [S1] |
| P0171 / P0174 | Fuel system lean, bank 1 / 2 | Vacuum leaks (PCV hoses, intake gaskets), the MAF, fuel pressure | [S1] |
| P0300-P0306 | Random / cylinder 1-6 misfire | Plugs, coils (swap a coil to another cylinder and see if the code follows), injectors | [S1] |
| P0335 | Crankshaft position sensor | Stalling at low rpm; see [Sensors](sensors.md#crankshaft-position-sensor) | [S1][S4] |
| P0340 / P0345 | Camshaft position sensor, bank 1 / 2 | Stalling, VDC/SLIP lights; see [Sensors](sensors.md#camshaft-position-sensors) | [S1][S5] |
| P0420 / P0430 | Catalyst efficiency, bank 1 / 2 | Rule out exhaust leaks and the downstream O2 sensor before replacing a catalyst | [S1] |
| P0441-P0456 | EVAP system; P0455 is a gross leak, P0456 a very small leak | The **fuel cap** first; see [EVAP system](evap-system.md) | [S1][S2] |
| P0447 / P0448 | EVAP vent control valve | The vent valve at the EVAP canister, behind the left rear wheel; see [EVAP system](evap-system.md) | [S1][S2] |
| P0460-P0463 | Fuel level sensor | The sender in the tank; see [Fuel pump and sender](fuel-pump.md) | [S1][S8] |
| P0500 | Vehicle speed sensor | ABS wheel sensors and wiring | [S1] |
| P0700-P0745, P1730-P1774 | Transmission (TCM, sensors, solenoids) | ATF level and condition; see [ATF change](atf-change.md) and [SMOD](smod.md) | [S1] |
| P1217 | Engine over temperature | Coolant level and fans; see [Coolant](coolant-flush.md) | [S1] |
| P1610-P1615 | NATS (immobilizer) malfunction | The key and the NATS antenna. One owner got P1615 after five failed start attempts | [S1][S2] |
| P1800 | VIAS solenoid valve circuit | VIAS solenoid on the intake plenum; see [Engine noises](engine-noises.md) | [S1] |
| P2100-P2138 | Electronic throttle and accelerator pedal sensors | Connectors, then the [throttle relearn](throttle-body-idle-relearn.md) | [S1] |
| U1000 / U1001 / U1010 | CAN communication | Diagnose these **before** any other codes | [S1] |

The full list of about 150 codes, with page references for each, is in the FSM's EC section index (pp. EC-9 to EC-12) [S1].

## Sources

Web sources accessed 2026-10-20.

- [S1] Nissan, 2007 Xterra Service Manual, section EC (Engine Control System): DTC number index (pp. EC-9 to EC-12), malfunction indicator lamp and diagnostic test modes (pp. EC-62 to EC-65). Revision September 2006. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2007%2Fec.pdf
- [S2] Muzikman, txelen, Kleibertron, HawaiianXterra and findinghope5608, "2005+ Xterra OBD-II Codes", thenewx.org, 2006-2021. https://www.thenewx.org/threads/2005-xterra-obd-ii-codes.2393/
- [S3] Nissan, 2013 Xterra Service Manual, section BRC (Brake Control System). https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FBRC.pdf
- [S4] Amazingracer, "How-to: Replace Crankshaft Position Sensor", thenewx.org, 2015-01-24. https://www.thenewx.org/threads/how-to-replace-crankshaft-position-sensor.138498/
- [S5] heathenized, "How-to: Replace Camshaft Position Sensor (P0345) - PBR", thenewx.org, 2012-03-05 (identifies bank 2 as the driver's side). https://www.thenewx.org/threads/how-to-replace-camshaft-position-sensor-p0345-pbr.52030/
- [S6] deadpilot, reply on P0011 after a timing chain job, "How-to: Change Timing Chain - PBR", thenewx.org, 2012-02-28. https://www.thenewx.org/threads/how-to-change-timing-chain-pbr.47728/
- [S7] Lowcountry idn, reply in "Electrical Issues, ECM or Bad Ground?", thenewx.org (on cleaning the MAF sensor). https://www.thenewx.org/threads/electrical-issues-ecm-or-bad-ground.284270/
- [S9] Nissan, 2013 Xterra Service Manual, section EM, camshaft valve clearance ("No. 1 cylinder (engine front side of RH bank)", p. EM-18), and 2007 section EC, cylinder number and bank layout (p. EC-20). https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FEM.pdf
- [S10] Prime, reply in "Damned squirrel....VIAS control solenoid wire chewed through", xterranation.org, 2026-04-07. https://www.xterranation.org/index.php?threads/damned-squirrel-vias-control-solenoid-wire-chewed-through.11523/
- [S8] natEDawgG, "How-to: Replace Fuel Sender Unit (FSU)", thenewx.org, 2011-01-04 (P0463). https://www.thenewx.org/threads/how-to-replace-fuel-sender-unit-fsu.37876/
