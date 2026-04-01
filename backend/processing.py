import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks, savgol_filter
from scipy.signal.windows import tukey
from scipy.ndimage import percentile_filter, gaussian_filter1d, binary_dilation
from scipy.interpolate import Akima1DInterpolator
import matplotlib.pyplot as plt
from scipy.signal import find_peaks, welch, correlate
from scipy.signal.windows import tukey
from scipy.fft import rfft, irfft, rfftfreq

def calculate_dfof(
    raw_trace: np.ndarray,
    sampling_rate: float,
    window_sec: float = 2.0,
    quantile: float = 0.20,
    invert_polarity: bool = True  
) -> tuple[np.ndarray, np.ndarray]:
    """
    Calculate baseline(f0) using rolling quantile and returns the df/f trace

    Parameters:
    raw_trace: 1d array of rawe fluorescence signal
    sampling_rate: sample rate in Hz
    window_sec: size of rolling window in second
    quantile: quantile to for baseline estimation (20% for default)
    invert_polarity: if True, multipy the df/f with -1

    Returns:
    dfof: normalized dfof trace
    f0: baseline trace 
    """
    window_samples = int(window_sec*sampling_rate)

    ## estimate the baseline(f0)
    f0 = percentile_filter(raw_trace, percentile=quantile*100, size=window_samples)
    f0 = np.where(f0 == 0, 1e-10, f0) ## prevent division by 0

    ## calculate dfof
    dfof = (raw_trace - f0) / f0
    if invert_polarity:
        dfof = -dfof
        
    return dfof, f0


def lowpass_filter(
    trace: np.ndarray,
    sampling_rate: float,
    cutoff_hz: float = 4.0,
    order: int = 5
) -> np.ndarray:
    """
    Butterworth low-pass filter to extract the subthreshold baseline
    """
    # normalize the cutoff frequency
    normal_cutoff = cutoff_hz / (0.5*sampling_rate)
    b, a = butter(order, normal_cutoff, btype='low', analog=False)
    
    return filtfilt(b, a, trace)


def gaussian_smoothing(
    trace: np.ndarray,
    sigma: float = 1.0
) -> np.ndarray:
    return gaussian_filter1d(trace, sigma)

def detect_spikes(
    smoothed_dfof: np.ndarray,
    baseline: np.ndarray,
    sampling_rate: float,
    std_threshold: float = 3,
    window_ms: float = 25
) -> np.ndarray:
    """
    Detect spike based on standard deviation threshold of the baseline

    Parameters:
    std_threshold: number of standard deviation above baseline as the threshold
    window_ms: window size (in ms) of the peak in local maximum

    Returns:
    spike_indices: 1d array containing index of the spikes
    """
    
    flattened_trace = smoothed_dfof - baseline

    ### standard deviation of the noise 
    noise_std = np.std(flattened_trace)
    threshold = std_threshold * noise_std

    ### convert window_ms into frame number 
    window_samples = int((window_ms / 1000) * sampling_rate)

    spike_indices, _ =  find_peaks(flattened_trace, height=threshold, distance=window_samples)

    return spike_indices

def remove_spikes_from_raw(
    raw_trace: np.ndarray, 
    spike_indices: np.ndarray, 
    sampling_rate: float, 
    pre_ms: float = 10.0, 
    post_ms: float = 25.0
) -> np.ndarray:
    """
    Removes spikes by interpolating over the spike windows. 
    Handles overlapping windows (bursts) seamlessly.
    """
    n_samples = len(raw_trace)
    clean_trace = raw_trace.copy()
    
    # If no spikes were found, just return the original trace
    if len(spike_indices) == 0:
        return clean_trace
        
    # Convert ms to sample indices
    pre_samples = int((pre_ms / 1000.0) * sampling_rate)
    post_samples = int((post_ms / 1000.0) * sampling_rate)
    

    is_spike_region = np.zeros(n_samples, dtype=bool)
    
    for idx in spike_indices:
        start = max(0, idx - pre_samples)
        end = min(n_samples, idx + post_samples)
        is_spike_region[start:end] = True
        
    # Separate the array into "valid" points and points we need to fix
    all_indices = np.arange(n_samples)
    valid_indices = all_indices[~is_spike_region]
    valid_values = raw_trace[~is_spike_region]
    
    # Perform linear interpolation over the polluted regions
    # np.interp uses the known good points to guess the missing points
    interpolated_values = np.interp(all_indices[is_spike_region], valid_indices, valid_values)
    
    # Replace the bad data with the clean interpolated data
    clean_trace[is_spike_region] = interpolated_values
    
    return clean_trace

def clean_artifact(
    time_vector: np.ndarray, 
    raw_trace: np.ndarray, 
    amplitude_threshold: float, 
    pad_samples: int = 2, 
    sg_window: int = 11,
    sg_order: int = 3
) -> np.ndarray:
    """
    Interpolates and smooths the artifact

    Parameters:
    amplitude_threshold: value under this threshold would be mark as artifact
    pad_sample: buffer data point to be delected near the noise under the threshold
    sg_window: window length in Savitzky-Golay filter, must be wider than the jaggend noise, unit in data-point
    sg_order: polynomial order in Savitzky-Golay filter, usually 3 (cubic)
    """
    final_trace = raw_trace.copy()

    is_artifact = raw_trace < amplitude_threshold
    
    if not np.any(is_artifact):
        return final_trace
        
    if pad_samples > 0:
        is_artifact = binary_dilation(is_artifact, iterations=pad_samples)
        
    valid_mask = ~is_artifact
    valid_times = time_vector[valid_mask]
    valid_values = raw_trace[valid_mask]
    artifact_times = time_vector[is_artifact]
    
    if len(artifact_times) == 0:
        return final_trace
        

    interpolator = Akima1DInterpolator(valid_times, valid_values)
    predictions = interpolator(artifact_times)

    temp_trace = raw_trace.copy()
    temp_trace[is_artifact] = predictions
    
    smoothed_temp_trace = savgol_filter(temp_trace, window_length=sg_window, polyorder=sg_order)
    blend_mask = binary_dilation(is_artifact, iterations=1)
    
    final_trace[blend_mask] = smoothed_temp_trace[blend_mask]
    
    return final_trace
