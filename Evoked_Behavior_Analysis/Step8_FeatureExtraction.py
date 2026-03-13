import pandas as pd
import numpy as np
import os

# ----- CONFIGURATION -----
# ====================================================================
INPUT_BASE_DIR = r"I:\Projects\orofacial_project\analysis\evoked\large_csv_files"
OUTPUT_DIR = r"I:\Projects\orofacial_project\analysis\evoked\summary_csv_files\expanded_features"

FPS = 62  # Match your video capture rate, MAKE SURE TO CHECK THIS!!
stim_frame = 2100  # 1050 or 2100 or 3600 (EARLIEST PROJECT DATA WAS 1050 or 3600!!) 

# Windows (in seconds converted to frames)
BASELINE_SEC = 2
POST_STIM_SEC = 2
AUC_WINDOW_SEC = 15
SNAP_WINDOW_SEC = 0.3 
ACTIVE_THRESH = 5 # mm/s
SIDE_ORDER = ['Right', 'Left']

# ====================================================================

def find_experiment_csv(base_dir: str, number_input: str):
    """
    Searches base_dir for a CSV file starting with 'Exp' + number_input.
    """
    prefix = f"Exp{number_input}"
    matches = []
    
    if not os.path.isdir(base_dir):
        print(f"Error: Directory does not exist: {base_dir}")
        return None
        
    for item in os.listdir(base_dir):
        # Change: Check if it's a file AND ends with .csv AND starts with our prefix
        if os.path.isfile(os.path.join(base_dir, item)):
            if item.startswith(prefix) and item.lower().endswith('.csv'):
                matches.append(item)
            
    if len(matches) == 1:
        return matches[0]
    elif len(matches) > 1:
        print(f"ERROR: Multiple CSVs found for '{prefix}': {matches}")
        return None
    else:
        print(f"ERROR: No CSV file found starting with '{prefix}' in {base_dir}")
        return None

def get_experiment_csv_path():
    """
    Prompts user for ID, finds the CSV, and returns the full path.
    """
    print(f"\nSearching for experiment CSV in: {INPUT_BASE_DIR}")
    
    number_input = input("Enter the 3-digit Experiment ID (e.g., '001'), or 'q' to quit: ").strip().lower()
    
    if number_input in ['done', 'q']:
        return "QUIT"
    
    # Pad to 3 digits (e.g., '1' -> '001')
    exp_id = number_input.zfill(3)

    file_name = find_experiment_csv(INPUT_BASE_DIR, exp_id)
    
    if file_name:
        full_path = os.path.normpath(os.path.join(INPUT_BASE_DIR, file_name))
        print(f"Found file: {file_name}")
        return full_path
    
    return None


# ====================================================================
# FEATURE CALCULATIONS
# ====================================================================
def calculate_features(group):
    group = group.sort_values('frame')
    
    # Pre-calculate derivative for acceleration
    speed = group['value_1']
    accel = speed.diff() * FPS
    

    group['t_rel'] = (group['frame'] - stim_frame) / FPS
    
    # 1. LATENCY TO RESPONSE
    baseline_data = group[(group['t_rel'] < 0) & (group['t_rel'] >= -BASELINE_SEC)]['value_1']
    thresh = baseline_data.mean() + (0.5 * baseline_data.std()) if len(baseline_data) > 0 else 5
        
    response_window = group[(group['t_rel'] >= 0) & (group['t_rel'] <= POST_STIM_SEC)]
    idx = response_window[response_window['value_1'] > thresh].index
    latency_ms = (response_window.loc[idx[0], 't_rel'] * 1000) if len(idx) > 0 else np.nan

    # 2. VIGOR METRICS (Slope and Accel)
    if not response_window['value_1'].dropna().empty:
        peak_idx = response_window['value_1'].dropna().idxmax()
        peak_speed = response_window['value_1'].max()
        time_to_peak_ms = response_window.loc[peak_idx, 't_rel'] * 1000
        
        # Vigor Slope (Peak Speed / Time to reach it)
        vigor_slope = peak_speed / (time_to_peak_ms / 1000) if time_to_peak_ms > 0 else 0
        max_accel = accel.loc[response_window.index].max()
    else:
        # If the whole 2s window is empty, it safely fills with NaN and MOVES ON
        peak_speed = vigor_slope = max_accel = np.nan

    # 3. SNAP SPEED (300ms Window)
    snap_data = group[(group['t_rel'] >= 0) & (group['t_rel'] <= SNAP_WINDOW_SEC)]
    snap_speed = snap_data['value_1'].max() if not snap_data.empty else np.nan

    # 4. TOTAL DISTANCE & ACTIVITY
    auc_window = group[(group['t_rel'] >= 0) & (group['t_rel'] <= AUC_WINDOW_SEC)]
    raw_dist = auc_window['value_1'].sum() * (1/FPS)
    coverage = auc_window['value_1'].notna().mean()
    total_dist_corrected = (raw_dist / coverage) if coverage > 0.1 else np.nan
    is_active = (auc_window['value_1'] > ACTIVE_THRESH).mean() * 100

    # 5. TRACKING CONFIDENCE (Average Likelihood)
    avg_likelihood = group['likelihood'].mean() if 'likelihood' in group.columns else np.nan


    return pd.Series({
        'latency_to_respond_ms': latency_ms,
        'head_snap_speed_300ms': snap_speed,
        'peak_speed_2s': peak_speed,
        'vigor_slope_mm_s2': vigor_slope,
        'max_accel_mm_s2': max_accel,
        'total_distance_mm': total_dist_corrected,
        'pct_time_active': is_active,
        'trial_tracking_quality': avg_likelihood
    })


def main():
    while True:
        INPUT_FILE = get_experiment_csv_path()

        if INPUT_FILE == "QUIT" or INPUT_FILE is None:
            return  # Exit  if user quits or file isn't found

        print("Loading Compiled CSV...")
        df = pd.read_csv(INPUT_FILE)

        # --- Extract Metadata for Output Filenames ---
        treatment_label = df['treatment'].iloc[0] if 'treatment' in df.columns else "Unknown"
        cage_label = df['cage_ID'].iloc[0] if 'cage_ID' in df.columns else "Unknown"
        date_label = df['date'].iloc[0] if 'date' in df.columns else "Unknown"
        ExpID_label = df['experiment_ID'].iloc[0] if 'experiment_ID' in df.columns else "Unknown"


        # Filter for nose speed
        df_nose = df[(df['body_part'] == 'nose') & (df['variable'] == 'speed_mm_s')].copy()

        print(f"Extracting features for {cage_label} ({treatment_label})...")

    
        trial_results = (df_nose.groupby(['unique_ID', 'treatment', 'trial', 'stimulus', 'side_of_stimulation'])
                            .apply(calculate_features, include_groups=False)
                            .reset_index())

        # The Sorting Step (organizes output files to make it easier to copy into prism)
        SIDE_ORDER = ['Right', 'Left']
        trial_results['side_of_stimulation'] = pd.Categorical(trial_results['side_of_stimulation'], 
                                                                categories=SIDE_ORDER, ordered=True)
        trial_results = trial_results.sort_values(by=['side_of_stimulation', 'unique_ID', 'trial'])

        # --- Save Trial Data with EXP_ID, date, cage_ID, treatment name ---
        trial_filename = f"{ExpID_label}_{date_label}_{cage_label}_{treatment_label}_TrialSummary.csv"
        trial_output = os.path.join(OUTPUT_DIR, trial_filename)
        trial_results.to_csv(trial_output, index=False)

        # The Summary Step
        subject_summary = (trial_results.groupby(['unique_ID', 'treatment', 'stimulus', 'side_of_stimulation'], observed=True)
                            .agg({
                                'latency_to_respond_ms': 'mean',
                                'head_snap_speed_300ms': 'mean',
                                'peak_speed_2s': 'mean',
                                'vigor_slope_mm_s2': 'mean',
                                'max_accel_mm_s2': 'mean',
                                'total_distance_mm': 'mean',
                                'pct_time_active': 'mean',
                                'trial_tracking_quality': 'mean'
                            }).reset_index())
        
        subject_summary = subject_summary.sort_values(by=['side_of_stimulation', 'stimulus', 'unique_ID'])

        # --- Save Subject Data with EXP_ID, date, cage_ID, treatment name ---
        subject_filename = f"{ExpID_label}_{date_label}_{cage_label}_{treatment_label}_SubjectSummary.csv"
        subject_output = os.path.join(OUTPUT_DIR, subject_filename)
        subject_summary.to_csv(subject_output, index=False)

        print("="*40)
        print(f"Analysis complete. Files saved to {OUTPUT_DIR}:")
        print(f" 1. {trial_filename}")
        print(f" 2. {subject_filename}")
        print("="*40)

     # --- RE-RUN PROMPT ---
        repeat = input("\n Would you like to analyze another file? (y/n): ").strip().lower()
        if repeat != 'y':
            print("Closing program. Good luck with the data!")
            break


if __name__ == "__main__":
    main()