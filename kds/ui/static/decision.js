import {api,message} from './api.js';
import {renderRun} from './results.js';

async function loadDecision(){
  const query=new URLSearchParams(location.search);
  const projectId=query.get('project_id');
  const runId=query.get('run_id');
  const profile=query.get('execution_profile');
  if(!projectId||!runId||profile!=='VERIFIED_INSTITUTIONAL')throw new Error('Geçerli project_id, run_id ve VERIFIED_INSTITUTIONAL profili gerekir. Referans veriye otomatik geçiş yapılmadı.');
  const [projectDocument,run]=await Promise.all([
    api(`/projects/${encodeURIComponent(projectId)}`),
    api(`/projects/${encodeURIComponent(projectId)}/analyses/${encodeURIComponent(runId)}`),
  ]);
  if(run.project_id!==projectId||run.id!==runId||run.execution_profile!==profile)throw new Error('Project/run/profile bağlamı uyuşmuyor. Ekran fail-closed kapatıldı.');
  document.getElementById('decision-title').textContent=projectDocument.project.name;
  document.getElementById('decision-subtitle').textContent=`${projectDocument.project.planning_year} · ${projectDocument.project.basin_or_irrigation_area||projectDocument.project.province_or_region||'Proje kapsamı'} · ${run.scenario} · ${run.algorithm}`;
  document.getElementById('decision-run-id').textContent=`Run: ${run.id}`;
  document.getElementById('back-to-project').href=`/projects#project=${encodeURIComponent(projectId)}`;
  const synthetic=run.result_authority_label==='SYNTHETIC / NOT_OFFICIAL'||run.result?.classification==='SYNTHETIC_TEST_OUTPUT';
  document.getElementById('decision-authority').hidden=!synthetic;
  renderRun(run);
}

loadDecision().catch(error=>{message(error.message,true);document.getElementById('decision-title').textContent='Karar ekranı açılamadı';document.getElementById('decision-subtitle').textContent='Kurumsal bağlam doğrulanamadı; Akkaya/reference fallback uygulanmadı.';});
