# Transmission and engine cooling upgrades

[Guides](index.md) · [Reference home](../index.md) · Related: [SMOD](smod.md), [Radiator replacement and bypass](radiator-smod-fix.md), [ATF change](atf-change.md), [Coolant flush](coolant-flush.md)

The automatic transmission fluid (ATF) has two coolers in series:
- the **radiator cooler**, in the bottom tank of the radiator;
- the **air cooler**, a small finned cooler in front of the A/C condenser [S1].

The SMOD fix (bypassing the radiator cooler, or replacing the radiator) removes the radiator cooler's failure risk. A bypass also removes cooling, so plan for it [S1].

## What one owner's measurements showed

An owner logged ATF temperatures at several points, and engine coolant temperature, on his truck [S1]:

- **The radiator cooler doesn't heat the ATF.** He never measured ATF leaving the radiator cooler hotter than it went in, including warm-ups at ambient temperatures as low as 20°F. The ATF in the pan reached 100°F before the coolant reached 165°F, below the thermostat's opening point [S1].
- **The air cooler does nothing below about 20-25 mph.** He measured no temperature drop across it at those speeds, so at low speed the radiator cooler does most of the work [S1].
- **How you drive matters more than the weather.** Under heavy load below about 2,500 rpm, the torque converter isn't locked and slips, which makes a lot of heat. Long grades and slow trails in D are the worst case [S1].
- **Stock coolers can still overheat it off road.** On high-altitude passes in Colorado, over 12,000 ft at 55-60°F ambient, his truck went into a limp mode twice in 4LO and D, with both factory coolers working. Shifting manually to 2nd got it moving and cooled the ATF quickly [S1].
- **Steady highway cruising is the easiest case.** At 45-70 mph in 5th with the converter locked, little heat is made, so highway temperatures say little about trail or towing needs [S1].

Other owners disagree on whether the bypass matters. One with a bypass, and only the stock air cooler, reported ATF at 170°F or lower in Texas heat, spiking to about 190°F once, with coolant at 195-215°F. He held that the radiator cooler warms the ATF more than it cools it [S2]. The measurements above contradict that for warm-up, so check your own truck with a gauge [S1].

## Step 1: watch the ATF temperature

- Fit an ATF temperature gauge with its sensor in the pan, or read it with an OBD monitor [S1][S2].
- The measuring owner eased off off-road at about **190°F**, a deliberately conservative limit [S1].

## Step 2: drive to keep the converter locked

- **Pick a lower gear manually** on climbs and slow trails. He found the stock coolers enough as long as the engine stayed above about 2,200 rpm [S1].
- Left in D on climbs, the transmission tends to upshift early and slip the converter [S1].
- One owner found **4LO much easier on the ATF than 4HI** for long snowy climbs [S1].

## Step 3: add a fan to the air cooler

A pusher fan on the factory air cooler adds a lot of low-speed cooling, but nothing above about 50-60 mph. It won't cover towing up long grades on its own [S1].

## Step 4: add or upgrade an air cooler

- **Give it its own airflow.** Don't sandwich a second cooler behind or in front of the factory one [S1].
  - One owner with two coolers sandwiched together, plus a fan, saw his engine coolant reach 220°F on a climb in hot weather. He blamed blocked airflow heat-soaking the radiator, and moved to one larger B&M cooler [S1].
- **One owner's plan for a standalone cooler with its own fan** (bypass done):
  - The hard lines out of the transmission are **5/16 in**, so he used 5/16 in compression to 3/8 in barb adapters and 3/8 in hose up to the cooler [S2].
  - The cooler had 1/2 in NPT ports [S2].
  - He wired the fan through a **15 A** inline fuse [S2].
  - He capped the flushed radiator lines.
  - He fitted a temperature sender in a 5/16 in compression tee in the hard line [S2].
- **Z1 stacked-plate cooler:** one owner swapped the factory air cooler for a Z1 19-row stacked-plate cooler in about 90 minutes [S3].
  - He joined the return line with a 5/16 in barbed connector [S3].
  - He needed thicker crush washers than the kit's on the banjo bolts to get them to seal [S3].

## Or keep a radiator cooler, without the SMOD risk

The measuring owner replaced the factory radiator with a **Koyo A2807**, which has a brass ATF cooler instead of the factory's brazed aluminum one. That kept the low-speed cooling of a radiator cooler [S1]. See [Radiator replacement and bypass](radiator-smod-fix.md) for the job.

## Engine cooling: the stock system is strong

- He never saw coolant above 205°F off road in 100°F+ heat in 4LO with the A/C on [S1].
- **Check the coolant level with the engine cold and running.** With it stopped, the reservoir can read falsely high. Low coolant first shows as weak heat at idle [S1].
- The reservoir is part of the pressurized system, an expansion and air-separator tank, not an overflow bottle. With enough coolant in it, the system purges trapped air by itself [S1].

## Sources

Web sources accessed 2026-10-20.

- [S1] jeff_redx, "Thoughts and Observations on Engine and Auto Trans Cooling", thenewx.org, 2008-12-28, with replies by rocknhd, Bliss_X, Mr. Bills and others (2010-2013). Read from the Internet Archive copy. https://www.thenewx.org/threads/thoughts-and-observations-on-engine-and-auto-trans-cooling.65980/
- [S2] Killswitch, dhyde79, Xtacular, granitex and mudchet, "Transmission cooler and the bypass...Question", xterranation.org, 2012-06-12 to 2012-09-12. https://www.xterranation.org/index.php?threads/transmission-cooler-and-the-bypass-question.1783/
- [S3] Brunnie, "Z1 Transmission Cooler Upgrade", xterranation.org, 2026-05-04. https://www.xterranation.org/index.php?threads/z1-transmission-cooler-upgrade.11535/
