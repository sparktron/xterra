# Throttle body cleaning and the idle relearn (no scan tool needed)

[Guides](index.md) · [Reference home](../index.md) · Related: [Electrical faults](electrical-faults.md), [Spark plugs and the intake plenum](spark-plugs.md)

| | |
|---|---|
| Applies to | 2005-2015 Xterra, VQ40DE with an electronic (drive-by-wire) throttle [S1] |
| When | After cleaning or replacing the throttle body, unplugging the throttle body or the ECM, replacing the ECM, or when the idle speed is out of spec [S1] |
| Specified idle | 625 ± 50 rpm in P or N; ignition timing 15 ± 5° BTDC [S1] |

## Cleaning the throttle body

- Do it with the **battery disconnected**. One owner who cleaned a dirty throttle body without disconnecting the battery had a poor idle for about a week while the ECM relearned [S2].
- The throttle body has two small **coolant hoses** (to keep it from icing). If you remove it, cap them [S2]. The manual partly drains the coolant first [S3].
- The intake side has a black plastic screen held by a small clip, which can be removed for access [S2].
- Use a throttle-body cleaner, and open the drive-by-wire blade **gently** by hand [S2].
- If you unplugged the throttle body, do the **Throttle Valve Closed Position Learning** below; if you replaced it, do the full **Idle Air Volume Learning** [S1][S3].

## The three relearn procedures (Nissan's)

Do them in this order. Each later one includes the earlier ones [S1].

### 1. Accelerator Pedal Released Position Learning

Needed whenever the accelerator pedal sensor or the ECM has been unplugged [S1].

1. Make sure the accelerator pedal is fully released [S1].
2. Ignition ON, wait at least 2 seconds [S1].
3. Ignition OFF, wait at least 10 seconds [S1].
4. Ignition ON, wait at least 2 seconds [S1].
5. Ignition OFF, wait at least 10 seconds [S1].

### 2. Throttle Valve Closed Position Learning

Needed whenever the throttle body or the ECM has been unplugged [S1].

1. Accelerator fully released [S1].
2. Ignition ON [S1].
3. Ignition OFF and wait at least 10 seconds. **Listen for the throttle valve moving** during those 10 seconds [S1].

### 3. Idle Air Volume Learning (without CONSULT)

**Preparation.** All of these must hold the whole time, or the learning cancels [S1]:

- Battery above 12.9 V at idle [S1]
- Coolant at 70-100°C (158-212°F), i.e. fully warm [S1]
- In P or N (PNP switch on) [S1]
- A/C, headlamps and rear defogger off. On trucks with daytime running lights, apply the parking brake **before** starting so the headlamps stay off [S1]
- Steering straight ahead, truck stopped [S1]
- Transmission warm: drive about 10 minutes [S1]

**Procedure** (time it with a clock; the timing matters) [S1]:

1. Do procedures 1 and 2 above [S1].
2. Start the engine and warm it fully. Check the preparation list again [S1].
3. Ignition OFF, wait at least 10 seconds [S1].
4. With the accelerator fully released, ignition ON, wait 3 seconds [S1].
5. Within 5 seconds, **fully press and fully release the accelerator 5 times** [S1].
6. Wait 7 seconds, then **press the accelerator fully and hold it about 20 seconds**, until the check engine light stops blinking and stays ON [S1].
7. **Release the pedal within 3 seconds** of the light coming on steady [S1].
8. Start the engine and let it idle for 20 seconds [S1].
9. Rev it two or three times and check that idle and timing are in spec [S1].

One owner needed three tries; he compared the timing to a dance game [S2].

**If it won't learn,** Nissan checks that the throttle valve closes fully, that the PCV valve works, and that there's no air leak downstream of the throttle. Then it looks at engine parts and their installation. If the engine stalls or idles erratically after starting, fix the cause and repeat the learning [S1].

With a CONSULT tool, the same learning is "IDLE AIR VOL LEARN" in WORK SUPPORT; it should show CMPLT after about 20 seconds [S1].

## Sources

Web sources accessed 2026-10-20.

- [S1] Nissan, 2007 Xterra Service Manual, section EC (Engine Control System), basic service procedure: accelerator pedal released position learning, throttle valve closed position learning, idle air volume learning (pp. EC-78 to EC-80). Revision September 2006. https://www.nicoclub.com/service-manual?fsm=Xterra%2F2007%2Fec.pdf
- [S2] Shiny, xterramex, bigriver and Wheelhorse, "Throttle Bottle Idle Air Re-learn", thenewx.org, 2009-01-01 to 01-02. https://www.thenewx.org/threads/throttle-bottle-idle-air-re-learn.14334/
- [S3] Nissan, 2013 Xterra Service Manual, section EM, intake manifold collector and electric throttle control actuator (pp. EM-25 to EM-27). https://www.nicoclub.com/service-manual?fsm=Xterra%2F2013%2FEM.pdf
