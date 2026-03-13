import os
import pandas as pd


# ----- USER CONFIGURATION -----
# ====================================================================
# Hardcoded base directory where all experiment folders reside.
INPUT_BASE_DIR = r"I:\Projects\orofacial_project\data\evoked\processed_files"
# Hardcoded evoked analysis folder to deposit large CSV
OUTPUT_DIR = r"I:\Projects\orofacial_project\analysis\evoked\large_csv_files"

# ====================================================================



# ====================================================================
# FIND EXPERIMENT FOLDER
# ====================================================================

def find_experiment_folder(base_dir: str, number_input: str):
    """
    Searches a base directory for a folder that starts with 'Exp' + number_input.
    Returns the full folder name if a unique match is found, otherwise returns None.
    """
    prefix = f"Exp{number_input}"
    
    matches = []
    
    # Check if the base directory exists
    if not os.path.isdir(base_dir):
        print(f"Error: Base directory does not exist at {base_dir}")
        return None
        
    for item in os.listdir(base_dir):
        if os.path.isdir(os.path.join(base_dir, item)) and item.startswith(prefix):
            matches.append(item)
            
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"ERROR: Found multiple folders starting with '{prefix}'. Please be more specific.")
        return None
    else:
        print(f"ERROR: No folder found starting with '{prefix}' in {base_dir}")
        return None


def get_experiment_folder_path():
    """
    Prompts the user for a 3-digit Experiment ID, finds the corresponding 
    experiment folder within the hardcoded INPUT_BASE_DIR, and returns 
    the full, normalized path to that folder.
    Returns the string 'QUIT' if the user chooses to exit.
    Returns None on error or if no folder is found.
    """
    print(f"\nSearching for experiment folder in: {INPUT_BASE_DIR}")
    
    # 1. Get User Input for Experiment ID
    number_input = input("Enter the 3-digit Experiment ID (e.g., '001'), or type 'done'/'q' to quit: ").strip().lower()
    
    if number_input in ['done', 'q']:
        return "QUIT"
    
    if not number_input.isdigit() or len(number_input) < 1:
        print("Invalid input. Please enter a numerical Experiment ID or 'done'.")
        return None

    # Pad with leading zeros if necessary (e.g., '1' becomes '001')
    exp_id = number_input.zfill(3)

    # 2. Find the Experiment Folder
    folder_name = find_experiment_folder(INPUT_BASE_DIR, exp_id)
    
    if folder_name:
        # 3. Construct the full path
        full_exp_path = os.path.normpath(os.path.join(INPUT_BASE_DIR, folder_name))
        print(f"Found folder: {folder_name}")
        return full_exp_path
    else:
        # Error message is handled within find_experiment_folder
        return None



# ====================================================================
# MAIN
# ====================================================================

def main():
    # user inputs
    print("DeepLabCut output CSV compiler (experiment.csv)")
    print("="*40)
    print("This will put all keypoint metric data from all mice into a single MEGA CSV! 0_0")
    print("="*40)
    protocol_number = 306     # Orofacial Pain Protocol number
    # Extract date and treatment from the root directory name
    root_dir = get_experiment_folder_path()
    folder_name = os.path.basename(root_dir)
    parts = folder_name.rsplit('_', 4)
    if len(parts) == 5:
        experiment_ID = parts[0]
        date = parts[1]
        treatment = parts[3]
        cage_ID = parts[4]
    else:
        # Fallback or error handling if root_dir doesn't match the expected format
        print(f"Could not extract date and treatment from: {root_dir}. Using placeholders.")
        date = 'UnknownDate'
        treatment = 'UnknownTreatment'
    
    all_data = []

    # Level 1: Iterate over subject IDs (Mice)
    for subject_id in os.listdir(root_dir):
        subject_path = os.path.join(root_dir, subject_id)
        if not os.path.isdir(subject_path):
            continue

        # Level 2: Iterate over stimulus/trial folders
        for stimulus_folder in os.listdir(subject_path):
            stimulus_path = os.path.join(subject_path, stimulus_folder)
            if not os.path.isdir(stimulus_path):
                continue
        
            # Assume 'dlc_outputs' and 'cleaned_csvs' are fixed intermediate folders
            dlc_path = os.path.join(stimulus_path, 'dlc_outputs')
            if not os.path.isdir(dlc_path):
                continue

            cleaned_csvs_path = os.path.join(dlc_path, 'cleaned_csvs')
            if not os.path.isdir(cleaned_csvs_path):
                continue

            # Level 3: Iterate over body part metric folders
            for body_part_folder in os.listdir(cleaned_csvs_path):
                # IMPORTANT: Only process folders ending in '_metrics_median'
                if not body_part_folder.endswith('_metrics_median'):
                    continue

                body_path = os.path.join(cleaned_csvs_path, body_part_folder)
                if not os.path.isdir(body_path):
                    continue

                # Extract body_part name, removing the '_metrics_median' suffix
                body_part = body_part_folder.replace('_metrics_median', '')

                # Level 4: Iterate over individual metric CSV files
                for file in os.listdir(body_path):
                    if not file.endswith('.csv'):
                        continue

                    file_path = os.path.join(body_path, file)

                    try:
                        parts = file.split('_')
                        # Assuming the first part is the subject_ID, second is 'Trial', third is '1', fourth is 'Left'
                        if len(parts) >= 4:
                            # Extract trial number (e.g., '1' from 'Trial_1')
                            trial = parts[2]
                            # Extract side (e.g., 'Left' from 'Left')
                            side_of_stimulus = parts[3] 
                        else:
                            # Fallback if filename format is wrong
                            trial = 'N/A'
                            side_of_stimulus = 'N/A'
                            print(f"Warning: Unexpected filename format for trial/side extraction: {file}. Using N/A.")

                        df = pd.read_csv(file_path)
                        likelihood_col = 'likelihood' if 'likelihood' in df.columns else None

                        # 1. Extract the Quality Score
                        if 'trial_tracking_quality_pct' in df.columns:
                            trial_quality = df['trial_tracking_quality_pct'].iloc[0]
                        else:
                            trial_quality = None

                        processed_paired_cols = set()

                        for col in df.columns:
                            # Skip 'frame', 'likelihood', and already processed 'y' components
                            if col.lower() == 'frame' or col.lower() == 'likelihood' or col in processed_paired_cols:
                                continue

                            temp = df[['frame', col]].copy()
                            temp['protocol_number'] = protocol_number
                            temp['experiment_ID'] = experiment_ID
                            temp['unique_ID'] = subject_id
                            temp['cage_ID'] = cage_ID
                            temp['treatment'] = treatment
                            temp['date'] = date
                            temp['body_part'] = body_part 
                            temp['stimulus'] = stimulus_folder # Use the stimulus folder name
                            temp['side_of_stimulation'] = side_of_stimulus
                            temp['trial'] = trial
                            temp['likelihood'] = df[likelihood_col] if likelihood_col else None 
                            temp['trial_tracking_quality_pct'] = trial_quality

                            # --- Logic for handling metrics ---
                            if col.lower() == 'x_mm':
                                temp = temp.rename(columns={col: 'value_1'})
                                temp['value_2'] = df.get('y_mm', None)
                                temp['variable'] = 'position'
                                processed_paired_cols.add('y_mm')

                            elif col.lower() == 'vx': 
                                temp = temp.rename(columns={col: 'value_1'})
                                temp['value_2'] = df.get('vy', None)
                                temp['variable'] = 'velocity_mm_s'
                                processed_paired_cols.add('vy')

                            elif col.lower() == 'speed_mm_s':
                                temp = temp.rename(columns={col: 'value_1'})
                                temp['value_2'] = None
                                temp['variable'] = 'speed_mm_s'

                            elif col.lower() == 'acceleration_mm_s2':
                                temp = temp.rename(columns={col: 'value_1'})
                                temp['value_2'] = None
                                temp['variable'] = 'acceleration_mm_s2'

                            elif col.lower() == 'is_active':
                                temp = temp.rename(columns={col: 'value_1'})
                                temp['value_2'] = None
                                temp['variable'] = 'is_active'

                            else:
                                continue

                            all_data.append(temp)

                    except Exception as e:
                        print(f"Error processing file {file_path}: {e}")

    if not all_data:
        print("No data was processed. Check your input directory, file names, and folder structure.")
        return
    
    all_data_filtered = [df for df in all_data if not df.empty]
        
    if not all_data_filtered:
        print("All data was empty after processing. Check file contents.")
        return

    result_df = pd.concat(all_data_filtered, ignore_index=True) # This line throws a warning, it may break in furture versions of Pandas!
    
    try:
        result_df['trial'] = pd.to_numeric(result_df['trial'], errors='coerce').fillna(0).astype(int)
    except Exception as e:
        print(f"Warning: Could not convert 'trial' column to integer. Error: {e}")

    output_filename = os.path.join(OUTPUT_DIR, f"{experiment_ID}_{date}_{cage_ID}_{treatment}.csv")
    
    # Define the desired order of columns
    desired_columns = [
        'protocol_number', 'experiment_ID', 'treatment', 'date', 'cage_ID',
        'unique_ID', 'body_part', 'stimulus', 'side_of_stimulation', 'trial', 'trial_tracking_quality_pct',
        'frame', 'variable', 'value_1', 'value_2', 'likelihood'
    ]
    
    # Filter and reorder columns, adding missing ones if any
    missing_cols = [col for col in desired_columns if col not in result_df.columns]
    for col in missing_cols:
        result_df[col] = None 
        
    result_df = result_df[desired_columns]

    result_df.to_csv(output_filename, index=False)
    print("="*40)
    print(f"Compilation complete! MEGA CSV file saved to: {output_filename}")
    print("="*40)

if __name__ == "__main__":
    main()