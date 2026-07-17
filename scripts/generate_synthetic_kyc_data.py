import json
import random
from pathlib import Path

from faker import Faker
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

SEED = 42
random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

ROOT = Path(__file__).resolve().parent.parent
PROFILES_PATH = ROOT / "data" / "synthetic" / "synthetic_profiles.json"
SOURCE_FACES = ROOT / "data" / "synthetic" / "source_faces"
IDS_OUT = ROOT / "data" / "synthetic" / "ids"
SELFIES_OUT = ROOT / "data" / "synthetic" / "selfies"
MANIFEST_OUT = ROOT / "data" / "synthetic" / "manifest.json"

CARD_SIZE = (856, 540)  # ~ID-1 card ratio, upscaled for readable OCR
PHOTO_BOX = (40, 120, 300, 460)  # left, top, right, bottom

FONT_PATH = ROOT / "assets" / "fonts" / "DejaVuSans-Bold.ttf"


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype(str(FONT_PATH), size)
    except OSError:
        try:
            return ImageFont.load_default(size=size)
        except TypeError:
            return ImageFont.load_default()  # very old Pillow -- ignores size


def pick_demo_profiles() -> list[dict]:
    """Deliberately curated selection, not a random sample -- picks one
    profile from each (country, is_sanctioned) combination so the demo set
    shows variety on both axes, plus one fully random profile as a wildcard.
    Uses id_number to track "already picked" since profile dicts aren't
    hashable and full_name alone isn't guaranteed unique."""
    profiles = json.loads(PROFILES_PATH.read_text())
    rng = random.Random(SEED)

    chosen = []
    chosen_ids = set()

    def pick_from(pool, label):
        available = [p for p in pool if p["id_number"] not in chosen_ids]
        if not available:
            print(f"WARNING: no profile available for {label} -- skipping.")
            return
        pick = rng.choice(available)
        chosen.append(pick)
        chosen_ids.add(pick["id_number"])

    for country in ("Country A", "Country B"):
        for is_sanctioned in (True, False):
            pool = [p for p in profiles if p["country"] == country and p["is_sanctioned"] == is_sanctioned]
            label = f"{'sanctioned' if is_sanctioned else 'normal'} + {country}"
            pick_from(pool, label)

    wildcard_pool = [
        p for p in profiles
        if p["country"] == "Country A" and not p["is_sanctioned"] and p["id_number"] not in chosen_ids
    ]
    pick_from(wildcard_pool, "wildcard (Country A, non-sanctioned, guaranteed pass)")

    return chosen


def make_id_card(identity: dict, face_path: Path, out_path: Path) -> None:
    card = Image.new("RGB", CARD_SIZE, color=(235, 240, 245))
    draw = ImageDraw.Draw(card)

    draw.rectangle([(0, 0), (CARD_SIZE[0], 70)], fill=(20, 45, 90))
    # 34 is the biggest size this exact title fits at in DejaVuSans-Bold
    # without running off the 856px-wide card
    draw.text((30, 14), "SYNTHETIC NATIONAL ID -- DEMO ONLY", font=_font(28), fill="white")

    face = Image.open(face_path).convert("RGB")
    box_w, box_h = PHOTO_BOX[2] - PHOTO_BOX[0], PHOTO_BOX[3] - PHOTO_BOX[1]
    face = face.resize((box_w, box_h))
    card.paste(face, (PHOTO_BOX[0], PHOTO_BOX[1]))
    draw.rectangle(PHOTO_BOX, outline=(20, 45, 90), width=3)

    # Field values come from synthetic_profiles.json, except "Expiry" which
    # isn't part of that schema (document-only attribute) -- Faker-generated,
    # deterministic per identity_id so re-runs are stable.
    fields = [
        ("Name", identity["full_name"]),
        ("DOB", identity["dob"]),
        ("ID No", identity["id_number"]),
        ("Nationality", identity["country"]),
        ("Expiry", identity["expiry"]),
    ]
    y = 130
    for label, value in fields:
        draw.text((330, y), f"{label}:", font=_font(24), fill=(60, 60, 60))
        draw.text((330, y + 30), value, font=_font(26), fill=(10, 10, 10))
        y += 78

    card.save(out_path)


def make_match_selfie(face_path: Path, out_path: Path, rng: random.Random) -> None:
    img = Image.open(face_path).convert("RGB")
    img = ImageEnhance.Brightness(img).enhance(rng.uniform(0.85, 1.15))
    img = ImageEnhance.Contrast(img).enhance(rng.uniform(0.9, 1.1))
    img = img.rotate(rng.uniform(-4, 4), expand=False, fillcolor=(255, 255, 255))
    img.save(out_path)


def main():
    IDS_OUT.mkdir(parents=True, exist_ok=True)
    SELFIES_OUT.mkdir(parents=True, exist_ok=True)
    SOURCE_FACES.mkdir(parents=True, exist_ok=True)

    if not PROFILES_PATH.exists():
        print(f"Missing {PROFILES_PATH}. Run src/data_generation/generate_profiles.py first.")
        return

    faces = sorted([p for p in SOURCE_FACES.glob("*") if p.suffix.lower() in (".jpg", ".jpeg", ".png")])
    if len(faces) < 1:
        print(f"Need at least 1 face photo in {SOURCE_FACES}. See docstring for where to get some.")
        return

    demo_profiles = pick_demo_profiles()
    rng = random.Random(SEED)

    # If you've dropped your own photo into source_faces/, pin it to the
    # wildcard slot (always the last entry in demo_profiles -- see
    # pick_demo_profiles(), which now forces that slot to Country A +
    # non-sanctioned) instead of letting it land on whatever slot
    # alphabetical file ordering happens to cycle it to. Detected as
    # "anything not named like the generic placeholder faces" -- adjust
    # this filter if your placeholder photos use a different naming scheme.
    personal_photos = [f for f in faces if not f.stem.lower().startswith("random-person")]
    personal_photo = personal_photos[0] if personal_photos else None
    other_faces = [f for f in faces if f != personal_photo] if personal_photo else faces
    if personal_photo:
        print(f"Pinning {personal_photo.name} to the wildcard (Country A, guaranteed-pass) identity.")

    identities = []
    for i, profile in enumerate(demo_profiles):
        is_wildcard_slot = i == len(demo_profiles) - 1
        if is_wildcard_slot and personal_photo is not None:
            face_path = personal_photo
        elif other_faces:
            face_path = other_faces[i % len(other_faces)]  # cycle if fewer faces than identities
        else:
            face_path = faces[i % len(faces)]  # only personal photo available -- reuse it everywhere
        identities.append({
            "identity_id": f"synth_{i:03d}",
            "full_name": profile["full_name"],
            "dob": profile["dob"],
            "id_number": profile["id_number"],
            "country": profile["country"],
            "is_sanctioned": profile["is_sanctioned"],  # carried through for demo visibility only -- the eKYC pipeline itself still ignores this
            "expiry": fake.date_between(start_date="+1y", end_date="+8y").strftime("%Y-%m-%d"),
            "source_face": str(face_path.relative_to(ROOT)),
        })

    manifest = []
    for i, identity in enumerate(identities):
        face_path = ROOT / identity["source_face"]

        id_path = IDS_OUT / f"{identity['identity_id']}.png"
        make_id_card(identity, face_path, id_path)

        # MATCH case
        match_path = SELFIES_OUT / f"{identity['identity_id']}.png"
        make_match_selfie(face_path, match_path, rng)
        manifest.append({
            **identity,
            "id_image": str(id_path.relative_to(ROOT)),
            "selfie_image": str(match_path.relative_to(ROOT)),
            "expected_face_match": True,
            "case_type": "match",
        })

        # MISMATCH case: next identity's face as the "selfie" (fraud sim)
        swap_identity = identities[(i + 1) % len(identities)]
        swap_face_path = ROOT / swap_identity["source_face"]
        swap_path = SELFIES_OUT / f"{identity['identity_id']}_swap.png"
        make_match_selfie(swap_face_path, swap_path, rng)
        manifest.append({
            **identity,
            "id_image": str(id_path.relative_to(ROOT)),
            "selfie_image": str(swap_path.relative_to(ROOT)),
            "expected_face_match": False,
            "case_type": "mismatch",
        })

    MANIFEST_OUT.write_text(json.dumps(manifest, indent=2))
    print(f"Generated {len(identities)} identities -> {len(manifest)} test pairs.")
    for identity in identities:
        tag = "SANCTIONED" if identity["is_sanctioned"] else "normal"
        print(f"  {identity['identity_id']}: {identity['full_name']} ({identity['country']}, {tag})")
    print(f"Manifest: {MANIFEST_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()