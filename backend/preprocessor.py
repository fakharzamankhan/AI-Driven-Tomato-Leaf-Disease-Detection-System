from pathlib import Path

import cv2
import numpy as np

DEFAULT_INPUT_SIZE = (128, 128)
MIN_FOLIAGE_RATIO = 0.25
MIN_LARGEST_COMPONENT_RATIO = 0.25
MAX_COMPONENT_COMPLEXITY = 9.0
MIN_EDGE_RATIO = 0.015


def _empty_metrics() -> dict[str, float]:
    return {
        "foliage_ratio": 0.0,
        "largest_component_ratio": 0.0,
        "component_complexity": 0.0,
        "edge_ratio": 0.0,
    }


def validate_tomato_leaf_image(
    image_path: str | Path,
    min_foliage_ratio: float = MIN_FOLIAGE_RATIO,
    min_largest_component_ratio: float = MIN_LARGEST_COMPONENT_RATIO,
    max_component_complexity: float = MAX_COMPONENT_COMPLEXITY,
    min_edge_ratio: float = MIN_EDGE_RATIO,
) -> tuple[bool, dict[str, float]]:
    path = Path(image_path)
    if not path.exists():
        return False, _empty_metrics()

    bgr_image = cv2.imread(str(path))
    if bgr_image is None:
        return False, _empty_metrics()

    hsv_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2HSV)
    hue, saturation, value = cv2.split(hsv_image)

    green_mask = (hue >= 25) & (hue <= 95) & (saturation >= 35) & (value >= 30)
    yellow_brown_mask = (hue >= 8) & (hue <= 35) & (saturation >= 40) & (value >= 20)
    foliage_mask = green_mask | yellow_brown_mask
    foliage_ratio = float(np.mean(foliage_mask))

    mask_uint8 = foliage_mask.astype(np.uint8) * 255
    label_count, labels, stats, _ = cv2.connectedComponentsWithStats(mask_uint8, 8)
    total_pixels = float(hue.size) if hue.size else 1.0

    if label_count > 1:
        largest_area = int(np.max(stats[1:, cv2.CC_STAT_AREA]))
        largest_component_ratio = float(largest_area / total_pixels)
    else:
        largest_area = 0
        largest_component_ratio = 0.0

    component_complexity = 999.0
    if label_count > 1 and largest_area > 0:
        largest_component_index = 1 + int(np.argmax(stats[1:, cv2.CC_STAT_AREA]))
        largest_component_mask = (labels == largest_component_index).astype(
            np.uint8
        ) * 255
        contours, _ = cv2.findContours(
            largest_component_mask,
            cv2.RETR_EXTERNAL,
            cv2.CHAIN_APPROX_SIMPLE,
        )
        if contours:
            perimeter = cv2.arcLength(contours[0], True)
            area = cv2.contourArea(contours[0]) + 1e-6
            component_complexity = float((perimeter * perimeter) / (4 * np.pi * area))

    grayscale = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2GRAY)
    edge_ratio = float(np.mean(cv2.Canny(grayscale, 80, 160) > 0))

    is_valid = (
        foliage_ratio >= min_foliage_ratio
        and largest_component_ratio >= min_largest_component_ratio
        and component_complexity <= max_component_complexity
        and edge_ratio >= min_edge_ratio
    )

    metrics = {
        "foliage_ratio": foliage_ratio,
        "largest_component_ratio": largest_component_ratio,
        "component_complexity": component_complexity,
        "edge_ratio": edge_ratio,
    }
    return is_valid, metrics


def preprocess(
    image_path: str | Path,
    target_size: tuple[int, int] | None = None,
) -> np.ndarray:
    size = target_size or DEFAULT_INPUT_SIZE
    path = Path(image_path)
    if not path.exists():
        raise FileNotFoundError(f"Image not found: {image_path}")

    bgr_image = cv2.imread(str(path))
    if bgr_image is None:
        raise ValueError(f"Could not read image: {image_path}")

    rgb_image = cv2.cvtColor(bgr_image, cv2.COLOR_BGR2RGB)
    resized_image = cv2.resize(rgb_image, size)
    normalized_image = resized_image.astype(np.float32) / 255.0
    return np.expand_dims(normalized_image, axis=0)
