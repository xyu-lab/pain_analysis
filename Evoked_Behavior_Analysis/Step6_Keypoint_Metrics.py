import pandas as pd
import os
from tqdm import tqdm
import subprocess
import sys
import shutil
from typing import Optional


# ----- USER CONFIGURATION -----

# Hardcoded base directory where all experiment folders reside.
INPUT_BASE_DIR = r"I:\Projects\orofacial_project\data\evoked\processed_files"

# ====================================================================



# ====================================================================
# FIND EXPERIMENT FOLDER
# ====================================================================

def find_experiment_folder(base_dir: str, number_input: str) -> Optional[str]:
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

def get_experiment_folder_path() -> Optional[str]:
    """
    Prompts the user for a 3-digit Experiment ID, finds the corresponding 
    experiment folder within the hardcoded INPUT_BASE_DIR, and returns 
    the full path to that folder.
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
# CLEAN DEEPLABCUT CSV HEADERS (DLC outputs csv files with annoyingly complicated 3-tier header, this script flattens the header)
# ====================================================================
def extract_body_parts(input_csv_path):
    """Reads the second line of a DLC CSV to extract the base names of tracked body parts."""
    try:
        with open(input_csv_path, 'r', encoding='utf-8-sig') as f:
            lines = [f.readline() for _ in range(3)]

        separator = '\t' if '\t' in lines[0] else ','

        if len(lines) < 2:
            print(f"File too short: {os.path.basename(input_csv_path)}")
            return None

        bodypart_line = lines[1].strip().split(separator)[1:]

        body_parts = []
        for i in range(0, len(bodypart_line), 3):
            if i >= len(bodypart_line):
                break

            full_name = bodypart_line[i]
            base_name = full_name.split('_')[-1].lower()

            if base_name in ['x', 'y', 'likelihood']:
                continue

            body_parts.append(base_name)

        return body_parts if body_parts else None

    except Exception as e:
        print(f"Error reading {os.path.basename(input_csv_path)}: {str(e)}")
        return None

def update_headers(input_csv_path, output_csv_path):
    """Reads the DLC CSV, skips the first 3 header rows, applies new simplified headers, and saves to a new file."""
    try:
        body_parts = extract_body_parts(input_csv_path)
        if not body_parts:
            return False

        try:
            df = pd.read_csv(input_csv_path, skiprows=3, header=None, encoding='utf-8-sig')
        except UnicodeDecodeError:
            try:
                df = pd.read_csv(input_csv_path, skiprows=3, header=None, encoding='latin1')
            except Exception as e:
                print(f"Encoding error in {os.path.basename(input_csv_path)}: {str(e)}")
                return False

        new_header = ['frame']
        for part in body_parts:
            new_header.extend([f"{part}_x", f"{part}_y", f"{part}_likelihood"])

        if len(df.columns) != len(new_header):
            print(f"Column mismatch in {os.path.basename(input_csv_path)}: "
                  f"Expected {len(new_header)} cols, found {len(df.columns)}")
            return False

        df.columns = new_header
        df.to_csv(output_csv_path, index=False)
        return True

    except pd.errors.EmptyDataError:
        print(f"Empty file: {os.path.basename(input_csv_path)}")
        return False
    except Exception as e:
        print(f"Unexpected error with {os.path.basename(input_csv_path)}: {str(e)}")
        return False


# ====================================================================
# CONSOLIDATE DEEPLABCUT OUTPUTS INTO "dlc_outputs" FOLDER
# ====================================================================

def find_data_directories(input_dir, ignore_parent_folders=None):
    """
    Finds all unique directories containing DLC output CSV files within the input_dir.
    """
    if ignore_parent_folders is None:
        ignore_parent_folders = []

    data_dirs = set()
    
    for root, dirs, files in os.walk(input_dir):
        dirs[:] = [d for d in dirs if d not in ignore_parent_folders]
        
        # Look for any CSV file with 'dlc' or 'deeplabcut' in the name
        if any(f.lower().endswith('.csv') and ('dlc' in f.lower() or 'deeplabcut' in f.lower()) for f in files):
            data_dirs.add(root)

    return list(data_dirs)

def consolidate_raw_dlc_outputs(data_directory):
    """
    1. Moves all raw DLC-related files/folders into 'dlc_outputs'.
    """
    dlc_output_folder = os.path.join(data_directory, 'dlc_outputs')
    os.makedirs(dlc_output_folder, exist_ok=True)
    
    moved_count = 0
    deleted_count = 0
    
    # Move Raw DLC Files into dlc_outputs
    for item_name in os.listdir(data_directory):
        source_path = os.path.join(data_directory, item_name)
        
        # Skip the 'dlc_outputs' folder itself and the new 'cleaned_csvs' folder
        if source_path == dlc_output_folder or item_name == "cleaned_csvs":
            continue
            
        # Move anything containing 'DLC' or 'dlc'
        if 'dlc' in item_name.lower():
            try:
                destination_path = os.path.join(dlc_output_folder, item_name)
                if not os.path.exists(destination_path):
                    shutil.move(source_path, destination_path)
                    moved_count += 1
            except Exception as e:
                print(f"Error moving {item_name}: {e}")


    # THIS CODE DELETES THE RAW CSV FILES
    # I used to reduce excessive files;
    # HOWEVER, losing the original DLC files can cause a headache when later analysis steps fail and the pipeline must be run again
#
#    for item_name in os.listdir(dlc_output_folder):
#        source_path = os.path.join(dlc_output_folder, item_name)
#        
#        # Only delete CSV files that are NOT in the 'cleaned_csvs' subfolder
#        if item_name.lower().endswith('.csv') and os.path.isfile(source_path):
#            try:
#                os.remove(source_path)
#                deleted_count += 1
#            except Exception as e:
#                print(f"Error deleting {item_name}: {e}")

    if moved_count > 0 or deleted_count > 0:
#        print(f"    -> Raw outputs moved: {moved_count}, Raw CSVs deleted: {deleted_count}")
        print(f"    -> Raw outputs moved: {moved_count}, Raw CSVs kept! ")

def process_directory(input_directory, ignore_subfolder_names=None):
    """
    Processes all DLC CSVs and saves cleaned files to the 'cleaned_csvs' 
    subfolder within the 'dlc_outputs' directory.
    """
    if ignore_subfolder_names is None:
        ignore_subfolder_names = []

    input_directory = os.path.normpath(input_directory)
    
    dlc_output_root = os.path.join(input_directory, "dlc_outputs")
    output_dir_name = "cleaned_csvs"
    output_root_directory = os.path.join(dlc_output_root, output_dir_name)
    # The final output directory for analysis is the one passed to metrics calculation script
    output_directory = output_root_directory 

    os.makedirs(output_directory, exist_ok=True)

    processed_files = 0
    skipped_files = 0
    error_files = 0

    all_files = []
    current_folder_name = os.path.basename(input_directory)
    
    for root, dirs, files in os.walk(input_directory):
        
        # Exclude the dlc_outputs folder and the cleaned_csvs folder from being walked
        if dlc_output_root in root:
             continue
        
        # Filter out specified subdirectories (like 'bad_videos')
        dirs[:] = [d for d in dirs if d not in ignore_subfolder_names]

        # Collect only DLC CSV files
        for f in files:
            if f.lower().endswith('.csv') and ('dlc' in f.lower() or 'deeplabcut' in f.lower()):
                all_files.append(os.path.join(root, f))


    for input_path in tqdm(all_files, desc=f"Cleaning CSVs in {current_folder_name}", unit='file'):
        rel_path = os.path.relpath(input_path, input_directory)
        output_path = os.path.join(output_directory, rel_path)
        os.makedirs(os.path.dirname(output_path), exist_ok=True)

        result = update_headers(input_path, output_path)
        if result is True:
            processed_files += 1
        elif result is False:
            skipped_files += 1

    print("="*70)
    print(f"Cleaning complete for {current_folder_name}. Files processed: {processed_files}")
    print(f"Cleaned files saved to: {output_directory}")
    print("="*70)

    return output_directory if processed_files > 0 else None



# ====================================================================
# CALL "metrics_calculations_script" TO DO KINEMATIC MATH
# ====================================================================

def run_dist_vel_acc(output_directory):
    """Runs the external motion analysis script on the cleaned data."""
    try:
        script_path = r"J:\Darian\Code\February-2026_Code_Repo\Evoked_Behavior_Analysis\Step6.1_Metrics_Calculations.py"

        if not os.path.exists(script_path):
            raise FileNotFoundError(f"Analysis script not found at {script_path}")

        print(f"\nRunning motion analysis...")
        result = subprocess.run(
            [sys.executable, script_path, output_directory],
            check=True,
            capture_output=True,
            text=True
        )
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)

    except subprocess.CalledProcessError as e:
        print(f"Analysis failed with code {e.returncode}:")
        print(e.stderr)
    except Exception as e:
        print(f"Failed to run analysis: {str(e)}")



# ====================================================================
# MAIN
# ====================================================================

def main():
    print("="*70)
    print("DeepLabCut Outputs Organizer, Cleaner, & Kinematics Calculator")
    print("1. Cleans CSV headers and saves to 'dlc_outputs/cleaned_csvs'.")
    print("2. Consolidates raw DLC files into 'dlc_outputs'.")
    print("3. DELETES raw DLC CSV files from 'dlc_outputs'")
    print("4. Calls Metrics_calculation.py to run kinematic calculations")
    print("="*70 + "\n")

    IGNORE_PARENT_FOLDERS = []
    # Ignore the consolidation folder itself
    IGNORE_SUBFOLDERS_WITHIN_DATA = ["bad_videos", "dlc_outputs"] 

    while True:
        input_dir = get_experiment_folder_path()
        if input_dir.lower() == 'quit':
            break

        if not os.path.exists(input_dir):
            print(f"Error: Directory not found - {input_dir}")
            continue

        data_directories = find_data_directories(input_dir, IGNORE_PARENT_FOLDERS)
        
        if not data_directories:
             print("No DLC data directories found in the specified path.")
             continue

        for data_dir in data_directories:
            print(f"\nProcessing data in: {data_dir}")
            
            # 1. Process and save cleaned CSVs 
            output_dir = process_directory(data_dir, IGNORE_SUBFOLDERS_WITHIN_DATA)
            
            # 2. Consolidate raw DLC files
            consolidate_raw_dlc_outputs(data_dir)

            if output_dir:
                # 3. Run analysis on the newly created cleaned folder
                print(f"\nRunning analysis on cleaned data...")
                run_dist_vel_acc(output_dir)
                

        print("\nAll data folders processed and cleaned.\n")
        print("="*70)

if __name__ == "__main__":
    def extract_cam_type_from_directory(input_directory): return None 
    main()