import os
import glob
import pandas as pd
import matplotlib.pyplot as plt
import re

# 1. Force Python to look in the exact folder where this Python script is saved
folder_path = os.path.dirname(os.path.abspath(__file__))

# 2. Grab ALL CSV files in that folder
csv_files = glob.glob(os.path.join(folder_path, "*.csv"))

# Safety check
if len(csv_files) == 0:
    print(f"CRITICAL ERROR: No CSV files were found in {folder_path}!")
    print("Please make sure your CSV files are in the same folder as this Python script.")
    exit()

print(f"Found {len(csv_files)} CSV files. Processing...")

data_list = []

for file in csv_files:
    base_name = os.path.basename(file)
    
    # Skip the summary file if the script is run multiple times
    if "averaged" in base_name.lower():
        continue
        
    # 3. Extract the angle using regex (handles "0degrees", "45degrees", "360degrees.csv", etc.)
    match = re.search(r"(\d+)", base_name)
    
    if match:
        angle = float(match.group(1))
    else:
        print(f"Skipping '{base_name}': Couldn't find a number in the filename.")
        continue

    # Read the CSV
    try:
        df = pd.read_csv(file)
        
        # Calculate the average for this angle
        avg_data = {
            "angle_deg": angle,
            "x_raw_avg": df["x_raw"].mean(),
            "y_raw_avg": df["y_raw"].mean(),
            "z_raw_avg": df["z_raw"].mean(),
            "x_cal_avg": df["x_cal"].mean(),
            "y_cal_avg": df["y_cal"].mean(),
            "z_cal_avg": df["z_cal"].mean()
        }
        
        data_list.append(avg_data)
        
    except Exception as e:
        print(f"Could not read {base_name}: {e}")

# Safety check
if len(data_list) == 0:
    print("ERROR: Files were found, but no data could be extracted.")
    exit()

# 4. Convert to DataFrame and sort by angle
result_df = pd.DataFrame(data_list)
result_df = result_df.sort_values(by="angle_deg").reset_index(drop=True)

print("\n--- Processing Complete! ---")
print(result_df[["angle_deg", "x_cal_avg", "y_cal_avg", "z_cal_avg"]])

# Save the averaged results
output_file = os.path.join(folder_path, "averaged_magnetometer_data_angles.csv")
result_df.to_csv(output_file, index=False)
print(f"\nResults saved to: {output_file}")

# ---------------------------------------------------------
# 5. Plotting the Calibrated Values
# ---------------------------------------------------------
plt.figure(figsize=(10, 6))
plt.plot(result_df["angle_deg"], result_df["x_cal_avg"], marker='o', label='X Calibrated')
plt.plot(result_df["angle_deg"], result_df["y_cal_avg"], marker='o', label='Y Calibrated')
plt.plot(result_df["angle_deg"], result_df["z_cal_avg"], marker='o', label='Z Calibrated')

plt.xlabel("Angle (degrees)")
plt.ylabel("Magnetic Field (Calibrated)")
plt.title("Average Calibrated Magnetometer Readings vs. Angle")
plt.grid(True)
plt.legend()
plt.xticks(range(0, 361, 45))  # Nice tick marks at every 45°
plt.tight_layout()
plt.show()

# ---------------------------------------------------------
# 6. Plotting the Raw Values
# ---------------------------------------------------------
plt.figure(figsize=(10, 6))
plt.plot(result_df["angle_deg"], result_df["x_raw_avg"], marker='s', linestyle='--', label='X Raw')
plt.plot(result_df["angle_deg"], result_df["y_raw_avg"], marker='s', linestyle='--', label='Y Raw')
plt.plot(result_df["angle_deg"], result_df["z_raw_avg"], marker='s', linestyle='--', label='Z Raw')

plt.xlabel("Angle (degrees)")
plt.ylabel("Magnetic Field (Raw)")
plt.title("Average Raw Magnetometer Readings vs. Angle")
plt.grid(True)
plt.legend()
plt.xticks(range(0, 361, 45))
plt.tight_layout()
plt.show()