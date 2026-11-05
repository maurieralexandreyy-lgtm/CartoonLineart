# -*- coding: utf-8 -*-
"""
Cartoon Lineart for Autodesk Maya
Modular entry point and backward-compatible facade.
"""

import sys
import types
import inspect
from pathlib import Path
from importlib import reload as _reload
from maya import cmds, mel

# Automatically reload submodules if previously loaded into the Maya session
_submodules = [
    'core.config', 'core.shading', 'core.presets', 'core.deformers',
    'core.utils', 'core.follow', 'core.mirror', 'core.listeners',
    'core.stroke', 'ui.pyside_compat', 'ui.theme', 'ui.widgets',
    'ui.main_window'
]
for _mod in _submodules:
    if _mod in sys.modules:
        try:
            _reload(sys.modules[_mod])
        except Exception:
            pass

import core.config as config
from core.shading import (
    findOrCreateShaderForColor, getLineMeshColor,
    detectOrCreateShader, assignLineShader
)
from core.presets import (
    DEFAULT_BASIC_PRESET, DEFAULT_INKBRUSH_PRESET,
    get_presets_file_path, load_all_presets,
    save_user_preset, delete_user_preset
)
from core.deformers import (
    removeSmoothFromStrokeMesh, removeDisplacementFromStrokeMesh,
    applySmoothToStrokeMesh, applyDisplacementToStrokeMesh,
    applyNoiseToStrokeMesh
)
from core.utils import (
    solve_param_pair, find_best_edge_pair_for_point,
    reset_pivots_to_origin, get_target_mesh_for_line,
    get_selected_mesh_from_scene
)
from core.follow import (
    applyFollowMethod, removeFollowMethodFromLine,
    changeLineFollowMethod
)
from core.mirror import (
    generate_mirror_name, mirrorSingleLine
)
from core.stroke import (
    get_or_create_master_group, get_next_line_id,
    setupStrokeMeshAttributes, createTaperController,
    shrinkWrapItem, bakeAllLines, extractLineAttributes,
    applyExtractedAttributes, rebuildLine, drawLine
)
from core.listeners import (
    clean_orphaned_stroke_brushes, setup_selection_listener,
    kill_selection_listener, arm_stroke_listener,
    kill_stroke_listener, setup_tool_listener,
    kill_tool_listener, find_lines_for_maya_selection
)

from ui.pyside_compat import (
    QtWidgets, QtCore, QtGui,
    QRegExp, QRegExpValidator,
    get_maya_main_window
)
from ui.theme import comic_theme
from ui.widgets import (
    ComicNameDisplay, CoolNameDisplay, ComicTitleBanner, ComicSeparator,
    ComicCollapsibleHeader, ComicBrushButton, ComicCheckBox,
    ComicSettingCheckBox, ComicTrashButton, ComicFooterAccents,
    RebuildLineOptionsDialog, lineListDisplayWidget
)
from ui.main_window import (
    DockableWindow, mainWidget, close_existing_ui, launch_ui
)

# Dynamic attribute proxy for config state
def __getattr__(name):
    """
    PEP 562 dynamic attribute lookup to keep state synchronized with core.config.
    """
    if hasattr(config, name):
        return getattr(config, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


def __dir__():
    return sorted(set(list(globals().keys()) + dir(config)))


def _get_active_shelf_layout():
    try:
        top_shelf = mel.eval('$tmp = $gShelfTopLevel;')
        if top_shelf and cmds.tabLayout(top_shelf, exists=True):
            current_tab = cmds.tabLayout(top_shelf, query=True, selectTab=True)
            if current_tab:
                full_path = f"{top_shelf}|{current_tab}"
                if cmds.shelfLayout(full_path, exists=True):
                    return full_path
                return current_tab
    except Exception:
        pass

    try:
        if cmds.tabLayout("ShelfLayout", exists=True):
            current_tab = cmds.tabLayout("ShelfLayout", query=True, selectTab=True)
            if current_tab:
                if cmds.shelfLayout(f"ShelfLayout|{current_tab}", exists=True):
                    return f"ShelfLayout|{current_tab}"
                return current_tab
    except Exception:
        pass

    try:
        all_shelves = cmds.lsUI(type="shelfLayout") or []
        for sh in all_shelves:
            if cmds.shelfLayout(sh, query=True, visible=True):
                return sh
        if all_shelves:
            return all_shelves[0]
    except Exception:
        pass

    return None


def onMayaDroppedPythonFile(*args):
    """
    Called automatically when dragging and dropping this file into Maya viewport.
    Creates/updates shelf button and opens Cartoon Lineart.
    """
    install_folder = None
    if args and len(args) > 0 and args[0]:
        p = Path(args[0])
        install_folder = p.parent.resolve().as_posix() if p.is_file() else p.resolve().as_posix()
    elif '__file__' in globals() and globals()['__file__']:
        p = Path(globals()['__file__'])
        install_folder = p.parent.resolve().as_posix() if p.is_file() else p.resolve().as_posix()
    else:
        try:
            p = Path(inspect.getfile(inspect.currentframe()))
            install_folder = p.parent.resolve().as_posix() if p.is_file() else p.resolve().as_posix()
        except Exception:
            install_folder = Path.cwd().resolve().as_posix()

    shelf_payload = (
        "import sys\n"
        f"install_dir = r'{install_folder}'\n"
        "if install_dir not in sys.path:\n"
        "    sys.path.insert(0, install_dir)\n"
        "import cartoon_lineart\n"
        "from importlib import reload\n"
        "reload(cartoon_lineart)\n"
        "cartoon_lineart.launch_ui()\n"
    )

    icon_path = Path(install_folder) / "ico" / "button.png"
    if not icon_path.exists():
        icon_path = Path(install_folder) / "button.png"
    icon_file = icon_path.as_posix() if icon_path.exists() else "button.png"

    active_shelf = _get_active_shelf_layout()
    if active_shelf:
        try:
            children = cmds.shelfLayout(active_shelf, query=True, childArray=True) or []
            for child in children:
                if cmds.shelfButton(child, exists=True):
                    lbl = cmds.shelfButton(child, query=True, imageOverlayLabel=True) or ""
                    cmd = cmds.shelfButton(child, query=True, command=True) or ""
                    img = cmds.shelfButton(child, query=True, image1=True) or ""
                    if lbl in ("Lineart", "Cartoon Lineart", "Cool Lines") or "cartoon_lineart" in cmd or "button.png" in img:
                        cmds.deleteUI(child)
        except Exception:
            pass

        try:
            cmds.shelfButton(
                parent=active_shelf,
                imageOverlayLabel="",
                annotation="Launch Cartoon Lineart :)",
                image1=icon_file,
                command=shelf_payload,
                sourceType="python"
            )
            print(f"[Cartoon Lineart] Shelf button created on: {active_shelf}")
            cmds.headsUpMessage("Cartoon Lineart shelf button created!", time=3.0)
        except Exception as e:
            print(f"[Cartoon Lineart] Warning creating shelf button: {e}")

    launch_ui()


if __name__ == '__main__':
    launch_ui()
