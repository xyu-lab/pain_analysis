import pandas as pd
import numpy as np
import os
import sys

# ==============================================================================
# CONSTANTS
# ==============================================================================
K_VAL = 11  
LIKELIHOOD_THRESHOLD = 0.5
LIKELIHOOD_THRESHOLD_PAWS = 0.2
FPS = 62
MM_PER_PX = 1.0 / 6.86

# ====================================================================
# MATH! MATH! MATH! 
# Originally written in R because it was easier for me, adapted to Python to fit with rest of analysis pipeline
# ====================================================================

def calculate_movement_median(df, bodypart, fps, mm_per_pixel):
    """
    1. Likelihood filtering
    2. Tracking Quality calculation
    3. Median smoothing
    4. Finite difference for Speed/Accel
    """
    
    x_col = f"{bodypart}_x"
    y_col = f"{bodypart}_y"
    l_col = f"{bodypart}_likelihood"
    
    thresh = LIKELIHOOD_THRESHOLD_PAWS if "paw" in bodypart.lower() else LIKELIHOOD_THRESHOLD
    
    # Raw coordinates in mm
    x_raw = df[x_col].astype(float) * mm_per_pixel
    y_raw = df[y_col].astype(float) * mm_per_pixel
    
    # 2. CALCULATE TRACKING QUALITY 
    # Percentage of frames above threshold in the current window
    if l_col in df.columns:
        is_valid = df[l_col] >= thresh
        quality_pct = (is_valid.sum() / len(df)) * 100
        
        # Apply mask
        x_raw[~is_valid] = np.nan
        y_raw[~is_valid] = np.nan
    else:
        quality_pct = np.nan

    # 3. Median Smoothing
    sm_x = x_raw.rolling(window=K_VAL, center=True, min_periods=1).median()
    sm_y = y_raw.rolling(window=K_VAL, center=True, min_periods=1).median()

    dt = 1.0 / fps

    vx = sm_x.diff() / dt
    vy = sm_y.diff() / dt
    speed = np.sqrt(vx**2 + vy**2)
    accel_mag = np.sqrt(vx.diff()**2 + vy.diff()**2) / dt
    
    # Active Time
    is_active = (speed > 5.0).astype(float)

    return pd.DataFrame({
        "frame": df["frame"].values,
        "x_mm": sm_x,
        "y_mm": sm_y,
        "speed_mm_s": speed,
        "acceleration_mm_s2": accel_mag,
        "vx": vx,
        "vy": vy,
        "is_active": is_active,
        "likelihood": df[l_col].values if l_col in df.columns else np.nan, # Raw per-frame
        "trial_tracking_quality_pct": quality_pct # Global per-trial

        })


# ====================================================================
# MAIN
# ====================================================================

def main(input_dir, fps, mm_per_pixel, start_f=None, end_f=None):
    # Walk through directory looking for 'cleaned_csvs'
    csv_files = []
    for root, _, files in os.walk(input_dir):
        if 'cleaned_csvs' in root.lower():
            for f in files:
                if f.endswith('.csv'):
                    csv_files.append(os.path.join(root, f))

    if not csv_files:
        print("No files found in 'cleaned_csvs' folders.")
        return

    for filepath in csv_files:
        try:
            df = pd.read_csv(filepath)
            
            # Optional Frame Clipping
            if start_f is not None and end_f is not None:
                df = df[(df['frame'] >= start_f) & (df['frame'] <= end_f)].copy()
            
            # Identify unique body parts
            bps = {col.split('_')[0] for col in df.columns if '_x' in col}
            
            # Process each part
            for bp in bps:
                res = calculate_movement_median(df, bp, fps, mm_per_pixel)
                
                # Output Setup
                out_dir = os.path.join(os.path.dirname(filepath), f"{bp}_metrics_median")
                os.makedirs(out_dir, exist_ok=True)
                
                fname = os.path.basename(filepath).replace('.csv', f'_{bp}_median.csv')
                res.to_csv(os.path.join(out_dir, fname), index=False)
                print(f"Processed {bp} for {os.path.basename(filepath)}")
                
        except Exception as e:
            print(f"Error in {filepath}: {e}")

if __name__ == "__main__":

    if len(sys.argv) < 2:
        print("Usage: python script.py <input_dir> [start] [end]")
        sys.exit(1)
        
    in_dir = sys.argv[1]
    s_frame = int(sys.argv[2]) if len(sys.argv) > 2 else None
    e_frame = int(sys.argv[3]) if len(sys.argv) > 3 else None
    
    main(in_dir, FPS, MM_PER_PX, s_frame, e_frame)