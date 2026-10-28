"use strict";
const $ = (id) => document.getElementById(id);
let points = [];
let isRefreshing = false;
const fmt = (n, decimals=1) => Number(n).toFixed(decimals);
const formatRate = (bps) => { const n = Math.max(0, Number(bps)||0); return n >= 1048576 ? `${fmt(n/1048576)} MB/s` : n >= 1024 ? `${fmt(n/1024)} KB/s` : `${Math.round(n)} B/s`; };
const timeLabel = (iso) => { const d = new Date(iso); return Number.isNaN(d.getTime()) ? 'Unknown' : d.toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}); };
const getJson = async (url) => { const resp=await fetch(url,{cache:'no-store'}); if(!resp.ok) throw new Error(`HTTP ${resp.status}`); return resp.json(); };
function setMetric(id,value,bar,alertAt,stateId){
  $(id).textContent=fmt(value);$(bar).style.width=`${Math.max(0,Math.min(100,value))}%`;
  $(stateId).textContent=value >= alertAt?'Needs attention':'Normal';$(stateId).classList.toggle('warning',value>=alertAt);
}
function renderOverview({sample,alerts}){
  if (!sample) { $('sync').textContent='Waiting for first sample…';return; }
  setMetric('cpu',sample.cpu_percent,'cpu-bar',90,'cpu-state');
  setMetric('memory',sample.memory_percent,'memory-bar',85,'memory-state');
  setMetric('disk',sample.disk_percent,'disk-bar',90,'disk-state');
  $('download').textContent=formatRate(sample.network_down_bps);
  $('upload').textContent=formatRate(sample.network_up_bps);
  $('memory-detail').textContent=`${fmt(sample.memory_used_gb)} / ${fmt(sample.memory_total_gb)} GB`;
  $('disk-detail').textContent=`${fmt(sample.disk_free_gb)} GB free`;
  $('machine').textContent=sample.os_name || 'Local device';
  $('sync').textContent=`Updated ${timeLabel(sample.timestamp)}`;
  const healthy=alerts.length===0;
  $('system-status').textContent=healthy?'Your system looks healthy':'Your system needs attention';
  $('banner-desc').textContent=healthy?'No resource thresholds are being exceeded right now.':`${alerts.length} performance threshold${alerts.length===1?' is':'s are'} exceeded. Review the alerts below.`;
  $('banner-pill').textContent=healthy?'HEALTHY':'REVIEW';
  $('banner-pill').classList.toggle('warn',!healthy);
  $('alert-count').textContent=String(alerts.length);
  const root=$('alerts');root.replaceChildren();
  if(healthy){const container=document.createElement('div');container.className='alert-okay'; const check=document.createElement('span'); check.textContent='✓';const div=document.createElement('div'); const strong=document.createElement('strong');strong.textContent='All checks passed';const small=document.createElement('small'); small.textContent='CPU, memory, and storage are below alert thresholds.';div.append(strong,small);container.append(check,div);root.append(container);return;}
  for(const a of alerts){const item=document.createElement('div');item.className='alert-item'; const icon=document.createElement('span');icon.className='alert-icon'; icon.textContent='⚠';const text=document.createElement('div');const strong=document.createElement('strong');strong.textContent=a.title;const small=document.createElement('small');small.textContent=`${a.detail} ${a.advice}`;text.append(strong,small);item.append(icon,text);root.append(item);}
}
function renderProcesses(data){const root=$('process-list');root.replaceChildren();for(const proc of data.processes||[]){const tr=document.createElement('tr');const name=document.createElement('td');const dot=document.createElement('span');dot.className='process-dot';const label=document.createElement('span');label.className='process-name';label.textContent=proc.name;name.append(dot,label);const pid=document.createElement('td');pid.textContent=String(proc.pid);const mem=document.createElement('td');mem.textContent=`${fmt(proc.memory_mb)} MB`;tr.append(name,pid,mem);root.append(tr);}if(!root.children.length){const tr=document.createElement('tr');const td=document.createElement('td');td.colSpan=3;td.textContent='No process information available';tr.append(td);root.append(tr);}}
function renderSecurity(data){const root=$('security-body');root.replaceChildren();if(data.status!=='available'){const p=document.createElement('p');p.className='security-msg';p.textContent=data.message || 'Security log unavailable';root.append(p);return;}
 const number=document.createElement('div');number.className='security-number';number.textContent=String(data.events.length);const small=document.createElement('span');small.textContent='failed sign-in events (max 25 shown)';number.append(small);const msg=document.createElement('p');msg.className='security-msg';msg.textContent=data.message;root.append(number,msg);
 for(const event of data.events.slice(0,3)){const row=document.createElement('div');row.className='security-row';const a=document.createElement('span');a.textContent='Event 4625';const b=document.createElement('span');b.textContent=timeLabel(event.time);row.append(a,b);root.append(row);}
}
function drawChart(){const canvas=$('activity-chart'), box=canvas.getBoundingClientRect(),ratio=window.devicePixelRatio||1; if(box.width<20)return;
 const w=box.width,h=box.height;canvas.width=Math.max(1,Math.floor(w*ratio));canvas.height=Math.max(1,Math.floor(h*ratio));const c=canvas.getContext('2d');c.scale(ratio,ratio);c.clearRect(0,0,w,h);$('chart-empty').hidden=points.length>0;
 const pad={left:30,right:11,top:13,bottom:14}, pw=w-pad.left-pad.right,ph=h-pad.top-pad.bottom;
 for(let p=0;p<=100;p+=25){const y=pad.top+ph*(1-p/100);c.strokeStyle='#2a3c50';c.lineWidth=.7;c.beginPath();c.moveTo(pad.left,y);c.lineTo(w-pad.right,y);c.stroke();c.fillStyle='#7589a4';c.font='10px Segoe UI,Arial';c.fillText(String(p),0,y+4);}
 if(!points.length)return;
 for(const [key,color] of [['cpu_percent','#5a9cff'],['memory_percent','#bb9afa']]){c.strokeStyle=color;c.lineWidth=2.3;c.lineJoin='round';c.lineCap='round';c.beginPath();points.forEach((p,i)=>{const x=pad.left+(points.length<=1?.5:i/(points.length-1))*pw;const y=pad.top+(1-Math.max(0,Math.min(100,Number(p[key])))/100)*ph;if(i===0)c.moveTo(x,y);else c.lineTo(x,y);});c.stroke();}
}
async function refreshMetrics(){if(isRefreshing)return;isRefreshing=true;try{const [overview,history,processes]=await Promise.all([getJson('/api/overview'),getJson(`/api/history?minutes=${$('window').value}`),getJson('/api/processes')]);renderOverview(overview);points=history.points||[];drawChart();renderProcesses(processes);}catch(e){$('sync').textContent='Connection lost — retrying';console.error('TechPulse refresh:',e);}finally{isRefreshing=false;}}
async function refreshSecurity(){try{renderSecurity(await getJson('/api/security'));}catch(e){renderSecurity({status:'unavailable',message:'Could not fetch security events.'});}}
$('refresh').addEventListener('click',()=>{refreshMetrics();refreshSecurity();});
$('window').addEventListener('change',refreshMetrics);
window.addEventListener('resize',drawChart);
refreshMetrics();refreshSecurity();setInterval(refreshMetrics,15000);setInterval(refreshSecurity,120000);
