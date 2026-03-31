from dataclasses import dataclass, field
from typing import List, Optional 
import numpy as np

@dataclass
class Cell:
    """Store data for a single cell"""
    cell_id: str
    raw_trace: np.ndarray
    interp_trace: Optional[np.ndarray] = None
    dfof: Optional[np.ndarray] = None
    smoothed_dfof: Optional[np.ndarray] = None
    baseline: Optional[np.ndarray] = None
    spike_indices: List[int] = field(default_factory=list)

@dataclass
class Recording:
    """Store the shared time for a set of Cells (usally in one sheet)"""
    sheet_name: str
    time: np.ndarray  ## default to be ms
    cells: List[Cell]

    @property
    def sampling_rate(self) -> float:
        """Calculate sample rate in Hz from time (ms)"""
        dt_ms = np.mean(np.diff(self.time))
        return 1000.0 / dt_ms
