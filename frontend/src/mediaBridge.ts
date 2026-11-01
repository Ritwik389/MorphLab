// Separate encode/decode workers: one operation in flight per boundary, no hidden backlog.
export class MediaBridge {
  private workers: Worker[] = [];
  private pending = new Map<number,{resolve:(v:any)=>void;reject:(e:Error)=>void}>();
  private sequence = 0;
  enabled = false;
  constructor() {
    if (typeof Worker === 'undefined' || typeof OffscreenCanvas === 'undefined' ||
        !OffscreenCanvas.prototype.convertToBlob || new URLSearchParams(location.search).get('worker') === 'off') return;
    try {
      this.workers = [0,1].map(()=>new Worker(new URL('./media.worker.ts',import.meta.url),{type:'module'}));
      for (const worker of this.workers) {
        worker.onmessage = ({data}) => {
          const pending = this.pending.get(data.id);
          this.pending.delete(data.id);
          if (!pending) {data.bitmap?.close();return;}
          if (data.error || data.dropped) pending.reject(new Error(data.error || 'Media worker is busy.'));
          else pending.resolve(data);
        };
        worker.onerror = ()=>{ this.close(); };
      }
      this.enabled = true;
    } catch { this.close(); }
  }
  private call(index:number,data:any,transfer:Transferable[]):Promise<any> {
    return new Promise((resolve,reject)=>{
      if (!this.enabled) {reject(new Error('Media worker unavailable.'));return;}
      const id=++this.sequence;
      this.pending.set(id,{resolve,reject});
      try { this.workers[index].postMessage({...data,id},transfer); }
      catch(error) { this.pending.delete(id); data.bitmap?.close(); reject(error instanceof Error ? error : new Error(String(error))); }
    });
  }
  encode(bitmap:ImageBitmap,width:number,height:number) { return this.call(0,{type:'encode',bitmap,width,height},[bitmap]); }
  decode(buffer:ArrayBuffer) { return this.call(1,{type:'decode',buffer},[buffer]); }
  close() {
    this.enabled=false;
    for(const worker of this.workers) worker.terminate();
    this.workers=[];
    for(const pending of this.pending.values()) pending.reject(new Error('Media worker stopped.'));
    this.pending.clear();
  }
}
