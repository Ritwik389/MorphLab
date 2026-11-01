"""Appearance-gated face association, sparse-flow prediction, and video metrics.

This combines established methods; it is not a new recognition or swap model.
Thresholds are experimental defaults, exposed in reports for reproducibility.
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass

import cv2
import numpy as np
from scipy.optimize import linear_sum_assignment


def clone_face(face):
    # InsightFace Face.__getattr__ returns None for __setstate__, which breaks copy.copy.
    return type(face)(dict(face)) if isinstance(face, dict) else copy.copy(face)


def embedding(face):
    value = getattr(face, 'normed_embedding', None)
    if value is None:
        value = getattr(face, 'embedding', None)
    if value is None:
        return None
    value = np.asarray(value, dtype=np.float32)
    norm = np.linalg.norm(value)
    return value / norm if np.isfinite(value).all() and norm > 1e-8 else None


def iou(a, b):
    a, b = np.asarray(a), np.asarray(b)
    intersection = np.maximum(0, np.minimum(a[2:], b[2:]) - np.maximum(a[:2], b[:2])).prod()
    area = np.maximum(0, a[2:] - a[:2]).prod() + np.maximum(0, b[2:] - b[:2]).prod()
    return float(intersection / max(1e-8, area - intersection))


def stabilize(predicted, observed):
    """Smooth small detection jitter; follow large genuine motion immediately."""
    if predicted is None:
        return np.asarray(observed, dtype=np.float32).copy()
    predicted, observed = np.asarray(predicted), np.asarray(observed)
    extent = max(1., float(np.linalg.norm(observed[0] - observed[1])))
    displacement = float(np.linalg.norm(predicted - observed, axis=1).mean()) / extent
    alpha = 1.0 if displacement > .12 else .65
    return (predicted * (1 - alpha) + observed * alpha).astype(np.float32)


@dataclass
class Track:
    id: int
    face: object
    appearance: np.ndarray | None
    missed: int = 0
    visible: bool = True


class FaceTracker:
    def __init__(self, max_missed=3, appearance_gate=.55, minimum_iou=.05, smooth=True, appearance=True):
        self.max_missed = max_missed
        self.appearance_gate = appearance_gate
        self.minimum_iou = minimum_iou
        self.smooth = smooth
        self.appearance_enabled = appearance
        self.tracks = []
        self.next_id = 1
        self.created = 0
        self.rejected_associations = 0

    def reset(self):
        self.tracks.clear()

    def update(self, faces):
        """Assign globally; never accept a spatial match with conflicting identity."""
        faces = list(faces)
        old = list(self.tracks)
        cost = np.full((len(old), len(faces)), 1e6)
        for i, track in enumerate(old):
            for j, face in enumerate(faces):
                overlap = iou(track.face.bbox, face.bbox)
                appearance = embedding(face)
                if self.appearance_enabled and track.appearance is not None and appearance is not None:
                    distance = float(1 - np.clip(np.dot(track.appearance, appearance), -1, 1))
                    if distance > self.appearance_gate:
                        self.rejected_associations += 1
                        continue
                    # Appearance can recover a fast mover with little box overlap.
                    if overlap < self.minimum_iou and distance > .25:
                        continue
                    cost[i, j] = .75 * distance + .25 * (1 - overlap)
                elif overlap >= .2:
                    cost[i, j] = 1 - overlap
        pairs = list(zip(*linear_sum_assignment(cost))) if cost.size else []
        assigned_tracks, assigned_faces = set(), set()
        for i, j in pairs:
            if cost[i, j] >= 1e6:
                continue
            track, face = old[i], clone_face(faces[j])
            if self.smooth and getattr(face, 'kps', None) is not None:
                face.kps = stabilize(getattr(track.face, 'kps', None), face.kps)
            observed = embedding(face)
            if observed is not None:
                merged = observed if track.appearance is None else .9 * track.appearance + .1 * observed
                track.appearance = merged / max(1e-8, np.linalg.norm(merged))
            track.face, track.missed, track.visible = face, 0, True
            assigned_tracks.add(i)
            assigned_faces.add(j)
        for i, track in enumerate(old):
            if i not in assigned_tracks:
                track.missed += 1
                track.visible = False
        self.tracks = [t for t in old if t.missed <= self.max_missed]
        for j, face in enumerate(faces):
            if j not in assigned_faces:
                self.tracks.append(Track(self.next_id, clone_face(face), embedding(face)))
                self.next_id += 1
                self.created += 1
        return [t for t in self.tracks if t.visible]

    def predict(self, previous_gray, gray):
        """Propagate landmarks on the CURRENT frame; refresh if flow is unreliable."""
        if previous_gray is None or previous_gray.shape != gray.shape:
            return False
        visible = [t for t in self.tracks if t.visible]
        if not visible:
            return False
        reliable = True
        for track in visible:
            points = getattr(track.face, 'kps', None)
            if points is None:
                track.visible = False
                reliable = False
                continue
            p0 = np.asarray(points, np.float32).reshape(-1, 1, 2)
            # At coarse pyramid levels a point near an image edge can leave
            # the usable LK window even when full-resolution motion is small.
            h, w = gray.shape
            margin = min(float(p0[:, 0, 0].min()), float(p0[:, 0, 1].min()),
                         w - 1 - float(p0[:, 0, 0].max()), h - 1 - float(p0[:, 0, 1].max()))
            level = max(0, min(2, int(np.log2(max(1., margin / 12)))))
            p1, status, _ = cv2.calcOpticalFlowPyrLK(previous_gray, gray, p0, None, maxLevel=level)
            if p1 is None or status is None:
                track.visible = False
                reliable = False
                continue
            backward, back_status, _ = cv2.calcOpticalFlowPyrLK(
                gray, previous_gray, p1, p0.copy(), flags=cv2.OPTFLOW_USE_INITIAL_FLOW, maxLevel=level)
            if backward is None or back_status is None:
                track.visible = False
                reliable = False
                continue
            error = np.linalg.norm(p0 - backward, axis=2).ravel()
            valid = (status.ravel() == 1) & (back_status.ravel() == 1) & (error < 1.5)
            if valid.sum() < 4:
                track.visible = False
                reliable = False
                continue
            transform, inliers = cv2.estimateAffinePartial2D(p0[valid], p1[valid], method=cv2.RANSAC)
            if transform is None or inliers is None or inliers.sum() < 4 or not np.isfinite(transform).all():
                track.visible = False
                reliable = False
                continue
            scale = np.linalg.norm(transform[:, 0])
            if not .8 < scale < 1.25:
                track.visible = False
                reliable = False
                continue
            face = clone_face(track.face)
            face.kps = cv2.transform(p0, transform).reshape(-1, 2)
            x1, y1, x2, y2 = face.bbox
            corners = np.array([[[x1, y1], [x2, y1], [x2, y2], [x1, y2]]], np.float32)
            corners = cv2.transform(corners, transform)[0]
            face.bbox = np.r_[corners.min(axis=0), corners.max(axis=0)]
            h, w = gray.shape
            if face.bbox[2] <= 0 or face.bbox[3] <= 0 or face.bbox[0] >= w or face.bbox[1] >= h:
                track.visible = False
                reliable = False
                continue
            track.face = face
        return reliable


def scene_changed(previous, current):
    if previous is None:
        return False
    if previous.shape != current.shape:
        return True
    a = cv2.resize(previous, (64, 64))
    b = cv2.resize(current, (64, 64))
    delta = float(np.abs(a.astype(float) - b.astype(float)).mean())
    histogram_a = cv2.calcHist([a], [0], None, [32], [0, 256])
    histogram_b = cv2.calcHist([b], [0], None, [32], [0, 256])
    distance = cv2.compareHist(histogram_a, histogram_b, cv2.HISTCMP_BHATTACHARYYA)
    return delta > 65 or (delta > 25 and distance > .65)


def aligned_crop(frame, face):
    template = np.array([[38.2946, 51.6963], [73.5318, 51.5014], [56.0252, 71.7366],
                         [41.5493, 92.3655], [70.7299, 92.2041]], np.float32)
    points = getattr(face, 'kps', None)
    if points is None or np.asarray(points).shape != (5, 2):
        return None
    transform, _ = cv2.estimateAffinePartial2D(np.asarray(points, np.float32), template, method=cv2.LMEDS)
    if transform is None:
        return None
    return cv2.warpAffine(frame, transform, (112, 112), borderMode=cv2.BORDER_REFLECT_101)


class TemporalProcessor:
    """Baseline/tracked/adaptive ablations with identical source and swap model."""
    def __init__(self, detector, swap, source_face, mode='tracked', interval=3,
                 many_faces=False, identity_metric=None, minimum_confidence=.5, postprocess=None):
        if mode not in {'baseline', 'tracked', 'adaptive'} or not 1 <= interval <= 10:
            raise ValueError('Invalid temporal strategy or detection interval.')
        self.detector, self.swap, self.source_face = detector, swap, source_face
        self.mode, self.interval, self.many_faces = mode, interval, many_faces
        self.identity_metric = identity_metric
        self.postprocess = postprocess
        self.minimum_confidence = minimum_confidence
        self.tracker = FaceTracker(smooth=mode != 'baseline')
        self.previous_gray = None
        self.selected_appearance = None
        self.frames = self.detector_calls = self.scene_cuts = self.faces_edited = 0
        self.previous_residual = {}
        self.timings = {'tracking_ms': [], 'detection_ms': [], 'swap_ms': [], 'evaluation_ms': [], 'total_ms': []}
        self.temporal_errors, self.identity_scores = [], []

    def process(self, frame):
        started = time.perf_counter()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        cut = scene_changed(self.previous_gray, gray)
        if cut:
            self.tracker.reset()
            self.previous_residual.clear()
            self.scene_cuts += 1
        tracking_start = time.perf_counter()
        flow_ok = False
        if self.mode != 'baseline' and not cut:
            flow_ok = self.tracker.predict(self.previous_gray, gray)
        self.timings['tracking_ms'].append((time.perf_counter() - tracking_start) * 1000)
        needs_detection = (self.mode != 'adaptive' or self.frames % self.interval == 0 or not flow_ok or cut)
        detection_start = time.perf_counter()
        if needs_detection:
            faces = [f for f in (self.detector(frame) or [])
                     if float(getattr(f, 'det_score', 1)) >= self.minimum_confidence]
            self.detector_calls += 1
            tracks = self.tracker.update(faces)
        else:
            tracks = [t for t in self.tracker.tracks if t.visible]
        self.timings['detection_ms'].append((time.perf_counter() - detection_start) * 1000)
        tracks.sort(key=lambda t: t.face.bbox[0])
        selected = tracks
        if tracks and not self.many_faces:
            if self.mode == 'baseline':
                selected = tracks[:1]
            elif self.selected_appearance is None:
                selected = tracks[:1]
                self.selected_appearance = tracks[0].appearance
            else:
                candidates = [t for t in tracks if t.appearance is not None and
                              1 - np.dot(t.appearance, self.selected_appearance) <= self.tracker.appearance_gate]
                selected = sorted(candidates, key=lambda t: -np.dot(t.appearance, self.selected_appearance))[:1]
        result = frame.copy()
        swap_start = time.perf_counter()
        for track in selected:
            result = self.swap(self.source_face, track.face, result)
            self.faces_edited += 1
        if self.postprocess is not None:
            result = self.postprocess(result, [t.face.bbox.astype(int) for t in selected])
        self.timings['swap_ms'].append((time.perf_counter() - swap_start) * 1000)
        evaluation_start = time.perf_counter()
        active_ids = {t.id for t in selected}
        self.previous_residual = {k: v for k, v in self.previous_residual.items() if k in active_ids}
        for track in selected:
            original_crop = aligned_crop(frame, track.face)
            edited_crop = aligned_crop(result, track.face)
            if original_crop is not None and edited_crop is not None:
                residual = edited_crop.astype(np.float32) - original_crop.astype(np.float32)
                if track.id in self.previous_residual:
                    self.temporal_errors.append(float(np.abs(residual - self.previous_residual[track.id]).mean()))
                self.previous_residual[track.id] = residual
            if self.identity_metric is not None and self.frames % 10 == 0:
                score = self.identity_metric(result, track.face)
                if score is not None and np.isfinite(score):
                    self.identity_scores.append(float(score))
        self.timings['evaluation_ms'].append((time.perf_counter() - evaluation_start) * 1000)
        self.timings['total_ms'].append((time.perf_counter() - started) * 1000)
        self.previous_gray = gray
        self.frames += 1
        return result

    def report(self):
        total = sum(self.timings['total_ms']) / 1000
        return {'schema_version': 1, 'strategy': self.mode, 'detection_interval': self.interval,
                'frames_processed': self.frames, 'detector_calls': self.detector_calls,
                'detector_call_reduction_fraction': 1 - self.detector_calls / max(1, self.frames),
                'scene_cuts': self.scene_cuts, 'tracks_created': self.tracker.created,
                'rejected_identity_associations': self.tracker.rejected_associations,
                'face_edits': self.faces_edited, 'processing_fps_excluding_io': self.frames / total if total else None,
                'latency': {k: {'mean': float(np.mean(v)), 'p50': float(np.median(v)),
                                'p95': float(np.percentile(v, 95))} for k, v in self.timings.items() if v},
                'aligned_edit_residual_change_mean_0_255': float(np.mean(self.temporal_errors)) if self.temporal_errors else None,
                'temporal_comparisons': len(self.temporal_errors),
                'source_output_embedding_cosine_mean': float(np.mean(self.identity_scores)) if self.identity_scores else None,
                'identity_samples': len(self.identity_scores),
                'parameters': {'appearance_distance_gate': self.tracker.appearance_gate,
                               'minimum_detection_confidence': self.minimum_confidence,
                               'flow_forward_backward_error_px': 1.5},
                'limitations': ['Temporal residual change is a flicker proxy, not perceptual ground truth.',
                               'Identity similarity uses the same recognition model as the pipeline.',
                               'Identity switches and detection recall require annotated ground truth.',
                               'Timings include evaluation but exclude video I/O and model loading.']}
