from xw.grounding import (dtc_grounded, grounded_terms, ground_fact, has_long_overlap, link_grounded, number_tokens,
                          part_grounded, spec_grounded, spec_value_grounded)
from xw.schemas import Fact, Part, Spec

TEXT = "Torque the pivot bolts to 83 ft-lb. Drain 1,000 ml and refill 7,5 l. New arm 54500-EA000. Code P0340 returned. [image: https://x.invalid/a.png]"


def test_number_tokens_normalise():
    assert number_tokens("83 ft-lb (113 N·m)") == ["83", "113"]
    assert number_tokens("1,000 ml") == ["1000"]
    assert number_tokens("7,5 l") == ["7.5"]


def test_spec_grounded_true_and_false():
    assert spec_grounded("83 ft-lb", "", TEXT)
    assert spec_grounded("1000 ml", "", TEXT)
    assert spec_grounded("7.5", "l", TEXT)
    assert not spec_grounded("85 ft-lb", "", TEXT)      # invented number
    assert not spec_grounded("113 N·m", "", TEXT)       # converted unit the text never states
    assert not spec_grounded("torque", "", TEXT)        # no number at all


def test_spec_grounded_needs_whole_number():
    assert not spec_grounded("8 ft-lb", "", "tighten to 83 ft-lb")
    assert not spec_grounded("3", "", "tighten to 3.5 turns")


def test_part_dtc_link():
    assert part_grounded("54500 EA000", TEXT)
    assert not part_grounded("54501-EA000", TEXT)
    assert not part_grounded("12", TEXT)
    assert dtc_grounded("p0340", TEXT) and not dtc_grounded("P0341", TEXT)
    assert link_grounded("https://x.invalid/a.png", TEXT) and not link_grounded("https://x.invalid/b.png", TEXT)


def test_a_value_needs_to_be_in_the_source_not_the_models_quote():
    """Decided 2026-10-16: only the value needs to be correct. 39 specs and 10 part numbers whose value (with its unit)
    is in the source were dropped because the model left `evidence` empty or paraphrased it; what makes a value wrong is
    a number, unit or part number the source does not state, and those are still refused."""
    for ev in ("", "the pivot bolts take 83 foot-pounds", "Torque the pivot bolts to 83 ft-lb"):
        assert spec_value_grounded(Spec(item="Pivot bolt torque", value="83", unit="ft-lb", evidence=ev), TEXT)
    assert not spec_value_grounded(Spec(item="Pivot bolt torque", value="85", unit="ft-lb",
                                        evidence="Torque the pivot bolts to 83 ft-lb"), TEXT)          # invented number
    assert not spec_value_grounded(Spec(item="Pivot bolt torque", value="83", unit="in-lb"), TEXT)      # wrong unit
    assert not spec_value_grounded(Spec(item="Fuse size", value="various"), TEXT)                       # not a value
    assert not spec_value_grounded(Spec(item="Pivot bolt torque", value="113", unit="N·m"), TEXT)       # converted


def test_grounded_terms():
    assert grounded_terms(["Off-Road", "SE"], "My 2008 Xterra Off-Road needs arms") == ["Off-Road"]


def test_grounded_terms_use_word_boundaries():
    assert grounded_terms(["SE", "LE"], "please raise the table") == []
    assert grounded_terms(["SE"], "the SE trim") == ["SE"]


def test_long_overlap():
    src = "loosen the lug nuts raise the front and support it on jack stands before you remove the lower ball joint nut today"
    assert has_long_overlap("Loosen the lug nuts, raise the front and support it on jack stands before you remove", src)
    assert not has_long_overlap("Lift the truck safely and take off the wheels", src)
    assert not has_long_overlap("too short to flag", src)


def test_ground_fact_alignment_checks_values_not_quotes():
    fact = Fact(
        category="repair", topic="Control arms", title="t", summary="s",
        parts=[Part(name="arm", part_number="54500-EA000", evidence="New arm 54500-EA000"),
               Part(name="bogus", part_number="99999-ZZ999", evidence="part 99999-ZZ999"),
               Part(name="no evidence", part_number="54500-EA000"),
               Part(name="bolt")],
        specs=[Spec(item="pivot bolt", value="83 ft-lb", evidence="Torque the pivot bolts to 83 ft-lb"),
               Spec(item="invented", value="120 ft-lb", evidence="Torque to 120 ft-lb"),
               Spec(item="no evidence", value="83 ft-lb"),
               Spec(item="evidence without the number", value="83 ft-lb", evidence="Torque the pivot bolts")],
    )
    g = ground_fact(fact, TEXT)
    assert g["parts"] == [True, False, True, True]    # the part number is what must be in the source; no part number -> nothing to check
    assert g["specs"] == [True, False, True, True]    # 120 ft-lb is invented; a missing or partial quote no longer matters


def test_unit_must_match_the_source():
    from xw.grounding import unit_grounded
    assert unit_grounded("80", "ft-lb", "torque to 80 ft lbs") and unit_grounded("80-90", "ft-lb", "80 to 90 foot pounds")
    assert not unit_grounded("80", "ft-lb", "torque to 80 in-lbs")                 # 12x error: inch-pounds
    assert not unit_grounded("80", "ft-lb", "torque to 80 Nm")
    assert not unit_grounded("83", "ft-lb", "torque to 83")                        # unit the source never states
    assert unit_grounded("9", "N·m", "9 Nm (80 in-lb)") and not unit_grounded("9", "in-lb", "9 Nm (80 in-lb)")
    assert unit_grounded("83", "", "83 Nm")                                        # no unit claimed, nothing to check
    s = Spec(item="Pivot bolt", value="80", unit="ft-lb", evidence="tighten the pivot bolt to 80 in-lbs")
    assert not spec_value_grounded(s, "Then tighten the pivot bolt to 80 in-lbs and lower it.")


def test_units_attach_only_to_adjacent_numbers():
    from xw.grounding import numbers_grounded, safety_values
    assert safety_values("Remove the 2 sway bar bolts") == set()
    assert safety_values("the 4.0L engine") == set()                               # displacement, not a capacity
    assert safety_values("Use a 16 oz hammer") == set()                            # weight ounces, not fluid
    assert safety_values("6.1 US fl oz of oil, 4 fluid ounces") == {("6.1", "fl oz"), ("4", "fl oz")}
    assert safety_values("2.75 qt (2.6 L), 35psi, ft-lbs: 80") == {("2.75", "qt"), ("2.6", "L"), ("35", "psi"), ("80", "ft-lb")}
    assert numbers_grounded("Remove the 2 bolts", "remove the two bolts") and not numbers_grounded("Use a 21mm socket", "a 19mm socket")


def test_dedupe_keeps_disagreeing_numbers_apart():
    from xw.export import _dedupe
    merged = _dedupe([("Replace the 15 amp fuse under the dash", "t1"), ("Replace the 20 amp fuse under the dash", "t2"),
                      ("Replace the 15 amp fuse under the dash.", "t3")])
    assert merged == [("Replace the 15 amp fuse under the dash", ["t1", "t3"]), ("Replace the 20 amp fuse under the dash", ["t2"])]
