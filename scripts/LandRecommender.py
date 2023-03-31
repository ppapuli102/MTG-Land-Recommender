import os
import tkinter as tk
from tkinter import Text, filedialog

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import PolynomialFeatures
from standardize_io import create_io

# Get the absolute path of the current working directory
current_dir = os.path.abspath(os.getcwd())

# Get the absolute path of the parent directory
parent_dir = os.path.abspath(os.path.join(current_dir, os.pardir))

# Read our card database
file_path = os.path.join(parent_dir, 'models', 'rf_multi_poly_model_no_outliers.joblib.z')

# Load the trained model from the joblib file
model = joblib.load(file_path)

header_font = ("Courier New", 20)
default_font = ("Courier New", 12)
button_style = {"bg": "lightblue", "fg": "black", "font": default_font}

# Function to open the file browser and read the selected file
def open_file():
    # Open file browser and get the selected file path
    file_path = filedialog.askopenfilename(initialdir="/", title="Select File", filetypes=(("text files", "*.txt"), ("all files", "*.*")))
    # Read the text file into a DataFrame
    input_data = pd.read_csv(file_path, delimiter='\t', names=['deck'])
    process_input_data(input_data)

# Function to process the input data and display the output dataframe
def process_input_data(input_data):
    input_data.columns = ['deck']
    input_data = input_data['deck']
    x, y = create_io(input_data)
    poly = PolynomialFeatures(degree=2, include_bias=False)
    x = poly.fit_transform(x)
    predictions_unrounded = model.predict(x)
    predictions = np.round(predictions_unrounded)
    df = pd.DataFrame(predictions, columns=y.columns)

    # Clear the output frame
    for widget in output_frame.winfo_children():
        widget.destroy()

    # Display the resulting dataframe in separate output widgets
    for i, col in enumerate(df.columns):
        col_label = tk.Label(output_frame, text=col, font=default_font)
        col_label.grid(row=i, column=0, padx=10, pady=10, sticky="w")
        col_output = Text(output_frame, wrap=tk.WORD, width=20, height=1)
        col_output.grid(row=i, column=1, padx=10, pady=10)
        col_output.insert(tk.END, df[col].to_string(index=False))

# Function to import data from the input textbox
def import_from_textbox():
    input_data_text = input_text.get("1.0", tk.END)
    input_data_list = input_data_text.splitlines()
    input_data = pd.DataFrame(input_data_list, columns=['deck'])
    process_input_data(input_data)

# Create a Tkinter window
root = tk.Tk()
root.title("Deck Analyzer")

# Add "Open File" button
open_file_button = tk.Button(root, text="Browse", command=open_file, **button_style)
open_file_button.grid(row=0, column=0, padx=10, pady=10)

# Add input textbox with a label
input_label = tk.Label(root, text="Import Deck from Text:", font=default_font)
input_label.grid(row=1, column=0, padx=10, pady=10, sticky="w")
input_text = Text(root, wrap=tk.WORD, width=50, height=10)
input_text.grid(row=2, column=0, padx=10, pady=10)

# Add "Import" button to import data from the input textbox
import_button = tk.Button(root, text="Import", command=import_from_textbox, **button_style)

import_button.grid(row=3, column=0, padx=10, pady=10)

# Add output frame and label
output_label = tk.Label(root, text="Recommendations:", font=default_font)
output_label.grid(row=4, column=0, padx=10, pady=10, sticky="w")
output_frame = tk.Frame(root)
output_frame.grid(row=5, column=0, padx=10, pady=10)

# Run the Tkinter window
root.mainloop()