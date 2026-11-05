import math
from maya import cmds
import maya.api.OpenMaya as om
import core.config as config


def reset_pivots_to_origin(*nodes):
    """
    Ensures that the given nodes (groups, meshes, curves) have their rotatePivot,
    scalePivot, and translate clean at the world origin (0, 0, 0), preventing offset pivots.
    """
    for node in nodes:
        if node and cmds.objExists(node):
            try:
                cmds.xform(node, ws=True, rp=(0.0, 0.0, 0.0), sp=(0.0, 0.0, 0.0))
                cmds.xform(node, zeroTransformPivots=True)
                for pivot_attr in ['rotatePivot', 'scalePivot', 'rotatePivotTranslate', 'scalePivotTranslate']:
                    if cmds.attributeQuery(pivot_attr, node=node, exists=True):
                        try:
                            cmds.setAttr(f"{node}.{pivot_attr}", 0.0, 0.0, 0.0)
                        except Exception:
                            pass
            except Exception:
                pass


def solve_param_pair(A1, B1, A2, B2, P):
    """
    Finds parameters u, v in [0, 1] along edges A1-B1 and A2-B2 such that their
    midpoint (average) minimizes the distance to point P.
    """
    v1 = [0.5 * (B1[k] - A1[k]) for k in range(3)]
    v2 = [0.5 * (B2[k] - A2[k]) for k in range(3)]
    w = [P[k] - 0.5 * (A1[k] + A2[k]) for k in range(3)]

    a = sum(v1[k] * v1[k] for k in range(3))
    b = sum(v1[k] * v2[k] for k in range(3))
    c = sum(v2[k] * v2[k] for k in range(3))
    d1 = sum(w[k] * v1[k] for k in range(3))
    d2 = sum(w[k] * v2[k] for k in range(3))

    det = a * c - b * b
    if abs(det) > 1e-9:
        u = (c * d1 - b * d2) / det
        v = (a * d2 - b * d1) / det
    else:
        u = d1 / a if a > 1e-9 else 0.5
        v = d2 / c if c > 1e-9 else 0.5

    u = max(0.0, min(1.0, u))
    v = max(0.0, min(1.0, v))

    mid = [0.5 * ((A1[k] + u * (B1[k] - A1[k])) + (A2[k] + v * (B2[k] - A2[k]))) for k in range(3)]
    dist = math.sqrt(sum((mid[k] - P[k]) ** 2 for k in range(3)))
    return u, v, dist, mid


def find_best_edge_pair_for_point(mfn_mesh, dag_mesh, P, poly_it=None, edge_it=None, all_points=None):
    """
    Finds the pair of edges in the closest polygon that forms the virtual triangle
    closest to point P, and computes parameters u, v and normal vector.
    Highly optimized: reuses iterators and pre-cached vertex positions when provided.
    """
    closest_pt, face_id = mfn_mesh.getClosestPoint(om.MPoint(P[0], P[1], P[2]), space=om.MSpace.kWorld)
    normal = mfn_mesh.getClosestNormal(closest_pt, space=om.MSpace.kWorld)[0]

    if poly_it is None:
        poly_it = om.MItMeshPolygon(dag_mesh)
    poly_it.setIndex(face_id)
    face_edges = poly_it.getEdges()
    n_edges = len(face_edges)

    if edge_it is None:
        edge_it = om.MItMeshEdge(dag_mesh)

    best_dist = float('inf')
    best_pair = (face_edges[0], face_edges[1] if n_edges > 1 else face_edges[0])
    best_uv = (0.5, 0.5)
    pt_coords = (closest_pt.x, closest_pt.y, closest_pt.z)

    # Pre-fetch edge vertex points and vertex sets
    edge_pts = []
    edge_verts = []
    for e in face_edges:
        edge_it.setIndex(e)
        v0 = edge_it.vertexId(0)
        v1 = edge_it.vertexId(1)
        if all_points is not None:
            p0 = all_points[v0]
            p1 = all_points[v1]
            edge_pts.append(((p0.x, p0.y, p0.z), (p1.x, p1.y, p1.z)))
        else:
            p0 = edge_it.point(0, om.MSpace.kWorld)
            p1 = edge_it.point(1, om.MSpace.kWorld)
            edge_pts.append(((p0.x, p0.y, p0.z), (p1.x, p1.y, p1.z)))
        edge_verts.append((v0, v1))

    for i in range(n_edges):
        A1, B1 = edge_pts[i]
        v1_0, v1_1 = edge_verts[i]
        for j in range(i + 1, n_edges):
            A2, B2 = edge_pts[j]
            v2_0, v2_1 = edge_verts[j]
            shares_vertex = (v1_0 == v2_0 or v1_0 == v2_1 or v1_1 == v2_0 or v1_1 == v2_1)

            u, v, dist, _ = solve_param_pair(A1, B1, A2, B2, pt_coords)

            # Prefer edges sharing a vertex to form the virtual triangle corner
            weight = 1.0 if shares_vertex else 1.3
            effective_dist = dist * weight

            if effective_dist < best_dist:
                best_dist = effective_dist
                best_pair = (face_edges[i], face_edges[j])
                best_uv = (u, v)

    return best_pair, best_uv, normal


def get_selected_mesh_from_scene():
    """
    Returns the transform name of the currently selected polygon mesh in Maya,
    or None if no valid mesh is selected (or if selected object is part of lineart).
    """
    try:
        sel = cmds.ls(sl=True)
        if not sel:
            return None

        for item in sel:
            node = item.split(".")[0] if "." in item else item
            if not cmds.objExists(node):
                continue
            if node == "grp_lines" or node.startswith("line_"):
                continue
            parents = cmds.listRelatives(node, allParents=True, fullPath=True) or []
            if any("grp_lines" in p for p in parents):
                continue

            # If it is a mesh shape node, get its parent transform
            if cmds.nodeType(node) == "mesh":
                parent = cmds.listRelatives(node, parent=True, fullPath=False)
                node = parent[0] if parent else node

            # Check if the node has at least one mesh shape
            shapes = cmds.listRelatives(node, shapes=True, type="mesh", fullPath=False) or []
            if shapes:
                if "|" in node:
                    short = node.split("|")[-1]
                    if len(cmds.ls(short)) == 1:
                        return short
                    return node
                return node
        return None
    except Exception:
        return None


def get_target_mesh_for_line(line_data):
    """
    Robustly determines the target character/object mesh for a cartoon line.
    Checks:
    1. 'target_mesh' in line_data
    2. Follow nodes in line_data (curveFromMeshEdge, uvPin, wrap) connections
    3. Global paint_on_mesh
    4. Active UI set_target_mesh_lineedit
    5. Scene mesh detection (excluding lineart groups)
    """
    if not line_data:
        return config.paint_on_mesh if config.paint_on_mesh and cmds.objExists(config.paint_on_mesh) else None

    # 1. Stored target_mesh
    tm = line_data.get("target_mesh")
    if tm and cmds.objExists(tm):
        return tm

    # 2. Inspect follow_nodes
    follow_nodes = line_data.get("follow_nodes", []) or []
    for fn in follow_nodes:
        if not cmds.objExists(fn):
            continue
        nt = cmds.nodeType(fn)
        if nt == "curveFromMeshEdge":
            conns = cmds.listConnections(f"{fn}.inputMesh", s=True, d=False) or []
            for c in conns:
                if cmds.nodeType(c) == "mesh":
                    p = cmds.listRelatives(c, p=True)
                    return p[0] if p else c
                elif cmds.objExists(c):
                    return c
        elif nt == "uvPin":
            for attr in ['deformedGeometry', 'originalGeometry']:
                if cmds.attributeQuery(attr, node=fn, exists=True):
                    conns = cmds.listConnections(f"{fn}.{attr}", s=True, d=False) or []
                    for c in conns:
                        if cmds.nodeType(c) == "mesh":
                            p = cmds.listRelatives(c, p=True)
                            return p[0] if p else c
                        elif cmds.objExists(c):
                            return c
        elif nt == "wrap":
            conns = cmds.listConnections(f"{fn}.driverPoints[0]", s=True, d=False) or []
            for c in conns:
                if cmds.nodeType(c) == "mesh":
                    p = cmds.listRelatives(c, p=True)
                    return p[0] if p else c
                elif cmds.objExists(c):
                    return c

    # 3. Inspect wrap_node
    wn = line_data.get("wrap_node")
    if wn and cmds.objExists(wn):
        conns = cmds.listConnections(f"{wn}.driverPoints[0]", s=True, d=False) or []
        for c in conns:
            if cmds.nodeType(c) == "mesh":
                p = cmds.listRelatives(c, p=True)
                return p[0] if p else c
            elif cmds.objExists(c):
                return c

    # 4. Global paint_on_mesh
    if config.paint_on_mesh and cmds.objExists(config.paint_on_mesh):
        return config.paint_on_mesh

    # 5. UI lineedit
    if config.global_main_widget and hasattr(config.global_main_widget, "set_target_mesh_lineedit"):
        txt = config.global_main_widget.set_target_mesh_lineedit.text().strip()
        if txt and cmds.objExists(txt):
            return txt

    # 6. Selected mesh
    detected = get_selected_mesh_from_scene()
    if detected:
        return detected

    return None

