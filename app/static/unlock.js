'use strict';
document.getElementById('unlock').addEventListener('submit', async event => {
  event.preventDefault();
  const button = event.target.querySelector('button');
  button.disabled = true;
  const error = document.getElementById('error');
  error.textContent = '';
  try {
    const response = await fetch('/auth/login', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:document.getElementById('key').value.trim()})});
    const result = await response.json();
    if (!response.ok) throw new Error(result.detail);
    document.getElementById('key').value = '';
    location.replace('/');
  } catch (problem) { error.textContent = problem.message || 'Unable to connect. Check the app terminal.'; }
  finally { button.disabled = false; }
});
