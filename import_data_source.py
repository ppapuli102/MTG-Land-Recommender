import pandas as pd

# Pull the data from the source json file
fp = "default-cards-20221230100442.json"
df_source = pd.read_json(fp, orient='records')

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
lexicon

# df_deck = pd.DataFrame(columns=lexicon.columns)

lexicon.to_feather('mtg_card_database')

def get_card_data():
    return pd.read_feather(path='mtg_card_database')


if __name__ == '__main__':
    get_card_data()
