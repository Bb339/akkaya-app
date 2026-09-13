export async function api(path, options={}) {
  const response = await fetch('/api/v2'+path, options);
  const data = await response.json();
  if (!response.ok) throw new Error(data.error || `HTTP ${response.status}`);
  return data;
}
export const post = (path, data) => api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
export const showJSON = (id, value) => { document.getElementById(id).textContent = JSON.stringify(value,null,2); };
export function facts(id, entries) {
  const element=document.getElementById(id); element.replaceChildren();
  for(const [label,value] of entries) {
    const dt=document.createElement('dt'),dd=document.createElement('dd');
    dt.textContent=label; dd.textContent=typeof value==='number'?new Intl.NumberFormat('tr-TR',{maximumFractionDigits:6}).format(value):value ?? 'Veri yok'; element.append(dt,dd);
  }
}
export function message(text,error=false) {
  const e=document.getElementById('message');e.textContent=text;e.className=error?'error':'';
}
