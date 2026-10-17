import unittest
from pathlib import Path
from app.production_pipeline import _script, _safe_input, pipeline_status

class ProductionPipelineTests(unittest.TestCase):
    def test_generated_blender_script_compiles(self):
        source=_script(Path('/tmp/sample.glb'),Path('/tmp/out'),12000,3,2048)
        compile(source,'generated_pipeline.py','exec')
        self.assertIn("asset_LOD", source)
        self.assertIn("smart_project", source)
        self.assertIn("asset_report.json", source)
        self.assertIn("bake_map", source)
        self.assertIn("ShaderNodeBump", source)
        self.assertIn("make_high_detail_source", source)
        self.assertIn("bake_high_detail_normal", source)
        self.assertIn("selected_to_active", source)
        self.assertIn("skin_pores", source)
        self.assertIn("bake_ao_map", source)
        self.assertIn("convex_hull", source)
        self.assertIn("collision_meshes.fbx", source)
        self.assertIn("topology_checks", source)

    def test_status_free_local(self):
        status=pipeline_status()
        self.assertTrue(status['free_local_only'])
        self.assertFalse(status['paid_api_calls'])
        self.assertIn('.glb',status['supported_inputs'])
        self.assertTrue(any('normal map baking' in feature for feature in status['features']))
        self.assertTrue(any('high-poly procedural geometry refinement' in feature for feature in status['features']))
        self.assertTrue(any('convex-hull collision' in feature for feature in status['features']))

    def test_rejects_outside_workspace(self):
        with self.assertRaises(ValueError): _safe_input('/etc/passwd')

    def test_detail_profiles_are_embedded(self):
        for profile in ('organic','fabric','hard_surface','damaged','skin_pores','clothing'):
            source=_script(Path('/tmp/sample.glb'),Path('/tmp/out'),12000,3,1024,profile,1.2)
            compile(source,'generated_pipeline.py','exec')
            self.assertIn('DETAIL_PROFILE='+repr(profile),source)

if __name__ == '__main__': unittest.main()
