import numpy as np
import cv2
from scipy import signal, stats
import matplotlib.pyplot as plt

def signal_filter(sg, freq, fr, order=3, mode='high'):
    """High/low passing the signal with butterworth filter"""
    normFreq = freq / (fr / 2)
    b, a = signal.butter(order, normFreq, mode)
    sg = np.single(signal.filtfilt(b, a, sg, padtype='odd', padlen=3 * (max(len(b), len(a)) - 1)))
    return sg

def simple_thresh(data, pks, clip, threshold=3.5, min_spikes=10):
    """Threshold method based on estimated noise level from the negative signal."""
    low_spikes = False
    ff1 = -data * (data < 0)
    Ns = np.sum(ff1 > 0)
    std = np.sqrt(np.divide(np.sum(ff1**2), Ns)) 
    thresh = threshold * std
    locs = signal.find_peaks(data, height=thresh)[0]
    
    if len(locs) < min_spikes:
        thresh = np.percentile(pks, 100 * (1 - min_spikes / len(pks)))
        low_spikes = True
    elif ((len(locs) > clip) & (clip > 0)):
        thresh = np.percentile(pks, 100 * (1 - clip / len(pks)))    
    return thresh, low_spikes

def adaptive_thresh(pks, clip, pnorm=0.5, min_spikes=10):
    """Adaptive threshold based on Kernel Density Estimation of peak heights."""
    spread = np.array([pks.min(), pks.max()])
    spread = spread + np.diff(spread) * np.array([-0.05, 0.05])
    low_spikes = False
    pts = np.linspace(spread[0], spread[1], 2001)
    kde = stats.gaussian_kde(pks)
    f = kde(pts)    
    xi = pts
    center = np.where(xi > np.median(pks))[0][0]

    fmodel = np.concatenate([f[0:center + 1], np.flipud(f[0:center])])
    if len(fmodel) < len(f):
        fmodel = np.append(fmodel, np.ones(len(f) - len(fmodel)) * min(fmodel))
    else:
        fmodel = fmodel[0:len(f)]

    csf = np.cumsum(f) / np.sum(f)
    csmodel = np.cumsum(fmodel) / np.max([np.sum(f), np.sum(fmodel)])
    lastpt = np.where(np.logical_and(csf[0:-1] > csmodel[0:-1] + np.spacing(1), csf[1:] < csmodel[1:]))[0]
    if not lastpt.size:
        lastpt = center
    else:
        lastpt = lastpt[0]
    fmodel[0:lastpt + 1] = f[0:lastpt + 1]
    fmodel[lastpt:] = np.minimum(fmodel[lastpt:], f[lastpt:])

    csf = np.cumsum(f)
    csmodel = np.cumsum(fmodel)
    csf2 = csf[-1] - csf
    csmodel2 = csmodel[-1] - csmodel
    obj = csf2 ** pnorm - csmodel2 ** pnorm
    maxind = np.argmax(obj)
    thresh = xi[maxind]

    if np.sum(pks > thresh) < min_spikes:
        low_spikes = True
        thresh = np.percentile(pks, 100 * (1 - min_spikes / len(pks)))
    elif ((np.sum(pks > thresh) > clip) & (clip > 0)):
        thresh = np.percentile(pks, 100 * (1 - clip / len(pks)))

    ix = np.argmin(np.abs(xi - thresh))
    falsePosRate = csmodel2[ix] / csf2[ix]
    detectionRate = (csf2[ix] - csmodel2[ix]) / np.max(csf2 - csmodel2)
    return thresh, falsePosRate, detectionRate, low_spikes

def whitened_matched_filter(data, locs, window):
    """The core algorithm: calculates noise spectrum and applies WMF."""
    N = np.ceil(np.log2(len(data)))
    censor = np.zeros(len(data))
    censor[locs] = 1
    censor = np.int16(np.convolve(censor.flatten(), np.ones([1, len(window)]).flatten(), 'same'))
    censor = (censor < 0.5)
    noise = data[censor]

    # Calculate noise spectrum using Welch's method
    _, pxx = signal.welch(noise, fs=2 * np.pi, window=signal.get_window('hamming', 1000), nfft=2 ** N, detrend=False, nperseg=1000)
    Nf2 = np.concatenate([pxx, np.flipud(pxx[1:-1])])
    scaling_vector = 1 / np.sqrt(Nf2)

    # Apply scaling in frequency domain via OpenCV DFT
    cc = np.pad(data.copy(),(0,int(2**N-len(data))),'constant')    
    dd = (cv2.dft(cc,flags=cv2.DFT_SCALE+cv2.DFT_COMPLEX_OUTPUT)[:,0,:]*scaling_vector[:,np.newaxis])[:,np.newaxis,:]
    dataScaled = cv2.idft(dd)[:,0,0]
    
    # Extract scaled templates and convolve
    PTDscaled = dataScaled[(locs[:, np.newaxis] + window)]
    PTAscaled = np.mean(PTDscaled, 0)
    datafilt = np.convolve(dataScaled, np.flipud(PTAscaled), 'same')
    datafilt = datafilt[:len(data)]
    return datafilt

def denoise_spikes(data, window_length, fr=400, hp_freq=1, clip=100, threshold_method='simple', min_spikes=10, pnorm=0.5, threshold=3.5, do_plot=True):
    """Main function to orchestrate the VolPy temporal pipeline."""
    # 1. High-pass filter
    data = signal_filter(data, hp_freq, fr, order=5)
    data = data - np.median(data)
    pks = data[signal.find_peaks(data, height=None)[0]]

    # 2. First round of spike detection    
    if threshold_method == 'adaptive':
        thresh, _, _, low_spikes = adaptive_thresh(pks, clip, 0.25, min_spikes)
        locs = signal.find_peaks(data, height=thresh)[0]
    elif threshold_method == 'simple':
        thresh, low_spikes = simple_thresh(data, pks, clip, threshold, min_spikes)
        locs = signal.find_peaks(data, height=thresh)[0]

    # 3. Spike template (Peak-Triggered Average)
    window = np.int64(np.arange(-window_length, window_length + 1, 1))
    locs = locs[np.logical_and(locs > (-window[0]), locs < (len(data) - window[-1]))]
    PTD = data[(locs[:, np.newaxis] + window)]
    PTA = np.median(PTD, 0)
    PTA = PTA - np.min(PTA)
    templates = PTA

    # 4. Whitened matched filtering 
    datafilt = whitened_matched_filter(data, locs, window)    
    datafilt = datafilt - np.median(datafilt)

    # 5. Second round of spike detection 
    pks2 = datafilt[signal.find_peaks(datafilt, height=None)[0]]
    if threshold_method == 'adaptive':
        thresh2, _, _, low_spikes = adaptive_thresh(pks2, clip=0, pnorm=pnorm, min_spikes=min_spikes) 
        spikes = signal.find_peaks(datafilt, height=thresh2)[0]
    elif threshold_method == 'simple':
        # Notice we use threshold here again for the output trace
        thresh2, low_spikes = simple_thresh(datafilt, pks2, 0, threshold, min_spikes)
        spikes = signal.find_peaks(datafilt, height=thresh2)[0]
    
    t_rec = np.zeros(datafilt.shape)
    t_rec[spikes] = 1
    t_rec = np.convolve(t_rec, PTA, 'same')   
    factor = np.mean(data[spikes]) / np.mean(datafilt[spikes])
    datafilt = datafilt * factor
    thresh2_normalized = thresh2 * factor
        
    if do_plot:
        fig, axs = plt.subplots(3, 1, figsize=(12, 10), sharex=False)
        
        # Plot A: PTA
        axs[0].plot(np.transpose(PTD), color='gray', alpha=0.3)
        axs[0].plot(PTA, color='black', linewidth=2)
        axs[0].set_title('Peak-Triggered Average (The Template)')
        
        # Plot B: Raw Trace with Initial Spikes
        axs[1].plot(data, color='black', label='High-Passed Data')
        axs[1].plot(locs, data[locs], 'ro', fillstyle='none', markersize=8, label='Pass 1 Spikes')
        axs[1].set_title('Original Trace & Initial Detection')
        axs[1].legend()

        # Plot C: WMF Trace with Final Spikes
        axs[2].plot(datafilt, color='blue', label='Whitened Output')
        axs[2].plot(spikes, datafilt[spikes], 'go', fillstyle='none', markersize=8, label='Final Spikes')
        axs[2].axhline(thresh2_normalized, color='r', linestyle='--', label='Final Threshold')
        axs[2].set_title('Whitened Matched Filter Output')
        axs[2].legend()
        
        plt.tight_layout()
        plt.show()

    return datafilt, spikes, t_rec, templates, low_spikes, thresh2_normalized
