import {api,post,showJSON,message} from './api.js';
export function wireImports(root,refresh,safe){
  let batch=null;
  const render=data=>{batch=data.id || data.batch_id;document.getElementById('import-preview').hidden=false;showJSON('preview',data);document.getElementById('mapping').value=JSON.stringify(data.mapping||{},null,2);};
  document.getElementById('upload-form').onsubmit=e=>{e.preventDefault();safe(async()=>{render(await api(root()+'/imports',{method:'POST',body:new FormData(e.target)}));await refresh();});};
  document.getElementById('map-import').onclick=()=>safe(async()=>{render(await post(root()+`/imports/${batch}/mapping`,{mapping:JSON.parse(document.getElementById('mapping').value)}));});
  document.getElementById('confirm-import').onclick=()=>safe(async()=>{render(await post(root()+`/imports/${batch}/confirm`,{confirm:true,acknowledge_warnings:document.getElementById('acknowledge').checked}));await refresh();message('Aktarım onaylandı.');});
  document.getElementById('scientific-form').onsubmit=e=>{e.preventDefault();safe(async()=>{const file=new FormData(e.target).get('file');await post(root()+'/scientific-inputs',JSON.parse(await file.text()));await refresh();message('Bilimsel girdiler kaydedildi; hazırlık raporu yenilendi.');});};
}
