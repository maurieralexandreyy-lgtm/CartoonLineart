import os
import json
from pathlib import Path
from maya import cmds

DEFAULT_BASIC_PRESET = {
    "line_default_scale": 0.1,
    "scale_profile": 0.1,
    "line_resolution": 5,
    "line_subdiv_offset": 0.01,
    "curve_points": 4,
    "smooth_curve": 1.0,
    "line_sweep_shape": 1.0,
    "roundness": 1.0,
    "current_line_color": [0.0, 0.0, 0.0],
    "color": [0.0, 0.0, 0.0],
    "line_smoothable": False,
    "smoothable": False,
    "line_displacement": False,
    "displacement": False,
    "line_disp_type": "noise",
    "disp_type": "noise",
    "Sides": 6,
    "Start_value": 0.0,
    "End_value": 0.0,
    "Pt1_value": 0.3,
    "PtLast_value": 0.7,
    "smooth_method": 0,
    "smooth_divisions": 1,
    "disp_strength": 0.03,
    "disp_offset": 0.0,
    "noise_type": 1,
    "frequency": 12.0,
    "ratio": 0.7,
    "time": 0.0
}
DEFAULT_NEUTRAL_PRESET = DEFAULT_BASIC_PRESET

DEFAULT_INKBRUSH_PRESET = {
    "line_default_scale": 0.15,
    "scale_profile": 0.15,
    "line_resolution": 5,
    "line_subdiv_offset": 0.01,
    "curve_points": 4,
    "smooth_curve": 1.0,
    "line_sweep_shape": 0.85,
    "roundness": 0.85,
    "current_line_color": [0.0, 0.0, 0.0],
    "color": [0.0, 0.0, 0.0],
    "line_smoothable": True,
    "smoothable": True,
    "line_displacement": True,
    "displacement": True,
    "line_disp_type": "noise",
    "disp_type": "noise",
    "Sides": 8,
    "Start_value": 0.0,
    "End_value": 0.0,
    "Pt1_value": 0.35,
    "PtLast_value": 0.75,
    "smooth_method": 0,
    "smooth_divisions": 1,
    "disp_strength": 0.025,
    "disp_offset": 0.0,
    "noise_type": 1,
    "frequency": 14.0,
    "ratio": 0.7,
    "time": 0.0
}


def get_presets_file_path():
    try:
        # Package root is parent of core/
        pkg_root = Path(__file__).resolve().parent.parent
        local_path = (pkg_root / "presets.json").as_posix()
    except Exception:
        local_path = os.path.join(os.getcwd(), "presets.json")

    try:
        if not os.path.exists(local_path):
            with open(local_path, "w") as f:
                json.dump({"Basic": DEFAULT_BASIC_PRESET, "InkBrush": DEFAULT_INKBRUSH_PRESET}, f, indent=2)
        return local_path
    except Exception:
        pref_dir = cmds.internalVar(userPrefDir=True)
        fallback_path = os.path.join(pref_dir, "CartoonLineart_presets.json")
        if not os.path.exists(fallback_path):
            try:
                with open(fallback_path, "w") as f:
                    json.dump({"Basic": DEFAULT_BASIC_PRESET, "InkBrush": DEFAULT_INKBRUSH_PRESET}, f, indent=2)
            except Exception:
                pass
        return fallback_path


def load_all_presets():
    file_path = get_presets_file_path()
    presets = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                presets = json.load(f)
        except Exception:
            presets = {}
    if not isinstance(presets, dict):
        presets = {}

    # Migrate legacy names if present
    if "neutral" in presets:
        if "Basic" not in presets:
            presets["Basic"] = presets.pop("neutral")
        else:
            presets.pop("neutral")
    if "TestMangaStyle" in presets:
        if "InkBrush" not in presets:
            presets["InkBrush"] = presets.pop("TestMangaStyle")
        else:
            presets.pop("TestMangaStyle")
    if "custom" in presets:
        presets.pop("custom")

    if "Basic" not in presets:
        presets["Basic"] = dict(DEFAULT_BASIC_PRESET)
    return presets


def save_user_preset(name, data):
    file_path = get_presets_file_path()
    presets = load_all_presets()
    presets[name] = data
    try:
        with open(file_path, "w") as f:
            json.dump(presets, f, indent=2)
        return True
    except Exception as e:
        print(f"Warning: could not save preset file: {e}")
        return False


def delete_user_preset(name):
    if not name or name in ["Basic", "neutral", "Custom", "custom"]:
        return False
    file_path = get_presets_file_path()
    presets = {}
    if os.path.exists(file_path):
        try:
            with open(file_path, "r") as f:
                presets = json.load(f)
        except Exception:
            presets = {}
    if not isinstance(presets, dict):
        presets = {}
    if name in presets:
        presets.pop(name)
        try:
            with open(file_path, "w") as f:
                json.dump(presets, f, indent=2)
            return True
        except Exception as e:
            print(f"Warning: could not delete preset: {e}")
            return False
    return False

