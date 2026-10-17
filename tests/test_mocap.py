from pathlib import Path
from app.mocap import _write_bvh

def test_bvh_writer_emits_frame_data(tmp_path):
    lm={str(i):{'x':0.3+i*0.01,'y':0.2+i*0.015,'z':0.0,'visibility':0.99} for i in range(33)}
    frames=[{'frame':0,'landmarks':lm},{'frame':1,'landmarks':lm}]
    target=tmp_path/'sample.bvh'
    _write_bvh(frames,target,15)
    text=target.read_text()
    assert 'HIERARCHY' in text and 'MOTION' in text
    assert 'Frames: 2' in text
    data_lines=text.split('Frame Time: ')[1].splitlines()[1:]
    assert len(data_lines)==2
    assert all(len(line.split())==42 for line in data_lines)
