import json
from pathlib import Path

CDD_CONFIG_PATH = Path(__file__).resolve().parents[2] / "cdd_configs" / "cdd_configs.json"

_cdd_configs_cache = None

def load_cdd_configs():
    global _cdd_configs_cache
    if _cdd_configs_cache is None:
        with open(CDD_CONFIG_PATH) as f:
            configs = json.load(f)
        _cdd_configs_cache = {c["country"]: c for c in configs}
    return _cdd_configs_cache

def get_cdd_config(country):
    configs = load_cdd_configs()
    if country not in configs:
        raise ValueError(f"No CDD config found for country: {country}")
    return configs[country]

def validate_profile(profile, cdd_config):
    missing = [f for f in cdd_config["required_fields"] if f not in profile or not profile[f]]
    return {"valid": len(missing) == 0, "missing_fields": missing}
