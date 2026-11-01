# Graph Report - MorphLab  (2026-11-01)

## Corpus Check
- 158 files · ~84,204 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 11 file(s) not represented in the graph (top: (none) 5, .lock 2, .vbs 1)

## Summary
- 1275 nodes · 3236 edges · 64 communities (46 shown, 18 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 167 edges (avg confidence: 0.87)
- Host-agent token usage: unavailable; zero counters in extraction intermediates are placeholders.

## Community Hubs (Navigation)
- Evidence and Evaluation
- Enhancer Runtime Dependencies
- HTTP API and Uploads
- Engineering Assurance Records
- Face Swap Compositing
- Live Session Assurance
- Desktop Processing Lifecycle
- Continuous Integration Workflows
- Face Analysis and Paths
- Model Registry Validation
- Live Inference Modules
- Mobile Generator Architecture
- Tracking and Temporal Tests
- Frontend Build Toolchain
- Face Enhancement Pipeline
- Legacy Camera Processing
- Streaming Protocol and Scheduling
- Studio Website Components
- Desktop Window Controls
- GPU Image Operations
- Desktop Preview Controls
- Video Media Utilities
- Media Regression Fixtures
- Frame Processing Pipelines
- Desktop Face Mapping
- CoreML Graph Optimization
- Desktop Settings Panels
- Browser Live Lifecycle
- Face Masks and Regions
- Research and Export Jobs
- Browser Workflow Configuration
- Camera Capture and Preview
- Desktop Worker Threads
- Browser Media Worker Bridge
- Legacy Web Launchers
- Frontend Runtime Dependencies
- TypeScript Compiler Configuration
- Model Parity Evaluation
- Desktop Compatibility Adapters
- CPU Container Configuration
- Desktop Tooltip Helpers
- Preview Image Rendering
- Installation Dependency Roles
- Tkinter Compatibility Patches
- Face Analyser Regression
- Video Preview Indexing
- Hardware Platform Detection
- CUDA Graph Adapter
- Codec and Orientation Assurance
- Frontend Test Commands
- Frame Worker Ordering
- Remote Archive Reader
- Independent AdaFace Evaluator
- Optional Content Classifier
- Paddle Reference Parity
- Media Worker Entrypoint
- Pinned NumPy Build
- Local Setup Script
- Mac Acceleration Setup
- Local Startup Script

## God Nodes (most connected - your core abstractions)
1. `fingerprint()` - 38 edges
2. `LiveSession` - 32 edges
3. `get_one_face()` - 31 edges
4. `MainWindow` - 31 edges
5. `ModelRegistry` - 30 edges
6. `imread_unicode()` - 29 edges
7. `Face` - 27 edges
8. `start()` - 24 edges
9. `write_report()` - 23 edges
10. `run_job()` - 22 edges

## Surprising Connections (you probably didn't know these)
- `test_evidence_requires_all_ten_second_windows_and_unique_swaps()` --calls--> `browser_gate()`  [EXTRACTED]
  tests/test_flagship.py → modules/evaluation.py
- `test_artifact_gate_does_not_trust_a_passed_label()` --calls--> `artifact_gate()`  [EXTRACTED]
  tests/test_flagship.py → modules/evaluation.py
- `test_dependency_audit_alone_cannot_pass_container_security()` --calls--> `artifact_gate()`  [EXTRACTED]
  tests/test_flagship.py → modules/evaluation.py
- `_analyse_faces()` --calls--> `Face`  [INFERRED]
  modules/face_analyser.py → tests/test_face_analyser_get_one_face.py
- `detect_one_face_fast()` --calls--> `Face`  [INFERRED]
  modules/face_analyser.py → tests/test_face_analyser_get_one_face.py

## Import Cycles
- None detected.

## Hyperedges (group relationships)
- **Quality-constrained live selection** — docs_experiments_selection_rule, docs_experiments_adaface, docs_experiments_browser_trials [EXTRACTED 1.00]
- **Required evidence release boundary** — docs_release_gates, docs_release_manual_checks, docs_security_container_gate, docs_test_strategy_fingerprints [EXTRACTED 1.00]
- **Separate code model and data rights** — docs_licensing_scope, docs_model_data_card_models, docs_model_data_card_ravdess [INFERRED 0.95]

## Communities (64 total, 18 thin omitted)

### Community 0 - "Evidence and Evaluation"
Cohesion: 0.05
Nodes (37): artifact_gate(), browser_gate(), fingerprint(), sha256(), validate_corpus(), write_report(), main(), main() (+29 more)

### Community 1 - "Enhancer Runtime Dependencies"
Cohesion: 0.07
Nodes (25): enhance_face(), get_enhancer(), pre_check(), process_frame(), process_frame_v2(), process_frames(), process_image(), process_video() (+17 more)

### Community 2 - "HTTP API and Uploads"
Cohesion: 0.06
Nodes (32): boundaries(), cancel_job(), clear_source(), create_job(), create_session(), delete_session(), download(), enroll() (+24 more)

### Community 3 - "Engineering Assurance Records"
Cohesion: 0.05
Nodes (31): Media Integrity Corrections, Session Isolation and Disconnect Cleanup, Verified Model Downloads, Graphify Code and Documentation Map, LiveSession Graph Queries, Non-root CPU Container, Material Studio Design, Offline AdaFace Validation (+23 more)

### Community 4 - "Face Swap Compositing"
Cohesion: 0.10
Nodes (24): default_source_face(), get_one_face(), imwrite_unicode(), apply_color_transfer(), apply_mouth_area(), _apply_poisson_blend(), apply_post_processing(), _create_elliptical_mask() (+16 more)

### Community 5 - "Live Session Assurance"
Cohesion: 0.09
Nodes (24): analyse_source(), extract(), erase(), LiveSession, main(), face(), test_appearance_ablation_exposes_crossing_tradeoff(), test_artifact_gate_does_not_trust_a_passed_label() (+16 more)

### Community 6 - "Desktop Processing Lifecycle"
Cohesion: 0.10
Nodes (26): decode_execution_providers(), destroy(), encode_execution_providers(), limit_resources(), parse_args(), pre_check(), release_resources(), run() (+18 more)

### Community 7 - "Continuous Integration Workflows"
Cohesion: 0.06
Nodes (36): if, runs-on, steps, runs-on, steps, strategy, AIMS_CPU_CI, jobs (+28 more)

### Community 8 - "Face Analysis and Paths"
Cohesion: 0.12
Nodes (20): find_closest_centroid(), find_cluster_centroids(), _analyse_faces(), default_target_face(), detect_many_faces_fast(), detect_one_face_fast(), dump_faces(), get_many_faces() (+12 more)

### Community 9 - "Model Registry Validation"
Cohesion: 0.14
Nodes (7): ModelRegistry, RuntimeConfig, run_candidate(), test_dense_five_point_topology_matches_detector(), test_real_cpu_model_detect_enroll_swap(), test_real_light_tracking_returns_consistent_embedding_space(), test_failed_accelerator_warmup_falls_back_to_validated_cpu()

### Community 10 - "Live Inference Modules"
Cohesion: 0.15
Nodes (10): paste_face(), edit_frame(), observe(), unpack_frame(), aligned_crop(), iou(), scene_changed(), Track (+2 more)

### Community 11 - "Mobile Generator Architecture"
Cohesion: 0.09
Nodes (12): ArrayUnpickler, ConvBlock, final_layers(), Generator, IdentityEncoder, IdentityWeights, IRBlock, load_paddle() (+4 more)

### Community 12 - "Tracking and Temporal Tests"
Cohesion: 0.17
Nodes (20): embedding(), FaceTracker, stabilize(), TemporalProcessor, face(), test_adaptive_saves_detections_only_when_flow_is_reliable(), test_bad_flow_forces_detection_instead_of_reusing_stale_boxes(), test_baseline_detects_every_frame() (+12 more)

### Community 13 - "Frontend Build Toolchain"
Cohesion: 0.10
Nodes (26): devDependencies, @axe-core/playwright@^4.14.0, daisyui@^5.7.0, @playwright/test@^1.56.0, tailwindcss@^4.1.0, @tailwindcss/vite@^4.1.0, @types/react@^19.2.0, @types/react-dom@^19.2.0 (+18 more)

### Community 14 - "Face Enhancement Pipeline"
Cohesion: 0.11
Nodes (12): _align_face(), enhance_face(), get_face_enhancer(), _paste_back(), _postprocess_face(), _preprocess_face(), process_frame(), process_frame_v2() (+4 more)

### Community 15 - "Legacy Camera Processing"
Cohesion: 0.12
Nodes (18): camera_frame(), capture_identity(), detect_faces(), draw_detections(), process_frame(), convert(), detected(), observation() (+10 more)

### Community 16 - "Streaming Protocol and Scheduling"
Cohesion: 0.12
Nodes (12): InferenceScheduler, pack_frame(), test_arbitrary_packet_cannot_escape_with_unexpected_error(), test_protocol_roundtrip_generated(), jpeg(), test_active_camera_pauses_offline_work_and_cancellation_still_works(), test_binary_frame_roundtrip_and_validation(), test_decoded_image_size_is_checked_before_expansion() (+4 more)

### Community 17 - "Studio Website Components"
Cohesion: 0.15
Nodes (21): api(), assetFile(), Examples, Fixture, Job, Pair, System, App() (+13 more)

### Community 18 - "Desktop Window Controls"
Cohesion: 0.12
Nodes (5): _emit_status(), MainWindow, _open_mapper_dialog(), render_image_preview(), update_status()

### Community 19 - "GPU Image Operations"
Cohesion: 0.14
Nodes (10): _cv_type_for(), _ensure_uint8(), gpu_add_weighted(), gpu_cvt_color(), gpu_flip(), gpu_resize(), gpu_sharpen(), is_gpu_accelerated() (+2 more)

### Community 20 - "Desktop Preview Controls"
Cohesion: 0.11
Nodes (9): predict_frame(), check_and_ignore_nsfw(), close_mapper_window(), _open_live_mapper_dialog(), _open_webcam_preview(), save_switch_states(), _update_tumbler(), has_image_extension() (+1 more)

### Community 21 - "Video Media Utilities"
Cohesion: 0.13
Nodes (8): create_video(), detect_fps(), estimate_frame_count(), get_temp_output_path(), move_temp(), restore_audio(), run_ffmpeg(), test_audio_is_preserved_and_silent_video_succeeds()

### Community 22 - "Media Regression Fixtures"
Cohesion: 0.10
Nodes (10): make_video(), preserve_state(), test_bad_model_hash_is_not_published(), test_incomplete_model_is_not_cached(), test_missing_permission_and_missing_face_are_errors(), test_model_hash_and_tls_are_verified(), test_pipe_does_not_reuse_previous_frame_detection(), test_pipe_preserves_duration_when_converting_fps() (+2 more)

### Community 23 - "Frame Processing Pipelines"
Cohesion: 0.14
Nodes (10): ensure_landmarks(), get_face_analyser(), load_frame_processor_module(), process_video_in_memory(), identity_metric(), swap_current(), _run_pipe_pipeline(), set_frame_processors_modules_from_ui() (+2 more)

### Community 24 - "Desktop Face Mapping"
Cohesion: 0.17
Nodes (5): add_blank_map(), has_valid_map(), simplify_maps(), LiveMapperDialog, MapperDialog

### Community 25 - "CoreML Graph Optimization"
Cohesion: 0.13
Nodes (7): _decompose_reflect_pad(), _decompose_split(), _fold_shape_gather(), optimize_for_coreml(), _preserve_emap_position(), _rewrite_scalar_gather(), test_coreml_cache_is_separated_by_input_shape()

### Community 26 - "Desktop Settings Panels"
Cohesion: 0.12
Nodes (6): get_available_cameras(), load_switch_states(), make(), make_circular_pixmap(), _make_image_drop(), _Switch

### Community 27 - "Browser Live Lifecycle"
Cohesion: 0.19
Nodes (11): Header, Person, quantile(), readPacket(), Metrics, useLive(), enroll(), ensureSession() (+3 more)

### Community 28 - "Face Masks and Regions"
Cohesion: 0.19
Nodes (9): gpu_gaussian_blur(), _ksize_odd(), apply_color_transfer(), apply_mask_area(), create_eyebrows_mask(), create_eyes_mask(), create_face_mask(), create_lower_mouth_mask() (+1 more)

### Community 29 - "Research and Export Jobs"
Cohesion: 0.24
Nodes (13): configure_runtime(), new_job(), probe_video(), process_image(), process_video(), quality(), read_image(), require_models() (+5 more)

### Community 32 - "Desktop Worker Threads"
Cohesion: 0.14
Nodes (3): _CaptureWorker, _ExportWorker, _ProcessingWorker

### Community 33 - "Browser Media Worker Bridge"
Cohesion: 0.19
Nodes (3): MediaBridge, Canvas, FakeWorker

### Community 34 - "Legacy Web Launchers"
Cohesion: 0.28
Nodes (7): build_app(), build_app(), capture_webcam_face(), image_experiment(), live_frame(), video_experiment(), test_browser_opens_live_with_webcam_only_input()

### Community 35 - "Frontend Runtime Dependencies"
Cohesion: 0.15
Nodes (13): dependencies, @fontsource-variable/roboto@^5.2.0, lucide-react@^0.468.0, motion@^12.23.0, react@^19.2.0, react-dom@^19.2.0, react-router-dom@^7.9.0, @fontsource-variable/roboto (+5 more)

### Community 36 - "TypeScript Compiler Configuration"
Cohesion: 0.15
Nodes (12): compilerOptions, allowImportingTsExtensions, jsx, lib, module, moduleResolution, noEmit, skipLibCheck (+4 more)

### Community 37 - "Model Parity Evaluation"
Cohesion: 0.21
Nodes (3): align(), MobileRuntime, validate()

### Community 38 - "Desktop Compatibility Adapters"
Cohesion: 0.18
Nodes (4): LanguageManager, init(), _UIBridge, _Window

### Community 39 - "CPU Container Configuration"
Cohesion: 0.18
Nodes (10): AIMS_EXECUTION_PROVIDER, build, cpus, environment, init, mem_limit, ports, restart (+2 more)

### Community 41 - "Preview Image Rendering"
Cohesion: 0.24
Nodes (5): _bgr_to_qpixmap(), fit_image_to_size(), _make_thumb(), _pil_to_qpixmap(), render_video_preview()

### Community 42 - "Installation Dependency Roles"
Cohesion: 0.22
Nodes (10): Shared requirements-core.txt inclusion, cv2_enumerate_cameras 1.1.15, Legacy desktop application dependencies, pygrabber on Windows only, PySide6 >=6.7,<7, Shared requirements-core.txt inclusion, FastAPI >=0.128,<1, python-multipart >=0.0.22,<1 (+2 more)

### Community 45 - "Video Preview Indexing"
Cohesion: 0.22
Nodes (4): get_video_frame(), get_video_frame_total(), PreviewWindow, test_preview_uses_zero_based_frame_index()

### Community 46 - "Hardware Platform Detection"
Cohesion: 0.25
Nodes (3): accelerator_label(), camera_backends(), print_banner()

### Community 48 - "Codec and Orientation Assurance"
Cohesion: 0.32
Nodes (4): test_ci_camera_fixture_works_with_manifest_but_without_downloaded_corpus(), test_exif_orientation_is_applied_before_processing(), test_rotated_video_export_uses_display_dimensions(), test_video_longer_than_audio_is_not_truncated()

### Community 49 - "Frontend Test Commands"
Cohesion: 0.29
Nodes (7): scripts, benchmark, build, dev, test, test:browser, test:unit

### Community 50 - "Frame Worker Ordering"
Cohesion: 0.33
Nodes (4): multi_process_frame(), process_video(), test_temporal_frames_run_in_order(), test_worker_errors_propagate()

### Community 53 - "Optional Content Classifier"
Cohesion: 0.67
Nodes (3): opennsfw2 0.10.2, Optional NSFW classifier dependencies, TensorFlow >=2.15,<2.20 for Python <3.13

## Knowledge Gaps
- **23 isolated node(s):** `Verified Model Downloads`, `Media Integrity Corrections`, `Material Studio Design`, `One-hour Browser Longevity`, `Digest-based Deployment Rollback` (+18 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 433 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **18 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `Desktop Window Controls` to `Desktop Settings Panels`, `Desktop Preview Controls`, `Desktop Compatibility Adapters`, `Desktop Processing Lifecycle`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **What connects `Verified Model Downloads`, `Media Integrity Corrections`, `Material Studio Design` to the rest of the system?**
  _23 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Evidence and Evaluation` be split into smaller, more focused modules?**
  _Cohesion score 0.05273047563123899 - nodes in this community are weakly interconnected._
- **Why does `imread_unicode()` connect `Face Analysis and Paths` to `Enhancer Runtime Dependencies`, `Face Swap Compositing`, `Desktop Processing Lifecycle`, `Live Inference Modules`, `Video Preview Indexing`, `Face Enhancement Pipeline`, `Desktop Preview Controls`, `Frame Processing Pipelines`, `Desktop Face Mapping`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Should `Enhancer Runtime Dependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.06775956284153005 - nodes in this community are weakly interconnected._
- **Why does `get_one_face()` connect `Face Swap Compositing` to `Enhancer Runtime Dependencies`, `Desktop Processing Lifecycle`, `Face Analysis and Paths`, `Video Preview Indexing`, `Legacy Camera Processing`, `Desktop Preview Controls`, `Frame Processing Pipelines`, `Desktop Face Mapping`, `Research and Export Jobs`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Should `HTTP API and Uploads` be split into smaller, more focused modules?**
  _Cohesion score 0.06219426974143955 - nodes in this community are weakly interconnected._
## Extraction Health and Scope

Graphify flagged 741 raw dangling-endpoint edges, 2 self-loop edges and 184 same-endpoint edge collapses in undirected construction. These are extraction limitations, not a verified complete call graph. Dynamic calls and excluded/external symbols may be unresolved.

One file (`pyproject.toml`) yielded no nodes; 22 code/configuration files yielded no symbols. All 25 semantic files have complete reported line coverage. Images, datasets, generated output and vendored code are excluded. See `docs/CODE_GRAPH.md` and `BUILD_AUDIT.json`.

`graphify-out/` is in the working tree. Portable graph outputs are committed; machine paths, intermediates and caches are ignored. Team workflow: https://docs.graphify.com/guides/team-workflows.
