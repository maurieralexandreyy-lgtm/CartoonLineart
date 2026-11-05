# -*- coding: utf-8 -*-
from maya import cmds
import core.config as config


def clean_orphaned_stroke_brushes():
    """
    Deletes any orphaned strokeDefaultBrush or stroke brush nodes not used by any stroke.
    Never deletes Maya's template 'defaultBrush'.
    """
    try:
        # Check specifically for 'strokeDefaultBrush'
        if cmds.objExists("strokeDefaultBrush"):
            strokes = cmds.listConnections("strokeDefaultBrush", type="stroke") or []
            if not strokes:
                try:
                    cmds.delete("strokeDefaultBrush")
                except Exception:
                    pass

        # Check for any other stroke brush patterns
        candidates = cmds.ls("strokeDefaultBrush*", "*DefaultBrush*", "*stroke*brush*", "*stroke*Brush*", type="brush") or []
        for b in candidates:
            if b == "defaultBrush":
                continue
            if cmds.objExists(b):
                strokes = cmds.listConnections(b, type="stroke") or []
                if not strokes:
                    try:
                        cmds.delete(b)
                    except Exception:
                        pass
    except Exception:
        pass


def setup_selection_listener(callback):
    """
    Registers a persistent SelectionChanged scriptJob to track active mesh selections.
    """
    kill_selection_listener()
    try:
        config.selection_event_catcher_num = cmds.scriptJob(event=["SelectionChanged", callback])
    except Exception:
        config.selection_event_catcher_num = None


def kill_selection_listener():
    """
    Safely kills the selection scriptJob if active.
    """
    if config.selection_event_catcher_num is not None:
        try:
            cmds.scriptJob(kill=config.selection_event_catcher_num, force=True)
        except Exception:
            pass
        config.selection_event_catcher_num = None


def arm_stroke_listener(callback=None):
    """
    Registers a one-shot SelectionChanged scriptJob to trigger drawLine on stroke completion.
    """
    if callback is None:
        from core.stroke import drawLine
        callback = drawLine

    kill_stroke_listener()
    try:
        config.stroke_event_catcher_num = cmds.scriptJob(runOnce=True, event=["SelectionChanged", callback])
    except Exception:
        config.stroke_event_catcher_num = None


def kill_stroke_listener():
    """
    Safely kills the stroke scriptJob if active.
    """
    if config.stroke_event_catcher_num is not None:
        try:
            cmds.scriptJob(kill=config.stroke_event_catcher_num, force=True)
        except Exception:
            pass
        config.stroke_event_catcher_num = None


def setup_tool_listener(callback):
    """
    Registers a ToolChanged scriptJob to detect tool switches during painting session.
    """
    kill_tool_listener()
    try:
        config.tool_event_catcher_num = cmds.scriptJob(event=["ToolChanged", callback])
    except Exception:
        config.tool_event_catcher_num = None


def kill_tool_listener():
    """
    Safely kills the tool change scriptJob if active.
    """
    if config.tool_event_catcher_num is not None:
        try:
            cmds.scriptJob(kill=config.tool_event_catcher_num, force=True)
        except Exception:
            pass
        config.tool_event_catcher_num = None


def find_lines_for_maya_selection(selection_list, line_data_list):
    """
    Given a list of Maya selection strings (transforms, shapes, components, groups),
    identifies which line items match based on mesh, curve, group, or associated nodes.
    Returns the list of matching line entries.
    """
    if not selection_list:
        return []

    candidates = set()
    for s in selection_list:
        if not s:
            continue
        node = s.split(".")[0]
        short_name = node.split("|")[-1]
        candidates.add(node)
        candidates.add(short_name)

        if cmds.objExists(node):
            try:
                parents = cmds.listRelatives(node, parent=True, fullPath=False) or []
                for p in parents:
                    candidates.add(p)
                    candidates.add(p.split("|")[-1])
                ancestors = cmds.listRelatives(node, allParents=True, fullPath=False) or []
                for a in ancestors:
                    candidates.add(a)
                    candidates.add(a.split("|")[-1])
                shapes = cmds.listRelatives(node, shapes=True, fullPath=False) or []
                for sh in shapes:
                    candidates.add(sh)
                    candidates.add(sh.split("|")[-1])
                children = cmds.listRelatives(node, children=True, fullPath=False) or []
                for ch in children:
                    candidates.add(ch)
                    candidates.add(ch.split("|")[-1])
            except Exception:
                pass

    matches = []
    for item in line_data_list:
        line_data = item[1] if isinstance(item, tuple) else item
        if not isinstance(line_data, dict):
            continue
        line_ids = {
            line_data.get("mesh"),
            line_data.get("curve"),
            line_data.get("group"),
            line_data.get("name"),
            line_data.get("root_convert_grp"),
            line_data.get("converted_curve_grp"),
            line_data.get("sweep_msh_node"),
            line_data.get("taper_ctrl_node"),
            line_data.get("smooth_node"),
            line_data.get("tex_def_node"),
        }
        line_ids = {v for v in line_ids if v}
        line_ids.update({v.split("|")[-1] for v in list(line_ids)})

        if candidates.intersection(line_ids):
            matches.append(item)

    return matches

