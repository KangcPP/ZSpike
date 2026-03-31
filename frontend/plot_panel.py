import json
import numpy as np
import pyqtgraph as pg
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton, 
                               QScrollArea, QApplication, QColorDialog) # Added QColorDialog
from PySide6.QtCore import Qt, QTimer

class DropAxis(pg.PlotWidget):
    def __init__(self, backend_store):
        super().__init__()
        self.backend_store = backend_store
        self.setAcceptDrops(True)
        self.setBackground('w') 
        self.showGrid(x=True, y=True)
        self.setLabel('bottom', 'Time')
        self.setLabel('left', 'Value')
        
        self.addLegend()
        self.colors = ['#1f77b4', '#d62728', '#2ca02c', '#ff7f0e', '#9467bd', '#8c564b']
        self.color_idx = 0

        # --- NEW: Hook into the PyQtGraph Right-Click Menu ---
        self.vb = self.getPlotItem().getViewBox()
        self.color_submenu = self.vb.menu.addMenu("Change Trace Color")
        # This signal triggers our function right before the menu appears on screen
        self.color_submenu.aboutToShow.connect(self.populate_color_menu)

    # --- NEW: Dynamic Menu Population ---
    def populate_color_menu(self):
        # Clear the old list so it doesn't duplicate items
        self.color_submenu.clear()
        
        # listDataItems() grabs the actual line/dot objects currently drawn on the plot
        items = self.getPlotItem().listDataItems()
        
        if not items:
            action = self.color_submenu.addAction("No traces to color")
            action.setEnabled(False)
            return
            
        for item in items:
            # Grab the name we assigned to the trace when we plotted it
            name = item.opts.get('name', 'Unknown Trace')
            action = self.color_submenu.addAction(name)
            
            # The lambda binding (i=item) is crucial here. It forces each button 
            # to remember exactly which trace it is supposed to recolor.
            action.triggered.connect(lambda checked=False, i=item: self.open_color_picker(i))

    # --- NEW: Color Picker Logic ---
    def open_color_picker(self, item):
        color = QColorDialog.getColor()
        
        # If the user clicks "Cancel" on the color picker, isValid() returns False
        if color.isValid():
            # Check if this trace is a Spike (dots) or a normal trace (lines)
            # When we plotted spikes, we explicitly set pen=None
            if item.opts.get('pen') is None:
                item.setSymbolBrush(color)
                item.setSymbolPen(color) # This recolors the outline of the dot too
            else:
                # Normal traces are lines, so we change the pen
                item.setPen(pg.mkPen(color, width=1.5))

    def dragEnterEvent(self, event):
        if event.mimeData().hasText(): event.acceptProposedAction()

    def dragMoveEvent(self, event):
        if event.mimeData().hasText(): event.acceptProposedAction()

    def dropEvent(self, event):
        text = event.mimeData().text()
        try:
            metadata = json.loads(text)
            if metadata.get("type") == "trace":
                event.acceptProposedAction()
                QTimer.singleShot(0, lambda: self.load_and_plot(metadata))
        except Exception as e:
            print(f"Drop failed: {repr(e)}")

    def load_and_plot(self, meta):
        try:
            store_key = f"{meta['file_path']}::{meta['sheet_name']}"
            if store_key not in self.backend_store: return
            recording = self.backend_store[store_key]
            cell = next((c for c in recording.cells if c.cell_id == meta['cell_col']), None)
            if not cell: return

            display_name = meta.get('display_name', meta['cell_col'])
            x_data = recording.time

            # --- SPECIAL HANDLING FOR SPIKES ---
            if meta['trace_type'] == "spikes":
                if not hasattr(cell, 'spike_indices') or len(cell.spike_indices) == 0:
                    print("No spikes detected to plot.")
                    return
                
                # Get the exact X time of the spikes
                spike_x = x_data[cell.spike_indices]
                
                # Calculate 95% of the CURRENT visible Y-axis height
                y_min, y_max = self.getViewBox().viewRange()[1]
                y_val = y_min + 0.95 * (y_max - y_min)
                
                # Generate a Y-array matching the length of the spikes
                spike_y = np.full_like(spike_x, y_val, dtype=float)
                
                # Plot the black dots WITHOUT clearing the plot
                # pen=None removes the connecting lines, symbol='o' makes them dots
                self.plot(
                    x=spike_x, 
                    y=spike_y, 
                    pen=None, 
                    symbol='o', 
                    symbolBrush='k', 
                    symbolSize=5, 
                    name=f"{display_name} (Spikes)"
                )
                return

            # --- HANDLING FOR NORMAL TRACES ---
            if meta['trace_type'] == "raw_trace": y_data = cell.raw_trace
            elif meta['trace_type'] == "interp_trace": y_data = cell.interp_trace
            elif meta['trace_type'] == "dfof": y_data = cell.dfof
            elif meta['trace_type'] == "smoothed_dfof": y_data = cell.smoothed_dfof
            else: return

            # Get the next color in the cycle
            color = self.colors[self.color_idx % len(self.colors)]
            self.color_idx += 1

            # Plot with clear=False to allow overlay!
            self.plot(
                x=x_data, 
                y=y_data, 
                pen=pg.mkPen(color, width=1.5), 
                name=f"{display_name} ({meta['trace_type']})"
            )
            
        except Exception as e:
            print(f"Plotting failed: {repr(e)}")

class AxisContainer(QWidget):
    def __init__(self, parent_layout, backend_store):
        super().__init__()
        self.parent_layout = parent_layout
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 15) 
        
        top_bar = QHBoxLayout()
        top_bar.addStretch() 
        self.btn_delete = QPushButton("Close Axis")
        self.btn_delete.setStyleSheet("color: #c0392b; font-weight: bold; border: none; padding: 2px 10px;")
        self.btn_delete.clicked.connect(self.delete_self)
        top_bar.addWidget(self.btn_delete)
        layout.addLayout(top_bar)
        
        # Pass the memory reference down to the Axis
        self.plot_widget = DropAxis(backend_store)
        layout.addWidget(self.plot_widget)

    def delete_self(self):
        self.parent_layout.removeWidget(self)
        self.deleteLater()


class PlotPanel(QWidget):
    def __init__(self, backend_store):
        super().__init__()
        self.backend_store = backend_store
        self.layout = QVBoxLayout(self)
        
        self.btn_add_axis = QPushButton("+ Add Axis")
        self.btn_add_axis.clicked.connect(self.add_new_axis)
        self.layout.addWidget(self.btn_add_axis)
        
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        
        self.axes_container = QWidget()
        self.axes_layout = QVBoxLayout(self.axes_container)
        self.axes_layout.setAlignment(Qt.AlignmentFlag.AlignTop) 
        self.scroll_area.setWidget(self.axes_container)
        self.layout.addWidget(self.scroll_area)

    def add_new_axis(self):
        container = AxisContainer(self.axes_layout, self.backend_store)
        container.setMinimumHeight(300) 
        self.axes_layout.addWidget(container)
