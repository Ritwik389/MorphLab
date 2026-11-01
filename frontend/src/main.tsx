import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  BrowserRouter,
  Link,
  NavLink,
  Route,
  Routes,
  useLocation,
} from "react-router-dom";
import { MotionConfig, motion, useReducedMotion } from "motion/react";
import {
  ArrowRight,
  ArrowUpRight,
  Camera,
  Check,
  ChevronRight,
  Download,
  ChevronsLeftRight,
  Image as ImageIcon,
  Info,
  Monitor,
  Play,
  ScanFace,
  Square,
  Sun,
  Upload,
  Video,
  X,
} from "lucide-react";
import "@fontsource-variable/roboto";
import "./styles.css";
import {
  api,
  assetFile,
  type Examples,
  type Job,
  type Pair,
  type System,
} from "./api";
import { useLive } from "./useLive";

const emptyExamples: Examples = { pairs: [], fixtures: [], credits: [] };
function Brand() {
  return (
    <Link to="/" className="brand" aria-label="MorphLab home">
      <svg
        width="30"
        height="30"
        viewBox="0 0 30 30"
        fill="none"
        aria-hidden="true"
      >
        <path
          d="M5 23V7l10 11L25 7v16"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
      MorphLab
    </Link>
  );
}
function ErrorMessage({ message }: { message: string }) {
  return message ? (
    <div className="alert alert-error alert-soft" role="alert">
      <Info size={19} />
      <span>{message}</span>
    </div>
  ) : null;
}
function App() {
  const [examples, setExamples] = useState<Examples>(emptyExamples),
    [error, setError] = useState("");
  const location = useLocation();
  useEffect(() => {
    api<Examples>("/api/examples")
      .then(setExamples)
      .catch((e) => setError(e.message));
  }, []);
  useEffect(() => {
    window.scrollTo({ top: 0 });
    const names: Record<string, string> = {
      "/": "Face editing studio",
      "/studio": "Studio",
      "/how-it-works": "How it works",
    };
    document.title = `MorphLab · ${names[location.pathname] || "Not found"}`;
  }, [location.pathname]);
  function theme() {
    const current = document.documentElement.dataset.theme;
    document.documentElement.dataset.theme =
      current === "aims-dark" ? "aims" : "aims-dark";
  }
  return (
    <>
      <header className="site-header">
        <div className="nav-frame">
          <Brand />
          <nav aria-label="Main navigation">
            <NavLink to="/" end>
              Overview
            </NavLink>
            <NavLink to="/studio">Studio</NavLink>
            <NavLink to="/how-it-works">How it works</NavLink>
          </nav>
          <button
            onClick={theme}
            className="btn btn-ghost btn-circle theme-button"
            aria-label="Toggle color theme"
          >
            <Sun size={20} />
          </button>
        </div>
      </header>
      <ErrorMessage message={error} />
      <main id="main">
        <Routes>
          <Route path="/" element={<Landing />} />
          <Route path="/studio" element={<Studio examples={examples} />} />
          <Route
            path="/how-it-works"
            element={<HowItWorks examples={examples} />}
          />
          <Route
            path="*"
            element={
              <div className="page-frame">
                <h1>Page not found</h1>
                <Link className="btn" to="/">
                  Go home
                </Link>
              </div>
            }
          />
        </Routes>
      </main>
      <footer className="site-footer">
        <Brand />
        <p>Face editing, with room to experiment.</p>
        <Link to="/how-it-works#credits">
          Sample credits <ArrowUpRight size={15} />
        </Link>
      </footer>
    </>
  );
}
function Reveal({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  const reduced = useReducedMotion();
  if (reduced) return <div className={className}>{children}</div>;
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 16 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.15 }}
      transition={{ duration: 0.35 }}
    >
      {children}
    </motion.div>
  );
}
function Compare({
  before,
  after,
  landing = false,
}: {
  before: string;
  after: string;
  landing?: boolean;
}) {
  const [position, setPosition] = useState(50);
  return (
    <div className={`comparison ${landing ? "hero-comparison" : ""}`}>
      <img src={before} alt="Original target portrait" />
      <img
        className="comparison-after"
        src={after}
        alt="Edited portrait produced by MorphLab"
        style={{ clipPath: `inset(0 ${100 - position}% 0 0)` }}
      />
      <span className="image-label before-label">Original</span>
      <span className="image-label after-label">MorphLab result</span>
      <div className="comparison-line" style={{ left: `${position}%` }}>
        <span aria-hidden="true">
          <ChevronsLeftRight size={19} />
        </span>
      </div>
      <input
        aria-label="Compare original and edited image"
        type="range"
        min="0"
        max="100"
        value={position}
        onChange={(e) => setPosition(Number(e.target.value))}
      />
    </div>
  );
}
function Landing() {
  return (
    <>
      <section className="hero-section page-frame">
        <div className="hero-copy">
          <Reveal>
            <h1>
              A new face.
              <br />
              Your expression.
            </h1>
          </Reveal>
          <Reveal>
            <p>
              Explore face swapping with your camera, photos, and videos. Create
              a result, compare it, and see how it was made.
            </p>
          </Reveal>
          <Reveal className="hero-actions">
            <Link className="btn btn-primary btn-lg" to="/studio">
              Open Studio <ArrowRight size={19} />
            </Link>
            <Link className="text-action" to="/studio?mode=photo">
              Try an example <ChevronRight size={18} />
            </Link>
          </Reveal>
          <Reveal className="local-note">
            <Monitor size={17} />
            <span>Built for local experiments</span>
          </Reveal>
        </div>
        <Reveal className="hero-media">
          <Compare
            before="/examples/target.jpg"
            after="/examples/demo-result.jpg"
            landing
          />
          <div className="demo-caption">
            <div className="source-mini">
              <img
                src="/examples/source.png"
                alt="Eileen Collins, sample source"
              />
              <div>
                <span>Source identity</span>
                <strong>Eileen Collins</strong>
              </div>
            </div>
            <p>
              Actual sample output
              <br />
              <Link to="/how-it-works#credits">Public-domain portraits</Link>
            </p>
          </div>
        </Reveal>
      </section>
      <section className="capabilities page-frame">
        <Reveal className="section-heading">
          <h2>Choose your canvas.</h2>
          <p>One studio. Three ways to experiment.</p>
        </Reveal>
        <div className="mode-links">
          <Reveal>
            <Link to="/studio?mode=live">
              <Camera size={27} />
              <h3>Live camera</h3>
              <p>
                Detect faces, choose an identity, and see your camera
                transformed as you move.
              </p>
              <span>
                Start with your camera <ArrowRight size={18} />
              </span>
            </Link>
          </Reveal>
          <Reveal>
            <Link to="/studio?mode=photo">
              <ImageIcon size={27} />
              <h3>Photo</h3>
              <p>
                Try a sample pair or bring your own. Slide between the original
                and your result.
              </p>
              <span>
                Try a photo <ArrowRight size={18} />
              </span>
            </Link>
          </Reveal>
          <Reveal>
            <Link to="/studio?mode=video">
              <Video size={27} />
              <h3>Short video</h3>
              <p>
                Apply an identity across a clip, follow progress, and download
                the edit with audio.
              </p>
              <span>
                Edit a video <ArrowRight size={18} />
              </span>
            </Link>
          </Reveal>
        </div>
      </section>
      <section className="explain-band">
        <div className="page-frame explain-inner">
          <Reveal>
            <h2>No mystery controls.</h2>
            <p>
              The source provides the identity. The target provides the
              expression, pose, and scene. MorphLab combines them, then lets you
              inspect the result.
            </p>
            <Link className="text-action" to="/how-it-works">
              See how it works <ArrowRight size={18} />
            </Link>
          </Reveal>
          <Reveal className="visual-equation">
            <figure>
              <img src="/examples/source.png" alt="Source portrait" />
              <figcaption>Identity</figcaption>
            </figure>
            <ArrowRight size={24} />
            <figure>
              <img src="/examples/target.jpg" alt="Target portrait" />
              <figcaption>Expression + scene</figcaption>
            </figure>
            <ArrowRight size={24} />
            <figure>
              <img
                src="/examples/demo-result.jpg"
                alt="Actual edited portrait"
              />
              <figcaption>Your result</figcaption>
            </figure>
          </Reveal>
        </div>
      </section>
    </>
  );
}
function Studio({ examples }: { examples: Examples }) {
  const location = useLocation();
  const query = new URLSearchParams(location.search).get("mode");
  const mode = ["live", "photo", "video"].includes(query || "")
    ? query!
    : "live";
  const [system, setSystem] = useState<System | null>(null);
  useEffect(() => {
    const update = () =>
      api<System>("/api/system")
        .then(setSystem)
        .catch(() => {});
    void update();
    const id = setInterval(update, 3000);
    return () => clearInterval(id);
  }, []);
  return (
    <div className="page-frame studio">
      <div className="studio-title">
        <div>
          <h1>Your Studio</h1>
          <p>Pick a medium. Make it yours.</p>
        </div>
        <div className="device-indicator">
          <Monitor size={17} />
          <span>
            {mode === "live" && system?.live_runtime
              ? system.live_runtime
              : system?.state === "ready"
                ? system.active_runtime?.startsWith("Native")
                  ? "Mac · Native CoreML"
                  : system.active_runtime
                : system?.apple_silicon
                  ? "Apple Silicon · automatic"
                  : system
                    ? `${system.os} · automatic`
                    : "Connecting…"}
          </span>
        </div>
      </div>
      <nav className="tabs tabs-box studio-tabs" aria-label="Studio mode">
        {[
          ["live", "Live camera", Camera],
          ["photo", "Photo", ImageIcon],
          ["video", "Video", Video],
        ].map(([value, label, Icon]) => (
          <Link
            key={value as string}
            className={`tab ${mode === value ? "tab-active" : ""}`}
            aria-current={mode === value ? "page" : undefined}
            to={`/studio?mode=${value}`}
          >
            {React.createElement(Icon as typeof Camera, { size: 18 })}
            {label as string}
          </Link>
        ))}
      </nav>
      {mode === "live" ? (
        <LiveStudio examples={examples} system={system} />
      ) : (
        <MediaEditor key={mode} kind={mode} examples={examples} />
      )}
      <EvaluationSummary />
      <details className="advanced system-details">
        <summary>Processing & hardware</summary>
        <p>
          Processing runs on the machine hosting MorphLab. On this local app, that
          is your computer. CoreML chooses compatible Apple GPU, Neural Engine,
          and CPU operations.
        </p>
        <dl>
          <div>
            <dt>Export model readiness</dt>
            <dd>{system?.state || "Connecting"}</dd>
          </div>
          <div>
            <dt>Selected export runtime</dt>
            <dd>
              {system?.active_runtime ||
                "Loads when you choose a swap identity"}
            </dd>
          </div>
          {system?.live_runtime && (
            <div>
              <dt>Selected live runtime</dt>
              <dd>{system.live_runtime}</dd>
            </div>
          )}
          {system?.benchmark && (
            <div>
              <dt>Saved model benchmark</dt>
              <dd>
                {system.benchmark.mean_ms.toFixed(1)} ms ·{" "}
                {system.benchmark.precision.toUpperCase()} · model only
              </dd>
            </div>
          )}
          {system?.fallback_reason && (
            <div>
              <dt>Runtime note</dt>
              <dd>{system.fallback_reason}</dd>
            </div>
          )}
        </dl>
        <p>
          Live FPS is measured separately below the preview. Model inference
          speed alone does not establish webcam performance.
        </p>
      </details>
    </div>
  );
}
function EvaluationSummary() {
  const [data,setData] = useState<{status:string;note:string;stale?:boolean;suite?:string;release_status?:string;run?:string;report?:string;checks:{name:string;status:string}[]} | null>(null);
  return <details className="advanced evaluation-status" onToggle={(event)=>{
    if(event.currentTarget.open) void api<any>("/api/evaluation").then(setData).catch(()=>setData(null));
  }}><summary>Testing & evaluation</summary>
    {data ? <><p><strong>{data.suite || "Verification"}: {data.status}</strong>{data.run ? ` · ${data.run}` : ""}</p><p>{data.stale ? "This report predates the current app code. Rerun verification." : ""}</p><p>Full release acceptance: <strong>{data.release_status || "Not Run"}</strong></p><p>{data.note}</p>
    <div className="overflow-x-auto"><table className="table table-sm"><tbody>{data.checks.map(check=><tr key={check.name}><td>{check.name}</td><td>{check.status}</td></tr>)}</tbody></table></div>
    {data.report && <a className="btn btn-outline btn-sm" href={data.report} download>Download verification report</a>}</> : <p>Open this section to load the latest local verification report.</p>}
  </details>;
}
function LiveStudio({
  examples,
  system,
}: {
  examples: Examples;
  system: System | null;
}) {
  const [mode, setMode] = useState("detect");
  const live = useLive(mode);
  useEffect(() => { if (live.source) setMode("swap"); }, [live.source]);
  const [selected, setSelected] = useState("");
  function sample(value: string) {
    setSelected(value);
    if (!value) return;
    const data = new FormData();
    data.set("example", value);
    void live.enroll(
      data,
      examples.pairs.find((p) => p.source === value)?.name.split(" → ")[0] ||
        "Sample identity",
    );
  }
  return (
    <div className="studio-workspace">
      <aside className="control-panel">
        <div className="control-group camera-actions">
          <button
            className={`btn ${live.running ? "btn-outline" : "btn-primary"} w-full`}
            disabled={live.starting}
            onClick={() => (live.running ? live.stop() : void live.start())}
          >
            {live.running ? <Square size={17} /> : <Camera size={18} />}{" "}
            {live.starting
              ? "Connecting camera…"
              : live.running
                ? "Stop camera"
                : "Start camera"}
          </button>
          {live.starting && (
            <button className="btn btn-ghost" onClick={live.stop}>
              Cancel
            </button>
          )}
          <p className="hint">
            Camera access stays off until you start it. Choose people and media
            you have permission to edit.
          </p>
        </div>
        <div className="control-group">
          <h2>Camera effect</h2>
          <p>Detection starts without a source image.</p>
          <label className="field-label" htmlFor="live-effect">
            Effect
          </label>
          <select
            id="live-effect"
            className="select w-full"
            value={mode}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="detect">Detect faces</option>
            <option value="swap">Swap identity</option>
            <option value="blur">Blur faces</option>
            <option value="pixelate">Pixelate faces</option>
          </select>
        </div>
        {(
          <div className="control-group">
            <h2>Source identity</h2>
            <p>Whose face should appear in your camera?</p>
            <label className="field-label" htmlFor="sample-identity">
              Choose a sample
            </label>
            <select
              className="select w-full"
              id="sample-identity"
              value={selected}
              disabled={live.busy}
              onChange={(e) => sample(e.target.value)}
            >
              <option value="">Choose a portrait</option>
              {examples.pairs.map((p) => (
                <option key={p.id} value={p.source}>
                  {p.name.split(" → ")[0]}
                </option>
              ))}
            </select>
            <label className="upload-button btn btn-outline">
              <Upload size={17} />
              Upload portrait
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp"
                disabled={live.busy}
                onChange={(e) => {
                  const file = e.target.files?.[0];
                  if (file) {
                    const data = new FormData();
                    data.set("file", file);
                    setSelected("");
                    void live.enroll(data, file.name);
                  }
                  e.target.value = "";
                }}
              />
            </label>
            <button
              className="btn btn-soft w-full"
              disabled={!live.running || live.busy}
              onClick={() => {
                const data = new FormData();
                data.set("camera", "true");
                setSelected("");
                void live.enroll(data, "Camera capture");
              }}
            >
              <Camera size={17} />
              Capture camera face
            </button>
            {live.busy ? (
              <p className="preparing" role="status">
                Preparing identity and warming model…
              </p>
            ) : live.source ? (
              <div className="source-ready">
                <Check size={17} />
                <span>{live.source}</span>
                <button
                  className="btn btn-ghost btn-circle btn-sm"
                  aria-label="Clear source identity"
                  onClick={() => {
                    void live.clear();
                    setSelected("");
                  }}
                >
                  <X size={15} />
                </button>
              </div>
            ) : (
              <p className="hint">A source is required only for swapping.</p>
            )}
            <p className="hint">
              Live prioritizes speed. Photo and Video use the standard model for
              stronger identity matching. Capturing your own face may look
              unchanged.
            </p>
          </div>
        )}
      </aside>
      <div className="preview-column">
        <ErrorMessage message={live.error} />
        {live.notice && <p role="status" className="source-advice">{live.notice}</p>}
        {live.checks && <div className="source-advice" role="status">
          <strong>{live.checks.status === "ready" ? "Source ready" : "Source guidance"}</strong>
          {live.checks.warnings.map((warning)=><p key={warning}>{warning}</p>)}
        </div>}
        <div className={`camera-stage ${live.running ? "is-running" : ""}`}>
          <video
            ref={live.video}
            autoPlay
            playsInline
            muted
            className="camera-input"
            aria-label="Unprocessed camera preview"
          />
          <canvas
            ref={live.canvas}
            className="camera-output"
            aria-label="Processed camera preview"
          />
          {!live.running && (
            <div className="camera-empty">
              <ScanFace size={54} strokeWidth={1.25} />
              <h2>Your camera, ready when you are.</h2>
              <p>
                Start the camera to detect faces.
                <br />
                Choose Swap identity to try a new face.
              </p>
            </div>
          )}
          {live.running && (
            <span className="camera-live-label">
              {mode === "swap" ? "Swap preview" : "Live preview"}
            </span>
          )}
        </div>
        <div className="preview-caption">
          <span>{live.metrics?.message || "Camera is off"}</span>
          <span>{live.metrics?.resolution || "Up to 640 × 480"}</span>
        </div>
        {live.people.length > 0 && (
          <div className="people-picker" aria-label="Choose the person to swap">
            <button className={`btn btn-sm ${live.metrics?.selectionMode === "auto" ? "btn-primary" : "btn-outline"}`}
              aria-pressed={live.metrics?.selectionMode === "auto"} onClick={live.automatic}>Auto</button>
            {live.people.map((person)=>(
              <button key={person.id} disabled={!person.visible}
                className={`btn person-button ${live.metrics?.selected === person.id ? "btn-soft btn-primary" : "btn-ghost"}`}
                aria-pressed={live.metrics?.selected === person.id} onClick={()=>live.select(person.id)}>
                <span className="avatar"><div><img src={person.thumbnail} alt="" /></div></span>
                <span>{person.label}<small>{live.metrics?.selected === person.id ? "Selected" : person.visible ? "Choose person" : "Temporarily away"}</small></span>
              </button>
            ))}
          </div>
        )}
        <div className="session-actions"><button className="btn btn-ghost btn-sm"
          onClick={()=>{setSelected("");void live.purge();}}>Clear session data</button></div>
        <details className="advanced" onToggle={(e)=>live.setProfile(e.currentTarget.open)}>
          <summary>Live performance</summary>
          {live.metrics ? (
            <>
              <dl className="metric-grid">
                {[
                  ["Processed", `${live.metrics.processed.toFixed(1)} FPS`],
                  ["Swapped", `${live.metrics.swapped.toFixed(1)} FPS`],
                  [
                    "Displayed swaps",
                    `${live.metrics.displayed.toFixed(1)} FPS`,
                  ],
                  [
                    "Capture to display",
                    `${Math.round(live.metrics.latency)} ms`,
                  ],
                  [
                    "Backend processing",
                    `${Math.round(live.metrics.backend)} ms`,
                  ],
                  ["Replaced stale frames", live.metrics.dropped],
                  ["Rolling latency p50 / p95", `${Math.round(live.metrics.p50)} / ${Math.round(live.metrics.p95)} ms`],
                  ["Processing path", live.metrics.mediaPath],
                  ["Tracking", live.metrics.targetStatus || "Searching"],
                  ["MPS tensors / driver", live.metrics.gpu !== undefined ? `${live.metrics.gpu.toFixed(0)} / ${live.metrics.gpuDriver?.toFixed(0)} MiB` : "Unavailable"],
                  ["Process memory", live.metrics.memory ? `${live.metrics.memory.toFixed(0)} MiB` : "Unavailable (open profiler)"],
                ].map(([label, value]) => (
                  <div key={label}>
                    <dt>{label}</dt>
                    <dd>{value}</dd>
                  </div>
                ))}
              </dl>
              <div className="overflow-x-auto"><table className="table table-sm profiler-table">
                <caption>Latest frame stages · CPU wall time, including output transfer</caption>
                <tbody>{Object.entries(live.metrics.stages).map(([stage,ms])=><tr key={stage}>
                  <td>{stage.replaceAll("_", " ").replace(/ ms$/, "")}</td><td>{ms.toFixed(1)} ms</td>
                </tr>)}</tbody>
              </table></div>
              <p className="hint">15 FPS budget: 66.7 ms · 30 FPS stretch: 33.3 ms. Stage durations are not independent GPU kernel timings. MPS figures cover Torch tensors and driver allocation, including cached memory. Browser heap and non-MPS GPU memory are unavailable.</p>
              <p>
                Swapped FPS counts newly generated face swaps. It is zero in
                detection mode. The target is 15 FPS; the numbers above are
                measured from this session.
              </p>
            </>
          ) : (
            <p>Start the camera to measure performance.</p>
          )}
        </details>
      </div>
    </div>
  );
}
function usePreview(file: File | null, url: string) {
  const [preview, setPreview] = useState(url);
  useEffect(() => {
    if (!file) {
      setPreview(url);
      return;
    }
    const object = URL.createObjectURL(file);
    setPreview(object);
    return () => URL.revokeObjectURL(object);
  }, [file, url]);
  return preview;
}
function MediaEditor({ kind, examples }: { kind: string; examples: Examples }) {
  const [pair, setPair] = useState<Pair | null>(null),
    [source, setSource] = useState<File | null>(null),
    [target, setTarget] = useState<File | null>(null);
  const [mode, setMode] = useState("swap"),
    [strength, setStrength] = useState(1),
    [many, setMany] = useState(false),
    [consent, setConsent] = useState(false);
  const [job, setJob] = useState<Job | null>(null),
    [submitting, setSubmitting] = useState(false),
    [error, setError] = useState("");
  const sourcePreview = usePreview(source, pair?.source || ""),
    targetPreview = usePreview(
      target,
      kind === "photo" ? pair?.target || "" : "",
    );
  useEffect(() => {
    if (examples.pairs.length && !pair) setPair(examples.pairs[0]);
  }, [examples]);
  useEffect(() => {
    if (!job || !["queued", "running"].includes(job.state)) return;
    const timer = setInterval(() => {
      void api<Job>(`/api/jobs/${job.id}`)
        .then(setJob)
        .catch((e) => setError(e.message));
    }, 500);
    return () => clearInterval(timer);
  }, [job?.id, job?.state]);
  useEffect(() => {
    const id = sessionStorage.getItem("aims-job-" + kind);
    if (id)
      void api<Job>(`/api/jobs/${id}`)
        .then(setJob)
        .catch(() => sessionStorage.removeItem("aims-job-" + kind));
  }, [kind]);
  const active =
    submitting || (!!job && ["queued", "running"].includes(job.state));
  async function run() {
    setError("");
    setSubmitting(true);
    setJob(null);
    try {
      const data = new FormData();
      data.set("kind", kind);
      data.set("mode", mode);
      data.set("strength", String(strength));
      data.set("many", String(many));
      data.set("consent", String(consent));
      if (mode === "swap") {
        if (!source && !pair) throw new Error("Choose a source portrait.");
        data.set("source", source || (await assetFile(pair!.source)));
      }
      if (!target && (kind === "video" || !pair))
        throw new Error("Choose a target file.");
      data.set("target", target || (await assetFile(pair!.target)));
      const created = await api<Job>("/api/jobs", {
        method: "POST",
        body: data,
      });
      sessionStorage.setItem("aims-job-" + kind, created.id);
      setJob(created);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSubmitting(false);
    }
  }
  return (
    <div className="studio-workspace">
      <aside className="control-panel">
        <div className="control-group">
          <h2>Try a sample pair</h2>
          <p>
            Portraits are ready to use. Processing starts when you choose
            Create.
          </p>
          <label className="field-label" htmlFor="pair">
            Source → target
          </label>
          <select
            id="pair"
            className="select w-full"
            disabled={active}
            value={pair?.id || ""}
            onChange={(e) => {
              setPair(
                examples.pairs.find((p) => p.id === e.target.value) || null,
              );
              setSource(null);
              setTarget(null);
              setJob(null);
            }}
          >
            {examples.pairs.map((p) => (
              <option key={p.id} value={p.id}>
                {p.name}
              </option>
            ))}
          </select>
        </div>
        <div className="control-group">
          <h2>Source identity</h2>
          {sourcePreview && (
            <img
              className="source-portrait"
              src={sourcePreview}
              alt="Selected source portrait"
            />
          )}
          <label className="upload-button btn btn-outline">
            <Upload size={17} />
            Change source
            <input
              type="file"
              accept="image/jpeg,image/png,image/webp"
              disabled={active}
              onChange={(e) => {
                setSource(e.target.files?.[0] || null);
                setJob(null);
              }}
            />
          </label>
          <p className="hint">
            {source?.name ||
              pair?.name.split(" → ")[0] ||
              "Choose a portrait with one face."}
          </p>
        </div>
        <div className="control-group">
          <h2>Target {kind === "photo" ? "photo" : "video"}</h2>
          <label className="upload-button btn btn-outline">
            <Upload size={17} />
            Upload {kind === "photo" ? "photo" : "video"}
            <input
              type="file"
              accept={
                kind === "photo"
                  ? "image/jpeg,image/png,image/webp"
                  : "video/mp4,video/quicktime,video/webm"
              }
              disabled={active}
              onChange={(e) => {
                setTarget(e.target.files?.[0] || null);
                setJob(null);
              }}
            />
          </label>
          <p className="hint">
            {target?.name ||
              (kind === "photo"
                ? pair?.name.split(" → ")[1]
                : "Up to 30 seconds · 720p · 100 MB")}
          </p>
        </div>
        <details className="advanced">
          <summary>Advanced options</summary>
          <label className="field-label" htmlFor="effect">
            Effect
          </label>
          <select
            id="effect"
            className="select w-full"
            value={mode}
            disabled={active}
            onChange={(e) => setMode(e.target.value)}
          >
            <option value="swap">Swap identity</option>
            <option value="blur">Blur faces</option>
            <option value="pixelate">Pixelate faces</option>
          </select>
          <label className="field-label" htmlFor="strength">
            Blend strength · {Math.round(strength * 100)}%
          </label>
          <input
            id="strength"
            className="range range-sm"
            type="range"
            min="0.1"
            max="1"
            step="0.05"
            value={strength}
            disabled={active}
            onChange={(e) => setStrength(Number(e.target.value))}
          />
          <label className="check-label">
            <input
              className="checkbox checkbox-sm"
              type="checkbox"
              checked={many}
              disabled={active}
              onChange={(e) => setMany(e.target.checked)}
            />
            Edit all detected faces
          </label>
        </details>
        <label className="check-label permission">
          <input
            className="checkbox checkbox-sm"
            type="checkbox"
            checked={consent}
            onChange={(e) => setConsent(e.target.checked)}
          />
          I have permission to edit this media.
        </label>
        <button
          className="btn btn-primary w-full"
          disabled={active || !consent}
          onClick={() => void run()}
        >
          <Play size={17} />
          {active
            ? "Processing…"
            : `Create ${kind === "photo" ? "photo" : "video"}`}
        </button>
        {active && job && (
          <button
            className="btn btn-ghost w-full"
            onClick={() =>
              void api<Job>(`/api/jobs/${job.id}`, { method: "DELETE" }).then(
                setJob,
              )
            }
          >
            Cancel processing
          </button>
        )}
      </aside>
      <div className="preview-column">
        <ErrorMessage
          message={error || (job?.state === "error" && job.message) || ""}
        />
        {job?.state === "complete" && job.result ? (
          kind === "photo" ? (
            <Compare
              before={job.original || targetPreview}
              after={job.result}
            />
          ) : (
            <video
              controls
              className="video-result"
              src={job.result}
              aria-label="Edited video"
            />
          )
        ) : kind === "photo" && targetPreview ? (
          <div className="target-stage">
            <img src={targetPreview} alt="Target portrait before processing" />
            <span className="image-label">Target preview</span>
          </div>
        ) : targetPreview && target ? (
          <video
            className="video-result"
            controls
            src={targetPreview}
            aria-label="Uploaded target video"
          />
        ) : (
          <div className="media-empty">
            <Video size={48} strokeWidth={1.3} />
            <h2>Give your video a new identity.</h2>
            <p>Choose a source portrait, then upload a short clip.</p>
          </div>
        )}
        {job && (
          <div className="job-status" role="status">
            <p>{job.message}</p>
            {["queued", "running"].includes(job.state) && (
              <progress className="progress" max="1" value={job.progress} />
            )}
          </div>
        )}
        {job?.state === "complete" && (
          <div className="download-row">
            <a className="btn btn-outline" href={job.result!}>
              <Download size={17} />
              Download result
            </a>
            <span>
              {Number(job.report.processing_seconds).toFixed(1)} seconds ·{" "}
              {String(job.report.faces_edited)} face edits
            </span>
          </div>
        )}
        {job?.state === "complete" && (
          <details className="advanced">
            <summary>Experiment report</summary>
            <p>
              These measurements describe the edit. They are not authenticity or
              anonymity scores.
            </p>
            <a className="text-action" href={job.report_url!}>
              Download JSON report <Download size={16} />
            </a>
            <pre>{JSON.stringify(job.report, null, 2)}</pre>
          </details>
        )}
        {kind === "photo" && (
          <details className="advanced">
            <summary>Test challenging images</summary>
            <p>
              Try these as a source or target. No-face samples should produce a
              clear explanation.
            </p>
            <div className="fixture-list">
              {examples.fixtures.map((f) => (
                <div key={f.url}>
                  <img src={f.url} alt={f.name} />
                  <div>
                    <strong>{f.name}</strong>
                    <p>{f.expected}</p>
                    <button
                      className="btn btn-sm btn-ghost"
                      disabled={active}
                      onClick={() =>
                        void assetFile(f.url).then((file) => {
                          setSource(file);
                          setJob(null);
                        })
                      }
                    >
                      Use as source
                    </button>
                    <button
                      className="btn btn-sm btn-ghost"
                      disabled={active}
                      onClick={() => {
                        void assetFile(f.url).then(setTarget);
                        setJob(null);
                      }}
                    >
                      Use as target
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </details>
        )}
      </div>
    </div>
  );
}
function HowItWorks({ examples }: { examples: Examples }) {
  return (
    <div className="page-frame how-page">
      <Reveal className="how-intro">
        <h1>From source to screen.</h1>
        <p>
          MorphLab edits faces in images and video. It does not detect whether media
          is real or fake.
        </p>
      </Reveal>
      <section className="how-definitions">
        <Reveal>
          <h2>The source is the identity.</h2>
          <p>
            Choose a clear portrait of the person whose facial identity you want
            to use. The source can be a sample, an uploaded photo, or a face
            captured directly from your webcam.
          </p>
          <img
            src="/examples/source.png"
            alt="Eileen Collins: example source identity"
          />
        </Reveal>
        <Reveal>
          <h2>The target is the performance.</h2>
          <p>
            The target supplies the pose, expression, movement, and background.
            This can be a photo, a short video, or the person visible in your
            live camera.
          </p>
          <img
            src="/examples/target.jpg"
            alt="Grace Hopper: example target scene"
          />
        </Reveal>
      </section>
      <section className="how-flow">
        <Reveal>
          <h2>What happens inside?</h2>
        </Reveal>
        <ol>
          <li>
            <Reveal>
              <h3>Find the face</h3>
              <p>
                A detector locates faces and key points around the eyes, nose,
                and mouth. If there are several people, choose the target face.
              </p>
            </Reveal>
          </li>
          <li>
            <Reveal>
              <h3>Align and transform</h3>
              <p>
                MorphLab aligns the target face, passes it and the source identity
                through the swap model, and generates an edited face crop.
              </p>
            </Reveal>
          </li>
          <li>
            <Reveal>
              <h3>Blend into the scene</h3>
              <p>
                The crop is placed back into the original image with softened
                edges. The rest of the scene is retained. Edited outputs carry
                an MorphLab label.
              </p>
            </Reveal>
          </li>
          <li>
            <Reveal>
              <h3>Track and measure</h3>
              <p>
                For live video, tracking follows the selected face between
                detections. Older waiting frames are replaced so delays do not
                keep accumulating.
              </p>
            </Reveal>
          </li>
        </ol>
      </section>
      <section className="how-instructions">
        <h2>Try it in the Studio.</h2>
        <div>
          <article>
            <h3>Live camera</h3>
            <p>
              Open Live camera and press Start camera. Allow access in your
              browser. Detection needs no portrait. For a swap, choose Swap
              identity and select, upload, or capture a source face.
            </p>
          </article>
          <article>
            <h3>Photo or video</h3>
            <p>
              Choose a sample pair or upload your own media. Confirm permission,
              then press Create. Compare your photo result or play your video,
              and download the result when ready.
            </p>
          </article>
        </div>
        <Link className="btn btn-primary" to="/studio">
          Open Studio <ArrowRight size={18} />
        </Link>
      </section>
      <section className="faq">
        <h2>A few useful answers.</h2>
        {[
          [
            "Does MorphLab use my Mac’s GPU?",
            "When you run MorphLab locally on Apple Silicon, it selects a validated native CoreML model when available. CoreML assigns supported work to Apple compute units. The Studio shows the selected runtime and measured live performance.",
          ],
          [
            "What changes when the website is hosted?",
            "Processing runs on the hosting server. Visiting a hosted MorphLab website from a Mac does not give that server access to your Mac’s GPU. Free CPU servers can be suitable for photo demos, but live performance will differ.",
          ],
          [
            "Why does swapping my webcam capture look the same?",
            "If you capture your own face and keep yourself in the camera, the source and target identity are the same. Choose a different sample identity to see an obvious change.",
          ],
          [
            "What happens when a face disappears?",
            "MorphLab automatically follows the main person and reacquires after brief tracking loss. Use the Person thumbnails to choose someone else, or Auto to resume automatic selection. If the selected person stays away for two seconds, MorphLab chooses another visible person. Uncertain frames pass through while tracking recovers.",
          ],
          [
            "Are the performance numbers real?",
            "Yes. Live performance separates processed frames, generated swaps, and displayed swaps. Capture-to-display latency includes transport and browser image decoding. Saved model benchmarks measure inference alone.",
          ],
          [
            "Where are my images kept?",
            "Camera frames and derived source identity are held in server memory for the session. Stop the camera to clear that session. Photo and video results remain locally for about an hour while the server runs. Source video uploads are removed when processing finishes or is cancelled.",
          ],
          [
            "What are the limits?",
            "The demo accepts photos under 16 megapixels and short videos up to 30 seconds, 720p, and 100 MB. The standard export model generates a 128 × 128 face crop; the lightweight live model uses 224 × 224. Enlarging the output does not create genuine extra facial detail.",
          ],
        ].map(([title, body]) => (
          <details key={title}>
            <summary>{title}</summary>
            <p>{body}</p>
          </details>
        ))}
      </section>
      <section id="credits" className="credits">
        <h2>Sample credits</h2>
        <p>
          Historical public-domain portraits are included for testing. Edited
          samples are demonstrations and do not imply endorsement.
        </p>
        {examples.credits.map((c) => (
          <p key={c.name}>
            <a href={c.url} target="_blank" rel="noreferrer">
              {c.name} <ArrowUpRight size={14} />
            </a>{" "}
            — {c.creator} · {c.license}
          </p>
        ))}
        <p>
          Test fixtures are derived from these portraits or drawn locally.
          Identity similarity and image-detail measurements are research
          heuristics.
        </p>
      </section>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(
  <MotionConfig reducedMotion="user">
    <BrowserRouter>
      <App />
    </BrowserRouter>
  </MotionConfig>,
);
