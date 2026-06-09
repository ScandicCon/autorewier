/* ---------- ready flag (used by the in-head fail-safe) ---------- */
window.__pkReady=true;

/* ---------- mobile menu ---------- */
function toggleMenu(){document.querySelector('.nav-links')?.classList.toggle('open');}

/* ---------- reveal on scroll ---------- */
const io=new IntersectionObserver((es)=>es.forEach(e=>{if(e.isIntersecting){e.target.classList.add('reveal');io.unobserve(e.target);}}),{threshold:.12});
document.querySelectorAll('[data-reveal]').forEach(el=>io.observe(el));

/* ---------- motion: count-up + gauge draw-in (in-view) ---------- */
const reduceMotion=window.matchMedia&&window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/* count-up: animates leading number in elements marked [data-countup],
   preserving any prefix/suffix text (e.g. "40К ₽", "120+"). */
function runCountUp(el){
  const raw=el.dataset.countup;
  const m=raw.match(/^(\D*)([\d\s]+)(.*)$/s);
  if(!m){el.textContent=raw;return;}
  const pre=m[1],post=m[3];
  const target=parseInt(m[2].replace(/\s/g,''),10);
  if(reduceMotion||!isFinite(target)){el.textContent=raw;return;}
  const dur=1100,t0=performance.now();
  (function tick(now){
    const p=Math.min(1,(now-t0)/dur);
    const eased=1-Math.pow(1-p,3);
    const val=Math.round(target*eased);
    el.textContent=pre+val.toLocaleString('ru')+post;
    if(p<1)requestAnimationFrame(tick);else el.textContent=raw;
  })(t0);
}

const ioCount=new IntersectionObserver((es)=>es.forEach(e=>{if(e.isIntersecting){runCountUp(e.target);ioCount.unobserve(e.target);}}),{threshold:.5});

const ioGauge=new IntersectionObserver((es)=>es.forEach(e=>{
  if(!e.isIntersecting)return;
  const ring=e.target;const final=ring.getAttribute('stroke-dashoffset');
  if(!reduceMotion){
    const len=parseFloat(ring.getAttribute('stroke-dasharray'))||339;
    ring.style.strokeDashoffset=len;               /* empty */
    ring.getBoundingClientRect();                   /* reflow */
    requestAnimationFrame(()=>{ring.style.strokeDashoffset=final;});
  }
  ioGauge.unobserve(ring);
}),{threshold:.4});

/* ====================================================
   REPORT PAGE
==================================================== */
const RISKS=[
 {id:1,title:'Сомнения в пробеге',prio:1,conf:64,high:true,cost:8000,
  desc:'Пробег 98 000 км для 2017 года ниже среднего по рынку. Износ руля и накладок педалей выглядит больше заявленного.',
  rationale:'Несоответствие пробега и визуального износа органов управления — типовой признак корректировки одометра.',
  evidence:'Текст объявления + фото салона + средний пробег по модели/году.'},
 {id:2,title:'Подвеска: стойки стабилизатора, сайлентблоки',prio:2,conf:78,high:true,cost:22000,
  desc:'К пробегу ~100 тыс на Camry обычно требуют замены стойки стабилизатора, реже — сайлентблоки рычагов.',
  rationale:'Плановый ресурс расходников подвески для этой модели и пробега подходит к концу.',
  evidence:'Типовые слабости модели + пробег. На фото оригинальные элементы без следов замены.'},
 {id:3,title:'Тормоза: диски и колодки передние',prio:2,conf:70,high:false,cost:28000,
  desc:'Вероятен скорый износ передних дисков и колодок. На фото виден буртик по краю диска.',
  rationale:'Возраст и пробег + визуальный признак выработки на фотографии колеса.',
  evidence:'Фото переднего колеса (дефект кромки диска).'},
 {id:4,title:'Запотевание передних фар',prio:3,conf:55,high:false,cost:6000,
  desc:'Косметический дефект — лёгкий конденсат в фаре. На работу света обычно не влияет.',
  rationale:'Распознан конденсат на фото; типичная мелочь для возрастных Camry.',
  evidence:'Фото передней части кузова.'},
 {id:5,title:'Лёгкая потливость заднего сальника',prio:3,conf:48,high:false,cost:0,
  desc:'Информационно: у 2.5 (2AR-FE) встречается лёгкое запотевание сальника. Часто не требует вмешательства.',
  rationale:'Известная особенность двигателя; прямых доказательств по объявлению нет.',
  evidence:'Типовые слабости двигателя 2AR-FE.'}
];
const REPAIR=[
 {cat:'Подвеска',work:'Стойки стабилизатора, диагностика рычагов',prio:2,min:8000,max:22000,parts:'Запчасти: 4 000–12 000',seller:false},
 {cat:'Тормоза',work:'Диски + колодки перед',prio:2,min:12000,max:28000,parts:'Запчасти: 7 000–18 000',seller:false},
 {cat:'ТО',work:'Масло, фильтры, свечи',prio:3,min:9000,max:16000,parts:'Запчасти: 5 000–9 000',seller:true},
 {cat:'Оптика',work:'Полировка/просушка фар',prio:3,min:2000,max:6000,parts:'Запчасти: 0–2 000',seller:false},
 {cat:'Диагностика',work:'Двигатель + АКПП на стенде',prio:1,min:3000,max:8000,parts:'Запчасти: —',seller:false}
];
const CLAIMS=[
 {q:'«Недавно меняли масло и колодки»',note:'Замена ТО — учтено в смете при включённом тумблере'},
 {q:'«Один владелец, не бит, не крашен»',note:'История ДТП и владельцев — сверить по VIN/отчёту'},
 {q:'«Вложений не требует»',note:'Противоречит плановому износу подвески и тормозов'}
];
const WEAK=[
 {t:'Расход масла на 2.5 (2AR-FE) после 100 тыс',how:'Проверить уровень по щупу, спросить долив между ТО, осмотреть свечи на масло.'},
 {t:'Помпа ГУР / рейка — стуки',how:'На тест-драйве крутить руль на месте и в движении, слушать стуки и подвывания.'},
 {t:'Запотевание фар',how:'Осмотреть фары вечером, искать конденсат внутри.'},
 {t:'Тонкое ЛКП, сколы на капоте',how:'Смотреть капот и пороги на свету под углом, замерить толщиномером.'}
];
const sc={1:'b-p1',2:'b-p2',3:'b-p3'},pn={1:'P1',2:'P2',3:'P3'};
let sellerOn=false,riskF='all';

function renderRisks(){
  const el=document.getElementById('riskList');if(!el)return;
  let arr=[...RISKS];
  const sortEl=document.getElementById('riskSort');
  if(sortEl&&sortEl.value==='cost')arr.sort((a,b)=>b.cost-a.cost);else arr.sort((a,b)=>a.prio-b.prio);
  const pass=r=>riskF==='all'||(riskF==='high'&&r.high)||(riskF==='p1'&&r.prio===1)||(riskF==='noinfo'&&r.cost>0);
  el.innerHTML=arr.map(r=>`<div class="risk ${pass(r)?'':'gone'}">
     <div class="risk-h">
       <h3>${r.title}</h3>
       <span class="badge ${sc[r.prio]}">${pn[r.prio]}</span>
       <span class="conf">${r.conf}%<span class="cbar"><i style="width:${r.conf}%"></i></span></span>
       ${r.cost>0?`<span class="cost-tag">~${r.cost.toLocaleString('ru')} ₽</span>`:`<span class="cost-tag info">инфо</span>`}
     </div>
     <p>${r.desc}</p>
     <div class="rmeta"><span><b>Почему так:</b> ${r.rationale}</span><span><b>Источник сигнала:</b> ${r.evidence}</span></div>
   </div>`).join('');
  const c=document.getElementById('riskCount');if(c)c.textContent=arr.filter(pass).length;
}
function sortRisks(){renderRisks();}
function renderRepair(){
  const b=document.getElementById('repairBody');if(!b)return;
  b.innerHTML=REPAIR.map(r=>{const dim=sellerOn&&r.seller;return `<tr style="${dim?'opacity:.4':''}">
     <td data-l="Категория"><b>${r.cat}</b></td>
     <td class="desc-cell" data-l="Работы">${r.work}<span class="ph">${r.parts}</span>${dim?'<span class="ph" style="color:var(--safe);display:inline-flex;align-items:center;gap:4px"><svg viewBox="0 0 24 24" width="13" height="13" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 12.5 9.5 18 20 6"/></svg> заявлено продавцом</span>':''}</td>
     <td data-l="Приоритет"><span class="badge ${sc[r.prio]}">${pn[r.prio]}</span></td>
     <td class="num mono" data-l="Стоимость">${r.min.toLocaleString('ru')} – ${r.max.toLocaleString('ru')}</td></tr>`;}).join('');
  const act=REPAIR.filter(r=>!(sellerOn&&r.seller));
  const min=act.reduce((s,r)=>s+r.min,0),max=act.reduce((s,r)=>s+r.max,0);
  set('tTotal',`${min.toLocaleString('ru')} – ${max.toLocaleString('ru')}`);
  set('tParts',`${Math.round(min*.6).toLocaleString('ru')} – ${Math.round(max*.6).toLocaleString('ru')}`);
  set('tLabor',`${Math.round(min*.4).toLocaleString('ru')} – ${Math.round(max*.4).toLocaleString('ru')}`);
}
function set(id,v){const e=document.getElementById(id);if(e)e.textContent=v;}
function toggleSeller(){sellerOn=!sellerOn;document.getElementById('sellerToggle')?.classList.toggle('on',sellerOn);renderRepair();}
function renderClaims(){
  const b=document.getElementById('claimsBody');if(!b)return;
  b.innerHTML=CLAIMS.map(c=>`<div class="claim"><div class="q">${c.q}<small>${c.note}</small></div><span class="badge b-p2">требует подтверждения</span></div>`).join('');
}
function renderWeak(){
  const b=document.getElementById('weakBody');if(!b)return;
  b.innerHTML=WEAK.map(w=>`<div class="acc-item">
     <div class="acc-head" onclick="accToggle(this)"><span class="ico"><svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M12 3v18M3 7l9 5 9-5M3 17l9 5 9-5"/></svg></span> ${w.t}<span class="chev">▾</span></div>
     <div class="acc-body"><div class="inner"><span class="lbl">Как проверить:</span> ${w.how}</div></div></div>`).join('');
}
function accToggle(h){const it=h.parentElement;it.classList.toggle('open');const b=h.nextElementSibling;b.style.maxHeight=it.classList.contains('open')?b.scrollHeight+'px':0;}

/* ====================================================
   CHECKLIST PAGE
==================================================== */
const CHECK={
 'Кузов':[{t:'Зазоры между панелями',s:'Равномерность слева/справа — следы ДТП',full:true},
   {t:'Толщина ЛКП толщиномером',s:'>200 мкм = перекрас. Капот, двери, крылья',full:false},
   {t:'Ржавчина: пороги, арки, днище',s:'Фонариком в скрытые зоны',full:true}],
 'Двигатель':[{t:'Уровень и цвет масла по щупу',s:'Эмульсия = проблема ГБЦ',full:false},
   {t:'Подтёки и запах гари в подкапотке',s:'Сальники, прокладки, патрубки',full:true},
   {t:'Холодный пуск',s:'Просить не прогревать заранее',full:false}],
 'КПП':[{t:'Переключения на тест-драйве',s:'АКПП без рывков и задержек',full:false},
   {t:'Цвет/запах жидкости АКПП',s:'Не должна пахнуть горелым',full:true}],
 'Подвеска':[{t:'Стуки на неровностях',s:'Стойки стаба, сайлентблоки',full:false},
   {t:'Равномерность износа шин',s:'Косвенно о развале/подвеске',full:true}],
 'Электрика':[{t:'Стеклоподъёмники, климат, мультимедиа',s:'Прощёлкать все кнопки',full:true},
   {t:'Ошибки по OBD-II сканеру',s:'Считать и сбросить, проверить повтор',full:false}],
 'Документы':[{t:'Сверить VIN: кузов, ПТС, стекло',s:'Совпадение и читаемость',full:false},
   {t:'Отчёт по истории (ДТП, владельцы, залог)',s:'Сверить с объявлением',full:false},
   {t:'Сервисная книжка / чеки',s:'Подтверждение заявленных замен',full:true}]
};
const ICO_SVG=(p)=>`<svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${p}</svg>`;
const SECICO={
 'Кузов':ICO_SVG('<path d="M3 13l2-5h14l2 5"/><path d="M3 13h18v4H3z"/><circle cx="7.5" cy="17.5" r="1.4"/><circle cx="16.5" cy="17.5" r="1.4"/>'),
 'Двигатель':ICO_SVG('<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M5 5l2 2M17 17l2 2M19 5l-2 2M7 17l-2 2"/>'),
 'КПП':ICO_SVG('<circle cx="6" cy="6" r="2"/><circle cx="12" cy="6" r="2"/><circle cx="6" cy="18" r="2"/><path d="M6 8v8M12 8v3a3 3 0 0 1-3 3H6"/>'),
 'Подвеска':ICO_SVG('<path d="M8 3h8M8 21h8M9 5l6 3-6 3 6 3-6 3"/>'),
 'Электрика':ICO_SVG('<path d="M13 2 4.5 13.5H11l-1 8.5L19.5 10H13z"/>'),
 'Документы':ICO_SVG('<path d="M6 2h8l4 4v16H6z"/><path d="M14 2v4h4M9 13h6M9 17h6"/>')
};
let chkFull=true;
function renderChecklist(){
  const b=document.getElementById('checklistBody');if(!b)return;
  b.innerHTML=Object.entries(CHECK).map(([sec,items],i)=>{
    const list=items.filter(it=>chkFull||!it.full);if(!list.length)return'';
    return `<div class="acc-item ${i===0?'open':''}">
      <div class="acc-head" onclick="accToggle(this)"><span class="ico">${SECICO[sec]||''}</span> ${sec} <span class="cnt" style="margin-left:6px">${list.length}</span><span class="chev">▾</span></div>
      <div class="acc-body" ${i===0?'style="max-height:640px"':''}><div class="inner">
        ${list.map(it=>`<div class="chk-line" onclick="this.classList.toggle('done')"><span class="chk-box">✓</span><span class="chk-txt">${it.t}<small>${it.s}</small></span></div>`).join('')}
      </div></div></div>`;}).join('');
}

/* ---------- init ---------- */
document.addEventListener('DOMContentLoaded',()=>{
  renderRisks();renderRepair();renderClaims();renderWeak();renderChecklist();

  /* count-up: tag stat numbers + verdict %, then observe */
  document.querySelectorAll('.stat b').forEach(el=>{if(!el.hasAttribute('data-countup'))el.setAttribute('data-countup',el.textContent.trim());});
  const gNum=document.querySelector('.gauge .num b');
  if(gNum&&!gNum.hasAttribute('data-countup'))gNum.setAttribute('data-countup',gNum.textContent.trim());
  document.querySelectorAll('[data-countup]').forEach(el=>ioCount.observe(el));
  const gRing=document.querySelector('.gauge circle:last-of-type');
  if(gRing)ioGauge.observe(gRing);

  /* risk filters */
  document.getElementById('riskFilter')?.addEventListener('click',e=>{
    if(e.target.tagName!=='BUTTON')return;
    [...e.currentTarget.children].forEach(b=>b.classList.remove('on'));
    e.target.classList.add('on');riskF=e.target.dataset.f;renderRisks();});

  /* checklist mode */
  document.getElementById('chkMode')?.addEventListener('click',e=>{
    if(e.target.tagName!=='BUTTON')return;
    [...e.currentTarget.children].forEach(b=>b.classList.remove('on'));
    e.target.classList.add('on');chkFull=e.target.dataset.m==='full';renderChecklist();});
});
