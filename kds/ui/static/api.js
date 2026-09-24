export async function api(path, options={}) {
  const response = await fetch('/api/v2'+path, options);
  const contentType=response.headers.get('content-type')||'';
  const data=contentType.includes('json')?await response.json():{error:await response.text()};
  if (!response.ok) { const error=new Error(data.error || `HTTP ${response.status}`); error.status=response.status; throw error; }
  return data;
}
export const post = (path, data) => api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});
export const showJSON = (id, value) => { const element=document.getElementById(id); if(element) element.textContent=JSON.stringify(value,null,2); };
export const formatNumber=(value,digits=2)=>value===null||value===undefined||value===''?'—':new Intl.NumberFormat('tr-TR',{maximumFractionDigits:digits}).format(value);
export const formatDate=value=>value?new Date(value).toLocaleString('tr-TR'):'—';
export function facts(id, entries) {
  const element=document.getElementById(id); if(!element)return; element.replaceChildren();
  for(const [label,value] of entries) { const dt=document.createElement('dt'),dd=document.createElement('dd'); dt.textContent=label; dd.textContent=typeof value==='number'?formatNumber(value,6):value ?? 'Veri yok'; element.append(dt,dd); }
}
export function message(text,error=false) { const element=document.getElementById('message'); element.textContent=text;element.className=error?'error':''; clearTimeout(message.timer);message.timer=setTimeout(()=>{if(element.textContent===text)element.textContent='';},7000); }
export function badge(text,kind='') { const span=document.createElement('span');span.className=`status-pill ${kind}`;span.textContent=text;return span; }
export function table(headers, rows) { const value=document.createElement('table'),head=document.createElement('tr');headers.forEach(label=>{const th=document.createElement('th');th.textContent=label;head.append(th);});value.append(head);rows.forEach(row=>{const tr=document.createElement('tr');row.forEach(cell=>{const td=document.createElement('td');if(cell instanceof Node)td.append(cell);else td.textContent=cell??'—';tr.append(td);});value.append(tr);});return value; }
export function kpis(id, values){const root=document.getElementById(id);root.replaceChildren();for(const [label,value] of values){const card=document.createElement('div');card.className='kpi';const caption=document.createElement('span'),strong=document.createElement('strong');caption.textContent=label;strong.textContent=value;card.append(caption,strong);root.append(card);}}
