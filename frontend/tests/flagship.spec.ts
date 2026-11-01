import { test,expect } from '@playwright/test';
import AxeBuilder from '@axe-core/playwright';

test('person thumbnail, automatic swap and explicit session clearing',async({page})=>{
 await page.goto('/studio?mode=live');
 await page.getByRole('button',{name:'Start camera',exact:true}).click();
 await expect(page.getByRole('button',{name:/Person 1/})).toBeVisible({timeout:20000});
 await expect(page.getByRole('button',{name:/Person 1/}).locator('img')).toHaveJSProperty('naturalWidth',80);
 await page.locator('#sample-identity').selectOption('/examples/source.png');
 await expect(page.getByText('Identity applied',{exact:true})).toBeVisible({timeout:45000});
 await expect(page.locator('#live-effect')).toHaveValue('swap');
 await page.getByRole('button',{name:/Person 1/}).focus();
 await page.keyboard.press('Enter');
 await expect(page.getByRole('button',{name:'Auto',exact:true})).toHaveAttribute('aria-pressed','false');
 await page.getByRole('button',{name:'Auto',exact:true}).click();
 await expect(page.getByRole('button',{name:'Auto',exact:true})).toHaveAttribute('aria-pressed','true');
 await page.getByText('Live performance',{exact:true}).click();
 await expect(page.getByText('Worker encode/decode',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Clear session data',exact:true}).click();
 await expect(page.getByText('Camera stopped and session data cleared.')).toBeVisible();
 await expect(page.getByRole('button',{name:/Person 1/})).toHaveCount(0);
});

test('worker-disabled fallback and accessible pages',async({page})=>{
 await page.emulateMedia({reducedMotion:'reduce'});
 for(const route of ['/','/how-it-works','/studio?mode=photo']) {
   await page.goto(route);
   const results=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
   expect(results.violations.filter(x=>['critical','serious'].includes(x.impact || ''))).toEqual([]);
   await page.getByRole('button',{name:'Toggle color theme',exact:true}).click();
   const dark=await new AxeBuilder({page}).withTags(['wcag2a','wcag2aa','wcag21aa']).analyze();
   expect(dark.violations.filter(x=>['critical','serious'].includes(x.impact || ''))).toEqual([]);
 }
 await page.goto('/studio?mode=live&worker=off');
 await page.getByRole('button',{name:'Start camera',exact:true}).click();
 await expect(page.getByText('1 face detected',{exact:true})).toBeVisible({timeout:20000});
 await page.getByText('Live performance',{exact:true}).click();
 await expect(page.getByText('Main-thread fallback',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'Stop camera',exact:true}).click();
});
