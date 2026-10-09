/* ========= Tiện ích ========= */
const $=s=>document.querySelector(s);
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const half=s=>s<=2?'S':'C';
const fmtD=d=>{const p=d.split('-');return p[2]+'/'+p[1]+'/'+p[0]};
const wd=d=>{const p=d.split('-').map(Number);return WD[new Date(p[0],p[1]-1,p[2]).getDay()]};
const lec=id=>S.lecs.find(l=>String(l.id)===String(id));
const exm=id=>S.exams.find(e=>e.id===id);
const cmpEx=(a,b)=>a.date.localeCompare(b.date)||rangeFor(a)[0]-rangeFor(b)[0]||rangeFor(a)[1]-rangeFor(b)[1]||String(a.room).localeCompare(String(b.room));
const depts=()=>[...new Set(S.lecs.map(l=>l.dept).concat(S.exams.map(e=>e.dept)).filter(Boolean))].sort();
function toast(m){const t=$('#toast');t.textContent=m;t.style.display='block';clearTimeout(toast.h);toast.h=setTimeout(()=>t.style.display='none',3200)}
function openModal(o){
  $('#modal').innerHTML='<div class="ov" data-act="ovclose"><div class="md '+(o.wide?'wide':'')+'" role="dialog" aria-modal="true" aria-label="'+esc(o.title)+'"><header><h3>'+esc(o.title)+'</h3><button class="x" data-act="close" aria-label="Đóng">'+IC.x+'</button></header><div class="bd">'+o.body+'</div>'+(o.foot?'<footer>'+o.foot+'</footer>':'')+'</div></div>';
  const f=$('#modal input[type=text],#modal input[type=number]');if(f)f.focus();
}
const closeModal=()=>{$('#modal').innerHTML='';pick=null};
function logoHTML(px){
  const inner=S.logo?'<img src="'+S.logo+'" alt="Logo Trường Đại học Công Thương" style="width:'+px+'px;height:'+px+'px">':'<div class="logo-ph" style="width:'+px+'px;height:'+px+'px;font-size:'+Math.round(px/4)+'px">HUIT</div>';
  return '<button class="logo-btn" data-act="logo" title="Bấm để thay bằng logo của trường" aria-label="Thay logo trường"><div class="logo-wrap">'+inner+'</div></button>';
}
function readTable(f){return new Promise((res,rej)=>{
  const r=new FileReader();
  r.onerror=()=>rej(new Error('Không đọc được file.'));
  if(/\.xlsx?$/i.test(f.name)){
    if(typeof XLSX==='undefined'){rej(new Error('Chưa tải được thư viện đọc Excel. Hãy lưu file dạng CSV rồi thử lại.'));return}
    r.onload=()=>{try{const wb=XLSX.read(r.result,{type:'array'});const ws=wb.Sheets[wb.SheetNames[0]];res(XLSX.utils.sheet_to_json(ws,{header:1,raw:false,dateNF:'dd/mm/yyyy',blankrows:false}))}catch(e){rej(new Error('File Excel không hợp lệ.'))}};
    r.readAsArrayBuffer(f);
  }else{
    r.onload=()=>{const t=String(r.result).replace(/^\uFEFF/,'');const lines=t.split(/\r?\n/).filter(x=>x.trim());const sep=t.indexOf('\t')>=0?'\t':(t.indexOf(';')>=0?';':',');res(lines.map(l=>l.split(sep).map(x=>x.trim().replace(/^"|"$/g,''))))};
    r.readAsText(f);
  }
})}
function validDate(y,m,d){const dt=new Date(y,m-1,d);if(dt.getFullYear()!==y||dt.getMonth()!==m-1||dt.getDate()!==d)return null;return y+'-'+String(m).padStart(2,'0')+'-'+String(d).padStart(2,'0')}
function parseDate(v){
  if(v instanceof Date && !isNaN(v.getTime())) return validDate(v.getFullYear(),v.getMonth()+1,v.getDate());
  v=String(v==null?'':v).trim();
  // ISO date/datetime from Excel or API
  let m=v.match(/^(\d{4})-(\d{1,2})-(\d{1,2})(?:$|T|\s)/);
  if(m)return validDate(+m[1],+m[2],+m[3]);
  // Vietnamese dd/mm/yyyy; allow 2-digit years and common separators.
  m=v.match(/^(\d{1,2})[\/\-.](\d{1,2})[\/\-.](\d{2,4})$/);
  if(m){
    let a=+m[1],b=+m[2],y=+m[3];if(y<100)y+=2000;
    return validDate(y,b,a)||validDate(y,a,b);
  }
  return null;
}
function plain(v){return String(v==null?'':v).normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLowerCase().replace(/đ/g,'d').replace(/[\u00a0\u200b\ufeff]/g,' ').replace(/\s+/g,' ').trim()}
function parsePeriod(v){const m=String(v||'').match(/(\d{1,2})\s*[→>-]\s*(\d{1,2})/);return m&&+m[1]<+m[2]&&+m[1]>=1&&+m[2]<=12?{start:+m[1],end:+m[2],key:+m[1]+'-'+(+m[2])}:null}
function parseExamSlot(v){const r=parsePeriod(v);if(r){const x=EXAM_SLOTS.find(s=>s[1]===r.start&&s[2]===r.end);return{start:r.start,end:r.end,label:x?x[0]:r.start+' → '+r.end}}const m=plain(v).match(/(?:ca\s*)?([1-4])(?:\D|$)/);if(!m)return null;const x=EXAM_SLOTS[[0,2,5,7][+m[1]-1]];return{start:x[1],end:x[2],label:x[0]}}
function teachName(rows,key){const r=rows.find(x=>x.name.trim().toLocaleLowerCase('vi')===key);return r?r.name:key}

