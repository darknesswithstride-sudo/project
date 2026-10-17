"""Free local asset production pipeline: inspect, UV, material fallback, LOD exports, and Unreal import helper."""
import json, re, subprocess, uuid
from pathlib import Path
from .config import BASE_DIR, WORKSPACE_DIR, BLENDER_EXE
from .autodetect import detect_tools

PIPELINE_ROOT = (WORKSPACE_DIR / 'omniforge_assets' / 'production').resolve()
PIPELINE_ROOT.mkdir(parents=True, exist_ok=True)
SUPPORTED = {'.glb', '.gltf', '.fbx', '.obj', '.ply', '.stl', '.blend'}

def _safe_input(relative_path):
    raw = Path(relative_path)
    path = raw.resolve() if raw.is_absolute() else (WORKSPACE_DIR / raw).resolve()
    if not path.is_relative_to(WORKSPACE_DIR.resolve()):
        raise ValueError('Input model must be inside the OmniForge workspace.')
    if not path.is_file(): raise ValueError('Input model file does not exist.')
    if path.suffix.lower() not in SUPPORTED: raise ValueError(f'Unsupported model format: {path.suffix}')
    return path

def _script(input_path, output_dir, target_faces, lod_count, bake_size, detail_profile="organic", detail_intensity=1.0):
    # Create a self-contained Blender background job for maps, detail, collision, LODs and validation.
    template = r'''import bpy, bmesh, json, math, os
from pathlib import Path
INPUT=Path(__INPUT__); OUT=Path(__OUT__); TARGET_FACES=__TARGET__; LOD_COUNT=__LODS__; BAKE_SIZE=__BAKE__; DETAIL_PROFILE=__PROFILE__; DETAIL_INTENSITY=__INTENSITY__
OUT.mkdir(parents=True,exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
suffix=INPUT.suffix.lower()
if suffix=='.blend': bpy.ops.wm.open_mainfile(filepath=str(INPUT))
elif suffix in {'.glb','.gltf'}: bpy.ops.import_scene.gltf(filepath=str(INPUT))
elif suffix=='.fbx': bpy.ops.import_scene.fbx(filepath=str(INPUT))
elif suffix=='.obj':
    if hasattr(bpy.ops.wm,'obj_import'): bpy.ops.wm.obj_import(filepath=str(INPUT))
    else: bpy.ops.import_scene.obj(filepath=str(INPUT))
elif suffix=='.ply': bpy.ops.import_mesh.ply(filepath=str(INPUT))
elif suffix=='.stl':
    if hasattr(bpy.ops.wm,'stl_import'): bpy.ops.wm.stl_import(filepath=str(INPUT))
    else: bpy.ops.import_mesh.stl(filepath=str(INPUT))
meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
if not meshes: raise RuntimeError('No mesh objects were imported.')
# Use Cycles for baking. GPU is opportunistic; CPU fallback keeps the workflow free and broadly compatible.
bpy.context.scene.render.engine='CYCLES'
bpy.context.scene.cycles.samples=16
try: bpy.context.scene.cycles.device='CPU'
except Exception: pass
bpy.context.scene.render.bake.margin=8
bpy.context.scene.render.bake.use_clear=True

def active_only(obj):
    bpy.ops.object.select_all(action='DESELECT'); obj.select_set(True); bpy.context.view_layer.objects.active=obj

def stats(objects):
    return {'mesh_objects':len(objects),'vertices':sum(len(o.data.vertices) for o in objects),'faces':sum(len(o.data.polygons) for o in objects),'materials':sorted({m.name for o in objects for m in o.data.materials if m}),'uv_mapped_objects':sum(bool(o.data.uv_layers) for o in objects)}

def principled(mat):
    if not mat.use_nodes: mat.use_nodes=True
    return next((n for n in mat.node_tree.nodes if n.type=='BSDF_PRINCIPLED'),None)

def add_material_and_detail(obj):
    if not obj.data.materials:
        m=bpy.data.materials.new(obj.name+'_OmniForge_PBR'); m.use_nodes=True; obj.data.materials.append(m)
    for mat in obj.data.materials:
        if mat is None: continue
        mat.use_nodes=True; bs=principled(mat)
        if not bs: continue
        nt=mat.node_tree; nodes=nt.nodes; links=nt.links
        # Add subtle procedural micro-surface relief when no normal input already exists.
        if not nodes.get('OmniForge_MicroBump'):
            original=list(bs.inputs['Normal'].links)
            noise=nodes.new('ShaderNodeTexNoise'); noise.name='OmniForge_MicroDetail'; noise.inputs['Scale'].default_value=180.0; noise.inputs['Detail'].default_value=4.0; noise.inputs['Roughness'].default_value=.72
            bump=nodes.new('ShaderNodeBump'); bump.name='OmniForge_MicroBump'; bump.inputs['Strength'].default_value=.16; bump.inputs['Distance'].default_value=.012
            for link in original:
                links.new(link.from_socket,bump.inputs['Normal']); links.remove(link)
            links.new(noise.outputs['Fac'],bump.inputs['Height']); links.new(bump.outputs['Normal'],bs.inputs['Normal'])
        if 'Roughness' in bs.inputs and not bs.inputs['Roughness'].is_linked:
            bs.inputs['Roughness'].default_value=.72

def ensure_uv(obj):
    if obj.data.uv_layers: return
    active_only(obj)
    try:
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.uv.smart_project(island_margin=.012); bpy.ops.object.mode_set(mode='OBJECT')
    except Exception:
        try: bpy.ops.object.mode_set(mode='OBJECT')
        except Exception: pass
    if not obj.data.uv_layers:
        raise RuntimeError('UV generation failed for '+obj.name)

def bake_map(obj, map_name, size, bake_type, socket_name=None):
    image=bpy.data.images.new(obj.name[:40]+'_'+map_name, width=size, height=size, alpha=(map_name=='basecolor'), float_buffer=False)
    if map_name in {'roughness','metallic','normal'}:
        try: image.colorspace_settings.name='Non-Color'
        except Exception: pass
    mats=[m for m in obj.data.materials if m]
    backups=[]
    for mat in mats:
        mat.use_nodes=True; nt=mat.node_tree; nodes=nt.nodes; links=nt.links
        saved=[(l.from_node,l.from_socket.name,l.to_node,l.to_socket.name) for l in list(links)]
        backups.append((nt,saved))
        # A dedicated active image node is required by Blender's bake operator.
        for n in list(nodes):
            if n.get('OmniForgeTempEmission'): nodes.remove(n)
        tex=nodes.new('ShaderNodeTexImage'); tex.name='OmniForge_BakeTarget_'+map_name; tex.image=image; tex.select=True
        for n in nodes: n.select=False
        tex.select=True; nodes.active=tex
        if map_name!='normal':
            bs=principled(mat); out=next((n for n in nodes if n.type=='OUTPUT_MATERIAL'),None)
            source=bs.inputs.get(socket_name) if bs else None
            emission=nodes.new('ShaderNodeEmission'); emission['OmniForgeTempEmission']=True
            if source and source.is_linked:
                links.new(source.links[0].from_socket, emission.inputs['Color'])
            elif source:
                val=source.default_value
                try: emission.inputs['Color'].default_value=val if len(val)>1 else (val,val,val,1)
                except TypeError: emission.inputs['Color'].default_value=(val,val,val,1)
            if out: links.new(emission.outputs[0],out.inputs['Surface'])
    active_only(obj)
    scene=bpy.context.scene
    if map_name=='normal':
        scene.render.bake.normal_space='TANGENT'
        bpy.ops.object.bake(type='NORMAL')
    else:
        bpy.ops.object.bake(type='EMIT')
    image.filepath_raw=str(OUT/(obj.name[:40]+'_'+map_name+'.png')); image.file_format='PNG'; image.save()
    # Restore the original shader graphs while keeping the bake target node available for diagnostics.
    for nt,saved in backups:
        for l in list(nt.links): nt.links.remove(l)
        for n in list(nt.nodes):
            if n.get('OmniForgeTempEmission'): nt.nodes.remove(n)
        for fn,fs,tn,ts in saved:
            try: nt.links.new(fn.outputs[fs],tn.inputs[ts])
            except Exception: pass
    return image

def make_high_detail_source(low, profile):
    """Create a temporary subdivided/displaced source for selected-to-active normal baking."""
    high=low.copy(); high.data=low.data.copy(); high.name='OmniForge_HighDetail_'+low.name
    bpy.context.scene.collection.objects.link(high)
    # Keep temporary high-poly density bounded so local machines do not explode memory.
    faces=len(high.data.polygons)
    levels=2 if faces<2500 else (1 if faces<18000 else 0)
    if levels:
        sub=high.modifiers.new('OmniForge_HighDetail_Subdivision','SUBSURF'); sub.subdivision_type='CATMULL_CLARK'; sub.levels=levels; sub.render_levels=levels
        active_only(high); bpy.ops.object.modifier_apply(modifier=sub.name)
    dims=high.dimensions
    scale=max(float(dims.x),float(dims.y),float(dims.z),0.01)
    settings={
      'organic': [('CLOUDS',0.0022,2.2),('DISTORTED_NOISE',0.0008,5.0)],
      'fabric': [('CLOUDS',0.0010,7.0),('DISTORTED_NOISE',0.00045,12.0)],
      'hard_surface': [('CLOUDS',0.00025,35.0)],
      'damaged': [('CLOUDS',0.0028,3.0),('DISTORTED_NOISE',0.0015,9.0),('CLOUDS',0.0006,28.0)],
      'skin_pores': [('CLOUDS',0.00045,95.0),('DISTORTED_NOISE',0.00018,140.0)],
      'clothing': [('CLOUDS',0.0014,11.0),('DISTORTED_NOISE',0.0006,19.0)]
    }.get(profile, [('CLOUDS',0.0015,4.0),('DISTORTED_NOISE',0.0005,15.0)])
    for index,(tex_type,strength,noise_scale) in enumerate(settings):
        tex=bpy.data.textures.new('OmniForge_'+profile+'_detail_'+str(index),type=tex_type)
        try: tex.noise_scale=max(0.001,1.0/noise_scale)
        except Exception: pass
        mod=high.modifiers.new('OmniForge_GeometryDetail_'+str(index),'DISPLACE'); mod.texture=tex
        mod.strength=scale*strength*max(0.0,min(2.0,DETAIL_INTENSITY)); mod.mid_level=0.5
        active_only(high)
        try: bpy.ops.object.modifier_apply(modifier=mod.name)
        except Exception: pass
    high.data.update()
    return high

def bake_high_detail_normal(low, high, size):
    image=bpy.data.images.new(low.name[:36]+'_normal',width=size,height=size,alpha=False,float_buffer=False)
    try: image.colorspace_settings.name='Non-Color'
    except Exception: pass
    for mat in [m for m in low.data.materials if m]:
        mat.use_nodes=True; nodes=mat.node_tree.nodes
        for node in nodes: node.select=False
        tex=nodes.new('ShaderNodeTexImage'); tex.name='OmniForge_BakeTarget_highdetail_normal'; tex.image=image; tex.select=True; nodes.active=tex
    scene=bpy.context.scene; scene.render.bake.use_selected_to_active=True
    try:
        scene.render.bake.normal_space='TANGENT'; scene.render.bake.use_cage=False
        scene.render.bake.cage_extrusion=max(float(max(low.dimensions))*0.01,0.001)
        bpy.ops.object.select_all(action='DESELECT'); high.select_set(True); low.select_set(True); bpy.context.view_layer.objects.active=low
        bpy.ops.object.bake(type='NORMAL')
        image.filepath_raw=str(OUT/(low.name[:40]+'_normal.png')); image.file_format='PNG'; image.save()
    finally:
        scene.render.bake.use_selected_to_active=False
        try: bpy.data.objects.remove(high,do_unlink=True)
        except Exception: pass
    return image

def bake_ao_map(obj,size):
    image=bpy.data.images.new(obj.name[:36]+'_ao',width=size,height=size,alpha=False,float_buffer=False)
    try: image.colorspace_settings.name='Non-Color'
    except Exception: pass
    for mat in [m for m in obj.data.materials if m]:
        tex=mat.node_tree.nodes.new('ShaderNodeTexImage'); tex.name='OmniForge_BakeTarget_ao'; tex.image=image
        for n in mat.node_tree.nodes: n.select=False
        tex.select=True; mat.node_tree.nodes.active=tex
    active_only(obj); bpy.context.scene.render.bake.use_selected_to_active=False
    bpy.ops.object.bake(type='AO')
    image.filepath_raw=str(OUT/(obj.name[:40]+'_ao.png')); image.file_format='PNG'; image.save()
    return image

def apply_baked_maps(obj, maps):
    for mat in [m for m in obj.data.materials if m]:
        nt=mat.node_tree; nodes=nt.nodes; links=nt.links; bs=principled(mat)
        if not bs: continue
        def texnode(img,label):
            n=nodes.new('ShaderNodeTexImage'); n.image=img; n.label='OmniForge baked '+label; n.name='OmniForge_Baked_'+label; n.interpolation='Linear'; return n
        bc=texnode(maps['basecolor'],'BaseColor'); links.new(bc.outputs['Color'],bs.inputs['Base Color'])
        rough=texnode(maps['roughness'],'Roughness'); links.new(rough.outputs['Color'],bs.inputs['Roughness'])
        metal=texnode(maps['metallic'],'Metallic'); links.new(metal.outputs['Color'],bs.inputs['Metallic'])
        norm=texnode(maps['normal'],'Normal'); nm=nodes.new('ShaderNodeNormalMap'); nm.label='OmniForge tangent-space normal'; links.new(norm.outputs['Color'],nm.inputs['Color']); links.new(nm.outputs['Normal'],bs.inputs['Normal'])
        if 'ao' in maps:
            ao=texnode(maps['ao'],'AO'); ao.image.colorspace_settings.name='Non-Color'

def export_selection(path, fmt, objects=None):
    bpy.ops.object.select_all(action='DESELECT')
    selected=list(objects) if objects is not None else [o for o in bpy.context.scene.objects if o.type=='MESH' and o.get('OmniForgeExport',False)]
    for o in selected: o.select_set(True)
    if not selected: raise RuntimeError('No export objects selected for '+str(path))
    bpy.context.view_layer.objects.active=selected[0]
    if fmt=='glb': bpy.ops.export_scene.gltf(filepath=str(path),export_format='GLB',use_selection=True,export_apply=True)
    else: bpy.ops.export_scene.fbx(filepath=str(path),use_selection=True,apply_scale_options='FBX_SCALE_ALL',add_leaf_bones=False,bake_anim=False)
    for o in selected: o.select_set(False)
    return selected

report={'source':str(INPUT),'warnings':[],'detail_generation':{'method':'bounded high-poly subdivision plus profile-driven procedural displacement; selected-to-active normal bake','profile':DETAIL_PROFILE,'intensity':DETAIL_INTENSITY,'high_poly_detail_bake':True,'neural_model_used':False,'note':'This creates geometry-derived surface detail locally; it is not a learned anatomy reconstruction model.'},'texture_maps':{},'collision':{},'lods':[],'validation':{},'bake_size':BAKE_SIZE}
# Normalize, create UVs, and add material detail. Apply only safe transforms; never destructively sculpt the source.
for o in meshes:
    active_only(o)
    try: bpy.ops.object.transform_apply(location=False,rotation=True,scale=True)
    except Exception: pass
    ensure_uv(o); add_material_and_detail(o)
    for poly in o.data.polygons: poly.use_smooth=True
# Bake maps per mesh; generated shader micro-relief is represented in the normal texture.
baked_by_object={}
for obj in meshes:
    try:
        maps={}
        maps['basecolor']=bake_map(obj,'basecolor',BAKE_SIZE,'EMIT','Base Color')
        maps['roughness']=bake_map(obj,'roughness',BAKE_SIZE,'EMIT','Roughness')
        maps['metallic']=bake_map(obj,'metallic',BAKE_SIZE,'EMIT','Metallic')
        high=make_high_detail_source(obj,DETAIL_PROFILE)
        maps['normal']=bake_high_detail_normal(obj,high,BAKE_SIZE)
        try: maps['ao']=bake_ao_map(obj,BAKE_SIZE)
        except Exception as ao_exc: report['warnings'].append('AO baking failed for '+obj.name+': '+str(ao_exc))
        apply_baked_maps(obj,maps); baked_by_object[obj.name]=maps
        report['texture_maps'][obj.name]={k:str(OUT/(obj.name[:40]+'_'+k+'.png')) for k in maps}
    except Exception as exc:
        report['warnings'].append('Texture baking failed for '+obj.name+': '+str(exc))
# Build convex hull collision proxies before LOD export. UCX objects are included in each matching FBX so Unreal can associate them during import.
base_meshes=[o for o in bpy.context.scene.objects if o.type=='MESH']
collision_col=bpy.data.collections.new('OmniForge_Collision'); bpy.context.scene.collection.children.link(collision_col); collision_sources={}
for src in base_meshes:
    proxy=src.copy(); proxy.data=src.data.copy(); proxy.name='UCX_'+src.name[:40]+'_LOD0_00'; collision_col.objects.link(proxy); active_only(proxy)
    try:
        bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT'); bpy.ops.mesh.convex_hull(); bpy.ops.object.mode_set(mode='OBJECT')
        if len(proxy.data.polygons)>64:
            mod=proxy.modifiers.new('OmniForge_CollisionReduce','DECIMATE'); mod.ratio=max(.05,min(1,64/len(proxy.data.polygons))); bpy.ops.object.modifier_apply(modifier=mod.name)
        proxy['OmniForgeExport']=True; collision_sources[src.name]=proxy
    except Exception as exc:
        report['warnings'].append('Collision hull generation failed for '+src.name+': '+str(exc))
        try: bpy.ops.object.mode_set(mode='OBJECT')
        except Exception: pass
for level in range(LOD_COUNT+1):
    col=bpy.data.collections.new('OmniForge_LOD'+str(level)); bpy.context.scene.collection.children.link(col); dupes=[]
    collision_dupes=[]
    for src in base_meshes:
        dup=src.copy(); dup.data=src.data.copy(); dup.name=src.name+'_LOD'+str(level); dup['OmniForgeExport']=True; col.objects.link(dup); dupes.append(dup)
        if level>0 and len(dup.data.polygons)>TARGET_FACES:
            target=max(100,int(TARGET_FACES*(.5**(level-1))))
            ratio=min(.98,max(.02,target/max(1,len(dup.data.polygons))))
            mod=dup.modifiers.new('OmniForge_Decimate_LOD','DECIMATE'); mod.ratio=ratio; active_only(dup)
            try: bpy.ops.object.modifier_apply(modifier=mod.name)
            except Exception as exc: report['warnings'].append('LOD modifier issue on '+dup.name+': '+str(exc))
        base_collision=collision_sources.get(src.name)
        if base_collision:
            cp=base_collision.copy(); cp.data=base_collision.data.copy(); cp.name='UCX_'+src.name[:40]+'_LOD'+str(level)+'_00'; cp['OmniForgeExport']=True; col.objects.link(cp); collision_dupes.append(cp)
    glb=OUT/f'asset_LOD{level}.glb'; fbx=OUT/f'asset_LOD{level}.fbx'
    export_selection(glb,'glb',dupes)
    export_selection(fbx,'fbx',dupes+collision_dupes)
    report['lods'].append({'level':level,'glb':glb.name,'fbx':fbx.name,'stats':stats(dupes),'collision_hulls_in_fbx':len(collision_dupes)})
    for o in dupes+collision_dupes: bpy.data.objects.remove(o,do_unlink=True)
    bpy.data.collections.remove(col)
collision_objects=list(collision_sources.values())
if collision_objects:
    try:
        export_selection(OUT/'collision_meshes.fbx','fbx',collision_objects)
        report['collision']={'file':'collision_meshes.fbx','hulls':len(collision_objects),'names':[o.name for o in collision_objects],'method':'per-mesh convex hull, decimated to approximately 64 faces max; also embedded by UCX naming in each LOD FBX','requires_visual_review':True}
    except Exception as exc: report['warnings'].append('Collision export failed: '+str(exc))
# Validate topology, maps, LODs, and collisions; no automated check can guarantee visual correctness in every engine.
source_stats=stats(base_meshes)
manifold={}
for obj in base_meshes:
    bm=bmesh.new(); bm.from_mesh(obj.data); bm.edges.ensure_lookup_table(); boundary=sum(1 for e in bm.edges if not e.is_manifold); bm.free(); manifold[obj.name]={'non_manifold_edges':boundary,'watertight_candidate':boundary==0}
map_paths=[Path(p) for maps in report['texture_maps'].values() for p in maps.values()]
report['source_stats']=source_stats; report['topology_checks']=manifold
report['validation']={'has_meshes':bool(base_meshes),'nonzero_faces':source_stats['faces']>0,'uvs_present':all(o.data.uv_layers for o in base_meshes),'all_requested_lods_exported':len(report['lods'])==LOD_COUNT+1 and all((OUT/x['glb']).is_file() and (OUT/x['fbx']).is_file() for x in report['lods']),'texture_map_files_exist':bool(map_paths) and all(p.is_file() for p in map_paths),'collision_file_exists':(OUT/'collision_meshes.fbx').is_file(),'visual_review_required':True}
if not report['validation']['texture_map_files_exist']: report['warnings'].append('Some texture maps were not generated; inspect Blender logs and the per-mesh warnings.')
(OUT/'asset_report.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'processed_asset.blend'))
print('OMNIFORGE_PIPELINE_RESULT='+json.dumps(report))
'''
    return template.replace('__INPUT__',repr(str(input_path).replace('\\','/'))).replace('__OUT__',repr(str(output_dir).replace('\\','/'))).replace('__TARGET__',str(int(target_faces))).replace('__LODS__',str(int(lod_count))).replace('__BAKE__',str(int(bake_size))).replace('__PROFILE__',repr(str(detail_profile))).replace('__INTENSITY__',str(float(detail_intensity)))

def create_unreal_import_script(output_dir):
    # Intended to be run inside Unreal Editor with its Python plugin enabled.
    content = r'''"""Run inside Unreal Editor with Editor Scripting/Python enabled. Imports FBX LOD assets that contain UCX collision hulls."""
import os, json, unreal
SOURCE_DIR = r"SOURCE_DIR_PLACEHOLDER"
DEST_PATH = "/Game/OmniForge/Generated"
os.makedirs(SOURCE_DIR, exist_ok=True)
results=[]
for name in sorted(os.listdir(SOURCE_DIR)):
    if not name.lower().endswith('.fbx') or '_LOD' not in name or name.lower()=='collision_meshes.fbx': continue
    task=unreal.AssetImportTask(); task.filename=os.path.join(SOURCE_DIR,name); task.destination_path=DEST_PATH
    task.automated=True; task.save=True; task.replace_existing=True; task.replace_existing_settings=True
    task.options=unreal.FbxImportUI(); task.options.import_mesh=True; task.options.import_as_skeletal=False
    task.options.import_materials=True; task.options.import_textures=True
    try:
        task.options.import_collision=True
    except Exception: pass
    try:
        task.options.static_mesh_import_data.auto_generate_collision=False
        task.options.static_mesh_import_data.import_mesh_lods=True
    except Exception: pass
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])
    for asset_path in list(task.imported_object_paths):
        asset=unreal.load_asset(asset_path); check={'asset_path':asset_path,'loaded':asset is not None}
        if asset and isinstance(asset,unreal.StaticMesh):
            check['lod_count']=asset.get_num_lods(); check['material_slots']=len(asset.get_editor_property('static_materials'))
            try:
                body=asset.get_editor_property('body_setup'); agg=body.get_editor_property('agg_geom') if body else None
                check['collision_hulls']=len(agg.get_editor_property('convex_elems')) if agg else 0
            except Exception: check['collision_hulls']='could_not_inspect'
            check['warnings']=[]
            if check['material_slots']==0: check['warnings'].append('No material slots detected.')
            if check['collision_hulls']==0: check['warnings'].append('No convex collision found; verify UCX hull association in Static Mesh Editor.')
        results.append({'source_file':name,**check})
report_path=os.path.join(SOURCE_DIR,'unreal_import_report.json')
with open(report_path,'w',encoding='utf-8') as f: json.dump({'destination':DEST_PATH,'results':results,'note':'Separate LOD FBXs may import as separate assets depending on Unreal version; verify desired LOD grouping in Static Mesh Editor.'},f,indent=2)
print('OmniForge import and validation complete:',report_path)
'''.replace('SOURCE_DIR_PLACEHOLDER', str(output_dir).replace('\\','/'))
    path = output_dir / 'unreal_import_assets.py'; path.write_text(content,encoding='utf-8'); return path

def run_pipeline(relative_path, target_faces=12000, lod_count=3, bake_size=2048, run_blender=True, detail_profile='organic', detail_intensity=1.0):
    source=_safe_input(relative_path)
    detail_profile=str(detail_profile).lower().strip()
    if detail_profile not in {'organic','fabric','hard_surface','damaged','skin_pores','clothing'}: raise ValueError('detail_profile must be organic, fabric, hard_surface, damaged, skin_pores, or clothing.')
    detail_intensity=max(0.0,min(2.0,float(detail_intensity)))
    target_faces=max(100,min(1_000_000,int(target_faces))); lod_count=max(1,min(4,int(lod_count))); bake_size=min(4096,max(512,int(bake_size)))
    detected=detect_tools(); blender=BLENDER_EXE or detected.get('blender_exe')
    job=PIPELINE_ROOT / (re.sub(r'[^a-zA-Z0-9_-]+','_',source.stem)[:45]+'_'+uuid.uuid4().hex[:8]); job.mkdir(parents=True)
    script=job/'build_asset_pipeline.py'; script.write_text(_script(source,job,target_faces,lod_count,bake_size,detail_profile,detail_intensity),encoding='utf-8')
    unreal_script=create_unreal_import_script(job)
    manifest={'app':'OmniForge AI','pipeline_version':'3.6','source':str(source),'output_dir':str(job),'free_local_only':True,'paid_api_calls':False,'target_faces_per_lod_mesh':target_faces,'lod_count':lod_count,'requested_texture_bake_size':bake_size,'texture_baking_requested':True,'detail_profile':detail_profile,'detail_intensity':detail_intensity,'high_detail_geometry_bake_requested':True,'ambient_occlusion_bake_requested':True,'notes':['Creates a bounded temporary high-poly source using profile-driven displacement and bakes its tangent-space normal map onto the source mesh; also attempts AO bake.','Collision proxies are per-mesh convex hulls with Unreal UCX naming; verify gameplay fit and collision complexity.','Procedural geometry refinement is deterministic local detail, not semantic AI reconstruction of anatomy, garments, or designed damage.','Unreal import helper must be run in Unreal Editor with Python Editor Script Plugin enabled; verify imported materials and collision in-editor.']}
    (job/'pipeline_manifest.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    result={'ok':True,'source':str(source),'output_dir':str(job),'blender_path':blender,'blender_detected':bool(blender and Path(blender).is_file()),'blender_run_requested':run_blender,'files':[str(script),str(unreal_script),str(job/'pipeline_manifest.json')],'blender_executed':False,'free_local_only':True}
    if run_blender:
        if not blender or not Path(blender).is_file(): result.update({'ok':False,'error':'Blender was not detected. Install Blender or set BLENDER_EXE.'}); return result
        try:
            proc=subprocess.run([str(blender),'-b','--python',str(script)],capture_output=True,text=True,timeout=1200,shell=False,cwd=str(job))
            result.update({'blender_executed':True,'returncode':proc.returncode,'stdout':proc.stdout[-7000:],'stderr':proc.stderr[-4000:],'success':proc.returncode==0 and (job/'asset_report.json').is_file(),'report_path':str(job/'asset_report.json') if (job/'asset_report.json').is_file() else None})
            if (job/'asset_report.json').is_file(): result['report']=json.loads((job/'asset_report.json').read_text(encoding='utf-8'))
        except subprocess.TimeoutExpired: result.update({'ok':False,'error':'Blender exceeded the 20-minute processing limit.'})
        except Exception as e: result.update({'ok':False,'error':str(e)})
    return result

def pipeline_status():
    found=detect_tools(); blender=BLENDER_EXE or found.get('blender_exe')
    return {'free_local_only':True,'paid_api_calls':False,'blender_detected':bool(blender and Path(blender).is_file()),'blender_path':blender,'supported_inputs':sorted(SUPPORTED),'features':['UV generation if missing','profile-driven high-poly procedural geometry refinement','selected-to-active high-detail tangent normal baking','base-color, roughness, metallic, ambient-occlusion, and tangent-space normal map baking','per-mesh convex-hull collision proxies with UCX names','LOD0 plus up to four decimated LOD exports','GLB and FBX exports per LOD','topology, UV, texture-file, collision, and export validation report','Unreal Editor Python import helper'],'limitations':['Profile-driven displacement creates baked surface relief; it does not infer exact anatomy, garment seams, or intentional damage semantically from an image or text prompt.','Generated LODs, texture maps, and convex collision proxies require visual review.','Unreal import script requires Editor Python support and must be run in Unreal.','Blender-version differences or unsupported shader nodes can cause an individual bake to fail; failures are reported.']}
