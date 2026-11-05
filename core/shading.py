from maya import cmds
import core.config as config


def findOrCreateShaderForColor(color=None):
    """
    Finds an existing surfaceShader with a color similar to `color` (tolerance < 0.02),
    or creates a new one and its shading group. Returns (shader, shading_engine).
    """
    if color is None:
        color = config.current_line_color
    r, g, b = float(color[0]), float(color[1]), float(color[2])

    all_shaders = cmds.ls(type='surfaceShader') or []
    best_shader = None
    best_dist = 0.02

    for s in all_shaders:
        if cmds.attributeQuery('outColor', node=s, exists=True):
            try:
                sc = cmds.getAttr(f"{s}.outColor")[0]
                dist = ((sc[0] - r) ** 2 + (sc[1] - g) ** 2 + (sc[2] - b) ** 2) ** 0.5
                if dist < best_dist:
                    best_dist = dist
                    best_shader = s
            except Exception:
                pass

    if best_shader:
        sgs = cmds.listConnections(f"{best_shader}.outColor", type='shadingEngine') or []
        if not sgs:
            sgs = cmds.listConnections(best_shader, type='shadingEngine') or []
        if sgs:
            return best_shader, sgs[0]
        sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=f"{best_shader}SG")
        cmds.connectAttr(f"{best_shader}.outColor", f"{sg}.surfaceShader")
        return best_shader, sg

    # Otherwise create a new shader
    hex_col = f"{int(round(r * 255)):02X}{int(round(g * 255)):02X}{int(round(b * 255)):02X}"
    base_name = f"CartoonLineart_{hex_col}" if hex_col != "000000" else "CartoonLineartShader"
    sg_name = f"{base_name}SG"

    if not cmds.objExists(base_name):
        sh = cmds.createNode('surfaceShader', name=base_name, ss=True)
    else:
        sh = cmds.createNode('surfaceShader', name=f"{base_name}#", ss=True)
        sg_name = f"{sh}SG"

    cmds.setAttr(f"{sh}.outColor", r, g, b, type='double3')

    if not cmds.objExists(sg_name):
        sg = cmds.sets(renderable=True, noSurfaceShader=True, empty=True, name=sg_name)
        cmds.connectAttr(f"{sh}.outColor", f"{sg}.surfaceShader")
    else:
        sg = sg_name

    return sh, sg


def getLineMeshColor(mesh_node):
    """
    Retrieves the RGB color of the shader currently assigned to `mesh_node`.
    """
    if not mesh_node or not cmds.objExists(mesh_node):
        return tuple(config.current_line_color)

    shapes = cmds.listRelatives(mesh_node, s=True, fullPath=True) or [mesh_node]
    for shape in shapes:
        sgs = cmds.listConnections(shape, type='shadingEngine') or []
        for sg in sgs:
            shaders = cmds.listConnections(f"{sg}.surfaceShader") or []
            if shaders:
                sh = shaders[0]
                if cmds.attributeQuery('outColor', node=sh, exists=True):
                    col = cmds.getAttr(f"{sh}.outColor")[0]
                    return (float(col[0]), float(col[1]), float(col[2]))
                elif cmds.attributeQuery('color', node=sh, exists=True):
                    col = cmds.getAttr(f"{sh}.color")[0]
                    return (float(col[0]), float(col[1]), float(col[2]))
    return tuple(config.current_line_color)


def detectOrCreateShader(color=None):
    sh, _ = findOrCreateShaderForColor(color)
    config.cartoon_lineart_shader = sh
    return sh


def assignLineShader(mesh_node, color=None):
    sh, sg = findOrCreateShaderForColor(color)
    if sg and cmds.objExists(sg):
        try:
            cmds.sets(mesh_node, forceElement=sg)
            return sh, sg
        except Exception:
            pass
    try:
        cmds.select(mesh_node, r=True)
        cmds.hyperShade(assign=sh)
        cmds.select(cl=True)
    except Exception:
        pass
    return sh, sg

