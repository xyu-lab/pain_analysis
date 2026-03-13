import pandas as pd
from pathlib import Path
import tkinter as tk
from tkinter import filedialog
import os
import re


# ----- Combine Digital & Analog files and extract stimulus-delivery events -----

# Code for converting voltage readings of the stimulus potentiometer into actual stimulus values
def voltage_to_stimulus(voltage):
    """Convert voltage to stimulus type"""
    try:
        v = float(voltage)
        if v < 0 or v <= 0.759:
            return "0.02g"
        elif 0.76 <= v <= 1.59:
            return "0.04g"
        elif 1.6 <= v <= 2.39:
            return "0.07g"
        elif 2.4 <= v <= 3.29:
            return "0.16g"
        elif 3.3 <= v <= 4.09:
            return "Air Puff"
        elif v >= 4.1:
            return "Other"
    except:
        return "Invalid"

# Code for processing the hit columns
def process_hits_column(frames_df, analog_df, hit_col, output_dir, round_id=""):
    frames = frames_df[frames_df['Frame'] == 1].copy()
    frames['Frame'] = range(1, len(frames) + 1)

    merged = pd.merge_asof(
        frames.sort_values('Time [s]'),
        analog_df.sort_values('Time [s]'),
        left_on='Time [s]',
        right_on='Time [s]',
        direction='nearest'
    )

    merged['Stimulus'] = merged['Stimulus'].apply(voltage_to_stimulus)
    merged['Stimulus'] = merged['Stimulus'].replace('', pd.NA).ffill().fillna('Invalid')
    merged.rename(columns={hit_col: 'Hit_Raw'}, inplace=True)

    merged['Hit'] = 0
    hit_counter = 0
    previous_stimulus = None
    previous_hit = 0

    for index, row in merged.iterrows():
        current_stimulus = row['Stimulus']
        current_hit_raw = row['Hit_Raw']

        if current_stimulus != previous_stimulus:
            hit_counter = 0
        elif current_hit_raw == 1 and previous_hit == 0:
            hit_counter += 1

        merged.at[index, 'Hit'] = hit_counter
        previous_stimulus = current_stimulus
        previous_hit = current_hit_raw

    output_cols = ['Time [s]', 'Hit', 'Frame', 'Stimulus']
    final_rows = []
    previous_hit_value = None

    for index, row in merged.iterrows():
        if row['Hit'] != previous_hit_value and row['Hit'] > 0:
            final_rows.append(row)
            previous_hit_value = row['Hit']

    # Save new file of corrected 'Hits' (integer) & 'Stimulus' (string)
    final_output = pd.DataFrame(final_rows, columns=output_cols)
    
    if round_id:
        output_file_name = f"Compiled-Saleae-Data-{hit_col}_{round_id}.csv"
    else:
        output_file_name = f"Compiled-Saleae-Data-{hit_col}.csv"
        
    output_file_path = os.path.join(output_dir, output_file_name)
    
    try:
        final_output.to_csv(output_file_path, index=False)
        print(f"Results saved to: {output_file_path}")
    except Exception as e:
        print(f"An error occurred while saving {hit_col} output file: {e}")



# ====================================================================
# MAIN
# ====================================================================

def main():
    print("Saleae Digital & Analog Data Compiler")
    print("="*40)

    root = tk.Tk()
    root.withdraw()

    # Pop-up file selection
    print("Please select the digital.csv file")
    digital_file_path = filedialog.askopenfilename(
        title="Select digital.csv",
        filetypes=[("CSV files", "*.csv")],
        initialdir= r"I:\Projects\orofacial_project\data\evoked\raw_files",
    )
    if not digital_file_path:
        print("No digital.csv file selected.")
        return

    print("Please select the analog.csv file")
    analog_file_path = filedialog.askopenfilename(
        title="Select analog.csv",
        filetypes=[("CSV files", "*.csv")],
         initialdir= r"I:\Projects\orofacial_project\data\evoked\raw_files",
    )
    if not analog_file_path:
        print("No analog.csv file selected.")
        return

    # Extract round_id
    round_id = ""
    # Look for "roundX" in the filename
    basename = os.path.basename(digital_file_path)
    match = re.search(r'(r\d+)', basename, re.IGNORECASE)
    if match:
        round_id = match.group(1)
    
    try:
        digital = pd.read_csv(digital_file_path)
        analog = pd.read_csv(analog_file_path)
    except Exception as e:
        print(f"Error reading CSV files: {e}")
        return

    print("="*40)
    print("Compiling Data...")
    print("="*40)


    output_dir = os.path.dirname(digital_file_path)
    analog['Stimulus'] = analog['Stimulus'].ffill()


    hit_columns = [col for col in digital.columns if col.startswith("Hits_b")]

    if not hit_columns:
        print("No hit columns found (e.g., 'Hits_bay1').")
        return

    for hit_col in hit_columns:
        print(f"Processing {hit_col}...")
        process_hits_column(digital.copy(), analog.copy(), hit_col, output_dir, round_id)

    print("All CSV files compiled!")

if __name__ == "__main__":
    main()