"""
Demo Site Tests
===============
Makes sure the demo sites keep triggering the problems they were built for.

Dependencies:
    - pytest
    - scripts.check_demo_sites
"""



from scripts.check_demo_sites import EXPECTED_RULES, scan_sites


def test_every_planted_problem_is_flagged():
    scans = scan_sites()
    for name, expected in EXPECTED_RULES.items():
        found = {i.rule_id for i in scans[name].issues if i.status == "violation"}
        assert expected <= found, f"{name} is missing {expected - found}"
