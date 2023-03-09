import pandas as pd
import os

"""
    TODO: 
        SET UP API CALL TO SCRYFALL AND DELETE default-cards.json file
"""

# Get the absolute path of the current working directory
current_dir = os.path.abspath(os.getcwd())

# Get the absolute path of the parent directory
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))

# Set file path to the json file with card data downloaded directly from scryfall
file_path = os.path.join(parent_dir, 'data', 'default-cards-20230308220851.json')

print(file_path)

df_source = pd.read_json(file_path, orient='records')

# Subset the source data into only fields we care about
lexicon = df_source[[
    'id',
    'name',
    'mana_cost',
    'cmc',
    'type_line',
    'oracle_text',
    'power',
    'toughness',
    'colors',
    'color_identity',
    'produced_mana',
    'keywords',
    'set',
    'rarity',
    'flavor_text',
    'edhrec_rank',
    'arena_id',
    'loyalty',
    'card_faces',
]]

lexicon.to_feather('mtg_card_database.feather')

def get_card_data():
    return pd.read_feather(path='mtg_card_database.feather')
