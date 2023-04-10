import logging
import os
from copy import deepcopy

import onnxruntime
import cv2
import numpy as np
from PyQt5 import QtCore

from anylabeling.views.labeling.shape import Shape
from anylabeling.views.labeling.utils.opencv import qt_img_to_cv_img
from .model import Model


class SegmentAnything(Model):
    """Segmentation model using SegmentAnything"""

    class Meta:
        required_config_names = [
            "type",
            "name",
            "display_name",
            "encoder_model_path",
            "decoder_model_path",
        ]
        buttons = [
            "button_run",
            "button_add_point",
            "button_remove_point",
            "button_add_rect",
            "button_undo",
            "button_clear",
            "button_finish_object",
        ]

    def __init__(self, config_path) -> None:
        # Run the parent class's init method
        super().__init__(config_path)
        self.input_size = self.config["input_size"]
        self.max_width = self.config["max_width"]
        self.max_height = self.config["max_height"]

        # Get encoder and decoder model paths
        encoder_model_abs_path = self.get_model_abs_path(
            self.config["encoder_model_path"]
        )
        if not os.path.isfile(encoder_model_abs_path):
            raise Exception(f"Encoder not found: {encoder_model_abs_path}")
        decoder_model_abs_path = self.get_model_abs_path(
            self.config["decoder_model_path"]
        )
        if not os.path.isfile(decoder_model_abs_path):
            raise Exception(f"Decoder not found: {decoder_model_abs_path}")

        # Load models
        self.encoder_session = onnxruntime.InferenceSession(
            encoder_model_abs_path
        )
        self.decoder_session = onnxruntime.InferenceSession(
            decoder_model_abs_path
        )

        # Mark for auto labeling
        # points, rectangles
        self.marks = []

        self.last_image = None
        self.last_image_embedding = None
        self.resized_ratio = [1, 1]

    def set_auto_labeling_marks(self, marks):
        """Set auto labeling marks"""
        self.marks = marks

    def get_input_points(self):
        """Get input points"""
        points = []
        labels = []
        for mark in self.marks:
            if mark["type"] == "point":
                points.append(mark["data"])
                labels.append(mark["label"])
        points, labels = np.array(points), np.array(labels)

        # Resize points based on scales
        points[:, 0] = points[:, 0] * self.resized_ratio[0]
        points[:, 1] = points[:, 1] * self.resized_ratio[1]
        return points, labels

    def pre_process(self, image):
        # Resize by max width and max height
        # In the original code, the image is resized to long side 1024
        # However, there is a positional deviation when the image does not
        # have the same aspect ratio as in the exported ONNX model (2250x1500)
        # => Resize by max width and max height
        max_width = self.max_width
        max_height = self.max_height
        self.original_size = image.shape[:2]
        h, w = image.shape[:2]
        if w > max_width:
            h = int(h * max_width / w)
            w = max_width
        if h > max_height:
            w = int(w * max_height / h)
            h = max_height
        image = cv2.resize(image, (w, h))
        self.resized_ratio = (
            w / self.original_size[1],
            h / self.original_size[0],
        )

        # Pad to have size at least max_width x max_height
        h, w = image.shape[:2]
        padh = max_height - h
        padw = max_width - w
        image = np.pad(image, ((0, padh), (0, padw), (0, 0)), mode="constant")
        self.size_after_apply_max_width_height = image.shape[:2]

        # Normalize
        pixel_mean = np.array([123.675, 116.28, 103.53]).reshape(1, 1, -1)
        pixel_std = np.array([58.395, 57.12, 57.375]).reshape(1, 1, -1)
        x = (image - pixel_mean) / pixel_std

        # Padding to square
        h, w = x.shape[:2]
        padh = self.input_size - h
        padw = self.input_size - w
        x = np.pad(x, ((0, padh), (0, padw), (0, 0)), mode="constant")
        x = x.astype(np.float32)

        # Transpose
        x = x.transpose(2, 0, 1)[None, :, :, :]

        encoder_inputs = {
            "x": x,
        }
        return encoder_inputs

    def run_encoder(self, encoder_inputs):
        output = self.encoder_session.run(None, encoder_inputs)
        image_embedding = output[0]
        return image_embedding

    @staticmethod
    def get_preprocess_shape(oldh: int, oldw: int, long_side_length: int):
        """
        Compute the output size given input size and target long side length.
        """
        scale = long_side_length * 1.0 / max(oldh, oldw)
        newh, neww = oldh * scale, oldw * scale
        neww = int(neww + 0.5)
        newh = int(newh + 0.5)
        return (newh, neww)

    def apply_coords(
        self, coords: np.ndarray, original_size, target_length
    ) -> np.ndarray:
        """
        Expects a numpy array of length 2 in the final dimension. Requires the
        original image size in (H, W) format.
        """
        old_h, old_w = original_size
        new_h, new_w = SegmentAnything.get_preprocess_shape(
            original_size[0], original_size[1], target_length
        )
        coords = deepcopy(coords).astype(float)
        coords[..., 0] = coords[..., 0] * (new_w / old_w)
        coords[..., 1] = coords[..., 1] * (new_h / old_h)
        return coords

    def run_decoder(self, image_embedding):
        input_points, input_labels = self.get_input_points()

        # Add a batch index, concatenate a padding point, and transform.
        onnx_coord = np.concatenate(
            [input_points, np.array([[0.0, 0.0]])], axis=0
        )[None, :, :]
        onnx_label = np.concatenate([input_labels, np.array([-1])], axis=0)[
            None, :
        ].astype(np.float32)
        onnx_coord = self.apply_coords(
            onnx_coord, self.size_after_apply_max_width_height, self.input_size
        ).astype(np.float32)

        # Create an empty mask input and an indicator for no mask.
        onnx_mask_input = np.zeros((1, 1, 256, 256), dtype=np.float32)
        onnx_has_mask_input = np.zeros(1, dtype=np.float32)

        decoder_inputs = {
            "image_embeddings": image_embedding,
            "point_coords": onnx_coord,
            "point_labels": onnx_label,
            "mask_input": onnx_mask_input,
            "has_mask_input": onnx_has_mask_input,
            "orig_im_size": np.array(
                self.size_after_apply_max_width_height, dtype=np.float32
            ),
        }
        masks, _, _ = self.decoder_session.run(None, decoder_inputs)
        masks = masks > 0.0
        masks = masks.reshape(self.size_after_apply_max_width_height)
        return masks

    def post_process(self, masks):
        """
        Post process masks
        """
        shapes = []
        # Find contours
        contours, _ = cv2.findContours(
            masks.astype(np.uint8), cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE
        )
        for contour in contours:
            # Approximate contour
            epsilon = 0.001 * cv2.arcLength(contour, True)
            approx = cv2.approxPolyDP(contour, epsilon, True)
            points = approx.reshape(-1, 2)

            # Scale points
            points[:, 0] = points[:, 0] / self.resized_ratio[0]
            points[:, 1] = points[:, 1] / self.resized_ratio[1]
            points = points.tolist()
            if len(points) < 3:
                continue
            points.append(points[0])

            # Create shape
            shape = Shape(flags={})
            for point in points:
                point[0] = int(point[0])
                point[1] = int(point[1])
                shape.add_point(QtCore.QPointF(point[0], point[1]))
            shape.type = "polygon"
            shape.closed = True
            shape.fill_color = "#000000"
            shape.line_color = "#000000"
            shape.line_width = 1
            shape.label = "unknown"
            shape.selected = False
            shapes.append(shape)

        return shapes

    def predict_shapes(self, image):
        """
        Predict shapes from image
        """
        if image is None:
            return []

        shapes = []
        try:
            # Prevent re-running the encoder if the image is the same
            if image == self.last_image:
                image_embedding = self.last_image_embedding
            else:
                cv_image = qt_img_to_cv_img(image)
                encoder_inputs = self.pre_process(cv_image)
                image_embedding = self.run_encoder(encoder_inputs)
                self.last_image = image
                self.last_image_embedding = image_embedding
            masks = self.run_decoder(image_embedding)
            shapes = self.post_process(masks)
        except Exception as e:
            logging.warning("Could not inference model")
            logging.warning(e)
            return []

        return shapes

    def unload(self):
        if self.encoder_session:
            self.encoder_session = None
        if self.decoder_session:
            self.decoder_session = None
