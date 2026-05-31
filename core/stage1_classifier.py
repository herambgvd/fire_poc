"""
Stage 1 — MobileNetV3-Small binary/multilabel classifier.
Runs on every frame.  Returns [fire_prob, smoke_prob].
Designed for high recall: better to flag a false positive than miss a real fire.
"""

import logging
import time

import cv2
import numpy as np
import torch
import torch.nn as nn
from PIL import Image
from torchvision import models, transforms

logger = logging.getLogger(__name__)


class Stage1Classifier:
    """Lightweight fire/smoke classifier using MobileNetV3-Small."""

    def __init__(self, model_path: str, num_classes: int = 3, device: str = "cpu"):
        self.device = torch.device(device)
        self.num_classes = num_classes

        # ── Image pre-processing (ImageNet normalization) ──
        self.transform = transforms.Compose([
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ])

        # ── Build model ──
        self.model = self._build_model(model_path)
        self.model.eval()
        logger.info(f"Stage 1 classifier loaded from {model_path}")

    # ──────────────────────────────────────────────────────────────────────────
    def _build_model(self, model_path: str) -> nn.Module:
        """Load MobileNetV3-Small with custom head."""
        model = models.mobilenet_v3_small(weights=None)

        # Replace classifier head to match your training setup
        in_features = model.classifier[-1].in_features
        model.classifier[-1] = nn.Linear(in_features, self.num_classes)

        # Load trained weights
        state_dict = torch.load(model_path, map_location=self.device, weights_only=True)

        # Handle DataParallel prefix if present
        if any(k.startswith("module.") for k in state_dict):
            state_dict = {k.replace("module.", ""): v for k, v in state_dict.items()}

        model.load_state_dict(state_dict)
        model.to(self.device)
        return model

    # ──────────────────────────────────────────────────────────────────────────
    def predict(self, bgr_frame: np.ndarray) -> dict:
        """
        Run classification on a single BGR frame.

        Returns:
            dict with keys:
                probs    – list[float]  per-class probabilities
                fire     – float        fire probability
                smoke    – float        smoke probability
                time_ms  – float        inference time in ms
        """
        # Convert BGR → RGB PIL
        pil_img = Image.fromarray(cv2.cvtColor(bgr_frame, cv2.COLOR_BGR2RGB))
        tensor = self.transform(pil_img).unsqueeze(0).to(self.device)

        t0 = time.perf_counter()
        with torch.no_grad():
            logits = self.model(tensor)
            # Use softmax since the model was trained with CrossEntropy (3-class)
            probs = torch.softmax(logits, dim=1).cpu().numpy()[0]
        elapsed = (time.perf_counter() - t0) * 1000

        # Class mapping for 2-class model: 0=Fire/Smoke, 1=Normal
        fire_prob = float(probs[0])
        normal_prob = float(probs[1]) if len(probs) > 1 else 0.0
        
        return {
            "probs": probs.tolist(),
            "fire": fire_prob,
            "smoke": fire_prob,  # Trigger for both fire/smoke using the same binary prob
            "normal": normal_prob,
            "time_ms": elapsed,
        }

    def is_triggered(self, result: dict, threshold: float) -> tuple:
        """
        Determine if fire or smoke exceeds the threshold.
        Returns (fire_flag: bool, smoke_flag: bool).
        """
        return (result["fire"] >= threshold, result["smoke"] >= threshold)
