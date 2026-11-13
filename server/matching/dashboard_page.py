# ruff: noqa: E501
"""Static page for the matching dashboard: one SVG diagram + a typed log. No libraries, no network."""

PAGE = r"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Matching, step by step</title>
<style>
:root{--bg:#f6f4ef;--ink:#16150f;--mute:#77736a;--rule:#d9d5c9;--acc:#1f3fd1;--font:-apple-system,BlinkMacSystemFont,"Helvetica Neue",Helvetica,Arial,sans-serif;--mono:ui-monospace,"SF Mono",Menlo,monospace}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 var(--font)}
main{max-width:1120px;margin:0 auto;padding:56px 32px 80px}
header{display:flex;justify-content:space-between;align-items:baseline;border-bottom:1px solid var(--ink);padding-bottom:14px}
h1{font:600 26px/1.2 var(--font);letter-spacing:-.01em;margin:0}
.mode{font:12px var(--mono);color:var(--mute)}
.lede{max-width:62ch;color:var(--mute);margin:18px 0 36px}
h2{font:600 12px var(--font);letter-spacing:.08em;text-transform:uppercase;color:var(--mute);margin:0 0 14px}
svg{width:100%;height:auto;display:block}
.steps{display:flex;gap:0;border-top:1px solid var(--rule);margin-top:8px}
.steps div{flex:1;padding:10px 0 0;font-size:12px;color:var(--mute);border-top:2px solid transparent;margin-top:-1px}
.steps div.on{color:var(--ink);border-top-color:var(--acc)}
.caption{min-height:3em;margin:14px 0 0;font-size:17px;max-width:70ch}
section{margin-top:56px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:56px}
@media(max-width:820px){.grid{grid-template-columns:1fr}}
.w{display:grid;grid-template-columns:110px 1fr 48px;align-items:center;gap:10px;padding:5px 0;font-size:14px}
.bar{height:6px;background:var(--rule)}.bar i{display:block;height:100%;background:var(--ink);transition:width .8s}
.w b{font:500 13px var(--mono);text-align:right}
.sub{font-size:13px;color:var(--mute);margin:0 0 10px}
.res{border-top:1px solid var(--rule);margin-top:12px;padding-top:10px;font:13px var(--mono)}
#log{font-size:14px;border-top:1px solid var(--ink)}
.ln{display:grid;grid-template-columns:84px 1fr;gap:14px;padding:9px 0;border-bottom:1px solid var(--rule)}
.k{font:600 11px var(--mono);letter-spacing:.08em;padding-top:3px}
.ln small{display:block;font:12px var(--mono);color:var(--mute)}
.READ .k{color:var(--mute)}.REASON .k{color:var(--acc)}.OUTPUT .k{color:var(--ink)}.CODE .k{color:var(--ink)}
.CODE{background:rgba(22,21,15,.035)}
.legend{font-size:13px;color:var(--mute);margin:0 0 14px;max-width:80ch}
.legend b{color:var(--ink);font-weight:600}
.nd{fill:var(--bg);stroke:var(--ink);stroke-width:1.2}.nd.acc{stroke:var(--acc);stroke-width:2}
.t{font:13px var(--font);fill:var(--ink)}.tm{font:12px var(--mono);fill:var(--mute)}.tl{font:600 11px var(--font);letter-spacing:.08em;fill:var(--mute)}
.ln-wire{stroke:var(--rule);stroke-width:1.5;fill:none}.ln-wire.on{stroke:var(--acc);stroke-dasharray:6 5;animation:d 1s linear infinite}
@keyframes d{to{stroke-dashoffset:-22}}
.hide{opacity:0;transition:opacity .5s}.show{opacity:1}
.hl{fill:var(--acc);font-weight:600}
</style></head><body><main>
<header><h1>How two answers become one match</h1><span class="mode" id="mode">connecting</span></header>
<p class="lede">Anonymous, synthetic players. Muse reads meaning and proposes groups. Code decides how much to trust each signal, then checks every guarantee. Watch one pair go through.</p>
<svg id="fig" viewBox="0 0 1056 420" role="img" aria-label="Two inputs enter Muse, Code checks, a match comes out">
 <text class="tl" x="0" y="16">INPUTS</text><text class="tl" x="440" y="16">DECIDE</text><text class="tl" x="820" y="16">OUTPUT</text>
 <g id="inA"><rect class="nd" x="0" y="40" width="300" height="130"/><text class="tl" x="16" y="64">PLAYER A</text><text class="t" id="ta" x="16" y="90"></text></g>
 <g id="inB"><rect class="nd" x="0" y="250" width="300" height="130"/><text class="tl" x="16" y="274">PLAYER B</text><text class="t" id="tb" x="16" y="300"></text></g>
 <path class="ln-wire" id="wA" d="M300 105 C 370 105, 380 205, 452 205"/>
 <path class="ln-wire" id="wB" d="M300 315 C 370 315, 380 215, 452 215"/>
 <circle class="nd acc" id="muse" cx="520" cy="210" r="64"/><text class="t" x="520" y="206" text-anchor="middle" style="font-weight:600;font-size:18px">Muse</text><text class="tm" id="musesub" x="520" y="226" text-anchor="middle">reads meaning</text>
 <rect class="nd" id="code" x="470" y="318" width="100" height="44"/><text class="t" x="520" y="345" text-anchor="middle">Code</text><text class="tm" x="520" y="380" text-anchor="middle">guarantees</text>
 <path class="ln-wire" id="wC" d="M520 274 L520 318"/>
 <path class="ln-wire" id="wO" d="M584 210 L820 210"/>
 <g id="out" class="hide"><rect class="nd" x="820" y="100" width="236" height="220"/><text class="tl" x="836" y="126" id="ol">RESULT</text>
  <text class="t" x="836" y="158" id="o1" style="font-size:20px;font-weight:600"></text><text class="t" x="836" y="188" id="o2"></text><text class="tm" x="836" y="216" id="o3"></text><text class="tm" x="836" y="238" id="o4"></text><text class="tm" x="836" y="260" id="o5"></text></g>
 <g id="signals" class="hide"><text class="tm" x="320" y="62" id="s1"></text><text class="tm" x="320" y="80" id="s2"></text></g>
</svg>
<div class="steps" id="steps"><div>1 Inputs enter</div><div>2 Signals read</div><div>3 Weights applied</div><div>4 Muse decides</div><div>5 Code checks</div><div>6 Output</div></div>
<p class="caption" id="cap">Waiting for the first pair.</p>

<section><div class="grid">
 <div><h2>Same pair, new player</h2><p class="sub" id="nsub"></p><div id="wn"></div><div class="res" id="rn"></div></div>
 <div><h2>Same pair, established player</h2><p class="sub" id="esub"></p><div id="we"></div><div class="res" id="re"></div></div>
</div></section>

<section><h2>Backend log</h2>
<p class="legend"><b>READ</b> Muse is being given input. <b>REASON</b> what Muse did with it, from the <b>recorded reasoning trace</b>: task, version, model, attempts, latency. Muse's private chain of thought is not available and is not shown. <b>OUTPUT</b> what Muse returned. <b>CODE</b> a guarantee our code enforced.</p>
<div id="log"></div></section>
</main>
<script>
const $=id=>document.getElementById(id);
const esc=s=>String(s).replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
function wrap(el,text,w){el.textContent='';const words=text.split(' ');let line='',n=0;const x=el.getAttribute('x');
 const add=l=>{const t=document.createElementNS('http://www.w3.org/2000/svg','tspan');t.setAttribute('x',x);t.setAttribute('dy',n?'1.35em':'0');t.textContent=l;el.appendChild(t);n++};
 for(const w1 of words){if((line+' '+w1).length>w&&line){add(line);line=w1}else line=line?line+' '+w1:w1}add(line)}
const KIND={READ:'READ',REASON:'REASON',OUTPUT:'OUTPUT',CODE:'CODE'},MARK={READ:'○ read',REASON:'◇ reason',OUTPUT:'● output',CODE:'■ code'};
function logLine(e){const d=document.createElement('div');d.className='ln '+e.k;d.innerHTML='<span class="k">'+MARK[e.k]+'</span><span>'+esc(e.msg)+(e.meta?'<small>'+esc(e.meta)+'</small>':'')+'</span>';
 const L=$('log');L.insertBefore(d,L.firstChild);while(L.children.length>80)L.removeChild(L.lastChild)}
function bars(id,w){$(id).innerHTML=[['Keywords',w.keyword],['Activity',w.activity],['Muse meaning',w.muse]].map(([n,v])=>'<div class="w"><span>'+n+'</span><span class="bar"><i style="width:'+Math.round(v*100)+'%"></i></span><b>'+v.toFixed(2)+'</b></div>').join('')}
const sleep=ms=>new Promise(r=>setTimeout(r,ms));let busy=false;const queue=[];
async function play(p){busy=true;const S=[...$('steps').children];const on=i=>S.forEach((s,j)=>s.classList.toggle('on',j===i));
 const w=['wA','wB','wC','wO'];w.forEach(i=>$(i).classList.remove('on'));$('out').className.baseVal='hide';$('signals').className.baseVal='hide';$('muse').classList.remove('acc');
 wrap($('ta'),p.a,38);wrap($('tb'),p.b,38);$('musesub').textContent='reads meaning';
 on(0);$('cap').textContent='Two anonymous answers arrive. Neither player knows who the other is.';await sleep(1800);
 on(1);$('wA').classList.add('on');$('wB').classList.add('on');$('s1').textContent='shared words: '+(p.shared.length?p.shared.join(', '):'none');$('s2').textContent='keyword similarity '+p.cosine.toFixed(2);$('signals').className.baseVal='show';
 $('cap').innerHTML=p.shared.length?'Only <span class="hl">'+p.shared.length+'</span> word(s) overlap. Keywords alone see a '+(p.cosine<.2?'weak':'partial')+' link.':'No words overlap. Keywords alone see nothing.';await sleep(2400);
 on(2);bars('wn',p.wn);bars('we',p.we);$('nsub').textContent=p.nsub;$('esub').textContent=p.esub;
 $('rn').textContent='closeness '+p.cn.toFixed(3)+' = '+p.cosine.toFixed(2)+' × '+p.wn.keyword.toFixed(2)+' + activity '+p.wn.activity.toFixed(2)+' × boost '+p.boost.toFixed(2);
 $('re').textContent='closeness '+p.ce.toFixed(3)+' = '+p.cosine.toFixed(2)+' × '+p.we.keyword.toFixed(2)+' + activity '+p.we.activity.toFixed(2)+' × boost '+p.boost.toFixed(2);
 $('cap').textContent='A new player has one answer and no history, so keywords and activity count for less and Muse meaning carries more. An established player is the opposite.';await sleep(3200);
 on(3);$('muse').classList.add('acc');$('wC').classList.add('on');$('musesub').textContent=p.muse.called?'deciding':'not called (offline)';
 $('cap').textContent=p.muse.called?'Muse reads both answers for meaning and proposes who belongs together.':'Muse not called (offline). Code estimate only; run with --live to see Muse decide.';await sleep(2200);
 on(4);$('wO').classList.add('on');$('cap').textContent='Code checks size, everyone placed once, blocked pairs apart, and that no answer is quoted.';await sleep(2200);
 on(5);const o=p.muse;$('out').className.baseVal='show';
 $('o1').textContent=o.called?(o.matched?'Matched':'Not matched'):'Not decided';
 $('o2').textContent=o.called&&o.matched?(o.meaning||''):(o.called?'different groups':'Muse not called');
 $('o3').textContent='brightness '+p.band+' · est. '+p.ce.toFixed(2);$('o4').textContent=o.called?'confidence '+(o.confidence==null?'n/a':o.confidence.toFixed(2)):'offline';$('o5').textContent=p.scenario;
 $('cap').textContent=o.called?(o.matched?'Same constellation. Neither of them sees the other’s words.':'Kept apart. Fewer shared meanings than other pairings available.'):'Offline: the diagram shows the code side only.';await sleep(3600);
 busy=false;if(queue.length)play(queue.shift())}
const es=new EventSource('/events');
es.onmessage=m=>{const e=JSON.parse(m.data);if(e.k==='mode'){$('mode').textContent=e.msg}else if(e.k==='pair'){if(busy){queue.splice(0,queue.length,e)}else play(e)}else if(KIND[e.k])logLine(e)};
es.onerror=()=>{$('mode').textContent='disconnected'};
</script></body></html>"""
