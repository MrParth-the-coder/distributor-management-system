function setTheme(theme){
  document.documentElement.setAttribute('data-theme', theme);
  const btn = document.getElementById('themeToggle');
  if(btn){btn.textContent = theme === 'dark' ? 'Light' : 'Dark';}
  try{localStorage.setItem('theme', theme);}catch(e){}
}
function initTheme(){
  const saved = (function(){try{return localStorage.getItem('theme');}catch(e){return null;}})();
  if(saved){setTheme(saved);return;}
  const prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
  setTheme(prefersDark ? 'dark' : 'light');
}
function autoDismissAlerts(){
  const alerts = document.querySelectorAll('.alert');
  alerts.forEach(alert=>{
    const t = parseInt(alert.getAttribute('data-autodismiss') || '3000',10);
    setTimeout(()=>{
      try{
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alert);
        bsAlert.close();
      }catch(e){}
    },t);
  });
}
function passwordStrengthMeter(){
  const pw = document.getElementById('password');
  const meter = document.getElementById('pwStrength');
  const bar = document.getElementById('pwStrengthBar');
  if(!pw || !meter || !bar) return;
  const update = ()=>{
    const v = pw.value || '';
    let score = 0;
    if(v.length >= 8) score += 25;
    if(/[A-Z]/.test(v)) score += 25;
    if(/[a-z]/.test(v)) score += 10;
    if(/[0-9]/.test(v)) score += 10;
    if(/[\W_]/.test(v)) score += 30;
    score = Math.max(0, Math.min(100, score));
    bar.style.width = score + '%';
    bar.classList.remove('bg-danger','bg-warning','bg-success','bg-primary');
    if(score < 40) bar.classList.add('bg-danger');
    else if(score < 70) bar.classList.add('bg-warning');
    else bar.classList.add('bg-success');
    meter.textContent = score < 40 ? 'Weak' : score < 70 ? 'Good' : 'Strong';
  };
  pw.addEventListener('input', update);
  update();
}
document.addEventListener('DOMContentLoaded', ()=>{
  initTheme();
  autoDismissAlerts();
  passwordStrengthMeter();
});

