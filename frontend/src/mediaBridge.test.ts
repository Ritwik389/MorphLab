import { beforeEach,afterEach,expect,it,vi } from 'vitest';
import { MediaBridge } from './mediaBridge';
class FakeWorker {
 static instances:FakeWorker[]=[];
 onmessage:any;onerror:any;messages:any[]=[];terminated=false;
 constructor(){FakeWorker.instances.push(this);}
 postMessage(data:any,transfer:any){this.messages.push({data,transfer});}
 terminate(){this.terminated=true;}
}
beforeEach(()=>{
 FakeWorker.instances=[];
 vi.stubGlobal('Worker',FakeWorker);
 vi.stubGlobal('location',{search:''});
 class Canvas {convertToBlob(){}}
 vi.stubGlobal('OffscreenCanvas',Canvas);
});
afterEach(()=>vi.unstubAllGlobals());
it('closes workers and rejects pending work on Stop',async()=>{
 const bridge=new MediaBridge();expect(bridge.enabled).toBe(true);
 const bitmap={close:vi.fn()} as unknown as ImageBitmap;
 const pending=bridge.encode(bitmap,640,480);
 const rejection=expect(pending).rejects.toThrow('stopped');
 bridge.close();await rejection;
 expect(FakeWorker.instances.every(w=>w.terminated)).toBe(true);
 expect(bridge.enabled).toBe(false);
});
it('transfers input and resolves only the matching operation',async()=>{
 const bridge=new MediaBridge();const bitmap={close:vi.fn()} as unknown as ImageBitmap;
 const pending=bridge.encode(bitmap,10,10);const worker=FakeWorker.instances[0];
 const {data,transfer}=worker.messages[0];expect(transfer[0]).toBe(bitmap);
 worker.onmessage({data:{id:data.id,buffer:new ArrayBuffer(3),ms:2}});
 expect((await pending).buffer.byteLength).toBe(3);bridge.close();
});
it('uses fallback when worker capability is absent or disabled',()=>{
 vi.stubGlobal('location',{search:'?worker=off'});const bridge=new MediaBridge();
 expect(bridge.enabled).toBe(false);expect(FakeWorker.instances).toHaveLength(0);
});
it('disposes late decoded bitmaps after shutdown',()=>{
 const bridge=new MediaBridge();const worker=FakeWorker.instances[1];const bitmap={close:vi.fn()};bridge.close();
 worker.onmessage({data:{id:999,bitmap}});expect(bitmap.close).toHaveBeenCalledOnce();
});
