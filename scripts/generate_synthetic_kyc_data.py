
import json
import random
from pathlib import Path

from faker import Faker
from PIL import Image, ImageDraw, ImageEnhance, ImageFont

SEED = 42
random.seed(SEED)
fake = Faker()
Faker.seed(SEED)

# --- demo size knob ---------------------------------------------------------
NUM_IDENTITIES = 5

ROOT = Path(__file__).resolve().parent.parent
PROFILES_PATH = ROOT / "data" / "synthetic" / "synthetic_profiles.json"
SOURCE_FACES = ROOT / "data" / "synthetic" / "source_faces"
IDS_OUT = ROOT / "data" / "synthetic" / "ids"
SELFIES_OUT = ROOT / "data" / "synthetic" / "selfies"
MANIFEST_OUT = ROOT / "data" / "synthetic" / "manifest.json"

CARD_SIZE = (856, 540)  # ~ID-1 card ratio, upscaled for readable OCR
PHOTO_BOX = (40, 120, 300, 460)  # left, top, right, bottom


def _font(size: int) -> ImageFont.FreeTypeFont:
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def pick_demo_profiles() -> list[dict]:
    profiles = json.loads(PROFILES_PATH.read_text())
    rng = random.Random(SEED)
    return rng.sample(profiles, min(NUM_IDENTITIES, len(profiles)))


def make_id_card(identity: dict, face_path: Path, out_path: Path) -> None:
    card = Image.new("RGB", CARD_SIZE, color=(235, 240, 245))
    draw = ImageDraw.Draw(card)

    draw.rectangle([(0, 0), (CARD_SIZE[0], 70)], fill=(20, 45, 90))
    draw.text((30, 18), "SYNTHETIC NATIONAL ID -- DEMO ONLY", font=_font(28), fill="white")

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
        draw.text((330, y), f"{label}:", font=_font(22), fill=(60, 60, 60))
        draw.text((330, y + 28), value, font=_font(26), fill=(10, 10, 10))
        y += 70

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

    identities = []
    for i, profile in enumerate(demo_profiles):
        face_path = faces[i % len(faces)]  # cycle if fewer faces than identities
        identities.append({
            "identity_id": f"synth_{i:03d}",
            "full_name": profile["full_name"],
            "dob": profile["dob"],
            "id_number": profile["id_number"],
            "country": profile["country"],
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
    print(f"Manifest: {MANIFEST_OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()