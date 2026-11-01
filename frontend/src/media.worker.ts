/// <reference lib="webworker" />
// Bounded media work. Transferables avoid JS buffer clones, not every driver-level copy.
const scope = self as unknown as DedicatedWorkerGlobalScope;
let busy = false;
scope.onmessage = async (event: MessageEvent) => {
  const { id, type, bitmap, buffer, width, height } = event.data;
  if (busy) { bitmap?.close(); scope.postMessage({id, dropped:true}); return; }
  busy = true;
  try {
    if (type === 'encode') {
      const started = performance.now();
      const canvas = new OffscreenCanvas(width,height);
      canvas.getContext('2d')!.drawImage(bitmap,0,0,width,height);
      bitmap.close();
      const blob = await canvas.convertToBlob({type:'image/jpeg',quality:.82});
      const bytes = await blob.arrayBuffer();
      scope.postMessage({id,buffer:bytes,ms:performance.now()-started},[bytes]);
    } else if (type === 'decode') {
      const started = performance.now();
      const decoded = await createImageBitmap(new Blob([buffer],{type:'image/jpeg'}));
      scope.postMessage({id,bitmap:decoded,ms:performance.now()-started},[decoded]);
    }
  } catch (error) {
    bitmap?.close();
    scope.postMessage({id,error:String(error)});
  } finally { busy = false; }
};
