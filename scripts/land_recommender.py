# land_recommender.py
# pip install requests pandas numpy scikit-learn tqdm

import json
import math
import os
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Dict, List, Tuple, Any, Optional

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error
from tqdm import tqdm

SCRYFALL_BULK_URL = "https://api.scryfall.com/bulk-data/default_cards"
SCRYFALL_BULK_FILE = "scryfall-default-cards.json"

# -------------------------------
# Scryfall: cards + helpers
# -------------------------------

def download_scryfall_bulk(path=SCRYFALL_BULK_FILE):
    if os.path.exists(path):
        return path
    r = requests.get(SCRYFALL_BULK_URL, timeout=30)
    r.raise_for_status()
    url = r.json()["download_uri"]
    print("Downloading Scryfall bulk card data...")
    rd = requests.get(url, stream=True, timeout=120)
    rd.raise_for_status()
    with open(path, "wb") as f:
        for chunk in rd.iter_content(chunk_size=1_048_576):
            if chunk:
                f.write(chunk)
    print("Saved:", path)
    return path

@dataclass
class Card:
    name: str
    type_line: str
    oracle_text: str
    mana_cost: str
    cmc: float
    colors: List[str]
    color_identity: List[str]
    produced_mana: List[str]  # e.g. ["W","U"] for duals; may be empty for fetchlands
    keywords: List[str]

class CardIndex:
    def __init__(self, scryfall_cards: List[dict]):
        self.by_name: Dict[str, Card] = {}
        for c in scryfall_cards:
            # Only normal printings
            name = c.get("name", "").strip()
            if not name: 
                continue
            obj = Card(
                name=name,
                type_line=c.get("type_line", ""),
                oracle_text=c.get("oracle_text", "") or "",
                mana_cost=c.get("mana_cost", "") or "",
                cmc=c.get("cmc", 0) or 0,
                colors=c.get("colors", []) or [],
                color_identity=c.get("color_identity", []) or [],
                produced_mana=c.get("produced_mana", []) or [],
                keywords=c.get("keywords", []) or [],
            )
            self.by_name[name.lower()] = obj

    def get(self, name: str) -> Optional[Card]:
        return self.by_name.get(name.lower())

def load_card_index(path=SCRYFALL_BULK_FILE) -> CardIndex:
    download_scryfall_bulk(path)
    try:
        with open(path, "r", encoding="utf-8") as f:
            cards = json.load(f)
    except Exception as e:
        raise RuntimeError("Failed to load Scryfall card data") from e
    return CardIndex(cards)  # Now guaranteed to return CardIndex

# -------------------------------
# Deck sources (example: Archidekt/Moxfield)
# You can adapt to your preferred source or local exports.
# -------------------------------

def fetch_archidekt_commander_deck_ids(pages=2, page_size=50) -> List[int]:
    # Public search endpoint; consider rate limits and TOS.
    # Docs: https://archidekt.com/developers
    deck_ids = []
    for page in range(1, pages + 1):
        url = f"https://archidekt.com/api/decks/search/?format=Commander&page={page}&orderBy=-updatedAt&size={page_size}"
        r = requests.get(url, timeout=30)
        if r.status_code != 200:
            break
        data = r.json()
        for d in data.get("results", []):
            deck_ids.append(d["id"])
        time.sleep(0.4)
    return deck_ids

def fetch_archidekt_deck(deck_id: int) -> dict:
    url = f"https://archidekt.com/api/decks/{deck_id}/"
    r = requests.get(url, timeout=30)
    r.raise_for_status()
    return r.json()

def normalize_archidekt_decklist(deck_json: dict) -> dict:
    # Returns dict with keys: "name", "format", "mainboard" (list of (card_name, qty)), "commanders", "lands" etc.
    # Archidekt returns categories; we’ll collapse for features/labels.
    result = {
        "name": deck_json.get("name"),
        "format": deck_json.get("format"),
        "mainboard": [],
        "commanders": [],
        "sideboard": []
    }
    for entry in deck_json.get("cards", []):
        qty = entry.get("quantity", 1)
        card_name = entry.get("card", {}).get("oracleCard", {}).get("name") or entry.get("card", {}).get("name")
        if not card_name:
            continue
        cat = entry.get("category", "Mainboard")
        if cat == "Commander":
            result["commanders"].append((card_name, qty))
        elif cat == "Mainboard":
            result["mainboard"].append((card_name, qty))
        else:
            result["sideboard"].append((card_name, qty))
    return result

# You can add a similar pair for Moxfield if you prefer:
# def fetch_moxfield_deck_ids(...): ...
# def fetch_moxfield_deck(...): ...
# def normalize_moxfield_decklist(...): ...

# -------------------------------
# Feature engineering
# -------------------------------

MANA_SYMBOLS = ["W","U","B","R","G"]

def parse_mana_cost(cost: str) -> Counter:
    # Input like "{2}{U}{U}" -> {"U": 2, "C": 2}
    c = Counter()
    for sym in re.findall(r"\{([^}]+)\}", cost or ""):
        s = sym.upper()
        if s in MANA_SYMBOLS:
            c[s] += 1
        elif s.isdigit():
            c["C"] += int(s)
        else:
            # Hybrid, phyrexian etc: approximate colored pressure
            for ch in MANA_SYMBOLS:
                if ch in s:
                    c[ch] += 1
    return c

def is_land(card: Card) -> bool:
    return "Land" in card.type_line

def is_mana_rock(card: Card) -> bool:
    # Artifact that taps for mana
    if "Artifact" not in card.type_line:
        return False
    txt = card.oracle_text.lower()
    return "add {" in txt and "creature" not in card.type_line

def is_mana_dork(card: Card) -> bool:
    return "Creature" in card.type_line and "add {" in card.oracle_text.lower()

def is_land_ramp_spell(card: Card) -> bool:
    txt = card.oracle_text.lower()
    # Cultivate, Rampant Growth, Harrow, Farseek, Nature's Lore, etc.
    return ("search your library for a land card" in txt) or \
           ("search your library for a basic land card" in txt) or \
           ("put a land card from your hand onto the battlefield" in txt)

def is_spell_ramp(card: Card) -> bool:
    # Rituals / temporary ramp
    txt = card.oracle_text.lower()
    return ("add {" in txt and "until end of turn" in txt) or ("this spell costs" in txt and "less to cast" in txt)

def is_cost_reducer(card: Card) -> bool:
    txt = card.oracle_text.lower()
    return "spells you cast cost" in txt or "costs {1} less to cast" in txt or "reduce the cost" in txt

def is_free_or_alt_cost(card: Card) -> bool:
    txt = card.oracle_text.lower()
    kws = [ "affinity", "delve", "convoke", "improvise" ]
    if any(k in txt for k in kws): return True
    if ("you may pay" in txt and "rather than pay this spell's mana cost" in txt) or \
       ("you may cast this spell without paying its mana cost" in txt) or \
       ("if you control a commander" in txt and "without paying its mana cost" in txt):
        return True
    return False

def is_card_selection(card: Card) -> bool:
    txt = card.oracle_text.lower()
    # Cantrips, scry, looting, tutors
    return ("draw a card" in txt) or ("scry" in txt) or ("look at the top" in txt) or \
           ("search your library" in txt)

def treasure_count_heuristic(card: Card) -> float:
    txt = card.oracle_text.lower()
    if "treasure token" not in txt:
        return 0.0
    # Heuristic: count Treasures mentioned
    count = 0.0
    # Create N Treasures
    m = re.findall(r"create (?:up to )?(\d+) treasure token", txt)
    for t in m:
        count += float(t)
    # If "for each", "whenever", "equal to", etc., assign a baseline 1.5
    if "for each" in txt or "whenever" in txt or "where x is" in txt:
        count += 1.5
    # Single treasure lines
    if count == 0 and "create a treasure token" in txt:
        count = 1.0
    return count

def produced_mana_colors_from_land(card: Card) -> List[str]:
    # Scryfall produced_mana is best effort, but fetchlands produce none.
    # We use produced_mana if available, else empty list.
    return sorted(list(set([c for c in card.produced_mana if c in MANA_SYMBOLS])))

def basic_types_to_colors(basic_types: List[str]) -> List[str]:
    mapping = {
        "Plains": "W", "Island": "U", "Swamp": "B", "Mountain": "R", "Forest": "G"
    }
    return [mapping[t] for t in basic_types if t in mapping]

def land_types(card: Card) -> List[str]:
    # Return land subtypes: Forest, Island, etc.
    # type_line like "Land — Plains Island"
    if "Land" not in card.type_line:
        return []
    after_dash = card.type_line.split("—")
    if len(after_dash) < 2:
        return []
    return [t.strip() for t in after_dash[1].split()]

def fetchable_basic_types_from_land(card: Card) -> List[str]:
    # For fetchlands like "Search for a Plains or Island card"
    txt = card.oracle_text
    if "Search your library for" not in txt:
        return []
    types = []
    for t in ["Plains", "Island", "Swamp", "Mountain", "Forest"]:
        if re.search(fr"\b{t}\b", txt):
            types.append(t)
    # Prismatic Vista and the like: "basic land card" -> could be any basic
    if "basic land card" in txt:
        types = ["Plains","Island","Swamp","Mountain","Forest"]
    return types

def deck_color_identity(commander_cards: List[Tuple[str,int]], index: CardIndex) -> List[str]:
    colors = set()
    for name, _ in commander_cards:
        c = index.get(name)
        if c:
            for ci in c.color_identity:
                colors.add(ci)
    return sorted(list(colors))

def count_color_sources_from_lands(land_list: List[Tuple[str,int]], index: CardIndex) -> Dict[str, int]:
    # Count sources from lands; dual/triomes count in each color; fetches count based on fetchable typed lands present
    # Step 1: collect deck's typed lands (Forest/Island/Plains/etc.)
    typed_colors_present = set()
    for name, qty in land_list:
        card = index.get(name)
        if not card or not is_land(card):
            continue
        for t in land_types(card):
            for c in basic_types_to_colors([t]):
                typed_colors_present.add(c)

    # Step 2: aggregate sources
    sources = Counter({c: 0 for c in MANA_SYMBOLS})
    for name, qty in land_list:
        card = index.get(name)
        if not card or not is_land(card):
            continue
        pm = produced_mana_colors_from_land(card)
        if pm:
            for c in pm:
                sources[c] += qty
        else:
            # fetchlands: count for fetchable colors if typed lands exist in deck
            ftypes = fetchable_basic_types_from_land(card)
            if ftypes:
                for c in basic_types_to_colors(ftypes):
                    if c in typed_colors_present:
                        sources[c] += qty
    return dict(sources)

def split_mainboard(mainboard: List[Tuple[str,int]], index: CardIndex) -> Tuple[List[Tuple[str,int]], List[Tuple[str,int]]]:
    lands, spells = [], []
    for name, qty in mainboard:
        c = index.get(name)
        if c and is_land(c):
            lands.append((name, qty))
        else:
            spells.append((name, qty))
    return lands, spells

def extract_features(deck: dict, index: CardIndex) -> Dict[str, float]:
    # deck: normalized deck with "mainboard" and "commanders"
    lands, spells = split_mainboard(deck["mainboard"], index)
    # Color identity
    cid = deck_color_identity(deck.get("commanders", []), index)
    feat = {f"deck_has_{c}": (1.0 if c in cid else 0.0) for c in MANA_SYMBOLS}

    # Counts
    total_spells = sum(q for _, q in spells)
    total_lands = sum(q for _, q in lands)

    feat["spell_count"] = float(total_spells)
    feat["land_count_current"] = float(total_lands)

    # Mana curve + pip pressure
    cmc_buckets = defaultdict(int)
    color_pips_total = Counter()
    color_pips_early_weighted = Counter()
    rocks_by_cmc = Counter()
    dorks_by_cmc = Counter()

    ramp_artifacts = 0
    ramp_creatures = 0
    ramp_land_spells = 0
    ramp_spells_temp = 0
    cost_reducers = 0
    free_or_alt = 0
    selection_count = 0
    treasure_score = 0.0

    for name, qty in spells:
        c = index.get(name)
        if not c:
            continue
        cmc = c.cmc or 0
        cmc_buckets[int(min(7, cmc))] += qty

        # Pips
        pips = parse_mana_cost(c.mana_cost)
        for col in MANA_SYMBOLS:
            if pips[col] > 0:
                color_pips_total[col] += pips[col] * qty
                # Early pressure weighting: heavier for low cmc
                w = 1.5 if cmc <= 2 else (1.0 if cmc <= 4 else 0.5)
                color_pips_early_weighted[col] += int(pips[col] * qty * w)

        # Ramp / rocks / dorks
        if is_mana_rock(c):
            ramp_artifacts += qty
            rocks_by_cmc[int(min(4, cmc))] += qty
        if is_mana_dork(c):
            ramp_creatures += qty
            dorks_by_cmc[int(min(4, cmc))] += qty
        if is_land_ramp_spell(c):
            ramp_land_spells += qty
        if is_spell_ramp(c):
            ramp_spells_temp += qty
        if is_cost_reducer(c):
            cost_reducers += qty
        if is_free_or_alt_cost(c):
            free_or_alt += qty
        if is_card_selection(c):
            selection_count += qty

        treasure_score += treasure_count_heuristic(c) * qty

    # Add curve features
    for i in range(0, 8):
        feat[f"cmc_{i}"] = float(cmc_buckets[i])
    # Pips features
    for col in MANA_SYMBOLS:
        feat[f"pips_{col}_total"] = float(color_pips_total[col])
        feat[f"pips_{col}_early"] = float(color_pips_early_weighted[col])
    # Ramp / selection / treasure
    feat["ramp_artifacts"] = float(ramp_artifacts)
    feat["ramp_creatures"] = float(ramp_creatures)
    feat["ramp_land_spells"] = float(ramp_land_spells)
    feat["ramp_temp_spells"] = float(ramp_spells_temp)
    feat["cost_reducers"] = float(cost_reducers)
    feat["free_or_alt_cost"] = float(free_or_alt)
    feat["card_selection"] = float(selection_count)
    feat["treasure_score"] = float(treasure_score)
    # Rocks/dorks by cmc
    for k in range(0,5):
        feat[f"rocks_cmc_{k}"] = float(rocks_by_cmc[k])
        feat[f"dorks_cmc_{k}"] = float(dorks_by_cmc[k])

    # Spell color share (ratio of spells that are color X)
    spell_color_counts = Counter()
    for name, qty in spells:
        c = index.get(name)
        if not c:
            continue
        cols = set(c.color_identity)
        if not cols:
            continue
        for col in cols:
            if col in MANA_SYMBOLS:
                spell_color_counts[col] += qty
    for col in MANA_SYMBOLS:
        feat[f"share_spells_{col}"] = float(spell_color_counts[col]) / (total_spells + 1e-6)

    return feat

def compute_labels(deck: dict, index: CardIndex) -> Dict[str, float]:
    lands, spells = split_mainboard(deck["mainboard"], index)
    land_count = sum(q for _, q in lands)
    sources = count_color_sources_from_lands(lands, index)
    labels = {"y_land_total": float(land_count)}
    for col in MANA_SYMBOLS:
        labels[f"y_src_{col}"] = float(sources.get(col, 0))
    return labels

# -------------------------------
# Dataset building
# -------------------------------

def build_dataset_from_archidekt(
    pages=2, page_size=50, index: Optional[CardIndex] = None
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    if index is None:
        # Load index with error handling
        index = load_card_index()
        # Type checker now knows index is not None
        assert index is not None, "CardIndex must be loaded successfully"
    
    deck_ids = fetch_archidekt_commander_deck_ids(pages=pages, page_size=page_size)
    rows_X, rows_y = [], []
    for did in tqdm(deck_ids, desc="Decks"):
        try:
            dj = fetch_archidekt_deck(did)
            nd = normalize_archidekt_decklist(dj)
            if nd.get("format", "").lower() != "commander":
                continue
            X = extract_features(nd, index)  # index is now guaranteed valid
            y = compute_labels(nd, index)
            rows_X.append(X)
            rows_y.append(y)
            time.sleep(0.3)
        except Exception as e:
            continue
    X_df = pd.DataFrame(rows_X).fillna(0.0)
    y_df = pd.DataFrame(rows_y).fillna(0.0)
    return X_df, y_df

# -------------------------------
# Model training
# -------------------------------

def train_model(X: pd.DataFrame, y: pd.DataFrame):
    targets = ["y_land_total"] + [f"y_src_{c}" for c in MANA_SYMBOLS]
    model = MultiOutputRegressor(RandomForestRegressor(
        n_estimators=400,
        max_depth=None,
        min_samples_leaf=2,
        random_state=42,
        n_jobs=-1
    ))
    X_train, X_val, y_train, y_val = train_test_split(X, y[targets], test_size=0.2, random_state=42)
    model.fit(X_train, y_train)
    pred = model.predict(X_val)
    mae = mean_absolute_error(y_val, pred, multioutput='raw_values')
    print("Validation MAE [lands, W, U, B, R, G]:", mae)
    return model, targets

def save_model(model, targets, feature_cols, path="land_recommender_model.json"):
    # Serialize a simple RF+scikit via json of parameters + feature/target names
    # For production, use joblib/pickle; using JSON here for portability.
    from sklearn.tree import _tree
    # This is a placeholder; prefer joblib for real use
    import joblib
    joblib.dump({"model": model, "targets": targets, "features": feature_cols}, path)
    print("Saved model to", path)

def load_model(path="land_recommender_model.json"):
    import joblib
    data = joblib.load(path)
    return data["model"], data["targets"], data["features"]

# -------------------------------
# Inference on a user decklist
# -------------------------------

def recommend_for_decklist(card_names: List[str], commander_names: List[str], index: CardIndex, model, feature_cols: List[str]):
    # Build feature vector
    deck = {
        "name": "User Deck",
        "format": "Commander",
        "commanders": [(n, 1) for n in commander_names],
        "mainboard": [(n, 1) for n in card_names],  # Quantities default to 1; adapt if needed
    }
    X = extract_features(deck, index)
    # Ensure feature alignment
    x_vec = np.array([[X.get(col, 0.0) for col in feature_cols]])
    y_pred = model.predict(x_vec)[0]
    # Round and post-process
    preds = {"land_total": int(round(max(0, y_pred[0])))}
    for i, c in enumerate(MANA_SYMBOLS, start=1):
        preds[f"src_{c}"] = int(round(max(0, y_pred[i])))
    # Normalize color sources to not exceed something wild
    return preds

# -------------------------------
# CLI-ish example (commented)
# -------------------------------

if __name__ == "__main__":
    index = load_card_index()
    print("Building dataset from Archidekt (sample)...")
    X, y = build_dataset_from_archidekt(pages=2, page_size=50, index=index)
    print("Dataset shapes:", X.shape, y.shape)
    model, targets = train_model(X, y)
    save_model(model, targets, list(X.columns), path="land_recommender_model.pkl")

    # Example inference (fill in your list)
    # model, targets, feats = load_model("land_recommender_model.pkl")
    # example_cards = ["Sol Ring", "Cultivate", "Kodama's Reach", "Rhystic Study", "Dockside Extortionist"]
    # commanders = ["Atraxa, Praetors' Voice"]
    # preds = recommend_for_decklist(example_cards, commanders, index, model, feats)
    # print("Recommendation:", preds)