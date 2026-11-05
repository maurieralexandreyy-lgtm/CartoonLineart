import re
from maya import cmds, mel
import maya.api.OpenMaya as om
import core.config as config
from core.utils import reset_pivots_to_origin, get_target_mesh_for_line
from core.shading import getLineMeshColor, assignLineShader
from core.deformers import applySmoothToStrokeMesh, applyDisplacementToStrokeMesh
from core.follow import applyFollowMethod


def generate_mirror_name(orig_name, direction):
    """
    Generates a mirrored line name based on direction ('L to R' or 'R to L').
    The mirrored line gets the base line's name with the suffix '_R' (for 'L to R')
    or '_L' (for 'R to L').
    Strips existing side indicators (_L, _R, .L, .R, -L, -R, _left, _right) from the base name.
    If the target name already exists in the scene, appends _1, _2, etc. (never generic line_X).
    """
    target_suffix = "_R" if direction == "L to R" else "_L"

    # Strip existing side suffix at the end (e.g., _L, _R, _Left, _Right, .L, .R, -L, -R)
    # optionally followed by digits (e.g. _L_1, _R_2)
    base_name = orig_name
    pat_suffix = r'([_\.-])(?:L|R|left|right|LEFT|RIGHT)(?:_\d+)?$'
    if re.search(pat_suffix, base_name, flags=re.IGNORECASE):
        base_name = re.sub(pat_suffix, '', base_name, flags=re.IGNORECASE)

    # Also strip prefix if present (e.g., L_brow -> brow)
    pat_prefix = r'^(?:L|R|left|right|LEFT|RIGHT)[_\.-]'
    if re.search(pat_prefix, base_name, flags=re.IGNORECASE):
        base_name = re.sub(pat_prefix, '', base_name, flags=re.IGNORECASE)

    if not base_name:
        base_name = orig_name

    candidate = f"{base_name}{target_suffix}"

    all_line_names = set(config.global_scene_data_obj.getAllLines().keys()) if config.global_scene_data_obj else set()
    if not cmds.objExists(candidate) and candidate not in all_line_names:
        return candidate

    idx = 1
    new_name = f"{candidate}_{idx}"
    while cmds.objExists(new_name) or new_name in all_line_names:
        idx += 1
        new_name = f"{candidate}_{idx}"
    return new_name


def mirrorSingleLine(orig_line_data, direction="L to R", target_mesh=None):
    """
    Mirrors a single cartoon line across the symmetry plane (X=0 in local target_mesh or world space).
    Duplicates the curve, mirrors its CVs, performs Sweep Mesh, copies all profile & taper attributes,
    applies the follow method, wires visibility multDL, and registers in GlobalSceneData.
    """
    from core.stroke import get_or_create_master_group, get_next_line_id, shrinkWrapItem, setupStrokeMeshAttributes

    orig_crv = orig_line_data.get("curve")
    if not orig_crv or not cmds.objExists(orig_crv):
        grp = orig_line_data.get("group")
        if grp and cmds.objExists(grp):
            rel_crvs = cmds.listRelatives(grp, allDescendents=True, type="nurbsCurve") or []
            if rel_crvs:
                orig_crv = cmds.listRelatives(rel_crvs[0], p=True)[0]
                orig_line_data["curve"] = orig_crv
    if not orig_crv or not cmds.objExists(orig_crv):
        return None

    if cmds.nodeType(orig_crv) == "nurbsCurve":
        crv_shape = orig_crv
        p_crvs = cmds.listRelatives(orig_crv, p=True, fullPath=True) or []
        orig_crv = p_crvs[0] if p_crvs else orig_crv
    else:
        crv_shapes = cmds.listRelatives(orig_crv, s=True, noIntermediate=True, fullPath=True) or cmds.listRelatives(orig_crv, s=True, fullPath=True) or []
        if not crv_shapes:
            return None
        crv_shape = crv_shapes[0]
    num_cvs = len(cmds.ls(f"{crv_shape}.cv[*]", fl=True))
    if num_cvs < 2:
        return None

    # Determine target mesh
    if not target_mesh or not cmds.objExists(target_mesh):
        target_mesh = get_target_mesh_for_line(orig_line_data)
    if target_mesh and not orig_line_data.get("target_mesh"):
        orig_line_data["target_mesh"] = target_mesh

    # Query target mesh matrix for local symmetry plane if available
    has_matrix = False
    inv_matrix = None
    world_matrix = None
    if target_mesh and cmds.objExists(target_mesh):
        try:
            sel = om.MSelectionList()
            sel.add(target_mesh)
            dag = sel.getDagPath(0)
            if not dag.hasFn(om.MFn.kTransform):
                dag.pop()
            inv_matrix = dag.inclusiveMatrix().inverse()
            world_matrix = dag.inclusiveMatrix()
            has_matrix = True
        except Exception:
            has_matrix = False

    # Calculate mirrored CV positions
    mirrored_pts = []
    for i in range(num_cvs):
        p = cmds.pointPosition(f"{crv_shape}.cv[{i}]", w=True)
        if has_matrix:
            pt = om.MPoint(p[0], p[1], p[2])
            local_pt = pt * inv_matrix
            mirrored_local = om.MPoint(-local_pt.x, local_pt.y, local_pt.z)
            mirrored_world = mirrored_local * world_matrix
            mirrored_pts.append((mirrored_world.x, mirrored_world.y, mirrored_world.z))
        else:
            mirrored_pts.append((-p[0], p[1], p[2]))

    # Names and IDs
    master_grp = get_or_create_master_group()
    orig_name = orig_line_data.get("name", "line_1")
    new_line_name = generate_mirror_name(orig_name, direction)
    line_id = get_next_line_id()

    # Create fresh, clean curve directly from mirrored points at world origin
    new_crv = cmds.curve(p=mirrored_pts, d=1, n=f"{new_line_name}_crv")

    # Optional shrinkwrap if offset active
    if config.line_subdiv_offset != 0.0 and target_mesh and cmds.objExists(target_mesh):
        t_shapes = cmds.listRelatives(target_mesh, s=True, noIntermediate=True, fullPath=True) or cmds.listRelatives(target_mesh, s=True, fullPath=True) or []
        if t_shapes:
            subdiv_lvl = cmds.getAttr(t_shapes[0] + '.displaySmoothMesh')
            if subdiv_lvl > 0:
                shrinkWrapItem(target_msh=target_mesh, wrapped_item=new_crv, target_subdiv_lvl=subdiv_lvl)
        cmds.delete(new_crv, ch=True)

    # Perform sweep mesh
    cmds.select(new_crv, r=True, noExpand=True)
    mel.eval('performSweepMesh 0;')
    sweep_mesh_node = cmds.listConnections(new_crv + '.worldSpace[0]', d=True, s=False)[0]
    result_mesh = cmds.listConnections(sweep_mesh_node + '.outMeshArray[0]', d=True, s=False)[0]

    # Setup hierarchy
    first_group = cmds.group(new_crv, n=f"{new_line_name}_crv_grp")
    root_converted_curve_group = cmds.group(first_group, n=f"{new_line_name}_keep_grp")
    cmds.setAttr(root_converted_curve_group + '.v', 0)

    line_group = cmds.group(em=True, n=new_line_name)
    cmds.parent(result_mesh, line_group)
    cmds.parent(root_converted_curve_group, line_group)
    cmds.parent(line_group, master_grp)
    reset_pivots_to_origin(master_grp, line_group, result_mesh, new_crv, root_converted_curve_group, first_group)

    # Read original attributes from orig_mesh
    orig_mesh = orig_line_data.get("mesh")
    num_driver_points = 2
    idx = 1
    pt_data = []
    scale_val = config.line_default_scale
    if orig_mesh and cmds.objExists(orig_mesh):
        if cmds.attributeQuery('scale_profile', node=orig_mesh, exists=True):
            scale_val = cmds.getAttr(f"{orig_mesh}.scale_profile")
        while cmds.attributeQuery(f'Pt{idx}_position', node=orig_mesh, exists=True):
            p_pos = cmds.getAttr(f"{orig_mesh}.Pt{idx}_position")
            p_val = cmds.getAttr(f"{orig_mesh}.Pt{idx}_value")
            p_int = cmds.getAttr(f"{orig_mesh}.Pt{idx}_interp")
            pt_data.append((p_pos, p_val, p_int))
            num_driver_points += 1
            idx += 1

    _, profile_mult = setupStrokeMeshAttributes(result_mesh, sweep_mesh_node, num_driver_points=num_driver_points, start_scale_value=scale_val, line_type=orig_line_data.get("type", "paint"))
    if profile_mult and cmds.objExists(profile_mult):
        profile_mult = cmds.rename(profile_mult, f"{new_line_name}_profileY_mult")

    smooth_node = None
    is_smoothable = orig_line_data.get("smoothable", False) or bool(orig_line_data.get("smooth_node")) or (
        bool(orig_mesh) and cmds.attributeQuery('divisions', node=orig_mesh, exists=True)
    )
    if is_smoothable:
        smooth_node = applySmoothToStrokeMesh(result_mesh, line_name=new_line_name)

    tex_def_node = None
    noise_node = None
    tex_handle_node = None
    has_disp = orig_line_data.get("displacement", False) or orig_line_data.get("add_noise", False) or bool(orig_line_data.get("noise_node")) or (
        bool(orig_mesh) and (
            cmds.attributeQuery('strength', node=orig_mesh, exists=True) or
            cmds.attributeQuery('noise_strength', node=orig_mesh, exists=True)
        )
    )
    disp_type = orig_line_data.get("disp_type")
    if not disp_type and orig_line_data.get("noise_node") and cmds.objExists(orig_line_data.get("noise_node")):
        disp_type = cmds.nodeType(orig_line_data.get("noise_node"))
    if not disp_type:
        disp_type = config.line_disp_type

    if is_smoothable and has_disp:
        tex_def_node, noise_node, tex_handle_node = applyDisplacementToStrokeMesh(result_mesh, line_name=new_line_name, disp_type=disp_type)
        if tex_handle_node and cmds.objExists(tex_handle_node):
            try:
                cmds.parent(tex_handle_node, line_group)
            except Exception:
                pass

    # Copy all attribute values from orig_mesh
    if orig_mesh and cmds.objExists(orig_mesh):
        for attr in [
            'scale_profile', 'roundness', 'rotate_profile', 'Sides', 'cap', 'precision', 'optimize_precision',
            'Start_position', 'Start_value', 'End_position', 'End_value',
            'method', 'divisions',
            'strength', 'offset',
            'noise_type', 'frequency', 'ratio', 'time',
            'snow_roughness', 'rock_roughness', 'boundary', 'altitude',
            'amplitude', 'frequency_ratio',
            'noise_strength', 'noise_frequency', 'noise_ratio', 'noise_offset', 'noise_time'
        ]:
            if cmds.attributeQuery(attr, node=orig_mesh, exists=True) and cmds.attributeQuery(attr, node=result_mesh, exists=True):
                try:
                    cmds.setAttr(f"{result_mesh}.{attr}", cmds.getAttr(f"{orig_mesh}.{attr}"))
                except Exception:
                    pass
        for i, (p_pos, p_val, p_int) in enumerate(pt_data, 1):
            if cmds.attributeQuery(f'Pt{i}_position', node=result_mesh, exists=True):
                try:
                    cmds.setAttr(f"{result_mesh}.Pt{i}_position", p_pos)
                    cmds.setAttr(f"{result_mesh}.Pt{i}_value", p_val)
                    cmds.setAttr(f"{result_mesh}.Pt{i}_interp", p_int)
                except Exception:
                    pass

    # Apply follow method
    follow_method = orig_line_data.get("follow_method", config.current_follow_method)
    follow_data = {"wrap_node": None, "follow_nodes": []}
    if target_mesh and cmds.objExists(target_mesh):
        try:
            follow_data = applyFollowMethod(
                follow_method=follow_method,
                curve_transform=new_crv,
                target_mesh=target_mesh,
                line_id=line_id,
                line_group=line_group,
                subdiv_offset=config.line_subdiv_offset
            )
        except Exception as e:
            print(f"Warning: could not apply follow method to mirrored line: {e}")

    # Setup visibility multDL
    mult_node = cmds.createNode('multDL', n=f"{new_line_name}_multDL", ss=True)
    cmds.setAttr(f"{mult_node}.input2", -1.0)
    cmds.connectAttr(f"{line_group}.v", f"{mult_node}.input1")
    cmds.connectAttr(f"{mult_node}.output", f"{sweep_mesh_node}.nodeState")
    if follow_data.get("wrap_node"):
        try:
            if not cmds.isConnected(f"{mult_node}.output", f"{follow_data['wrap_node']}.nodeState"):
                cmds.connectAttr(f"{mult_node}.output", f"{follow_data['wrap_node']}.nodeState")
        except Exception:
            pass
    for fn in follow_data.get("follow_nodes", []):
        if cmds.objExists(fn) and cmds.attributeQuery('nodeState', node=fn, exists=True):
            try:
                if not cmds.isConnected(f"{mult_node}.output", f"{fn}.nodeState"):
                    cmds.connectAttr(f"{mult_node}.output", f"{fn}.nodeState")
            except Exception:
                pass

    # Rename nodes cleanly
    if smooth_node and cmds.objExists(smooth_node):
        smooth_node = cmds.rename(smooth_node, f"{new_line_name}_smooth")
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

    result_mesh = cmds.rename(result_mesh, f"{new_line_name}_msh")
    sweep_mesh_node = cmds.rename(sweep_mesh_node, f"{new_line_name}_sweep")
    if cmds.objExists(new_crv) and not new_crv.endswith(f"{new_line_name}_crv"):
        new_crv = cmds.rename(new_crv, f"{new_line_name}_crv")
    reset_pivots_to_origin(master_grp, line_group, result_mesh, new_crv, root_converted_curve_group, first_group)

    # Shading - inherit base line color
    orig_color = orig_line_data.get("color")
    if orig_color is None and orig_mesh and cmds.objExists(orig_mesh):
        orig_color = getLineMeshColor(orig_mesh)
    if orig_color is None:
        orig_color = tuple(config.current_line_color)

    assignLineShader(result_mesh, color=orig_color)

    new_line_data = {
        "name": new_line_name,
        "type": orig_line_data.get("type", "paint"),
        "follow_method": follow_method,
        "target_mesh": target_mesh,
        "color": tuple(orig_color),
        "group": line_group,
        "mesh": result_mesh,
        "curve": new_crv,
        "sweep_msh_node": sweep_mesh_node,
        "sweep_mesh_node": sweep_mesh_node,
        "taper_ctrl_node": result_mesh,
        "brush_node": None,
        "wrap_node": follow_data.get("wrap_node"),
        "smooth_node": smooth_node,
        "smoothable": is_smoothable,
        "tex_def_node": tex_def_node,
        "noise_node": noise_node,
        "tex_handle": tex_handle_node,
        "displacement": bool(is_smoothable and has_disp),
        "disp_type": disp_type,
        "add_noise": bool(is_smoothable and has_disp),
        "profile_mult_node": profile_mult,
        "follow_nodes": follow_data.get("follow_nodes", []),
        "root_convert_grp": root_converted_curve_group,
        "converted_curve_grp": first_group,
        "mult_dl_node": mult_node,
        "reverse_state_node": mult_node,
        "baked": False
    }
    config.global_scene_data_obj.addLineData(new_line_data)
    return new_line_data

