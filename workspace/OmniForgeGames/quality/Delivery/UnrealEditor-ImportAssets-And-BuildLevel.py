import unreal, json, os, math
PROJECT = unreal.Paths.project_dir()
ROOT = os.path.join(PROJECT, "Content", "OmniForgeImported")
DEST = "/Game/OmniForgeImported"
LEVEL_NAME = "MainSurvivalLevel"
LOG = os.path.join(PROJECT, "Delivery", "editor_pipeline_result.json")
os.makedirs(os.path.dirname(LOG), exist_ok=True)
result={"imports":[],"level_created":False,"spawned_actors":0,"errors":[],"engine_ran":True}
try:
    tasks=[]
    for base, dirs, files in os.walk(ROOT):
        for fn in files:
            ext=os.path.splitext(fn)[1].lower()
            if ext not in (".fbx", ".obj", ".glb", ".gltf", ".png", ".jpg", ".jpeg", ".tga", ".wav", ".ogg", ".mp3"): continue
            task=unreal.AssetImportTask(); task.filename=os.path.join(base,fn); task.destination_path=DEST
            task.automated=True; task.save=True; task.replace_existing=True; task.replace_existing_settings=False
            tasks.append(task)
    if tasks:
        unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks(tasks)
        for t in tasks: result["imports"].append({"source":t.filename,"imported":list(t.imported_object_paths)})
    level_path="/Game/OmniForgeLevels/"+LEVEL_NAME
    unreal.EditorAssetLibrary.make_directory("/Game/OmniForgeLevels")
    unreal.EditorLevelLibrary.new_level(level_path)
    # Large ground plane and survival route markers, all editable actors in a real UE level.
    cube=unreal.load_asset("/Engine/BasicShapes/Cube.Cube")
    if cube:
        def spawn_cube(label, loc, scale, color=None):
            actor=unreal.EditorLevelLibrary.spawn_actor_from_object(cube, unreal.Vector(*loc), unreal.Rotator(0,0,0))
            if actor:
                actor.set_actor_label(label); actor.set_actor_scale3d(unreal.Vector(*scale)); result["spawned_actors"]+=1
                if color:
                    try:
                        mat=unreal.MaterialInstanceDynamic.create(unreal.load_asset("/Engine/BasicShapes/BasicShapeMaterial.BasicShapeMaterial"), actor)
                        mat.set_vector_parameter_value("Color",unreal.LinearColor(*color)); actor.set_material(0,mat)
                    except Exception: pass
                return actor
        spawn_cube("OF_Level_Ground",(0,0,-80),(80,80,1))
        # Grid of cover, salvage points and navigation landmarks. Labels support later AI/editor review.
        for i in range(6):
            x=(i-2.5)*850
            spawn_cube("OF_Cover_Barricade_%02d"%i,(x,750,60),(2.4,.25,1.2))
            spawn_cube("OF_Salvage_Landmark_%02d"%i,(x,-550,90),(.6,.6,1.8))
        for i in range(4):
            spawn_cube("OF_Route_Marker_%02d"%i,(-900+i*600,0,20),(.18, .18, .18))
    unreal.EditorLevelLibrary.save_current_level()
    result["level_created"]=True; result["level_path"]=level_path
except Exception as e:
    result["errors"].append(str(e))
with open(LOG,"w",encoding="utf-8") as f: json.dump(result,f,indent=2)
print("OMNIFORGE_DELIVERY_RESULT="+json.dumps(result))
