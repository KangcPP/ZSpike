import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pprint

from structure import Cell, Recording
from processing import *
from spikepursuit import *

data_file = "../all-optical trace.xlsx"
xls = pd.ExcelFile(data_file)

sheets_names = xls.sheet_names
print(sheets_names)

dict_sheets = {sheet_name: xls.parse(sheet_name) for sheet_name in sheets_names}

accept_slice = slice(100, None)
recording_dict = {}
for sheet_name, df in dict_sheets.items():
    time_vector = df[df.columns[0]].to_numpy()[accept_slice]

    cells = []
    for cell_name in df.columns[1:]:
        cell = Cell(
            cell_id = cell_name,
            raw_trace = df[cell_name].to_numpy()[accept_slice]
        )

        cells.append(cell)

    recording = Recording(
        sheet_name = sheet_name,
        time = time_vector,
        cells = cells
    )

    print(recording.sampling_rate)
    recording_dict[sheet_name] = recording


recording = recording_dict[sheets_names[0]]
fs = recording.sampling_rate

for cell in recording.cells:
    cell.interp_trace = clean_artifact(
        time_vector=recording.time,
        raw_trace=cell.raw_trace,
        amplitude_threshold=120.0,
        pad_samples=2,
        sg_window=11,
        sg_order=3
    )

    cell.dfof, _ = calculate_dfof(cell.interp_trace, fs, window_sec=2, quantile=0.15, invert_polarity=False)
    cell.baseline = lowpass_filter(cell.dfof, fs, cutoff_hz=4)
    cell.smoothed_dfof = gaussian_smoothing(cell.dfof, sigma=1.0)

    wmf_trace, final_spikes, reconstructed_trace, template, _, final_thresh = denoise_spikes(
        data=cell.dfof,                
        window_length=int((15.0 / 1000.0) * fs), 
        fr=fs,                         
        hp_freq=5.0,                   
        clip=100,                       
        threshold_method='adaptive',     
        threshold=3.5,                 
        min_spikes=5,                  
        do_plot=False                    
    )

    cell.spike_indices = final_spikes

######
# plotting
######
cell = recording.cells[0]

fig, axs = plt.subplots(nrows=3, ncols=1, figsize=(10, 6))
axs[0].plot(recording.time, cell.raw_trace)
axs[0].set_title("Raw Trace")

axs[1].plot(recording.time, cell.interp_trace)
axs[1].set_title("Interpolated Trace")

axs[2].plot(recording.time, cell.smoothed_dfof)
axs[2].set_title("smoothed dfof")
axs[2].set_ylabel("dfof")
axs[2].set_xlabel("time (ms)")

#for ax in axs:
#    ax.set_xlim(2200, 4000)


spike_times = recording.time[cell.spike_indices]

axs[2].plot(
    spike_times, 
    [0.95] * len(spike_times), 
    'k.',                    # 'k' = black, '.' = dot marker
    markersize=4,            # Adjust size as needed
    transform=axs[2].get_xaxis_transform(), # X is data coords, Y is axis coords (0-1)
    clip_on=False            # Prevents dots from being cut off if they touch the top border
)
plt.tight_layout()
plt.show()


