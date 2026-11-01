import {test,expect} from '@playwright/test';
import fs from 'node:fs/promises';
const output=process.env.AIMS_LONGEVITY_OUTPUT || '../outputs/benchmarks';

test('100 complete Start/Stop cycles release browser and server resources',async({page,request})=>{
 await page.goto('/studio?mode=live');
 for(let cycle=0;cycle<100;cycle++) {
   await page.getByRole('button',{name:'Start camera',exact:true}).click();
   await expect(page.getByText('1 face detected',{exact:true})).toBeVisible({timeout:20000});
   await page.getByRole('button',{name:'Stop camera',exact:true}).click();
   await expect(page.locator('video')).toHaveJSProperty('srcObject',null);
   await expect.poll(async()=>(await(await request.get('/api/system')).json()).active_live_sessions).toBe(0);
   if(cycle%10===9) console.log(`Completed ${cycle+1} camera cycles`);
 }
 await fs.mkdir(output,{recursive:true});
 await fs.writeFile(`${output}/lifecycle-100.json`,JSON.stringify({complete:true,cycles:100,
   camera_tracks_released:true,server_sessions_released:true,scope:'Chrome fake camera; actual browser Start/Stop and worker disposal'},null,2));
});

test('one-hour full browser live soak',async({page,request})=>{
 test.skip(process.env.AIMS_RUN_SOAK !== '1','Explicit one-hour release check; not silently claimed as passed.');
 await page.addInitScript(()=>{
   (window as any).__aimsSoak={swaps:0,lastFrame:0};
   window.addEventListener('aims-frame',((event:CustomEvent)=>{
     if(event.detail.swapped) {
       (window as any).__aimsSoak.swaps++;
       (window as any).__aimsSoak.lastFrame=performance.now();
     }
   }) as EventListener);
 });
 await page.goto('/studio?mode=live');
 await page.getByRole('button',{name:'Start camera',exact:true}).click();
 await page.locator('#sample-identity').selectOption('/examples/source.png');
 await expect(page.getByText('Identity applied',{exact:true})).toBeVisible({timeout:45000});
 const started=Date.now(), memory:any[]=[];
 let previousSwaps=0;
 for(let minute=0;minute<60;minute++) {
   await page.waitForTimeout(60000);
   const system=await(await request.get('/api/system')).json();
   const sample=await(await request.get('/api/diagnostics/resources')).json();
   const progress=await page.evaluate(()=>({... (window as any).__aimsSoak,
     frameAgeMs:performance.now()-(window as any).__aimsSoak.lastFrame}));
   memory.push({elapsed_seconds:(Date.now()-started)/1000,...sample,...progress});
   await fs.mkdir(output,{recursive:true});
   await fs.writeFile(`${output}/browser-soak.partial.json`,JSON.stringify({complete:false,memory},null,2));
   expect(system.active_live_sessions).toBe(1);
   expect(progress.swaps).toBeGreaterThan(previousSwaps);
   expect(progress.frameAgeMs).toBeLessThan(5000);
   previousSwaps=progress.swaps;
   await expect(page.getByRole('button',{name:'Stop camera',exact:true})).toBeVisible();
   console.log(`Soak minute ${minute+1}: ${sample.process_rss_mb.toFixed(1)} MiB`);
 }
 await page.getByRole('button',{name:'Stop camera',exact:true}).click();
 await expect(page.locator('video')).toHaveJSProperty('srcObject',null);
 await expect.poll(async()=>(await(await request.get('/api/system')).json()).active_live_sessions).toBe(0);
 const first=memory.slice(1,11).reduce((a,x)=>a+x.process_rss_mb,0)/10;
 const last=memory.slice(-10).reduce((a,x)=>a+x.process_rss_mb,0)/10;
 const passed=last-first<=Math.max(first*.1,128);
 await fs.writeFile(`${output}/browser-soak.json`,JSON.stringify({complete:true,duration_seconds:(Date.now()-started)/1000,
   memory,rss_growth_mb:last-first,memory_gate_passed:passed,new_displayed_swaps:previousSwaps,
   frame_progress_verified:true,camera_tracks_released:true,server_sessions_released:true,
   scope:'Chrome fake-camera full browser live pipeline; progress checked every minute'},null,2));
 expect(passed).toBe(true);
});
