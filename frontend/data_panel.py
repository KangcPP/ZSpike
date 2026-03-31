import re
import json
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QPushButton, QTreeWidget, 
                               QTreeWidgetItem, QFileDialog, QMenu, QInputDialog,
                               QMessageBox)
from PySide6.QtCore import Qt, QMimeData
from PySide6.QtWidgets import QAbstractItemView
from frontend.import_dialog import ImportDialog


class DraggableTree(QTreeWidget):
    def __init__(self):
        super().__init__()
        self.setDragEnabled(True)
        from PySide6.QtWidgets import QAbstractItemView
        self.setDragDropMode(QAbstractItemView.DragDropMode.DragOnly)

    def mimeData(self, items):
        mime = QMimeData()
        item = items[0]
        data = item.data(0, Qt.ItemDataRole.UserRole)
        
        if data and data.get("type") == "trace":            
            export_data = data.copy()
            
            parent_cell = item.parent()
            export_data['display_name'] = parent_cell.text(0)
            
            mime.setText(json.dumps(export_data))
        return mime

class DataPanel(QWidget):
    def __init__(self):
        super().__init__()
        
        layout = QVBoxLayout()
        layout.setContentsMargins(5, 5, 5, 5) 
        
        self.btn_add_recording = QPushButton("+ Add Recording (Excel)")
        self.btn_add_recording.clicked.connect(self.open_file_dialog)
        layout.addWidget(self.btn_add_recording)
        
        # Use our new custom tree instead of the default QTreeWidget
        self.tree = DraggableTree()
        self.tree.setHeaderLabel("Loaded Data")
        self.tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.tree.customContextMenuRequested.connect(self.open_context_menu)
        layout.addWidget(self.tree)
        
        self.setLayout(layout)

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "Select Excel File", 
            "", 
            "Excel Files (*.xlsx *.xls);;CSV Files (*.csv)"
        )
        
        if file_path:
            dialog = ImportDialog(file_path, parent=self)
            if dialog.exec(): 
                # Notice we now pass the file_path to the tree!
                self.add_recording_to_tree(file_path, dialog.selected_sheet, dialog.selected_time, dialog.selected_cells)

    def add_recording_to_tree(self, file_path, sheet_name, time_col, cell_cols):
        recording_item = QTreeWidgetItem(self.tree)
        recording_item.setText(0, sheet_name)
        
        recording_data = {"type": "recording"}
        recording_item.setData(0, Qt.ItemDataRole.UserRole, recording_data)
        
        for cell in cell_cols:
            cell_item = QTreeWidgetItem(recording_item)
            cell_item.setText(0, cell)
            cell_data = {"type": "cell"}
            cell_item.setData(0, Qt.ItemDataRole.UserRole, cell_data)

            # --- NEW: Add the 3rd Level (The Data Arrays) ---
            trace_item = QTreeWidgetItem(cell_item)
            trace_item.setText(0, "raw_trace")
            
            # This is the vital metadata that will travel via drag-and-drop
            trace_data = {
                "type": "trace",
                "file_path": file_path,
                "sheet_name": sheet_name,
                "time_col": time_col,
                "cell_col": cell,
                "trace_type": "raw_trace"
            }
            trace_item.setData(0, Qt.ItemDataRole.UserRole, trace_data)
        
        recording_item.setExpanded(True)

    def open_context_menu(self, position):
        # Find exactly which item is under the mouse cursor
        item = self.tree.itemAt(position)
        
        # If they right-clicked on empty white space, do nothing
        if not item:
            return

        # Create a dropdown menu on the fly
        menu = QMenu()
        rename_action = menu.addAction("Rename")
        
        # Show the menu at the exact screen coordinates of the mouse click
        # .exec() halts the local execution until the user clicks an option or clicks away
        action = menu.exec(self.tree.viewport().mapToGlobal(position))
        
        # If the user clicked our 'Rename' option, trigger the popup
        if action == rename_action:
            self.rename_item(item)

    def rename_item(self, item):
        current_name = item.text(0)
        
        dialog = QInputDialog(self)
        dialog.setWindowTitle("Rename Item")
        dialog.setLabelText(f"Enter new name: Current: {current_name}")
        dialog.setTextValue(current_name)
        dialog.resize(400, 150) 
        
        if dialog.exec():
            raw_name = dialog.textValue().strip()
            
            if not raw_name:
                return

            sanitized_name = re.sub(r'[<>:"/\\|?*\x00-\x1F]', '_', raw_name)

            lower_name = sanitized_name.lower()
            reserved_words = {'true', 'false', 'nan', 'null', 'none', 'inf'}
            
            is_numeric = False
            try:
                float(sanitized_name)
                is_numeric = True
            except ValueError:
                pass
                
            if lower_name in reserved_words or is_numeric:
                QMessageBox.warning(
                    self, 
                    "Invalid Name", 
                    f"The name '{sanitized_name}' is a reserved data keyword or number.\n\n"
                    "To prevent data export errors, please include at least one letter."
                )
                return

            item.setText(0, sanitized_name)
