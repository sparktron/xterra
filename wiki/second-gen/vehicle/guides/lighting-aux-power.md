# Lighting, auxiliary lights and wiring

[Guides](index.md) · [Reference home](../index.md) · Related: [Fuses and relays](fuse-relay-map.md), [Electrical faults](electrical-faults.md)

## Factory bulbs

| Lamp | Wattage | Bulb | Source |
|---|---|---|---|
| Headlamp, low/high | 55/65 W | 9007 dual-filament, one owner reports | [S1][S2] |
| Front fog lamp | 55 W | | [S1] |
| Roof-mounted off-road lights (Off-Road and PRO-4X) | 55 W | One owner found **9005**, though his owner's manual said 9006; a 9006 has a wider base and doesn't fit | [S1][S3] |
| Front turn signal / parking lamp | 28/8 W | | [S1] |
| Front side marker | 3.8 W | | [S1] |
| Rear stop/tail lamp | 27/8 W | | [S1] |
| Rear turn signal | 27 W | | [S1] |
| Back-up lamp | 18 W | | [S1] |
| License plate lamp | 5 W | | [S1] |

These are from Nissan's 2012 manual, which says to check with a parts department for the current part [S1].

## How the factory lights interlock

- **Fog lamps** need the headlamps on. The lighting stalk sends the fog request to the body control module (BCM). The BCM passes it over the CAN bus to the engine-room fuse and relay box (IPDM E/R), which grounds the fog lamp relay coil [S1].
- On owners' trucks the fogs **go off when you switch to high beams**. The roof lights work **only with the high beams on**, so you can't run fogs and roof lights together without a modification [S4].
- **Roof lights and their covers:** the roof lights won't come on with the plastic covers fitted. One owner found that refitting the covers resets them: with the covers off, he had to switch on the high beams, then the off-road light switch [S3].

## Roof light bulbs (Off-Road and PRO-4X)

1. Remove the roof basket from the rack, using the Torx wrench from the jack kit under the rear seat. You don't need to touch the headliner [S3].
2. If you still can't reach the bulbs, unbolt the air dam that carries the lights. It has 4 bolts on the leading edge into the roof, and one owner thought there was one each side at the back [S3].
3. Fit 9005 bulbs. One owner's PIAA 9005 swap took about 10 minutes [S3].
4. **Aiming:** with the light cover off, there's an adjusting screw in a hole [S3].

## Replacing and aiming the headlight assemblies

From an owner's write-up on a 2015 PRO-4X. He fitted CAPA-certified TYC housings from RockAuto, and found their fit as good as Nissan's [S5].

1. Remove the grille: plastic push fasteners, then tabs into the bumper [S5].
2. Remove the front bumper cover in one piece [S5]:
   1. the plastic fasteners to the crash bar [S5];
   2. the 10 mm screws to the radiator skid plate [S5];
   3. 2 screws at the bottom of each wheel well and 2 on its outer edge [S5];
   4. a 10 mm bolt behind the fender liner at the top [S5];
   5. the fog lamp connectors, if fitted [S5].
   
   Pull it off from the sides, gently: there are clips under the fender front [S5].
3. Each headlight has **4 bolts**: 2 on top, 1 low by the grille, and 1 under the fender behind the bumper. Unplug the side marker, turn signal and headlamp connectors [S5].
4. Install in reverse. Start every bolt loosely before snugging them, and don't overtighten [S5].
5. **Aim them:** [S5]
   1. Load the truck as it normally sits: full tank, spare fitted, a driver's weight in the seat [S5].
   2. Park on level ground with the headlights 25 ft from a wall [S5].
   3. Put tape on the wall at the height of the headlamp bulbs (about 39 in on his truck) [S5].
   4. Adjust each lamp with the up/down screw on the back of the housing (8 mm socket or #2 Phillips) until the top of the low beam lines up with the bottom of the tape. Cover the other lamp while you adjust [S5].
   5. Turn the fogs off while aiming [S5].

## Brighter headlights with a relay harness

A relay harness feeds the bulbs straight from the battery through heavier wire than the factory's, and the factory headlamp circuit only switches the relays [S2].

- One owner's harness: 12 AWG wire, 2 Pico 40 A waterproof relays, 9007 plug-in pigtails at the factory connector and at both bulbs, and separately fused low and high beam feeds from the battery, so one fault can't kill both beams [S2].
- **Current:** stock 9007 55/65 W bulbs draw about 4.58 A low and 7.08 A high each. Hella Optilux 80/100 W bulbs draw about 6.67 A and 8.33 A each. At about 5 ft, 12 AWG loses a little under 1% voltage [S2].

## Wiring auxiliary lights properly

From a detailed write-up on wiring roof lights, bumper lights and a switch panel on a 2009 Off-Road [S6]:

- **Current:** a 55 W lamp draws about 4.58 A at 12 V, so a pair is about 10 A. Fuse that pair at 15 A, and use a relay rated **20 A or more**, because a cold filament has a large inrush current [S6].
- **Use a relay.** Switch the lights through a relay's 30 and 87 terminals (the normally open contact). The dash switch then carries only the small coil current, on thin wire [S6].
- **Fuse at the battery.** Put the main fuse as close to the battery as possible. It protects the wire, so size it below what the thinnest wire can carry [S6].
- **Take power from the battery post,** not after the factory fuses [S6].
- **Size wire for 1 V of drop or less** over the whole run. At 12 V, 1 V is about 8% [S6].
  - The writer used 12 AWG for every light circuit, and 4 AWG from the battery to a 60 A main fuse and a Blue Sea 5026 fuse block by the glove box [S6].
  - Doubling a wire's capacity means half the resistance, not half the gauge number: four 14 AWG wires equal one 8 AWG [S6].
- **Grounds:** ground the lights inside the cab or under the hood rather than on an exterior bumper, where rust degrades the joint. Sand to bare metal where a ground bolts on [S6].
- **Keep water out:**
  - Route every wire down, then up into each connector or grommet, so water drips off first [S6].
  - He entered the cab through the driver's-side firewall grommet [S6].
  - For roof wiring he cut a 1 1/8 in hole for a seal-tight cord connector, near the roof bin, and silicone-filled the gaps between the wires inside heat-shrink. It was still dry a year later [S6].
- Use wire loom, and don't overtighten cable ties on bundled wires [S6].

## Fog light bypass

The mod lets you run the fogs with the high beams and roof lights, still using the factory fog switch on the stalk [S4][S7].

- **How it works:** two wires are brought out of the stalk's fog switch. One is grounded, and the other runs to the fog lamp relay circuit, so the switch drives the relay directly [S4][S7]. One writer said it took about an hour and under $10 of parts [S7].
- **2005-2008:** use macguyvermedic's original method, which works at the factory fog lamp relay [S4][S7].
- **2009 and later:** the fog lamp relay is integrated into the IPDM, so there's no relay to modify. You add your own relay, wired to fuse slots in the IPDM and to the battery [S4][S7]. Check the fuse positions against your own fuse box and the [fuse map](fuse-relay-map.md) before you tap anything [Unverified].
- **Don't make it fully independent unless you mean to.** Fed from the parking-light circuit, the fogs can only come on when the parking lights are on, so you can't leave them on and flatten the battery [S4][S7].

## Sources

Web sources accessed 2026-10-20.

- [S1] Nissan, 2012 Xterra Service Manual, section EXL (Exterior Lighting System): front fog lamp system description (p. EXL-14), bulb specifications (p. EXL-153). Revision December 2011. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2012%2FEXL.pdf
- [S2] General_Tarfun, "How to: Build Relay Harness For 100 Watt Headlight Bulbs", xterranation.org, 2019-08-01. https://www.xterranation.org/index.php?threads/how-to-build-relay-harness-for-100-watt-headlight-bulbs.8850/
- [S3] Xebra, "Pro-4X Off Road Lights Bulb Replacement", xterranation.org, 2012-05-24, with replies by J Everett (2016-02-05), RikRong (2016-02-07) and Xebra (2012-05-25, 2016-02-16). https://www.xterranation.org/index.php?threads/pro-4x-off-road-lights-bulb-replacement.1662/
- [S4] 2k11pro4x, "How-to: Fog lights by-pass without giving up factory switch", xterranation.org, 2011-12-15, with replies by J Everett (2013-03-02) and Prime (2014-04-24). https://www.xterranation.org/index.php?threads/how-to-fog-lights-by-pass-without-giving-up-factory-switch.561/
- [S5] XterraRising, "How To:Replace Your Headlight Assemblies", xterranation.org, 2021-02-21. https://www.xterranation.org/index.php?threads/how-to-replace-your-headlight-assemblies.9918/
- [S6] XJ-TERRA, "-How-to: From the Battery to the Roof Lights and In-between - PBR", thenewx.org, 2010-12-26. Read from the Internet Archive copy. https://www.thenewx.org/threads/how-to-from-the-battery-to-the-roof-lights-and-in-between-pbr.37578/
- [S7] Replies by macguyvermedic, treybomb, joelo and others in "How-to: Pictorial Guide for the Fog Light Bypass MOD - PBR", thenewx.org, 2011-04-10 to 2011-09-21. The opening post was not in the archived copy. https://www.thenewx.org/threads/how-to-pictorial-guide-for-the-fog-light-bypass-mod-pbr.41057/
