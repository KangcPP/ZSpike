import pandas as pd
from PySide6.QtWidgets import QMainWindow, QSplitter, QApplication, QTreeWidgetItem
from PySide6.QtCore import Qt

from frontend.control_panel import ControlPanel
from frontend.data_panel import DataPanel
from frontend.plot_panel import PlotPanel

from backend.structure import Recording, Cell 
from backend.processing import clean_artifact, calculate_dfof, gaussian_smoothing
from backend.spikepursuit import denoise_spikes

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ZSpike!")
        self.resize(1200, 800) 

        self.backend_store = {}
        self.cached_dfs = {}
        
        self.active_store_key = None
        self.active_cell_id = None
        self.active_tree_item = None

        self.main_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.setCentralWidget(self.main_splitter)

        self.left_splitter = QSplitter(Qt.Orientation.Vertical)
        self.control_panel = ControlPanel() 
        self.data_panel = DataPanel()       
        
        self.left_splitter.addWidget(self.control_panel)
        self.left_splitter.addWidget(self.data_panel)
        self.left_splitter.setStretchFactor(0, 4) 
        self.left_splitter.setStretchFactor(1, 6)

        self.right_panel = PlotPanel(self.backend_store)

        self.main_splitter.addWidget(self.left_splitter)
        self.main_splitter.addWidget(self.right_panel)
        self.main_splitter.setStretchFactor(0, 20)  
        self.main_splitter.setStretchFactor(1, 80)

        self.data_panel.tree.itemSelectionChanged.connect(self.on_tree_selection_changed)
        
        # --- CONNECT ALL THE GENERATE BUTTONS ---
        self.control_panel.btn_apply_slice.clicked.connect(self.run_apply_slice)
        self.control_panel.btn_generate_interp.clicked.connect(self.run_interpolate)
        self.control_panel.btn_generate_dfof.clicked.connect(self.run_dfof)
        self.control_panel.btn_generate_smooth.clicked.connect(self.run_smooth)
        self.control_panel.btn_generate_spikes.clicked.connect(self.run_spikes)


    def run_apply_slice(self):
        if not self.active_store_key or not self.active_tree_item: return

        # Get the parent Recording item because a slice applies to the whole recording time-vector
        recording_ui_item = self.active_tree_item if self.active_tree_item.parent() is None else self.active_tree_item.parent()

        # Grab metadata from the first cell's raw_trace to know what file to target
        trace_meta = recording_ui_item.child(0).child(0).data(0, Qt.ItemDataRole.UserRole)
        file_path = trace_meta["file_path"]
        sheet_name = trace_meta["sheet_name"]
        time_col = trace_meta["time_col"]

        # Reload the memory structures. Because we cached the DataFrame, this is instant!
        self.load_recording_into_memory(self.active_store_key, file_path, sheet_name, time_col, recording_ui_item)

        # Visually clear all computed traces (Interp, dF/F, etc.) from the UI 
        # because the underlying length of the raw_trace array has changed!
        for i in range(recording_ui_item.childCount()):
            cell_item = recording_ui_item.child(i)
            # Iterate backwards when deleting children in Qt to avoid index shifting errors
            for j in reversed(range(cell_item.childCount())):
                child = cell_item.child(j)
                if child.text(0) != "raw_trace":
                    cell_item.removeChild(child)

        # Refresh UI buttons based on the newly reset cell
        recording = self.backend_store[self.active_store_key]
        cell = next((c for c in recording.cells if c.cell_id == self.active_cell_id), None)
        if cell:
            self.update_control_panel_state(cell)

    def on_tree_selection_changed(self):
        selected_items = self.data_panel.tree.selectedItems()
        
        if not selected_items:
            self.control_panel.set_title(None)
            self.disable_all_controls()
            return
            
        item = selected_items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        item_type = data.get("type") if data else None
        
        # --- NEW LOGIC: Handle both Cell and Trace clicks ---
        if item_type == "cell":
            cell_item = item
            trace_meta = cell_item.child(0).data(0, Qt.ItemDataRole.UserRole)
        elif item_type == "trace":
            cell_item = item.parent() # Look up one level to the Cell!
            trace_meta = item.data(0, Qt.ItemDataRole.UserRole)
        else:
            # If they clicked the Recording folder or empty space
            self.control_panel.set_title(None)
            self.disable_all_controls()
            return

        # --- Extract Metadata ---
        file_path = trace_meta["file_path"]
        sheet_name = trace_meta["sheet_name"]
        time_col = trace_meta["time_col"]
        cell_col = trace_meta["cell_col"]

        # Update Title using the Cell's name, not the trace's name
        self.control_panel.set_title(cell_item.text(0))

        # --- Lazy Load into Memory ---
        store_key = f"{file_path}::{sheet_name}"
        if store_key not in self.backend_store:
            self.load_recording_into_memory(store_key, file_path, sheet_name, time_col, cell_item.parent())

        # --- Save State ---
        self.active_store_key = store_key
        self.active_cell_id = cell_col
        # IMPORTANT: Always save the cell_item, so when we hit 'Generate', 
        # the new trace is added under the Cell, not under another trace!
        self.active_tree_item = cell_item 

        # --- Update Buttons ---
        recording_obj = self.backend_store[store_key]
        target_cell = next((c for c in recording_obj.cells if c.cell_id == cell_col), None)

        if target_cell:
            self.update_control_panel_state(target_cell)

    # --- EXECUTION FUNCTIONS ---

    def run_interpolate(self):
        if not self.active_store_key or not self.active_cell_id: return
        recording = self.backend_store[self.active_store_key]
        cell = next((c for c in recording.cells if c.cell_id == self.active_cell_id), None)
        if not cell: return

        amp_thresh = self.control_panel.spn_amp_thresh.value()
        pad_samples = self.control_panel.spn_pad_samples.value()
        sg_window = self.control_panel.spn_sg_window.value()
        sg_order = self.control_panel.spn_sg_order.value()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            cell.interp_trace = clean_artifact(
                time_vector=recording.time,
                raw_trace=cell.raw_trace,
                amplitude_threshold=amp_thresh,
                pad_samples=pad_samples,
                sg_window=sg_window,
                sg_order=sg_order
            )
            self.add_trace_to_tree_ui(self.active_tree_item, "interp_trace")
            self.update_control_panel_state(cell)
        except Exception as e:
            print(f"Interpolation Error: {repr(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def run_dfof(self):
        if not self.active_store_key or not self.active_cell_id: return
        recording = self.backend_store[self.active_store_key]
        cell = next((c for c in recording.cells if c.cell_id == self.active_cell_id), None)
        if not cell or cell.interp_trace is None: return

        # Get parameters from UI
        window_sec = self.control_panel.spn_window_sec.value()
        quantile = self.control_panel.spn_quantile.value()
        invert_polarity = self.control_panel.chk_invert.isChecked()
        
        # Get sampling rate from the Recording dataclass property
        fs = recording.sampling_rate

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # calculate_dfof returns a tuple: (dfof, baseline)
            dfof_trace, baseline_trace = calculate_dfof(
                raw_trace=cell.interp_trace, 
                sampling_rate=fs, 
                window_sec=window_sec, 
                quantile=quantile, 
                invert_polarity=invert_polarity
            )
            
            # Store in the backend
            cell.dfof = dfof_trace
            cell.baseline = baseline_trace
            
            # Update UI
            self.add_trace_to_tree_ui(self.active_tree_item, "dfof")
            self.update_control_panel_state(cell)
        except Exception as e:
            print(f"dF/F Error: {repr(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def run_smooth(self):
        if not self.active_store_key or not self.active_cell_id: return
        recording = self.backend_store[self.active_store_key]
        cell = next((c for c in recording.cells if c.cell_id == self.active_cell_id), None)
        if not cell or cell.dfof is None: return

        # Get parameter from UI
        sigma = self.control_panel.spn_sigma.value()

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            cell.smoothed_dfof = gaussian_smoothing(
                trace=cell.dfof, 
                sigma=sigma
            )
            
            # Update UI
            self.add_trace_to_tree_ui(self.active_tree_item, "smoothed_dfof")
            self.update_control_panel_state(cell)
        except Exception as e:
            print(f"Smoothing Error: {repr(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    # --- HELPER FUNCTIONS ---

    def add_trace_to_tree_ui(self, cell_item, trace_type):
        for i in range(cell_item.childCount()):
            if cell_item.child(i).text(0) == trace_type:
                return 

        trace_item = QTreeWidgetItem(cell_item)
        trace_item.setText(0, trace_type)

        base_meta = cell_item.child(0).data(0, Qt.ItemDataRole.UserRole)
        new_meta = base_meta.copy()
        new_meta["trace_type"] = trace_type
        
        trace_item.setData(0, Qt.ItemDataRole.UserRole, new_meta)
        cell_item.setExpanded(True)

    def load_recording_into_memory(self, store_key, file_path, sheet_name, time_col, recording_ui_item):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            # 1. Check cache first to avoid re-reading Excel!
            if store_key not in self.cached_dfs:
                df = pd.read_excel(file_path, sheet_name=sheet_name)
                df.columns = df.columns.astype(str)
                self.cached_dfs[store_key] = df
            else:
                df = self.cached_dfs[store_key]

            # 2. Get the current slice value from the UI
            skip_n = self.control_panel.spn_skip_frames.value()
            
            # 3. Apply the slice to the time vector
            time_vector = pd.to_numeric(df[str(time_col)], errors='coerce').to_numpy(dtype=float)[skip_n:]
            
            # 4. Apply the slice to all cells in the recording
            cells = []
            for i in range(recording_ui_item.childCount()):
                cell_item = recording_ui_item.child(i)
                trace_meta = cell_item.child(0).data(0, Qt.ItemDataRole.UserRole)
                c_name = trace_meta["cell_col"]
                
                raw_trace = pd.to_numeric(df[str(c_name)], errors='coerce').to_numpy(dtype=float)[skip_n:]
                
                # Instantiating a new Cell automatically resets interp/dfof/spikes to None
                cells.append(Cell(cell_id=c_name, raw_trace=raw_trace))
                
            self.backend_store[store_key] = Recording(sheet_name=sheet_name, time=time_vector, cells=cells)
        except Exception as e:
            print(f"Failed to load recording: {repr(e)}")
        finally:
            QApplication.restoreOverrideCursor()

    def update_control_panel_state(self, cell: Cell):
        self.control_panel.btn_apply_slice.setEnabled(True)
        self.control_panel.btn_generate_interp.setEnabled(True)
        self.control_panel.btn_generate_dfof.setEnabled(cell.interp_trace is not None)
        self.control_panel.btn_generate_smooth.setEnabled(cell.dfof is not None)
        self.control_panel.btn_generate_spikes.setEnabled(cell.dfof is not None)

    def disable_all_controls(self):
        self.control_panel.btn_apply_slice.setEnabled(False)
        self.control_panel.btn_generate_interp.setEnabled(False)
        self.control_panel.btn_generate_dfof.setEnabled(False)
        self.control_panel.btn_generate_smooth.setEnabled(False)
        self.control_panel.btn_generate_spikes.setEnabled(False)

    def run_spikes(self):
        if not self.active_store_key or not self.active_cell_id: return
        recording = self.backend_store[self.active_store_key]
        cell = next((c for c in recording.cells if c.cell_id == self.active_cell_id), None)
        if not cell or cell.dfof is None: return

        # Extract parameters
        window_ms = self.control_panel.spn_window_ms.value()
        hp_freq = self.control_panel.spn_hp_freq.value()
        clip = self.control_panel.spn_clip.value()
        thresh_method = self.control_panel.cmb_thresh_method.currentText()
        threshold = self.control_panel.spn_threshold.value()
        min_spikes = self.control_panel.spn_min_spikes.value()
        
        fs = recording.sampling_rate
        window_length = int((window_ms / 1000.0) * fs)

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            wmf_trace, final_spikes, reconstructed_trace, template, _, final_thresh = denoise_spikes(
                data=cell.dfof,                
                window_length=window_length, 
                fr=fs,                         
                hp_freq=hp_freq,                   
                clip=clip,                       
                threshold_method=thresh_method,     
                threshold=threshold,                 
                min_spikes=min_spikes,                  
                do_plot=False 
            )
            
            # Store the array of indices in the backend
            cell.spike_indices = final_spikes
            
            # Add to UI tree
            self.add_trace_to_tree_ui(self.active_tree_item, "spikes")
            self.update_control_panel_state(cell)
            
        except Exception as e:
            print(f"Spike Detection Error: {repr(e)}")
        finally:
            QApplication.restoreOverrideCursor()
