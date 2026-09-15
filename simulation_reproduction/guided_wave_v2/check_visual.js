const fs=require('fs'),vm=require('vm'),assert=require('assert'),path=require('path');
const file=path.resolve(__dirname,'visual-template.html');
const text=fs.readFileSync(file,'utf8');
const source=text.match(/<script>([\s\S]*?)<\/script>/)[1];
assert(Buffer.byteLength(text)<1000000);
assert(!text.includes('__SIMULATION_DATA__'));
for(const width of [320,736]){
 const elements={};
 function make(){return {attrs:{},children:[],value:'',setAttribute(k,v){this.attrs[k]=v},appendChild(e){this.children.push(e)},replaceChildren(){this.children=[]},events:{},addEventListener(k,f){this.events[k]=f}}}
 for(const id of ['.wave-model','#gw-slider','#gw-state','#gw-time','#gw-r1','#gw-r2'])elements[id]=make();
 elements['#gw-state'].value='damage';
 const root={clientWidth:width,querySelector(s){assert(elements[s],s);return elements[s]}};
 const context={document:{getElementById(id){assert.equal(id,'guided-wave-physical-v2');return root},createElementNS(){return make()}},ResizeObserver:class{constructor(f){this.f=f}observe(){this.f()}}};
 vm.runInNewContext(source,context);
 const data=JSON.parse(fs.readFileSync(path.join(__dirname,'visual-data.json'),'utf8'));
 for(const mode of ['healthy','damage','difference'])for(const idx of [0,35,75,110]){
  elements['#gw-state'].value=mode;elements['#gw-slider'].value=idx;
  elements['#gw-slider'].events.input();elements['#gw-state'].events.change();
  const k=data.x.indexOf(180),value=mode==='difference'?data.damage[idx][k]-data.healthy[idx][k]:data[mode][idx][k];
  assert.equal(elements['#gw-r1'].textContent,'R1：'+value.toFixed(4)+' nm');
  assert(elements['.wave-model'].children.length>500);
  for(const e of elements['.wave-model'].children)for(const v of Object.values(e.attrs))assert(!String(v).includes('NaN'));
 }
}
console.log('PASS: two widths, 24 time/state combinations, readout matches solved data; fragment <1MB.');
