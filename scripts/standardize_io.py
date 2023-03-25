# %% [markdown]
# ### This script will combine the cards.feather and decks.feather into one dataframe which can be used for input to a model

# %%
import pandas as pd
import numpy as np
from tqdm import tqdm
import os
import logging
import warnings
from IPython.display import display, HTML


# %%
# Get the absolute path of the current working directory
current_dir = os.path.abspath(os.getcwd())

# Get the absolute path of the parent directory
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))

# Read our card database
file_path = os.path.join(parent_dir, 'data', 'mtg_card_database')

card_fp = os.path.join(parent_dir, 'data', 'cards.feather')
deck_fp = os.path.join(parent_dir, 'data', 'decks.feather')

card_df = pd.read_feather(card_fp)
deck_df = pd.read_feather(deck_fp)

# %%
deck_df = deck_df.reset_index().drop(columns=['index'])
deck_df
# %%
num_decks = len(deck_df)

input = pd.DataFrame(columns=[
    'avg_cmc', 
    'cast_cost_W',
    'cast_cost_U',
    'cast_cost_B',
    'cast_cost_R',
    'cast_cost_G',
    'cast_cost_C',
    'cast_cost_P',
    'produces_W',
    'produces_U',
    'produces_B',
    'produces_R',
    'produces_G',
    'produces_C',
    'produces_P',
    'num_x_in_mana_cost',
    'has_looting',
    'has_carddraw',
    'makes_treasure_tokens',
    'reduced_spells',
    'free_spells',
    'is_land',
])
output = pd.DataFrame(columns=[
    'color_sources_W',
    'color_sources_U',
    'color_sources_B',
    'color_sources_R',
    'color_sources_G',
    'color_sources_C',
    'number_of_lands',
])


# %%
def handle_dfc(row):
    try:
        return row.split(' // ')[0]
    except:
        return row

# We need to get a name from the card database which can be joined with the deck
# But since there are DFC cards with the format 'name1 // name2' we need to extract name1 to create a valid join
card_df['name2'] = card_df['name'].apply(lambda row: handle_dfc(row))

# %%
# Extract the card amount
def extract_card_amount(_deck):
    def extract_card(row):
        try:
            card = row[1:].strip()
            return card
        except:
            return row

    def extract_card_amt(row):
        try:
            amount_of_card = row[0]
            return amount_of_card
        except:
            return row

    _deck = _deck.copy()
    _deck['card'] = _deck['card+amt'].apply(lambda row: extract_card(row))
    _deck['amount'] = _deck['card+amt'].apply(lambda row: extract_card_amt(row))

    _deck = _deck.drop(columns='card+amt')

    return _deck

# %%
def handle_set_in_card_name(_deck):
    def extract_info(row):
        return row.split('(')[0].strip()
    _deck['card'] = _deck['card'].apply(lambda row: extract_info(row))

    return _deck

# %%
def create_io(_deck):
    """
        Creates the input and output row from a single deck row in df_decks
        The data should be of format [1 'Atraxa...' 2 'Swamp'], etc
        Data will be output as two single line input and output x and y

    Args:
        deck (pd.Series): a single row which we will extract data from

    Returns:
        df_merged, df_lands: input and target output for model
    """
    _deck = pd.DataFrame(data={'card+amt': _deck})
    _deck = extract_card_amount(_deck)
    _deck = handle_set_in_card_name(_deck)

    # Merge the deck back together with the cards data
    merged_df = pd.merge(left=_deck, right=card_df, left_on='card', right_on='name2', how='left')

    # Drop the irrelevant columns
    merged_df = merged_df.drop(columns=[
        'card',
        'name',
        'type_line',
        'name2',
        'produces_P',
    ])

    # Extract the lands from the deck into their own dataframe
    land_df = merged_df[merged_df['is_land'] == 1]
    merged_df = merged_df[merged_df['is_land'] == 0]

    merged_df = merged_df.drop(columns=['is_land'])

    num_cards = merged_df['amount'].astype(int).sum()

    # Multiply relevant columns by the amount col
    def multiply_amounts(row):
        try:
            return row * int(row.amount)
        except:
            return row

    merged_df = merged_df.apply(multiply_amounts, axis=1)
    land_df = land_df.apply(multiply_amounts, axis=1)

    # Rename and drop some columns
    col_to_drop = ['amount']
    merged_df = merged_df.drop(columns=col_to_drop)
    land_df = land_df.drop(columns=col_to_drop)
    col_rename = {
        'produces_W' : 'color_sources_W',
        'produces_U' : 'color_sources_U',
        'produces_B' : 'color_sources_B',
        'produces_R' : 'color_sources_R',
        'produces_G' : 'color_sources_G',
        'produces_C' : 'color_sources_C',
        'is_land' : 'number_of_lands',
    }
    land_df = land_df.rename(columns=col_rename)

    def sum_columns_to_single_row(df):
        summed_values = {column: int(df[column].sum()) for column in df.columns}
        return pd.DataFrame([summed_values])

    df_merged = sum_columns_to_single_row(merged_df)
    df_lands = sum_columns_to_single_row(land_df)

    # Convert cmc from a total value to an average rounded up to nearest decimal
    df_merged = df_merged.rename(columns={'cmc': 'avg_cmc'})
    df_merged['avg_cmc'] = df_merged['avg_cmc'] / num_cards
    df_merged['avg_cmc'] = df_merged['avg_cmc'].apply(lambda row: round(row, 1))

    # Clean up the output
    df_lands = df_lands.drop(columns=[
        'cmc',
        'cast_cost_W',
        'cast_cost_U',
        'cast_cost_B',
        'cast_cost_R',
        'cast_cost_G',
        'cast_cost_C',
        'cast_cost_P',
        # 'produces_P',
        'num_x_in_mana_cost',
        'has_looting',
        'has_carddraw',
        'makes_treasure_tokens',
        'reduced_spells',
        'free_spells',
    ])

    return df_merged, df_lands


if __name__ == '__main__':

    # %%
    warnings.simplefilter("ignore")
    pd.options.display.max_columns = 20000
    pd.set_option('display.width', 1000)

    # %%
    # Define a custom log handler that writes messages to the notebook output
    class NotebookLogHandler(logging.Handler):
        def emit(self, record):
            message = self.format(record)
            display(HTML(f'<p style="color: {record.levelname.lower()}">{message}</p>'))

    # Create a logger and set its level to INFO
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Create a formatter and add it to the logger
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler = NotebookLogHandler()
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    # %% [markdown]
    # #### Read in our cards and deck data

    for i in tqdm(range(num_decks), desc="Processing decks"):
        deck_i = deck_df.iloc[i][0]
        try:
            x, y = create_io(deck_i)
        except Exception as e:
            print(f'Failed to append deck: \n{deck_i}\nError Message: \n\t{e}')
            continue
        input = input.append(x)
        output = output.append(y)

    input = input.reset_index(drop=True)
    output = output.reset_index(drop=True)

    print(input)
    print(output)

    # %%
    input = input.drop(columns=['produces_P', 'is_land'])

    # %% [markdown]
    # ### We need to clean the decks which had empty data

    # %%
    bad_data = input.loc[input['avg_cmc'].isna()]
    indx_to_drop = bad_data.index
    input_cleaned = input.drop(indx_to_drop)
    output_cleaned = output.drop(indx_to_drop)

    # %%
    input_cleaned

    # %%
    output_single = output_cleaned['number_of_lands']

    # %%
    input_fp = os.path.join(parent_dir, 'data', 'input.feather')
    output_fp = os.path.join(parent_dir, 'data', 'output.feather')

    input_fp = os.path.join(parent_dir, 'data', 'input.feather')
    output_fp = os.path.join(parent_dir, 'data', 'output.feather')

    # Reset the row index for input and output DataFrames
    input_reset = input_cleaned.reset_index(drop=True)
    output_reset = output_cleaned.reset_index(drop=True)

    if isinstance(input_reset, pd.Series):
        input_reset = input_reset.to_frame()
    if isinstance(output_reset, pd.Series):
        output_reset = output_reset.to_frame()

    # Transpose and reset the column index for input and output DataFrames, then transpose back
    # input_reset = input_reset.T.reset_index(drop=True).T
    # output_reset = output_reset.T.reset_index(drop=True).T

    # Save the DataFrames to feather format
    input_reset.to_feather(input_fp)
    output_reset.to_feather(output_fp)

