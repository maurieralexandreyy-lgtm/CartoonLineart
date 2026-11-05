"""
Cartoon Lineart — Installer

Drag and drop this file into the Maya viewport to install the shelf button and launch the tool.
"""
from pathlib import Path
from maya import cmds


def _get_active_shelf_layout():
    import maya.mel as mel
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
            import inspect
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

    # Resolve button icon (button.png)
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
    else:
        print("[Cartoon Lineart] Warning: Active shelf could not be found.")

    # Execute payload immediately to launch the UI on drop
    try:
        exec(shelf_payload)
    except Exception as e:
        print(f"[Cartoon Lineart] Error launching UI: {e}")


if __name__ == '__main__':
    onMayaDroppedPythonFile()
