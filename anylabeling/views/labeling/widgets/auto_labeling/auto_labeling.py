import os

from PyQt5 import uic
from PyQt5.QtWidgets import QWidget
from PyQt5.QtCore import pyqtSignal, pyqtSlot
from PyQt5 import QtGui

from anylabeling.services.auto_labeling.model_manager import ModelManager
from anylabeling.services.auto_labeling.types import AutoLabelingMode


class AutoLabelingWidget(QWidget):
    new_model_selected = pyqtSignal(str)
    prediction_requested = pyqtSignal(QtGui.QImage)
    auto_segmentation_requested = pyqtSignal()
    auto_segmentation_disabled = pyqtSignal()
    auto_labeling_mode_changed = pyqtSignal(AutoLabelingMode)
    undo_auto_labeling_action_requested = pyqtSignal()
    clear_auto_labeling_action_requested = pyqtSignal()
    finish_auto_labeling_object_action_requested = pyqtSignal()

    def __init__(self, parent):
        super().__init__()
        self.parent = parent
        current_dir = os.path.dirname(__file__)
        uic.loadUi(os.path.join(current_dir, "auto_labeling.ui"), self)

        self.model_manager = ModelManager()
        self.model_manager.new_model_status.connect(self.on_new_model_status)
        self.new_model_selected.connect(self.model_manager.load_model)
        self.model_manager.model_loaded.connect(self.update_visible_buttons)
        self.model_manager.model_loaded.connect(
            self.enable_model_select_combobox
        )
        self.model_manager.new_auto_labeling_result.connect(
            lambda auto_labeling_result: self.parent.new_shapes_from_auto_labeling(
                auto_labeling_result
            )
        )
        self.prediction_requested.connect(
            lambda image: self.model_manager.predict_shapes(image)
        )
        self.model_manager.auto_segmentation_model_selected.connect(
            self.auto_segmentation_requested
        )
        self.model_manager.auto_segmentation_model_unselected.connect(
            self.auto_segmentation_disabled
        )

        # Add models to combobox
        self.model_select_combobox.clear()
        self.model_select_combobox.addItem("No Model", userData=None)
        for model_info in self.model_manager.get_model_infos().values():
            self.model_select_combobox.addItem(
                model_info["display_name"], userData=model_info["name"]
            )

        # Auto labeling buttons
        self.button_run.setShortcut("I")
        self.button_run.clicked.connect(self.run_prediction)
        self.button_add_point.clicked.connect(
            lambda: self.set_auto_labeling_mode(
                AutoLabelingMode.ADD, AutoLabelingMode.POINT
            )
        )
        self.button_remove_point.clicked.connect(
            lambda: self.set_auto_labeling_mode(
                AutoLabelingMode.REMOVE, AutoLabelingMode.POINT
            )
        )
        self.button_add_rect.clicked.connect(
            lambda: self.set_auto_labeling_mode(
                AutoLabelingMode.ADD, AutoLabelingMode.RECTANGLE
            )
        )
        self.button_undo.clicked.connect(
            self.undo_auto_labeling_action_requested
        )
        self.button_clear.clicked.connect(
            self.clear_auto_labeling_action_requested
        )
        self.button_finish_object.clicked.connect(
            self.finish_auto_labeling_object_action_requested
        )
        self.button_finish_object.setShortcut("F")

        # Hide labeling buttons by default
        self.hide_labeling_buttons()

        # Handle close button
        self.button_close.clicked.connect(self.unload_and_hide)

        # Handle model select combobox
        self.model_select_combobox.currentIndexChanged.connect(
            self.on_model_select_combobox_changed
        )

    @pyqtSlot()
    def update_button_colors(self, auto_labeling_mode):
        """Update button colors"""
        style_sheet = """
            text-align: center;
            margin-right: 3px;
            border-radius: 5px;
            padding: 4px 8px;
            border: 1px solid #999999;
        """
        for button in [
            self.button_add_point,
            self.button_remove_point,
            self.button_add_rect,
            self.button_clear,
            self.button_undo,
            self.button_finish_object,
        ]:
            button.setStyleSheet(style_sheet + "background-color: #ffffff;")
        if auto_labeling_mode.edit_mode == AutoLabelingMode.ADD:
            if auto_labeling_mode.shape_type == AutoLabelingMode.POINT:
                self.button_add_point.setStyleSheet(
                    style_sheet + "background-color: #00ff00;"
                )
            elif auto_labeling_mode.shape_type == AutoLabelingMode.RECTANGLE:
                self.button_add_rect.setStyleSheet(
                    style_sheet + "background-color: #00ff00;"
                )
        elif auto_labeling_mode.edit_mode == AutoLabelingMode.REMOVE:
            if auto_labeling_mode.shape_type == AutoLabelingMode.POINT:
                self.button_remove_point.setStyleSheet(
                    style_sheet + "background-color: #ff0000;"
                )

    def set_auto_labeling_mode(self, edit_mode, shape_type):
        """Set auto labeling mode"""
        self.auto_labeling_mode_changed.emit(
            AutoLabelingMode(edit_mode, shape_type)
        )

    def run_prediction(self):
        """Run prediction"""
        if self.parent.image_path:
            self.prediction_requested.emit(self.parent.image)

    def unload_and_hide(self):
        """Unload model and hide widget"""
        self.model_select_combobox.setCurrentIndex(0)
        self.hide()

    def on_new_model_status(self, status):
        self.model_status_label.setText(status)

    @pyqtSlot()
    def enable_model_select_combobox(self):
        self.model_select_combobox.setEnabled(True)

    def on_model_select_combobox_changed(self, index):
        model_name = self.model_select_combobox.itemData(index)
        # Disable combobox while loading model
        if model_name:
            self.model_select_combobox.setEnabled(False)
        self.hide_labeling_buttons()
        self.new_model_selected.emit(model_name)

    def update_visible_buttons(self, buttons):
        """Update button status"""
        for button in buttons:
            getattr(self, button).show()

    def hide_labeling_buttons(self):
        """Hide labeling buttons by default"""
        buttons = [
            "button_run",
            "button_add_point",
            "button_remove_point",
            "button_add_rect",
            "button_undo",
            "button_clear",
            "button_finish_object",
        ]
        for button in buttons:
            getattr(self, button).hide()

    def on_new_marks(self, marks):
        """Handle new marks"""
        self.model_manager.set_auto_labeling_marks(marks)
        self.run_prediction()

    def on_open(self):
        pass

    def on_close(self):
        return True
