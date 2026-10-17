import json
import unittest
from pathlib import Path
from app.graphics_lab import PRESETS, _blender_script, create_pack

class GraphicsLabTests(unittest.TestCase):
    def test_expected_presets(self):
        self.assertTrue({'post_apocalyptic','dark_forest','industrial','desert'}.issubset(PRESETS))

    def test_blender_script_syntax(self):
        source = _blender_script('dark_forest', 12)
        compile(source, 'generated_blender.py', 'exec')
        self.assertIn('PBR_Weathered_Concrete', source)
        self.assertIn('bpy.ops.render.render', source)

    def test_pack_contains_expected_files(self):
        result = create_pack('post_apocalyptic', 'Unit Test Graphics', 7, False)
        folder = Path(result['folder'])
        self.assertTrue(result['ok'])
        self.assertTrue((folder/'build_environment.py').is_file())
        self.assertTrue((folder/'graphics_brief.json').is_file())
        self.assertTrue((folder/'UnrealConfig'/'DefaultEngine.ini').is_file())
        script = (folder/'build_environment.py').read_text(encoding='utf-8')
        compile(script, str(folder/'build_environment.py'), 'exec')
        self.assertNotIn('OUT_BLEND_PLACEHOLDER', script)
        brief = json.loads((folder/'graphics_brief.json').read_text(encoding='utf-8'))
        self.assertTrue(brief['free_local_only'])
        self.assertTrue(brief['limitations'])

if __name__ == '__main__': unittest.main()
