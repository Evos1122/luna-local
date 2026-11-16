'use strict';
const $=id=>document.getElementById(id);
let history=[], attachments=[], token='', busy=false, settings=null, conns={}, pullTimer=null,ctl=null,stopped=false,askResolve=null,listening=false,rec=null;
// Husk brugerens valg i denne browser; nye installationer beholder HTML-standarderne.
const CHAT_PREFERENCE_KEY='luna.chat-preferences.v1';
const CHAT_PREFERENCE_IDS=['solo','memory','think','agents','skills','tools','edit','web','full','confirm','folders','github','mcp'];
let chatPreferences={};
try{
  const saved=JSON.parse(localStorage.getItem(CHAT_PREFERENCE_KEY));
  if(saved&&typeof saved==='object'&&!Array.isArray(saved)){
    for(const id of CHAT_PREFERENCE_IDS)if(typeof saved[id]==='boolean')chatPreferences[id]=saved[id];
  }
}catch{} // Browseren kan have blokeret lagring, eller gamle data kan være ugyldige.
function rememberChatPreference(id){
  chatPreferences[id]=$(id).checked;
  try{localStorage.setItem(CHAT_PREFERENCE_KEY,JSON.stringify(chatPreferences));}catch{}
}
for(const id of CHAT_PREFERENCE_IDS){
  if(typeof chatPreferences[id]==='boolean')$(id).checked=chatPreferences[id];
  $(id).addEventListener('change',()=>rememberChatPreference(id));
}
async function status(){try{const r=await fetch('/api/status');const s=await r.json();token=s.token||'';$('status').textContent=s.ready?'● Klar — '+s.model:s.online?'● Ollama kører. Modellen '+s.model+' mangler.':'○ Åbn Ollama eller kør ollama serve.';$('modelname').textContent=s.model||'Model';conns=s.connections||{};document.querySelectorAll('.conn').forEach(el=>{el.hidden=!conns[el.dataset.conn];$(el.dataset.conn).checked=!!conns[el.dataset.conn]&&chatPreferences[el.dataset.conn]===true;});}catch{$('status').textContent='Serveren svarer ikke.';}}
function message(role,text,image){
  $('welcome')?.remove();
  const el=document.createElement('article');el.className='message '+role;
  const who=document.createElement('strong');who.className='who';who.textContent=role==='user'?'DIG':role==='error'?'FEJL':'LUNA LOCAL';el.append(who);
  const content=document.createElement('div');content.textContent=text;el.append(content);
  const live=document.createElement('div');live.className='live-status';live.hidden=true;el.append(live);
  for(const src of (Array.isArray(image)?image:image?[image]:[])){const img=document.createElement('img');img.src=src;img.alt='Dit vedhæftede billede';el.append(img);}
  if(role==='assistant'){const b=document.createElement('button');b.textContent='Kopiér svar';b.onclick=()=>navigator.clipboard.writeText(content.textContent).then(()=>{b.textContent='Kopieret';}).catch(()=>{b.textContent='Markér teksten og kopiér';});el.append(b);}
  $('messages').append(el);el.scrollIntoView({block:'end'});return {el,content,status:live};
}
function detail(el,title,value){const d=document.createElement('details'),s=document.createElement('summary'),p=document.createElement('div');s.textContent=title;p.textContent=value;d.append(s,p);el.append(d);}
const MAX_BILLEDE=3000000, dataUrl=f=>new Promise((res,rej)=>{const r=new FileReader();r.onload=()=>res(r.result);r.onerror=rej;r.readAsDataURL(f);});
function tegnBillede(src,skala,fmt){return new Promise(resolve=>{const img=new Image();img.onload=()=>{const c=document.createElement('canvas');c.width=Math.max(1,Math.round(img.naturalWidth*skala));c.height=Math.max(1,Math.round(img.naturalHeight*skala));c.getContext('2d').drawImage(img,0,0,c.width,c.height);let u='';try{u=c.toDataURL(fmt,0.92);}catch(e){u='';}resolve(u);};img.onerror=()=>resolve('');img.src=src;});}
async function billedData(f){
  /* Returnerer en dataURL i PNG/JPEG på højst 3 MB — eller null. */
  if(!f)return null;
  const src=await dataUrl(f).catch(()=>null);if(!src)return null;
  const passer=u=>u.length<=(MAX_BILLEDE*4/3)+16;
  const png=src.startsWith('data:image/png'), jpeg=src.startsWith('data:image/jpeg');
  if((png||jpeg)&&passer(src))return src;                 // allerede pænt og lille nok
  for(const skala of [1,0.75,0.5,0.25]){
    const prov=await tegnBillede(src,skala,'image/png');   // skarphed først (skærmbilleder)
    if(prov&&passer(prov))return prov;
    if(skala===1){const j=await tegnBillede(src,1,'image/jpeg');if(j&&passer(j))return j;}
  }
  return null;
}
let readingFiles=0;
const TEXT_EXT=/\.(txt|md|markdown|csv|tsv|json|jsonl|js|mjs|cjs|jsx|ts|tsx|py|html|css|xml|yaml|yml|toml|ini|log|sh|ps1|sql|rs|go|java|c|h|cpp|cs|vue|svelte)$/i;
function renderAttachments(){
  $('attachment').replaceChildren();
  attachments.forEach((file,index)=>{
    const row=document.createElement('div');row.className='attachment-item';
    if(file.image){const img=document.createElement('img');img.src=file.image;img.alt=file.name;row.append(img);}
    const label=document.createElement('span');label.textContent=file.name;row.append(label);
    const button=document.createElement('button');button.type='button';button.textContent='Fjern';
    button.setAttribute('aria-label','Fjern '+file.name);
    button.onclick=()=>{if(busy)return;attachments.splice(index,1);renderAttachments();};
    row.append(button);$('attachment').append(row);
  });
}
function clearImage(){attachments=[];$('image').value='';renderAttachments();}
async function addFiles(files){
  if(busy)return;
  readingFiles++;$('send').disabled=true;
  try{for(const file of files){
    try{
      if(!file.type.startsWith('image/')&&file.size>3000000)throw new Error('Filen er for stor (højst 3 MB).');
      const bytes=new Uint8Array(await file.arrayBuffer());
      const png=[137,80,78,71,13,10,26,10].every((v,i)=>bytes[i]===v);
      const jpeg=bytes[0]===255&&bytes[1]===216&&bytes[2]===255;
      let item={name:file.name};
      if(png||jpeg||file.type.startsWith('image/')){
        item.image=await billedData(file);
        if(!item.image)throw new Error('Billedet kunne ikke bruges — det skal ende som PNG eller JPEG på højst 3 MB.');
      }else if(/\.(pdf|docx)$/i.test(file.name)){
        if(!token)await status();
        if(!token)throw new Error('Serveren svarer ikke. Prøv igen.');
        const encoded=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result.split(',')[1]);reader.onerror=()=>reject(new Error('Filen kunne ikke læses.'));reader.readAsDataURL(file);});
        item.text=(await api('/api/attachments/extract',{name:file.name,data:encoded})).text;
      }else{
        if(!TEXT_EXT.test(file.name)&&!file.type.startsWith('text/'))throw new Error('Brug PNG/JPEG, PDF, Word (.docx) eller en tekst-/kodefil.');
        try{item.text=new TextDecoder('utf-8',{fatal:true}).decode(bytes);}catch{throw new Error('Tekstfilen skal være gemt som UTF-8.');}
        if(/[\x00-\x08\x0e-\x1f]/.test(item.text))throw new Error('Filen indeholder binære data.');
        if(!item.text.trim())throw new Error('Tekstfilen er tom.');
        if(item.text.length>12000)throw new Error('Tekstfilen må højst indeholde 12.000 tegn.');
      }
      if(attachments.length>=8)throw new Error('Højst otte vedhæftninger ad gangen.');
      if(item.image&&attachments.filter(f=>f.image).length>=2)throw new Error('Højst to billeder ad gangen.');
      const textSize=attachments.reduce((n,f)=>n+(f.text?.length||0),0)+(item.text?.length||0);
      if(textSize>12000)throw new Error('Filerne må tilsammen højst indeholde 12.000 tegn.');
      attachments.push(item);renderAttachments();
    }catch(error){message('error',file.name+': '+error.message);}
  }}finally{readingFiles--;$('send').disabled=busy||readingFiles>0;$('image').value='';}
}
$('image').onchange=()=>addFiles(Array.from($('image').files));
document.addEventListener('paste',event=>{
  const clipboard=event.clipboardData;if(!clipboard)return;
  let files=Array.from(clipboard.files||[]);
  if(!files.length)files=Array.from(clipboard.items||[]).filter(item=>item.kind==='file'&&/^image\//.test(item.type)).map(item=>item.getAsFile()).filter(Boolean);
  if(files.length){event.preventDefault();if(busy){message('error','Vent til det nuværende svar er færdigt.');return;}addFiles(files);}
});
let dragDepth=0;
window.addEventListener('dragenter',event=>{
  if(!Array.from(event.dataTransfer?.types||[]).includes('Files'))return;
  event.preventDefault();dragDepth++;if(!busy)$('form').classList.add('drag-over');
});
window.addEventListener('dragover',event=>{
  if(!Array.from(event.dataTransfer?.types||[]).includes('Files'))return;
  event.preventDefault();event.dataTransfer.dropEffect=busy?'none':'copy';
});
window.addEventListener('dragleave',()=>{if(--dragDepth<=0){dragDepth=0;$('form').classList.remove('drag-over');}});
window.addEventListener('drop',event=>{
  event.preventDefault();dragDepth=0;$('form').classList.remove('drag-over');
  addFiles(Array.from(event.dataTransfer?.files||[]));
});
$('new').onclick=()=>{if(busy||readingFiles)return;history=[];clearImage();$('messages').replaceChildren();message('assistant','Ny samtale. Hvad skal vi lave?');};
$('refresh').onclick=status;
document.querySelectorAll('[data-prompt]').forEach(b=>b.onclick=()=>{$('prompt').value=b.dataset.prompt;if(b.dataset.prompt.startsWith('List')){$('tools').checked=true;rememberChatPreference('tools');}$('prompt').focus();});
$('prompt').onkeydown=e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();$('form').requestSubmit();}};
const FLAGS=['send','new','image','think','agents','skills','tools','edit','web','full','confirm','solo','memory','folders','github','mcp','openSettings'];
async function api(path,body){const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Luna-Token':token},body:JSON.stringify(body),signal:ctl?ctl.signal:undefined});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||'Serverfejl');return d;}
function updateLiveStatus(pending,label,startedAt){
  pending.status.dataset.label=label||'';
  if(!label){pending.status.hidden=true;pending.status.textContent='';return;}
  const seconds=Math.floor((Date.now()-startedAt)/1000),minutes=Math.floor(seconds/60),rest=String(seconds%60).padStart(2,'0');
  pending.status.hidden=false;pending.status.textContent=label+' · '+minutes+':'+rest;
}
async function streamApi(path,body,onEvent){
  const r=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Luna-Token':token},body:JSON.stringify(body),signal:ctl?ctl.signal:undefined});
  if(!r.ok){const d=await r.json().catch(()=>({}));throw new Error(d.error||'Serverfejl');}
  if(!r.body)throw new Error('Browseren kan ikke læse live-svaret.');
  const reader=r.body.getReader(),decoder=new TextDecoder();let buffer='',result=null;
  const dispatch=frame=>{
    const line=frame.split('\n').find(item=>item.startsWith('data:'));
    if(!line)return;
    const event=JSON.parse(line.slice(5).trim());
    if(event.type==='error')throw new Error(event.message||'Serverfejl');
    if(event.type==='done'){result=event.result;return;}
    onEvent(event);
  };
  while(true){
    const part=await reader.read();buffer+=decoder.decode(part.value||new Uint8Array(),{stream:!part.done});
    let boundary;
    while((boundary=buffer.indexOf('\n\n'))!==-1){dispatch(buffer.slice(0,boundary));buffer=buffer.slice(boundary+2);}
    if(part.done)break;
  }
  if(buffer.trim())dispatch(buffer);
  if(result===null)throw new Error('Forbindelsen sluttede, før Luna blev færdig.');
  return result;
}
function ask(el,items){return new Promise(resolve=>{el.textContent='Luna vil gerne udføre:';const box=document.createElement('div');box.className='approve';const boxes=items.map(it=>{const l=document.createElement('label'),cb=document.createElement('input'),s=document.createElement('span');cb.type='checkbox';cb.checked=true;s.textContent=it.title||it.name;l.append(cb,s);box.append(l);return cb;});const bar=document.createElement('div');bar.className='bar';const stop=document.createElement('button');stop.type='button';stop.textContent='Afvist';const go=document.createElement('button');go.type='button';go.textContent='Kør valgte';const done=v=>{box.remove();bar.remove();askResolve=null;resolve(v);};stop.onclick=()=>done(items.map(()=>false));go.onclick=()=>done(boxes.map(b=>b.checked));bar.append(stop,go);el.append(box,bar);askResolve=done;});}
$('form').onsubmit=async e=>{
  e.preventDefault();if(busy||readingFiles)return;
  const prompt=$('prompt').value.trim();if(!prompt&&!attachments.length)return;
  const text=[prompt,...attachments.filter(f=>f.text!==undefined).map(f=>'Vedhæftet fil: '+f.name+'\n'+f.text)].filter(Boolean).join('\n\n');
  const pictures=attachments.filter(f=>f.image).map(f=>f.image);if(!token){message('error','Tryk Tjek forbindelse først.');return;}
  const user={role:'user',content:text};if(pictures.length)user.images=pictures.map(image=>image.split(',')[1]);
  const solo=$('solo').checked;const next=[...history,user];let send=next;
  if(solo){if(text.length>40000){message('error','Din besked er for lang. Højst 40.000 tegn.');return;}send=[...history.slice(-2).map(m=>({role:m.role,content:m.content})),user];while(send.length>1&&send.reduce((n,m)=>n+m.content.length,0)>40000)send.shift();}
  else{while(next.length>1&&(next.length>40||next.reduce((n,m)=>n+m.content.length,0)>45000))next.shift();if(next.reduce((n,m)=>n+(m.images||[]).length,0)>2){message('error','Højst to billeder pr. samtale. Start en ny samtale.');return;}}
  busy=true;stopped=false;ctl=new AbortController();setBusy(true);FLAGS.forEach(id=>$(id).disabled=true);message('user',text,pictures);
  const pending=message('assistant','');const startedAt=Date.now();
  const onLive=event=>{
    if(event.type==='status')updateLiveStatus(pending,event.text,startedAt);
    else if(event.type==='delta'){pending.content.textContent+=event.text;pending.el.scrollIntoView({block:'end'});}
    else if(event.type==='clear')pending.content.textContent='';
  };
  updateLiveStatus(pending,'Venter på lokal model…',startedAt);
  const liveTimer=setInterval(()=>{if(pending.status.dataset.label)updateLiveStatus(pending,pending.status.dataset.label,startedAt);},1000);
  const flags={think:$('think').checked,agents:$('agents').checked,skills:$('skills').checked,tools:$('tools').checked,edit:$('edit').checked,web:$('web').checked,full:$('full').checked,confirm:$('confirm').checked,solo:$('solo').checked,memory:$('memory').checked,folders:$('folders').checked,github:$('github').checked,mcp:$('mcp').checked};
  try{
    let data=await streamApi('/api/chat/stream',{messages:send,...flags},onLive);
    while(data.pending){
      const picks=await ask(pending.content,data.pending);if(picks===null)throw Object.assign(new Error('Afbrudt.'),{stopped:true});
      pending.content.textContent='Arbejder videre…';data=await streamApi('/api/confirm/stream',{id:data.pending_id,approve:picks},onLive);
    }
    pending.content.textContent=data.answer;updateLiveStatus(pending,'',startedAt);
    if(data.thinking)detail(pending.el,'Vis modellens tænkning',data.thinking);
    if(data.tools?.length)detail(pending.el,'Anvendte værktøjer',data.tools.map(t=>t.name+'\n'+t.result).join('\n\n'));
    history=[...next,{role:'assistant',content:data.answer}];$('prompt').value='';clearImage();
  }catch(err){
    if(stopped||err.name==='AbortError'){pending.content.textContent='Afbrudt. Din besked står stadig i feltet — tryk Send for at prøve igen.';updateLiveStatus(pending,'',startedAt);}
    else{pending.el.remove();message('error',err.message+' Din besked er bevaret, så du kan prøve igen.');}
  }finally{clearInterval(liveTimer);ctl=null;busy=false;setBusy(false);FLAGS.forEach(id=>$(id).disabled=false);$('prompt').focus();}
};
$('export').onclick=()=>{const text='# Luna Local\n\n'+history.map(m=>'## '+(m.role==='user'?'Dig':'Luna')+'\n\n'+m.content+(m.images?'\n\n[Billede vedhæftet; ikke med i eksport]':'')).join('\n\n');const url=URL.createObjectURL(new Blob([text],{type:'text/markdown;charset=utf-8'}));const a=document.createElement('a');a.href=url;a.download='Luna-samtale.md';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);};
function hint(id,text,kind){const el=$(id);if(!el)return;el.textContent=text||'';el.className='muted'+(kind===true?' hint-ok':kind===false?' hint-bad':'');}
async function getjson(path,extra){const r=await fetch(path,{headers:Object.assign({'X-Luna-Token':token},extra||{})});const d=await r.json().catch(()=>({}));if(!r.ok)throw new Error(d.error||'Serverfejl');return d;}
function listRow(title,sub,actions){const li=document.createElement('li'),span=document.createElement('span');span.className='txt';const b=document.createElement('b');b.textContent=title;span.append(b);if(sub){span.append(document.createElement('br'));const s=document.createElement('span');s.textContent=sub;span.append(s);}const acts=document.createElement('span');acts.className='acts';actions.forEach(a=>{const btn=document.createElement('button');btn.type='button';btn.textContent=a.label;btn.disabled=!!a.disabled;btn.onclick=a.on;acts.append(btn);});li.append(span,acts);return li;}
function emptyRow(ul,text){const li=document.createElement('li');li.className='empty';li.textContent=text;ul.append(li);}
function payload(){return {github:{token:$('ghToken').value.trim(),user:$('ghUser').value.trim()},mcp:settings.mcp,folders:settings.folders,model:$('setModel').value.trim()};}
async function saveSettings(silent){
  // Gem også de viste flueben, før status opdaterer forbindelserne.
  for(const id of CHAT_PREFERENCE_IDS){
    if(!$(id).closest('.conn')?.hidden)rememberChatPreference(id);
  }
  const saved=await api('/api/settings',payload());settings={github:saved.github,mcp:saved.mcp,folders:saved.folders,model:saved.model};if(!silent){await status();renderSettings();hint('saveHint','Gemt.',true);}return saved;}
function renderMcp(){const ul=$('mcpList');ul.replaceChildren();if(!settings.mcp.length){emptyRow(ul,'(ingen MCP-servere endnu)');return;}settings.mcp.forEach((m,i)=>{ul.append(listRow(m.name,(m.url||m.command)+(m.env?' · '+m.env:''),[{label:'Test',on:e=>testMcp(m.name,e.target)},{label:'Fjern',on:()=>{settings.mcp.splice(i,1);renderMcp();hint('mcpHint','Fjernet — husk at gemme.',true);}}]));});}
function renderFolders(){const ul=$('folderList');ul.replaceChildren();if(!settings.folders.length){emptyRow(ul,'(ingen godkendte mapper endnu)');return;}settings.folders.forEach((f,i)=>{ul.append(listRow(f,'',[{label:'Fjern',on:()=>{settings.folders.splice(i,1);renderFolders();hint('folderHint','Fjernet — husk at gemme.',true);}}]));});}
function renderSettings(){$('setModel').value=settings.model||'';$('ghToken').value=settings.github.token||'';$('ghUser').value=settings.github.user||'';hint('ghHint',settings.github.connected?'Token gemt. Test forbindelsen.':'Ingen token endnu.');renderMcp();renderFolders();hint('saveHint','');}
async function openSettings(){if(!token){message('error','Tryk Tjek forbindelse først.');return;}try{settings=await getjson('/api/settings');}catch(e){message('error',e.message);return;}renderSettings();$('settings').hidden=false;$('setModel').focus({preventScroll:true});document.querySelector('#settings .pane').scrollTop=0;}
async function testMcp(name,btn){btn.disabled=true;hint('mcpHint','Tester '+name+' …');try{await saveSettings(true);const r=await api('/api/settings/test',{kind:'mcp',name});hint('mcpHint',r.message,true);await status();}catch(e){hint('mcpHint',e.message,false);}finally{btn.disabled=false;}}
async function loadModels(){hint('modelsHint','Henter modeller …');try{const d=await getjson('/api/models');renderModels(d);pullUI(d.pull||{});hint('modelsHint',(d.installed||[]).length+' model(er) installeret.',true);}catch(e){hint('modelsHint',e.message,false);}}
function renderModels(d){const ul=$('modelList');ul.replaceChildren();const list=d.installed||[];if(!list.length){emptyRow(ul,'(Ollama har ingen modeller installeret)');return;}list.forEach(m=>{const active=m.name===d.active;ul.append(listRow(m.name,m.size?(m.size/1e9).toFixed(1)+' GB':'',[{label:active?'Aktiv':'Brug',disabled:active,on:()=>{$('setModel').value=m.name;hint('saveHint','Model valgt — husk at gemme.',true);}}]));});}
function pullUI(p){$('pullBox').hidden=!p.running;$('pullStatus').textContent=p.running?('Henter '+p.name+' … '+(p.total?(p.percent+' % · '+(p.done/1e9).toFixed(1)+'/'+(p.total/1e9).toFixed(1)+' GB'):'')):'';}
async function pollPull(){try{const d=await getjson('/api/models');pullUI(d.pull||{});if(!d.pull.running){clearInterval(pullTimer);pullTimer=null;renderModels(d);hint('modelsHint',d.pull.error?('Fejl ved hentning: '+d.pull.error):('Hentet: '+d.pull.name),!d.pull.error);}}catch(e){clearInterval(pullTimer);pullTimer=null;hint('modelsHint',e.message,false);}}
async function startPull(name){try{await api('/api/models/pull',{name});hint('modelsHint','Starter hentning af '+name+' …',true);if(pullTimer)clearInterval(pullTimer);pullTimer=setInterval(pollPull,2000);pollPull();}catch(e){hint('modelsHint',e.message,false);}}
$('openSettings').onclick=openSettings;
$('settingsClose').onclick=()=>{$('settings').hidden=true;};
$('settings').onclick=e=>{if(e.target===$('settings'))$('settings').hidden=true;};
$('settingsSave').onclick=()=>saveSettings(false).catch(e=>hint('saveHint',e.message,false));
$('modelsReload').onclick=loadModels;
$('ghTest').onclick=async()=>{const btn=$('ghTest');btn.disabled=true;hint('ghHint','Tester …');try{await saveSettings(true);const r=await api('/api/settings/test',{kind:'github'});settings=await getjson('/api/settings');$('ghUser').value=settings.github.user||'';hint('ghHint',r.message,true);}catch(e){hint('ghHint',e.message,false);}finally{btn.disabled=false;await status();}};
$('mcpAdd').onclick=()=>{const name=$('mcpName').value.trim(),url=$('mcpUrl').value.trim(),command=$('mcpCmd').value.trim(),tk=$('mcpToken').value.trim(),env=$('mcpEnv').value.trim();if(!name)return hint('mcpHint','Serveren mangler et navn.',false);if(!url===!command)return hint('mcpHint','Udfyld enten adresse eller kommando — ikke begge.',false);if(settings.mcp.some(m=>m.name.toLowerCase()===name.toLowerCase()))return hint('mcpHint','Der findes allerede en server med det navn.',false);settings.mcp.push({name,url,command,token:tk,env});$('mcpName').value='';$('mcpUrl').value='';$('mcpCmd').value='';$('mcpToken').value='';$('mcpEnv').value='';renderMcp();hint('mcpHint','Tilføjet — husk at gemme.',true);};
$('folderAdd').onclick=async()=>{const path=$('folderPath').value.trim();if(!path)return hint('folderHint','Skriv den fulde sti først.',false);hint('folderHint','Tjekker …');try{const r=await api('/api/settings/test',{kind:'folder',path});if(!settings.folders.includes(r.path))settings.folders.push(r.path);$('folderPath').value='';renderFolders();hint('folderHint','Tilføjet — husk at gemme.',true);}catch(e){hint('folderHint',e.message,false);}};
$('libraryGo').onclick=async()=>{const q=$('libraryQ').value.trim();if(!q)return hint('modelsHint','Skriv et navn at søge efter, fx qwen3.5.',false);hint('modelsHint','Søger i biblioteket …');try{const d=await getjson('/api/models',{'X-Luna-Query':q});const ul=$('libraryList');ul.replaceChildren();const names=d.library||[];if(!names.length){emptyRow(ul,'(ingen fundet for "'+q+'")');return;}names.forEach(name=>{ul.append(listRow(name,'',[{label:'Brug',on:()=>{$('setModel').value=name;hint('saveHint','Model valgt — husk at gemme.',true);}},{label:'Hent',on:()=>startPull(name)}]));});hint('modelsHint',names.length+' fundet.',true);}catch(e){hint('modelsHint',e.message,false);}};
$('pullStop').onclick=async()=>{try{await api('/api/models/pull/stop',{});pollPull();}catch(e){hint('modelsHint',e.message,false);}};
document.addEventListener('keydown',e=>{
  if(e.key==='Escape'){
    if(!$('rootMenu').hidden)$('rootMenu').hidden=true;       // 📁-menuen først
    else if(!$('settings').hidden)$('settings').hidden=true;
    else if(!$('files').hidden)closeFiles();
    return;
  }
  if((e.ctrlKey||e.metaKey)&&!e.altKey&&!e.shiftKey&&e.key.toLowerCase()==='o'){e.preventDefault();openFiles('fil');}   // Åbn fil
  if((e.ctrlKey||e.metaKey)&&!e.altKey&&e.shiftKey&&e.key.toLowerCase()==='b'){e.preventDefault();openFiles('web');}   // Browser
});
status();

/* Stop: bryder det kørende modelkald på serveren og giver inputtet tilbage. */
function setBusy(on){$('stop').hidden=!on;$('send').hidden=on;}
function stopRun(){if(!busy||stopped)return;stopped=true;if(askResolve)askResolve(null);try{ctl&&ctl.abort();}catch(e){}ctl=null;fetch('/api/stop',{method:'POST',headers:{'Content-Type':'application/json','X-Luna-Token':token},body:'{}'}).catch(()=>{});}
$('stop').onclick=stopRun;

/* Mikrofon: tale bliver til tekst i beskedfeltet (da-DK). */
const MIC_HINT=$('hint').textContent,SR=window.SpeechRecognition||window.webkitSpeechRecognition;
if(!SR)$('mic').hidden=true;   // browseren kan slet ikke (Firefox) — knappen giver ingen mening
function micHint(t){$('hint').textContent=t;}
function micOff(msg){listening=false;$('mic').classList.remove('on');micHint(MIC_HINT);if(msg)message('error',msg);}
function appendSpoken(t){const ta=$('prompt'),s=(t||'').trim();if(!s)return;ta.value=(ta.value&&!/\s$/.test(ta.value)?ta.value+' ':'')+s;}
function stopRec(){if(!listening)return;micOff();try{rec&&rec.stop();}catch(e){}}
function startRec(){
  if(!SR){const ua=navigator.userAgent;
    const who=/Firefox/i.test(ua)?'Firefox har ingen talegenkendelse':/Edg\//i.test(ua)?'Denne Edge understøtter ikke talegenkendelse':/Chrome|Chromium|OPR/i.test(ua)?'Denne Chrome understøtter ikke talegenkendelse':'Din browser understøtter ikke talegenkendelse';
    message('error',who+'. Åbn Luna i Chrome eller Edge, så kan du tale beskeden ind — ellers skriver du den bare.');return;}
  try{rec=new SR();}catch(e){message('error','Talegenkendelsen kunne ikke startes.');return;}
  rec.lang='da-DK';rec.continuous=true;rec.interimResults=true;rec.maxAlternatives=1;
  rec.onresult=e=>{let interim='';for(let i=e.resultIndex;i<e.results.length;i++){const r=e.results[i];if(r.isFinal)appendSpoken(r[0].transcript);else interim+=r[0].transcript;}micHint(interim?'Hører efter: '+interim:'Lytter … sig din besked.');};
  rec.onerror=e=>{if(!listening)return;const f=e.error;   // kun én fejlbesked, også hvis browseren gentager den
    if(f==='not-allowed'||f==='service-not-allowed')micOff('Mikrofonen må ikke bruges. Godkend den i browseren (mikrofon-ikonet ved adresselinjen) og prøv igen.');
    else if(f==='network')micOff('Talegenkendelsen kan ikke nå nettet. Tjek forbindelsen, eller skriv i stedet.');
    else if(f==='audio-capture')micOff('Ingen mikrofon blev fundet.');
    else if(f==='language-not-supported')micOff('Din browser understøtter ikke dansk talegenkendelse.');
    else if(f==='aborted')micOff();};
  rec.onend=()=>{if(listening){try{rec.start();}catch(e){micOff();}}};
  listening=true;$('mic').classList.add('on');micHint('Lytter … sig din besked.');
  try{rec.start();}catch(e){micOff('Talegenkendelsen kunne ikke startes.');}
}
$('mic').onclick=()=>{if(listening)stopRec();else startRec();};

/* Filer: filtræde og editor i samme rude. Læsning virker altid for workspace og
   godkendte mapper; Gem kræver fluebenet Rediger filer (eller Fuld adgang). */
const fileQ=()=>`&full=${$('full').checked?1:0}&edit=${$('edit').checked?1:0}`;
const fileGet=path=>getjson('/api/files?path='+encodeURIComponent(path||'')+fileQ());
function dirNode(name,path){
  const det=document.createElement('details');det.dataset.path=path;
  const sum=document.createElement('summary');sum.textContent='📁 '+name;det.append(sum);
  const ul=document.createElement('ul');det.append(ul);
  det.addEventListener('toggle',()=>{if(det.open&&!ul.dataset.load)fillDir(ul,path);});
  return det;
}
async function fillDir(ul,path){
  ul.dataset.load='1';
  try{
    const d=await fileGet(path);ul.replaceChildren();
    d.dirs.forEach(n=>{const li=document.createElement('li');li.append(dirNode(n,path?path+'/'+n:n));ul.append(li);});
    d.files.forEach(f=>{const li=document.createElement('li');const b=document.createElement('button');b.type='button';b.className='ffile';b.textContent='📄 '+f.name;b.title=path?path+'/'+f.name:f.name;b.onclick=()=>showFile(b.title,b);li.append(b);ul.append(li);});
    if(!d.dirs.length&&!d.files.length){const li=document.createElement('li');li.className='empty';li.textContent='(tom)';ul.append(li);}
  }catch(e){hint('fileHint',e.message,false);}
}
async function renderRoots(){
  const d=await fileGet('');
  ROOTS=d.roots||[];                                          // husk rødderne til 📁-menuen
  const ul=document.createElement('ul');ul.className='ftree';
  (d.roots||[]).forEach(r=>{const li=document.createElement('li');li.append(dirNode(r.name,r.path));ul.append(li);});
  $('fileTree').replaceChildren(ul);
  const first=ul.querySelector('details');
  if(first)first.open=true;                    // workspace folder sig ud med det samme
}
async function showFile(path,btn){
  let mål=faner.find(f=>f.type==='fil'&&f.sti===path);        // filen er allerede åben et sted → skift dertil
  if(!mål){
    mål=(aktiv()&&aktiv().type==='fil')?aktiv():faner.find(f=>f.type==='fil');
    if(!mål)mål=nyFane('fil');                                // ellers brug/nyd en fil-fane
    mål.sti=path;
  }
  if(mål.id!==aktivFane)skiftFane(mål.id);
  hint('fileHint','Åbner '+path+' …');
  try{
    const d=await getjson('/api/file?path='+encodeURIComponent(path)+fileQ());
    mål.sti=path;mål.tekst=d.content;
    mål.hint=path+' · '+d.content.length+' tegn';
    if(mål.id===aktivFane){                                  // vis den hvis den er aktiv
      $('fileText').value=d.content;$('filePath').value=path;
      document.querySelectorAll('#fileTree .ffile').forEach(b=>b.classList.remove('on'));
      if(btn)btn.classList.add('on');
      hint('fileHint',mål.hint,true);
    }
    tegnFaner();
  }catch(e){mål.hint=e.message;if(mål.id===aktivFane)hint('fileHint',e.message,false);}
}
let faner=[],aktivFane=0,naesteId=1,ROOTS=[];                 // faner: {type:'fil'|'web', ...} — ROOTS: træets rødder
const aktiv=()=>faner.find(f=>f.id===aktivFane);
function faneNavn(f){
  if(f.type==='web'){
    if(!f.url&&!f.src)return 'ny fane';
    if(f.søg)return f.søg.length>22?f.søg.slice(0,21)+'…':f.søg;    // søgeordet er fane-navnet
    try{return new URL(f.src||f.url).hostname||'ny fane'}catch(e){return 'ny fane'}
  }
  return f.sti?f.sti.split(/[\\/]/).pop():'ny fil';
}
function tegnFaner(){                                        // byg fane-rækken (+ er altid sidst og synlig)
  const liste=$('faneListe');
  [...liste.querySelectorAll('.tab:not(.tabny)')].forEach(t=>t.remove());
  faner.forEach(f=>{
    const b=document.createElement('button');b.type='button';
    b.className='tab'+(f.id===aktivFane?' on':'');
    b.title=(f.type==='web'?'Browser: ':'Fil: ')+(f.sti||f.url||'ny');
    const t=document.createElement('span');t.className='tabnavn';
    t.textContent=(f.type==='web'?'🌐 ':'📄 ')+faneNavn(f);
    const x=document.createElement('i');x.className='tabx';x.textContent='✕';x.title='Luk fane';
    x.onclick=e=>{e.stopPropagation();lukFane(f.id);};
    b.append(t,x);b.onclick=()=>skiftFane(f.id);
    liste.append(b);
  });
}
function gemAktiv(){                                         // husk den åbne tekst før skift
  const f=aktiv();if(f&&f.type==='fil')f.tekst=$('fileText').value;
}
function skiftFane(id){if(id===aktivFane)return;gemAktiv();aktivFane=id;visFane();}
function visFane(){
  const f=aktiv();if(!f)return;
  tegnFaner();
  const web=f.type==='web';
  $('openFiles').classList.toggle('on',!web);                // headerens ikoner lyser efter typen
  $('openWeb').classList.toggle('on',web);
  $('fileView').hidden=web;$('fileNav').hidden=web;
  $('webView').hidden=!web;$('webNav').hidden=!web;
  if(web){
    $('webUrl').value=f.vis||f.url||'';
    const blok=!!f.blokeret;                                       // spærret side → boks i stedet for død ramme
    $('webBlock').hidden=!blok;
    $('webFrames').hidden=blok;
    if(blok)$('webBlockTekst').textContent=f.blokeret;
    document.querySelectorAll('#webFrames .webframe').forEach(d=>d.hidden=d.dataset.id!=f.id);
  }else{
    $('filePath').value=f.sti||'';
    $('fileText').value=f.tekst||'';
    hint('fileHint',f.hint||'');
    document.querySelectorAll('#fileTree .ffile').forEach(b=>b.classList.toggle('on',!!f.sti&&b.title===f.sti));
    if(!$('fileTree').children.length)                       // træet hentes første gang det ses
      renderRoots().catch(e=>hint('fileHint',e.message,false));
  }
}
function nyFane(type){
  const f=Object.assign({id:naesteId++},type==='web'
    ?{type:'web',url:'',src:''}:{type:'fil',sti:'',tekst:'',hint:''});
  faner.push(f);
  if(type==='web')webRame(f);                                // en skjult iframe pr. browser-fane
  aktivFane=f.id;visFane();return f;
}
function webRame(f){
  const d=document.createElement('div');d.className='webframe';d.dataset.id=f.id;d.hidden=true;
  const ifr=document.createElement('iframe');ifr.title='Browser';
  ifr.setAttribute('sandbox','allow-scripts allow-same-origin allow-forms allow-popups');
  if(f.src)ifr.src=f.src;                                    // kun http/https er nået hertil
  d.append(ifr);$('webFrames').append(d);return d;
}
function lukFane(id){
  const i=faner.findIndex(f=>f.id===id);if(i<0)return;
  const f=faner[i];faner.splice(i,1);
  if(f.type==='web')$('webFrames').querySelector('[data-id="'+id+'"]')?.remove();
  if(!faner.length){tegnFaner();return closeFiles();}         // sidste fane lukker hele panelet
  if(aktivFane===id)aktivFane=faner[Math.max(0,i-1)].id;
  visFane();
}
$('faneNy').onclick=()=>nyFane((aktiv()||{type:'fil'}).type); // + laver samme type som den aktive
$('webFaneNy').onclick=()=>{                                  // 🌐 Browser: altid én klik væk
  const mål=faner.find(f=>f.type==='web');
  if(mål)skiftFane(mål.id);else nyFane('web');
};
async function gemMapper(folders){                           // gem kun mapperne — resten hentes frisk
  const s=await getjson('/api/settings');
  s.folders=folders;
  const gemt=await api('/api/settings',s);
  return gemt.folders;
}
function tegnMappeMenu(folders,fejl){                         // byg indholdet i 📁-menuen
  const m=$('rootMenu');m.replaceChildren();
  const ny=document.createElement('button');ny.type='button';ny.className='rmitem add';
  ny.textContent='＋ Tilføj mappe …';ny.onclick=tilføjMappe;m.append(ny);
  const hr1=document.createElement('hr');hr1.className='rmhr';m.append(hr1);
  const faste=ROOTS.filter(r=>!folders.includes(r.path));
  if(faste.length){
    const lab=document.createElement('p');lab.className='rmlab';lab.textContent='Fast i træet:';
    m.append(lab);
    faste.forEach(r=>{
      const rad=document.createElement('div');rad.className='rmrow';
      const s=document.createElement('span');s.textContent='📁 '+r.name;s.title=r.path||r.name;
      rad.append(s);m.append(rad);
    });
  }
  const hr2=document.createElement('hr');hr2.className='rmhr';m.append(hr2);
  if(folders.length){
    const lab=document.createElement('p');lab.className='rmlab';lab.textContent='Dine mapper:';
    m.append(lab);
    folders.forEach((f,i)=>{
      const rad=document.createElement('div');rad.className='rmrow';
      const s=document.createElement('span');s.textContent='📁 '+f;s.title=f;
      const x=document.createElement('button');x.type='button';x.className='rmx';x.textContent='✕';
      x.title='Fjern mappen fra træet';
      x.onclick=()=>fjernMappe(folders,i);
      rad.append(s,x);m.append(rad);
    });
  }else{
    const t=document.createElement('p');t.className='rmempty';
    t.textContent='Ingen ekstra mapper endnu — tilføj én, så bliver den en ny rod.';
    m.append(t);
  }
  if(fejl){const e=document.createElement('p');e.className='rmfejl';e.textContent=fejl;m.append(e);}
}
async function tilføjMappe(){
  const sti=prompt('Fuld sti til mappen der skal være en ny rod i træet (fx D:\\projekter):','');
  if(!sti||!sti.trim())return;
  try{
    const r=await api('/api/settings/test',{kind:'folder',path:sti.trim()});   // validerer + normaliserer
    const s=await getjson('/api/settings');
    const folders=s.folders.includes(r.path)?s.folders:[...s.folders,r.path];
    const gemt=await gemMapper(folders);
    await renderRoots();                                      // træet + ROOTS opdateres først
    tegnMappeMenu(gemt);
    hint('fileHint','Tilføjet som rod: '+r.path,true);
  }catch(e){$('rootMenu').hidden=false;tegnMappeMenu([],'Kan ikke tilføje: '+e.message);}
}
async function fjernMappe(folders,i){
  try{
    const bort=folders[i];
    const gemt=await gemMapper(folders.filter((_,j)=>j!==i));
    await renderRoots();
    tegnMappeMenu(gemt);
    hint('fileHint','Fjernet fra træet: '+bort,true);
  }catch(e){tegnMappeMenu(folders,'Kan ikke fjerne: '+e.message);}
}
$('mappeMenu').onclick=async e=>{                             // 📁: åbn/luk menuen
  e.stopPropagation();
  const m=$('rootMenu');
  if(!m.hidden){m.hidden=true;return;}
  try{
    const s=await getjson('/api/settings');
    tegnMappeMenu(s.folders);
  }catch(err){tegnMappeMenu([],'Kan ikke hente indstillinger: '+err.message);}
  m.hidden=false;
};
document.addEventListener('click',e=>{                        // klik udenfor lukker 📁-menuen
  if(!$('rootMenu').hidden&&!e.target.closest('.roedder'))$('rootMenu').hidden=true;
});
const SOEG='https://www.bing.com/search?q=';                  // Bing må vises i en ramme — Google gør ikke
function erAdresse(s){                                         // er det en adresse eller en søgning?
  if(/^https?:\/\//i.test(s))return true;
  if(/\s/.test(s))return false;                                // mellemrum = en søgning
  return /^(localhost|127\.0\.0\.1)(:\d+)?([\/?#].*)?$/i.test(s)
      ||/^[\w-]+(\.[\w-]+)+(:\d+)?([\/?#].*)?$/.test(s);       // domæne.tld med evt. sti
}
async function openWeb(tekst){                                       // åbn adresse eller søg — i den aktive browser-fane
  const f=aktiv();if(!f||f.type!=='web')return;
  const raw=(tekst||'').trim();if(!raw)return;
  const søg=!erAdresse(raw);
  const u=søg?SOEG+encodeURIComponent(raw)                           // søgning → Bing
        :/^https?:\/\//i.test(raw)?raw:'https://'+raw;               // kun http/https slipper igennem
  f.url=u;f.src=u;f.søg=søg?raw:'';f.vis=raw;
  f.vers=(f.vers||0)+1;                                              // en nyere adresse vinder over en langsom tjekning
  const vers=f.vers;
  f.blokeret='Tjekker om siden må vises herinde …';
  $('webUrl').value=raw;
  tegnFaner();visFane();                                             // vis tjekket med det samme
  let svar=null;
  try{
    const kontrol=api('/api/webcheck',{url:u});
    const ventet=await Promise.race([
      kontrol.then(x=>({svar:x})),
      new Promise(færdig=>setTimeout(()=>færdig({ventet:true}),4500))   // tidsgrænse: ikke hæng på et langsomt tjek
    ]);
    if(ventet.ventet){
      if(f.vers!==vers)return;
      f.vers=vers+1;                                                    // denne runde er slut — rammen prøves
      f.blokeret=null;
      const gammel=$('webFrames').querySelector('[data-id="'+f.id+'"] iframe');
      if(gammel)gammel.src=u;
      visFane();return;
    }
    svar=ventet.svar;
  }catch(e){svar=null;}                                                 // ingen forbindelse → bare prøv
  if(f.vers!==vers)return;                                           // der blev skrevet noget nyt imens
  if(svar&&svar.tilladt===false){
    if(svar.arsag==='spærret'){
      const vindue=window.open(u,'_blank');                          // Firefox tager over
      if(vindue)vindue.opener=null;                                  // samme isolation som noopener
      f.blokeret=vindue
        ? 'Siden er åbnet i din browser i stedet — den nægter at blive vist herinde.'
        : (svar.besked||'Siden vil ikke vises herinde.');            // browseren blokerede → boksen hjælper
    }else{
      f.blokeret=svar.besked||'Adressen blev ikke fundet.';          // findes ikke → Firefox kan heller ikke
    }
    visFane();return;
  }
  f.blokeret=null;
  const ifr=$('webFrames').querySelector('[data-id="'+f.id+'"] iframe');
  if(ifr)ifr.src=u;
  visFane();                                                         // fane-navnet bliver værtsnavnet eller søgeordet
}
$('webBlockBing').onclick=()=>{                                     // udvej nr. 1: klar til en søgning
  const f=aktiv();if(f&&f.type==='web')f.blokeret=null;
  visFane();
  $('webUrl').value='';$('webUrl').focus();                        // skriv søgeordet — Enter søger på Bing
};
$('webBlockEkstern').onclick=()=>{                                    // udvej nr. 2: rigtig fane i din browser
  const f=aktiv();if(f&&f.type==='web'&&f.url)window.open(f.url,'_blank','noopener');
};
$('webGo').onclick=()=>openWeb($('webUrl').value);
$('webUrl').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();openWeb($('webUrl').value);}};
function closeFiles(){
  gemAktiv();$('files').hidden=true;
  $('openFiles').classList.remove('on');$('openWeb').classList.remove('on');
}
async function openFiles(type){
  if(!token)await status();                                  // hurtigt klik før status svarede
  if(!token){message('error','Tryk Tjek forbindelse først.');return;}
  const mål=type||'fil';                                     // panel-ikonet = fil-fane, 🌐 = browser
  if(!$('files').hidden){
    const nu=aktiv();
    if(nu&&nu.type===mål)return closeFiles();                // samme knap/genvej på samme type lukker
  }
  $('files').hidden=false;
  if(!faner.length){                                         // første åbning — frisk træ
    nyFane(mål);
    if(mål==='fil'){
      $('fileTree').replaceChildren();
      try{await renderRoots();}catch(e){hint('fileHint',e.message,false);}
    }
    return;
  }
  if(aktiv()&&aktiv().type!==mål){                           // skift til fane af den rette type
    const f=faner.find(x=>x.type===mål);
    if(f)skiftFane(f.id);else nyFane(mål);
  }else visFane();
}
$('openFiles').onclick=()=>openFiles();                      // ikonknappen: fil-fane
$('openWeb').onclick=()=>openFiles('web');                   // headerens 🌐: browser-fane
$('filesClose').onclick=closeFiles;
$('fileText').oninput=()=>{const f=aktiv();if(f&&f.type==='fil')f.tekst=$('fileText').value;};
$('fileGo').onclick=()=>{const p=$('filePath').value.trim();if(p)showFile(p);};
$('filePath').onkeydown=e=>{if(e.key==='Enter'){e.preventDefault();$('fileGo').click();}};
$('fileSave').onclick=async()=>{
  const f=aktiv();if(!f||f.type!=='fil')return;
  if(!f.sti)return hint('fileHint','Vælg først en fil.',false);
  if(!$('edit').checked&&!$('full').checked)return hint('fileHint','Slå Rediger filer til i Indstillinger, så du må skrive.',false);
  hint('fileHint','Gemmer …');
  try{
    const r=await api('/api/file',{path:f.sti,content:$('fileText').value,edit:$('edit').checked,full:$('full').checked});
    f.hint=(r.message||'Gemt.');
    hint('fileHint',f.hint,true);
    if(!$('fileTree').querySelector('.ffile.on'))await renderRoots();   // ny fil — vis den i træet
    tegnFaner();
  }catch(e){f.hint=e.message;hint('fileHint',e.message,false);}
};
$('fileNew').onclick=()=>{
  let f=aktiv();if(!f||f.type!=='fil')f=nyFane('fil');        // fra browser-fane → ny fil-fane
  const p=prompt('Navn på den nye fil (sti i workspace, fx notat.md):','notat.md');
  if(!p)return;
  f.sti=p;f.tekst='';f.hint='Skriv indholdet og tryk Gem.';
  $('filePath').value=p;$('fileText').value='';
  document.querySelectorAll('#fileTree .ffile').forEach(b=>b.classList.remove('on'));
  hint('fileHint',f.hint,true);$('fileText').focus();tegnFaner();
};
