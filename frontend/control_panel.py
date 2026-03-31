from PySide6.QtWidgets import (QWidget, QVBoxLayout, QGroupBox, QFormLayout, 
                               QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton, 
                               QLabel, QScrollArea, QComboBox)
from PySide6.QtCore import Qt

class ControlPanel(QWidget):
    def __init__(self):
        super().__init__()
        
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        main_layout.addWidget(scroll_area)
        
        content_widget = QWidget()
        self.layout = QVBoxLayout(content_widget)
        scroll_area.setWidget(content_widget)
        
        self.lbl_title = QLabel("DSP Parameters")
        self.lbl_title.setStyleSheet("font-size: 16px; font-weight: bold; margin-bottom: 5px;")
        self.layout.addWidget(self.lbl_title)
        
        # --- NEW: Added Preprocessing Section ---
        self.build_preprocessing_section()
        self.build_interpolate_section()
        self.build_dfof_section()
        self.build_smooth_section()
        self.build_spikes_section()
        
        self.layout.addStretch() 

    # --- NEW: Preprocessing Group ---
    def build_preprocessing_section(self):
        group = QGroupBox("0. Preprocessing")
        form = QFormLayout(group)

        self.spn_skip_frames = QSpinBox()
        self.spn_skip_frames.setRange(0, 100000)
        self.spn_skip_frames.setValue(100) # Default to your 100 frame skip!
        form.addRow("Discard First N Frames:", self.spn_skip_frames)

        self.btn_apply_slice = QPushButton("Apply")
        self.btn_apply_slice.setEnabled(False)
        # Style it slightly differently to indicate it's a reset action
        self.btn_apply_slice.setStyleSheet("color: #d35400; font-weight: bold;")
        form.addRow(self.btn_apply_slice)

        self.layout.addWidget(group)

    def build_interpolate_section(self):
        group = QGroupBox("1. Clean Artifact (Interpolate)")
        form = QFormLayout(group)
        self.spn_amp_thresh = QDoubleSpinBox()
        self.spn_amp_thresh.setRange(-1000.0, 1000.0)
        self.spn_amp_thresh.setValue(120.0)
        self.spn_pad_samples = QSpinBox()
        self.spn_pad_samples.setRange(0, 100)
        self.spn_pad_samples.setValue(2)
        self.spn_sg_window = QSpinBox()
        self.spn_sg_window.setRange(3, 999)
        self.spn_sg_window.setSingleStep(2)
        self.spn_sg_window.setValue(11)
        self.spn_sg_order = QSpinBox()
        self.spn_sg_order.setRange(1, 10)
        self.spn_sg_order.setValue(3)
        form.addRow("Amplitude Threshold:", self.spn_amp_thresh)
        form.addRow("Pad Samples:", self.spn_pad_samples)
        form.addRow("SG Window:", self.spn_sg_window)
        form.addRow("SG Order:", self.spn_sg_order)
        self.btn_generate_interp = QPushButton("Generate Interpolated Trace")
        self.btn_generate_interp.setEnabled(False)
        form.addRow(self.btn_generate_interp)
        self.layout.addWidget(group)
        
    def build_dfof_section(self):
        group = QGroupBox("2. Calculate dF/F")
        form = QFormLayout(group)
        self.spn_window_sec = QDoubleSpinBox()
        self.spn_window_sec.setRange(0.1, 60.0)
        self.spn_window_sec.setSingleStep(0.5)
        self.spn_window_sec.setValue(2.0)
        self.spn_quantile = QDoubleSpinBox()
        self.spn_quantile.setRange(0.01, 1.0)
        self.spn_quantile.setSingleStep(0.05)
        self.spn_quantile.setValue(0.15)
        self.chk_invert = QCheckBox()
        self.chk_invert.setChecked(False)
        form.addRow("Window (sec):", self.spn_window_sec)
        form.addRow("Quantile:", self.spn_quantile)
        form.addRow("Invert Polarity:", self.chk_invert)
        self.btn_generate_dfof = QPushButton("Calculate dF/F")
        self.btn_generate_dfof.setEnabled(False) 
        form.addRow(self.btn_generate_dfof)
        self.layout.addWidget(group)
        
    def build_smooth_section(self):
        group = QGroupBox("3. Gaussian Smoothing")
        form = QFormLayout(group)
        self.spn_sigma = QDoubleSpinBox()
        self.spn_sigma.setRange(0.1, 10.0)
        self.spn_sigma.setSingleStep(0.1)
        self.spn_sigma.setValue(1.0)
        form.addRow("Sigma:", self.spn_sigma)
        self.btn_generate_smooth = QPushButton("Generate Smoothed Trace")
        self.btn_generate_smooth.setEnabled(False) 
        form.addRow(self.btn_generate_smooth)
        self.layout.addWidget(group)

    def build_spikes_section(self):
        group = QGroupBox("4. Spike Detection (based on dF/F)")
        form = QFormLayout(group)
        
        self.spn_window_ms = QDoubleSpinBox()
        self.spn_window_ms.setRange(1.0, 100.0)
        self.spn_window_ms.setValue(15.0)
        
        self.spn_hp_freq = QDoubleSpinBox()
        self.spn_hp_freq.setRange(0.1, 50.0)
        self.spn_hp_freq.setValue(5.0)
        
        self.spn_clip = QSpinBox()
        self.spn_clip.setRange(0, 1000)
        self.spn_clip.setValue(100)
        
        self.cmb_thresh_method = QComboBox()
        self.cmb_thresh_method.addItems(['adaptive', 'simple'])
        
        self.spn_threshold = QDoubleSpinBox()
        self.spn_threshold.setRange(0.1, 20.0)
        self.spn_threshold.setSingleStep(0.1)
        self.spn_threshold.setValue(3.5)
        
        self.spn_min_spikes = QSpinBox()
        self.spn_min_spikes.setRange(0, 100)
        self.spn_min_spikes.setValue(5)
        
        form.addRow("Window (ms):", self.spn_window_ms)
        form.addRow("HP Freq (Hz):", self.spn_hp_freq)
        form.addRow("Clip:", self.spn_clip)
        form.addRow("Threshold Method:", self.cmb_thresh_method)
        form.addRow("Threshold:", self.spn_threshold)
        form.addRow("Min Spikes:", self.spn_min_spikes)
        
        self.btn_generate_spikes = QPushButton("Detect Spikes!")
        self.btn_generate_spikes.setEnabled(False)
        form.addRow(self.btn_generate_spikes)
        
        self.layout.addWidget(group)

    def set_title(self, cell_name):
        if cell_name:
            self.lbl_title.setText(f"Parameters ({cell_name})")
        else:
            self.lbl_title.setText("Parameters")
