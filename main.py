import pandas as pd
import numpy as np
import os
import json
# import gui
import re


# Pull the data from the source json file
fp = "C:/Users/Peter/Desktop/mtg_land_suggestor/default-cards-20221230100442.json"
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
    'keywords',
    'set',
    'rarity',
    'flavor_text',
    'edhrec_rank',
    'arena_id',
    'loyalty',
    'card_faces',
]]

df_deck = pd.DataFrame(columns=lexicon.columns)

imported_deck = []

def RejoinCardName(lst):
    card_name = ''
    for word in lst:
        card_name += word + ' '
    return card_name.strip()

# Read the contents of the text file with the decklist
with open('mtga_import.txt', 'r') as file:
    file_lines = file.readlines()
    # Read through each line and isolate the card name and amounts
    for line in file_lines:
        split = line.split(' ')
        if len(split) < 3:
            continue
        amt = split[0]
        card = split[1:-2]
        card_set = split[-2]

        imported_deck.append([amt, card, card_set])

for line in imported_deck:
    if len(line) > 0:
        card_name_joined = RejoinCardName(line[1])
        mask = lexicon['name'].str.match(card_name_joined)
        card_to_add = lexicon[mask].sort_values(by='arena_id', ascending=False)
        # Handle the out-of-bounds error
        try:
            card_to_add = card_to_add.iloc[[0]]
        except IndexError:
            print('Index out of bounds')
            continue
        df_deck = pd.concat([df_deck, card_to_add])
        # df_deck.iloc[0]['amount'] = line[0]

# print(df_deck[df_deck['mana_cost'].isna()])
print(df_deck.iloc[2]['card_faces'][0]['mana_cost'])

###### If the mana_cost is na and the cmc == 0.0
###### Then go into that cards 'card_faces' and loop over all elements in the array of dictionaries and grab the 'mana_cost' value of each
###### Compare the mana cost values after the loop is completed and grab the most stringent one

# # create a Pandas Series with some strings
# s = lexicon['name']

# # use a regular expression to check if any of the strings in the Series match the pattern 'b.t'
# mask = s.str.match('Treasure Map')
# print(mask.iloc[2787])

# # print the elements in the Series that match the pattern 'b.t'
# print(s[mask])



# # Define the regex pattern
# pattern = r"Branchloft Pathway"

# # Define the strings to compare
# string1 = lexicon[lexicon['name']]

# # Use the `search` function to check if the regex pattern matches either string
# match1 = re.search(pattern, string1)

# # Check if a match was found in either string
# if match1:
#   print("The pattern was found in string 1.")



# # Create the GUI 
# gui.CreateGUI()

# # Once a decklist is imported, convert it into a serializable data type
# def ConvertDeckList(dl):
#     '''
#         Converts a string of characters into a list of elements which 
#         can be looped through:
#         Representing a deck of MtG cards.
#     '''



