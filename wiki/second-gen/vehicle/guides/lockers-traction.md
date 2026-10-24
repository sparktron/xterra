# Lockers, traction aids and diff breathers

[Guides](index.md) · [Reference home](../index.md) · Related: [Differential rebuild and locker installs](differential-rebuild.md), [Re-gearing](regearing.md), [Differential fluid](differential-fluid.md)

## The factory rear locker (E-Lock)

Off-Road and PRO-4X Xterras have an **M226 rear axle with an electronic locking differential** (Nissan's "ELD"). A switch on the dash locks it [S1][S2].

**How it works:** the differential lock control unit (DLCU) watches vehicle speed and VDC activity from the ABS unit, and the 4WD switch position from the transfer control unit. When conditions allow, it powers a solenoid in the diff. The solenoid pushes a pressure plate against a cam ring, which locks the side gear to the case. A position switch tells the DLCU when it's locked [S1]. Owners give the factory conditions as 4LO and under about 5 mph [S3].

| DIFF LOCK lamp | Meaning | Source |
|---|---|---|
| On | Locked | [S1] |
| Flashing, once every 2 seconds | Standby: switch on, conditions not met yet, or not yet engaged | [S1] |
| Off with the switch on | Fault. The system fails safe by unlocking; read the codes with a scan tool | [S1] |

The DLCU sits **near the hood release** on Xterras and Frontiers [S3]. On the 2012 Xterra, Nissan's diagram shows the DLCU and the mode switch next to the steering column [S1].

## "Locker anytime" modifications

Owners have two ways to let the factory locker engage in 2WD and 4HI and above the speed limit [S3]:

- **A plug-in module** between the factory harness and the DLCU. It installs in a couple of minutes and keeps the factory switch and indicator [S3].
- **A wiring change at the DLCU connector**, from a schematic shared on the forum. It also keeps the factory switch and lamp [S3]. The pins one owner cut and spliced, after a first attempt where he spliced the wrong side, were [S4]:
  - cut pins 9, 11, 12, 20, 21 and 22, and cap the connector-side ends except pin 22's [S4];
  - splice the connector side of pin 22 into the pin 1 wire [S4];
  - splice the **vehicle** side of pin 11 into the ground at pin 3 (he first used the connector side, and it didn't work) [S4];
  - join the vehicle sides of pins 9 and 12, and of pins 20 and 21 [S4];
  - cap the vehicle sides of pins 11 and 22 [S4].

  **Work from the schematic, not this summary.** A wiring mistake here can disable the locker or damage the DLCU [Unverified]. The DLCU wires are about 18-20 gauge, which takes the small (red) T-taps [S5].
- **Warning from the module's seller:** engaging a locker in the wrong conditions can damage the drivetrain. If unsure, stick to the factory limits of 4LO and under 5 mph [S3].

## Adding an E-Lock axle to a truck without one

One owner swapped an E-Lock M226 into an S model and wired the locker with an indicator light [S2]:

- **Match the front ratio.** Off-Road and PRO-4X M226 axles are 3.36 or 3.69, so a 3.13 truck needs a matching front diff as well; see [Re-gearing](regearing.md) [S2].
- You need new U-bolts, new driveshaft flange bolts, brake fluid (the brake line comes apart), and 75W-140 for the M226 [S2].
- Support the frame on tall stands and let the axle droop with the wheels off. The lower shock mounts take a beating off-road; straighten them roughly with a big adjustable wrench [S2].

## Front lockers

- **Lokka** makes an automatic locker for the R180A front diff (2005-on Frontier, Xterra and Pathfinder). It replaces the spider gears in the open carrier; see the [install steps](differential-rebuild.md#example-installing-a-lokka-locker-in-an-r180a-front-diff) [S6].
- An automatic locker in the **front** of an IFS truck affects steering when it's engaged in 4WD [Unverified].

## Diff breathers for water crossings

- **Rear:** route a length of vinyl tube from the axle breather, behind the bumper and along the frame rail, to a high point behind the right taillight. Leave slack for suspension travel, and put a 1 in aquarium airstone in the end as a dust filter [S7]. On the M226, the breather is on top of the axle on the passenger side and takes a 14 mm deep socket [S8].
- **Front:** the front diff's breather tube already runs up near the air box, but it's open-ended; filter or cap it [S7].
- Check the **transfer case and transmission breathers** too before deep water [S7].
- A clogged rear breather pressurizes the axle and pushes oil past the axle seals [S8].

## Sources

Web sources accessed 2026-10-20.

- [S1] Nissan, 2012 Xterra Service Manual, section DLN (Driveline), rear final drive M226 (ELD): differential lock system cross-section, system description, indicator lamp operation and component locations (pp. DLN-245 to DLN-248). Revision December 2011. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2012%2FDLN.pdf
- [S2] Killswitch, "How-to: Install Rear Axle and Wire Locker with Indicator Light - PBR", thenewx.org, 2013-01-07. Read from the Internet Archive copy. https://www.thenewx.org/threads/how-to-install-rear-axle-and-wire-locker-w-indicator-light-pbr.60959/
- [S3] rm975, "How-to: Override M226 E-Locker - PBR", thenewx.org, 2010-03-24, with a reply by dark_knight. Read from the Internet Archive copy. https://www.thenewx.org/threads/how-to-overide-m226-e-locker-pbr.26903/
- [S4] MotorPsycho, "Locker Anytime Mod: How To (and How Not To) Do It", thenewx.org, 2013-04-28. Read from the Internet Archive copy. https://www.thenewx.org/threads/locker-anytime-mod-how-to-how-not-to-do-it.63664/
- [S5] sass, Surf and Snow and snowjunkie, replies in "How-to: Override M226 E-Locker - PBR", thenewx.org, 2010-11-05 to 11-06. https://www.thenewx.org/threads/how-to-overide-m226-e-locker-pbr.26903/
- [S6] Rooney, "How-to: Install Lokka R180 Locker - PBR", thenewx.org, 2014-04-02. Read from the Internet Archive copy. https://www.thenewx.org/threads/how-to-install-lokka-r180-locker-pbr.96865/
- [S7] BioMan, MidnightCNR and others, "How-to: Install Rear Diff Breather Extension - PBR", thenewx.org, 2006-02-17. Read from the Internet Archive copy. https://www.thenewx.org/threads/how-to-install-rear-diff-breather-extension-pbr.54/
- [S8] Longboardr, "How-to: M226 Axle Seal Replacement", thenewx.org, 2018-06-25. Read from the Internet Archive copy. https://www.thenewx.org/threads/how-to-m226-axle-seal-replacement.269492/
