# Graph Report - MorphLab  (2026-11-03)

## Corpus Check
- 161 files · ~86,244 words
- Verdict: corpus is large enough that graph structure adds value.
- Unclassified: 10 file(s) not represented in the graph (top: (none) 5, .lock 2, .vbs 1)

## Summary
- 1300 nodes · 3276 edges · 78 communities (54 shown, 24 thin omitted)
- Extraction: 95% EXTRACTED · 5% INFERRED · 0% AMBIGUOUS · INFERRED: 177 edges (avg confidence: 0.87)
- Host-agent token usage: unavailable; zero extraction counters are placeholders.

## Community Hubs (Navigation)
- Evidence and Evaluation
- HTTP API and Sessions
- Model Registry Validation
- Live Session Assurance
- Tracking and Temporal Tests
- CI Workflows
- Mobile Generator Architecture
- Desktop Processing Lifecycle
- Frontend Build Toolchain
- Desktop Capture Interface
- Frame Processing Pipeline
- Face Analysis and Paths
- Live Processing Modules
- GPU Masks and Geometry
- Media File Utilities
- Studio Website Components
- Media Regression Fixtures
- Legacy Camera Processing
- Face Enhancement Pipeline
- Desktop Window Controls
- Cancellable Media Exports
- Streaming Protocol Assurance
- Face Compositing Types
- CoreML Graph Optimization
- Legacy Face Swapper
- Browser Live Lifecycle
- Platform and CLI Startup
- Browser Workflow Configuration
- ONNX Enhancement Inference
- Camera Capture and Preview
- Research Processing Utilities
- Desktop Compatibility Adapters
- Container Release Assurance
- Desktop Worker Threads
- Browser Media Worker Bridge
- Desktop Live Mapping
- Legacy Web Launchers
- Model Data and Testing
- Frontend Runtime Dependencies
- TypeScript Compiler Configuration
- GPEN256 Enhancement
- Desktop Settings Panels
- Model Parity Evaluation
- Input Selection Controls
- GPEN512 Enhancement
- CPU Container Configuration
- Desktop Tooltip Helpers
- GPU Image Operations
- Desktop Control State
- Installation Dependency Roles
- Tkinter Compatibility Patches
- Architecture Map Navigation
- Live Tracking Tradeoffs
- Face Analyser Regression
- Source Target Mapping
- README Map Renderer
- Shared Capture Globals
- CUDA Graph Adapter
- Verified Model Downloads
- Frontend Test Commands
- Remote Archive Reader
- Platform Lock Assurance
- Hardware Runtime Decisions
- Privacy and Release Boundaries
- ONNX Session Providers
- Experiment Decision Policy
- Optional Content Classifier
- Paddle Reference Parity
- Media Worker Entrypoint
- Pinned NumPy Build
- Local Setup Script
- Mac Acceleration Setup
- Local Startup Script
- Project Metadata

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
- **Curated architecture overview traceability** — docs_code_graph_graphify, docs_code_graph_curated_overview, docs_code_graph_overview_source_mapping [EXTRACTED 1.00]
- **Runtime remediation with unchanged gate** — docs_decisions_wolfi_runtime, docs_security_container_gate, docs_security_wolfi_scan, docs_deployment_rebuild_evidence [EXTRACTED 1.00]
- **Quality-constrained live selection** — docs_experiments_selection_rule, docs_experiments_adaface, docs_experiments_browser_trials [EXTRACTED 1.00]
- **Remaining release acceptance boundary** — docs_release_gates, docs_release_manual_checks, docs_security_wolfi_scan, readme_research_candidate [EXTRACTED 1.00]
- **Separate code model and data rights** — docs_licensing_scope, docs_model_data_card_models, docs_model_data_card_ravdess [INFERRED 0.95]

## Communities (78 total, 24 thin omitted)

### Community 0 - "Evidence and Evaluation"
Cohesion: 0.06
Nodes (34): artifact_gate(), browser_gate(), fingerprint(), sha256(), validate_corpus(), write_report(), main(), main() (+26 more)

### Community 1 - "HTTP API and Sessions"
Cohesion: 0.06
Nodes (30): boundaries(), cancel_job(), clear_source(), create_session(), delete_session(), download(), enroll(), extract() (+22 more)

### Community 2 - "Model Registry Validation"
Cohesion: 0.09
Nodes (11): AdaFaceEvaluator, InferenceScheduler, ModelRegistry, RuntimeConfig, run_candidate(), test_dense_five_point_topology_matches_detector(), test_real_cpu_model_detect_enroll_swap(), test_real_light_tracking_returns_consistent_embedding_space() (+3 more)

### Community 3 - "Live Session Assurance"
Cohesion: 0.09
Nodes (24): analyse_source(), erase(), LiveSession, Track, main(), worker(), face(), test_appearance_ablation_exposes_crossing_tradeoff() (+16 more)

### Community 4 - "Tracking and Temporal Tests"
Cohesion: 0.16
Nodes (23): aligned_crop(), embedding(), FaceTracker, iou(), scene_changed(), stabilize(), TemporalProcessor, face() (+15 more)

### Community 5 - "CI Workflows"
Cohesion: 0.06
Nodes (36): if, runs-on, steps, runs-on, steps, strategy, AIMS_CPU_CI, jobs (+28 more)

### Community 6 - "Mobile Generator Architecture"
Cohesion: 0.08
Nodes (12): ArrayUnpickler, ConvBlock, final_layers(), Generator, IdentityEncoder, IdentityWeights, IRBlock, load_paddle() (+4 more)

### Community 7 - "Desktop Processing Lifecycle"
Cohesion: 0.12
Nodes (20): decode_execution_providers(), destroy(), encode_execution_providers(), limit_resources(), parse_args(), pre_check(), release_resources(), run() (+12 more)

### Community 8 - "Frontend Build Toolchain"
Cohesion: 0.10
Nodes (26): devDependencies, @axe-core/playwright@^4.14.0, daisyui@^5.7.0, @playwright/test@^1.56.0, tailwindcss@^4.1.0, @tailwindcss/vite@^4.1.0, @types/react@^19.2.0, @types/react-dom@^19.2.0 (+18 more)

### Community 9 - "Desktop Capture Interface"
Cohesion: 0.10
Nodes (10): gpu_cvt_color(), predict_frame(), _bgr_to_qpixmap(), check_and_ignore_nsfw(), fit_image_to_size(), _make_thumb(), _pil_to_qpixmap(), render_video_preview() (+2 more)

### Community 10 - "Frame Processing Pipeline"
Cohesion: 0.11
Nodes (16): ensure_landmarks(), get_face_analyser(), get_one_face(), load_frame_processor_module(), multi_process_frame(), process_video(), process_video_in_memory(), identity_metric() (+8 more)

### Community 11 - "Face Analysis and Paths"
Cohesion: 0.14
Nodes (16): find_closest_centroid(), find_cluster_centroids(), add_blank_map(), _analyse_faces(), default_target_face(), detect_many_faces_fast(), detect_one_face_fast(), dump_faces() (+8 more)

### Community 12 - "Live Processing Modules"
Cohesion: 0.12
Nodes (3): paste_face(), observe(), main()

### Community 13 - "GPU Masks and Geometry"
Cohesion: 0.13
Nodes (12): _cv_type_for(), gpu_gaussian_blur(), gpu_resize(), is_gpu_accelerated(), _ksize_odd(), apply_color_transfer(), apply_mask_area(), create_eyebrows_mask() (+4 more)

### Community 14 - "Media File Utilities"
Cohesion: 0.13
Nodes (13): create_temp(), create_video(), detect_fps(), estimate_frame_count(), extract_frames(), get_temp_directory_path(), get_temp_frame_paths(), get_temp_output_path() (+5 more)

### Community 15 - "Studio Website Components"
Cohesion: 0.15
Nodes (21): api(), assetFile(), Examples, Fixture, Job, Pair, System, App() (+13 more)

### Community 16 - "Media Regression Fixtures"
Cohesion: 0.09
Nodes (11): get_video_frame(), make_video(), preserve_state(), test_missing_permission_and_missing_face_are_errors(), test_model_hash_and_tls_are_verified(), test_model_provenance_does_not_become_a_gradio_file_download(), test_pipe_does_not_reuse_previous_frame_detection(), test_pipe_preserves_duration_when_converting_fps() (+3 more)

### Community 17 - "Legacy Camera Processing"
Cohesion: 0.12
Nodes (18): camera_frame(), capture_identity(), detect_faces(), draw_detections(), process_frame(), convert(), detected(), observation() (+10 more)

### Community 18 - "Face Enhancement Pipeline"
Cohesion: 0.14
Nodes (10): _align_face(), enhance_face(), _paste_back(), _postprocess_face(), _preprocess_face(), process_frame(), process_frame_v2(), process_frames() (+2 more)

### Community 19 - "Desktop Window Controls"
Cohesion: 0.12
Nodes (5): _emit_status(), MainWindow, _open_mapper_dialog(), render_image_preview(), update_status()

### Community 20 - "Cancellable Media Exports"
Cohesion: 0.18
Nodes (10): probe_video(), create_job(), edit_frame(), Job, run_job(), test_ci_camera_fixture_works_with_manifest_but_without_downloaded_corpus(), test_exif_orientation_is_applied_before_processing(), test_rotated_video_export_uses_display_dimensions() (+2 more)

### Community 21 - "Streaming Protocol Assurance"
Cohesion: 0.16
Nodes (12): pack_frame(), unpack_frame(), test_arbitrary_packet_cannot_escape_with_unexpected_error(), test_deeply_nested_header_is_a_friendly_validation_error(), test_protocol_roundtrip_generated(), jpeg(), test_binary_frame_roundtrip_and_validation(), test_decoded_image_size_is_checked_before_expansion() (+4 more)

### Community 22 - "Face Compositing Types"
Cohesion: 0.17
Nodes (11): apply_mouth_area(), _apply_poisson_blend(), _create_elliptical_mask(), create_face_mask(), create_lower_mouth_mask(), draw_mouth_mask_visualization(), _fast_paste_back(), get_faces_optimized() (+3 more)

### Community 23 - "CoreML Graph Optimization"
Cohesion: 0.13
Nodes (7): _decompose_reflect_pad(), _decompose_split(), _fold_shape_gather(), optimize_for_coreml(), _preserve_emap_position(), _rewrite_scalar_gather(), test_coreml_cache_is_separated_by_input_shape()

### Community 24 - "Legacy Face Swapper"
Cohesion: 0.16
Nodes (10): default_source_face(), apply_color_transfer(), get_face_swapper(), _init_cuda_graph_session(), pre_start(), process_frame(), process_frame_v2(), process_frames() (+2 more)

### Community 25 - "Browser Live Lifecycle"
Cohesion: 0.19
Nodes (11): Header, Person, quantile(), readPacket(), Metrics, useLive(), enroll(), ensureSession() (+3 more)

### Community 26 - "Platform and CLI Startup"
Cohesion: 0.12
Nodes (3): accelerator_label(), camera_backends(), print_banner()

### Community 28 - "ONNX Enhancement Inference"
Cohesion: 0.19
Nodes (5): enhance_face_onnx(), _get_face_affine(), postprocess_face(), preprocess_face(), run_inference()

### Community 30 - "Research Processing Utilities"
Cohesion: 0.27
Nodes (10): configure_runtime(), new_job(), process_image(), process_video(), quality(), read_image(), require_models(), watermark() (+2 more)

### Community 31 - "Desktop Compatibility Adapters"
Cohesion: 0.14
Nodes (5): LanguageManager, init(), PreviewWindow, _UIBridge, _Window

### Community 32 - "Container Release Assurance"
Cohesion: 0.20
Nodes (8): Non-root CPU Container, Platform-aware Universal Dependency Lock, Required Release Gates, Digest-based Deployment Rollback, Historical Debian Container Scan Failure, Patched Maintained Python Dependencies, Passing Local Wolfi HIGH/CRITICAL Scan, Development Assurance Tools

### Community 33 - "Desktop Worker Threads"
Cohesion: 0.14
Nodes (3): _CaptureWorker, _ExportWorker, _ProcessingWorker

### Community 34 - "Browser Media Worker Bridge"
Cohesion: 0.19
Nodes (3): MediaBridge, Canvas, FakeWorker

### Community 35 - "Desktop Live Mapping"
Cohesion: 0.24
Nodes (4): close_mapper_window(), LiveMapperDialog, _open_live_mapper_dialog(), _open_webcam_preview()

### Community 36 - "Legacy Web Launchers"
Cohesion: 0.28
Nodes (7): build_app(), build_app(), capture_webcam_face(), image_experiment(), live_frame(), video_experiment(), test_browser_opens_live_with_webcam_only_input()

### Community 37 - "Model Data and Testing"
Cohesion: 0.18
Nodes (10): Media Integrity Corrections, Verified Model Downloads, One-hour Browser Longevity, Pretrained Model Roles, Identity-partitioned RAVDESS Corpus, Pending Physical Webcam and Safari Review, Deferred Foreground Occlusion Segmentation, Native CoreML Precision Parity (+2 more)

### Community 38 - "Frontend Runtime Dependencies"
Cohesion: 0.15
Nodes (13): dependencies, @fontsource-variable/roboto@^5.2.0, lucide-react@^0.468.0, motion@^12.23.0, react@^19.2.0, react-dom@^19.2.0, react-router-dom@^7.9.0, @fontsource-variable/roboto (+5 more)

### Community 39 - "TypeScript Compiler Configuration"
Cohesion: 0.15
Nodes (12): compilerOptions, allowImportingTsExtensions, jsx, lib, module, moduleResolution, noEmit, skipLibCheck (+4 more)

### Community 40 - "GPEN256 Enhancement"
Cohesion: 0.28
Nodes (8): enhance_face(), get_enhancer(), process_frame(), process_frame_v2(), process_frames(), process_image(), process_video(), warmup_session()

### Community 41 - "Desktop Settings Panels"
Cohesion: 0.18
Nodes (4): get_available_cameras(), load_switch_states(), make_circular_pixmap(), _make_image_drop()

### Community 42 - "Model Parity Evaluation"
Cohesion: 0.24
Nodes (5): align(), MobileRuntime, reference(), run_reference(), validate()

### Community 43 - "Input Selection Controls"
Cohesion: 0.27
Nodes (10): update_status(), pre_check(), pre_start(), pre_check(), pre_start(), pre_check(), pre_start(), analyse() (+2 more)

### Community 44 - "GPEN512 Enhancement"
Cohesion: 0.33
Nodes (8): imwrite_unicode(), enhance_face(), get_enhancer(), process_frame(), process_frame_v2(), process_frames(), process_image(), process_video()

### Community 45 - "CPU Container Configuration"
Cohesion: 0.18
Nodes (10): AIMS_EXECUTION_PROVIDER, build, cpus, environment, init, mem_limit, ports, restart (+2 more)

### Community 47 - "GPU Image Operations"
Cohesion: 0.25
Nodes (5): _ensure_uint8(), gpu_add_weighted(), gpu_flip(), gpu_sharpen(), apply_post_processing()

### Community 48 - "Desktop Control State"
Cohesion: 0.24
Nodes (4): make(), save_switch_states(), _Switch, _update_tumbler()

### Community 49 - "Installation Dependency Roles"
Cohesion: 0.22
Nodes (10): Shared requirements-core.txt inclusion, cv2_enumerate_cameras 1.1.15, Legacy desktop application dependencies, pygrabber on Windows only, PySide6 >=6.7,<7, Shared requirements-core.txt inclusion, FastAPI >=0.128,<1, python-multipart >=0.0.22,<1 (+2 more)

### Community 51 - "Architecture Map Navigation"
Cohesion: 0.28
Nodes (6): Session Isolation and Disconnect Cleanup, Graphify Code and Documentation Map, LiveSession Graph Queries, Validated Overview Source Mapping, MorphLab Web Entry, MorphLab

### Community 52 - "Live Tracking Tradeoffs"
Cohesion: 0.22
Nodes (5): Material Studio Design, M4 Browser Replay Trials, Appearance-gated Identity Continuity, Historical Gentle Portrait Replay, Historical CPU Motion Baseline

### Community 55 - "README Map Renderer"
Cohesion: 0.43
Nodes (5): main(), node(), path(), render(), text()

### Community 58 - "Verified Model Downloads"
Cohesion: 0.29
Nodes (5): pre_check(), conditional_download(), main(), test_bad_model_hash_is_not_published(), test_incomplete_model_is_not_cached()

### Community 59 - "Frontend Test Commands"
Cohesion: 0.29
Nodes (7): scripts, benchmark, build, dev, test, test:browser, test:unit

### Community 65 - "Experiment Decision Policy"
Cohesion: 0.67
Nodes (3): Offline AdaFace Validation, Pinned Three-way Baselines, Comparative Engineering Evidence

### Community 66 - "Optional Content Classifier"
Cohesion: 0.67
Nodes (3): opennsfw2 0.10.2, Optional NSFW classifier dependencies, TensorFlow >=2.15,<2.20 for Python <3.13

## Knowledge Gaps
- **26 isolated node(s):** `morphlab`, `Verified Model Downloads`, `Media Integrity Corrections`, `Session Isolation and Disconnect Cleanup`, `Material Studio Design` (+21 more)
  These have ≤1 connection - possible missing edges or undocumented components. (Counts symbols only; 441 node(s) total have ≤1 connection when file, concept and rationale nodes are included.)
- **24 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `MainWindow` connect `Desktop Window Controls` to `Desktop Live Mapping`, `Desktop Capture Interface`, `Desktop Settings Panels`, `Input Selection Controls`, `Desktop Control State`, `Desktop Compatibility Adapters`?**
  _High betweenness centrality (0.032) - this node is a cross-community bridge._
- **What connects `morphlab`, `Verified Model Downloads`, `Media Integrity Corrections` to the rest of the system?**
  _26 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Evidence and Evaluation` be split into smaller, more focused modules?**
  _Cohesion score 0.059008654602675056 - nodes in this community are weakly interconnected._
- **Why does `imread_unicode()` connect `Face Analysis and Paths` to `Desktop Live Mapping`, `Tracking and Temporal Tests`, `Desktop Processing Lifecycle`, `GPEN256 Enhancement`, `Desktop Capture Interface`, `Frame Processing Pipeline`, `Live Processing Modules`, `GPEN512 Enhancement`, `Face Enhancement Pipeline`, `Cancellable Media Exports`, `Source Target Mapping`, `Legacy Face Swapper`?**
  _High betweenness centrality (0.022) - this node is a cross-community bridge._
- **Should `HTTP API and Sessions` be split into smaller, more focused modules?**
  _Cohesion score 0.06377551020408163 - nodes in this community are weakly interconnected._
- **Why does `get_one_face()` connect `Frame Processing Pipeline` to `Desktop Live Mapping`, `Desktop Processing Lifecycle`, `GPEN256 Enhancement`, `Desktop Capture Interface`, `Face Analysis and Paths`, `Live Processing Modules`, `GPEN512 Enhancement`, `Legacy Camera Processing`, `Face Compositing Types`, `Source Target Mapping`, `Legacy Face Swapper`, `Research Processing Utilities`?**
  _High betweenness centrality (0.021) - this node is a cross-community bridge._
- **Should `Model Registry Validation` be split into smaller, more focused modules?**
  _Cohesion score 0.08776595744680851 - nodes in this community are weakly interconnected._
## Extraction health and overview scope

The refreshed extraction has 750 dangling-endpoint references, 2 self-loops and 186 same-endpoint edge collapses during undirected construction. Dynamic/external references can remain unresolved. Twenty-three code/configuration files yielded no symbols; all 25 semantic files are represented and all seven changed files had complete line coverage. This is a navigation aid, not a lossless verified call graph.

The README SVGs group reviewed source responsibilities into six parts; these are not the 78 algorithmic communities above. Node/file membership is exported in `OVERVIEW.json`. Runtime changes through the Wolfi/container CI remediation are included. See `BUILD_AUDIT.json` for scope and warnings.

`graphify-out/` lives in the working tree. Portable outputs are shared; local paths, caches and extraction intermediates are ignored. Team workflow: https://docs.graphify.com/guides/team-workflows.
