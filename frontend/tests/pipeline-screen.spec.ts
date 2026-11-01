import {test,expect} from '@playwright/test';
import fs from 'node:fs/promises';
import path from 'node:path';

const configurations=[{worker:'on',hud:false},{worker:'off',hud:false},{worker:'on',hud:true}];
for(let repeat=0;repeat<3;repeat++) {
  const order=repeat===1?[2,0,1]:repeat===2?[1,2,0]:[0,1,2];
  for(const index of order) {
    const config=configurations[index];
    test(`media worker ${config.worker}, HUD ${config.hud}, repeat ${repeat}`,async({page,browser})=>{
      await page.addInitScript(()=>{
        (window as any).__screen={recording:false,frames:[],longTasks:[]};
        window.addEventListener('aims-frame',((event:CustomEvent)=>{
          const data=(window as any).__screen;
          if(data.recording && event.detail.swapped) data.frames.push(event.detail);
        }) as EventListener);
        try {new PerformanceObserver(list=>{
          const data=(window as any).__screen;
          if(data.recording) data.longTasks.push(...list.getEntries().map(x=>x.duration));
        }).observe({type:'longtask',buffered:false});} catch {}
      });
      await page.goto(`/studio?mode=live${config.worker==='off'?'&worker=off':''}`);
      await page.getByRole('button',{name:'Start camera',exact:true}).click();
      await page.locator('#sample-identity').selectOption('/examples/source.png');
      await expect(page.getByText('Identity applied',{exact:true})).toBeVisible({timeout:45000});
      if(config.hud) await page.getByText('Live performance',{exact:true}).click();
      await page.waitForTimeout(3000);
      await page.evaluate(()=>{(window as any).__screen.recording=true;(window as any).__screen.started=performance.now();});
      await page.waitForTimeout(20000);
      const result=await page.evaluate(()=>{
        const data=(window as any).__screen;data.recording=false;
        const duration=(performance.now()-data.started)/1000;
        const costs=data.frames.map((x:any)=>x.rendered_at-x.captured_at).sort((a:number,b:number)=>a-b);
        return {duration_seconds:duration,new_displayed_swaps:data.frames.length,displayed_swap_fps:data.frames.length/duration,
          p95_capture_to_display_ms:costs[Math.floor(costs.length*.95)],long_tasks_over_50ms:data.longTasks.length,
          long_task_total_ms:data.longTasks.reduce((a:number,b:number)=>a+b,0),
          main_thread_js_heap_bytes:(performance as any).memory?.usedJSHeapSize ?? null};
      });
      await page.getByRole('button',{name:'Stop camera',exact:true}).click();
      const output=process.env.AIMS_PIPELINE_SCREEN_OUTPUT || '../outputs/evaluations/browser-pipeline-screen';
      await fs.mkdir(output,{recursive:true});
      await fs.writeFile(path.join(output,`${config.worker}-${config.hud}-${repeat}.json`),JSON.stringify({configuration:config,repeat,
        browser:browser.version(),scope:'20-second engineering screen; not two-minute acceptance. Main-thread heap excludes worker/driver memory.',...result},null,2));
      expect(result.new_displayed_swaps).toBeGreaterThan(0);
    });
  }
}
