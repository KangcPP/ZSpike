import pandas as pd
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                               QComboBox, QListWidget, QTableWidget, 
                               QTableWidgetItem, QPushButton, QAbstractItemView, QMessageBox)

class ImportDialog(QDialog):
    def __init__(self, file_path, parent=None):
        super().__init__(parent)
        self.file_path = file_path
        self.setWindowTitle(f"Import Data: {file_path.split('/')[-1]}")
        self.resize(600, 500)

        self.selected_sheet = None
        self.selected_time = None
        self.selected_cells = []
        self.all_columns = [] # Store all columns so we can filter them later

        try:
            self.xls = pd.ExcelFile(self.file_path)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open Excel file:\n{e}")
            self.reject()
            return

        self.setup_ui()
        self.on_sheet_changed() 

    def setup_ui(self):
        layout = QVBoxLayout(self)

        # --- Sheet Selection ---
        sheet_layout = QHBoxLayout()
        sheet_layout.addWidget(QLabel("1. Select Sheet:"))
        self.sheet_combo = QComboBox()
        self.sheet_combo.addItems(self.xls.sheet_names)
        self.sheet_combo.currentTextChanged.connect(self.on_sheet_changed)
        sheet_layout.addWidget(self.sheet_combo)
        layout.addLayout(sheet_layout)

        # --- Time Column Selection ---
        time_layout = QHBoxLayout()
        time_layout.addWidget(QLabel("2. Select Time Vector:"))
        self.time_combo = QComboBox()
        # FIX: Listen for changes to the time combo!
        self.time_combo.currentTextChanged.connect(self.update_cell_list)
        time_layout.addWidget(self.time_combo)
        layout.addLayout(time_layout)

        # --- Cell Columns Selection ---
        layout.addWidget(QLabel("3. Select Cell/Trace Columns (Hold Ctrl/Cmd to select multiple):"))
        self.cell_list = QListWidget()
        self.cell_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self.cell_list)

        # --- Data Preview Table ---
        layout.addWidget(QLabel("Data Preview (First 5 Rows):"))
        self.preview_table = QTableWidget()
        layout.addWidget(self.preview_table)

        # --- Action Buttons ---
        btn_layout = QHBoxLayout()
        btn_import = QPushButton("Import Data")
        btn_cancel = QPushButton("Cancel")
        btn_import.clicked.connect(self.accept_import)
        btn_cancel.clicked.connect(self.reject)
        btn_layout.addWidget(btn_cancel)
        btn_layout.addWidget(btn_import)
        layout.addLayout(btn_layout)

    def on_sheet_changed(self):
        sheet_name = self.sheet_combo.currentText()
        if not sheet_name: return

        df_preview = pd.read_excel(self.xls, sheet_name=sheet_name, nrows=5)
        self.all_columns = [str(c) for c in df_preview.columns.tolist()]

        # Block signals briefly so setting items doesn't trigger update_cell_list prematurely
        self.time_combo.blockSignals(True)
        self.time_combo.clear()
        self.time_combo.addItems(self.all_columns)
        self.time_combo.blockSignals(False)

        # Trigger the filter manually the first time
        self.update_cell_list()

        # Update the Preview Table
        self.preview_table.setColumnCount(len(self.all_columns))
        self.preview_table.setRowCount(len(df_preview))
        self.preview_table.setHorizontalHeaderLabels(self.all_columns)

        for row in range(len(df_preview)):
            for col in range(len(self.all_columns)):
                val = str(df_preview.iat[row, col])
                self.preview_table.setItem(row, col, QTableWidgetItem(val))

    def update_cell_list(self):
        """Filters out the selected time column from the available cell list."""
        current_time_col = self.time_combo.currentText()
        
        # QoL feature: Remember what the user already highlighted so it doesn't 
        # unselect everything if they accidentally click the time dropdown.
        previously_selected = [item.text() for item in self.cell_list.selectedItems()]
        
        self.cell_list.clear()
        
        # Only add the column if it is NOT the chosen time vector
        for col in self.all_columns:
            if col != current_time_col:
                self.cell_list.addItem(col)
        
        # Restore their previous selections if those columns are still in the list
        for i in range(self.cell_list.count()):
            item = self.cell_list.item(i)
            if item.text() in previously_selected:
                item.setSelected(True)

    def accept_import(self):
        self.selected_sheet = self.sheet_combo.currentText()
        self.selected_time = self.time_combo.currentText()
        self.selected_cells = [item.text() for item in self.cell_list.selectedItems()]

        if not self.selected_cells:
            QMessageBox.warning(self, "Warning", "Please select at least one cell column!")
            return
            
        self.accept()
