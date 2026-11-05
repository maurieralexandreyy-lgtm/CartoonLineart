import scene_data
from maya import cmds, mel

# Global UI and scene references
main_window_instance = None
paint_on_mesh = None
global_main_widget = None
cartoon_lineart_shader = None

# Shared scene data object
global_scene_data_obj = scene_data.GlobalSceneData()

# Default parameters
line_default_scale = 0.1
line_subdiv_offset = 0.01
line_resolution = 5
curve_points = 4
smooth_curve = 1.0
brush_size = 1.0
current_follow_method = "Node based"
current_line_color = (0.0, 0.0, 0.0)
line_smoothable = False
line_displacement = False
line_add_noise = False
line_disp_type = "noise"
line_sweep_shape = 1.0

# Runtime session state
active_preset_config = None
_copied_line_attributes = None
_is_drawing_line = False

# ScriptJob event catchers
scene_event_catcher_num = None
selection_event_catcher_num = None
stroke_event_catcher_num = None
tool_event_catcher_num = None

# Ensure sweep plugin is loaded
if not cmds.pluginInfo('sweep', q=True, loaded=True):
    try:
        cmds.loadPlugin('sweep')
    except Exception as e:
        print(f"Warning: could not load sweep plugin: {e}")

# Patch Maya's AEstrokeTemplate to avoid 'No object matches name: strokeShapeDefaultBrush1.useNormal' error
try:
    mel.eval('''
    global proc AEstrokeDimUseNormal( string $nodeName )
    {
        if (`objExists ($nodeName + ".useNormal")`) {
            int $n = `getAttr ($nodeName + ".useNormal")`;
            editorTemplate -dimControl $nodeName "normal" (!$n);
            editorTemplate -dimControl $nodeName "minimalTwist" ($n);
        }
    }
    ''')
except Exception:
    pass

# Installing script job to refresh file on scene opened
try:
    scene_event_catcher_num = cmds.scriptJob(event=["SceneOpened", global_scene_data_obj.detectSceneChange])
except Exception:
    pass

