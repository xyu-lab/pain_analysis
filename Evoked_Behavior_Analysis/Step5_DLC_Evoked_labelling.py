import deeplabcut as dlc
import os
import pandas as pd
from tqdm import tqdm
import glob
from typing import Optional

# Run this with deeplabcut environment!!!!!!!!!!!


# ----- USER CONFIGURATION -----
# ====================================================================
# Base directories
evoked_INPUT_BASE_DIR = r"I:\Projects\orofacial_project\data\evoked\processed_files"
spont_INPUT_BASE_DIR = r"I:\Projects\orofacial_project\data\spontaneous\raw_files"

# Select which set of videos to analyze
INPUT_BASE_DIR = evoked_INPUT_BASE_DIR

# DeepLabCut project path (Change this if needed!!)
DLC_PROJECT_PATH = r"C:\Users\dmohsenin\Desktop\DeepLabCut\FEBcam03-Darian-2025-02-24"
CONFIG_FILE = os.path.join(DLC_PROJECT_PATH, 'config.yaml')

# DeepLabCut analysis parameters
CREATE_NEW_VIDEO = True
PCUTOFF = 0.0  # Set to 0 so all model predictions are displayed
VIDEO_EXTENSIONS = ('.mp4', '.mov', '.avi') # Can add more extensions if needed, analysis was completed with .avi files

# ====================================================================



# ====================================================================
# FIND EXPERIMENT FOLDER
# ====================================================================

def find_experiment_folder(base_dir: str, number_input: str) -> Optional[str]:
    """Finds a folder starting with ExpXXX where XXX is number_input."""
    prefix = f"Exp{number_input}"
    matches = []

    if not os.path.isdir(base_dir):
        print(f"Error: Base directory does not exist at {base_dir}")
        return None

    for item in os.listdir(base_dir):
        full_path = os.path.join(base_dir, item)
        if os.path.isdir(full_path) and item.startswith(prefix):
            matches.append(item)

    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"ERROR: Multiple folders found starting with '{prefix}': {matches}")
        return None
    else:
        print(f"ERROR: No folder found starting with '{prefix}' in {base_dir}")
        return None


def find_videos_recursive(exp_dir):
    """Recursively finds all video files, case-insensitive."""
    video_files = []
    for root, _, files in os.walk(exp_dir):
        for file in files:
            if file.lower().endswith(tuple(ext.lower() for ext in VIDEO_EXTENSIONS)):
                full_path = os.path.join(root, file)
                video_files.append(full_path)
    return video_files


# ====================================================================
# DEEPLABCUT ANALYSIS SCRIPT
# ====================================================================

def analyze_videos_and_create_csv(exp_dir, config_file, create_new_video, pcutoff):
    """Analyzes videos with DLC and converts h5 outputs to CSV."""
    exp_dir = os.path.normpath(exp_dir)
    print(f"\nSearching for videos in: {exp_dir}")

    video_files = find_videos_recursive(exp_dir)

    if not video_files:
        print(f"No videos found in {exp_dir}. Check folder contents and file extensions.")
        return

    print(f"Found {len(video_files)} video(s):")
    for v in video_files:
        print(f"  {v}")

    for video_path in tqdm(video_files, desc=f"Analyzing videos in {os.path.basename(exp_dir)}"):
        try:
            video_dir = os.path.dirname(video_path)
            file = os.path.basename(video_path)
            video_type = os.path.splitext(file)[1][1:]

            print(f"\nAnalyzing video: {video_path} (type: {video_type})")
            dlc.analyze_videos(config_file, [video_path], videotype=video_type)

            if create_new_video:
                dlc.create_labeled_video(config_file, [video_path], videotype=video_type, pcutoff=pcutoff)

            # Convert .h5 to CSV
            video_name = os.path.splitext(file)[0]
            h5_files = glob.glob(os.path.join(video_dir, f"{video_name}*DLC*.h5"))

            if h5_files:
                h5_file = h5_files[0]
                try:
                    data = pd.read_hdf(h5_file)
                    csv_file = os.path.join(video_dir, f"{video_name}_dlc_output.csv")
                    data.to_csv(csv_file)
                    print(f"  CSV created: {csv_file}")
                except Exception as e:
                    print(f"  Error reading .h5 or creating CSV for {video_path}: {e}")
            else:
                print(f"  Warning: .h5 file not found for {video_path} after analysis.")

        except Exception as e:
            print(f"  Error analyzing {video_path}: {e}")



# ====================================================================
# MAIN
# ====================================================================

def main():
    """Main workflow for DLC video analysis."""
    if not os.path.exists(CONFIG_FILE):
        print(f"Error: DLC config file not found at {CONFIG_FILE}")
        return

    print(f"Using DLC Config: {CONFIG_FILE}")
    print(f"Video creation: {'ON' if CREATE_NEW_VIDEO else 'OFF'} (pcutoff={PCUTOFF})")

    # Ask user for experiment ID
    number_input = input("Enter the 3-digit Experiment ID (e.g., '001'): ").strip()
    if not number_input.isdigit():
        print("Invalid input. Please enter a numerical experiment ID.")
        return
    exp_id = number_input.zfill(3)

    # Find experiment folder
    folder_name = find_experiment_folder(INPUT_BASE_DIR, exp_id)
    if folder_name is None:
        return

    exp_dir = os.path.join(INPUT_BASE_DIR, folder_name)
    print(f"\nFound experiment folder: {folder_name}")

    # Run analysis
    analyze_videos_and_create_csv(exp_dir, CONFIG_FILE, CREATE_NEW_VIDEO, PCUTOFF)
    print("\nAnalysis complete.")


if __name__ == "__main__":
    main()
