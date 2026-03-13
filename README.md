# Facial Pain Analysis

This repository stores scripts used in the analysis of mouse facial pain behaviors. 

## Modules

Within the 'Evoked Behavior Analysis' module:

- `Step1_Behavior_file_transfer` : Used for transfering data files from an external drive to the machine running analysis
- `Step2_SaleaeCSVCompiler` : Takes both csv files (digital & analog) from Saleae logic analyzer to pull out stimulus delivery events
- `Step3_FrameCorrection` : Manually validate stimulus delivery events
- `Step4_evoked_clip_trim` : Batch trimmming of evoked clips across multiple mice
- `Step5_DLC_Evoked_labelling` : Batch DeepLabCut(DLC) labelling script
- `Step6_Keypoint_Metrics` : Calculate kinematic values from DLC csv files
  - `Step6.1_Metrics_Calculations` : Called by Step6 script, contains kinematic math
- `Step7_longReadCSV_compiler` : Concatenates kinematic data from all mice/trials into a single long read csv for analysis
- `Step8_FeatureExtraction` : Extract behavior features from the long read csv file


## Contact

This analysis was created by the Xiaobing Yu Lab at University of California, San Francisco

Darian Mohsenin

Email: darian.mohsenin@ucsf.edu 

GitHub: dmohsenin
