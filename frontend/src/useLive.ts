import { useEffect, useRef, useState } from "react";
import { api } from "./api";

import { readPacket, quantile, type Header, type Person } from "./liveProtocol";
import { MediaBridge } from "./mediaBridge";
export type Metrics = {
  processed: number;
  swapped: number;
  displayed: number;
  latency: number;
  backend: number;
  dropped: number;
  resolution: string;
  message: string;
  faces: Header["faces"];
  selected?: number;
  selectionMode?: string;
  targetStatus?: string;
  p50: number;
  p95: number;
  stages: Record<string, number>;
  memory?: number;
  gpu?: number;
  gpuDriver?: number;
  mediaPath: string;
};

export function useLive(mode: string) {
  const video = useRef<HTMLVideoElement>(null),
    canvas = useRef<HTMLCanvasElement>(null);
  const bridge = useRef<MediaBridge | null>(null);
  const [people,setPeople] = useState<Person[]>([]);
  const [checks,setChecks] = useState<{warnings:string[];status:string;note:string} | null>(null);
  const [notice,setNotice] = useState("");
  const targetRevision = useRef(0);
  const profile = useRef(false);
  const stream = useRef<MediaStream | null>(null),
    socket = useRef<WebSocket | null>(null);
  const session = useRef<string | null>(null),
    revision = useRef(0),
    generation = useRef(0),
    frameId = useRef(0);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const modeRef = useRef(mode);
  modeRef.current = mode;
  const [running, setRunning] = useState(false),
    [starting, setStarting] = useState(false),
    [busy, setBusy] = useState(false);
  const [source, setSource] = useState(""),
    [error, setError] = useState(""),
    [metrics, setMetrics] = useState<Metrics | null>(null);
  const pendingSession = useRef<Promise<string> | null>(null);
  const sessionEpoch = useRef(0);
  async function ensureSession() {
    if (session.current) return session.current;
    const lifetime = sessionEpoch.current;
    if (!pendingSession.current)
      pendingSession.current = api<{ id: string; revision: number }>(
        "/api/sessions",
        { method: "POST" },
      )
        .then((x) => {
          if (lifetime !== sessionEpoch.current) {
            void fetch(`/api/sessions/${x.id}`, { method: "DELETE" });
            throw new Error("Camera session cancelled.");
          }
          session.current = x.id;
          revision.current = x.revision;
          return x.id;
        })
        .finally(() => {
          pendingSession.current = null;
        });
    return pendingSession.current;
  }
  function stop() {
    generation.current++;
    sessionEpoch.current++;
    bridge.current?.close();
    bridge.current = null;
    targetRevision.current = 0;
    clearTimeout(timer.current);
    socket.current?.close();
    socket.current = null;
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
    if (video.current) video.current.srcObject = null;
    const id = session.current;
    session.current = null;
    revision.current = 0;
    if (id)
      void fetch(`/api/sessions/${id}`, { method: "DELETE", keepalive: true });
    canvas.current
      ?.getContext("2d")
      ?.clearRect(0, 0, canvas.current.width, canvas.current.height);
    setRunning(false);
    setStarting(false);
    setSource("");
    setMetrics(null);
    setPeople([]);
    setChecks(null);
  }
  async function start() {
    const epoch = ++generation.current;
    setStarting(true);
    setError("");
    try {
      if (!navigator.mediaDevices?.getUserMedia)
        throw new Error(
          "Camera access requires localhost or HTTPS in a supported browser.",
        );
      const id = await ensureSession();
      if (epoch !== generation.current) {
        void fetch(`/api/sessions/${id}`, { method: "DELETE" });
        if (session.current === id) session.current = null;
        return;
      }
      const media = await navigator.mediaDevices.getUserMedia({
        audio: false,
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          frameRate: { ideal: 24, max: 30 },
          facingMode: "user",
        },
      });
      if (epoch !== generation.current) {
        media.getTracks().forEach((t) => t.stop());
        return;
      }
      stream.current = media;
      media.getVideoTracks()[0].addEventListener("ended", () => {
        if (epoch === generation.current) {
          stop();
          setError("Camera access ended. Start the camera to reconnect.");
        }
      });
      video.current!.srcObject = media;
      await video.current!.play();
      const ws = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/live/${id}`,
      );
      ws.binaryType = "arraybuffer";
      socket.current = ws;
      await new Promise<void>((resolve, reject) => {
        const timeout = setTimeout(
          () => reject(new Error("Camera connection timed out. Try again.")),
          10000,
        );
        ws.onopen = () => {
          clearTimeout(timeout);
          resolve();
        };
        ws.onerror = () => {
          clearTimeout(timeout);
          reject(new Error("Could not connect to the camera processor."));
        };
      });
      if (epoch !== generation.current) {
        ws.close();
        return;
      }
      ws.send(JSON.stringify({ mode: modeRef.current, profile: profile.current }));
      bridge.current = new MediaBridge();
      setRunning(true);
      setStarting(false);
      const input = document.createElement("canvas");
      const ctx = input.getContext("2d")!;
      let lastDrawn = -1,
        processed = 0,
        swapped = 0,
        displayed = 0,
        windowStart = performance.now(),
        decoding = false;
      const latencies: number[] = [];
      let lastVideoTime = -1, captureMs = 0, decodeMs = 0;
      ws.onmessage = async (event) => {
        if (typeof event.data === "string") {
          const data = JSON.parse(event.data);
          if (epoch !== generation.current) return;
          if (data.error) setError(data.error);
          if (data.type === "people" && data.revision === revision.current) setPeople(data.people);
          if (data.type === "control") targetRevision.current = Math.max(targetRevision.current,data.target_revision || 0);
          return;
        }
        if (epoch !== generation.current) return;
        let packet;
        try { packet = readPacket(event.data as ArrayBuffer); }
        catch { setError("Invalid camera response. Restart the camera."); return; }
        const {header, image} = packet;
        if (
          header.revision !== revision.current ||
          header.frame_id <= lastDrawn ||
          (header.target_revision || 0) < targetRevision.current
        )
          return;
        processed++;
        if (header.swapped) swapped++;
        if (decoding) return;
        decoding = true;
        try {
          const decodeStart = performance.now();
          let bitmap: ImageBitmap;
          if (bridge.current?.enabled) {
            try {
              const result = await bridge.current.decode(image.slice().buffer);
              bitmap = result.bitmap;
            } catch {
              if(epoch !== generation.current) return;
              bitmap = await createImageBitmap(new Blob([image.slice().buffer],{type:"image/jpeg"}));
            }
          } else bitmap = await createImageBitmap(new Blob([image.slice().buffer],{type:"image/jpeg"}));
          decodeMs = performance.now()-decodeStart;
          if (
            epoch !== generation.current ||
            header.revision !== revision.current || (header.target_revision || 0) < targetRevision.current
          ) {
            bitmap.close();
            return;
          }
          const out = canvas.current!;
          if (out.width !== header.width || out.height !== header.height) {
            out.width = header.width;
            out.height = header.height;
          }
          out.getContext("2d")!.drawImage(bitmap, 0, 0);
          bitmap.close();
          lastDrawn = header.frame_id;
          targetRevision.current = Math.max(targetRevision.current,header.target_revision || 0);
          await new Promise(requestAnimationFrame);
          if (
            epoch !== generation.current ||
            header.revision !== revision.current || (header.target_revision || 0) < targetRevision.current
          )
            return;
          out.dispatchEvent(
            new CustomEvent("aims-frame", {
              bubbles: true,
              detail: {
                frame_id: header.frame_id,
                swapped: header.swapped,
                captured_at: header.captured_at,
                rendered_at: performance.now(),
                processing_ms: header.processing_ms,
              },
            }),
          );
          if (header.swapped) displayed++;
          latencies.push(performance.now()-header.captured_at);
          if(latencies.length > 240) latencies.shift();
          const now = performance.now(),
            elapsed = (now - windowStart) / 1000;
          if (elapsed >= 0.5) {
            setMetrics({
              processed: processed / elapsed,
              swapped: swapped / elapsed,
              displayed: displayed / elapsed,
              latency: now - header.captured_at,
              backend: header.processing_ms,
              dropped: header.dropped_frames,
              resolution: `${header.width} × ${header.height}`,
              message: header.message,
              faces: header.faces,
              selected: header.selected_face,
              selectionMode: header.selection_mode,
              targetStatus: header.target_status,
              p50: quantile(latencies,.5), p95: quantile(latencies,.95),
              stages: {capture_encode_worker_ms:captureMs,decode_worker_ms:decodeMs,input_decode_ms:header.input_decode_ms || 0,queue_wait_ms:header.queue_wait_ms || 0,...header.stages},
              memory: header.process_rss_mb, gpu: header.mps_tensors_mb, gpuDriver:header.mps_driver_mb,
              mediaPath: bridge.current?.enabled ? "Worker encode/decode" : "Main-thread fallback",
            });
            processed = swapped = displayed = 0;
            windowStart = now;
          }
        } catch {
          setError(
            "Could not display a processed frame. Try restarting the camera.",
          );
        } finally {
          decoding = false;
        }
      };
      ws.onclose = () => {
        if (epoch === generation.current) {
          stop();
          setError("Camera connection closed. Start again to reconnect.");
        }
      };
      async function tick() {
        if (epoch !== generation.current || ws.readyState !== WebSocket.OPEN)
          return;
        const v = video.current!;
        if (v.readyState >= 2 && v.currentTime !== lastVideoTime && ws.bufferedAmount < 200000) {
          const scale = Math.min(1, 640 / v.videoWidth, 480 / v.videoHeight);
          input.width = Math.round(v.videoWidth * scale);
          input.height = Math.round(v.videoHeight * scale);
          const capturedAt = performance.now(),
            rev = revision.current;
          lastVideoTime = v.currentTime;
          let blob: Blob | null;
          if (bridge.current?.enabled) {
            try {
              const bitmap = await createImageBitmap(v);
              if (epoch !== generation.current) { bitmap.close(); return; }
              const result = await bridge.current.encode(bitmap,input.width,input.height);
              blob = new Blob([result.buffer],{type:"image/jpeg"});
            } catch {
              if (epoch !== generation.current) return;
              ctx.drawImage(v,0,0,input.width,input.height);
              blob = await new Promise<Blob | null>(resolve=>input.toBlob(resolve,"image/jpeg",.82));
            }
          } else {
            ctx.drawImage(v,0,0,input.width,input.height);
            blob = await new Promise<Blob | null>(resolve=>input.toBlob(resolve,"image/jpeg",.82));
          }
          captureMs = performance.now()-capturedAt;
          if (
            blob &&
            epoch === generation.current &&
            ws.readyState === WebSocket.OPEN &&
            rev === revision.current
          ) {
            const header = new TextEncoder().encode(
              JSON.stringify({
                frame_id: ++frameId.current,
                captured_at: capturedAt,
                revision: rev,
              }),
            );
            const length = new Uint8Array(4);
            new DataView(length.buffer).setUint32(0, header.length);
            ws.send(new Blob([length, header, blob]));
          }
        }
        timer.current = setTimeout(tick, 1000 / 24);
      }
      void tick();
    } catch (e) {
      if (epoch === generation.current) {
        stop();
        setError(
          e instanceof DOMException && e.name === "NotAllowedError"
            ? "Camera access was denied. Allow it in your browser settings, then try again."
            : (e as Error).message,
        );
      }
    }
  }
  async function enroll(data: FormData, label: string) {
    const lifetime = sessionEpoch.current;
    setBusy(true);
    setError("");
    try {
      const id = await ensureSession();
      const result = await api<{ revision: number; checks: {warnings:string[];status:string;note:string} }>(
        `/api/sessions/${id}/source`,
        { method: "PUT", body: data },
      );
      if (session.current === id) {
        revision.current = result.revision;
        setSource(label);
        setChecks(result.checks);
        setNotice("");
      }
    } catch (e) {
      if (lifetime === sessionEpoch.current) setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  async function clear() {
    if (session.current) {
      const x = await api<{ revision: number }>(
        `/api/sessions/${session.current}/source`,
        { method: "DELETE" },
      );
      revision.current = x.revision;
    }
    setSource("");
    setChecks(null);
  }
  async function purge() {
    const id = session.current;
    stop();
    if (id) {
      try { await api(`/api/sessions/${id}`,{method:"DELETE"}); }
      catch(e) { setError((e as Error).message); return; }
    }
    setNotice("Camera stopped and session data cleared.");
  }
  function setProfile(enabled:boolean) {
    profile.current=enabled;
    if(socket.current?.readyState === WebSocket.OPEN) socket.current.send(JSON.stringify({profile:enabled}));
  }
  function automatic() { if(socket.current?.readyState === WebSocket.OPEN) { targetRevision.current++; socket.current.send(JSON.stringify({auto:true})); } }
  function select(id: number) {
    if(socket.current?.readyState === WebSocket.OPEN) { targetRevision.current++; socket.current.send(JSON.stringify({ select: id })); }
  }
  useEffect(() => {
    if (socket.current?.readyState === WebSocket.OPEN)
      socket.current.send(JSON.stringify({ mode }));
  }, [mode]);
  useEffect(() => {
    const hide = () => stop();
    window.addEventListener("pagehide", hide);
    return () => {
      window.removeEventListener("pagehide", hide);
      stop();
    };
  }, []);
  return {
    video,
    canvas,
    running,
    starting,
    busy,
    source,
    error,
    metrics,
    start,
    stop,
    enroll,
    clear,
    select,
    automatic, people, checks, notice, purge, setProfile,
  };
}
