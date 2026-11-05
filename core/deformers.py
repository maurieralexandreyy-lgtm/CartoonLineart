from maya import cmds
import core.config as config


def removeSmoothFromStrokeMesh(stroke_mesh, line_data=None):
    if not stroke_mesh or not cmds.objExists(stroke_mesh):
        return
    hist = cmds.listHistory(stroke_mesh) or []
    for h in hist:
        if cmds.objExists(h) and cmds.nodeType(h) == "polySmoothFace":
            try:
                cmds.delete(h)
            except Exception:
                pass
    for attr in ['Smooth', 'method', 'divisions']:
        if cmds.attributeQuery(attr, node=stroke_mesh, exists=True):
            try:
                cmds.setAttr(f"{stroke_mesh}.{attr}", lock=False)
                cmds.deleteAttr(f"{stroke_mesh}.{attr}")
            except Exception:
                pass
    if line_data is not None:
        line_data["smooth_node"] = None
        line_data["smoothable"] = False


def removeDisplacementFromStrokeMesh(stroke_mesh, line_data=None):
    if not stroke_mesh or not cmds.objExists(stroke_mesh):
        return
    hist = cmds.listHistory(stroke_mesh) or []
    for h in hist:
        if cmds.objExists(h) and cmds.nodeType(h) == "textureDeformer":
            conn = cmds.listConnections(f"{h}.texture", s=True, d=False) or []
            for c in conn:
                if cmds.objExists(c) and cmds.nodeType(c) in ["noise", "mountain", "fractal"]:
                    try:
                        cmds.delete(c)
                    except Exception:
                        pass
            handle_conn = cmds.listConnections(f"{h}.handleMatrix", s=True, d=False) or []
            for hc in handle_conn:
                if cmds.objExists(hc):
                    try:
                        cmds.delete(hc)
                    except Exception:
                        pass
            if cmds.objExists(h):
                try:
                    cmds.delete(h)
                except Exception:
                    pass
    for attr in ['Displacement', 'Noise', 'strength', 'offset', 'noise_type', 'frequency', 'ratio', 'time',
                 'snow_roughness', 'rock_roughness', 'boundary', 'altitude', 'amplitude', 'frequency_ratio',
                 'noise_strength', 'noise_offset', 'noise_frequency', 'noise_ratio', 'noise_time']:
        if cmds.attributeQuery(attr, node=stroke_mesh, exists=True):
            try:
                cmds.setAttr(f"{stroke_mesh}.{attr}", lock=False)
                cmds.deleteAttr(f"{stroke_mesh}.{attr}")
            except Exception:
                pass
    if line_data is not None:
        line_data["tex_def_node"] = None
        line_data["noise_node"] = None
        line_data["tex_handle"] = None
        line_data["displacement"] = False
        line_data["add_noise"] = False


def applySmoothToStrokeMesh(result_mesh, line_name=None):
    """
    Applies a polySmoothFace node to the result mesh, adds a 'Smooth' Channel Box separator,
    and custom 'method' and 'divisions' attributes on the line's stroke mesh transform,
    connected to drive polySmoothFace.
    """
    if not result_mesh or not cmds.objExists(result_mesh):
        return None

    # Check if a polySmoothFace is already attached in history
    hist = cmds.listHistory(result_mesh) or []
    smooth_node = None
    for h in hist:
        if cmds.nodeType(h) == "polySmoothFace":
            smooth_node = h
            break
    else:
        smooth_nodes = cmds.polySmooth(result_mesh, mth=0, dv=1)
        if not smooth_nodes:
            return None
        smooth_node = smooth_nodes[0]

    # Add 'Smooth' Channel Box separator
    if not cmds.attributeQuery('Smooth', node=result_mesh, exists=True):
        cmds.addAttr(result_mesh, at='enum', k=True, en='__________', shortName='Smooth', h=False)
        cmds.setAttr(f"{result_mesh}.Smooth", lock=True)

    # Add custom attributes method and divisions if not existing
    if not cmds.attributeQuery('method', node=result_mesh, exists=True):
        cmds.addAttr(result_mesh, at='enum', en='Exponential:Linear', k=True, shortName='method')
        cmds.setAttr(f"{result_mesh}.method", 0)
    if not cmds.attributeQuery('divisions', node=result_mesh, exists=True):
        cmds.addAttr(result_mesh, at='long', k=True, min=0, max=4, defaultValue=1, shortName='divisions')
        cmds.setAttr(f"{result_mesh}.divisions", 1)

    # Ensure connections
    if not cmds.isConnected(f"{result_mesh}.method", f"{smooth_node}.method"):
        try:
            cmds.connectAttr(f"{result_mesh}.method", f"{smooth_node}.method", force=True)
        except Exception:
            pass
    if not cmds.isConnected(f"{result_mesh}.divisions", f"{smooth_node}.divisions"):
        try:
            cmds.connectAttr(f"{result_mesh}.divisions", f"{smooth_node}.divisions", force=True)
        except Exception:
            pass

    if line_name and smooth_node != f"{line_name}_smooth" and not cmds.objExists(f"{line_name}_smooth"):
        smooth_node = cmds.rename(smooth_node, f"{line_name}_smooth")

    mult_name = f"{line_name}_multDL" if line_name else None
    if mult_name and cmds.objExists(mult_name) and smooth_node and cmds.objExists(smooth_node):
        try:
            if not cmds.isConnected(f"{mult_name}.output", f"{smooth_node}.nodeState"):
                cmds.connectAttr(f"{mult_name}.output", f"{smooth_node}.nodeState", force=True)
        except Exception:
            pass

    return smooth_node


def applyDisplacementToStrokeMesh(result_mesh, line_name=None, disp_type=None):
    """
    Applies a textureDeformer node driven by a procedural texture node ('noise', 'mountain', or 'fractal')
    to the result mesh.
    Adds a 'Displacement' Channel Box separator and custom attributes on the line's stroke mesh transform:
    - Common: 'strength', 'offset'
    - noise: 'noise_type' (Billow by default), 'frequency', 'ratio', 'time'
    - mountain: 'snow_roughness', 'rock_roughness', 'boundary', 'altitude'
    - fractal: 'amplitude', 'ratio', 'frequency_ratio', 'time'
    """
    if not result_mesh or not cmds.objExists(result_mesh):
        return None, None, None

    chosen_type = (disp_type or config.line_disp_type or "noise").lower().strip()
    if chosen_type not in ["noise", "mountain", "fractal"]:
        chosen_type = "noise"

    hist = cmds.listHistory(result_mesh) or []
    tex_def = None
    for h in hist:
        if cmds.nodeType(h) == "textureDeformer":
            tex_def = h
            break

    tex_handle = None
    tex_node = None

    if not tex_def:
        tex_name = f"{line_name}_texDef" if line_name else "line_texDef"
        tex_def_nodes = cmds.textureDeformer(result_mesh, name=tex_name)
        tex_def = tex_def_nodes[0]
        if len(tex_def_nodes) > 1:
            tex_handle = tex_def_nodes[1]
            if line_name and not tex_handle.startswith(line_name):
                try:
                    tex_handle = cmds.rename(tex_handle, f"{line_name}_texDefHandle")
                except Exception:
                    pass

        # Normal displacement along surface normals for subtle brush stroke irregularity
        try:
            cmds.setAttr(f"{tex_def}.direction", 0)  # 0 = Normal
        except Exception:
            pass

        # Hide deformer handle in viewport
        try:
            cmds.setAttr(f"{tex_def}.handleVisibility", 0)
        except Exception:
            pass

        # Create procedural texture node according to chosen_type
        tex_node_name = f"{line_name}_{chosen_type}" if line_name else f"line_{chosen_type}"
        tex_node = cmds.createNode(chosen_type, name=tex_node_name)
        cmds.connectAttr(f"{tex_node}.outColor", f"{tex_def}.texture", force=True)

        if chosen_type == "noise":
            try:
                cmds.setAttr(f"{tex_node}.noiseType", 1)  # 1 = Billow
                cmds.setAttr(f"{tex_node}.frequency", 12.0)
                cmds.setAttr(f"{tex_node}.ratio", 0.7)
            except Exception:
                pass
        elif chosen_type == "mountain":
            try:
                cmds.setAttr(f"{tex_node}.snowRoughness", 0.4)
                cmds.setAttr(f"{tex_node}.rockRoughness", 0.7)
                cmds.setAttr(f"{tex_node}.boundary", 1.0)
                cmds.setAttr(f"{tex_node}.snowAltitude", 0.5)
            except Exception:
                pass
        elif chosen_type == "fractal":
            try:
                cmds.setAttr(f"{tex_node}.amplitude", 1.0)
                cmds.setAttr(f"{tex_node}.ratio", 0.707)
                cmds.setAttr(f"{tex_node}.frequencyRatio", 2.0)
            except Exception:
                pass
    else:
        existing_tex_node = None
        conn = cmds.listConnections(f"{tex_def}.texture", s=True, d=False) or []
        for c in conn:
            nt = cmds.nodeType(c)
            if nt in ["noise", "mountain", "fractal"]:
                existing_tex_node = c
                break
        handle_conn = cmds.listConnections(f"{tex_def}.handleMatrix", s=True, d=False) or []
        if handle_conn:
            tex_handle = handle_conn[0]

        if existing_tex_node and cmds.nodeType(existing_tex_node) != chosen_type:
            # Different texture type requested! Delete old texture node and old type-specific attrs
            try:
                cmds.delete(existing_tex_node)
            except Exception:
                pass
            existing_tex_node = None

            type_specific_attrs = [
                'noise_type', 'frequency', 'ratio', 'time',
                'snow_roughness', 'rock_roughness', 'boundary', 'altitude',
                'amplitude', 'frequency_ratio'
            ]
            for attr in type_specific_attrs:
                if cmds.attributeQuery(attr, node=result_mesh, exists=True):
                    try:
                        cmds.setAttr(f"{result_mesh}.{attr}", lock=False)
                        cmds.deleteAttr(f"{result_mesh}.{attr}")
                    except Exception:
                        pass

        if not existing_tex_node:
            tex_node_name = f"{line_name}_{chosen_type}" if line_name else f"line_{chosen_type}"
            tex_node = cmds.createNode(chosen_type, name=tex_node_name)
            cmds.connectAttr(f"{tex_node}.outColor", f"{tex_def}.texture", force=True)

            if chosen_type == "noise":
                try:
                    cmds.setAttr(f"{tex_node}.noiseType", 1)  # 1 = Billow
                    cmds.setAttr(f"{tex_node}.frequency", 12.0)
                    cmds.setAttr(f"{tex_node}.ratio", 0.7)
                except Exception:
                    pass
            elif chosen_type == "mountain":
                try:
                    cmds.setAttr(f"{tex_node}.snowRoughness", 0.4)
                    cmds.setAttr(f"{tex_node}.rockRoughness", 0.7)
                    cmds.setAttr(f"{tex_node}.boundary", 1.0)
                    cmds.setAttr(f"{tex_node}.snowAltitude", 0.5)
                except Exception:
                    pass
            elif chosen_type == "fractal":
                try:
                    cmds.setAttr(f"{tex_node}.amplitude", 1.0)
                    cmds.setAttr(f"{tex_node}.ratio", 0.707)
                    cmds.setAttr(f"{tex_node}.frequencyRatio", 2.0)
                except Exception:
                    pass
        else:
            tex_node = existing_tex_node

    # Add 'Displacement' Channel Box separator on result_mesh
    if not cmds.attributeQuery('Displacement', node=result_mesh, exists=True) and not cmds.attributeQuery('Noise', node=result_mesh, exists=True):
        cmds.addAttr(result_mesh, at='enum', k=True, en='__________', shortName='Displacement', h=False)
        cmds.setAttr(f"{result_mesh}.Displacement", lock=True)

    # Common displacement attributes: strength and offset
    if not cmds.attributeQuery('strength', node=result_mesh, exists=True):
        cmds.addAttr(result_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=0.03, shortName='strength', niceName='Strength')
        cmds.setAttr(f"{result_mesh}.strength", 0.03)
        if cmds.attributeQuery('noise_strength', node=result_mesh, exists=True):
            try:
                cmds.setAttr(f"{result_mesh}.strength", cmds.getAttr(f"{result_mesh}.noise_strength"))
            except Exception:
                pass

    if not cmds.attributeQuery('offset', node=result_mesh, exists=True):
        cmds.addAttr(result_mesh, at='float', k=True, defaultValue=0.0, shortName='offset', niceName='Offset')
        cmds.setAttr(f"{result_mesh}.offset", 0.0)
        if cmds.attributeQuery('noise_offset', node=result_mesh, exists=True):
            try:
                cmds.setAttr(f"{result_mesh}.offset", cmds.getAttr(f"{result_mesh}.noise_offset"))
            except Exception:
                pass

    if tex_def and cmds.objExists(tex_def):
        if not cmds.isConnected(f"{result_mesh}.strength", f"{tex_def}.strength"):
            try:
                cmds.connectAttr(f"{result_mesh}.strength", f"{tex_def}.strength", force=True)
            except Exception:
                pass
        if not cmds.isConnected(f"{result_mesh}.offset", f"{tex_def}.offset"):
            try:
                cmds.connectAttr(f"{result_mesh}.offset", f"{tex_def}.offset", force=True)
            except Exception:
                pass

    # Type-specific custom attributes
    if chosen_type == "noise":
        if not cmds.attributeQuery('noise_type', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='enum', en='Perlin Noise:Billow:Wave:Wispy:SpaceTime', k=True, defaultValue=1, shortName='noise_type', niceName='Noise Type')
            cmds.setAttr(f"{result_mesh}.noise_type", 1)  # Billow by default

        if not cmds.attributeQuery('frequency', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.1, defaultValue=12.0, shortName='frequency', niceName='Frequency')
            cmds.setAttr(f"{result_mesh}.frequency", 12.0)
            if cmds.attributeQuery('noise_frequency', node=result_mesh, exists=True):
                try:
                    cmds.setAttr(f"{result_mesh}.frequency", cmds.getAttr(f"{result_mesh}.noise_frequency"))
                except Exception:
                    pass

        if not cmds.attributeQuery('ratio', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=0.7, shortName='ratio', niceName='Ratio')
            cmds.setAttr(f"{result_mesh}.ratio", 0.7)
            if cmds.attributeQuery('noise_ratio', node=result_mesh, exists=True):
                try:
                    cmds.setAttr(f"{result_mesh}.ratio", cmds.getAttr(f"{result_mesh}.noise_ratio"))
                except Exception:
                    pass

        if not cmds.attributeQuery('time', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, defaultValue=0.0, shortName='time', niceName='Time')
            cmds.setAttr(f"{result_mesh}.time", 0.0)
            if cmds.attributeQuery('noise_time', node=result_mesh, exists=True):
                try:
                    cmds.setAttr(f"{result_mesh}.time", cmds.getAttr(f"{result_mesh}.noise_time"))
                except Exception:
                    pass

        if tex_node and cmds.objExists(tex_node):
            if not cmds.isConnected(f"{result_mesh}.noise_type", f"{tex_node}.noiseType"):
                try:
                    cmds.connectAttr(f"{result_mesh}.noise_type", f"{tex_node}.noiseType", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.frequency", f"{tex_node}.frequency"):
                try:
                    cmds.connectAttr(f"{result_mesh}.frequency", f"{tex_node}.frequency", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.ratio", f"{tex_node}.ratio"):
                try:
                    cmds.connectAttr(f"{result_mesh}.ratio", f"{tex_node}.ratio", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.time", f"{tex_node}.time"):
                try:
                    cmds.connectAttr(f"{result_mesh}.time", f"{tex_node}.time", force=True)
                except Exception:
                    pass

    elif chosen_type == "mountain":
        if not cmds.attributeQuery('snow_roughness', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=0.4, shortName='snow_roughness', niceName='Snow Roughness')
            cmds.setAttr(f"{result_mesh}.snow_roughness", 0.4)

        if not cmds.attributeQuery('rock_roughness', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=0.7, shortName='rock_roughness', niceName='Rock Roughness')
            cmds.setAttr(f"{result_mesh}.rock_roughness", 0.7)

        if not cmds.attributeQuery('boundary', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=1.0, shortName='boundary', niceName='Boundary')
            cmds.setAttr(f"{result_mesh}.boundary", 1.0)

        if not cmds.attributeQuery('altitude', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, defaultValue=0.5, shortName='altitude', niceName='Altitude')
            cmds.setAttr(f"{result_mesh}.altitude", 0.5)

        if tex_node and cmds.objExists(tex_node):
            if not cmds.isConnected(f"{result_mesh}.snow_roughness", f"{tex_node}.snowRoughness"):
                try:
                    cmds.connectAttr(f"{result_mesh}.snow_roughness", f"{tex_node}.snowRoughness", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.rock_roughness", f"{tex_node}.rockRoughness"):
                try:
                    cmds.connectAttr(f"{result_mesh}.rock_roughness", f"{tex_node}.rockRoughness", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.boundary", f"{tex_node}.boundary"):
                try:
                    cmds.connectAttr(f"{result_mesh}.boundary", f"{tex_node}.boundary", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.altitude", f"{tex_node}.snowAltitude"):
                try:
                    cmds.connectAttr(f"{result_mesh}.altitude", f"{tex_node}.snowAltitude", force=True)
                except Exception:
                    pass

    elif chosen_type == "fractal":
        if not cmds.attributeQuery('amplitude', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, defaultValue=1.0, shortName='amplitude', niceName='Amplitude')
            cmds.setAttr(f"{result_mesh}.amplitude", 1.0)

        if not cmds.attributeQuery('ratio', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.0, max=1.0, defaultValue=0.707, shortName='ratio', niceName='Ratio')
            cmds.setAttr(f"{result_mesh}.ratio", 0.707)

        if not cmds.attributeQuery('frequency_ratio', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, min=0.1, defaultValue=2.0, shortName='frequency_ratio', niceName='Frequency Ratio')
            cmds.setAttr(f"{result_mesh}.frequency_ratio", 2.0)

        if not cmds.attributeQuery('time', node=result_mesh, exists=True):
            cmds.addAttr(result_mesh, at='float', k=True, defaultValue=0.0, shortName='time', niceName='Time')
            cmds.setAttr(f"{result_mesh}.time", 0.0)

        if tex_node and cmds.objExists(tex_node):
            if not cmds.isConnected(f"{result_mesh}.amplitude", f"{tex_node}.amplitude"):
                try:
                    cmds.connectAttr(f"{result_mesh}.amplitude", f"{tex_node}.amplitude", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.ratio", f"{tex_node}.ratio"):
                try:
                    cmds.connectAttr(f"{result_mesh}.ratio", f"{tex_node}.ratio", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.frequency_ratio", f"{tex_node}.frequencyRatio"):
                try:
                    cmds.connectAttr(f"{result_mesh}.frequency_ratio", f"{tex_node}.frequencyRatio", force=True)
                except Exception:
                    pass
            if not cmds.isConnected(f"{result_mesh}.time", f"{tex_node}.time"):
                try:
                    cmds.connectAttr(f"{result_mesh}.time", f"{tex_node}.time", force=True)
                except Exception:
                    pass

    mult_name = f"{line_name}_multDL" if line_name else None
    if mult_name and cmds.objExists(mult_name) and tex_def and cmds.objExists(tex_def):
        try:
            if not cmds.isConnected(f"{mult_name}.output", f"{tex_def}.nodeState"):
                cmds.connectAttr(f"{mult_name}.output", f"{tex_def}.nodeState", force=True)
        except Exception:
            pass

    line_group = f"{line_name}_grp" if line_name else None
    if line_group and cmds.objExists(line_group) and tex_handle and cmds.objExists(tex_handle):
        parent = cmds.listRelatives(tex_handle, parent=True) or []
        if not parent or parent[0] != line_group:
            try:
                cmds.parent(tex_handle, line_group)
            except Exception:
                pass

    return tex_def, tex_node, tex_handle


applyNoiseToStrokeMesh = applyDisplacementToStrokeMesh

