"""Zero-cost local Blender automation helpers. No cloud API or API credits are used."""
import json, re, subprocess, uuid
from pathlib import Path
from .config import WORKSPACE_DIR, BLENDER_EXE
from .asset_studio import OUTPUT_DIR, ASSET_DIR

TOOLS_DIR = ASSET_DIR / "generated_scripts"
TOOLS_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_EXT = {'.glb', '.gltf', '.fbx', '.obj', '.blend', '.ply', '.stl'}


def _asset_path(relative: str) -> Path:
    p = (WORKSPACE_DIR / relative).resolve()
    if not p.is_relative_to(WORKSPACE_DIR) or not p.is_file():
        raise ValueError('Choose an existing model file inside the OmniForge workspace.')
    if p.suffix.lower() not in ALLOWED_EXT:
        raise ValueError('Supported inputs: GLB, GLTF, FBX, OBJ, BLEND, PLY, STL.')
    return p


def _run(script: str, label: str):
    if not BLENDER_EXE:
        raise RuntimeError('Blender is not configured. Install Blender and set BLENDER_EXE in .env. This feature is free and runs locally.')
    script_path = TOOLS_DIR / f'{label}_{uuid.uuid4().hex[:8]}.py'
    script_path.write_text(script, encoding='utf-8')
    try:
        result = subprocess.run([BLENDER_EXE, '--background', '--python', str(script_path)], cwd=str(WORKSPACE_DIR), capture_output=True, text=True, timeout=900, shell=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError('Blender exceeded the 15-minute safety timeout.') from exc
    output = ((result.stdout or '') + '\n' + (result.stderr or ''))[-18000:]
    if result.returncode:
        raise RuntimeError(f'Blender {label} failed (exit {result.returncode}). Details: {output[-5000:]}')
    return {'ok': True, 'operation': label, 'output': output}


def inspect_model(relative_path: str):
    source = _asset_path(relative_path)
    report = OUTPUT_DIR / f'{source.stem}_inspection_{uuid.uuid4().hex[:8]}.json'
    script = r'''import bpy, json, os
src = __SOURCE__
report = __REPORT__
if src.lower().endswith('.blend'):
    bpy.ops.wm.open_mainfile(filepath=src)
else:
    ext=os.path.splitext(src)[1].lower()
    if ext in ('.glb','.gltf'): bpy.ops.import_scene.gltf(filepath=src)
    elif ext=='.fbx': bpy.ops.import_scene.fbx(filepath=src)
    elif ext=='.obj':
        if hasattr(bpy.ops.wm,'obj_import'): bpy.ops.wm.obj_import(filepath=src)
        else: bpy.ops.import_scene.obj(filepath=src)
    elif ext=='.ply': bpy.ops.import_mesh.ply(filepath=src)
    elif ext=='.stl': bpy.ops.import_mesh.stl(filepath=src)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
armatures=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
materials={m.name for o in meshes for m in o.data.materials if m}
faces=sum(len(o.data.polygons) for o in meshes); verts=sum(len(o.data.vertices) for o in meshes)
objects=[]
for o in meshes:
    dims=[round(float(v),4) for v in o.dimensions]
    objects.append({'name':o.name,'vertices':len(o.data.vertices),'faces':len(o.data.polygons),'dimensions':dims,'materials':[m.name if m else None for m in o.data.materials]})
report_data={'source':src,'mesh_count':len(meshes),'armature_count':len(armatures),'material_count':len(materials),'vertices':verts,'faces':faces,'objects':objects,'armatures':[{'name':a.name,'bones':len(a.data.bones)} for a in armatures], 'warnings':[]}
if not meshes: report_data['warnings'].append('No mesh objects found.')
if not armatures: report_data['warnings'].append('No armature found; this model is not rigged yet.')
if not materials: report_data['warnings'].append('No materials assigned; inspect texture/material setup.')
if faces>150000: report_data['warnings'].append('High polygon count; consider making an optimized copy.')
with open(report,'w',encoding='utf-8') as f: json.dump(report_data,f,indent=2)
print('OMNIFORGE_REPORT='+json.dumps(report_data))
'''.replace('__SOURCE__', repr(str(source))).replace('__REPORT__', repr(str(report)))
    result = _run(script, 'inspect')
    try: data = json.loads(report.read_text(encoding='utf-8'))
    except Exception: data = {'output': result['output'], 'report_file': str(report.relative_to(WORKSPACE_DIR))}
    data['report_file'] = str(report.relative_to(WORKSPACE_DIR))
    return data


def optimize_model(relative_path: str, target_faces: int = 50000, export_format: str = 'glb'):
    source = _asset_path(relative_path)
    if not 1000 <= target_faces <= 2000000: raise ValueError('Target face count must be between 1,000 and 2,000,000.')
    if export_format not in {'glb','fbx'}: raise ValueError('Export format must be glb or fbx.')
    target = OUTPUT_DIR / f'{source.stem}_optimized_{uuid.uuid4().hex[:8]}.{export_format}'
    script = r'''import bpy, os
src=__SOURCE__; dst=__DEST__; target=__TARGET__; target_faces=__FACES__
if src.lower().endswith('.blend'): bpy.ops.wm.open_mainfile(filepath=src)
else:
 ext=os.path.splitext(src)[1].lower()
 if ext in ('.glb','.gltf'): bpy.ops.import_scene.gltf(filepath=src)
 elif ext=='.fbx': bpy.ops.import_scene.fbx(filepath=src)
 elif ext=='.obj':
  if hasattr(bpy.ops.wm,'obj_import'): bpy.ops.wm.obj_import(filepath=src)
  else: bpy.ops.import_scene.obj(filepath=src)
 elif ext=='.ply': bpy.ops.import_mesh.ply(filepath=src)
 elif ext=='.stl': bpy.ops.import_mesh.stl(filepath=src)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
if not meshes: raise RuntimeError('No mesh objects to optimize')
faces=sum(len(o.data.polygons) for o in meshes)
if faces>target_faces:
 ratio=max(0.01,min(1.0,target_faces/faces))
 for o in meshes:
  if len(o.data.polygons)>4:
   mod=o.modifiers.new('OmniForge_Decimate','DECIMATE'); mod.ratio=ratio
   bpy.context.view_layer.objects.active=o
   try: bpy.ops.object.modifier_apply(modifier=mod.name)
   except Exception: pass
for o in meshes:
 bpy.context.view_layer.objects.active=o
 try: bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
 except Exception: pass
if dst=='glb': bpy.ops.export_scene.gltf(filepath=target,export_format='GLB',use_selection=False)
else: bpy.ops.export_scene.fbx(filepath=target,use_selection=False,add_leaf_bones=False,bake_anim=True)
print('OMNIFORGE_EXPORTED='+target)
'''.replace('__SOURCE__',repr(str(source))).replace('__DEST__',repr(export_format)).replace('__TARGET__',repr(str(target))).replace('__FACES__',str(target_faces))
    script = script.replace("target=__TARGET__", f"target={repr(str(target))}")
    result = _run(script, 'optimize')
    if not target.is_file(): raise RuntimeError('Blender reported success but the exported file was not found.')
    return {'ok':True,'input':str(source.relative_to(WORKSPACE_DIR)),'output':str(target.relative_to(WORKSPACE_DIR)),'bytes':target.stat().st_size,'target_faces':target_faces,'blender_output':result['output']}


def animate_rig(relative_path: str, action: str = 'walk', fps: int = 24):
    source = _asset_path(relative_path)
    if action not in {'idle','walk','run','attack','death'}: raise ValueError('Action must be idle, walk, run, attack, or death.')
    if not 12 <= fps <= 60: raise ValueError('FPS must be between 12 and 60.')
    target = OUTPUT_DIR / f'{source.stem}_{action}_{uuid.uuid4().hex[:8]}.fbx'
    # This creates a procedural starter animation only on an existing armature; it does not claim to rig an unrigged mesh.
    script = r'''import bpy, os, math
src=__SOURCE__; dst=__DEST__; action=__ACTION__; fps=__FPS__
if src.lower().endswith('.blend'): bpy.ops.wm.open_mainfile(filepath=src)
else:
 ext=os.path.splitext(src)[1].lower()
 if ext in ('.glb','.gltf'): bpy.ops.import_scene.gltf(filepath=src)
 elif ext=='.fbx': bpy.ops.import_scene.fbx(filepath=src)
 elif ext=='.obj':
  if hasattr(bpy.ops.wm,'obj_import'): bpy.ops.wm.obj_import(filepath=src)
  else: bpy.ops.import_scene.obj(filepath=src)
 elif ext=='.ply': bpy.ops.import_mesh.ply(filepath=src)
 elif ext=='.stl': bpy.ops.import_mesh.stl(filepath=src)
rigs=[o for o in bpy.context.scene.objects if o.type=='ARMATURE']
if not rigs: raise RuntimeError('No armature found. This tool animates existing rigs; it does not automatically rig arbitrary meshes.')
rig=rigs[0]; scene=bpy.context.scene; scene.render.fps=fps
scene.frame_start=1; scene.frame_end=24 if action in ('idle','walk','run') else 30
for pose in rig.pose.bones: pose.rotation_mode='XYZ'
# Match common Mixamo / Rigify naming conventions, then fall back to substring matching.
def find(*terms):
 for p in rig.pose.bones:
  n=p.name.lower().replace('_','').replace(' ','')
  if any(t in n for t in terms): return p
 return None
hips=find('hips','pelvis','root'); spine=find('spine','chest'); armL=find('leftarm','upperarml','upper_arm.l','arml'); armR=find('rightarm','upperarmr','upper_arm.r','armr'); legL=find('leftupleg','thighl','thigh.l','upperlegl'); legR=find('rightupleg','thighr','thigh.r','upperlegr'); head=find('head')
frames=[1,7,13,19,25] if scene.frame_end==24 else [1,8,16,23,30]
for idx,frame in enumerate(frames):
 t=idx*math.pi/2
 for bone in rig.pose.bones:
  bone.rotation_euler=(0,0,0)
  if action in ('walk','run'):
   speed=1.0 if action=='walk' else 1.6
   if bone==legL: bone.rotation_euler.x=math.sin(t)*0.42*speed
   if bone==legR: bone.rotation_euler.x=-math.sin(t)*0.42*speed
   if bone==armL: bone.rotation_euler.x=-math.sin(t)*0.28*speed
   if bone==armR: bone.rotation_euler.x=math.sin(t)*0.28*speed
   if hips: hips.location.z=abs(math.sin(t))*0.035*(1.5 if action=='run' else 1)
  elif action=='idle':
   if spine: spine.rotation_euler.y=math.sin(t)*0.025
   if head: head.rotation_euler.y=math.sin(t+1)*0.035
  elif action=='attack':
   if spine: spine.rotation_euler.y=[0,-0.25,-0.5,0.2,0][idx]
   if armL: armL.rotation_euler.x=[0,-0.4,-1.1,0.3,0][idx]
   if armR: armR.rotation_euler.x=[0,-0.4,-1.1,0.3,0][idx]
  elif action=='death':
   if spine: spine.rotation_euler.x=[0,0.15,0.5,0.9,1.1][idx]
   if hips: hips.location.z=[0,-0.03,-0.12,-0.25,-0.3][idx]
 for bone in rig.pose.bones: bone.keyframe_insert(data_path='rotation_euler',frame=frame,group=bone.name)
 if hips: hips.keyframe_insert(data_path='location',frame=frame,group=hips.name)
scene.frame_set(1)
bpy.ops.export_scene.fbx(filepath=dst,use_selection=False,add_leaf_bones=False,bake_anim=True)
print('OMNIFORGE_ANIMATION='+action+'; output='+dst)
'''.replace('__SOURCE__',repr(str(source))).replace('__DEST__',repr(str(target))).replace('__ACTION__',repr(action)).replace('__FPS__',str(fps))
    result = _run(script, 'animate')
    if not target.is_file(): raise RuntimeError('Blender reported success but animation export was not found.')
    return {'ok':True,'action':action,'output':str(target.relative_to(WORKSPACE_DIR)),'bytes':target.stat().st_size,'note':'Procedural starter motion was applied to an existing armature. Inspect in Blender before production use.','blender_output':result['output']}


def auto_rig_humanoid(relative_path: str, export_format: str = 'fbx'):
    """Best-effort humanoid auto-rig: generated skeleton + Blender automatic weights."""
    source = _asset_path(relative_path)
    if export_format not in {'fbx','glb'}: raise ValueError('Export format must be fbx or glb.')
    target = OUTPUT_DIR / f'{source.stem}_autorig_{uuid.uuid4().hex[:8]}.{export_format}'
    script = r"""
import bpy, os
src=__SOURCE__; dst=__DEST__; fmt=__FMT__
if src.lower().endswith('.blend'): bpy.ops.wm.open_mainfile(filepath=src)
else:
 ext=os.path.splitext(src)[1].lower()
 if ext in ('.glb','.gltf'): bpy.ops.import_scene.gltf(filepath=src)
 elif ext=='.fbx': bpy.ops.import_scene.fbx(filepath=src)
 elif ext=='.obj':
  if hasattr(bpy.ops.wm,'obj_import'): bpy.ops.wm.obj_import(filepath=src)
  else: bpy.ops.import_scene.obj(filepath=src)
 elif ext=='.ply': bpy.ops.import_mesh.ply(filepath=src)
 elif ext=='.stl': bpy.ops.import_mesh.stl(filepath=src)
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
if not meshes: raise RuntimeError('No mesh objects found.')
if any(o.type=='ARMATURE' for o in bpy.context.scene.objects): raise RuntimeError('This asset already has a skeleton; use animation/retargeting instead.')
bpy.ops.object.select_all(action='DESELECT')
for o in meshes: o.select_set(True)
bpy.context.view_layer.objects.active=meshes[0]
if len(meshes)>1: bpy.ops.object.join()
mesh=bpy.context.view_layer.objects.active
coords=[mesh.matrix_world @ v.co for v in mesh.data.vertices]
minx=min(v.x for v in coords); maxx=max(v.x for v in coords); miny=min(v.y for v in coords); maxy=max(v.y for v in coords); minz=min(v.z for v in coords); maxz=max(v.z for v in coords)
h=maxz-minz; w=maxx-minx; cx=(minx+maxx)/2; cy=(miny+maxy)/2
if h<0.05 or w>h*1.5: raise RuntimeError('Mesh proportions do not appear humanoid/upright; automatic rigging stopped to protect the asset.')
z=lambda r:minz+h*r
shoulder=max(w*.25,h*.12); hip=max(w*.12,h*.06)
data=bpy.data.armatures.new('OmniForge_Humanoid_Rig'); arm=bpy.data.objects.new('OmniForge_Humanoid_Rig',data); bpy.context.collection.objects.link(arm)
bpy.context.view_layer.objects.active=arm; arm.select_set(True); mesh.select_set(False); bpy.ops.object.mode_set(mode='EDIT')
def b(name,head,tail,parent=None,connect=False):
 x=data.edit_bones.new(name); x.head=head; x.tail=tail
 if parent: x.parent=data.edit_bones.get(parent); x.use_connect=connect
b('root',(cx,cy,z(.02)),(cx,cy,z(.10)))
b('pelvis',(cx,cy,z(.43)),(cx,cy,z(.52)),'root'); b('spine',(cx,cy,z(.50)),(cx,cy,z(.68)),'pelvis'); b('chest',(cx,cy,z(.68)),(cx,cy,z(.79)),'spine',True); b('neck',(cx,cy,z(.79)),(cx,cy,z(.86)),'chest',True); b('head',(cx,cy,z(.86)),(cx,cy,z(.98)),'neck',True)
for side,sgn in [('L',-1),('R',1)]:
 sx=cx+sgn*shoulder; hx=cx+sgn*hip
 b('upper_arm.'+side,(cx,cy,z(.76)),(sx,cy,z(.67)),'chest'); b('forearm.'+side,(sx,cy,z(.67)),(cx+sgn*shoulder*1.65,cy,z(.54)),'upper_arm.'+side,True); b('hand.'+side,(cx+sgn*shoulder*1.65,cy,z(.54)),(cx+sgn*shoulder*1.85,cy,z(.52)),'forearm.'+side,True)
 b('thigh.'+side,(hx,cy,z(.46)),(hx,cy,z(.27)),'pelvis'); b('shin.'+side,(hx,cy,z(.27)),(hx,cy,z(.06)),'thigh.'+side,True); b('foot.'+side,(hx,cy,z(.06)),(hx,cy-h*.07,z(.025)),'shin.'+side,True)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.select_all(action='DESELECT'); mesh.select_set(True); arm.select_set(True); bpy.context.view_layer.objects.active=arm
try: bpy.ops.object.parent_set(type='ARMATURE_AUTO')
except Exception as e: raise RuntimeError('Blender automatic skin weighting failed: '+str(e))
if not mesh.parent or mesh.parent.type!='ARMATURE': raise RuntimeError('Armature binding did not complete.')
if fmt=='glb': bpy.ops.export_scene.gltf(filepath=dst,export_format='GLB',use_selection=False,export_animations=True)
else: bpy.ops.export_scene.fbx(filepath=dst,use_selection=False,add_leaf_bones=False,bake_anim=True)
print('OMNIFORGE_AUTORIG='+dst)
""".replace('__SOURCE__',repr(str(source))).replace('__DEST__',repr(str(target))).replace('__FMT__',repr(export_format))
    result = _run(script, 'autorig')
    if not target.is_file(): raise RuntimeError('Blender completed without producing the rigged export.')
    return {'ok':True,'input':str(source.relative_to(WORKSPACE_DIR)),'output':str(target.relative_to(WORKSPACE_DIR)),'bytes':target.stat().st_size,'method':'Generated approximate humanoid skeleton + Blender automatic weights','limitations':'Best effort for upright human proportions only; inspect skin weights and joint placement before production. Not universal creature rigging or facial rigging.','blender_output':result['output']}

def validate_local_pipeline():
    from .autodetect import detect_tools, version_of
    from .config import TRIPOSR_DIR, TRIPOSR_PYTHON, UNREAL_BUILD_TOOL
    found=detect_tools(); blender=BLENDER_EXE or found.get('blender_exe'); ollama=found.get('ollama_exe'); unreal=UNREAL_BUILD_TOOL or found.get('unreal_build_tool')
    gpu={'torch_available':False,'cuda_available':False,'message':'PyTorch not installed in application environment.'}
    try:
        import torch
        gpu={'torch_available':True,'cuda_available':bool(torch.cuda.is_available()),'cuda_device':torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,'torch_version':torch.__version__}
    except Exception as e: gpu['message']=str(e)
    
    try:
        import cv2, mediapipe
        mocap={'available':True,'opencv_version':cv2.__version__,'mediapipe_version':mediapipe.__version__}
    except Exception as e:
        mocap={'available':False,'note':'Optional local capture packages missing. Install requirements-motion.txt.','error':str(e)}
    return {'free_local_only':True,'motion_capture':mocap,'detected_paths':{'blender':blender,'ollama':ollama,'unreal_build_tool':unreal,'triposr_dir':TRIPOSR_DIR or found.get('triposr_dir')},'versions':{'blender':version_of(blender),'ollama':version_of(ollama),'unreal_build_tool':version_of(unreal,('--help',),10)},'gpu':gpu,'triposr':{'configured':bool(TRIPOSR_DIR and (Path(TRIPOSR_DIR)/'run.py').is_file()),'python':TRIPOSR_PYTHON,'note':'Actual model inference must be run to validate GPU generation.'},'unreal':{'build_tool_detected':bool(unreal),'note':'Compile validation requires a specific .uproject and target configuration.'}}


def smoke_test_blender(export_format: str = 'glb'):
    """Create a temporary cube and verify a real local Blender export."""
    if export_format not in {'glb','fbx'}: raise ValueError('Format must be glb or fbx.')
    target=OUTPUT_DIR/f'omni_smoke_{uuid.uuid4().hex[:8]}.{export_format}'
    script = r"""
import bpy
dst=__DEST__
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_cube_add()
if __FMT__=='glb': bpy.ops.export_scene.gltf(filepath=dst,export_format='GLB')
else: bpy.ops.export_scene.fbx(filepath=dst,use_selection=False,add_leaf_bones=False)
print('OMNIFORGE_SMOKE_EXPORT='+dst)
""".replace('__DEST__',repr(str(target))).replace('__FMT__',repr(export_format))
    result=_run(script,'smoke_export')
    if not target.is_file() or target.stat().st_size < 100: raise RuntimeError('Blender smoke export did not produce a valid-sized file.')
    return {'ok':True,'format':export_format,'output':str(target.relative_to(WORKSPACE_DIR)),'bytes':target.stat().st_size,'blender_output':result['output']}
