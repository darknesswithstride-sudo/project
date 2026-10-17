"""Free local graphics-production toolkit for OmniForge AI.
Generates a reviewed, reproducible Blender environment starter pack and Unreal quality templates.
"""
import json, re, shutil, subprocess, uuid
from pathlib import Path
from .config import BASE_DIR, WORKSPACE_DIR, BLENDER_EXE

OUT = WORKSPACE_DIR / 'omniforge_assets' / 'outputs'
OUT.mkdir(parents=True, exist_ok=True)
PRESETS = {
    'post_apocalyptic': {'title':'Post-apocalyptic overgrown ruins','palette':['moss green','weathered concrete','rusted steel'],'props':['broken concrete slabs','rusted barrels','ruined wall sections','scattered rocks','dead trees'],'lighting':'overcast cinematic with warm practical accents'},
    'dark_forest': {'title':'Cinematic dark forest','palette':['deep forest green','wet bark','cold blue haze'],'props':['tree trunks','rocks','ferns','fallen branches','ground debris'],'lighting':'cool moonlight with volumetric mist'},
    'industrial': {'title':'Abandoned industrial facility','palette':['oxidized steel','oil-dark concrete','warning yellow'],'props':['pipes','steel beams','concrete pillars','industrial tanks','debris'],'lighting':'high-contrast industrial key lights'},
    'desert': {'title':'Photorealistic desert outpost','palette':['sandstone','sun-bleached metal','dust'],'props':['rock formations','ruined walls','scrub vegetation','debris'],'lighting':'hard sun with atmospheric distance haze'},
}

def _slug(s):
    return re.sub(r'[^a-z0-9_-]+','_',s.lower()).strip('_')[:40] or 'environment'

def _blender_script(preset, seed=42):
    spec=PRESETS[preset]
    # Self-contained Blender Python script; intentionally procedural, not a claim of photogrammetry.
    return r'''import bpy, math, random
from mathutils import Vector
random.seed(SEED)
bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
for d in bpy.data.materials: bpy.data.materials.remove(d)
scene=bpy.context.scene
scene.render.engine='CYCLES' if hasattr(bpy.types, 'CyclesRenderSettings') else 'BLENDER_EEVEE_NEXT'
scene.cycles.samples=32 if scene.render.engine=='CYCLES' else 1
scene.render.resolution_x=1920; scene.render.resolution_y=1080; scene.render.resolution_percentage=100
scene.render.image_settings.file_format='PNG'
scene.world.color=(0.025,0.035,0.05)
scene.view_settings.view_transform='AgX' if hasattr(scene.view_settings,'view_transform') else 'Standard'
def mat(name, color, metallic=0.0, rough=0.7, noise_scale=4.0, bump_strength=.18):
 m=bpy.data.materials.new(name); m.diffuse_color=(*color,1); m.use_nodes=True
 n=m.node_tree.nodes; l=m.node_tree.links; bs=n.get('Principled BSDF'); bs.inputs['Base Color'].default_value=(*color,1); bs.inputs['Metallic'].default_value=metallic; bs.inputs['Roughness'].default_value=rough
 tex=n.new('ShaderNodeTexNoise'); tex.inputs['Scale'].default_value=noise_scale; tex.inputs['Detail'].default_value=5; tex.inputs['Roughness'].default_value=.72
 ramp=n.new('ShaderNodeValToRGB'); ramp.color_ramp.elements[0].position=.18; ramp.color_ramp.elements[0].color=(*(c*.42 for c in color),1); ramp.color_ramp.elements[1].position=.82; ramp.color_ramp.elements[1].color=(*(min(1,c*1.22+.025) for c in color),1)
 l.new(tex.outputs['Fac'],ramp.inputs['Fac']); l.new(ramp.outputs['Color'],bs.inputs['Base Color'])
 bump=n.new('ShaderNodeBump'); bump.inputs['Strength'].default_value=bump_strength; bump.inputs['Distance'].default_value=.12; l.new(tex.outputs['Fac'],bump.inputs['Height']); l.new(bump.outputs['Normal'],bs.inputs['Normal'])
 return m
concrete=mat('PBR_Weathered_Concrete',(0.22,.24,.22),0,.92,3.5,.24)
metal=mat('PBR_Rusted_Steel',(.19,.075,.035),.68,.68,6,.2)
soil=mat('PBR_Damp_Gravel',(.075,.095,.07),.05,.94,7,.28)
accent=mat('PBR_Faded_Paint',(.29,.25,.14),.25,.72,5,.12)
def cube(name, loc, scale, material, bevel=.08, rot=(0,0,0)):
 bpy.ops.mesh.primitive_cube_add(size=1, location=loc, rotation=rot); o=bpy.context.object; o.name=name; o.dimensions=scale; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(material)
 if bevel:
  mod=o.modifiers.new('Worn_edges','BEVEL'); mod.width=bevel; mod.segments=2
  o.modifiers.new('Weighted_normals','WEIGHTED_NORMAL')
 return o
def rock(loc, scale):
 bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=2, radius=1, location=loc); o=bpy.context.object; o.name='Procedural_Rock'; o.scale=scale; o.rotation_euler=[random.random()*.8 for _ in range(3)]; bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); o.data.materials.append(concrete)
 for p in o.data.polygons: p.use_smooth=True
 return o
# Large ground slab and layered terrain detail
cube('Terrain_Base',(0,0,-.35),(34,34,.7),soil,.1)
for i in range(65):
 x=random.uniform(-15,15); y=random.uniform(-14,14); s=random.uniform(.15,.9)
 rock((x,y,random.uniform(-.02,.12)),(s*1.5,s,s*.55))
# Ruined wall segments with broken silhouettes
for i in range(9):
 x=-8+i*1.85; h=random.uniform(1.3,3.6); width=random.uniform(1.1,2.1)
 cube('Ruined_Concrete_Wall',(x,5,h/2),(width,.48,h),concrete,.06,(random.uniform(-.05,.05),random.uniform(-.12,.12),random.uniform(-.06,.06)))
 # chipped/broken upper chunks
 if i%2==0: rock((x+width*.28,5,h+.05),(random.uniform(.25,.55),.35,.22))
# rusty industrial props
for i in range(7):
 x=random.uniform(-9,9); y=random.uniform(-6,2)
 bpy.ops.mesh.primitive_cylinder_add(vertices=20, radius=random.uniform(.35,.55), depth=random.uniform(.8,1.4), location=(x,y,.5)); o=bpy.context.object; o.name='Rusted_Barrel'; o.data.materials.append(metal)
 bevel=o.modifiers.new('Rolled_edges','BEVEL'); bevel.width=.045; bevel.segments=2; o.modifiers.new('Weighted_normals','WEIGHTED_NORMAL')
# beams and scattered panels
for i in range(12):
 loc=(random.uniform(-10,10),random.uniform(-8,8),random.uniform(.08,.25)); dims=(random.uniform(.8,2.8),.12,.12)
 cube('Debris_Steel_Beam',loc,dims,metal,.025,tuple(random.uniform(-.4,.4) for _ in range(3)))
# Low-poly dead-tree silhouettes as modular starter placeholders
for x,y in [(-10,-2),(-7,9),(10,6),(12,-4)]:
 cube('Dead_Tree_Trunk',(x,y,2),(.28,.32,4),metal,.06,(.05,.08,random.uniform(-.2,.2)))
 for j in range(4): cube('Dead_Tree_Branch',(x+random.uniform(-.8,.8),y,2.2+j*.35),(random.uniform(.8,1.7),.12,.12),metal,.02,(0,random.uniform(-.7,.7),random.uniform(-.7,.7)))
# Camera, cinematic lighting, and subtle world haze
bpy.ops.object.camera_add(location=(13,-19,8)); cam=bpy.context.object; cam.name='Cinematic_Camera'; direction=Vector((0,1.5,1.1))-cam.location; cam.rotation_euler=direction.to_track_quat('-Z','Y').to_euler(); cam.data.lens=42; scene.camera=cam
bpy.ops.object.light_add(type='AREA', location=(1,-7,12)); key=bpy.context.object; key.name='Large_Soft_Key'; key.data.energy=3800; key.data.shape='DISK'; key.data.size=10; key.rotation_euler=(Vector((0,2,0))-key.location).to_track_quat('-Z','Y').to_euler()
bpy.ops.object.light_add(type='AREA', location=(-8,4,7)); rim=bpy.context.object; rim.name='Cool_Rim'; rim.data.energy=2200; rim.data.color=(.48,.63,1.0); rim.data.size=7; rim.rotation_euler=(Vector((0,1,1))-rim.location).to_track_quat('-Z','Y').to_euler()
# Fog volume in a dedicated cube; low density keeps preview readable
fogmat=bpy.data.materials.new('Atmospheric_Haze'); fogmat.use_nodes=True; nt=fogmat.node_tree; nt.nodes.clear(); out=nt.nodes.new('ShaderNodeOutputMaterial'); vol=nt.nodes.new('ShaderNodeVolumePrincipled'); vol.inputs['Density'].default_value=.012; vol.inputs['Color'].default_value=(.48,.56,.62,1); nt.links.new(vol.outputs['Volume'],out.inputs['Volume'])
bpy.ops.mesh.primitive_cube_add(size=1, location=(0,0,5)); fog=bpy.context.object; fog.name='Atmospheric_Haze_Volume'; fog.dimensions=(40,40,14); bpy.ops.object.transform_apply(location=False,rotation=False,scale=True); fog.data.materials.append(fogmat); fog.display_type='WIRE'
# Save editable project and render a preview image
bpy.ops.wm.save_as_mainfile(filepath=OUT_BLEND)
scene.render.filepath=OUT_RENDER
try: bpy.ops.render.render(write_still=True)
except Exception as e: print('Render skipped or failed:',e)
print('OMNIFORGE_GRAPHICS_PACK_COMPLETE')
'''.replace('SEED', str(int(seed))).replace('OUT_BLEND', repr('OUT_BLEND_PLACEHOLDER')).replace('OUT_RENDER', repr('OUT_RENDER_PLACEHOLDER')).replace("'OUT_BLEND_PLACEHOLDER'", repr('OUT_BLEND_PLACEHOLDER')).replace("'OUT_RENDER_PLACEHOLDER'", repr('OUT_RENDER_PLACEHOLDER'))

def create_pack(preset='post_apocalyptic', project_name='OmniForge AAA Graphics Starter', seed=42, run_blender=False):
    if preset not in PRESETS: raise ValueError(f'Unknown preset. Choose one of: {", ".join(PRESETS)}')
    pack_id=uuid.uuid4().hex[:8]; folder=OUT/f'graphics_lab_{_slug(project_name)}_{pack_id}'; folder.mkdir(parents=True,exist_ok=False)
    blend=folder/'environment.blend'; render=folder/'preview.png'; script=folder/'build_environment.py'
    content=_blender_script(preset,seed).replace('OUT_BLEND_PLACEHOLDER',str(blend).replace('\\','/')).replace('OUT_RENDER_PLACEHOLDER',str(render).replace('\\','/'))
    script.write_text(content,encoding='utf-8')
    ue_dir=folder/'UnrealConfig'; ue_dir.mkdir()
    (ue_dir/'DefaultEngine.ini').write_text('''; OmniForge quality-oriented UE starter settings. Tune to target hardware and engine version.\n[/Script/Engine.RendererSettings]\nr.GenerateMeshDistanceFields=True\nr.DynamicGlobalIlluminationMethod=1\nr.ReflectionMethod=1\nr.Shadow.Virtual.Enable=1\nr.Nanite.ProjectEnabled=True\nr.Lumen.HardwareRayTracing=False\nr.DefaultFeature.AutoExposure.ExtendDefaultLuminanceRange=True\nr.TemporalAA.Upsampling=True\n\n; NOTE: Lumen/Nanite/Virtual Shadow Maps availability and behavior depend on UE version, platform, project settings and hardware.\n''',encoding='utf-8')
    spec=PRESETS[preset]
    brief={'product':'OmniForge AI Graphics Lab','version':'3.3.0','preset':preset,'project_name':project_name,'seed':seed,'free_local_only':True,'paid_api_calls':False,'art_direction':spec,'quality_goals':{'materials':'PBR base color, roughness, metallic and procedural surface variation','lighting':'cinematic key/rim lighting and atmospheric haze','composition':'1080p preview camera','geometry':'procedural blockout and set dressing; replace hero props with authored/scanned assets for production'},'performance_budgets':{'desktop_target':'60 FPS starting target, profile on target hardware','hero_asset_triangles':'10k–100k starting guideline, depends on silhouette and LOD','background_prop_triangles':'500–10k starting guideline','texture_resolution':'1K–2K common props; 2K–4K hero assets when justified','draw_calls':'batch repeated props; use instancing/HLOD where appropriate'},'limitations':['This creates a procedural environment starter, not finished AAA art.','No proprietary game assets or paid services are bundled.','Generated scene and quality settings require visual review and target-hardware profiling.','For true AAA results, combine strong art direction, high-quality authored assets, PBR texture work, animation, VFX, lighting, optimization and QA.']}
    (folder/'graphics_brief.json').write_text(json.dumps(brief,indent=2),encoding='utf-8')
    (folder/'README_GRAPHICS_LAB.md').write_text(f'''# OmniForge AI Graphics Lab starter\n\nPreset: {spec['title']}\n\n## Run locally\n1. Ensure Blender is installed and detected by OmniForge.\n2. In PowerShell, run the generated script with your detected Blender executable:\n   `"PATH_TO_BLENDER" -b --python "{script}"`\n3. The script saves `environment.blend` and attempts a 1920x1080 `preview.png` render. Cycles may take time; GPU support depends on your Blender build and drivers.\n4. Import suitable assets into Unreal Engine and profile on the target PC.\n\n## Included\n- Self-contained procedural Blender environment script.\n- Editable Blender scene output (after execution).\n- Unreal Engine renderer settings starter at `UnrealConfig/DefaultEngine.ini`.\n- Art direction brief and performance-budget guidelines.\n\nThis is a blockout/starter pack. Replace procedural props with original, high-detail assets and author final textures, LODs, collision, animation, VFX and lighting for production quality.\n''',encoding='utf-8')
    result={'ok':True,'pack_id':pack_id,'preset':preset,'folder':str(folder),'files':[str(p) for p in folder.rglob('*') if p.is_file()],'blender_detected':bool(BLENDER_EXE and Path(BLENDER_EXE).is_file()),'blender_path':BLENDER_EXE or None,'blender_run_requested':run_blender,'blender_executed':False,'message':'Starter pack created locally. Run the included Blender script to build the editable scene.'}
    if run_blender:
        if not BLENDER_EXE or not Path(BLENDER_EXE).is_file(): result['blender_error']='Blender not detected. Install Blender or set BLENDER_EXE in .env.'
        else:
            try:
                proc=subprocess.run([BLENDER_EXE,'-b','--python',str(script)],capture_output=True,text=True,timeout=900,shell=False,cwd=str(folder))
                result.update({'blender_executed':True,'blender_returncode':proc.returncode,'blender_stdout':proc.stdout[-5000:],'blender_stderr':proc.stderr[-3000:],'blend_created':blend.exists(),'preview_created':render.exists(),'message':'Blender job finished; inspect return code and output files.'})
            except subprocess.TimeoutExpired: result['blender_error']='Blender exceeded the 15-minute limit.'
            except Exception as e: result['blender_error']=str(e)
    return result

def validate_graphics_pipeline():
    from .autodetect import detect_tools, version_of
    found=detect_tools(); blender=found.get('blender_exe') or BLENDER_EXE
    return {'free_local_only':True,'paid_api_calls':False,'blender':version_of(blender) if blender else {'installed':False,'error':'Blender not detected'},'unreal_build_tool':found.get('unreal_build_tool'),'graphics_presets':list(PRESETS.keys()),'recommended_workflow':['Define art direction and reference board','Generate a procedural blockout','Replace hero assets with original high-quality meshes and PBR textures','Create LODs and collision','Set up lighting, fog, VFX and post-processing','Import into Unreal and profile GPU/CPU/memory','Run visual QA on target hardware'],'aaa_reality_check':'AAA-level results are possible as a long-term production goal, not guaranteed by a single AI model or this starter pack. Quality depends on assets, art direction, engine setup, hardware, iteration and testing.'}
