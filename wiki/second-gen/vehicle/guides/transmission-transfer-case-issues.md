# Transmission and 4WD faults: warning lights, lost 4WD and limp mode

[Guides](index.md) · [Reference home](../index.md) · Related: [SMOD](smod.md), [Cooling upgrades](cooling-upgrades.md), [ATF change](atf-change.md), [Transfer case fluid](transfer-case-fluid.md), [Sensors](sensors.md), [Clutch and manual transmission](clutch-transmission-swap.md)

**Automatic acting up? Check the ATF for coolant first.** See [SMOD](smod.md).

## What the 4WD lights mean

From Nissan's 2012 manual for the TX15B transfer case [S1]:

| Light | Meaning | Source |
|---|---|---|
| 4WD warning lamp **on** | A fault in the 4WD system. The 4WD shift indicator lamps go out while it's on | [S1] |
| 4WD warning lamp **flashing slowly** (once every 2 seconds) | A large difference between front and rear tire diameters, for example a mismatched spare. It keeps flashing until the ignition is turned off | [S1] |
| **4LO lamp flashing** | The transfer case didn't finish shifting between 4H and 4LO. **It may be in neutral, and Park may not hold the truck** | [S1] |
| ATP warning lamp (automatic) | The transfer case is in neutral, so the truck can roll even with the selector in P | [S1] |

The transfer control unit gets **vehicle speed and the brake signal from the ABS unit** over the CAN bus. It also uses the automatic's output shaft speed and range signal, and engine speed. Switches on the transfer case report 4WD engaged ("wait detection"), 4LO, and neutral (the ATP switch, automatics only) [S1].

## Shifting it correctly

- **2WD and 4H:** you can switch while driving, below 100 km/h (60 mph) [S1].
- **4H and 4LO:** stop. With an automatic, shift to N with your foot on the brake; with a manual, select neutral with the clutch pressed. Turn the switch, then **wait for the 4LO lamp to stop flashing** before you select a gear or let the clutch out. It won't shift unless the transmission is in N and the truck is stopped [S1].
- Owners find 2WD-to-4H usually works while stopped in neutral too, as long as there's no tension in the driveline; try it on level pavement first. One owner who had slid off a trail edge couldn't get it to engage that way [S5].

## Lost 4WD with ABS, VDC OFF and SLIP lights on

Because the transfer control unit needs the ABS unit's speed signal, an ABS wheel speed sensor fault can also stop the transfer case shifting [S1]. Owners' cases:

- After a water crossing one owner's dash lit up with ABS, VDC OFF and SLIP, the 4WD indicator kept blinking, and there was no 4WD. A dealer found a bad wheel speed sensor, the one he'd stressed on a branch [S2].
- A front left ABS sensor wire sheared off at its plug on the hub, after snow driving. A shop spliced the wires and heat-shrank the joint [S3].
- Intermittent VDC and SLIP lights were traced to a faulty rear ABS sensor on another truck [S4].
- **A basic code reader may show nothing.** One owner's $200 scanner read no codes, but the dealer's CONSULT found them [S2].

**Prevention for water:**
- Cross slowly.
- Spray the electrical connections with silicone before trips.
- Put dielectric grease in any connector you open. A wet connector may also recover once it dries out [S2].

### Trail workaround: get into 4WD with a bad wheel speed sensor

Two owners' method, for getting home [S2][S5]:

1. With the engine off, turn the 4WD switch to 4H [S5].
2. Pull the **ABS fuse** in the engine-room fuse box (IPDM). On the newer black IPDM, one owner says it's fuse 20 [S5].
3. Start the engine, then **put the fuse back in**. You should hear the transfer case shift into 4WD [S5].
4. You can then switch between 4H and 4LO as normal. Going back to 2WD means repeating the steps [S5].

**Don't drive with the fuse out.** One owner who did lost the speedometer and odometer, the 4WD and brake warning lights stayed on, and the check engine light came on after about 10 miles [S5]. The workaround only gets you moving: the bad sensor still needs replacing.

## Steering angle sensor codes (VDC and SLIP lights)

- VDC and SLIP lights with codes C1143 or C1163 point to the steering angle sensor. One owner's steering wheel had been crooked for some time [S7]. Another's codes, C1163 and C1140, appeared after his son clipped a curb, and an alignment didn't clear them [S6].
- After a Titan swap, one owner's VDC read an off-center steering wheel as a turn, braked a wheel, then shut itself off. Re-centering the wheel fixed it [S12].
- **Bigger tires:** after fitting 33 in tires, some owners got VDC and SLIP activating on gentle curves at 20-25 mph. For one, it stopped by itself after a while [S12].

## Transfer case switches

The transfer case has three switches: 4WD engaged, 4LO, and ATP (neutral) [S1]. One owner who couldn't engage 4WD, and got a warning chime when he tried, found the front-most switch cracked almost in two. A new one was about $50 from a dealer and fixed it. Unplug each switch, check it for cracks, and clean the contacts with electrical parts cleaner [S7].

## Re-syncing the transfer control unit

Nissan's procedure after replacing the transfer control unit or the transfer case aligns the unit with the transfer case's actual position [S1].

1. Start the engine and let it run at least 10 seconds [S1].
2. Stop, and put the transmission in N with the brake pressed (clutch too, on a manual) [S1].
3. Then follow the case that matches your truck [S1]:
   - **Switch at 2WD, and a lamp is flashing:** [S1]
     1. Hold N for 2 seconds [S1].
     2. Turn the switch to 4LO and hold it there 2 seconds [S1].
     3. Ignition off, then restart [S1].
   - **Switch at 2WD, and no lamp flashing:** hold N for 2 seconds, then ignition off and restart [S1].
   - **Switch at 4H or 4LO:** hold N for 2 seconds, turn the switch to 2WD for 2 seconds, then ignition off and restart [S1].
4. Nissan then erases the stored codes with its scan tool, and checks the indicator lamps again. If they still don't follow the switch, it replaces the transfer control unit [S1].

Nissan also says to turn the ignition off and disconnect the battery before unplugging the transfer control unit, because it's powered even with the key off [S1].

## Automatic transmission (RE5R05A) limp mode

- **Fail-safe mode:** when the transmission control module sees a fault in a main input or output circuit, it locks the transmission in 2nd, 4th or 5th, depending on the fault. That feels like slipping or poor acceleration [S8].
- **It can trigger with no fault,** for example after braking hard with the wheels spinning wildly. Turning the ignition off for 10 seconds restores normal shifting [S8].
- **Overheating:** one owner's transmission went into a limp mode twice on long, slow climbs in 4LO with D selected. See [Cooling upgrades](cooling-upgrades.md) [S13].
- **Wiring:** one 2006's "limp mode" happened only with the headlights on. The cause was a botched trailer-brake splice into the right rear wiring harness, and it took a shop over 10 hours to trace [S9].
- **Downshifts on hills:** an automatic that drops a gear when you brake on a descent, then holds it at high rpm, is normal for these trucks, owners say [S10].

**Buying a used automatic:** owners say the 4WD transmission's output shaft is shorter than the 2WD's [S11].

## Sources

Web sources accessed 2026-10-20.

- [S1] Nissan, 2012 Xterra Service Manual, section DLN (Driveline), TX15B transfer: 4WD system components, indicator and warning lamps (pp. DLN-9 to DLN-11), 4WD shift operation and transfer position adjustment (pp. DLN-86 to DLN-87). Revision December 2011. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2012%2FDLN.pdf
- [S2] maillet282, obi_krash, granitex, TJTJ, metzican and others, "ABS/ VDC Off/ Slip light on and loss of 4x4 after river crossing", xterranation.org, 2014-07-13 to 2018-05-31. https://www.xterranation.org/index.php?threads/abs-vdc-off-slip-light-on-and-loss-of-4x4-after-river-crossing.5655/
- [S3] Razzmaniac and others, "ABS. VDO, SLIP lights on and NO 4WD", xterranation.org, 2014-02-16 to 2014-02-24. https://www.xterranation.org/index.php?threads/abs-vdo-slip-lights-on-and-no-4wd.4825/
- [S4] xterradad, Xebra, Maxterra and others, "Vdc and slip light", xterranation.org, 2012-08-29 to 2012-11-27. https://www.xterranation.org/index.php?threads/vdc-and-slip-light.2172/
- [S5] maillet282, "How To: 4x4 with faulty Wheel speed sensor", xterranation.org, 2019-10-28, with replies by Prime (2019-10-28, 10-29), IM1RU and Xterrorista (2023-02-03). https://www.xterranation.org/index.php?threads/how-to-4x4-with-faulty-wheel-speed-sensor.9171/
- [S6] TeXas-Hooligan, "ABS BRAKE VDC SLIP Lights all 'ON'", thenewx.org, 2019-04-16. Read from the Internet Archive copy. https://www.thenewx.org/threads/abs-brake-vdc-slip-lights-all-on.283005/
- [S7] TheFauxFox and FishOnDan, "4LO Light Blinking", xterranation.org, 2015-04-20 to 2015-04-29. https://www.xterranation.org/index.php?threads/4lo-light-blinking.6776/
- [S8] Nissan, 2008 Xterra Service Manual, section TM (Transaxle and Transmission), RE5R05A TCM fail-safe (pp. TM-183 to TM-184). Revision February 2010. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2008%2FTM.pdf
- [S9] Trexterra and NismoFire, "Feels Like Limp Mode... No Codes... Pending SMOD?", xterranation.org, 2014-04-20 to 2014-05-07. https://www.xterranation.org/index.php?threads/feels-like-limp-mode-no-codes-pending-smod.5182/
- [S10] Xterradude05 and ryandavenport, "Possible Transmission problems...", xterranation.org, 2011-10-30. https://www.xterranation.org/index.php?threads/possible-transmission-problems.104/
- [S11] BigTim55 and Pro-2X, "Difference between 4x4 and 4x2 transmission", xterranation.org, 2013-06-20. https://www.xterranation.org/index.php?threads/difference-between-4x4-and-4x2-transmission.3613/
- [S12] Oz_X, reply in "Pre Titan Swap Checklist", xterranation.org, 2012-05-16; and Diadaga, Slasa and others, "Front Diff Slip Issue", xterranation.org, 2015-01-24 to 2015-01-25. https://www.xterranation.org/index.php?threads/pre-titan-swap-checklist.1571/ and https://www.xterranation.org/index.php?threads/front-diff-slip-issue.6426/
- [S13] jeff_redx, "Thoughts and Observations on Engine and Auto Trans Cooling", thenewx.org, 2008-12-28. Read from the Internet Archive copy. https://www.thenewx.org/threads/thoughts-and-observations-on-engine-and-auto-trans-cooling.65980/
