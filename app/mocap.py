"""Free, local, single-camera pose capture using MediaPipe Pose.

Outputs landmark JSON and a BVH preview. BVH rotations are planar approximations from
2D landmarks; this is not markerless full-3D motion capture and should be retargeted
and cleaned before production use.
"""
import csv, json, math, shutil, subprocess, uuid
from pathlib import Path
import os
from .config import WORKSPACE_DIR
from .asset_studio import OUTPUT_DIR

CAPTURE_DIR = WORKSPACE_DIR / 'omniforge_assets' / 'inputs' / 'motion_capture'
CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_VIDEO = {'.mp4', '.mov', '.avi', '.mkv', '.webm'}
MAX_VIDEO_BYTES = 250 * 1024 * 1024

# MediaPipe landmark indices, named for a compact BVH-like humanoid.
JOINTS = {
    'Hips': 23, 'Spine': 11, 'Head': 0,
    'LeftShoulder': 11, 'LeftElbow': 13, 'LeftWrist': 15,
    'RightShoulder': 12, 'RightElbow': 14, 'RightWrist': 16,
    'LeftKnee': 25, 'LeftAnkle': 27, 'RightKnee': 26, 'RightAnkle': 28,
}

def _bvh_angle(a, b):
    return math.degrees(math.atan2(-(b['y']-a['y']), b['x']-a['x']))

def _write_bvh(frames, target, fps):
    # A simple planar BVH hierarchy for previews and retargeting. Bone lengths are
    # normalized from first-frame landmark distances; rotations are relative angles.
    first = frames[0]['landmarks']
    def point(i):
        p = first.get(str(i)) or {'x':.5,'y':.5,'z':0}
        return p
    def length(a,b):
        p,q=point(a),point(b)
        return max(0.01, math.sqrt((p['x']-q['x'])**2+(p['y']-q['y'])**2)*100)
    hierarchy = '''HIERARCHY\nROOT Hips\n{\n OFFSET 0 0 0\n CHANNELS 6 Xposition Yposition Zposition Zrotation Xrotation Yrotation\n JOINT Spine\n {\n  OFFSET 0 10 0\n  CHANNELS 3 Zrotation Xrotation Yrotation\n  JOINT Head\n  {\n   OFFSET 0 15 0\n   CHANNELS 3 Zrotation Xrotation Yrotation\n   End Site { OFFSET 0 8 0 }\n  }\n }\n JOINT LeftShoulder\n {\n  OFFSET -8 10 0\n  CHANNELS 3 Zrotation Xrotation Yrotation\n  JOINT LeftElbow\n  {\n   OFFSET -'''+f'{length(11,13):.4f}'+''' 0 0\n   CHANNELS 3 Zrotation Xrotation Yrotation\n   JOINT LeftWrist { OFFSET -'''+f'{length(13,15):.4f}'+''' 0 0 CHANNELS 3 Zrotation Xrotation Yrotation End Site { OFFSET -3 0 0 } }\n  }\n }\n JOINT RightShoulder\n {\n  OFFSET 8 10 0\n  CHANNELS 3 Zrotation Xrotation Yrotation\n  JOINT RightElbow\n  {\n   OFFSET '''+f'{length(12,14):.4f}'+''' 0 0\n   CHANNELS 3 Zrotation Xrotation Yrotation\n   JOINT RightWrist { OFFSET '''+f'{length(14,16):.4f}'+''' 0 0 CHANNELS 3 Zrotation Xrotation Yrotation End Site { OFFSET 3 0 0 } }\n  }\n }\n JOINT LeftKnee\n {\n  OFFSET -5 -10 0\n  CHANNELS 3 Zrotation Xrotation Yrotation\n  JOINT LeftAnkle { OFFSET 0 -'''+f'{length(23,25):.4f}'+''' 0 CHANNELS 3 Zrotation Xrotation Yrotation End Site { OFFSET 0 -'''+f'{length(25,27):.4f}'+''' 0 } }\n }\n JOINT RightKnee\n {\n  OFFSET 5 -10 0\n  CHANNELS 3 Zrotation Xrotation Yrotation\n  JOINT RightAnkle { OFFSET 0 -'''+f'{length(24,26):.4f}'+''' 0 CHANNELS 3 Zrotation Xrotation Yrotation End Site { OFFSET 0 -'''+f'{length(26,28):.4f}'+''' 0 } }\n }\n}\n'''
    def angle_for(frame, a, b):
        la=frame['landmarks'].get(str(a)); lb=frame['landmarks'].get(str(b))
        if not la or not lb or la.get('visibility',0)<0.2 or lb.get('visibility',0)<0.2: return 0.0
        return _bvh_angle(la,lb)
    lines=[hierarchy.rstrip(),'MOTION',f'Frames: {len(frames)}',f'Frame Time: {1.0/fps:.7f}']
    for fr in frames:
        # BVH root position + 13 joints x 3 Euler channels. Pose is a front-view planar estimate.
        lm=fr['landmarks']; hip=lm.get('23',{})
        rootx=(hip.get('x',.5)-.5)*100; rooty=(.5-hip.get('y',.5))*100
        angles=[angle_for(fr,23,11), angle_for(fr,11,0), angle_for(fr,11,13), angle_for(fr,13,15), angle_for(fr,15,19), angle_for(fr,12,14), angle_for(fr,14,16), angle_for(fr,16,20), angle_for(fr,23,25), angle_for(fr,25,27), angle_for(fr,24,26), angle_for(fr,26,28)]
        vals=[rootx,rooty,0.0,0.0,0.0,0.0]
        for a in angles: vals.extend([a,0.0,0.0])
        lines.append(' '.join(f'{x:.4f}' for x in vals))
    target.write_text('\n'.join(lines)+'\n',encoding='utf-8')

def process_video(video_path: str, sample_fps: int = 15, max_frames: int = 900):
    path=Path(video_path).resolve()
    if not path.is_relative_to(CAPTURE_DIR.resolve()) or not path.is_file(): raise ValueError('Video must be uploaded to the local motion-capture input folder.')
    if path.suffix.lower() not in ALLOWED_VIDEO: raise ValueError('Supported video types: MP4, MOV, AVI, MKV, WEBM.')
    if not 1 <= sample_fps <= 30: raise ValueError('Sample FPS must be between 1 and 30.')
    try:
        import cv2
        import mediapipe as mp
    except ImportError as exc:
        raise RuntimeError('Free local motion capture needs optional packages. Run: .venv\\Scripts\\python.exe -m pip install -r requirements-motion.txt') from exc
    cap=cv2.VideoCapture(str(path))
    if not cap.isOpened(): raise RuntimeError('Could not open the uploaded video.')
    source_fps=cap.get(cv2.CAP_PROP_FPS) or 30
    stride=max(1,round(source_fps/sample_fps))
    frames=[]; index=0; processed=0
    try:
        with mp.solutions.pose.Pose(static_image_mode=False,model_complexity=1,enable_segmentation=False,min_detection_confidence=.5,min_tracking_confidence=.5) as pose:
            while len(frames)<max_frames:
                ok,frame=cap.read()
                if not ok: break
                if index % stride == 0:
                    rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB); result=pose.process(rgb)
                    if result.pose_landmarks:
                        lm={str(i):{'x':round(float(p.x),6),'y':round(float(p.y),6),'z':round(float(p.z),6),'visibility':round(float(p.visibility),4)} for i,p in enumerate(result.pose_landmarks.landmark)}
                        frames.append({'frame':len(frames),'source_frame':index,'time_seconds':round(index/source_fps,4),'landmarks':lm})
                    processed+=1
                index+=1
    finally: cap.release()
    if len(frames)<2: raise RuntimeError('Could not detect a human pose in at least two sampled frames. Use a clear, well-lit video with the full body visible.')
    token=uuid.uuid4().hex[:8]; json_path=OUTPUT_DIR/f'{path.stem}_mocap_{token}.json'; bvh_path=OUTPUT_DIR/f'{path.stem}_mocap_{token}.bvh'; csv_path=OUTPUT_DIR/f'{path.stem}_mocap_{token}.csv'
    payload={'source_video':path.name,'capture_mode':'single-camera 2D landmark capture with approximate planar BVH rotations','source_fps':source_fps,'sample_fps':sample_fps,'frame_count':len(frames),'landmark_count':33,'frames':frames,'limitations':['Single-camera depth is ambiguous.','BVH rotations are a planar preview approximation, not production-quality full 3D motion capture.','Retarget and inspect the BVH on the target skeleton before game use.']}
    json_path.write_text(json.dumps(payload,indent=2),encoding='utf-8'); _write_bvh(frames,bvh_path,sample_fps)
    with csv_path.open('w',newline='',encoding='utf-8') as f:
        w=csv.writer(f); w.writerow(['frame','time_seconds','landmark_id','x','y','z','visibility'])
        for fr in frames:
            for lid,p in fr['landmarks'].items(): w.writerow([fr['frame'],fr['time_seconds'],lid,p['x'],p['y'],p['z'],p['visibility']])
    return {'ok':True,'source_video':path.name,'frames_detected':len(frames),'sample_fps':sample_fps,'outputs':{'landmarks_json':str(json_path.relative_to(WORKSPACE_DIR)),'approximate_bvh':str(bvh_path.relative_to(WORKSPACE_DIR)),'landmarks_csv':str(csv_path.relative_to(WORKSPACE_DIR))},'limitations':payload['limitations']}
