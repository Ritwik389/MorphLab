import {test,expect} from '@playwright/test';
test('public pages load without camera access or model warmup',async({page,request})=>{
 await page.addInitScript(()=>{
   (window as any).__cameraRequested=false;
   navigator.mediaDevices.getUserMedia=async()=>{(window as any).__cameraRequested=true;throw new Error('Unexpected camera access');};
 });
 const before=await(await request.get('/api/system')).json();
 for(const route of ['/','/how-it-works','/studio?mode=live']){
   await page.goto(route);
   await expect(page.getByRole('heading',{level:1})).toBeVisible();
   expect(await page.evaluate(()=>(window as any).__cameraRequested)).toBe(false);
   expect((await(await request.get('/api/system')).json()).state).toBe(before.state);
 }
});
