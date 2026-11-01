import { describe,it,expect } from 'vitest';
import { readPacket,quantile } from './liveProtocol';
describe('binary camera contract',()=>{
 it('rejects truncation and oversized headers',()=>{
   expect(()=>readPacket(new ArrayBuffer(2))).toThrow();
   const bad=new ArrayBuffer(9);new DataView(bad).setUint32(0,900000);
   expect(()=>readPacket(bad)).toThrow();
 });
 it('parses typed selection and timing fields',()=>{
   const h={frame_id:5,revision:2,captured_at:15,width:640,height:480,selected_face:2,target_status:'tracking'};
   const bytes=new TextEncoder().encode(JSON.stringify(h));const b=new Uint8Array(4+bytes.length+1);
   new DataView(b.buffer).setUint32(0,bytes.length);b.set(bytes,4);b[b.length-1]=123;
   expect(readPacket(b.buffer).header.selected_face).toBe(2);
 });
 it('computes latency quantiles without mutating samples',()=>{
   const samples=[20,1,5,10];expect(quantile(samples,.95)).toBe(20);expect(samples[0]).toBe(20);
 });
});
