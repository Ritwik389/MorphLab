from types import SimpleNamespace

import cv2
import numpy as np
import pytest

from modules.temporal import FaceTracker, TemporalProcessor, embedding, scene_changed, stabilize


def face(x=0, identity=0, confidence=.95):
    return SimpleNamespace(bbox=np.array([x, 10, x+80, 110], dtype=np.float32),
        kps=np.array([[x+20,40],[x+60,40],[x+40,60],[x+25,85],[x+55,85]], np.float32),
        normed_embedding=np.eye(3, dtype=np.float32)[identity], det_score=confidence)


def test_crossing_faces_keep_their_ids_despite_detection_order():
    tracker = FaceTracker()
    tracks = tracker.update([face(10,0), face(100,1)])
    ids = {int(t.appearance.argmax()): t.id for t in tracks}
    crossed = tracker.update([face(10,1), face(100,0)])
    assert {int(t.appearance.argmax()): t.id for t in crossed} == ids
    assert tracker.created == 2


def test_real_insightface_objects_can_be_cloned_without_losing_properties():
    from insightface.app.common import Face
    original=face()
    detected=Face(bbox=original.bbox,kps=original.kps,embedding=np.array([1.,0.,0.]),det_score=.95)
    tracker=FaceTracker()
    tracked=tracker.update([detected])[0].face
    assert isinstance(tracked,Face) and tracked is not detected
    np.testing.assert_allclose(tracked.normed_embedding,detected.normed_embedding)


def test_wrong_identity_cannot_take_over_overlapping_track():
    tracker = FaceTracker()
    first = tracker.update([face(10,0)])[0].id
    second = tracker.update([face(10,1)])[0].id
    assert first != second
    assert tracker.rejected_associations > 0


def test_empty_detection_hides_face_and_recovers_short_occlusion():
    tracker = FaceTracker(max_missed=2)
    first = tracker.update([face()])[0].id
    assert tracker.update([]) == []
    assert tracker.update([face()])[0].id == first
    for _ in range(3):
        tracker.update([])
    assert tracker.update([face()])[0].id != first


def test_smoothing_reduces_jitter_and_follows_large_motion():
    original = face().kps
    jitter = original + .5
    assert np.linalg.norm(stabilize(original,jitter)-original) < np.linalg.norm(jitter-original)
    moved = original + 30
    np.testing.assert_allclose(stabilize(original,moved), moved)


def test_cut_detection_and_tracker_reset():
    a=np.zeros((128,128),np.uint8)
    assert not scene_changed(None,a)
    assert not scene_changed(a,a)
    assert scene_changed(a,np.full_like(a,255))
    tracker=FaceTracker()
    first=tracker.update([face()])[0].id
    tracker.reset()
    assert tracker.update([face()])[0].id > first


def test_sparse_flow_uses_current_frame_coordinates():
    rng=np.random.default_rng(9)
    gray=rng.integers(0,256,(160,220),dtype=np.uint8)
    translated=cv2.warpAffine(gray,np.array([[1,0,3],[0,1,2]],np.float32),(220,160))
    tracker=FaceTracker()
    track=tracker.update([face(35)])[0]
    before=track.face.kps.copy()
    assert tracker.predict(gray,translated)
    np.testing.assert_allclose(track.face.kps,before+[3,2],atol=.15)


def test_bad_flow_forces_detection_instead_of_reusing_stale_boxes():
    gray=np.zeros((160,220),np.uint8)
    tracker=FaceTracker()
    tracker.update([face(35)])
    assert not tracker.predict(gray,gray)
    assert not tracker.tracks[0].visible


def test_baseline_detects_every_frame():
    calls=[]
    def detect(frame):
        calls.append(1)
        return [face(30)]
    processor=TemporalProcessor(detect,lambda source,face,frame:frame,face(),mode='baseline')
    for _ in range(4):processor.process(np.zeros((160,220,3),np.uint8))
    report=processor.report()
    assert report['detector_calls']==4
    assert report['identity_samples']==0
    assert report['source_output_embedding_cosine_mean'] is None
    assert 'identity_switches' not in report


def test_adaptive_saves_detections_only_when_flow_is_reliable():
    rng=np.random.default_rng(4)
    frame=rng.integers(0,256,(160,220,3),dtype=np.uint8)
    processor=TemporalProcessor(lambda frame:[face(30)],lambda source,face,frame:frame,
                                face(),mode='adaptive',interval=3)
    for _ in range(7):processor.process(frame)
    report=processor.report()
    assert report['detector_calls']==3
    assert report['frames_processed']==7
    assert report['temporal_comparisons']==6
    assert report['aligned_edit_residual_change_mean_0_255']==0
    assert report['detector_call_reduction_fraction']==pytest.approx(4/7)


def test_low_confidence_face_is_not_edited():
    processor=TemporalProcessor(lambda frame:[face(confidence=.1)],lambda *a:pytest.fail('unsafe swap'),
                                face(),mode='tracked')
    processor.process(np.zeros((160,220,3),np.uint8))
    assert processor.report()['face_edits']==0


def test_single_identity_target_does_not_switch_when_faces_cross():
    observations=iter([[face(10,0),face(100,1)],[face(10,1),face(100,0)]])
    edited=[]
    def swap(source,target,frame):
        edited.append(int(embedding(target).argmax()))
        return frame
    processor=TemporalProcessor(lambda frame:next(observations),swap,face(),mode='tracked')
    for _ in range(2):processor.process(np.zeros((160,220,3),np.uint8))
    assert edited==[0,0]


def test_scene_cut_does_not_carry_temporal_pixels_or_select_unrelated_person():
    observations=iter([[face(30,0)],[face(30,1)]])
    processor=TemporalProcessor(lambda frame:next(observations),lambda source,target,frame:frame,
                                face(),mode='tracked')
    processor.process(np.zeros((160,220,3),np.uint8))
    processor.process(np.full((160,220,3),255,np.uint8))
    report=processor.report()
    assert report['scene_cuts']==1
    assert report['temporal_comparisons']==0
    assert report['face_edits']==1
