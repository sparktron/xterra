# Automatic transmission fluid change and flush (RE5R05A)

[Guides](index.md) · [Reference home](../index.md) · [Fluids and capacities](../fluids-capacities.md) · Related: [SMOD radiator failure](smod.md)

| | |
|---|---|
| Applies to | 2005-2015 Xterra with the 5-speed automatic (RE5R05A) [S1][S2] |
| Difficulty | Easy to drain and fill. A full flush through the cooler line needs a helper [S3] |
| Time | About 30 minutes once you have done it before [S3] |
| Interval | On Nissan's severe-use Schedule 1, inspect every 15,000 mi (24,000 km). If you tow, carry a roof load, or drive rough or muddy roads, change it every 30,000 mi (48,000 km) or 24 months [S1] |

## Specifications

| Item | Value | Source |
|---|---|---|
| Fluid, 2005-2008 | Genuine Nissan Matic J ATF | [S4][S5] |
| Fluid, 2009-2015 | Genuine Nissan Matic S ATF; Matic J if S is not available | [S1][S5] |
| Total capacity | 10.3 L, 10-7/8 US qt | [S1][S4] |
| Fluid for a full flush | 30-50% more than the capacity, so roughly 14-16 qt | [S2] |
| Drain plug | 34 N·m (25 ft-lb), new gasket | [S2] |
| Oil pan bolts, if you drop the pan | 7.9 N·m (70 in-lb). The bolts are self-sealing: use new ones and a new pan gasket, and tighten in the numbered sequence | [S2] |
| Dipstick (fluid level gauge) bolt | 5.1 N·m (45 in-lb) | [S2] |
| Cooler tube union bolts at the transmission | 49 N·m (36 ft-lb), new copper washers | [S2] |

Nissan warns that any other ATF can hurt shift quality and damage the transmission, and that the damage is not covered by warranty [S1]. Many owners run Matic S in older trucks too, since Nissan lists it as the successor [Unverified].

**Do not confuse the pan bolts with the drain plug.** Forum write-ups quote "25 ft-lbs" for the drain plug, which is correct [S2][S3]. The pan perimeter bolts take 70 *inch*-pounds, about 6 ft-lb [S2].

## Tools

- 10 mm socket for the dipstick tube bolt, and a socket for the pan drain plug [S3]
- Torque wrench that reads low enough for the dipstick bolt
- Long funnel for the dipstick tube [S3]
- Drain container large enough for 5 qt from the pan and about 10 more from a flush. Owners like the free 5-gallon fry-oil jugs restaurants throw out [S3].
- About 4 ft of clear hose that fits the cooler line, so you can see the fluid's color [S3]
- A helper to run the engine and shift while you watch the hose [S3]

## Method 1: drain and fill (Nissan's basic change)

A drain and fill replaces only what comes out of the pan, about 4-5 qt of the 10-7/8 qt [S1][S3]. Repeat it to work the new fluid through.

1. Drive until the ATF is about 80°C (176°F), then stop the engine [S2].
2. Remove the dipstick (10 mm bolt) [S2][S3].
3. Remove the drain plug and drain the fluid. Measure how much came out [S2].
4. Fit the drain plug with a **new gasket** and torque it to 34 N·m (25 ft-lb) [S2].
5. Refill through the dipstick tube with the **same volume that drained out** [S2].
6. Drive to warm the ATF to about 80°C (176°F) again, then check the level and condition. If the fluid is still dirty, repeat from step 2 [S2].
7. Refit the dipstick and torque its bolt to 5.1 N·m (45 in-lb) [S2].

## Method 2: flush through the cooler line (Nissan's method, owners call it the PMF)

Nissan's manual flushes the coolers this way. Pour new ATF into the dipstick tube with the engine idling while old fluid drains from the auxiliary cooler's return line. Stop when the fluid coming out looks like the new fluid; that takes 30-50% more fluid than the capacity [S2]. Owners call it the "poor man's flush" (PMF) [S3].

1. Do Method 1 steps 1-5 first: drain the pan, refit the plug, refill with what came out, about 4-5 qt [S3].
2. Disconnect a cooler hose. Nissan uses the auxiliary cooler's return line [S2]. Owners have used either the supply line or the line leaving the radiator's cooler; any break in the loop works [S3]. Push a length of clear hose onto the line and run it into your container [S3].
3. Have the helper start the engine. Fluid pumps out of the hose. Pour new ATF into the dipstick tube as fast as it comes out, so the transmission never runs low [S2][S3].
   - If you are working alone, run the engine a few seconds, shut it off, add fluid, and repeat [S3].
   - Running the pump dry for long can damage it [S3].
4. Stop when the fluid in the clear hose is the same red as the new fluid [S2][S3].
5. Reconnect the cooler hose and its clamp, then top up the dipstick tube [S3].
6. With the engine idling, move the selector through every position and back to P [S1].
7. Warm the transmission, then check the level on the dipstick's HOT range (see below) and correct it [S1].

## Checking the level correctly

The RE5R05A dipstick has a COLD range for 30-50°C (86-122°F) and a HOT range for about 65°C (149°F); the HOT band covers 50-80°C (122-176°F) [S1].

1. Park level, set the parking brake, idle the engine, run the selector through every position, and leave it in P [S1].
2. Wipe the dipstick with **lint-free paper, not cloth** [S1].
3. Push the dipstick in **reversed from its normal position**, until its cap touches the top of the charging pipe, then pull it and read it [S1].
4. Nissan reads the fluid temperature with a scan tool (CONSULT, "ATF TEMP 1"), because the level changes a lot with temperature [S1]. A generic OBD-II tool that shows the transmission temperature does the same job [Unverified].
5. Do not overfill [S1].

## What the old fluid tells you

- Very dark fluid, or fluid that smells burnt, can mean internal wear [S1].
- Clutch or band material in the fluid means the transmission needs repair, the radiator must be replaced and the cooler lines cleaned [S1].
- **Pink, milky fluid ("strawberry milkshake") means coolant has got into the ATF**, usually through a failed cooler inside the radiator (SMOD). Stop driving and see [SMOD radiator failure](smod.md).

## Sources

Web sources accessed 2026-10-20. Torque values in the factory service manual (FSM) are printed on its drawings.

- [S1] Nissan, 2013 Xterra Service Manual, section MA (Maintenance): "Fluids and Lubricants" (p. MA-13), Schedule 1 (p. MA-9), "A/T Fluid" checking and changing (pp. MA-25 to MA-28). Revision January 2013. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FMA.pdf
- [S2] Nissan, 2013 Xterra Service Manual, section TM (Transaxle and Transmission), RE5R05A: "Changing the A/T Fluid (ATF)" (p. TM-215), "Oil Pan" (pp. TM-230 to TM-231), control valve and oil pan components (p. TM-232), transmission assembly 4WD components (p. TM-251). Revision January 2013. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FTM.pdf
- [S3] Rook, "How-to: Transmission PMF (Poor Man's Flush) - PBR", thenewx.org, 2009-07-07, with replies by MikeStaten and Surf and Snow. https://www.thenewx.org/threads/how-to-transmission-pmf-poor-mans-flush-pbr.30213/
- [S4] Nissan, 2006 Xterra Service Manual, section MA, "Fluids and Lubricants" (p. MA-11). https://www.nicoclub.com/service-manual?fsm=Xterra%2F2006%2Fma.pdf
- [S5] Nissan, 2008 and 2009 Xterra Owner's Manuals, "Recommended fluids/lubricants and capacities" (2008 lists Matic J; 2009 lists Matic S). https://owners.nissanusa.com/content/techpub/ManualsAndGuides/Xterra/2009/2009-Xterra-owner-manual.pdf
