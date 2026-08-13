import { chromium } from 'playwright';
const b=await chromium.launch();
const p=await b.newPage({viewport:{width:1440,height:900}});
await p.goto('https://antivenom.pages.dev/?x='+Date.now(),{waitUntil:'domcontentloaded'});
await p.waitForTimeout(2600);
await p.locator('#cascade').scrollIntoViewIfNeeded(); await p.waitForTimeout(400);
const t0=Date.now(); let last=null; const marks={};
while ((Date.now()-t0)/1000 < 60) {
  const s=await p.evaluate(()=>document.querySelector('.stage--now .stage__label')?.textContent);
  if (s!==last){ const t=(Date.now()-t0)/1000; marks[s]=t; console.log(`  ${t.toFixed(1).padStart(5)}s  ${s}`); last=s; }
  const done=await p.evaluate(()=>document.querySelector('.cascade-foot .mono')?.textContent);
  if (done==='158/158'){ console.log(`  ${((Date.now()-t0)/1000).toFixed(1).padStart(5)}s  complete`); break; }
  await p.waitForTimeout(100);
}
await b.close();
