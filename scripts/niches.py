"""Niche helpers shared by finder + generator.
Strategy: start with 3 strong niches (config active_niches), every `rollout_days` the bot auto-adds the next one from `queue`."""
import datetime

def today():
    return datetime.date.today()

def active_niches(cfg, on=None):
    on = on or today()
    act = list(cfg["active_niches"])
    start = datetime.date.fromisoformat(cfg["rollout_start"])
    for i, k in enumerate(cfg.get("queue", [])):
        if on >= start + datetime.timedelta(days=cfg["rollout_days"] * (i + 1)) and k not in act:
            act.append(k)
    return act

def next_niche(cfg, on=None):
    """-> (niche_key, date) of the next auto-activation, or (None, None)."""
    on = on or today()
    start = datetime.date.fromisoformat(cfg["rollout_start"])
    for i, k in enumerate(cfg.get("queue", [])):
        d = start + datetime.timedelta(days=cfg["rollout_days"] * (i + 1))
        if d > on:
            return k, d
    return None, None

def sub_labels(cfg):
    """{(osm_key, osm_value): (niche, label)}"""
    out = {}
    for nk, n in cfg["niches"].items():
        for key, vals in n["tags"].items():
            for v, label in vals.items():
                out[(key, v)] = (nk, label)
    return out

def classify(tags, cfg):
    sl = sub_labels(cfg)
    for key in ("shop", "amenity", "leisure", "craft"):
        v = tags.get(key)
        if (key, v) in sl:
            return sl[(key, v)]
    return None, None

LEGACY = {"Salon": "salon", "Beauty Studio": "salon", "Barber Shop": "salon", "Dental Clinic": "clinic", "Clinic": "clinic",
          "Restaurant": "restaurant", "Cafe": "restaurant", "Gym": "gym", "Auto Repair": "garage", "Bakery": "bakery"}

def overpass_tags(cfg, keys):
    """-> {osm_key: [values]} for the given niches."""
    out = {}
    for nk in keys:
        for key, vals in cfg["niches"][nk]["tags"].items():
            out.setdefault(key, [])
            out[key] += [v for v in vals if v not in out[key]]
    return out
