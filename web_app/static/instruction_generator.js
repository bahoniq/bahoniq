(() => {
  const $ = s => document.querySelector(s);
  const steps = $('#igSteps');
  if (!steps) return;
  let result = null;
  const renumber = () => [...steps.children].forEach((card,i)=>card.querySelector('.ig-step-title').textContent=`Шаг ${i+1}`);
  function addStep(data={}) {
    const card=document.createElement('article'); card.className='ig-step card';
    card.innerHTML=`<div class="ig-step-head"><strong class="ig-step-title"></strong><div><button type="button" class="button secondary ig-up">↑</button><button type="button" class="button secondary ig-down">↓</button><button type="button" class="button danger ig-delete">Удалить</button></div></div><label>Черновое описание<textarea class="ig-text" rows="4" placeholder="Например: потом заходим в раздел заявки и нажимаем согласовать…"></textarea></label><label>Подпись к скриншоту<input class="ig-caption" placeholder="Например: Раздел новых заявок"></label><label class="file-drop ig-drop"><input class="ig-image" type="file" accept="image/png,image/jpeg,image/webp"><span class="file-title">Загрузите скриншот или вставьте Ctrl+V</span><small class="ig-file-name">PNG, JPG или WebP</small></label><img class="ig-preview hidden" alt="Предпросмотр"><textarea class="ig-data hidden"></textarea>`;
    card.querySelector('.ig-text').value=data.text||''; card.querySelector('.ig-caption').value=data.caption||'';
    const setImage=(file)=>{ if(!file)return; const reader=new FileReader(); reader.onload=()=>{card.querySelector('.ig-data').value=reader.result; const im=card.querySelector('.ig-preview');im.src=reader.result;im.classList.remove('hidden');card.querySelector('.ig-file-name').textContent=file.name};reader.readAsDataURL(file)};
    card.querySelector('.ig-image').onchange=e=>setImage(e.target.files[0]);
    card.addEventListener('paste',e=>{const f=[...e.clipboardData.files].find(x=>x.type.startsWith('image/'));if(f){e.preventDefault();setImage(f)}});
    card.querySelector('.ig-delete').onclick=()=>{if(steps.children.length>1)card.remove();renumber()};
    card.querySelector('.ig-up').onclick=()=>{if(card.previousElementSibling)steps.insertBefore(card,card.previousElementSibling);renumber()};
    card.querySelector('.ig-down').onclick=()=>{if(card.nextElementSibling)steps.insertBefore(card.nextElementSibling,card);renumber()};
    steps.appendChild(card);renumber();
  }
  const payload=()=>({title:$('#igTitle').value,audience:$('#igAudience').value,department:$('#igDepartment').value,intro:$('#igIntro').value,steps:[...steps.children].map(c=>({text:c.querySelector('.ig-text').value,caption:c.querySelector('.ig-caption').value,image:c.querySelector('.ig-data').value}))});
  $('#igAdd').onclick=()=>addStep();
  $('#igGenerate').onclick=async()=>{const btn=$('#igGenerate'),status=$('#igStatus');btn.disabled=true;status.textContent='ИИ обрабатывает черновик…';try{const r=await fetch('/api/instruction-generator/generate',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(payload())});const d=await r.json();if(!r.ok)throw new Error(d.detail||'Ошибка генерации');result=d;render(d);status.textContent=`Готово · ${d.steps.length} шагов · ${d.provider}`}catch(e){status.textContent=e.message}finally{btn.disabled=false}};
  function render(d){const preview=$('#igResult');preview.innerHTML=`<header><h1>${escapeHtml(d.title)}</h1><p>${escapeHtml([d.department,d.audience].filter(Boolean).join(' · '))}</p></header>${d.intro?`<p>${escapeHtml(d.intro)}</p>`:''}`+d.steps.map(s=>`<section><h2>Шаг ${s.number}</h2><p>${escapeHtml(s.text)}</p>${s.note?`<aside><b>Примечание.</b> ${escapeHtml(s.note)}</aside>`:''}${s.image?`<img src="${s.image}" alt=""><small>Рисунок ${s.number}. ${escapeHtml(s.caption)}</small>`:''}</section>`).join('');preview.classList.remove('hidden');$('#igExports').classList.remove('hidden')}
  const escapeHtml=s=>String(s||'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]));
  document.querySelectorAll('[data-ig-export]').forEach(b=>b.onclick=async()=>{if(!result)return;const kind=b.dataset.igExport;const r=await fetch(`/api/instruction-generator/export/${kind}`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(result)});if(!r.ok)return;const blob=await r.blob(),a=document.createElement('a');a.href=URL.createObjectURL(blob);a.download=`instruction.${kind}`;a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000)});
  addStep();
})();
