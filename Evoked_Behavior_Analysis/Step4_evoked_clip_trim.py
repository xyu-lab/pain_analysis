import pandas as pd
import os
import subprocess
import logging
import csv
import re
from collections import defaultdict
from typing import Dict, Tuple, Optional, Set


# ----- USER CONFIGURATION -----
# ====================================================================

# BASE DIRECTORIES
# Hardcoded base directory where all experiment folders reside.
INPUT_BASE_DIR = r"I:\Projects\orofacial_project\data\evoked\raw_files"
# Hardcoded base directory where all processed results will be saved.
OUTPUT_BASE_DIR = r"I:\Projects\orofacial_project\data\evoked\processed_files"

# GLOBAL METADATA FILE LOCATION (Saved one level up from processed experiment folders)
GLOBAL_METADATA_PATH = os.path.join(
    r"I:\Projects\orofacial_project\data\evoked\raw_files",
    'experiment_metadata.csv'
)

# ====================================================================



# FFmpeg and Logging
FFMPEG_PATH = r"C:\Users\dmohsenin\Desktop\ffmpeg\bin\ffmpeg.exe"   # FFMPEG path, change if on a different machine!!
LOG_FILENAME = 'batch_trimming_log.txt'
VIDEO_EXTENSION = ".avi"
VIDEO_KEYWORD = "evoked"

# Setup basic logging configuration
logging.basicConfig(
    filename=LOG_FILENAME,
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


# ----- Match behavior ".avi" videos to corrected frames ".csv" files by unique_ID -----

def extract_id_from_filename(filename: str) -> Optional[str]:
    """
    Extracts the ID as the first segment of the filename when split by '_'.
    
    Example: 'Mouse102A_evoked_Trial1.avi' -> 'Mouse102A'
    """
    # Remove extension first to ensure clean split
    base_name = os.path.splitext(filename)[0]
    
    # Split by '_' and return the first element
    parts = base_name.split('_')
    
    # Ensure there is at least one part (i.e., not an empty filename)
    if parts and parts[0]:
        return parts[0]
    return None

def find_file_matches(input_dir: str) -> Dict[str, Tuple[str, str]]:
    """
    Scans the input directory and performs a strict one-to-one match of 
    'evoked' AVIs and CSVs based on the extracted ID (first part of filename).
    """
    logging.info(f"Scanning input directory: {input_dir}. ID logic: first segment split by '_'.")
    print("\n--- Scanning for ID Matches (First Segment Split by '_') ---")
    
    videos: Dict[str, str] = {}
    csvs: Dict[str, str] = {}  
    
    # 1. Collect all valid files and their extracted IDs
    for filename in os.listdir(input_dir):
        file_path = os.path.join(input_dir, filename)
        if os.path.isdir(file_path): continue
            
        file_id = extract_id_from_filename(filename)
        if not file_id: continue
            
        if filename.lower().endswith(VIDEO_EXTENSION) and VIDEO_KEYWORD in filename.lower():
            videos[file_id] = file_path
        elif filename.lower().endswith(".csv"):
            csvs[file_id] = file_path

    matches: Dict[str, Tuple[str, str]] = {}
    
    # 2. Perform Strict One-to-One Matching
    for file_id, video_path in videos.items():
        if file_id in csvs:
            csv_path = csvs[file_id]
            matches[file_id] = (video_path, csv_path)
        
    print(f"\nFound {len(matches)} EXACT pairs to process.")
    return matches



# ====================================================================
# TRIM CLIPS OF STIMULUS EVENTS
# ====================================================================

def trim_video_by_frame_count(input_video_path, output_dir, frame_count, fps, before_duration, after_duration, output_filename):
    """Trims a video clip around a given frame count using the hardcoded FFmpeg path."""
    try:
        frame_count = int(frame_count)
        timestamp = frame_count / fps
        
        start_time = max(timestamp - before_duration, 0)
        end_time = timestamp + after_duration

        os.makedirs(output_dir, exist_ok=True)
        output_file = os.path.join(output_dir, output_filename)

        command = [
            FFMPEG_PATH, 
            '-i', input_video_path,
            '-ss', str(start_time),
            '-to', str(end_time),
            '-c:v', 'libx264',
            '-c:a', 'aac',
            '-y',
            output_file
        ]

        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            logging.error(f"Error trimming video for {output_filename}: {result.stderr}")
            print(f"[ERROR] FFmpeg failed for {output_filename}. Check {LOG_FILENAME}.")
            return None, None

        # Calculation of trimmed frame count
        trimmed_duration = end_time - start_time
        new_frame_count = int(trimmed_duration * fps) 
        
        return output_file, new_frame_count

    except FileNotFoundError:
        logging.critical(f"FFmpeg executable not found at '{FFMPEG_PATH}'.")
        print(f"\n[CRITICAL ERROR] FFmpeg not found! Check the path in the script: {FFMPEG_PATH}")
        return None, None
    except Exception as e:
        logging.exception(f"Error during video trimming for frame {frame_count}")
        return None, None


def process_file_pair(
    file_id: str,
    csv_file_path: str, 
    video_path: str, 
    output_dir_base: str,
    before_duration: float, 
    after_duration: float, 
    fps: float
):
    """
    Processes a single CSV and video file pair.
    """
    output_dir_id = os.path.join(output_dir_base, file_id)
    os.makedirs(output_dir_id, exist_ok=True)
    
    print(f"\n--- Processing ID: {file_id} ---")

    try:
        df = pd.read_csv(csv_file_path)
        required_columns = ['Stimulus', 'Hit', 'Frame', 'Side of Stimulation', 'Bad stimulation']
        
        if not all(col in df.columns for col in required_columns):
            missing = [col for col in required_columns if col not in df.columns]
            logging.error(f"CSV {csv_file_path} is missing required columns: {missing}")
            print(f"[SKIP] CSV is missing required columns: {', '.join(missing)}")
            return

        von_frey_counts = defaultdict(int)
        frame_counts_used = []

        for index, row in df.iterrows():
            
            # Replaces spaces with '_' but keeps decimal points (ex. 0.04g)
            von_frey = str(row['Stimulus']).replace(' ', '_') 
            
            original_hit_count = row['Hit']
            von_frey_counts[von_frey] += 1
            current_hit_count = von_frey_counts[von_frey]
                
            frame_count = row['Frame']
            side = 'Left' if str(row['Side of Stimulation']).lower().startswith('l') else 'Right'
            bad_stim = row['Bad stimulation']

            # Build filename: ID_Stimulus_Sequence_Side_Bad.mp4 
            base_name = f"{file_id}_{von_frey}_{current_hit_count}"
            stim_tag = f"_{side}"
            bad_tag = "_bad" if pd.notna(bad_stim) and bad_stim == 1 else ""
            output_filename = f"{base_name}{stim_tag}{bad_tag}.mp4"

            # Create von Frey subfolder
            von_frey_dir = os.path.join(output_dir_id, von_frey)
            
            output_file, new_frame_count = trim_video_by_frame_count(
                video_path, von_frey_dir, frame_count, fps, before_duration, 
                after_duration, output_filename
            )
            
            if output_file:
                frame_counts_used.append((
                    frame_count, 
                    os.path.basename(output_file), 
                    new_frame_count,
                    side,
                    bool(bad_stim),
                    original_hit_count
                ))

        # Save processing metadata
        if frame_counts_used:
            csv_path = os.path.join(output_dir_id, f"{file_id}_metadata.csv")
            with open(csv_path, 'w', newline='') as f:
                writer = csv.writer(f)
                writer.writerow([
                    "Original Frame", "Filename", "Trimmed Frames", 
                    "Side", "Bad Stim", "Original Hit Count"
                ])
                writer.writerows(frame_counts_used)
            print(f"Successfully processed {len(frame_counts_used)} clips. Metadata saved in {file_id} folder.")

    except Exception as e:
        logging.exception(f"Error processing CSV for ID {file_id}")
        print(f"[ERROR] Failed to process ID {file_id}. See {LOG_FILENAME}.")



# ====================================================================
# UNIQUE_ID METADATA FILE (contains video trimming parameters)
# ====================================================================

def update_global_metadata_csv(exp_folder_name: str, metadata_path: str):
    """
    Parses the experiment folder name and appends the data to the global metadata CSV.
    
    Expected format: 'ExpID_Date_Treatment_CageID' 
    Example: 'Exp001_2025-october-24_TEST_t'
    """
    
    # 1. Parse the folder name
    parts = exp_folder_name.split('_')
    
    # Check if the folder name has at least 4 parts
    if len(parts) < 4:
        logging.warning(
            f"Skipping global metadata update for '{exp_folder_name}'. "
            "Folder name must contain at least 4 segments split by '_': ExpID_Date_Treatment_CageID."
        )
        print("[WARNING] Skipping global metadata update: Folder name format is incorrect.")
        return

    # Extract the required fields
    experiment_data = {
        'experiment_ID': parts[0],
        'date': parts[1],
        'treatment': parts[2],
        'cage_ID': parts[3],
        'full_folder_name': exp_folder_name  # I keep the full folder name for reference
    }
    
    # 2. Determine if header is needed
    write_header = not os.path.exists(metadata_path)
    
    # 3. Append data to CSV
    try:
        with open(metadata_path, 'a', newline='') as f:
            writer = csv.writer(f)
            
            # Write header if file is new
            if write_header:
                writer.writerow(list(experiment_data.keys()))
                
            # Write the data row
            writer.writerow(list(experiment_data.values()))
        
        print(f"Appended metadata for {experiment_data['experiment_ID']} to {os.path.basename(metadata_path)}")
        logging.info(f"Appended global metadata for {exp_folder_name}.")

    except Exception as e:
        logging.error(f"Failed to update global metadata CSV: {e}")
        print(f"[ERROR] Failed to update global metadata CSV: {os.path.basename(metadata_path)}")


# ====================================================================
# FIND EXPERIMENT FOLDER
# ====================================================================

def find_experiment_folder(base_dir: str, number_input: str) -> Optional[str]:
    """
    Searches base_dir for a directory that starts with 'Exp' + number_input.
    Returns the full folder name if a unique match is found, otherwise None.
    """
    # Construct the required prefix, e.g., 'Exp001'
    prefix = f"Exp{number_input}"
    
    matches = []
    
    # Check if the base directory exists
    if not os.path.isdir(base_dir):
        return None # Base directory must exist
        
    for item in os.listdir(base_dir):
        full_path = os.path.join(base_dir, item)
        # Check if it is a directory and starts with the required prefix
        if os.path.isdir(full_path) and item.startswith(prefix):
            matches.append(item)
            
    if len(matches) == 1:
        # Unique match found, return the full folder name
        return matches[0]
    elif len(matches) > 1:
        print(f"[INPUT ERROR] Found multiple folders starting with '{prefix}'. Please be more specific.")
        print("Matches found:", matches)
        return None
    else:
        print(f"[INPUT ERROR] No folder found starting with '{prefix}' in {base_dir}")
        return None


# ====================================================================
# MAIN
# ====================================================================

def main():
    """Main application loop to gather parameters and start batch processing."""
    
    print("Clean Batch Video Trimming Tool (Global Metadata)\n" + "="*40)
    print(f"**FFmpeg Path:** {FFMPEG_PATH}")
    print(f"**Input Base:** {INPUT_BASE_DIR}")
    print(f"**Output Base:** {OUTPUT_BASE_DIR}")
    print(f"**Global Metadata:** {GLOBAL_METADATA_PATH}")
    print("="*40)
    
    while True:
        try:
            # Get Experiment Folder Name
            print("\n--- Setup: Experiment Folder ---")
            print(f"Base Input Directory is: {INPUT_BASE_DIR}")
            
            # User only inputs the numeric part (e.g., '001')
            number_input = input("Enter the **Experiment Number** (e.g., '001' for Exp001...): ").strip('"').strip()
            
            if not number_input.isdigit():
                 raise ValueError("Experiment number must be numeric (e.g., '001').")
            
            # Find the full experiment folder name
            exp_folder_name = find_experiment_folder(INPUT_BASE_DIR, number_input)
            
            if not exp_folder_name:
                continue # Go back to the start of the while loop

            # Construct Full Paths
            input_dir = os.path.join(INPUT_BASE_DIR, exp_folder_name)
            main_output_dir = os.path.join(OUTPUT_BASE_DIR, exp_folder_name)
            
            # Create the mirrored output directory structure
            os.makedirs(main_output_dir, exist_ok=True)

            print(f"\nProcessing Folder: {exp_folder_name}")
            print(f"Source: {input_dir}")
            print(f"Destination: {main_output_dir}")
            
            # Trimming Parameters
            print("\n--- Setup: Trimming Parameters (Hardcoded) ---")
            before = 30.0
            after = 30.0
            fps = 70.0
            print(f"Clip Duration: {before}s before trigger, {after}s after trigger. FPS: {fps}")

            if fps <= 0:
                raise ValueError("FPS must be a positive number.")

            print("\n" + "="*40)
            print(f"Starting batch process for experiment: {exp_folder_name}")
            print("="*40)

            # Find file Matches
            matches = find_file_matches(input_dir)
            
            if not matches:
                print("\n[ALERT] No EXACT matching video and CSV file pairs found in the experiment folder.")
            else:
                print(f"\nFound **{len(matches)}** unique pairs to process. Starting trimming...")
            
                for file_id, (video_path, csv_path) in matches.items():
                    process_file_pair(
                        file_id,
                        csv_path, 
                        video_path, 
                        main_output_dir, 
                        before, 
                        after, 
                        fps
                    )
            
            update_global_metadata_csv(exp_folder_name, GLOBAL_METADATA_PATH)


            print("\n" + "="*40)
            if input("Batch processing complete! Process another experiment folder? (y/n): ").lower() != 'y':
                print("Done! Exiting tool. Thank you!")
                break

        except (ValueError, FileNotFoundError) as e:
            print(f"\n[INPUT ERROR] {str(e)}")
            print("Please correct the folder name or check the base paths.")
        except Exception as e:
            print(f"\n[CRITICAL ERROR] An unexpected error occurred. Check {LOG_FILENAME} for details.")
            logging.exception("Main loop error")
            if input("Try again? (y/n): ").lower() != 'y':
                print("Exiting tool.")
                break

if __name__ == "__main__":
    main()