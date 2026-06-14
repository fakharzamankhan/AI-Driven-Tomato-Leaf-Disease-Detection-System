import json
from pathlib import Path

import numpy as np

_model = None
_class_names = None
_loaded_model_path = None


class ModelNotAvailableError(RuntimeError):
    pass


def _default_classes() -> list[str]:
    return ["Early Blight", "Late Blight", "Leaf Mold", "Healthy"]


def _read_class_names(class_json_path: Path) -> list[str]:
    try:
        raw_names = json.loads(class_json_path.read_text(encoding="utf-8"))
    except Exception:
        return _default_classes()
    cleaned_names = []
    for name in raw_names:
        cleaned = str(name).replace("___", " ").replace("_", " ").replace("Tomato ", "")
        cleaned_names.append(cleaned.strip() or "Unknown")
    return cleaned_names or _default_classes()


def get_class_names(
    class_json_path: str | Path = "models/class_names.json",
) -> list[str]:
    global _class_names
    if _class_names is not None:
        return _class_names
    path = Path(class_json_path)
    if not path.is_absolute():
        path = Path.cwd() / path
    if path.exists():
        _class_names = _read_class_names(path)
    else:
        _class_names = _default_classes()
    return _class_names


def load_model(model_path: str | Path):
    global _model, _loaded_model_path
    resolved_path = Path(model_path).resolve()
    if not resolved_path.exists():
        return None
    if _model is not None and _loaded_model_path == str(resolved_path):
        return _model
    import tensorflow as tf

    _model = tf.keras.models.load_model(str(resolved_path))
    _loaded_model_path = str(resolved_path)
    return _model


def get_input_shape(model_path: str | Path) -> tuple[int, int] | None:
    model = load_model(model_path)
    if model is None:
        return None
    try:
        shape = model.input_shape
        if shape and len(shape) >= 3:
            return int(shape[1]), int(shape[2])
    except Exception:
        return None
    return None


def predict(image_tensor, model_path: str | Path) -> tuple[str, float]:
    model = load_model(model_path)
    if model is None:
        raise ModelNotAvailableError(f"Model not found at {model_path}")

    probabilities = model.predict(image_tensor, verbose=0)
    scores = (
        probabilities[0] if hasattr(probabilities[0], "__len__") else [probabilities[0]]
    )
    best_index = int(np.argmax(scores))
    confidence = float(scores[best_index])

    class_names = get_class_names()
    if best_index < len(class_names):
        label = class_names[best_index]
    else:
        label = f"Class {best_index}" if best_index < len(scores) else "Unknown"

    return label, confidence
