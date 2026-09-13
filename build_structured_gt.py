# script to help build structured ground truth (gt) file 
# note: script assisted by AI

import json
from pathlib import Path

# ---------- CONFIG ----------

INPUT_CLEANED_JSON = "ocr/results_val_cleaned.json"   # or results_test_cleaned.json
OUTPUT_GT_JSON     = "ocr/structured_val_gt.json"     # your ground-truth file

def ask_yes_no(msg):
    while True:
        s = input(f"{msg} [y/n]: ").strip().lower()
        if s in {"y", "yes"}:
            return True
        if s in {"n", "no"}:
            return False
        print("Please enter y or n.")


def ask_optional(msg):
    s = input(f"{msg} (blank = None): ").strip()
    return s or None


def ask_time(msg):
    """
    Ask for time in HH:MM 24h format. Empty -> None.
    """
    while True:
        s = input(f"{msg} (HH:MM 24h, blank = None): ").strip()
        if not s:
            return None
        if ":" in s:
            h, m = s.split(":", 1)
            if h.isdigit() and m.isdigit():
                h, m = int(h), int(m)
                if 0 <= h <= 23 and 0 <= m <= 59:
                    return f"{h:02d}:{m:02d}"
        print("Invalid time. Please enter e.g. 08:30, 18:00.")


def ask_days(msg):
    """
    Prompt for days (e.g. 'MON-FRI' or 'MON,TUE' or 'MON-SUN')
    Automatically expands ranges like MON-FRI -> ['MON','TUE','WED','THU','FRI'].
    """
    DAYS_ORDER = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
    s = input(f"{msg} (e.g. MON-FRI or MON,TUE; blank = none): ").strip().upper()
    if not s:
        return []

    parts = [p.strip() for p in s.split(",") if p.strip()]
    expanded = []

    for p in parts:
        if "-" in p:
            start, end = [x.strip() for x in p.split("-", 1)]
            if start in DAYS_ORDER and end in DAYS_ORDER:
                i1, i2 = DAYS_ORDER.index(start), DAYS_ORDER.index(end)
                if i1 <= i2:
                    expanded.extend(DAYS_ORDER[i1:i2+1])
                else:
                    # handle wraparound like FRI-MON
                    expanded.extend(DAYS_ORDER[i1:] + DAYS_ORDER[:i2+1])
            else:
                expanded.append(p)
        else:
            expanded.append(p)

    # dedupe while preserving order
    deduped = []
    for d in expanded:
        if d not in deduped:
            deduped.append(d)
    return deduped


def ask_payment_type():
    """
    Ask for payment_type with default FREE.
    Allowed: FREE, TICKET, METER.
    """
    allowed = {"FREE", "TICKET", "METER", ""}
    while True:
        s = input("  payment_type [FREE/TICKET/METER] (blank = FREE): ").strip().upper()
        if s == "":
            return "FREE"
        if s in allowed:
            return s
        print("  Please enter FREE, TICKET, METER or leave blank for FREE.")


def annotate_rules_for_sign(sign_idx):
    rules = []
    while True:
        try:
            n = int(input(f"  How many rules in sign {sign_idx}? (0,1,2,...): ").strip())
            if n < 0:
                raise ValueError
            break
        except ValueError:
            print("  Enter a non-negative integer.")

    for r in range(1, n + 1):
        print(f"  -- Rule {r} --")
        time_limit = ask_optional("  time_limit (e.g. 1P, 2P, 30MIN; blank if none)")
        days = ask_days("  days list")
        time_start = ask_time("  time_start")
        time_end = ask_time("  time_end")
        payment_type = ask_payment_type()
        rule_notes = ask_optional("  notes for this rule (e.g. PUBLIC HOLIDAYS, SCHOOL DAYS; blank = None)")

        rules.append({
            "rule_id": r,
            "time_limit": time_limit,
            "days": days,
            "time_start": time_start,
            "time_end": time_end,
            "payment_type": payment_type,
            "notes": rule_notes
        })
    return rules


def annotate_signs_for_image(image_name, clean_text):
    print("\n" + "=" * 80)
    print(f"Image: {image_name}")
    print(f"Clean text: {clean_text}")
    print("=" * 80)

    while True:
        try:
            n = int(input("How many signs in this crop? (0,1,2,...): ").strip())
            if n < 0:
                raise ValueError
            break
        except ValueError:
            print("Enter a non-negative integer.")

    signs = []
    for i in range(1, n + 1):
        print(f"\n--- Sign {i} ---")
        sign_type = ask_optional("sign_type (e.g. RESTRICTION)")
        restriction_type = ask_optional("restriction_sign_type (e.g. TIME, BUS ZONE, LOADING ZONE, MAIL ZONE, NO STOPPING)")
        permit_zone = ask_optional("permit_zone (e.g. AREA G)")
        sign_notes = ask_optional("sign-level notes (applies to whole sign; blank = None)")
        rules = annotate_rules_for_sign(i)

        signs.append({
            "sign_id": i,
            "sign_type": sign_type,
            "restriction_sign_type": restriction_type,
            "permit_zone": permit_zone,
            "notes": sign_notes,  # still available if you ever need global notes
            "rules": rules
        })

    return signs


def main():
    input_path = Path(INPUT_CLEANED_JSON)
    if not input_path.exists():
        print(f"Input file not found: {input_path}")
        return

    cleaned = json.loads(input_path.read_text(encoding="utf-8"))

    out_path = Path(OUTPUT_GT_JSON)
    if out_path.exists():
        gt = json.loads(out_path.read_text(encoding="utf-8"))
        print(f"Loaded existing GT: {out_path}")
    else:
        gt = {}
        print(f"Starting new GT: {out_path}")

    image_names = sorted(cleaned.keys())
    print(f"\nThere are {len(image_names)} crops in {INPUT_CLEANED_JSON}.\n")

    for name in image_names:
        clean_text = (
            cleaned[name].get("clean_text")
            or cleaned[name].get("normalized_text")
            or ""
        )

        if name in gt and gt[name].get("signs"):
            print(f"\n{name} already has GT signs.")
            if not ask_yes_no("Re-annotate / overwrite this image?"):
                continue

        if not ask_yes_no(f"\nAnnotate image {name}?"):
            continue

        signs = annotate_signs_for_image(name, clean_text)
        gt[name] = {"clean_text": clean_text, "signs": signs}

        out_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Saved {name}.")

    print(f"\nDone. Ground-truth saved to: {out_path}")

if __name__ == "__main__":
    main()
    # to run: python build_structured_gt.py