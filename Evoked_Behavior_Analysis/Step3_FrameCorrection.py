import pandas as pd
import os
import time
import cv2
import tkinter as tk
from tkinter import filedialog
from tkinter import ttk
import re 



# ====================================================================
# FRAME CORRECTION OF STIMULUS VIDEOS
# ====================================================================

def read_csv(file_path):
    """Read the CSV file into a pandas DataFrame."""
    if not os.path.exists(file_path):
        print(f"Error: The file at {file_path} does not exist.")
        return None
    return pd.read_csv(file_path)

def detect_hit_counter_changes(df):
    """Find the rows where the Hit Counter changes value."""
    # Ensure 'Hit' column is numeric
    df['Hit'] = pd.to_numeric(df['Hit'], errors='coerce').fillna(0).astype(int)
    changes = df[df['Hit'].diff().ne(0)]
    return changes

def open_video_at_frame(video_path, frame_number):
    """Open the video at a specified frame using OpenCV."""
    cap = cv2.VideoCapture(video_path)

    if not cap.isOpened():
        print(f"Error: Could not open the video file {video_path}")
        return None

    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

    return cap

def show_frame_with_counter(cap, current_frame, hit_count, stimulus, video_name):
    """Read and display the current frame from the video capture object with a frame counter, hit count, and stimulus value."""
    ret, frame = cap.read()
    if ret:
        font = cv2.FONT_HERSHEY_SIMPLEX
        # Code for overlying important info on frame correction window
        cv2.putText(frame, f"{video_name} - Frame: {current_frame}", (10, 30), font, 1, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, f"{video_name} - Frame: {current_frame}", (10, 30), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"Hit: {hit_count}", (10, 60), font, 1, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, f"Hit: {hit_count}", (10, 60), font, 1, (255, 255, 255), 2, cv2.LINE_AA)
        cv2.putText(frame, f"Stimulus: {stimulus}", (10, 90), font, 1, (0, 0, 0), 4, cv2.LINE_AA)
        cv2.putText(frame, f"Stimulus: {stimulus}", (10, 90), font, 1, (255, 255, 255), 2, cv2.LINE_AA)

        cv2.imshow(video_name, frame)
    else:
        print(f"Error: Could not read the frame from {video_name}.")

    return ret

def save_corrected_frame(corrected_frames, df, output_csv, updated_hit_counts):
    """Save the corrected frame numbers into a new CSV file without duplicates and manage the hit count logic."""
    corrected_data = []

    if os.path.exists(output_csv):
        try:
            existing_data = pd.read_csv(output_csv)
            existing_frames = set(existing_data['original frame'])
            if not existing_data.empty:
                last_hit_count = existing_data['Hit'].max()
            else:
                last_hit_count = 0
        except pd.errors.EmptyDataError:
             existing_data = pd.DataFrame()
             existing_frames = set()
             last_hit_count = 0
    else:
        existing_data = pd.DataFrame()
        existing_frames = set()
        last_hit_count = 0

    sorted_frames = sorted(corrected_frames.items(), key=lambda x: x[0])
    for original_frame, (corrected_frame, stimulation_side, bad_stimulation, stimulus_override) in sorted_frames:
        if original_frame in existing_frames:
            continue

        row = df[df['Frame'] == original_frame]
        if not row.empty:
            stimulus = stimulus_override if stimulus_override is not None else row.iloc[0]['Stimulus']

            # Only increment hit count for a newly saved event
            last_hit_count += 1

            corrected_data.append([stimulus, last_hit_count, original_frame, corrected_frame,
                                   stimulation_side, bad_stimulation])

    if corrected_data:
        corrected_df = pd.DataFrame(corrected_data,
                                    columns=['Stimulus', 'Hit', 'original frame', 'Frame',
                                             'Side of Stimulation', 'Bad stimulation'])

        # Append new data to the existing file or create a new one
        corrected_df.to_csv(output_csv, mode='a', header=not os.path.exists(output_csv) or existing_data.empty, index=False)
        print(f"Corrected frame saved.")
    else:
        print("No corrected frames to save.")



# ====================================================================
# DIRECTORY/FILE SELECTION
# ====================================================================

# Tkinter based GUI 
class VideoCorrectionApp:
    # Class-level dictionary to store details for easy lookup
    video_details = {} 
    current_dir = ""

    def __init__(self, master):
        self.master = master
        self.master.title("Video Frame Corrector")

        # Variables for selected files
        self.selected_subject = tk.StringVar(master)
        self.csv_file = ''
        self.video_file = ''
        self.output_csv = ''
        self.video_name = ''

        self.create_widgets()

    def create_widgets(self):
        # 1. Directory selection
        self.dir_label = tk.Label(self.master, text="Select Directory with Files:")
        self.dir_label.grid(row=0, column=0, padx=10, pady=5, sticky='w')
        self.dir_button = tk.Button(self.master, text="Browse Folder", command=self.load_directory)
        self.dir_button.grid(row=0, column=1, padx=10, pady=5, sticky='e')

        # 2. Subject selection dropdown menu
        self.subject_label = tk.Label(self.master, text="Select Subject to Process:")
        self.subject_label.grid(row=1, column=0, padx=10, pady=5, sticky='w')

        self.subject_combobox = ttk.Combobox(self.master, textvariable=self.selected_subject, state='disabled')
        self.subject_combobox.grid(row=1, column=1, padx=10, pady=5, sticky='ew')
        self.subject_combobox.bind("<<ComboboxSelected>>", self.on_subject_selected)
        
        # 3. status
        self.status_label = tk.Label(self.master, text="Status: Ready, select a folder.", fg="blue")
        self.status_label.grid(row=2, column=0, columnspan=2, padx=10, pady=5)

        # 4. Start button
        self.start_button = tk.Button(self.master, text="Start Correction", command=self.start_video, state='disabled')
        self.start_button.grid(row=3, column=0, columnspan=2, pady=10)

    def load_directory(self):
        """Open dialog to select a directory and then scan for videos."""
        selected_dir = filedialog.askdirectory()
        if not selected_dir:
            self.status_label.config(text="Status: No directory selected.", fg="red")
            return

        VideoCorrectionApp.current_dir = selected_dir
        self.status_label.config(text=f"Scanning: {os.path.basename(selected_dir)}...", fg="blue")
        self.scan_videos()

    def scan_videos(self):
        """Scans the selected directory, extracts subject IDs, and populates the dropdown."""
        VideoCorrectionApp.video_details = {}
        unique_subjects = []
        
        # Regex to find the filename parts for file matching
        # "subjectID-cageID_evoked_roundID_bayID.avi" (ex: 1L-K_evoked_r1_b1.avi)
        video_pattern = re.compile(r'(.+?)_evoked_(r\d+?)_(b\d+?)\.(avi|mp4)$', re.IGNORECASE)

        for filename in os.listdir(VideoCorrectionApp.current_dir):
            match = video_pattern.match(filename)
            
            if match:
                subject_id, round_id_short, bay_id_short, _ = match.groups()
                full_video_path = os.path.join(VideoCorrectionApp.current_dir, filename)
                
                # Check for corresponding CSV file
                csv_filename = f"Compiled-Saleae-Data-Hits_{bay_id_short}_{round_id_short}.csv"
                full_csv_path = os.path.join(VideoCorrectionApp.current_dir, csv_filename)

                if os.path.exists(full_csv_path):
                    # Store all necessary details for the run under the subject ID
                    VideoCorrectionApp.video_details[subject_id] = {
                        'video_path': full_video_path,
                        'csv_path': full_csv_path,
                        'output_path': os.path.join(VideoCorrectionApp.current_dir, f"{subject_id}_corrected_frames.csv"),
                        'video_name': filename,
                        'round_id': round_id_short,
                        'bay_id': bay_id_short
                    }
                    if subject_id not in unique_subjects:
                        unique_subjects.append(subject_id)
                else:
                    print(f"Warning: Missing CSV {csv_filename} for video {filename}")

        if unique_subjects:
            self.subject_combobox['values'] = unique_subjects
            self.subject_combobox.set("Select a Subject")
            self.subject_combobox.config(state='readonly')
            self.start_button.config(state='disabled')
            self.status_label.config(text=f"Status: Found {len(unique_subjects)} subjects. Select one.", fg="green")
        else:
            self.subject_combobox['values'] = []
            self.subject_combobox.set("No Subjects Found")
            self.subject_combobox.config(state='disabled')
            self.start_button.config(state='disabled')
            self.status_label.config(text="Status: No matching video/CSV sets found.", fg="red")

    def on_subject_selected(self, event):
        """Updates the status and enables the start button when a subject is chosen."""
        subject_id = self.selected_subject.get()
        if subject_id and subject_id in VideoCorrectionApp.video_details:
            details = VideoCorrectionApp.video_details[subject_id]
            self.video_file = details['video_path']
            self.csv_file = details['csv_path']
            self.output_csv = details['output_path']
            self.video_name = details['video_name']

            # Check if an output file already exists to warn the user
            if os.path.exists(self.output_csv) and os.path.getsize(self.output_csv) > 0:
                 self.status_label.config(text=f"Ready to process {subject_id}. NOTE: Output file already exists. Will append/skip completed frames.", fg="orange")
            else:
                 self.status_label.config(text=f"Ready to process {subject_id}. Output will be saved to {os.path.basename(self.output_csv)}.", fg="green")
            
            self.start_button.config(state='normal')
        else:
            self.start_button.config(state='disabled')
            self.status_label.config(text="Status: Please select a valid subject.", fg="red")


    def start_video(self):
        """Start video correction using the selected subject's files."""
        subject_id = self.selected_subject.get()
        if not subject_id or subject_id not in VideoCorrectionApp.video_details:
            print("Please select a subject to process.")
            self.status_label.config(text="Status: Please select a subject.", fg="red")
            return

        print(f"Starting correction for Subject ID: {subject_id}")
        
        try:
            df = read_csv(self.csv_file)
            if df is None:
                return
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return

        # Hide Tkinter window while correcting frames
        self.master.withdraw() 
        
        print("\nCSV file loaded successfully.")
        print("------------------------------")
        print("Keybindings:")
        print("n - next frame")
        print("p - previous frame")
        print("m - jump 100 frames forward") 
        print("o - jump 100 frames backward") 
        print("q - skip stimulation")
        print("c - save corrected stimulation frame")
        print(", - mark stimulation as LEFT side")
        print(". - mark stimulation as RIGHT side")
        print("x - mark as BAD stimulation (toggle 0/1)")
        print("z - mark Paw response (toggle 0/1)")
        print("1-7 - override stimulation value:")
        print("   1 = 0.008g, 2 = 0.02g, 3 = 0.04g")
        print("   4 = 0.07g, 5 = 0.16g, 6 = Air_Puff")
        print("   7 = other stimulus")
        print("------------------------------")
        print("NOTE: When 'Hit'= 0, skip stimulation with 'q'.")
        print("------------------------------")

        changes = detect_hit_counter_changes(df)
        corrected_frames = {}
        updated_hit_counts = {}

        # Determine last side of stimulation from existing output file for auto-alternating logic
        last_side = None
        if os.path.exists(self.output_csv):
            try:
                existing_output = pd.read_csv(self.output_csv)
                if not existing_output.empty and 'Side of Stimulation' in existing_output.columns:
                    valid_sides = existing_output['Side of Stimulation'].dropna()
                    if not valid_sides.empty:
                        last_side = valid_sides.iloc[-1]
            except pd.errors.EmptyDataError:
                last_side = None

        # Stimulus override mapping
        stimulus_mapping = {
            ord('1'): '0.008g', ord('2'): '0.02g', ord('3'): '0.04g',
            ord('4'): '0.07g', ord('5'): '0.16g', ord('6'): 'Air_Puff',
            ord('7'): 'other stimulus'
        }

        if changes.empty:
            print("No hit counter changes detected in the CSV. Exiting.")
            self.master.deiconify() 
            return

        # Read existing frames from the output CSV to skip them
        existing_frames_to_skip = set()
        if os.path.exists(self.output_csv):
             try:
                existing_output = pd.read_csv(self.output_csv)
                if 'original frame' in existing_output.columns:
                    existing_frames_to_skip = set(existing_output['original frame'].values)
             except pd.errors.EmptyDataError:
                pass


        # Main loop through all detected changes
        for index, row in changes.iterrows():
            original_frame = row['Frame']
            
            # Skip if the original frame is already in the output file
            if original_frame in existing_frames_to_skip:
                 print(f"Skipping frame {original_frame} for {subject_id}. Already corrected.")
                 continue

            hit_count = row['Hit']
            original_stimulus = row['Stimulus']
            
            print(f"\n--- Processing frame {original_frame} (Hit: {hit_count}) ---")

            cap = open_video_at_frame(self.video_file, original_frame)
            if cap is None:
                cv2.destroyAllWindows()
                self.master.deiconify()
                return

            current_frame = original_frame
            stimulation_side = None
            bad_stimulation = 0
            paw_response = 0 # Not used anymore but kept this just in case to ensure it stays at zero
            stimulus_override = None

            show_frame_with_counter(cap, current_frame, hit_count, original_stimulus, "Video")
            
            # Frame Correction Loop (user runs through video frames and selects the frame-of-stimulation)
            while True:
                # Keybindings below!
                key = cv2.waitKey(10) & 0xFF

                if key == ord('n'):
                    current_frame += 1
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
                    show_frame_with_counter(cap, current_frame, hit_count,
                                             stimulus_override if stimulus_override else original_stimulus,
                                             "Video")
                elif key == ord('p'):
                    current_frame = max(0, current_frame - 1) 
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
                    show_frame_with_counter(cap, current_frame, hit_count,
                                             stimulus_override if stimulus_override else original_stimulus,
                                             "Video")
                elif key == ord('m'): 
                    current_frame += 100
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
                    show_frame_with_counter(cap, current_frame, hit_count,
                                             stimulus_override if stimulus_override else original_stimulus,
                                             "Video")
                elif key == ord('o'):
                    current_frame = max(0, current_frame - 100) 
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
                    show_frame_with_counter(cap, current_frame, hit_count,
                                             stimulus_override if stimulus_override else original_stimulus,
                                             "Video")
                elif key == ord(','):
                    stimulation_side = 'left'
                    print(f"Stimulation side set to LEFT")
                elif key == ord('.'):
                    stimulation_side = 'right'
                    print(f"Stimulation side set to RIGHT")
                elif key == ord('x'):
                    bad_stimulation = 1 if bad_stimulation == 0 else 0
                    print(f"Bad stimulation set to {bad_stimulation}")
                elif key in stimulus_mapping:
                    stimulus_override = stimulus_mapping[key]
                    print(f"Stimulus overridden to: {stimulus_override}")
                elif key == ord('c'):
                    # Save/Correct logic
                    if stimulation_side is None:
                        # Auto-set logic: alternate from last_side
                        if last_side == 'left':
                            stimulation_side = 'right'
                        elif last_side == 'right':
                            stimulation_side = 'left'
                        else:
                            stimulation_side = 'left' # Default
                        print(f"Auto-set stimulation side to {stimulation_side}")

                    corrected_frames[original_frame] = (current_frame, stimulation_side, bad_stimulation, stimulus_override)
                    print(f"Frame corrected to {current_frame}. Side: {stimulation_side}. Bad: {bad_stimulation}. Stimulus: {stimulus_override if stimulus_override else original_stimulus}")
                    print("------------------------------\n")
                    last_side = stimulation_side
                    break
                elif key == ord('q'):
                    print("Skipping this stimulation event and moving to the next one.")
                    break
                
                # Update frame with any annotation changes (important for showing current state)
                if key in [ord(','), ord('.'), ord('x'), ord('z')] or key in stimulus_mapping:
                    cap.set(cv2.CAP_PROP_POS_FRAMES, current_frame)
                    show_frame_with_counter(cap, current_frame, hit_count,
                                            stimulus_override if stimulus_override else original_stimulus,
                                            "Video")


            cap.release() 
            cv2.destroyWindow("Video") # Close the current video window

        # Save all corrections after 'frame correction' loop finishes
        save_corrected_frame(corrected_frames, df, self.output_csv, updated_hit_counts)

        print("------------------------------")
        print(f"Correction process finished for {subject_id}. Corrected CSV saved to {self.output_csv}.")
        print("------------------------------")
        
        # Show Tkinter window again and update status
        self.master.deiconify()
        self.status_label.config(text=f"Status: Correction finished for {subject_id}. Select another subject.", fg="purple")


# open Tkinter window
if __name__ == "__main__":
    root = tk.Tk()
    root.grid_columnconfigure(1, weight=1)
    app = VideoCorrectionApp(root)
    root.mainloop()