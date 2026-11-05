from maya import cmds
import maya.api.OpenMaya as om
import core.config as config
from core.utils import reset_pivots_to_origin, find_best_edge_pair_for_point, get_target_mesh_for_line


def applyFollowMethod(follow_method, curve_transform, target_mesh, line_id, line_group, subdiv_offset):
    """
    Applies one of the three follow methods:
    1. 'Wrap deformer': Native Maya wrap deformer.
    2. 'UV pin': Maya 2026 native rivets snapped to closest UV, driving control points.
    3. 'Node based': 2 curveFromMeshEdge + 2 pointOnCurveInfo (turnOnPercentage) averaged via plusMinusAverage.
    """
    follow_nodes = []
    wrap_node = None
    curve_shapes = cmds.listRelatives(curve_transform, s=True, noIntermediate=True, fullPath=True) or cmds.listRelatives(curve_transform, s=True, fullPath=True) or []
    if not curve_shapes:
        return {"wrap_node": None, "follow_nodes": []}
    curve_shape = curve_shapes[0]

    visible_shapes = cmds.listRelatives(target_mesh, s=True, noIntermediate=True, fullPath=True) or []
    if not visible_shapes:
        visible_shapes = cmds.listRelatives(target_mesh, s=True, fullPath=True) or []
    target_shape = visible_shapes[0] if visible_shapes else target_mesh

    if follow_method == "Wrap deformer":
        cmds.select([curve_transform, target_mesh], r=True, noExpand=True)
        cmds.CreateWrap()
        curve_shapes = cmds.listRelatives(curve_transform, s=True, noIntermediate=True, fullPath=True) or cmds.listRelatives(curve_transform, s=True, fullPath=True) or []
        for s in curve_shapes:
            conns = cmds.listConnections(s + '.create', d=False, s=True)
            if conns:
                wrap_node = conns[0]
                break
        if not wrap_node:
            all_shapes = cmds.listRelatives(curve_transform, s=True, fullPath=True) or []
            for s in all_shapes:
                conns = cmds.listConnections(s + '.create', d=False, s=True)
                if conns:
                    wrap_node = conns[0]
                    break
        if wrap_node:
            wrap_node = cmds.rename(wrap_node, f"{line_group}_wrap")
            follow_nodes.append(wrap_node)
        return {"wrap_node": wrap_node, "follow_nodes": follow_nodes}

    elif follow_method == "UV pin":
        import maya.internal.nodes.uvpin.node_interface as uvpin_if

        sel = om.MSelectionList()
        sel.add(target_shape)
        dag = sel.getDagPath(0)
        mfn_mesh = om.MFnMesh(dag)

        num_cvs = len(cmds.ls(f"{curve_shape}.cv[*]", fl=True))
        rivets_grp = cmds.group(em=True, n=f"{line_group}_rivets_grp")
        cmds.parent(rivets_grp, line_group)
        cmds.setAttr(rivets_grp + '.v', 0)
        reset_pivots_to_origin(rivets_grp)
        follow_nodes.append(rivets_grp)

        for i in range(num_cvs):
            cv_pos = cmds.pointPosition(f"{curve_shape}.cv[{i}]", w=True)
            m_point = om.MPoint(cv_pos[0], cv_pos[1], cv_pos[2])
            closest_pt, face_id = mfn_mesh.getClosestPoint(m_point, space=om.MSpace.kWorld)
            u, v, _ = mfn_mesh.getUVAtPoint(closest_pt, space=om.MSpace.kWorld)
            normal = mfn_mesh.getClosestNormal(closest_pt, space=om.MSpace.kWorld)[0]

            cmds.select(f"{target_mesh}.f[{face_id}]", r=True)
            uvpin_if.createRivet()
            created = cmds.ls(sl=True)
            pin_node = cmds.rename(created[0], f"{line_group}_pin_{i}")
            loc = cmds.rename(created[1], f"{line_group}_rivet_{i}")
            cmds.parent(loc, rivets_grp)

            # Snap rivet to closest UV position
            cmds.setAttr(f"{pin_node}.coordinate[0].coordinateU", u)
            cmds.setAttr(f"{pin_node}.coordinate[0].coordinateV", v)

            decomp = cmds.createNode('decomposeMatrix', n=f"{line_group}_decomp_{i}")
            cmds.connectAttr(f"{pin_node}.outputMatrix[0]", f"{decomp}.inputMatrix")
            follow_nodes.extend([pin_node, loc, decomp])

            if subdiv_offset != 0:
                pma_off = cmds.createNode('plusMinusAverage', n=f"{line_group}_offset_{i}")
                cmds.setAttr(f"{pma_off}.operation", 1)  # Sum
                cmds.connectAttr(f"{decomp}.outputTranslate", f"{pma_off}.input3D[0]")
                cmds.setAttr(f"{pma_off}.input3D[1]", normal.x * subdiv_offset, normal.y * subdiv_offset, normal.z * subdiv_offset)
                cmds.connectAttr(f"{pma_off}.output3D", f"{curve_shape}.controlPoints[{i}]")
                follow_nodes.append(pma_off)
            else:
                cmds.connectAttr(f"{decomp}.outputTranslate", f"{curve_shape}.controlPoints[{i}]")

        cmds.select(cl=True)
        return {"wrap_node": None, "follow_nodes": follow_nodes}

    elif follow_method == "Node based":
        sel = om.MSelectionList()
        sel.add(target_shape)
        dag = sel.getDagPath(0)
        mfn_mesh = om.MFnMesh(dag)
        all_points = mfn_mesh.getPoints(om.MSpace.kWorld)
        poly_it = om.MItMeshPolygon(dag)
        edge_it = om.MItMeshEdge(dag)

        curve_sel = om.MSelectionList()
        curve_sel.add(curve_shape)
        curve_dag = curve_sel.getDagPath(0)
        mfn_curve = om.MFnNurbsCurve(curve_dag)
        all_cvs = mfn_curve.cvPositions(om.MSpace.kWorld)
        num_cvs = len(all_cvs)

        for i in range(num_cvs):
            cv_pos = all_cvs[i]
            pair, uv, normal = find_best_edge_pair_for_point(mfn_mesh, dag, cv_pos, poly_it=poly_it, edge_it=edge_it, all_points=all_points)
            e1, e2 = pair
            u, v = uv

            cfme1 = cmds.createNode('curveFromMeshEdge', n=f"{line_group}_cfme_{i}_a")
            cmds.connectAttr(f"{target_shape}.worldMesh[0]", f"{cfme1}.inputMesh")
            cmds.setAttr(f"{cfme1}.edgeIndex[0]", e1)

            cfme2 = cmds.createNode('curveFromMeshEdge', n=f"{line_group}_cfme_{i}_b")
            cmds.connectAttr(f"{target_shape}.worldMesh[0]", f"{cfme2}.inputMesh")
            cmds.setAttr(f"{cfme2}.edgeIndex[0]", e2)

            poci1 = cmds.createNode('pointOnCurveInfo', n=f"{line_group}_poci_{i}_a")
            cmds.connectAttr(f"{cfme1}.outputCurve", f"{poci1}.inputCurve")
            cmds.setAttr(f"{poci1}.turnOnPercentage", 1)
            cmds.setAttr(f"{poci1}.parameter", u)

            poci2 = cmds.createNode('pointOnCurveInfo', n=f"{line_group}_poci_{i}_b")
            cmds.connectAttr(f"{cfme2}.outputCurve", f"{poci2}.inputCurve")
            cmds.setAttr(f"{poci2}.turnOnPercentage", 1)
            cmds.setAttr(f"{poci2}.parameter", v)

            pma_avg = cmds.createNode('plusMinusAverage', n=f"Line_{line_id}_avg_{i}")
            cmds.setAttr(f"{pma_avg}.operation", 3)  # Average
            cmds.connectAttr(f"{poci1}.position", f"{pma_avg}.input3D[0]")
            cmds.connectAttr(f"{poci2}.position", f"{pma_avg}.input3D[1]")

            follow_nodes.extend([cfme1, cfme2, poci1, poci2, pma_avg])

            if subdiv_offset != 0:
                pma_off = cmds.createNode('plusMinusAverage', n=f"{line_group}_offset_{i}")
                cmds.setAttr(f"{pma_off}.operation", 1)  # Sum
                cmds.connectAttr(f"{pma_avg}.output3D", f"{pma_off}.input3D[0]")
                cmds.setAttr(f"{pma_off}.input3D[1]", normal.x * subdiv_offset, normal.y * subdiv_offset, normal.z * subdiv_offset)
                cmds.connectAttr(f"{pma_off}.output3D", f"{curve_shape}.controlPoints[{i}]")
                follow_nodes.append(pma_off)
            else:
                cmds.connectAttr(f"{pma_avg}.output3D", f"{curve_shape}.controlPoints[{i}]")

        return {"wrap_node": None, "follow_nodes": follow_nodes}

    return {"wrap_node": None, "follow_nodes": []}


def removeFollowMethodFromLine(line_data):
    """
    Cleanly removes the follow deformer / rivets / nodes attached to the curve
    so that a new follow method can be attached cleanly without leftover connections.
    Preserves the exact current world-space position and shape of the curve.
    """
    if not line_data:
        return
    crv = line_data.get("curve")
    line_group = line_data.get("group")
    if (not crv or not cmds.objExists(crv)) and line_group and cmds.objExists(line_group):
        rel_crvs = cmds.listRelatives(line_group, allDescendents=True, type="nurbsCurve") or []
        if rel_crvs:
            crv = cmds.listRelatives(rel_crvs[0], p=True)[0]
            line_data["curve"] = crv
    if not crv or not cmds.objExists(crv):
        return

    crv_shapes = cmds.listRelatives(crv, s=True, noIntermediate=True, fullPath=True) or cmds.listRelatives(crv, s=True, fullPath=True) or []
    if not crv_shapes:
        return
    crv_shape = crv_shapes[0]
    num_cvs = len(cmds.ls(f"{crv_shape}.cv[*]", fl=True))

    # Capture exact world-space position before disconnecting/deleting
    ws_positions = []
    if num_cvs > 0:
        try:
            ws_positions = [cmds.pointPosition(f"{crv_shape}.cv[{i}]", w=True) for i in range(num_cvs)]
        except Exception:
            ws_positions = []

    for i in range(num_cvs):
        conns = cmds.listConnections(f"{crv_shape}.controlPoints[{i}]", d=False, s=True, p=True) or []
        for src in conns:
            try:
                cmds.disconnectAttr(src, f"{crv_shape}.controlPoints[{i}]")
            except Exception:
                pass

    wn = line_data.get("wrap_node")
    if wn and cmds.objExists(wn):
        try:
            cmds.delete(wn)
        except Exception:
            pass
        for s in cmds.listRelatives(crv, s=True) or []:
            if 'Orig' in s and cmds.objExists(s):
                try:
                    cmds.delete(s)
                except Exception:
                    pass

    for fn in line_data.get("follow_nodes", []):
        if fn and cmds.objExists(fn):
            try:
                cmds.delete(fn)
            except Exception:
                pass

    # Re-assert world space positions so the curve permanently holds its exact evaluated shape
    if ws_positions and len(ws_positions) == num_cvs:
        for i, pos in enumerate(ws_positions):
            try:
                cmds.xform(f"{crv_shape}.cv[{i}]", ws=True, t=pos)
            except Exception:
                pass

    line_data["wrap_node"] = None
    line_data["follow_nodes"] = []


def changeLineFollowMethod(line_data, new_follow_method, subdiv_offset=None):
    """
    Switches or re-applies the follow method of a cartoon line (Node based, Wrap deformer, UV pin).
    Keeps all line nodes intact and only changes what is plugged into the curve.
    """
    if not line_data or not new_follow_method:
        return False
    line_group = line_data.get("group")
    crv = line_data.get("curve")
    if not crv or not cmds.objExists(crv):
        if line_group and cmds.objExists(line_group):
            rel_crvs = cmds.listRelatives(line_group, allDescendents=True, type="nurbsCurve") or []
            if rel_crvs:
                crv = cmds.listRelatives(rel_crvs[0], p=True)[0]
                line_data["curve"] = crv
    if not crv or not cmds.objExists(crv):
        return False

    target_mesh = line_data.get("target_mesh") or get_target_mesh_for_line(line_data) or config.paint_on_mesh
    if not target_mesh or not cmds.objExists(target_mesh):
        return False

    if subdiv_offset is None:
        subdiv_offset = config.line_subdiv_offset

    crv_shapes = cmds.listRelatives(crv, s=True, noIntermediate=True, fullPath=True) or cmds.listRelatives(crv, s=True, fullPath=True) or []
    if not crv_shapes:
        return False
    crv_shape = crv_shapes[0]

    current_method = line_data.get("follow_method")

    # If the line already has this follow method and its nodes are connected and valid,
    # keep all existing nodes intact and avoid re-projecting or accumulating drift.
    if current_method == new_follow_method:
        if new_follow_method == "Wrap deformer":
            wn = line_data.get("wrap_node")
            if wn and cmds.objExists(wn):
                return True
        elif new_follow_method in ("Node based", "UV pin"):
            fns = line_data.get("follow_nodes", [])
            has_valid_fn = any(cmds.objExists(fn) for fn in fns)
            conns = cmds.listConnections(f"{crv_shape}.controlPoints[0]", d=False, s=True) or []
            if has_valid_fn and conns:
                return True

    # 1. Capture exact world-space CV positions before modifying any connections
    num_cvs = len(cmds.ls(f"{crv_shape}.cv[*]", fl=True))
    exact_ws = [cmds.pointPosition(f"{crv_shape}.cv[{i}]", w=True) for i in range(num_cvs)]

    # 2. Safely remove old follow method connections and nodes
    removeFollowMethodFromLine(line_data)

    # 3. Re-assert the exact world-space coordinates on the curve CVs so geometry is fixed
    for i, pos in enumerate(exact_ws):
        try:
            cmds.xform(f"{crv_shape}.cv[{i}]", ws=True, t=pos)
        except Exception:
            pass

    line_name = line_data.get("name", "line_1")
    line_id = line_name.replace("line_", "") if "line_" in line_name else "1"

    # 4. Plug in the new follow method at the exact CV positions
    follow_data = applyFollowMethod(
        follow_method=new_follow_method,
        curve_transform=crv,
        target_mesh=target_mesh,
        line_id=line_id,
        line_group=line_group,
        subdiv_offset=subdiv_offset
    )

    mult_node = line_data.get("mult_dl_node") or (f"{line_name}_multDL" if line_name else None)
    if mult_node and cmds.objExists(mult_node):
        if follow_data.get("wrap_node"):
            try:
                cmds.connectAttr(f"{mult_node}.output", f"{follow_data['wrap_node']}.nodeState", force=True)
            except Exception:
                pass
        for fn in follow_data.get("follow_nodes", []):
            if cmds.objExists(fn) and cmds.attributeQuery('nodeState', node=fn, exists=True):
                try:
                    cmds.connectAttr(f"{mult_node}.output", f"{fn}.nodeState", force=True)
                except Exception:
                    pass

    line_data["follow_method"] = new_follow_method
    line_data["target_mesh"] = target_mesh
    line_data["wrap_node"] = follow_data.get("wrap_node")
    line_data["follow_nodes"] = follow_data.get("follow_nodes", [])
    line_data["baked"] = False
    return True

