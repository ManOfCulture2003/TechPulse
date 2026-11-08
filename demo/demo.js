'use strict';
function sampleScenario() { return document.getElementById('scenario').value; }
function demoPoints(minutes=120) {
  if(sampleScenario()==='empty') return [];
  const high=sampleScenario()==='pressure';
  const count=Math.min(240,Math.floor(minutes/2)+1);
  return Array.from({length:count},(_,i)=>({timestamp:new Date(Date.UTC(2026,0,15,12)-minutes*60000+i*minutes*60000/(count-1)).toISOString(),cpu_percent:Math.round(high?92+3*Math.sin(i/7):25+8*Math.sin(i/7)),memory_percent:high?91:42,disk_percent:high?95:63,memory_used_gb:high?29.12:13.44,memory_total_gb:32,disk_free_gb:high?25:185,disk_total_gb:500,network_up_bps:12000,network_down_bps:240000}));
}
window.demoApi = async path => {
  const url=new URL(path,'https://demo.invalid');
  const scenario=sampleScenario(), rows=demoPoints(Number(url.searchParams.get('minutes')||120));
  if(url.pathname==='/api/history') return {points:rows};
  if(url.pathname==='/api/processes') return {processes:scenario==='empty'?[]:[{name:'Example browser (sample)',pid:100,memory_mb:640},{name:'Example editor (sample)',pid:200,memory_mb:220}]};
  if(url.pathname==='/api/security') return {status:'unavailable',events:[],message:'Demo only. No Windows Security log was read. The local app checks access on your own PC.'};
  if(url.pathname==='/api/overview') {
    const sample=rows.at(-1)||null;
    if(sample) sample.os_name='Example Windows device · synthetic';
    const live=scenario!=='stale'&&scenario!=='empty';
    const alerts=[];
    for(const [key,threshold,title] of [['cpu_percent',90,'High CPU load'],['memory_percent',85,'Memory pressure'],['disk_percent',90,'Storage running low']]) {
      if(live&&sample[key]>=threshold) alerts.push({title,detail:`Sample ${sample[key]}% (threshold ${threshold}%).`,advice:'Inspect the sample trend. Run the local app for real device readings.'});
    }
    return {sample,alerts,collection:{state:scenario==='empty'?'waiting':scenario==='stale'?'stale':'fresh',age_seconds:scenario==='stale'?600:0},collector:{state:scenario==='stale'?'stopped':scenario==='empty'?'disabled':'running'}};
  }
  throw Error('This endpoint is not part of the browser demo.');
};
window.exportDemo = path => {
  const rows=demoPoints(60),csv=path.includes('.csv');
  const keys=['timestamp','cpu_percent','memory_percent','disk_percent','memory_used_gb','memory_total_gb','disk_free_gb','disk_total_gb','network_up_bps','network_down_bps'];
  const data=csv?['data_source,'+keys.join(','),...rows.map(row=>'synthetic,'+keys.map(k=>row[k]).join(','))].join('\n'):JSON.stringify({data_source:'synthetic',scenario:sampleScenario(),notice:'Demo report. No visitor device was measured.',sample_count:rows.length,average_cpu_percent:rows.length?rows.reduce((n,r)=>n+r.cpu_percent,0)/rows.length:null,points:rows},null,2);
  const url=URL.createObjectURL(new Blob([data],{type:csv?'text/csv':'application/json'}));const a=document.createElement('a');a.href=url;a.download='techpulse-demo.'+(csv?'csv':'json');a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
};
