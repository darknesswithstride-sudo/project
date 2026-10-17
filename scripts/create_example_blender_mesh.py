# Example Blender script: creates a procedural low-poly test asset and saves a .blend file.
import bpy
bpy.ops.object.select_all(action="SELECT"); bpy.ops.object.delete(use_global=False)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1, location=(0,0,1))
obj=bpy.context.object; obj.name="OmniForge_Procedural_TestMesh"
mat=bpy.data.materials.new("OmniForge_TestMaterial"); mat.diffuse_color=(0.12,0.38,0.82,1)
obj.data.materials.append(mat)
bpy.ops.wm.save_as_mainfile(filepath="//OmniForge_Procedural_TestMesh.blend")
