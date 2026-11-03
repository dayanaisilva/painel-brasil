// Teste de DOM simulado: valida rotas e interações; não substitui inspeção visual dos gráficos.
const { JSDOM } = require('jsdom');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.join(__dirname, '..');
const data = JSON.parse(fs.readFileSync(path.join(root,'site/data/painel.json'),'utf8'));
const dom = new JSDOM(fs.readFileSync(path.join(root,'site/index.html'),'utf8'), {
  url:'https://tirateimabr.com.br/',runScripts:'outside-only',pretendToBeVisual:true
});
const w=dom.window, errors=[];
w.matchMedia=()=>({matches:false,addEventListener(){}});
w.scrollTo=()=>{};
w.fetch=async()=>({ok:true,json:async()=>data});
w.addEventListener('error',e=>errors.push(e.message));
w.eval(fs.readFileSync(path.join(root,'site/numeros.js'),'utf8'));
w.eval(fs.readFileSync(path.join(root,'site/app.js'),'utf8'));
const tick=()=>new Promise(resolve=>setTimeout(resolve,15));
async function route(hash){w.location.hash=hash;await tick();assert(w.document.querySelector('main h1'),hash);assert(!w.document.querySelector('main').textContent.includes('Os dados não carregaram'),hash);}
(async()=>{
 await tick();
 const routes=['#/','#/indicadores','#/governos','#/comparar','#/calculadora','#/metodologia',
 ...Object.keys(data.indicadores).map(id=>'#/i/'+id),...data.governos.map(g=>'#/g/'+g.id)];
 for(const r of routes)await route(r);
 for(const id of ['homicidios','universidades_federais','municipios_federais']){
   await route('#/i/'+id);
   assert(w.document.querySelector('main').textContent.includes('Comparação por governo suspensa'));
   assert.equal(w.document.querySelector('#tab-gov'),null);
 }
 await route('#/i/fome');
 assert.equal(w.document.querySelector('#tab-gov'),null);
 assert(w.document.querySelector('.veredito').textContent.includes('abaixo de 2,5%'));
 await route('#/calculadora');
 const input=w.document.querySelector('#calc-valor');
 input.value='1.000';input.dispatchEvent(new w.Event('input',{bubbles:true}));
 assert(w.document.querySelector('.calc-card'));
 input.value='abc';input.dispatchEvent(new w.Event('input',{bubbles:true}));
 assert.equal(w.document.querySelector('.calc-card'),null);
 assert.deepEqual(errors,[]);
 console.log(`${routes.length} rotas e restrições de publicação verificadas no DOM simulado.`);
 dom.window.close();
})().catch(e=>{console.error(e);dom.window.close();process.exitCode=1;});
