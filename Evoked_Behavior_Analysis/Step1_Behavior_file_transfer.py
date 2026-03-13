import os
import shutil
import csv
from pathlib import Path

# ----- USER CONFIGURATION -----
# ====================================================================
# Base directory where transferred experiment folders land
INPUT_BASE_DIR = r"I:\Projects\orofacial_project\data"

# Metadata file  that tracks all Experiments
GLOBAL_METADATA_PATH = os.path.join(
    INPUT_BASE_DIR,
    'OPexperiment_metadata.csv'
)

# ====================================================================



# ====================================================================
# FIND EXPERIMENT FOLDER
# ====================================================================

def get_existing_folders(metadata_path: str):
    """Reads the existing full_folder_name entries from the metadata CSV to prevent duplicates."""
    existing_folders = set()
    if os.path.exists(metadata_path):
        try:
            with open(metadata_path, 'r', newline='') as f:
                reader = csv.reader(f)
                header = next(reader)
                if 'full_folder_name' in header:
                    folder_name_index = header.index('full_folder_name')
                    for row in reader:
                        if len(row) > folder_name_index:
                            existing_folders.add(row[folder_name_index])
        except Exception as e:
            print(f"ERROR: Could not read existing metadata for duplicate check: {e}")
            pass
    return existing_folders

def update_global_metadata_csv(exp_folder_name: str, metadata_path: str, has_evoked_data: bool, has_spontaneous_data: bool):
    """
    Parses the experiment folder name and appends the data to the global metadata CSV,
    including flags for the presence of evoked and spontaneous data.

    Expected folder name format: 'ExpID_Date_week#_Treatment_cageIDs' Example: 'Exp005_2025-october-28_wk0_baseline_K-L'
    """

    parts = exp_folder_name.split('_')
    
    if len(parts) < 5:
        print("ERROR: Skipping global metadata update: Folder name format is incorrect.")
        return

    # Check for Duplicates
    existing_folders = get_existing_folders(metadata_path)
    if exp_folder_name in existing_folders:
        print(f"ERROR: Metadata for '{exp_folder_name}' already exists in CSV.")
        return

    # Prepare data
    experiment_data = {
        'experiment_ID': parts[0],
        'date': parts[1],
        'week_post_injury' : parts[2],
        'treatment': parts[3],
        'cages_tested': parts[4],
        'has_evoked_data': str(has_evoked_data),       
        'has_spontaneous_data': str(has_spontaneous_data),
        'full_folder_name': exp_folder_name,
    }
    
    # Append data to metadata CSV
    try:
        write_header = not os.path.exists(metadata_path)
        if os.path.exists(metadata_path) and not write_header:
            # Re-read to check if file is empty or header is missing, ensuring proper header write
            with open(metadata_path, 'r', newline='') as f:
                reader = csv.reader(f)
                try:
                    next(reader) # Try to read the header row
                except StopIteration:
                    write_header = True # File is empty
                except Exception:
                    write_header = True # Reading failed, assume no header

        with open(metadata_path, 'a', newline='') as f:
            fieldnames = list(experiment_data.keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            
            if write_header:
                writer.writeheader()
                
            writer.writerow(experiment_data)
        
        print(f"Added {exp_folder_name} to the orofacial pain experiment list!")

    except Exception as e:
        print(f"ERROR: Failed to update global metadata CSV: {e}")

# ====================================================================
# FILE TRANSFER LOGIC
# ====================================================================

def transfer_vf_experiment(experiment_id):
    """
    Transfers specific experiment files from a source experiment directory (External Drive) to a local machine,
    creating destination folders (Evoked/Spontaneous) only if the corresponding data types are present, and
    updates the global metadata CSV with the experiment info.
    """

    # Source & deposit (root) paths, edit if on new machine or directory structure!!!
    source_root = Path(r"J:\Projects\orofacial_pain_project\data\orofacial_pain_setup\raw_files")
    target_evoked_root = Path(r"I:\Projects\orofacial_project\data\evoked\raw_files")
    target_spontaneous_root = Path(r"I:\Projects\orofacial_project\data\spontaneous\raw_files")

    # Find the correct source directory
    source_dir = None
    exp_prefix = f"Exp{experiment_id}"
    for item in source_root.iterdir():
        if item.is_dir() and item.name.startswith(exp_prefix):
            source_dir = item
            break
            
    if not source_dir:
        print(f"ERROR: No directory found starting with '{exp_prefix}' in {source_root}")
        return

    exp_folder_name = source_dir.name
    
    # Pre-scan the source directory to determine data presence (evoked and/or spontaneous data)
    has_evoked_data = False
    has_spontaneous_data = False
    source_files = os.listdir(source_dir)
    
    for item_name in source_files:
        item_name_lower = item_name.lower()
        if "spontaneous" in item_name_lower or "spont" in item_name_lower:
            has_spontaneous_data = True
        elif item_name_lower.endswith('.avi') or item_name_lower.endswith('.csv'):
            has_evoked_data = True

    # Create destination directories ONLY if data is present
    target_evoked_dir = None
    target_spontaneous_dir = None

    if has_evoked_data:
        target_evoked_dir = target_evoked_root / exp_folder_name
        target_evoked_dir.mkdir(parents=True, exist_ok=True)
        print(f"Evoked data discovered!")
    
    if has_spontaneous_data:
        target_spontaneous_dir = target_spontaneous_root / exp_folder_name
        target_spontaneous_dir.mkdir(parents=True, exist_ok=True)
        print(f"Spontaneous data discovered!")

    if not has_evoked_data and not has_spontaneous_data:
        print("ERROR: No evoked nor spontaneous files found :(")
        return

    print(f"\n--- Transferring files from {exp_folder_name} ---")

    # Iterate and transfer files
    for item_name in source_files:
        source_item_path = source_dir / item_name
        
        if source_item_path.is_dir():
            continue

        item_name_lower = item_name.lower()
        
        # Strip everything after the first space for .avi files (This removes the date from filename that ICcapture puts on video files)
        if item_name_lower.endswith('.avi'):
            name_part = item_name.split(' ')[0]
            new_item_name = f"{name_part}.avi"
        else:
            new_item_name = item_name

        if ("spontaneous" in item_name_lower or "spont" in item_name_lower) and target_spontaneous_dir:
            destination_path = target_spontaneous_dir / new_item_name
            print(f"Copying spontaneous video: {new_item_name}")
            shutil.copy2(source_item_path, destination_path)
        elif (item_name_lower.endswith('.avi') or item_name_lower.endswith('.csv')) and target_evoked_dir:
            destination_path = target_evoked_dir / new_item_name
            # Check for evoked file types
            if item_name_lower.endswith('.avi'):
                print(f"Copying evoked video: {new_item_name}")
            elif item_name_lower.endswith('.csv'):
                print(f"Copying evoked CSV file: {new_item_name}")
            shutil.copy2(source_item_path, destination_path)

    print("\nFile Transfer complete.")
    
    # Update metadata with data presence flags
    update_global_metadata_csv(exp_folder_name, GLOBAL_METADATA_PATH, has_evoked_data, has_spontaneous_data)


# ====================================================================
# MAIN
# ====================================================================

def main():
    print("Orofacial Pain Experiment File Transfer Tool")
    print("="*40)
    while True:
        experiment_id = input("Enter the experiment ID you wish to transfer (ex. '001' for Exp001): ").strip()
        print("="*40)
        
        if not experiment_id.isdigit():
            print("ERROR: Input must be the numeric part of the experiment ID (e.g., '001').")
            return
            
        transfer_vf_experiment(experiment_id.zfill(3))
        run_again = input("Do you wish to transfer another experiment folder (yes/no): ").strip()
        if run_again != 'yes':
            print("Process Complete! :) ")
            break

if __name__ == "__main__":
    main()