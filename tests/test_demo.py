import shutil
import subprocess
from pathlib import Path
import pytest


def test_demo_scenarios_use_computed_thresholds_and_explicit_missing_data():
    node=shutil.which('node')
    if not node:
        pytest.skip('Node is needed for browser-demo logic tests')
    result=subprocess.run([node,'-e',r'''
const fs=require('fs'),vm=require('vm'),assert=require('assert');let scenario='normal';
const c={window:{},URL,document:{getElementById:()=>({value:scenario})}};vm.createContext(c);vm.runInContext(fs.readFileSync('demo/demo.js','utf8'),c);
(async()=>{const api=c.window.demoApi;assert.equal((await api('/api/overview')).alerts.length,0);scenario='pressure';assert.equal((await api('/api/overview')).alerts.length,3);scenario='stale';const stale=await api('/api/overview');assert.equal(stale.alerts.length,0);assert.equal(stale.collection.state,'stale');scenario='empty';assert.equal((await api('/api/overview')).sample,null);assert.equal((await api('/api/history')).points.length,0);assert.equal((await api('/api/security')).status,'unavailable');})();
'''],cwd=Path(__file__).resolve().parents[1],capture_output=True,text=True)
    assert result.returncode == 0, result.stderr
