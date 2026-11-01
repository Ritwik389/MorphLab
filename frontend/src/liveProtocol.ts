export type Person = { id: number; label: string; visible: boolean; thumbnail: string };
export type Header = {
  frame_id: number; captured_at: number; revision: number; swapped: boolean;
  processing_ms: number; dropped_frames: number; message: string;
  faces: { id: number; bbox: number[] }[]; width: number; height: number;
  selected_face?: number; selection_mode?: string; target_status?: string;
  target_revision?: number; stages?: Record<string, number>; process_rss_mb?: number; mps_tensors_mb?: number; mps_driver_mb?: number; input_decode_ms?: number; queue_wait_ms?: number;
};
export function readPacket(buffer: ArrayBuffer): { header: Header; image: Uint8Array } {
  if (buffer.byteLength < 5) throw new Error('Incomplete camera frame.');
  const size = new DataView(buffer).getUint32(0);
  if (!size || size > 65536 || size + 4 >= buffer.byteLength) throw new Error('Invalid camera header.');
  const header = JSON.parse(new TextDecoder().decode(new Uint8Array(buffer,4,size))) as Header;
  if (!Number.isInteger(header.frame_id) || !Number.isFinite(header.captured_at) ||
      !Number.isInteger(header.revision) || header.width <= 0 || header.height <= 0 ||
      header.width > 1280 || header.height > 960) throw new Error('Invalid camera metadata.');
  return { header, image: new Uint8Array(buffer,4+size) };
}
export function quantile(values: number[], q: number) {
  if (!values.length) return 0;
  const sorted = [...values].sort((a,b)=>a-b);
  return sorted[Math.min(sorted.length-1,Math.ceil(q*sorted.length)-1)];
}
