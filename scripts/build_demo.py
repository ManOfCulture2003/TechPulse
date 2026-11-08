"""Build a static demo. Never reads the build machine's metrics or database."""
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'demo'
OUT.mkdir(exist_ok=True)
static=ROOT/'app/static'
html=(static/'index.html').read_text(encoding='utf-8')
html=html.replace('/static/styles.css','./styles.css').replace('/static/app.js','./app.js')
html=html.replace('<script defer src="./app.js">','<script defer src="./demo.js"></script><script defer src="./app.js">')
html=html.replace('<main', '<main',1).replace('<div class="layout">','<section class="demo-notice"><strong>TechPulse interactive demo — no account needed.</strong><p>These are synthetic sample readings, not measurements from your device. Try a scenario, inspect the charts, and export the sample report. Nothing is sent to the project owner.</p><label>Sample scenario <select id="scenario"><option value="normal">Normal resource usage</option><option value="pressure">High CPU, memory and disk usage</option><option value="stale">Collector stopped / stale readings</option><option value="empty">No readings available</option></select></label> <a href="https://github.com/ManOfCulture2003/TechPulse/tree/secure-local-and-demo-nov08#start-on-windows-beginner-friendly" target="_blank" rel="noopener">Run on your own computer →</a></section><div class="layout">')
html=html.replace('Lock workspace','Reset demo').replace('Local agent connected','Demo · no device connected').replace('Live system metrics','Sample system metrics').replace('Auto-refreshes every 15 seconds','Synthetic sample · change the scenario above').replace('Your PC, at a glance.','Explore a sample PC report.').replace('All monitoring stays on this computer. No cloud account.','This demo does not read your computer or collect personal data.').replace('Data stored locally for up to 7 days while monitoring runs','Synthetic data only · no uploads or tracking').replace('href="/api/docs"','href="https://github.com/ManOfCulture2003/TechPulse"').replace('API documentation','Source code').replace('Waiting for the first system sample.','Choose a sample scenario to explore.')
html=re.sub(r'<h1>.*?</h1>','<h1>Explore a sample PC report.</h1>',html)
html=html.replace('aria-label="Live system health"','aria-label="Sample system health"')
(OUT/'index.html').write_text(html,encoding='utf-8')
css=(static/'styles.css').read_text(encoding='utf-8')
css+='\n.demo-notice{padding:22px 28px;background:#142c35;color:#dff9f2;border-bottom:2px solid #3fd9b5;position:relative;z-index:3}.demo-notice p{line-height:1.6}.demo-notice select{padding:9px;background:#192c3e;color:white;border:1px solid #7698ab;border-radius:6px}.demo-notice a{color:#6deace;margin-left:16px}.layout{min-height:100vh}.sidebar{position:relative;top:auto}button:focus-visible,a:focus-visible,select:focus-visible{outline:3px solid #64f2d4;outline-offset:3px}\n'
(OUT/'styles.css').write_text(css,encoding='utf-8')
js=(static/'app.js').read_text(encoding='utf-8')
start=js.index('const getJson =');end=js.index('function setMetric',start)
js=js[:start]+'const getJson = async url => window.demoApi(url);\n'+js[end:]
js=js[:js.index("document.getElementById('lock').addEventListener")]
js=js.replace('Updated ${timeLabel(sample.timestamp)}','Sample time ${timeLabel(sample.timestamp)}')
js += "\n$('scenario').addEventListener('change',()=>{refreshMetrics();refreshSecurity();});$('lock').addEventListener('click',()=>{$('scenario').value='normal';$('window').value='120';refreshMetrics();refreshSecurity();});document.querySelectorAll('a[href^=\"/api/\"]').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();window.exportDemo(a.getAttribute('href'));}));\n"
(OUT/'app.js').write_text(js,encoding='utf-8')
(OUT/'.nojekyll').touch()
