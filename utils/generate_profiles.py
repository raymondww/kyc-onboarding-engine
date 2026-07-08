from faker import Faker
import random
import json

fake = Faker()

COUNTRIES = ["Country A", "Country B"]

def generate_profile(planted_sanctioned_name=None):
    profile = {
        "full_name": planted_sanctioned_name or fake.name(),
        "dob": fake.date_of_birth(minimum_age=18, maximum_age=80).isoformat(),
        "address": fake.address(),
        "id_number": fake.bothify(text="ID#########"),
        "country": random.choice(COUNTRIES),
        "email": fake.email(),
    }
    return profile
