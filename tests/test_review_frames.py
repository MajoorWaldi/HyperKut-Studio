import subprocess
from backend.review import build_review_frames


def test_review_frames_have_known_times_and_are_cached(tmp_path):
    video=tmp_path/'video.mp4'
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=64x64:r=24:d=2','-c:v','libx264',str(video)],check=True)
    frames=build_review_frames(video,tmp_path/'review')
    assert [f['seconds'] for f in frames]==[0,.5,1,1.5]
    assert all((tmp_path/'review'/f['file']).is_file() for f in frames)
    assert build_review_frames(video,tmp_path/'review')==frames


def test_review_includes_last_partial_interval(tmp_path):
    video=tmp_path/'short.mp4'
    subprocess.run(['ffmpeg','-y','-v','error','-f','lavfi','-i','color=c=red:s=64x64:r=24','-frames:v','15','-c:v','libx264',str(video)],check=True)
    assert [f['seconds'] for f in build_review_frames(video,tmp_path/'review')]==[0,.5]
