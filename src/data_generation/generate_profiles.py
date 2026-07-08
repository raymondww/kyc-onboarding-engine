from faker import Faker
import random
import json
import pandas as pd
from pathlib import Path

output_path = Path("data/synthetic/synthetic_profiles.json")
output_path.parent.mkdir(parents=True, exist_ok=True)  # creates folder if missing

fake = Faker()

COUNTRIES = ["Country A", "Country B"]

def load_sdn_names():
    """Load individual names from the OFAC SDN list."""
    sdn_df = pd.read_csv(
        "data/raw/sdn.csv",
        header=None,
        names=["uid", "name", "entity", "region", "role", "vessel_id",
               "vessel_type", "vessel_length", "vessel_width", "country", "null", "reason"]
    )
    return sdn_df.loc[sdn_df["entity"] == "individual", ["name", "region"]]

def generate_profile(planted_sanctioned_name=None):
    return {
        "full_name": planted_sanctioned_name or fake.name(),
        "dob": fake.date_of_birth(minimum_age=18, maximum_age=80).isoformat(),
        "address": fake.address(),
        "id_number": fake.bothify(text="ID#########"),
        "country": random.choice(COUNTRIES),
        "email": fake.email(),
    }

def generate_sanctioned_profiles(num_profiles=10, seed=42):
    sdn_names = load_sdn_names()
    planted_names = sdn_names["name"].sample(n=num_profiles, random_state=seed).tolist()
    return [generate_profile(planted_sanctioned_name=name) for name in planted_names]


# Generate 90 normal profiles
profiles = [generate_profile() for _ in range(90)]

# Generate 10 profiles with sanctioned names
planted_profiles = generate_sanctioned_profiles(num_profiles=10)

all_profiles = profiles + planted_profiles
random.shuffle(all_profiles)

with open(output_path, "w") as f:
    json.dump(all_profiles, f, indent=2)

print(f"Generated {len(all_profiles)} profiles ({len(planted_profiles)} planted for sanctions demo)")