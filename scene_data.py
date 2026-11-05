import json
from maya import cmds
import pprint

from ui.pyside_compat import QtCore


class GlobalSceneData(QtCore.QObject):
    request_ui_sync = QtCore.Signal()
    request_ui_clear = QtCore.Signal()

    def __init__(self, *args, **kwargs):
        super().__init__()

        self.global_lines_data = {}
        self.scene_data_node = None
        self.scene_data_node_default_name = 'CartoonLineart_SceneData'

        self.checkSceneDataNode()

    def checkSceneDataNode(self):
        has_node = False
        if cmds.objExists(self.scene_data_node_default_name):
            print('CartoonLineart SceneDataNode found!')
            self.scene_data_node = self.scene_data_node_default_name
            self.loadSceneData()
            has_node = True
        elif cmds.objExists('CoolLines_SceneData'):
            print('Legacy CoolLines SceneDataNode found! Upgrading to CartoonLineart...')
            self.scene_data_node = cmds.rename('CoolLines_SceneData', self.scene_data_node_default_name)
            self.loadSceneData()
            has_node = True
        else:
            print('Cant find data! Creating a new CartoonLineart node so you can draw... :)')
            self.createSceneDataNode()

        self.syncFromScene()
        return has_node

    def createSceneDataNode(self):
        # Create Node to store data. Data will be empty at first.
        self.scene_data_node = cmds.scriptNode(st=0, bs='', n=self.scene_data_node_default_name, stp='python')

    def addLineData(self, line_data):
        self.global_lines_data[line_data["name"]] = line_data
        self.request_ui_sync.emit()
        self.saveSceneData()

    def getGlobalLinesData(self):
        return self.global_lines_data

    def getAllLines(self):
        return self.global_lines_data

    def getLineData(self, line_key):
        return self.global_lines_data.get(line_key)

    def removeLineData(self, line_key):
        if line_key in self.global_lines_data:
            self.global_lines_data.pop(line_key)
            self.saveSceneData()
            self.request_ui_sync.emit()

    def clearGlobalLinesData(self):
        self.global_lines_data.clear()
        self.saveSceneData()
        self.request_ui_clear.emit()

    def updateLineData(self, line_key, new_line_data, update_name=False):
        print('*********')
        print('Updating Line Data:')

        if update_name:
            if line_key in self.global_lines_data:
                self.global_lines_data.pop(line_key)
            self.global_lines_data[new_line_data["name"]] = new_line_data
            pprint.pprint(self.global_lines_data[new_line_data["name"]])
        else:
            self.global_lines_data[line_key] = new_line_data
            pprint.pprint(self.global_lines_data[line_key])

        self.saveSceneData()
        self.request_ui_sync.emit()

    def saveSceneData(self):
        if not (self.scene_data_node and cmds.objExists(self.scene_data_node)):
            self.checkSceneDataNode()
        # Dump data to node:
        if self.scene_data_node and cmds.objExists(self.scene_data_node):
            cmds.scriptNode(self.scene_data_node, e=True, bs=json.dumps(self.global_lines_data))
        else:
            cmds.warning("Cannot save scene data because there is no scene data node..")

    def loadSceneData(self):
        if not (self.scene_data_node and cmds.objExists(self.scene_data_node)):
            if not self.checkSceneDataNode():
                return
        if self.scene_data_node and cmds.objExists(self.scene_data_node):
            scene_data_str = cmds.scriptNode(self.scene_data_node, q=True, bs=True)
        else:
            cmds.warning("Cannot load scene data because there is no scene data node..")
            return

        if scene_data_str:
            try:
                scene_data = json.loads(scene_data_str)
                print('******************')
                print('Loaded Data:')
                print(scene_data)
                self.rebuildData(scene_data)
                self.request_ui_sync.emit()
            except Exception as e:
                print(f"Error parsing scene data json: {e}")
                self.global_lines_data.clear()
                self.request_ui_clear.emit()
        else:
            print("Skipping loading, data empty !")
            self.global_lines_data.clear()
            self.syncFromScene()
            self.request_ui_sync.emit()

    def rebuildData(self, scene_data):
        self.global_lines_data.clear()
        for current_line_name in list(scene_data.keys()):
            # Safe data rebuilding:
            grp_name = scene_data[current_line_name].get("group")
            if grp_name and cmds.objExists(grp_name):
                self.global_lines_data[current_line_name] = dict(scene_data[current_line_name])
            else:
                print(f"Cannot find {current_line_name}'s Data ! Removing...")

        self.syncFromScene()
        self.saveSceneData()
        print('Data rebuilt successfully')

    def syncFromScene(self):
        """
        Scans 'grp_lines' in the Maya scene and ensures all line groups ('line_1', 'line_2', etc.)
        are properly tracked in global_lines_data.
        """
        if not cmds.objExists("grp_lines"):
            return

        children = cmds.listRelatives("grp_lines", children=True, type="transform") or []
        added_any = False
        for child in children:
            line_name = child.split("|")[-1]
            if line_name in self.global_lines_data:
                continue

            descendants = cmds.listRelatives(child, allDescendents=True, fullPath=True) or []

            # 1. Mesh transform
            mesh_node = None
            for d in descendants:
                short_d = d.split("|")[-1]
                if short_d.endswith("_msh") and cmds.objExists(d):
                    mesh_node = short_d
                    break
            if not mesh_node:
                for d in descendants:
                    try:
                        shapes = cmds.listRelatives(d, shapes=True, type="mesh") or []
                        if shapes:
                            mesh_node = d.split("|")[-1]
                            break
                    except Exception:
                        pass

            # 2. Curve transform
            curve_node = None
            for d in descendants:
                short_d = d.split("|")[-1]
                if short_d.endswith("_crv") and cmds.objExists(d):
                    curve_node = short_d
                    break
            if not curve_node:
                for d in descendants:
                    try:
                        shapes = cmds.listRelatives(d, shapes=True, type="nurbsCurve") or []
                        if shapes:
                            curve_node = d.split("|")[-1]
                            break
                    except Exception:
                        pass

            # 3. Sweep node
            sweep_node = None
            if cmds.objExists(f"{line_name}_sweep"):
                sweep_node = f"{line_name}_sweep"
            elif mesh_node:
                conn = cmds.listConnections(f"{mesh_node}.inMesh", s=True, d=False) or []
                for c in conn:
                    if cmds.nodeType(c) == "sweepMesh":
                        sweep_node = c
                        break

            # 4. MultDL node
            mult_node = None
            if cmds.objExists(f"{line_name}_multDL"):
                mult_node = f"{line_name}_multDL"
            elif sweep_node:
                conn = cmds.listConnections(f"{sweep_node}.nodeState", s=True, d=False) or []
                for c in conn:
                    if cmds.nodeType(c) == "multDoubleLinear":
                        mult_node = c
                        break

            # 5. Wrap node
            wrap_node = None
            if cmds.objExists(f"{line_name}_wrap"):
                wrap_node = f"{line_name}_wrap"

            # 6. Smooth node
            smooth_node = None
            if cmds.objExists(f"{line_name}_smooth"):
                smooth_node = f"{line_name}_smooth"
            elif mesh_node:
                hist = cmds.listHistory(mesh_node) or []
                for h in hist:
                    if cmds.nodeType(h) == "polySmoothFace":
                        smooth_node = h
                        break
            smoothable = (smooth_node is not None) or (bool(mesh_node) and cmds.attributeQuery('divisions', node=mesh_node, exists=True))

            # 7. Displacement deformer and texture node
            tex_def_node = None
            noise_node = None
            tex_handle = None
            disp_type = "noise"
            if cmds.objExists(f"{line_name}_texDef"):
                tex_def_node = f"{line_name}_texDef"
            elif mesh_node:
                hist = cmds.listHistory(mesh_node) or []
                for h in hist:
                    if cmds.nodeType(h) == "textureDeformer":
                        tex_def_node = h
                        break

            for t_suffix in ["_noise", "_mountain", "_fractal"]:
                if cmds.objExists(f"{line_name}{t_suffix}"):
                    noise_node = f"{line_name}{t_suffix}"
                    disp_type = t_suffix[1:]
                    break

            if not noise_node and tex_def_node:
                conn = cmds.listConnections(f"{tex_def_node}.texture", s=True, d=False) or []
                for c in conn:
                    nt = cmds.nodeType(c)
                    if nt in ["noise", "mountain", "fractal"]:
                        noise_node = c
                        disp_type = nt
                        break

            if cmds.objExists(f"{line_name}_texDefHandle"):
                tex_handle = f"{line_name}_texDefHandle"

            has_disp = (tex_def_node is not None) or (bool(mesh_node) and (
                cmds.attributeQuery('strength', node=mesh_node, exists=True) or
                cmds.attributeQuery('noise_strength', node=mesh_node, exists=True)
            ))

            # 8. Profile mult node
            profile_mult = None
            if cmds.objExists(f"{line_name}_profileY_mult"):
                profile_mult = f"{line_name}_profileY_mult"

            # 9. Follow method
            follow_method = "Node based"
            if wrap_node:
                follow_method = "Wrap"
            elif cmds.objExists(f"{line_name}_rivets_grp"):
                follow_method = "UV pin"

            baked = (sweep_node is None)

            constructed_data = {
                "name": line_name,
                "type": "paint",
                "follow_method": follow_method,
                "group": child,
                "mesh": mesh_node or child,
                "curve": curve_node or child,
                "sweep_msh_node": sweep_node,
                "taper_ctrl_node": mesh_node or child,
                "wrap_node": wrap_node,
                "smooth_node": smooth_node,
                "smoothable": smoothable,
                "tex_def_node": tex_def_node,
                "noise_node": noise_node,
                "tex_handle": tex_handle,
                "displacement": has_disp,
                "disp_type": disp_type,
                "add_noise": has_disp,
                "profile_mult_node": profile_mult,
                "follow_nodes": [],
                "root_convert_grp": None,
                "converted_curve_grp": None,
                "mult_dl_node": mult_node,
                "reverse_state_node": mult_node,
                "baked": baked
            }
            self.global_lines_data[line_name] = constructed_data
            added_any = True
            print(f"[Cartoon Lineart] Discovered existing line in grp_lines: {line_name}")

        if added_any:
            self.saveSceneData()
            self.request_ui_sync.emit()

    def detectSceneChange(self):
        # A new scene has been opened..
        if not self.checkSceneDataNode():
            self.global_lines_data.clear()
            self.syncFromScene()
            self.request_ui_sync.emit()
