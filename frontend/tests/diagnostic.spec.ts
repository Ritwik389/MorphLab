import {test,expect} from '@playwright/test';
import fs from 'node:fs/promises';
test('profile genuine camera replay without treating diagnostics as acceptance',async({page})=>{
 await page.goto('/studio?mode=live');
 await page.getByRole('button',{name:'Start camera',exact:true}).click();
 await page.locator('#sample-identity').selectOption('/examples/source.png');
 await expect(page.getByText('Identity applied',{exact:true})).toBeVisible({timeout:45000});
 await page.getByText('Live performance',{exact:true}).click();
 const samples=[];
 for(let i=0;i<20;i++) {
   await page.waitForTimeout(1000);
   samples.push(await page.locator('.preview-column').innerText());
 }
 await page.getByRole('button',{name:'Stop camera',exact:true}).click();
 await fs.writeFile('../outputs/benchmarks/diagnostics.json',JSON.stringify(samples,null,2));
 console.log(samples.slice(-3).join('\n'));
});
