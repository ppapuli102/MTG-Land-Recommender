# # app.py
# # Streamlit web UI for the land/color-source recommender
# # pip install -r requirements.txt
# import re
# import time
# import joblib
# import numpy as np
# import pandas as pd
# import streamlit as st

# from land_recommender import (
#     load_card_index,
#     load_model,
#     recommend_for_decklist,
#     extract_features,
#     split_mainboard,
#     count_color_sources_from_lands,
#     deck_color_identity,
#     fetch_archidekt_deck,
#     normalize_archidekt_decklist,
#     MANA_SYMBOLS,
# )

# MODEL_PATH = "land_recommender_model.pkl"

# @st.cache_resource(show_spinner=True)
# def get_card_index():
#     return load_card_index()

# @st.cache_resource(show_spinner=True)
# def get_model():
#     try:
#         model, targets, feature_cols = load_model(MODEL_PATH)
#         return model, targets, feature_cols, None
#     except Exception as e:
#         return None, None, None, e

# def parse_decklist_text(text: str):
#     # Parse simple "qty name" lines; ignore empty/comment lines.
#     # Returns list[(name, qty)]
#     mainboard = []
#     for raw in text.splitlines():
#         line = raw.strip()
#         if not line or line.startswith("#") or line.lower().startswith("//"):
#             continue
#         # Remove set/collector info in () or []
#         line = re.sub(r"\s*[KATEX_INLINE_OPEN```math
# ].*?[KATEX_INLINE_CLOSE```]\s*", " ", line).strip()
#         # Common "1x Card Name" or "1 Card Name"
#         m = re.match(r"^\s*(\d+)\s*[xX]?\s+(.+)$", line)
#         if m:
#             q = int(m.group(1))
#             name = m.group(2).strip()
#             mainboard.append((name, q))
#             continue
#         # No qty -> assume 1
#         mainboard.append((line, 1))
#     return mainboard

# def parse_commanders_text(text: str):
#     names = []
#     for raw in text.splitlines():
#         line = raw.strip()
#         if not line:
#             continue
#         # Remove set/collector info
#         line = re.sub(r"\s*[KATEX_INLINE_OPEN```math
# ].*?[KATEX_INLINE_CLOSE```]\s*", " ", line).strip()
#         names.append(line)
#     return names

# def recommend(deck_mainboard, commander_names, index, model, feature_cols):
#     # Build a normalized deck for feature extraction
#     deck = {
#         "name": "User Deck",
#         "format": "Commander",
#         "commanders": [(n, 1) for n in commander_names],
#         "mainboard": deck_mainboard,
#     }
#     # Predict via model (if present), else fallback heuristic
#     preds = None
#     if model is not None:
#         X = extract_features(deck, index)
#         x_vec = np.array([[X.get(col, 0.0) for col in feature_cols]])
#         y_pred = model.predict(x_vec)[0]
#         preds = {"land_total": int(round(max(0, y_pred[0])))}  # total lands
#         for i, c in enumerate(MANA_SYMBOLS, start=1):
#             preds[f"src_{c}"] = int(round(max(0, y_pred[i])))
#         return preds

#     # Fallback heuristic if model missing
#     X = extract_features(deck, index)
#     # Land baseline and adjustments
#     land_total = 36
#     land_total -= 0.35 * (X.get("ramp_artifacts", 0) + X.get("ramp_creatures", 0))
#     land_total -= 0.55 * X.get("ramp_land_spells", 0)
#     land_total -= 0.2 * X.get("cost_reducers", 0)
#     land_total -= 0.1 * X.get("free_or_alt_cost", 0)
#     land_total -= 0.1 * X.get("card_selection", 0)
#     land_total -= 0.2 * X.get("treasure_score", 0)
#     # Heavy curve penalty
#     land_total += 0.5 * (X.get("cmc_6", 0) + X.get("cmc_7", 0))
#     land_total = int(round(min(max(28, land_total), 42)))

#     preds = {"land_total": land_total}
#     # Color source targets from early pip pressure
#     for c in MANA_SYMBOLS:
#         p_early = X.get(f"pips_{c}_early", 0.0)
#         p_total = X.get(f"pips_{c}_total", 0.0)
#         # 7 baseline if color present, plus scaled pressure
#         base = 7.0 if X.get(f"deck_has_{c}", 0.0) > 0 else 0.0
#         target = base + 0.7 * p_early + 0.15 * p_total
#         preds[f"src_{c}"] = int(round(max(0, target)))
#     return preds

# def color_sources_from_user_lands(deck_mainboard, index):
#     lands, spells = split_mainboard(deck_mainboard, index)
#     return count_color_sources_from_lands(lands, index), sum(q for _, q in lands)

# def basic_mix_suggestion(pred_sources, current_sources, delta_lands):
#     # Suggest basic lands to cover deficits. If delta_lands is negative,
#     # suggest swaps instead.
#     basic_map = {"W": "Plains", "U": "Island", "B": "Swamp", "R": "Mountain", "G": "Forest"}
#     deficits = {c: max(0, pred_sources.get(f"src_{c}", 0) - current_sources.get(c, 0)) for c in MANA_SYMBOLS}
#     add_list = []
#     swaps = []
#     remaining_adds = max(0, delta_lands)
#     # Greedy: use available slots to cover biggest deficits first
#     order = sorted(MANA_SYMBOLS, key=lambda c: deficits[c], reverse=True)
#     for c in order:
#         need = deficits[c]
#         if need == 0: 
#             continue
#         if remaining_adds > 0:
#             take = min(need, remaining_adds)
#             if take > 0:
#                 add_list.append((basic_map[c], int(take)))
#                 remaining_adds -= take
#                 need -= take
#         if need > 0:
#             # Still need sources -> suggest swaps
#             swaps.append((basic_map[c], int(need)))
#     return add_list, swaps

# def render_prediction(preds, current_sources, current_land_count):
#     cols = ["W", "U", "B", "R", "G"]
#     st.subheader("Recommendation")
#     st.metric("Predicted land total", preds["land_total"])
#     src_df = pd.DataFrame(
#         {
#             "Color": cols,
#             "Target sources": [preds[f"src_{c}"] for c in cols],
#             "Your current sources": [current_sources.get(c, 0) for c in cols],
#             "Delta": [preds[f"src_{c}"] - current_sources.get(c, 0) for c in cols],
#         }
#     )
#     st.dataframe(src_df, hide_index=True, use_container_width=True)

#     delta_lands = preds["land_total"] - current_land_count
#     st.write(f"Current land count: {current_land_count} | Change needed: {delta_lands:+d}")
#     add_list, swaps = basic_mix_suggestion(preds, current_sources, delta_lands)

#     if add_list:
#         st.markdown("Add these basics (first):")
#         st.write(", ".join([f"{q} {n}" for n, q in add_list]))
#     if swaps:
#         st.markdown("Then swap existing lands for:")
#         st.write(", ".join([f"{q} {n}" for n, q in swaps]))

# def try_fetch_archidekt(url: str):
#     m = re.search(r"archidekt\.com/decks/(\d+)", url)
#     if not m:
#         return None
#     did = int(m.group(1))
#     dj = fetch_archidekt_deck(did)
#     return normalize_archidekt_decklist(dj)

# # ----------------- Streamlit UI -----------------

# st.set_page_config(page_title="MTG Land Recommender", page_icon="🗺️", layout="wide")
# st.title("🗺️ Land & Color Source Recommender (Commander)")

# index = get_card_index()
# model, targets, feature_cols, model_err = get_model()
# if model is None:
#     st.info("No trained model found (land_recommender_model.pkl). Using a fallback heuristic. "
#             "Run 'python land_recommender.py' to train and save a model for better results.")

# tab1, tab2 = st.tabs(["Paste decklist", "Archidekt URL"])

# with tab1:
#     st.subheader("Deck inputs")
#     commanders_text = st.text_area("Commander(s) — one per line", height=60, placeholder="Atraxa, Praetors' Voice")
#     deck_text = st.text_area(
#         "Decklist (any 'qty name' format; include lands if you want current source analysis)",
#         height=280,
#         placeholder="1 Sol Ring\n1 Cultivate\n2 Island\n1 Command Tower\n..."
#     )
#     run_btn = st.button("Recommend")

#     if run_btn:
#         commander_names = parse_commanders_text(commanders_text)
#         deck_mainboard = parse_decklist_text(deck_text)

#         if not commander_names:
#             st.warning("Please provide at least one commander.")
#         elif not deck_mainboard:
#             st.warning("Please paste your decklist.")
#         else:
#             with st.spinner("Crunching features and predicting..."):
#                 preds = recommend(deck_mainboard, commander_names, index, model, feature_cols)
#                 current_sources, current_land_count = color_sources_from_user_lands(deck_mainboard, index)
#                 render_prediction(preds, current_sources, current_land_count)

# with tab2:
#     st.subheader("Import from Archidekt")
#     arch_url = st.text_input("Archidekt deck URL", placeholder="https://archidekt.com/decks/1234567")
#     fetch_btn = st.button("Fetch from Archidekt")
#     if fetch_btn and arch_url:
#         with st.spinner("Fetching deck..."):
#             nd = try_fetch_archidekt(arch_url)
#             if not nd:
#                 st.error("Could not parse the URL. Make sure it's like https://archidekt.com/decks/<id>")
#             else:
#                 deck_mainboard = nd["mainboard"]
#                 commander_names = [n for (n, q) in nd["commanders"]]
#                 preds = recommend(deck_mainboard, commander_names, index, model, feature_cols)
#                 current_sources, current_land_count = color_sources_from_user_lands(deck_mainboard, index)

#                 st.success(f"Loaded: {nd.get('name','Deck')}")
#                 st.write("Commanders:", ", ".join(commander_names))
#                 render_prediction(preds, current_sources, current_land_count)