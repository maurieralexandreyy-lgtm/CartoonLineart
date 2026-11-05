# -*- coding: utf-8 -*-
import math
from maya import cmds, mel
import core.config as config
from core.utils import reset_pivots_to_origin, get_selected_mesh_from_scene
from core.shading import getLineMeshColor, assignLineShader
from core.deformers import (
    applySmoothToStrokeMesh,
    removeSmoothFromStrokeMesh,
    applyDisplacementToStrokeMesh,
    removeDisplacementFromStrokeMesh
)
from core.follow import applyFollowMethod, changeLineFollowMethod
from core.listeners import clean_orphaned_stroke_brushes, arm_stroke_listener


def get_or_create_master_group():
    master_grp = "grp_lines"
    if not cmds.objExists(master_grp):
        master_grp = cmds.group(em=True, n=master_grp)
        cmds.xform(master_grp, os=True, pivots=(0, 0, 0))
    return master_grp


def get_next_line_id():
    existing_ids = set()
    # 1. Check in grp_lines
    if cmds.objExists("grp_lines"):
        children = cmds.listRelatives("grp_lines", children=True, type="transform") or []
        for ch in children:
            base = ch.split("|")[-1].lower()
            if base.startswith("line_"):
                try:
                    num_part = base.split("_")[1]
                    existing_ids.add(int(num_part))
                except Exception:
                    pass
    # 2. Check in global_scene_data_obj
    if config.global_scene_data_obj:
        for k in config.global_scene_data_obj.getGlobalLinesData().keys():
            k_lower = k.lower()
            if k_lower.startswith("line_"):
                try:
                    num_part = k_lower.split("_")[1]
                    existing_ids.add(int(num_part))
                except Exception:
                    pass
    next_id = 1
    while next_id in existing_ids:
        next_id += 1
    return next_id


def setupStrokeMeshAttributes(stroke_mesh, sweep_mesh_node, num_driver_points=4, start_scale_value=0.1, line_type="paint", sweep_shape=None):
    """
    Sets up custom cartoon line attributes directly on the stroke mesh transform
    instead of creating a separate network node.
    Locks and hides standard transform attributes (TRS + V) so that selecting the stroke mesh
    in the viewport directly presents the line parameters cleanly in Maya's Channel Box.
    """
    if sweep_shape is None:
        sweep_shape = config.line_sweep_shape

    # 1. Lock and hide standard transform attributes and visibility
    for attr in ['tx', 'ty', 'tz', 'rx', 'ry', 'rz', 'sx', 'sy', 'sz', 'v']:
        try:
            cmds.setAttr(f"{stroke_mesh}.{attr}", lock=True, keyable=False, channelBox=False)
        except Exception:
            pass

    # 2. General profile attributes
    cmds.addAttr(stroke_mesh, at='float', k=True, min=0, shortName='scale_profile')
    cmds.addAttr(stroke_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=sweep_shape, shortName='roundness')
    cmds.setAttr(f"{stroke_mesh}.roundness", sweep_shape)
    cmds.addAttr(stroke_mesh, at='long', k=True, shortName='rotate_profile')
    cmds.setAttr(stroke_mesh + '.rotate_profile', 0)
    cmds.addAttr(stroke_mesh, at='long', k=True, shortName='Sides', min=1, defaultValue=6)
    cmds.setAttr(stroke_mesh + '.Sides', 6)
    cmds.addAttr(stroke_mesh, at='bool', k=True, defaultValue=False, shortName='cap')
    cmds.setAttr(f"{stroke_mesh}.cap", 0)
    cmds.addAttr(stroke_mesh, at='long', k=True, shortName='precision')
    cmds.addAttr(stroke_mesh, at='bool', k=True, shortName='optimize_precision')

    cmds.setAttr(sweep_mesh_node + '.interpolationMode', 0)
    cmds.setAttr(sweep_mesh_node + '.scaleProfileUniform', False)
    default_interpolation_precision = 90  # Default precision set to 90

    cmds.setAttr(stroke_mesh + '.precision', default_interpolation_precision)
    cmds.setAttr(stroke_mesh + '.optimize_precision', 1)

    cmds.connectAttr(stroke_mesh + '.scale_profile', sweep_mesh_node + '.scaleProfileX')

    # Profile mult node so scaleProfileY = scale_profile * roundness (flat to circular sweep shape)
    profile_mult = cmds.createNode('multDL', n=f"{stroke_mesh}_profileY_mult", ss=True)
    cmds.connectAttr(f"{stroke_mesh}.scale_profile", f"{profile_mult}.input1", force=True)
    cmds.connectAttr(f"{stroke_mesh}.roundness", f"{profile_mult}.input2", force=True)
    cmds.connectAttr(f"{profile_mult}.output", f"{sweep_mesh_node}.scaleProfileY", force=True)

    cmds.connectAttr(f"{stroke_mesh}.cap", f"{sweep_mesh_node}.capsEnable", force=True)
    cmds.connectAttr(stroke_mesh + '.rotate_profile', sweep_mesh_node + '.rotateProfile')
    cmds.connectAttr(stroke_mesh + '.Sides', sweep_mesh_node + '.profilePolySides')
    cmds.connectAttr(stroke_mesh + '.precision', sweep_mesh_node + '.interpolationPrecision')
    cmds.connectAttr(stroke_mesh + '.optimize_precision', sweep_mesh_node + '.interpolationOptimize')

    # 3. Taper section (POINTS renamed to Taper, enum separator "__________")
    cmds.addAttr(stroke_mesh, at='enum', k=True, en='__________', shortName='Taper', h=False)
    cmds.setAttr(stroke_mesh + '.Taper', lock=True)
    cmds.addAttr(stroke_mesh, at='float', k=True, shortName='Start_position')
    cmds.addAttr(stroke_mesh, at='float', k=True, min=0, defaultValue=0.0, shortName='Start_value')

    num_driver_points = max(2, int(num_driver_points))
    num_inter = num_driver_points - 2
    if num_driver_points == 4:
        default_positions = [0.2, 0.8]
    elif num_inter > 0:
        default_positions = [(k + 1) / float(num_driver_points - 1) for k in range(num_inter)]
    else:
        default_positions = []

    for idx, pos in enumerate(default_positions, 1):
        if len(default_positions) == 1:
            pt_val = 0.7
        elif idx == 1:
            pt_val = 0.3
        elif idx == len(default_positions):
            pt_val = 0.7
        else:
            pt_val = 1.0

        cmds.addAttr(stroke_mesh, at='float', k=True, shortName=f'Pt{idx}_position')
        cmds.addAttr(stroke_mesh, at='float', k=True, min=0, defaultValue=pt_val, shortName=f'Pt{idx}_value')
        cmds.addAttr(stroke_mesh, at='enum', k=True, en='None:Linear:Smooth:Spline', shortName=f'Pt{idx}_interp')
        cmds.setAttr(f'{stroke_mesh}.Pt{idx}_position', pos)
        cmds.setAttr(f'{stroke_mesh}.Pt{idx}_value', pt_val)
        cmds.setAttr(f'{stroke_mesh}.Pt{idx}_interp', 1)

    cmds.addAttr(stroke_mesh, at='float', k=True, min=0, shortName='End_position')
    cmds.addAttr(stroke_mesh, at='float', k=True, min=0, defaultValue=0.0, shortName='End_value')

    # Defaults: Start_value is 0.0, Pt1 is 0.3, last Pt is 0.7, End_value is 0.0
    cmds.setAttr(stroke_mesh + '.scale_profile', start_scale_value)
    cmds.setAttr(stroke_mesh + '.Start_position', 0.0)
    cmds.setAttr(stroke_mesh + '.Start_value', 0.0)
    cmds.setAttr(stroke_mesh + '.End_position', 1.0)
    cmds.setAttr(stroke_mesh + '.End_value', 0.0)

    try:
        cmds.setAttr(sweep_mesh_node + '.taperCurve[0].taperCurve_FloatValue', 0.0)
        cmds.setAttr(sweep_mesh_node + '.taperCurve[1].taperCurve_FloatValue', 0.0)
    except Exception:
        pass

    cmds.connectAttr(stroke_mesh + '.Start_position', sweep_mesh_node + '.taperCurve[0].taperCurve_Position')
    cmds.connectAttr(stroke_mesh + '.Start_value', sweep_mesh_node + '.taperCurve[0].taperCurve_FloatValue')

    cmds.connectAttr(stroke_mesh + '.End_position', sweep_mesh_node + '.taperCurve[1].taperCurve_Position')
    cmds.connectAttr(stroke_mesh + '.End_value', sweep_mesh_node + '.taperCurve[1].taperCurve_FloatValue')

    for idx in range(1, len(default_positions) + 1):
        target_idx = 1 + idx
        cmds.connectAttr(f'{stroke_mesh}.Pt{idx}_position', f'{sweep_mesh_node}.taperCurve[{target_idx}].taperCurve_Position')
        cmds.connectAttr(f'{stroke_mesh}.Pt{idx}_interp', f'{sweep_mesh_node}.taperCurve[{target_idx}].taperCurve_Interp')
        cmds.connectAttr(f'{stroke_mesh}.Pt{idx}_value', f'{sweep_mesh_node}.taperCurve[{target_idx}].taperCurve_FloatValue')

    return stroke_mesh, profile_mult


def createTaperController(sweep_mesh_node, line_type="paint", paint_mode=False, num_driver_points=4, start_scale_value=1.0):
    """
    Deprecated: Kept for backwards-compatibility.
    Redirects attribute setup to the sweep mesh's output mesh directly.
    """
    mesh_conns = cmds.listConnections(sweep_mesh_node + '.outMeshArray[0]', d=True, s=False)
    if mesh_conns:
        res = setupStrokeMeshAttributes(mesh_conns[0], sweep_mesh_node, num_driver_points=num_driver_points, start_scale_value=start_scale_value, line_type=line_type)
        return res[0] if isinstance(res, (tuple, list)) else res
    res = setupStrokeMeshAttributes(sweep_mesh_node, sweep_mesh_node, num_driver_points=num_driver_points, start_scale_value=start_scale_value, line_type=line_type)
    return res[0] if isinstance(res, (tuple, list)) else res


def shrinkWrapItem(target_msh, wrapped_item, target_subdiv_lvl=0, offset=None):
    if target_subdiv_lvl <= 0 or not target_msh or not cmds.objExists(target_msh):
        return

    shapes = cmds.listRelatives(target_msh, s=True, noIntermediate=True) or []
    if not shapes:
        shapes = cmds.listRelatives(target_msh, s=True) or []
    if not shapes:
        return
    target_msh_shape = shapes[0]

    shrinkwrap_deformer = cmds.deformer(wrapped_item, type='shrinkWrap')[0]

    cmds.connectAttr(target_msh_shape + '.boundaryRule', shrinkwrap_deformer + '.boundaryRule')
    cmds.connectAttr(target_msh_shape + '.continuity', shrinkwrap_deformer + '.continuity')
    cmds.connectAttr(target_msh_shape + '.keepBorder', shrinkwrap_deformer + '.keepBorder')
    cmds.connectAttr(target_msh_shape + '.keepHardEdge', shrinkwrap_deformer + '.keepHardEdge')
    cmds.connectAttr(target_msh_shape + '.keepMapBorders', shrinkwrap_deformer + '.keepMapBorders')
    cmds.connectAttr(target_msh_shape + '.smoothUVs', shrinkwrap_deformer + '.smoothUVs')
    cmds.connectAttr(target_msh_shape + '.worldMesh[0]', shrinkwrap_deformer + '.targetGeom')

    eff_offset = config.line_subdiv_offset if offset is None else float(offset)
    cmds.setAttr(shrinkwrap_deformer + '.prj', 4)
    cmds.setAttr(shrinkwrap_deformer + '.bi', 0)  # Unidirectional (prevents piercing through thin features to opposite side)
    cmds.setAttr(shrinkwrap_deformer + '.offset', eff_offset)
    cmds.setAttr(shrinkwrap_deformer + '.targetSmoothLevel', 3)

    cmds.select(wrapped_item, r=True, noExpand=True)
    mel.eval("DeleteHistory;")


def bakeAllLines():
    """
    Bakes the curve animation over the playback range so that the curve is no longer
    dynamically deformed by nodes/wrap/rivets, but has animated vertices (control points).
    This frees deformation computation and saves memory.
    """
    global_line_data = config.global_scene_data_obj.getGlobalLinesData() if config.global_scene_data_obj else {}
    if not global_line_data:
        cmds.warning("No cartoon lines to bake.")
        return

    start_frame = int(cmds.playbackOptions(q=True, min=True))
    end_frame = int(cmds.playbackOptions(q=True, max=True))
    current_time = cmds.currentTime(q=True)

    target_keys = list(global_line_data.keys())

    # Maya Progress bar
    total_steps = max(1, (end_frame - start_frame + 1) * len(target_keys))
    progress_bar = None
    try:
        progress_bar = mel.eval('global string $gMainProgressBar; $tmp = $gMainProgressBar;')
        if progress_bar:
            cmds.progressBar(progress_bar, edit=True, beginProgress=True, isInterruptable=True,
                             status='Baking curve animations...', maxValue=total_steps)
    except Exception:
        pass

    try:
        for line_key in target_keys:
            line_data = dict(global_line_data[line_key])
            curve_transform = line_data.get("curve")
            if not curve_transform or not cmds.objExists(curve_transform):
                continue

            curve_shapes = cmds.listRelatives(curve_transform, s=True)
            if not curve_shapes:
                continue
            curve_shape = curve_shapes[0]
            num_cvs = len(cmds.ls(f"{curve_shape}.cv[*]", fl=True))

            # 1. Sample local positions across playback range
            anim_data = {i: [] for i in range(num_cvs)}
            for t in range(start_frame, end_frame + 1):
                cmds.currentTime(t, edit=True)
                for i in range(num_cvs):
                    pos = cmds.pointPosition(f"{curve_shape}.cv[{i}]", local=True)
                    anim_data[i].append((t, pos))
                if progress_bar:
                    cmds.progressBar(progress_bar, edit=True, step=1)

            # 2. Delete/disconnect deformation setup
            wrap_node = line_data.get("wrap_node")
            if wrap_node and cmds.objExists(wrap_node):
                cmds.delete(wrap_node)
                for s in cmds.listRelatives(curve_transform, s=True):
                    if 'Orig' in s:
                        cmds.delete(s)

            follow_nodes = line_data.get("follow_nodes", [])
            for fn in follow_nodes:
                if fn and cmds.objExists(fn):
                    try:
                        cmds.delete(fn)
                    except Exception:
                        pass

            # Ensure all control points connections are disconnected
            for i in range(num_cvs):
                conns = cmds.listConnections(f"{curve_shape}.controlPoints[{i}]", d=False, s=True, p=True)
                if conns:
                    for src in conns:
                        try:
                            cmds.disconnectAttr(src, f"{curve_shape}.controlPoints[{i}]")
                        except Exception:
                            pass

            # 3. Apply keyframes to controlPoints
            for i in range(num_cvs):
                for t, pos in anim_data[i]:
                    cmds.setKeyframe(f"{curve_shape}.controlPoints[{i}].xValue", t=t, v=pos[0])
                    cmds.setKeyframe(f"{curve_shape}.controlPoints[{i}].yValue", t=t, v=pos[1])
                    cmds.setKeyframe(f"{curve_shape}.controlPoints[{i}].zValue", t=t, v=pos[2])

            line_data["baked"] = True
            line_data["wrap_node"] = None
            line_data["follow_nodes"] = []
            if config.global_scene_data_obj:
                config.global_scene_data_obj.updateLineData(line_key, line_data)

    finally:
        if progress_bar:
            try:
                cmds.progressBar(progress_bar, edit=True, endProgress=True)
            except Exception:
                pass
        cmds.currentTime(current_time, edit=True)
        cmds.select(cl=True)


def extractLineAttributes(mesh_node, line_data=None):
    if not mesh_node or not cmds.objExists(mesh_node):
        return None

    data = {
        "color": getLineMeshColor(mesh_node)
    }

    # Profile attributes
    for a in ['scale_profile', 'roundness', 'rotate_profile', 'Sides', 'cap', 'precision', 'optimize_precision',
              'Start_position', 'Start_value', 'End_position', 'End_value']:
        if cmds.attributeQuery(a, node=mesh_node, exists=True):
            try:
                data[a] = cmds.getAttr(f"{mesh_node}.{a}")
            except Exception:
                pass

    # Intermediate taper points
    data["intermediate_points"] = []
    i = 1
    while cmds.attributeQuery(f"Pt{i}_position", node=mesh_node, exists=True):
        pt_entry = {
            "idx": i,
            "pos": cmds.getAttr(f"{mesh_node}.Pt{i}_position"),
            "val": cmds.getAttr(f"{mesh_node}.Pt{i}_value") if cmds.attributeQuery(f"Pt{i}_value", node=mesh_node, exists=True) else 1.0,
            "interp": cmds.getAttr(f"{mesh_node}.Pt{i}_interp") if cmds.attributeQuery(f"Pt{i}_interp", node=mesh_node, exists=True) else 1,
        }
        data["intermediate_points"].append(pt_entry)
        i += 1

    # Smooth
    has_smooth = bool(line_data.get("smoothable")) if line_data else False
    if not has_smooth:
        has_smooth = cmds.attributeQuery('divisions', node=mesh_node, exists=True)
    data["smoothable"] = has_smooth
    if has_smooth:
        if cmds.attributeQuery('method', node=mesh_node, exists=True):
            data["method"] = cmds.getAttr(f"{mesh_node}.method")
        if cmds.attributeQuery('divisions', node=mesh_node, exists=True):
            data["divisions"] = cmds.getAttr(f"{mesh_node}.divisions")

    # Displacement
    has_disp = bool(line_data.get("displacement")) if line_data else False
    if not has_disp:
        has_disp = cmds.attributeQuery('strength', node=mesh_node, exists=True)
    data["displacement"] = has_disp
    if has_disp:
        disp_type = "noise"
        if line_data and line_data.get("disp_type"):
            disp_type = line_data["disp_type"]
        elif line_data and line_data.get("noise_node") and cmds.objExists(line_data["noise_node"]):
            disp_type = cmds.nodeType(line_data["noise_node"])
        else:
            hist = cmds.listHistory(mesh_node) or []
            for h in hist:
                if cmds.nodeType(h) == "textureDeformer":
                    conn = cmds.listConnections(f"{h}.texture", s=True, d=False) or []
                    for c in conn:
                        nt = cmds.nodeType(c)
                        if nt in ["noise", "mountain", "fractal"]:
                            disp_type = nt
                            break
        data["disp_type"] = disp_type

        for a in ['strength', 'offset', 'noise_type', 'frequency', 'ratio', 'time',
                  'snow_roughness', 'rock_roughness', 'boundary', 'altitude',
                  'amplitude', 'frequency_ratio']:
            if cmds.attributeQuery(a, node=mesh_node, exists=True):
                try:
                    data[a] = cmds.getAttr(f"{mesh_node}.{a}")
                except Exception:
                    pass

    return data


def rebuildLine(line_data, new_attrs=None, rebuild_ui_elements=True, rebuild_custom_attrs=True, rebuild_follow_method=False):
    """
    Rebuilds / adapts a cartoon line with given attributes (or active UI settings).
    Allows selective rebuilding of:
    - rebuild_ui_elements: Profile scale, roundness, smoothable toggle, displacement toggle, disp_type, color shader
    - rebuild_custom_attrs: Sides, rotate_profile, cap, precision, optimize_precision, taper points,
                            smooth divisions/method, displacement noise parameters
    - rebuild_follow_method: Switches or re-applies line follow method to the specified or active UI follow method
    """
    if not line_data:
        return False

    line_name = line_data.get("name", "line")
    mesh = line_data.get("mesh")
    if not mesh or not cmds.objExists(mesh):
        grp = line_data.get("group") or f"{line_name}_grp"
        if grp and cmds.objExists(grp):
            transforms = cmds.listRelatives(grp, allDescendents=True, type="transform") or []
            for tr in transforms:
                if tr.endswith("_msh") and cmds.objExists(tr):
                    mesh = tr
                    line_data["mesh"] = mesh
                    break
        elif cmds.objExists(f"{line_name}_msh"):
            mesh = f"{line_name}_msh"
            line_data["mesh"] = mesh

    if not mesh or not cmds.objExists(mesh):
        return False

    if new_attrs is None:
        if config.global_main_widget and hasattr(config.global_main_widget, "getCurrentUISettings"):
            new_attrs = config.global_main_widget.getCurrentUISettings()
        elif isinstance(config.active_preset_config, dict):
            new_attrs = dict(config.active_preset_config)
        else:
            new_attrs = {}

    line_group = line_data.get("group") or (cmds.listRelatives(mesh, p=True)[0] if cmds.listRelatives(mesh, p=True) else None)
    if line_group:
        line_data["group"] = line_group

    # 1. Sweep mesh node and profile wiring (structural wiring)
    sweep_mesh_node = line_data.get("sweep_mesh_node")
    if not sweep_mesh_node or not cmds.objExists(sweep_mesh_node):
        hist = cmds.listHistory(mesh) or []
        for h in hist:
            if cmds.nodeType(h) == "sweepMeshCreator":
                sweep_mesh_node = h
                line_data["sweep_mesh_node"] = sweep_mesh_node
                break

    # Ensure profile multDL exists for roundness (flat to round)
    if sweep_mesh_node and cmds.objExists(sweep_mesh_node):
        if not cmds.attributeQuery('roundness', node=mesh, exists=True):
            cmds.addAttr(mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=1.0, shortName='roundness')
            cmds.setAttr(f"{mesh}.roundness", 1.0)

        pm = line_data.get("profile_mult_node")
        if not pm or not cmds.objExists(pm):
            pm = f"{mesh}_profileY_mult"
            if not cmds.objExists(pm):
                pm = cmds.createNode('multDL', n=pm, ss=True)
            line_data["profile_mult_node"] = pm

        if cmds.attributeQuery('scale_profile', node=mesh, exists=True):
            if not cmds.isConnected(f"{mesh}.scale_profile", f"{pm}.input1"):
                cmds.connectAttr(f"{mesh}.scale_profile", f"{pm}.input1", force=True)
            if not cmds.isConnected(f"{mesh}.roundness", f"{pm}.input2"):
                cmds.connectAttr(f"{mesh}.roundness", f"{pm}.input2", force=True)
            if not cmds.isConnected(f"{pm}.output", f"{sweep_mesh_node}.scaleProfileY"):
                cmds.connectAttr(f"{pm}.output", f"{sweep_mesh_node}.scaleProfileY", force=True)
            if not cmds.isConnected(f"{mesh}.scale_profile", f"{sweep_mesh_node}.scaleProfileX"):
                cmds.connectAttr(f"{mesh}.scale_profile", f"{sweep_mesh_node}.scaleProfileX", force=True)

        if not cmds.attributeQuery('cap', node=mesh, exists=True):
            cmds.addAttr(mesh, at='bool', k=True, defaultValue=False, shortName='cap')
            cmds.setAttr(f"{mesh}.cap", 0)
        if not cmds.isConnected(f"{mesh}.cap", f"{sweep_mesh_node}.capsEnable"):
            try:
                cmds.connectAttr(f"{mesh}.cap", f"{sweep_mesh_node}.capsEnable", force=True)
            except Exception:
                pass

        if not cmds.attributeQuery('Sides', node=mesh, exists=True):
            cmds.addAttr(mesh, at='long', k=True, shortName='Sides', min=1, defaultValue=6)
            cmds.setAttr(f"{mesh}.Sides", 6)
        if not cmds.isConnected(f"{mesh}.Sides", f"{sweep_mesh_node}.profilePolySides"):
            try:
                cmds.connectAttr(f"{mesh}.Sides", f"{sweep_mesh_node}.profilePolySides", force=True)
            except Exception:
                pass

    # Ensure multDL node exists for visibility bypass
    mult_node = line_data.get("mult_dl_node") or (f"{line_name}_multDL" if line_name else None)
    if mult_node and cmds.objExists(mult_node):
        line_data["mult_dl_node"] = mult_node
    elif line_group and cmds.objExists(line_group) and sweep_mesh_node and cmds.objExists(sweep_mesh_node):
        mult_node = cmds.createNode('multDL', n=f"{line_name}_multDL", ss=True)
        cmds.setAttr(f"{mult_node}.input2", -1.0)
        cmds.connectAttr(f"{line_group}.v", f"{mult_node}.input1", force=True)
        cmds.connectAttr(f"{mult_node}.output", f"{sweep_mesh_node}.nodeState", force=True)
        line_data["mult_dl_node"] = mult_node

    # 2. Apply Profile attributes (UI elements vs Custom attributes)
    if rebuild_ui_elements:
        for a in ['scale_profile', 'roundness']:
            if a in new_attrs and cmds.attributeQuery(a, node=mesh, exists=True):
                try:
                    cmds.setAttr(f"{mesh}.{a}", new_attrs[a])
                except Exception:
                    pass

    if rebuild_custom_attrs:
        for a in ['rotate_profile', 'Sides', 'cap', 'precision', 'optimize_precision',
                  'Start_position', 'Start_value', 'End_position', 'End_value']:
            if a in new_attrs and cmds.attributeQuery(a, node=mesh, exists=True):
                try:
                    cmds.setAttr(f"{mesh}.{a}", new_attrs[a])
                except Exception:
                    pass

        # Intermediate taper points
        inter_points = new_attrs.get("intermediate_points", [])
        if inter_points:
            for pt in inter_points:
                i = pt.get("idx")
                if i is not None and cmds.attributeQuery(f"Pt{i}_position", node=mesh, exists=True):
                    try:
                        if "pos" in pt:
                            cmds.setAttr(f"{mesh}.Pt{i}_position", pt["pos"])
                        if "val" in pt:
                            cmds.setAttr(f"{mesh}.Pt{i}_value", pt["val"])
                        if "interp" in pt:
                            cmds.setAttr(f"{mesh}.Pt{i}_interp", pt["interp"])
                    except Exception:
                        pass
        else:
            pts = []
            k = 1
            while cmds.attributeQuery(f"Pt{k}_value", node=mesh, exists=True):
                pts.append(k)
                k += 1
            if pts:
                if "Pt1_value" in new_attrs:
                    try:
                        cmds.setAttr(f"{mesh}.Pt{pts[0]}_value", new_attrs["Pt1_value"])
                    except Exception:
                        pass
                if "PtLast_value" in new_attrs and len(pts) > 1:
                    try:
                        cmds.setAttr(f"{mesh}.Pt{pts[-1]}_value", new_attrs["PtLast_value"])
                    except Exception:
                        pass

    # 3. Smoothable
    if rebuild_ui_elements:
        is_smooth = new_attrs.get("smoothable") if "smoothable" in new_attrs else new_attrs.get("line_smoothable")
        if is_smooth:
            smooth_node = applySmoothToStrokeMesh(mesh, line_name=line_name)
            if mult_node and cmds.objExists(mult_node) and smooth_node and cmds.objExists(smooth_node):
                try:
                    if not cmds.isConnected(f"{mult_node}.output", f"{smooth_node}.nodeState"):
                        cmds.connectAttr(f"{mult_node}.output", f"{smooth_node}.nodeState", force=True)
                except Exception:
                    pass
            line_data["smooth_node"] = smooth_node
            line_data["smoothable"] = True
        elif is_smooth is not None and not is_smooth:
            removeDisplacementFromStrokeMesh(mesh, line_data)
            removeSmoothFromStrokeMesh(mesh, line_data)
            line_data["smoothable"] = False
            line_data["smooth_node"] = None
            line_data["displacement"] = False
            line_data["tex_def_node"] = None
            line_data["noise_node"] = None
            line_data["tex_handle"] = None
            line_data["add_noise"] = False

    if rebuild_custom_attrs:
        method_val = new_attrs.get("method") if "method" in new_attrs else new_attrs.get("smooth_method")
        if method_val is not None and cmds.attributeQuery('method', node=mesh, exists=True):
            try:
                cmds.setAttr(f"{mesh}.method", method_val)
            except Exception:
                pass
        div_val = new_attrs.get("divisions") if "divisions" in new_attrs else new_attrs.get("smooth_divisions")
        if div_val is not None and cmds.attributeQuery('divisions', node=mesh, exists=True):
            try:
                cmds.setAttr(f"{mesh}.divisions", div_val)
            except Exception:
                pass

    # 4. Displacement
    if rebuild_ui_elements:
        is_disp = new_attrs.get("displacement") if "displacement" in new_attrs else new_attrs.get("line_displacement")
        can_disp = (new_attrs.get("smoothable") if "smoothable" in new_attrs else new_attrs.get("line_smoothable")) or line_data.get("smoothable") or cmds.attributeQuery("divisions", node=mesh, exists=True)
        if is_disp and can_disp:
            disp_type = new_attrs.get("disp_type", new_attrs.get("line_disp_type", "noise"))
            tex_def, tex_node, tex_handle = applyDisplacementToStrokeMesh(mesh, line_name=line_name, disp_type=disp_type)
            if tex_handle and cmds.objExists(tex_handle) and line_group and cmds.objExists(line_group):
                parent = cmds.listRelatives(tex_handle, parent=True) or []
                if not parent or parent[0] != line_group:
                    try:
                        cmds.parent(tex_handle, line_group)
                    except Exception:
                        pass

            if mult_node and cmds.objExists(mult_node) and tex_def and cmds.objExists(tex_def):
                try:
                    if not cmds.isConnected(f"{mult_node}.output", f"{tex_def}.nodeState"):
                        cmds.connectAttr(f"{mult_node}.output", f"{tex_def}.nodeState", force=True)
                except Exception:
                    pass

            line_data["tex_def_node"] = tex_def
            line_data["noise_node"] = tex_node
            line_data["tex_handle"] = tex_handle
            line_data["displacement"] = True
            line_data["disp_type"] = disp_type
            line_data["add_noise"] = True
        elif is_disp is not None and not is_disp:
            removeDisplacementFromStrokeMesh(mesh, line_data)
            line_data["displacement"] = False
            line_data["tex_def_node"] = None
            line_data["noise_node"] = None
            line_data["tex_handle"] = None
            line_data["add_noise"] = False

    if rebuild_custom_attrs:
        disp_param_map = {
            'strength': ['strength', 'disp_strength'],
            'offset': ['offset', 'disp_offset'],
            'noise_type': ['noise_type'],
            'frequency': ['frequency'],
            'ratio': ['ratio'],
            'time': ['time'],
            'snow_roughness': ['snow_roughness'],
            'rock_roughness': ['rock_roughness'],
            'boundary': ['boundary'],
            'altitude': ['altitude'],
            'amplitude': ['amplitude'],
            'frequency_ratio': ['frequency_ratio']
        }
        for attr, keys in disp_param_map.items():
            for k in keys:
                if k in new_attrs and cmds.attributeQuery(attr, node=mesh, exists=True):
                    try:
                        cmds.setAttr(f"{mesh}.{attr}", new_attrs[k])
                        break
                    except Exception:
                        pass

    # 5. Color / Shader
    if rebuild_ui_elements:
        color = new_attrs.get("color")
        if color is None:
            color = new_attrs.get("current_line_color")
        if color is not None:
            assignLineShader(mesh, color=color)
            line_data["color"] = tuple(color)

    # 6. Follow Method
    if rebuild_follow_method:
        target_follow_method = new_attrs.get("follow_method")
        if not target_follow_method:
            target_follow_method = config.current_follow_method
        if target_follow_method:
            changeLineFollowMethod(line_data, target_follow_method)

    if config.global_scene_data_obj:
        config.global_scene_data_obj.updateLineData(line_name, line_data)
    return True


def applyExtractedAttributes(tgt_mesh, tgt_line_data, attrs_dict):
    if not tgt_mesh or not cmds.objExists(tgt_mesh) or not attrs_dict:
        return
    if not tgt_line_data and config.global_scene_data_obj:
        all_lines = config.global_scene_data_obj.getAllLines()
        for name, data in all_lines.items():
            if data.get("mesh") == tgt_mesh:
                tgt_line_data = data
                break
        if not tgt_line_data:
            tgt_name = tgt_mesh.replace("_msh", "")
            tgt_group = cmds.listRelatives(tgt_mesh, p=True)[0] if cmds.listRelatives(tgt_mesh, p=True) else None
            tgt_line_data = {
                "name": tgt_name,
                "mesh": tgt_mesh,
                "group": tgt_group
            }
    return rebuildLine(tgt_line_data, new_attrs=attrs_dict)


def drawLine():
    if config._is_drawing_line:
        return

    if not config.paint_on_mesh or not cmds.objExists(config.paint_on_mesh):
        sel_mesh = get_selected_mesh_from_scene()
        if sel_mesh:
            config.paint_on_mesh = sel_mesh
        elif config.global_main_widget and hasattr(config.global_main_widget, "set_target_mesh_lineedit"):
            txt = config.global_main_widget.set_target_mesh_lineedit.text().strip()
            if txt and cmds.objExists(txt):
                config.paint_on_mesh = txt

    sl = cmds.ls(sl=True) or []
    if not sl:
        if config.global_main_widget and getattr(config.global_main_widget, "_is_paint_mode_active", False):
            arm_stroke_listener()
        return

    shapes = cmds.listRelatives(sl, fullPath=False, shapes=True) or []
    stroke_shape = None
    for s in shapes:
        if cmds.objectType(s) == 'stroke':
            stroke_shape = s
            break

    if not stroke_shape:
        if config.global_main_widget and getattr(config.global_main_widget, "_is_paint_mode_active", False):
            arm_stroke_listener()
        return

    config._is_drawing_line = True
    eff_smoothing = float(config.smooth_curve * 100.0)
    cmds.setAttr(stroke_shape + '.smoothing', eff_smoothing)

    was_symmetry = False
    try:
        was_symmetry = bool(cmds.symmetricModelling(q=True, symmetry=True))
        if was_symmetry:
            cmds.symmetricModelling(symmetry=False)
    except Exception:
        pass

    # Suspend viewport refresh and open single undo chunk for ultra-fast creation
    cmds.refresh(suspend=True)
    cmds.undoInfo(openChunk=True, chunkName="CartoonLineartDraw")
    try:
        mel.eval("PaintEffectsToCurve;")
        start_scale = config.line_default_scale

        converted_curve_transform = cmds.listConnections(stroke_shape + '.outMainCurves[0]', d=True, s=False)[0]
        converted_curve_shape = cmds.listRelatives(converted_curve_transform, s=True)[0]

        # Query spans amount to perform reduction based on user curve res & smooth_curve
        converted_curve_spans = cmds.getAttr(converted_curve_shape + '.s')
        eff_divisor = 1.0 + (float(config.line_resolution) - 1.0) * config.smooth_curve
        spans = max(1, int(round(converted_curve_spans / max(1.0, eff_divisor))))

        cmds.select(converted_curve_transform, noExpand=True)
        mel.eval(f'rebuildCurve -ch 0 -rpo 1 -rt 0 -end 1 -kr 0 -kcp 0 -kep 1 -kt 0 -s {spans} -d 1 -tol 0.0001;')

        # Only apply shrinkWrap if offset != 0.0 and subdiv preview active (avoids heavy multi-second mesh freeze)
        if config.line_subdiv_offset != 0.0 and config.paint_on_mesh and cmds.objExists(config.paint_on_mesh):
            target_shapes = cmds.listRelatives(config.paint_on_mesh, s=True, noIntermediate=True) or cmds.listRelatives(config.paint_on_mesh, s=True) or []
            if target_shapes:
                target_subdiv = cmds.getAttr(target_shapes[0] + '.displaySmoothMesh')
                if target_subdiv > 0:
                    shrinkWrapItem(target_msh=config.paint_on_mesh, wrapped_item=converted_curve_transform, target_subdiv_lvl=target_subdiv)

        # Delete construction history on converted_curve_transform to ensure clean curve geometry
        cmds.delete(converted_curve_transform, ch=True)

        cmds.select(converted_curve_transform, r=True, noExpand=True)
        mel.eval('performSweepMesh 0;')

        sweep_mesh_node = cmds.listConnections(converted_curve_transform + '.worldSpace[0]', d=True, s=False)[0]
        result_mesh = cmds.listConnections(sweep_mesh_node + '.outMeshArray[0]', d=True, s=False)[0]

        master_grp = get_or_create_master_group()
        line_id = get_next_line_id()
        line_name = f"line_{line_id}"

        # Setup custom line parameters directly on the stroke mesh (lock/hide TRS + V)
        setup_res = setupStrokeMeshAttributes(result_mesh, sweep_mesh_node, num_driver_points=config.curve_points, start_scale_value=start_scale, line_type="paint", sweep_shape=config.line_sweep_shape)
        profile_mult = setup_res[1] if isinstance(setup_res, (tuple, list)) else None

        smooth_node = None
        if config.line_smoothable:
            smooth_node = applySmoothToStrokeMesh(result_mesh, line_name=line_name)

        tex_def_node = None
        noise_node = None
        tex_handle_node = None
        has_disp = config.line_smoothable and (config.line_displacement or config.line_add_noise)
        if has_disp:
            tex_def_node, noise_node, tex_handle_node = applyDisplacementToStrokeMesh(result_mesh, line_name=line_name, disp_type=config.line_disp_type)

        fg = cmds.listRelatives(converted_curve_transform, p=True)
        first_group = fg[0] if fg else converted_curve_transform
        rg = cmds.listRelatives(first_group, p=True) if fg else None
        root_converted_curve_group = rg[0] if rg else first_group

        stroke_tf = cmds.listRelatives(stroke_shape, p=True)
        stroke_transform = stroke_tf[0] if stroke_tf else stroke_shape
        if stroke_transform and cmds.objExists(stroke_transform):
            cmds.setAttr(stroke_transform + '.v', 0)
        if root_converted_curve_group and cmds.objExists(root_converted_curve_group) and root_converted_curve_group != converted_curve_transform:
            cmds.setAttr(root_converted_curve_group + '.v', 0)

        line_group = cmds.group(em=True, n=line_name)
        cmds.parent(result_mesh, line_group)
        if root_converted_curve_group and cmds.objExists(root_converted_curve_group) and root_converted_curve_group != line_group:
            try:
                cmds.parent(root_converted_curve_group, line_group)
            except Exception:
                pass
        if tex_handle_node and cmds.objExists(tex_handle_node):
            try:
                cmds.parent(tex_handle_node, line_group)
            except Exception:
                pass
        cmds.parent(line_group, master_grp)
        reset_pivots_to_origin(master_grp, line_group, result_mesh, converted_curve_transform, root_converted_curve_group, first_group)

        # Query connected brush node before deleting stroke
        brush_nodes = []
        try:
            if cmds.attributeQuery('brush', node=stroke_shape, exists=True):
                brush_nodes = cmds.listConnections(stroke_shape + '.brush', type='brush') or []
            if not brush_nodes:
                brush_nodes = cmds.listConnections(stroke_shape, type='brush') or []
        except Exception:
            pass
        brush_node = brush_nodes[0] if brush_nodes else None

        # Clean up temporary stroke transform and its brush asynchronously so Maya's Attribute Editor doesn't query a deleted node
        def _deferred_stroke_cleanup(tf_name, brush_names=None):
            if tf_name and cmds.objExists(tf_name):
                try:
                    cmds.delete(tf_name)
                except Exception:
                    pass
            if brush_names:
                for b in brush_names:
                    if b and b != "defaultBrush" and cmds.objExists(b):
                        try:
                            cmds.delete(b)
                        except Exception:
                            pass
            clean_orphaned_stroke_brushes()

        cmds.evalDeferred(lambda tf=stroke_transform, bn=brush_nodes: _deferred_stroke_cleanup(tf, bn))

        # Apply chosen follow method!
        follow_data = applyFollowMethod(
            follow_method=config.current_follow_method,
            curve_transform=converted_curve_transform,
            target_mesh=config.paint_on_mesh,
            line_id=line_id,
            line_group=line_group,
            subdiv_offset=config.line_subdiv_offset
        )

        mult_node = cmds.createNode('multDL', n=f"{line_name}_multDL", ss=True)
        cmds.setAttr(f"{mult_node}.input2", -1.0)
        cmds.connectAttr(f"{line_group}.v", f"{mult_node}.input1")
        cmds.connectAttr(f"{mult_node}.output", f"{sweep_mesh_node}.nodeState")
        if follow_data.get("wrap_node"):
            cmds.connectAttr(f"{mult_node}.output", f"{follow_data['wrap_node']}.nodeState")
        for fn in follow_data.get("follow_nodes", []):
            if cmds.objExists(fn) and cmds.attributeQuery('nodeState', node=fn, exists=True):
                try:
                    cmds.connectAttr(f"{mult_node}.output", f"{fn}.nodeState")
                except Exception:
                    pass

        ccg = cmds.listRelatives(converted_curve_transform, p=True)
        converted_curve_grp = ccg[0] if ccg else first_group

        if smooth_node and cmds.objExists(smooth_node):
            smooth_node = cmds.rename(smooth_node, f"{line_name}_smooth")
            if mult_node and cmds.objExists(mult_node):
                try:
                    cmds.connectAttr(f"{mult_node}.output", f"{smooth_node}.nodeState")
                except Exception:
                    pass

        if tex_def_node and cmds.objExists(tex_def_node):
            if mult_node and cmds.objExists(mult_node):
                try:
                    cmds.connectAttr(f"{mult_node}.output", f"{tex_def_node}.nodeState")
                except Exception:
                    pass

        if profile_mult and cmds.objExists(profile_mult):
            profile_mult = cmds.rename(profile_mult, f"{line_name}_profileY_mult")

        def _safe_rename(node_path, new_name):
            if not node_path:
                return None
            short = node_path.split("|")[-1]
            if cmds.objExists(short) and len(cmds.ls(short)) == 1:
                return cmds.rename(short, new_name)
            if cmds.objExists(node_path):
                return cmds.rename(node_path, new_name)
            matches = cmds.ls(f"*{short}")
            if matches and cmds.objExists(matches[0]):
                return cmds.rename(matches[0], new_name)
            return node_path

        result_mesh = _safe_rename(result_mesh, f"{line_name}_msh")
        sweep_mesh_node = _safe_rename(sweep_mesh_node, f"{line_name}_sweep")
        if root_converted_curve_group and cmds.objExists(root_converted_curve_group) and root_converted_curve_group != line_group and root_converted_curve_group != converted_curve_transform:
            root_converted_curve_group = _safe_rename(root_converted_curve_group, f"{line_name}_keep_grp")
        converted_curve_transform = _safe_rename(converted_curve_transform, f"{line_name}_crv")
        if converted_curve_grp and cmds.objExists(converted_curve_grp) and converted_curve_grp != line_group and converted_curve_grp != root_converted_curve_group and converted_curve_grp != converted_curve_transform:
            converted_curve_grp = _safe_rename(converted_curve_grp, f"{line_name}_crv_grp")
        reset_pivots_to_origin(master_grp, line_group, result_mesh, converted_curve_transform, root_converted_curve_group, converted_curve_grp)

        line_data = {
            "name": line_name,
            "type": "paint",
            "follow_method": config.current_follow_method,
            "target_mesh": config.paint_on_mesh,
            "color": tuple(config.current_line_color),
            "group": line_group,
            "mesh": result_mesh,
            "curve": converted_curve_transform,
            "sweep_msh_node": sweep_mesh_node,
            "taper_ctrl_node": result_mesh,
            "brush_node": brush_node,
            "smooth_node": smooth_node,
            "smoothable": bool(config.line_smoothable),
            "tex_def_node": tex_def_node,
            "noise_node": noise_node,
            "tex_handle": tex_handle_node,
            "displacement": bool(has_disp),
            "disp_type": config.line_disp_type,
            "add_noise": bool(has_disp),
            "profile_mult_node": profile_mult,
            "wrap_node": follow_data.get("wrap_node"),
            "follow_nodes": follow_data.get("follow_nodes", []),
            "root_convert_grp": root_converted_curve_group,
            "converted_curve_grp": converted_curve_grp,
            "mult_dl_node": mult_node,
            "reverse_state_node": mult_node,
            "baked": False
        }

        # Fast direct shading engine assignment (no Hypershade / no selection overhead)
        if config.active_preset_config:
            applyExtractedAttributes(result_mesh, line_data, config.active_preset_config)
        else:
            assignLineShader(result_mesh, color=config.current_line_color)

        if config.global_scene_data_obj:
            config.global_scene_data_obj.addLineData(line_data)

    finally:
        cmds.undoInfo(closeChunk=True)
        cmds.refresh(suspend=False)
        config._is_drawing_line = False
        if was_symmetry:
            try:
                cmds.symmetricModelling(symmetry=True)
            except Exception:
                pass

    # Clear selection so created mesh is not selected
    if config.global_main_widget:
        config.global_main_widget._is_syncing_selection = True
    try:
        cmds.select(cl=True)
    finally:
        if config.global_main_widget:
            config.global_main_widget._is_syncing_selection = False

    # Continue painting session if active
    if config.global_main_widget and getattr(config.global_main_widget, "_is_paint_mode_active", False):
        try:
            if config.paint_on_mesh and cmds.objExists(config.paint_on_mesh):
                cmds.select(config.paint_on_mesh, noExpand=True)
                mel.eval("MakePaintable")
                cmds.select(cl=True)
            cmds.setToolTo("paintMesh")
        except Exception:
            pass
        arm_stroke_listener()
    else:
        try:
            cmds.setToolTo('moveSuperContext')
        except Exception:
            pass

