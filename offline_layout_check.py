"""
offline_layout_check.py - check AlfieBot V0.1 layout maths without Fusion.

This does NOT run Fusion and does NOT validate the CAD model. It evaluates the
parameter table in alfiebot_parameters.py and checks the analytic layout:
part envelopes, A1 Mini build volume, parts inside the enclosure cavity,
features on flat wall regions, and FDM wall thicknesses.

Usage:
    python offline_layout_check.py
    python offline_layout_check.py --set body_width="170 mm" --set corner_radius="18 mm"
    python offline_layout_check.py --flex      # also run the FLEX_TESTS edits

Exit code is 1 if any check FAILs.
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import alfiebot_parameters as AP  # noqa: E402


def run(overrides, title, verbose=True):
    v = AP.evaluate(overrides)
    results = AP.design_rule_checks(v)
    if verbose:
        print("=" * 78)
        print(title)
        print("=" * 78)
        print("\nPart envelopes (assembly coordinates, mm):")
        print("  %-22s %-20s %-20s %-20s %s" % ("Component", "X", "Y", "Z", "Size"))
        for name, box in AP.part_envelopes(v).items():
            size = AP.box_size(box)
            print("  %-22s %-20s %-20s %-20s %.1f x %.1f x %.1f" % (
                name, "%.1f..%.1f" % box[0], "%.1f..%.1f" % box[1], "%.1f..%.1f" % box[2], *size))
        env = AP.assembly_envelope(v)
        print("\nOverall envelope: %.1f x %.1f x %.1f mm (X x Y x Z)" % AP.box_size(env))
        print("\nDesign rule checks:")
        for status, name, detail in results:
            print("  [%s] %-50s %s" % (status, name, detail))
    fails = [r for r in results if r[0] == "FAIL"]
    warns = [r for r in results if r[0] == "WARN"]
    print("%s: %d checks, %d FAIL, %d WARN" % (title, len(results), len(fails), len(warns)))
    for r in fails + warns:
        if not verbose:
            print("  [%s] %s: %s" % r)
    return not fails


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", action="append", default=[], metavar="NAME=EXPR",
                    help="Override a parameter expression, e.g. body_width='170 mm'")
    ap.add_argument("--flex", action="store_true", help="Also check each FLEX_TESTS edit")
    args = ap.parse_args()

    overrides = {}
    for item in args.set:
        name, _, expr = item.partition("=")
        if name not in AP.PARAMETER_UNITS:
            ap.error("unknown parameter %r" % name)
        overrides[name] = expr
    ok = run(overrides, "AlfieBot V%s offline layout check" % AP.VERSION)
    if args.flex:
        print()
        for name, expr in AP.FLEX_TESTS:
            ok = run(dict(overrides, **{name: expr}), "Flex %s = %s" % (name, expr), verbose=False) and ok
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
