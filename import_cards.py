import pandas as pd
import numpy as np
from collections import Counter
import re
from import_data_source import get_card_data

pd.options.display.max_columns = 20000

# %% [markdown]
# # Create a pandas dataframe of all cards

# %% [markdown]
# ### Create initial dataframe and perform some preprocessing tasks

# %%
# Import card data
lexicon = get_card_data()

# %%
# Only keep the most recent arena set, dropping all reprints
lexicon = lexicon.sort_values(by='arena_id', ascending=False).copy()
lexicon = lexicon.drop_duplicates(subset=["name"])
lexicon = lexicon.set_index("name", drop=False)
lexicon.index.name = "card_name"

# %% [markdown]
# ### Fix Double-Sided Cards

# %%
# Let's first create a dataframe that just has the card name and the column 'card_faces'
double_cards_df = lexicon[['name','card_faces']].dropna()

# We also filter it so we get cards that actually have 2 sides
double_cards_df = double_cards_df[double_cards_df['card_faces']!="none"]

# DFC are a list of two dictionaries [ {k:v, k2:v2}, {k3:v3} ]
def split_card_faces(row, face_number):
    face = row[face_number]
    return face

face_one = 0
face_two = 1
double_cards_df['face1'] = double_cards_df['card_faces'].apply(lambda row: split_card_faces(row, face_one))
double_cards_df['face2'] = double_cards_df['card_faces'].apply(lambda row: split_card_faces(row, face_two))

# # Now let's drop the column 'card_faces'
# double_cards_df = double_cards_df.copy()
# double_cards_df.drop("card_faces",axis=1)

# We now go into each key within the dictionary of face1 and face2 and separate them into columns
try:
    double_cards_df[double_cards_df['face1'].apply(pd.Series).columns + "_1"] = double_cards_df['face1'].apply(pd.Series)
    double_cards_df[double_cards_df['face2'].apply(pd.Series).columns + "_2"] = double_cards_df['face2'].apply(pd.Series)
except:
    pass

# Define a list of columns we want to keep from the 2 sided cards
cols_to_keep = ['name', 'name_1', 'name_2', 'oracle_text_1','oracle_text_2',
                'mana_cost_1', 'mana_cost_2', 'type_line_1', 'type_line_2']

# For each column in the dataframe, if it's not a selected column, we drop it
for col in double_cards_df.columns:
    if col not in cols_to_keep:
        double_cards_df.drop(col, axis=1, inplace=True)

# We now need to consolidate the 2 oracle texts into 1, we join them together
double_cards_df['oracle_text_dobles'] = double_cards_df['oracle_text_1'] + "\n" + double_cards_df['oracle_text_2']

# Reset the indexes
double_cards_df = double_cards_df.reset_index(drop=True)

# %%
# Merge the 2 faces info into our main df

# We now merge them by card name
lexicon = lexicon.merge(double_cards_df, on=["name"], how="left")
# .drop("card_faces",axis=1, left_index=True)

# %%
# We use this script to replace Nulls with "None"
lexicon[['oracle_text_1','oracle_text_2']] = lexicon[['oracle_text_1','oracle_text_2']].fillna("None")

try:
    lexicon[['name', 'name_1', 'name_2', 'oracle_text_1','oracle_text_2',
                'mana_cost_1', 'mana_cost_2', 'type_line_1', 'type_line_2']] = lexicon[['name', 'name_1', 'name_2', 'oracle_text_1','oracle_text_2',
                                                                                        'mana_cost_1', 'mana_cost_2', 'type_line_1', 'type_line_2']].fillna("None")
except:
    pass

# Now that we have our oracle text from the 2 card sides joined together, we want to use it to replace
# the actual "oracle_text" from the original dataframe, which is actually empty

# If oracle_text is empty (meaning it's a double faced card), we replace it with our 'oracle_text_dobles' column
lexicon['oracle_text'] = np.where(lexicon['oracle_text'].isna(),lexicon['oracle_text_dobles'],lexicon['oracle_text'])

lexicon.columns

# # And now that column is useless so we drop it
# lexicon = lexicon.drop("oracle_text_dobles",axis=1)

# %%
lexicon[lexicon["name"] == "Esika, God of the Tree // The Prismatic Bridge"]

# %% [markdown]
# ### Create columns for casting cost pips

# %%
def count_pips(s):
    """Applied to the mana_cost column in lexicon to return the number of pips in that color

    Args:
        s (string): mana cost separated by brackets

    Returns:
        pips (Counter): a Counter of the number of pips in each color W U B R G
    """
    
    s = s.replace("{", "").replace("}", "")

    colors = ["W", "U", "B", "R", "G"]
    W, U, B, R, G = 0, 0, 0, 0, 0
    pips = Counter(s)

    # Delete unecessary information
    to_delete = []
    for e in pips:
        if e not in colors:
            to_delete.append(e)
    for e in to_delete:
        del pips[e]


    return pips
# print(count_pips("WUBRG")["R"])

# %%
# A copy of the lexicon df is created so that we can avoid making changes to a copy of a sliced df
lexicon = lexicon.copy()
lexicon.loc[:, 'cast_cost_W'] = lexicon['mana_cost'].map(lambda s: count_pips(s)['W'], na_action='ignore')
lexicon.loc[:, 'cast_cost_U'] = lexicon['mana_cost'].map(lambda s: count_pips(s)['U'], na_action='ignore')
lexicon.loc[:, 'cast_cost_B'] = lexicon['mana_cost'].map(lambda s: count_pips(s)['B'], na_action='ignore')
lexicon.loc[:, 'cast_cost_R'] = lexicon['mana_cost'].map(lambda s: count_pips(s)['R'], na_action='ignore')
lexicon.loc[:, 'cast_cost_G'] = lexicon['mana_cost'].map(lambda s: count_pips(s)['G'], na_action='ignore')
lexicon.loc[:, 'cast_cost_C'] = lexicon['mana_cost'].map(lambda s: count_pips(s)['C'], na_action='ignore')


# %% [markdown]
# ### Create columns for produced mana colors of non-land cards

# %%
def count_produced_mana(s):
    """Applied to the produced_mana column, returns the colors produced by a card

    Args:
        s (List[str]): 

    Returns:
        prod_mana: _description_
    """    
    return Counter(s)

print(count_produced_mana(['B']))

# %%
lexicon.loc[:, 'produces_W'] = lexicon['produced_mana'].map(lambda s: count_produced_mana(s)['W'], na_action='ignore')
lexicon.loc[:, 'produces_U'] = lexicon['produced_mana'].map(lambda s: count_produced_mana(s)['U'], na_action='ignore')
lexicon.loc[:, 'produces_B'] = lexicon['produced_mana'].map(lambda s: count_produced_mana(s)['B'], na_action='ignore')
lexicon.loc[:, 'produces_R'] = lexicon['produced_mana'].map(lambda s: count_produced_mana(s)['R'], na_action='ignore')
lexicon.loc[:, 'produces_G'] = lexicon['produced_mana'].map(lambda s: count_produced_mana(s)['G'], na_action='ignore')
lexicon.loc[:, 'produces_C'] = lexicon['produced_mana'].map(lambda s: count_produced_mana(s)['C'], na_action='ignore')



