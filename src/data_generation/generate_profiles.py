from faker import Faker
import random
import json
import pandas as pd
from pathlib import Path
import re

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
    return sdn_df.loc[sdn_df["entity"] == "individual", ["name", "region", "reason"]]

def generate_profile(planted_sanctioned_name=None, date_of_birth=None):
    dob = date_of_birth if date_of_birth else fake.date_of_birth(minimum_age=18, maximum_age=80)
    return {
        "full_name": planted_sanctioned_name or fake.name(),
        "dob": dob.isoformat(),
        "address": fake.address(),
        "id_number": fake.bothify(text="ID#########"),
        "country": random.choice(COUNTRIES),
        "email": fake.email(),
    }

def extract_dob_from_sdn_entry(name, sdn_names):
    """Extract and parse DOB from an SDN entry's 'reason' field, if present."""
    sdn_entry = sdn_names.loc[sdn_names["name"] == name]["reason"].values[0]
    pattern = r'DOB\s+([^;]+)'
    match = re.search(pattern, sdn_entry)

    if not match:
        return fake.date_of_birth(minimum_age=18, maximum_age=80)

    dob_str = match.group(1).strip()
    try:
        dob = pd.to_datetime(dob_str, errors='coerce')
        if pd.isnull(dob):
            print(f"Warning: Could not parse DOB '{dob_str}' for {name}. Using random DOB.")
            return fake.date_of_birth(minimum_age=18, maximum_age=80)
        return dob.date()
    except Exception as e:
        print(f"Error parsing DOB for {name}: {e}. Using random DOB.")
        return fake.date_of_birth(minimum_age=18, maximum_age=80)
    
def generate_sanctioned_profiles(num_profiles=10, seed=42):
    sdn_names = load_sdn_names()
    planted_names = sdn_names["name"].sample(n=num_profiles, random_state=seed).tolist()

    profiles = []
    for name in planted_names:
        dob = extract_dob_from_sdn_entry(name, sdn_names)
        profiles.append(generate_profile(planted_sanctioned_name=name, date_of_birth=dob))

    return profiles


# Generate 90 normal profiles
profiles = [generate_profile() for _ in range(90)]

# Generate 10 profiles with sanctioned names
planted_profiles = generate_sanctioned_profiles(num_profiles=10)

all_profiles = profiles + planted_profiles
random.shuffle(all_profiles)

with open(output_path, "w") as f:
    json.dump(all_profiles, f, indent=2)

print(f"Generated {len(all_profiles)} profiles ({len(planted_profiles)} planted for sanctions demo)")