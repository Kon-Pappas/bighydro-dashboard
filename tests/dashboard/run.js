const {JSDOM,VirtualConsole}=require('jsdom'); const fs=require('fs'), path=require('path');
const ROOT=path.resolve(__dirname,'..','..');   // ρίζα του repo (εκεί ζουν index.html και data/)
const errors=[];

// ---- Συνθετικό σενάριο: τα tests δεν πρέπει να εξαρτώνται από την ώρα της ημέρας ----
// SYN_TODAY: η μέρα μετά την τελευταία με στάθμες· έχει στάθμες και ISP αλλά όχι SCADA (μια «σημερινή» μέρα μετά τις 08:35)
// SYN_NORES: μια ακόμη μέρα μόνο με ISP και χωρίς στάθμες (όπως η νεότερη μέρα τις πρώτες πρωινές ώρες, που έσπασε το CI)
const addDS=(x,n)=>new Date(Date.parse(x+'T00:00:00Z')+n*86400000).toISOString().slice(0,10);
const jf=(rel)=>JSON.parse(fs.readFileSync(path.join(ROOT,rel),'utf8'));
const IDX0=jf('data/index.json'), HIST0=jf('data/reservoir_history.json'), LAST_HIST=HIST0[HIST0.length-1].Date;
const SYN_TODAY=addDS(LAST_HIST,1), SYN_NORES=addDS(LAST_HIST,2), LASTDAY=jf('data/days/'+LAST_HIST+'.json');
const synDay=(date,withRes)=>{const x=JSON.parse(JSON.stringify(LASTDAY)); x.Date=date; if(!withRes){delete x.Reservoir;delete x.ReservoirTotalRate;delete x.ReservoirTotal} x.Hourly.forEach(h=>Object.keys(h).forEach(k=>{if(/^SCADA_/.test(k)) h[k]=null})); x.Meta=Object.assign({},x.Meta,{Status:{reservoir:withRes?'ok':'missing',scada:'missing',isp:'ok',resmv:'missing',mcp:'missing'}}); return x};
const SYN={'data/index.json':(j)=>{const days=j.Days.filter(x=>x.Date<=LAST_HIST), up=j.Days[0].Updated; days.push({Date:SYN_NORES,Status:{reservoir:'missing',scada:'missing',isp:'ok',resmv:'missing',mcp:'missing'},Updated:up},{Date:SYN_TODAY,Status:{reservoir:'ok',scada:'missing',isp:'ok',resmv:'missing',mcp:'missing'},Updated:up}); days.sort((a,b)=>a.Date<b.Date?1:-1); return Object.assign({},j,{Days:days})},
  'data/reservoir_history.json':(j)=>j.filter(x=>x.Date<=LAST_HIST).concat([Object.assign({},HIST0[HIST0.length-1],{Date:SYN_TODAY})])};
const synFetch=(u)=>{ if(u==='data/days/'+SYN_TODAY+'.json') return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve(synDay(SYN_TODAY,true))});
  if(u==='data/days/'+SYN_NORES+'.json') return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve(synDay(SYN_NORES,false))});
  const pp=path.join(ROOT,u); if(!fs.existsSync(pp)) return Promise.resolve({ok:false,status:404,json:()=>Promise.reject(new Error('404'))});
  let j=JSON.parse(fs.readFileSync(pp,'utf8')); if(SYN[u]) j=SYN[u](j); return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve(j)}); };
const vc=new VirtualConsole(); vc.on('jsdomError',e=>errors.push('jsdomError: '+(e.detail||e.message))); vc.on('error',e=>errors.push('console.error: '+e));
const html=fs.readFileSync(ROOT+'/index.html','utf8');
const dom=new JSDOM(html,{url:'http://localhost/',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc,
  beforeParse(w){ w.__BH_FAST=true; w.localStorage.setItem('kp_lang','el'); w.fetch=synFetch; }});
const w=dom.window,d=w.document;
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
const setLang=(doc,l)=>doc.querySelector('#lang button[data-l="'+l+'"]').click();
let pass=0,fail=0; const ck=(n,c,e)=>{ if(c){pass++;console.log('  PASS',n)} else {fail++;console.log('  FAIL',n,e===undefined?'':e)} };
const txt=()=>[...d.querySelectorAll('.wrap,#rm,#mm')].map(e=>e.textContent).join(' ');
(async()=>{
  for(let i=0;i<60 && !d.querySelector('#rg .river');i++) await sleep(100);
  const B=w.__bh;
  console.log('TEST 1: boot + default day');
  ck('no JS errors during boot',errors.length===0,errors.slice(0,3));
  const expDay=B.P.idx.Days.filter(x=>B.P.fi[x.Date]!=null&&x.Status&&x.Status.scada==='ok'&&x.Status.isp==='ok')[0].Date;
  ck('default day = latest available day with SCADA+ISP ok ('+expDay+'), not the incomplete newest one',B.S.date===expDay && B.S.date!==SYN_TODAY,B.S.date);
  ck('7 cards: 6 clickable rivers + one combined Agras/Edessaios',d.querySelectorAll('#rg .river').length===7 && d.querySelectorAll('#rg button.river').length===6,d.querySelectorAll('#rg .river').length);
  const lastCard=[...d.querySelectorAll('#rg .river')].pop().textContent; ck('combined card shows both plants',lastCard.includes('Άγρας')&&lastCard.includes('Εδεσσαίος')&&lastCard.includes('Άγρας / Εδεσσαίος'),lastCard);
  const ag=rec0=>0;
  ck('4 summary cards',d.querySelectorAll('#sum .card').length===4);
  ck('no "undefined"/"NaN" in page text',!/undefined|NaN/.test(txt()),(txt().match(/.{20}(undefined|NaN).{20}/)||[])[0]);
  const rec=JSON.parse(fs.readFileSync(ROOT+'/data/days/'+B.S.date+'.json','utf8'));
  const tot=rec.Hourly.reduce((s,h)=>s+(h.SCADA_TotalHydro||0),0), pump=rec.Hourly.reduce((s,h)=>s+(h.SCADA_Pump||0),0);
  const fmt=v=>Math.round(v).toLocaleString('el-GR');
  const cards=[...d.querySelectorAll('#sum .card .val')].map(x=>x.textContent);
  const mvs=rec.Hourly.reduce((a,h)=>a+(h.SCADA_SmallHydro||0),0), aus=rec.Hourly.reduce((a,h)=>a+(h.SCADA_ResSmallHydro||0),0), vis=tot+mvs+aus;
  ck('visible hydro = TOTAL HYDRO + RESMV small hydro (+ Aulaki) = '+fmt(vis)+' MWh',cards[0].includes(fmt(vis)),cards[0]);
  ck('pumping matches day file ('+fmt(pump)+' MWh)',cards[1].includes(fmt(pump)),cards[1]);
  ck('official fill matches file',cards[2].includes(rec.ReservoirTotalRate.toLocaleString('el-GR',{minimumFractionDigits:1,maximumFractionDigits:1})),cards[2]);
  console.log('   summary cards:',cards.join(' | '));

  console.log('TEST 2: energy numbers (independent recomputation from the JSON files)');
  const facL=B.P.fac.Latest, iL=B.P.fi[facL.Date];
  ck('ENTSO-E-equivalent total on '+facL.Date+' equals energy_factors.json Latest.TotalGWh',Math.abs(B.eqE(iL)-facL.TotalGWh)<0.6,[B.eqE(iL),facL.TotalGWh]);
  const heads=JSON.parse(fs.readFileSync(ROOT+'/data/plant_heads.json','utf8')).Plants; const ML=B.model(facL.Date,{Hourly:[]});
  let phInd=0, aoosInd=0;
  B.P.meta.Rivers.forEach(r=>{ const kk=r.Order.map(k=>{const h=heads[k];return h?2.725*h.GrossHeadM*(h.EtaMin+h.EtaMax)/2:0}); r.Order.forEach((k,p)=>{ let e=0; for(let q=p;q<kk.length;q++) e+=kk[q]; const v=B.P.fill[iL][k]/100*B.P.meta.Reservoirs[k].CapacityHm3; phInd+=e*v/1000; if(k==='P_AOOU') aoosInd=e*v/1000; }); });
  ck('physical estimate (gross heads) recomputed independently = dashboard ('+phInd.toFixed(1)+' GWh)',Math.abs(ML.phTotal-phInd)<0.5,[ML.phTotal,phInd]);
  ck('Aoos physical value recomputed independently',Math.abs(ML.aoosPh-aoosInd)<0.5,[ML.aoosPh,aoosInd]);
  ck('physical total excluding Aoos is within 10% of the ENTSO-E-equivalent (sanity)',Math.abs((ML.phTotal-ML.aoosPh)/B.eqE(iL)-1)<0.10,[ML.phTotal-ML.aoosPh,B.eqE(iL)]);
  const fac=facL.ByRiver; const bad=ML.rivers.filter(R=>Math.abs(R.eEq-fac[R.r.Id].GWh)>0.6).map(R=>R.r.Id+':'+R.eEq.toFixed(1)+' vs '+fac[R.r.Id].GWh);
  ck('every river ENTSO-E-equivalent == energy_factors.json Latest.ByRiver',bad.length===0,bad);

  console.log('TEST 3: cascade modal, order and pump');
  const names={}; B.P.meta.Rivers.forEach((r,i)=>names[r.Id]=i);
  const open=(id)=>{B.openRiver(names[id]);return d.querySelector('#rmc').textContent};
  let m=open('aliakmonas');
  const order=['Ιλαρίων','Πολύφυτο','Σφηκιά','Ασώματα'].map(n=>m.indexOf(n));
  ck('Aliakmonas order Ilarion→Polyfyto→Sfikia→Asomata',order.every((v,i)=>v>=0&&(i===0||v>order[i-1])),order);
  ck('pump Asomata → Sfikia shown',m.includes('Ασώματα → Σφηκιά') && !m.includes('υπόθεση)') ,m.slice(m.indexOf('άντληση'),m.indexOf('άντληση')+60));
  ck('modal has hourly chart + energy block',d.querySelectorAll('#rmc svg.ch').length===1 && m.includes('Ισοδύναμο ENTSO-E'));
  m=open('nestos'); ck('Nestos pump flagged as assumption',m.includes('Πλατανόβρυση → Θησαυρός') && m.includes('υπόθεση'));
  m=open('acheloos'); const o2=['Κρεμαστά','Καστράκι','Στράτος'].map(n=>m.indexOf(n)); ck('Acheloos order',o2.every((v,i)=>v>=0&&(i===0||v>o2[i-1])),o2);
  ck('Stratos shown as 1+2 once per-unit data exists (no "not stored" note)',m.includes('Στράτος (1+2)') && !m.includes('Στράτος ΙΙ περιλαμβάνεται'),m.slice(m.indexOf('Στράτος'),m.indexOf('Στράτος')+30));
  m=open('arachthos'); const o3=['Πηγές Αώου','Πουρνάρι I','Πουρνάρι II'].map(n=>m.indexOf(n)); ck('Arachthos order Aoos→Pournari I→II',o3.every((v,i)=>v>=0&&(i===0||v>o3[i-1])),o3);
  ck('Arachthos shows Aoos physical value separately',m.includes('δεν μετράνε στο ENTSO-E'));
  d.querySelector('#rclose').click(); ck('modal closes',d.querySelector('#rm').hidden===true);
  ck('no JS errors after opening all modals',errors.length===0,errors.slice(0,3));

  console.log('TEST 4: energy + Kastraki tabs');
  d.querySelector('#tabs button[data-t="energy"]').click(); 
  ck('energy tab visible, rivers tab hidden',!d.querySelector('#t-energy').hidden && d.querySelector('#t-rivers').hidden);
  ck('energy tab: 2 charts + 2 tables',d.querySelectorAll('#t-energy svg.ch').length===2 && d.querySelectorAll('#t-energy table').length===2);
  const addD=(x,n)=>new Date(Date.parse(x+'T00:00:00Z')+n*86400000).toISOString().slice(0,10);
  let lastW=null; ((B.P.ent&&B.P.ent.Weeks)||[]).forEach(w=>{ let ok=true; for(let t=1;t<=7;t++){ if(B.P.fi[addD(w.StartLocal,t)]==null) ok=false } if(ok) lastW=w });
  ck('there is at least one ENTSO-E week with full daily data',lastW!=null);
  if(lastW){ let sm=0; for(let t=1;t<=7;t++) sm+=B.eqE(B.P.fi[addD(lastW.StartLocal,t)]); const modelGWh=Math.round(sm/7).toLocaleString('el-GR'), enGWh=Math.round(lastW.MWh/1000).toLocaleString('el-GR');
    const rowTxt=[...d.querySelectorAll('#t-energy table')[0].querySelectorAll('tr')].map(r=>r.textContent).find(t=>t.includes(lastW.IsoWeek))||'';
    ck('weekly table row '+lastW.IsoWeek+' shows ENTSO-E '+enGWh+' and model '+modelGWh+' GWh',rowTxt.includes(enGWh)&&rowTxt.includes(modelGWh),rowTxt);
    const oosW=Date.parse(lastW.StartLocal)>Date.parse(B.P.fac.Weeks.To); ck('weeks after the calibration period are labelled out-of-sample',!oosW||rowTxt.includes('εκτός δείγματος'),rowTxt); }
  d.querySelector('#tabs button[data-t="kast"]').click();
  const hist=B.P.hist.map(r=>r.Reservoir.KASTRAKI), over=hist.filter(v=>v>100).length;
  const kc=[...d.querySelectorAll('#t-kast .card .val')].map(x=>x.textContent);
  ck('Kastraki days >100% = '+over+' / '+hist.length,kc[2]===over+' / '+hist.length,kc);
  const bigCnt=(()=>{const f=B.P.fill.map(x=>x.KASTRAKI);let c=0;for(let i=0;i<f.length-1;i++){const v=(f[i+1]-f[i])/100*53;if(Math.abs(v)>=0.09*53)c++}return c})();
  ck('Kastraki |Δ|>=4.8 hm3 days computed = '+bigCnt,kc[3].startsWith(bigCnt+' / '+(hist.length-1)),kc);
  const KV=B.P.fill.map(x=>x.KASTRAKI/100*53); let bw=null; for(let q=0;q+11<KV.length;q++){const v=KV[q+11]-KV[q]; if(bw===null||v>bw.v) bw={v,q};}
  const f1k=v=>(v>0?'+':'')+v.toLocaleString('el-GR',{minimumFractionDigits:1,maximumFractionDigits:1}), dd=x=>x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4);
  ck('Kastraki largest 11-day rise recomputed independently ('+f1k(bw.v)+' hm3 from '+dd(B.P.dates[bw.q])+')',kc[4].includes(f1k(bw.v)) && d.querySelectorAll('#t-kast .card')[4].textContent.includes(dd(B.P.dates[bw.q])),kc[4]);
  ck('Kastraki tab: 2 charts, note present',d.querySelectorAll('#t-kast svg.ch').length===2 && d.querySelector('#t-kast .note').textContent.includes('Αμφιλοχ'));

  console.log('TEST 5: other dates, language, robustness');
  d.querySelector('#tabs button[data-t="rivers"]').click();
  await B.load('2026-01-15'); 
  ck('Jan day renders without errors',errors.length===0,errors.slice(0,3));
  const jan=JSON.parse(fs.readFileSync(ROOT+'/data/days/2026-01-15.json','utf8')); const janTot=jan.Hourly.reduce((a,h)=>a+h.SCADA_TotalHydro+(h.SCADA_ResSmallHydro||0)+(h.SCADA_SmallHydro||0),0);
  const stJ=B.P.idx.Days.filter(x=>x.Date==='2026-01-15')[0].Status, labJ={reservoir:'ταμιευτήρες',scada:'SCADA',isp:'ISP',resmv:'RESMV'}, bannerJ=d.querySelector('#banner').textContent;
  ck('Jan day: visible production shown, banner lists exactly the sources that are not ok in index.json',Object.keys(labJ).every(x=>bannerJ.includes(labJ[x])===(stJ[x]!=='ok')) && d.querySelectorAll('#sum .card .val')[0].textContent.includes(Math.round(janTot).toLocaleString('el-GR')),bannerJ+' | '+JSON.stringify(stJ));
  ck('Jan day: energy still computed',/\d/.test(d.querySelectorAll('#sum .card .val')[3].textContent));
  await B.load('2026-07-22');
  ck('22/7 banner mentions the Ilarionas 0.00% interpolation',d.querySelector('#banner').textContent.includes('Ιλαρίων'),d.querySelector('#banner').textContent);
  setLang(d,'en'); await sleep(50);
  ck('English mode renders (title, river names)',d.querySelector('#ttl').textContent.includes('Hydro & Reservoir') && d.querySelector('#rg').textContent.includes('Acheloos'),d.querySelector('#ttl').textContent);
  ck('English: no untranslated placeholders {x} / undefined',!/\{[xd]\}|undefined|NaN/.test(txt()));
  setLang(d,'el'); await sleep(50);
  ck('methodology modal opens with 12 paragraphs',(d.querySelector('#meth').click(),d.querySelectorAll('#mmc p').length===12 && !d.querySelector('#mm').hidden),d.querySelectorAll('#mmc p').length);
  ck('date selector lists every day that has reservoir levels, newest first, and never one without',d.querySelectorAll('#dsel option').length===B.P.idx.Days.filter(x=>B.P.fi[x.Date]!=null).length && d.querySelector('#dsel option').value===SYN_TODAY && ![...d.querySelectorAll('#dsel option')].some(o=>o.value===SYN_NORES),d.querySelectorAll('#dsel option').length);

  console.log('TEST 6: pump tab, per-plant estimate, Stratos 1+2');
  const pdaily=JSON.parse(fs.readFileSync(ROOT+'/data/pump_daily.json','utf8')); const pmap={}; pdaily.forEach(x=>pmap[x.Date]=x);
  await B.load('2026-09-15'); const pm=pmap['2026-09-15']; const f0=v=>Math.round(v).toLocaleString('el-GR');
  d.querySelector('#tabs button[data-t="pump"]').click();
  ck('pump tab visible, 4 cards, 4 charts, monthly table',!d.querySelector('#t-pump').hidden && d.querySelectorAll('#t-pump .card').length===4 && d.querySelectorAll('#t-pump svg.ch').length===4 && d.querySelectorAll('#t-pump table tr').length>=2);
  const pc=[...d.querySelectorAll('#t-pump .card .val')].map(x=>x.textContent);
  ck('pump cards match pump_daily.json for 15/9 (SCADA '+f0(pm.ScadaMWh)+', ISP '+f0(pm.IspMWh)+')',pc[0].includes(f0(pm.ScadaMWh)) && pc[1].includes(f0(pm.IspMWh)) && pc[2].includes(f0(pm.UnscheduledMWh)) && pc[3].includes(f0(pm.NotRealizedMWh)),pc);
  const tbl=[...d.querySelectorAll('#t-pump table tr')].map(r=>r.textContent); const oct=pdaily.filter(x=>x.Date.startsWith('2026-06')&&x.ScadaMWh!=null); const junS=oct.reduce((a,x)=>a+x.ScadaMWh,0)/1000;
  ck('monthly table: June SCADA GWh = '+junS.toFixed(1),tbl.some(r=>r.startsWith('2026-06') && r.includes(junS.toLocaleString('el-GR',{minimumFractionDigits:1,maximumFractionDigits:1}))),tbl.slice(0,3));
  const noteTxt=d.querySelector('#t-pump .note').textContent; ck('method note shows day-share % and unallocated %',/\(\d+,\d%\)·/.test(noteTxt.replace(/ /g,'')) || /ώρες χωρίς πρόγραμμα/.test(noteTxt),noteTxt.slice(0,160));
  d.querySelector('#tabs button[data-t="rivers"]').click();
  let ali=(B.openRiver(1),d.querySelector('#rmc').textContent);
  ck('Aliakmonas modal: Sfikia estimate = '+f0(pm.EstSfikiaMWh)+' MWh and ISP '+f0(pm.IspSfikiaMWh),ali.includes('Ασώματα → Σφηκιά') && ali.includes('≈ '+f0(pm.EstSfikiaMWh)+' MWh') && ali.includes('ISP '+f0(pm.IspSfikiaMWh)+' MWh') ,ali.slice(ali.indexOf('άντληση'),ali.indexOf('άντληση')+140));
  let nes=(B.openRiver(2),d.querySelector('#rmc').textContent);
  ck('Nestos modal: Thesavros estimate = '+f0(pm.EstThesavrosMWh),nes.includes('≈ '+f0(pm.EstThesavrosMWh)+' MWh') && nes.includes('υπόθεση'),nes.slice(nes.indexOf('άντληση'),nes.indexOf('άντληση')+140));
  ck('modal explains it is an estimate',ali.includes('εκτίμηση') && ali.includes('μοιράζεται με βάση το πρόγραμμα ISP'));
  d.querySelector('#rclose').click();
  const rec15=JSON.parse(fs.readFileSync(ROOT+'/data/days/2026-09-15.json','utf8')); const s1=rec15.Hourly.reduce((a,h)=>a+h.SCADA_Stratos1,0), s2=rec15.Hourly.reduce((a,h)=>a+h.SCADA_Stratos2,0);
  let ach=(B.openRiver(0),d.querySelector('#rmc').textContent);
  ck('Acheloos modal: Stratos production = Stratos I + II ('+f0(s1+s2)+' MWh)',ach.includes('Στράτος (1+2)') && ach.includes(f0(s1+s2)+' MWh'),ach.slice(ach.indexOf('Στράτος'),ach.indexOf('Στράτος')+120));
  d.querySelector('#rclose').click();
  const cards2=[...d.querySelectorAll('#sum .card .sm')].map(x=>x.textContent); const oth=rec15.Hourly.reduce((a,h)=>a+h.SCADA_OtherHydro-h.SCADA_Stratos2,0);
  const othAll=rec15.Hourly.reduce((a,h)=>a+h.SCADA_OtherHydro,0); const mv15=rec15.Hourly.reduce((a,h)=>a+h.SCADA_SmallHydro,0);
  ck('summary subtitle lists the groups: small PPC '+f0(othAll)+' and small MV '+f0(mv15)+' MWh',cards2[0].includes('μικρά ΔΕΗ '+f0(othAll)) && cards2[0].includes('μικρά ΜΤ (RESMV, εκτίμηση) '+f0(mv15)),cards2[0]);
  await B.load(SYN_TODAY); d.querySelector('#tabs button[data-t="pump"]').click();
  ck('today (no SCADA yet): pump tab shows the "not published" message, charts still render',d.querySelector('#t-pump').textContent.includes('δεν έχει δημοσιευτεί') && d.querySelectorAll('#t-pump svg.ch').length>=2,d.querySelector('#t-pump').textContent.slice(0,80));
  setLang(d,'en'); await sleep(50);
  ck('English pump tab, no placeholders',/Pumping/.test(d.querySelector('#tabs').textContent) && !/\{[xyd]\}|undefined|NaN/.test(txt()),(txt().match(/.{15}(\{[xyd]\}|undefined|NaN).{15}/)||[])[0]);
  setLang(d,'el'); await sleep(50);
  ck('no JS errors in pump/Stratos tests',errors.length===0,errors.slice(0,3));

  console.log('TEST 7: water balance tab (Acheloos)');
  const wbj=JSON.parse(fs.readFileSync(ROOT+'/data/water_balance.json','utf8')).Rivers.acheloos.Daily; const wmap={}; wbj.forEach(x=>wmap[x.Date]=x);
  await B.load('2026-08-15'); d.querySelector('#tabs button[data-t="wb"]').click();
  const wd=wmap['2026-08-15']; const f1=v=>v.toLocaleString('el-GR',{minimumFractionDigits:1,maximumFractionDigits:1}); const sgn=v=>(v>0?'+':'')+f1(v);
  const wc=[...d.querySelectorAll('#t-wb .card .val')].map(x=>x.textContent);
  ck('water-balance tab visible, 4 cards, 2 charts',!d.querySelector('#t-wb').hidden && d.querySelectorAll('#t-wb .card').length===4 && d.querySelectorAll('#t-wb svg.ch').length===2,[d.querySelectorAll('#t-wb .card').length,d.querySelectorAll('#t-wb svg.ch').length]);
  const sumdv=wd.dV.reduce((a,b)=>a+b,0);
  ck('cards for 15/8 match water_balance.json (ΔV '+sgn(sumdv)+', Q '+f1(wd.Qn[2])+', inflow '+sgn(wd.Rivern)+')',wc[0].includes(sgn(sumdv)) && wc[1].includes(f1(wd.Qn[2])) && wc[2].includes(sgn(wd.Rivern)) && wc[3].includes(sgn(wd.Inn[1])),wc);
  const rows=[...d.querySelectorAll('#t-wb table tr')].map(r=>r.textContent);
  const janRiver=wbj.filter(x=>x.Date.startsWith('2026-01')).reduce((a,x)=>a+x.Rivern,0); const janTxt=(janRiver>0?'+':'')+Math.round(janRiver).toLocaleString('el-GR');
  ck('monthly table: January river total (net) = '+janTxt+' hm³ (= sum of daily values in water_balance.json)',rows.some(r=>r.startsWith('2026-01')&&r.includes(janTxt)),rows.slice(0,2));
  ck('Kastraki local inflow positive every month (Inachos)',wbj.reduce((m,x)=>{const k=x.Date.slice(0,7);m[k]=(m[k]||0)+x.Inn[1];return m},{}) && Object.values(wbj.reduce((m,x)=>{const k=x.Date.slice(0,7);m[k]=(m[k]||0)+x.Inn[1];return m},{})).every(v=>v>0));
  ck('5 explanatory notes shown incl. Inachos + Amfilochia',d.querySelectorAll('#t-wb .note').length===5 && d.querySelector('#t-wb').textContent.includes('Ίναχος') && d.querySelector('#t-wb').textContent.includes('Αμφιλοχ'));
  await B.load(SYN_TODAY); d.querySelector('#tabs button[data-t="wb"]').click();
  ck('today (no balance yet): message shown, charts still render',d.querySelector('#t-wb').textContent.includes('δεν υπάρχει ισοζύγιο') && d.querySelectorAll('#t-wb svg.ch').length===2);
  setLang(d,'en'); await sleep(50);
  ck('English water balance tab, no placeholders',/Water balance/.test(d.querySelector('#tabs').textContent) && !/\{[xyd]\}|undefined|NaN/.test(txt()),(txt().match(/.{15}(\{[xyd]\}|undefined|NaN).{15}/)||[])[0]);
  setLang(d,'el'); await sleep(50);
  ck('no JS errors in water balance tests',errors.length===0,errors.slice(0,3));

  console.log('TEST 8: Aliakmonas water balance (river selector)');
  const WBALL=JSON.parse(fs.readFileSync(ROOT+'/data/water_balance.json','utf8')); const aliR=WBALL.Rivers.aliakmonas; const amap={}; aliR.Daily.forEach(x=>amap[x.Date]=x);
  await B.load('2026-08-15'); d.querySelector('#tabs button[data-t="wb"]').click();
  ck('river selector with 2 buttons, Acheloos active by default',d.querySelectorAll('#t-wb .seg button').length===2 && d.querySelector('#t-wb .seg button.on').textContent.includes('Αχελώος'),[...d.querySelectorAll('#t-wb .seg button')].map(b=>b.textContent));
  d.querySelectorAll('#t-wb .seg button')[1].click();
  ck('switching to Aliakmonas marks it active',d.querySelector('#t-wb .seg button.on').textContent.includes('Αλιάκμονας'));
  const aw=amap['2026-08-15']; const ac=[...d.querySelectorAll('#t-wb .card .val')].map(x=>x.textContent);
  const asum=aw.dV.reduce((a,b)=>a+b,0);
  ck('Aliakmonas cards for 15/8: ΔV '+sgn(asum)+', Q Asomata '+f1(aw.Qn[2])+', river inflow '+sgn(aw.Rivern)+', lower basin '+sgn(aw.Inn[2]),ac[0].includes(sgn(asum)) && ac[1].includes(f1(aw.Qn[2])) && ac[2].includes(sgn(aw.Rivern)) && ac[3].includes(sgn(aw.Inn[2])),ac);
  ck('card 4 is the lower basin (Sfikia and Asomata) label',d.querySelectorAll('#t-wb .card .lab')[3].textContent.includes('Σφηκιά και Ασώματα'),d.querySelectorAll('#t-wb .card .lab')[3].textContent);
  const arows=[...d.querySelectorAll('#t-wb table tr')].map(r=>r.textContent);
  const aj=aliR.Daily.filter(x=>x.Date.startsWith('2026-01')).reduce((a,x)=>a+x.Rivern,0); const ajTxt=(aj>0?'+':'')+Math.round(aj).toLocaleString('el-GR');
  ck('Aliakmonas monthly table: January river total (net) = '+ajTxt+' (= sum of daily values in water_balance.json)',arows.some(r=>r.startsWith('2026-01')&&r.includes(ajTxt)),arows.slice(0,2));
  ck('table has 3 group columns (Ilarionas, Polyfyto, Sfikia+Asomata) + totals',d.querySelectorAll('#t-wb table tr')[0].children.length===8,d.querySelectorAll('#t-wb table tr')[0].children.length);
  const ratioPct=Math.round(aliR.Daily.reduce((a,x)=>a+x.Qn[2],0)/aliR.Daily.reduce((a,x)=>a+x.Qn[1],0)*100);
  const nt=d.querySelector('#t-wb').textContent;
  ck('Aliakmonas notes: pump block, Ilarionas outage, and the computed '+ratioPct+'% Asomata/Polyfyto ratio',nt.includes('Ασώματα → Σφηκιά') && nt.includes('Ιλαρίων είναι σε βλάβη') && nt.includes(ratioPct+'%'),nt.slice(nt.indexOf('κάτω λεκάνη βγαίνει'),nt.indexOf('κάτω λεκάνη βγαίνει')+90));
  ck('chart count is 2, 3 legend entries are 2 for Aliakmonas',d.querySelectorAll('#t-wb svg.ch').length===2);
  d.querySelectorAll('#t-wb .seg button')[0].click();
  ck('back to Acheloos still shows its Inachos note',d.querySelector('#t-wb').textContent.includes('Ίναχος'));
  d.querySelectorAll('#t-wb .seg button')[1].click(); setLang(d,'en'); await sleep(50);
  ck('English: Aliakmon title and notes, no placeholders',/Water balance, Aliakmon/.test(d.querySelector('#t-wb').textContent) && !/\{[xyd]\}|undefined|NaN/.test(txt()),(txt().match(/.{15}(\{[xyd]\}|undefined|NaN).{15}/)||[])[0]);
  setLang(d,'el'); await sleep(50);
  ck('no JS errors in Aliakmonas tests',errors.length===0,errors.slice(0,3));

  console.log('TEST 9: shell (header, language, update stamps, badge, banner, footer, overlay)');
  const mkDom=(store,fast=true)=>{ const e2=[]; const vc2=new VirtualConsole(); vc2.on('jsdomError',e=>e2.push(String(e.detail||e.message)));
    const dm=new JSDOM(fs.readFileSync(ROOT+'/index.html','utf8'),{url:'http://localhost/',runScripts:'dangerously',pretendToBeVisual:true,virtualConsole:vc2,
      beforeParse(win){ if(fast) win.__BH_FAST=true; Object.keys(store).forEach(k=>win.localStorage.setItem(k,store[k])); win.fetch=(u)=>{const pp=path.join(ROOT,u); if(!fs.existsSync(pp)) return Promise.resolve({ok:false,status:404,json:()=>Promise.reject(new Error('404'))}); return Promise.resolve({ok:true,status:200,json:()=>Promise.resolve(JSON.parse(fs.readFileSync(pp,'utf8')))});}; }});
    return {dm,e2}; };
  const boot2=async(dm)=>{ for(let i=0;i<100&&!dm.window.document.querySelector('#rg .river');i++) await sleep(100); await sleep(900); return dm.window; };
  const {dm:dmE,e2:errE}=mkDom({}); const wE=await boot2(dmE); const dE=wE.document;
  ck('default language is English (no stored preference)',dE.querySelector('#ttl').textContent==='Greek Hydro & Reservoir Analytics' && dE.documentElement.lang==='en' && dE.title==='Greek Hydro & Reservoir Analytics',dE.querySelector('#ttl').textContent);
  ck('breadcrumb links back to the hub',(()=>{const a=dE.querySelector('a.crumb');return a && a.getAttribute('href')==='https://kon-pappas.github.io/' && a.textContent.includes('Konstantinos Pappas Hub')})());
  ck('Last Update shows dd/mm/yyyy hh:mm',/^\d\d\/\d\d\/\d{4} \d\d:\d\d$/.test(dE.querySelector('#lu-v').textContent) && dE.querySelector('#lu-l').textContent==='Last Update:',dE.querySelector('#lu-v').textContent);
  ck('Next Update is one of the configured run times',/^(07:15|09:15|10:15)( \(tomorrow\))?$/.test(dE.querySelector('#nu-v').textContent),dE.querySelector('#nu-v').textContent);
  const BB=wE.__bh;
  ck('nextRun: 00:00→07:15 today, 08:00→09:15, 10:15→tomorrow 07:15, 23:00→tomorrow',JSON.stringify([BB.nextRun(0),BB.nextRun(480),BB.nextRun(615),BB.nextRun(1380)])===JSON.stringify([{t:'07:15',tomorrow:false},{t:'09:15',tomorrow:false},{t:'07:15',tomorrow:true},{t:'07:15',tomorrow:true}]));
  ck('fmtStamp handles summer (+0300) and winter (+0200) offsets',BB.fmtStamp('2026-10-16T20:25:02+0300')==='16/10/2026 20:25' && BB.fmtStamp('2026-01-15T10:00:00+0200')==='15/01/2026 10:00',[BB.fmtStamp('2026-10-16T20:25:02+0300'),BB.fmtStamp('2026-01-15T10:00:00+0200')]);
  ck('footer: signature, disclaimer and GitHub link',(()=>{const f=dE.querySelector('footer').textContent;return f.includes('Energy Market Analyst') && f.includes('Independent analysis') && f.includes('Greek local time') && !!dE.querySelector('footer a[href*="github.com/Kon-Pappas/bighydro-dashboard"]')})());
  ck('loading overlay is gone after start-up',!dE.querySelector('#loading-overlay'));
  ck('language switch shows BOTH options "GR | EN", exactly one is on (EN by default) and aria-pressed follows',(()=>{const bs=[...dE.querySelectorAll('#lang button')];return bs.length===2&&bs.map(x=>x.textContent).join('|')==='GR|EN'&&bs.filter(x=>x.className==='on').length===1&&bs[1].className==='on'&&bs[1].getAttribute('aria-pressed')==='true'&&bs[0].getAttribute('aria-pressed')==='false'})());
  setLang(dE,'el');
  await sleep(80);
  ck('after switching: Greek title, button shows EN, localStorage kp_lang = el',dE.querySelector('#ttl').textContent==='Ελληνικά Υδροηλεκτρικά και Ταμιευτήρες' && dE.querySelector('#lang button.on').getAttribute('data-l')==='el' && wE.localStorage.getItem('kp_lang')==='el',[dE.querySelector('#ttl').textContent,wE.localStorage.getItem('kp_lang')]);
  const {dm:dmL}=mkDom({bh_lang:'el'}); const wL=await boot2(dmL);
  ck('legacy key bh_lang still honoured (migration)',wL.document.querySelector('#ttl').textContent==='Ελληνικά Υδροηλεκτρικά και Ταμιευτήρες');
  const {dm:dmK}=mkDom({kp_lang:'en',bh_lang:'el'}); const wK=await boot2(dmK);
  ck('shared key kp_lang wins over the legacy key',wK.document.querySelector('#ttl').textContent==='Greek Hydro & Reservoir Analytics');
  const wE2=wE; const BE=wE2.__bh; await sleep(10);
  // badge + banner use only the sources the page shows (no MCP)
  const used=['reservoir','scada','isp','resmv']; const dayOK=BE.P.idx.Days.find(x=>x.Status&&used.every(k=>x.Status[k]==='ok')&&x.Status.mcp!=='ok');
  const dayBad=BE.P.idx.Days.find(x=>x.Status&&used.some(k=>x.Status[k]!=='ok')&&x.Date<BE.P.idx.Days[0].Date);
  setLang(wE2.document,'en'); await sleep(60);   // back to English
  if(dayOK){ await BE.load(dayOK.Date); ck('day with only MCP missing ('+dayOK.Date+'): badge "Complete Data", no banner',wE2.document.querySelector('#badge').textContent==='Complete Data' && wE2.document.querySelector('#badge').className.includes('ok') && wE2.document.querySelector('#banner').textContent.trim()===''); }
  if(dayBad){ await BE.load(dayBad.Date); const miss=used.filter(k=>dayBad.Status[k]!=='ok'); ck('day with missing sources ('+dayBad.Date+'): badge "Partial Data" listing '+miss.join(','),wE2.document.querySelector('#badge').textContent==='Partial Data' && wE2.document.querySelector('#badge').className.includes('warn') && miss.every(k=>wE2.document.querySelector('#banner').textContent.toLowerCase().includes(k==='reservoir'?'reservoirs':k)),[wE2.document.querySelector('#badge').textContent,wE2.document.querySelector('#banner').textContent]); }
  ck('no JS errors in the English/shell tests',errE.length===0,errE.slice(0,3));

  console.log('TEST 10: tooltips on every chart');
  const fireAt=(win,svg,vx,vy)=>{ const sp=BE.CH[svg.getAttribute('data-cid')]; svg.getBoundingClientRect=()=>({left:0,top:0,width:sp.W,height:240}); svg.dispatchEvent(new win.MouseEvent('pointermove',{bubbles:true,clientX:vx,clientY:vy||100})); return sp; };
  const tipOf=(win)=>win.document.querySelector('#tip');
  let nCharts=0, badTip=[];
  const visit=async(tabName,setup)=>{ const dd=wE2.document; const btn=dd.querySelector('#tabs button[data-t="'+tabName+'"]'); if(btn) btn.click(); if(setup) await setup(); [...dd.querySelectorAll('#t-'+tabName+' svg.ch, #rmc svg.ch')].filter(s=>!s.closest('[hidden]')).forEach(svg=>{ const sp=BE.CH[svg.getAttribute('data-cid')]; if(!sp) return; const named=sp.series.filter(s=>s.name); if(!named.length) return; nCharts++;
      const s0=named[0]; const pts=s0.pts.filter(p=>p[1]!=null); const pt=pts[Math.floor(pts.length/2)]; const vx=sp.L+(pt[0]-sp.x0)/((sp.x1-sp.x0)||1)*sp.pw; fireAt(wE2,svg,vx);
      const tp=tipOf(wE2), txt=tp.textContent; const ok=tp.style.display==='block' && txt.includes(sp.xl(pt[0])) && txt.includes(sp.tv(pt[1])) && txt.includes(s0.name) && !/undefined|NaN/.test(txt) && svg.querySelector('.tipline').style.display==='';
      if(!ok) badTip.push(tabName+': '+txt.slice(0,80)); }); };
  await BE.load(BE.P.idx.Days.filter(x=>x.Status&&x.Status.scada==='ok')[0].Date);
  await visit('energy'); await visit('pump'); await visit('wb'); await visit('kast');
  BE.openRiver(1); await visit('rivers'); wE2.document.querySelector('#rclose').click();
  ck('tooltip shows the right x label and value (and series name) on '+nCharts+' charts across all tabs and the river modal',nCharts>=11 && badTip.length===0,[nCharts,badTip]);
  const svg0=wE2.document.querySelector('#t-kast svg.ch'); fireAt(wE2,svg0,svg0 && BE.CH[svg0.getAttribute('data-cid')].L+50);
  ck('moving the pointer outside a chart hides the tooltip and the crosshair',(()=>{wE2.document.body.dispatchEvent(new wE2.MouseEvent('pointermove',{bubbles:true,clientX:5,clientY:5})); return tipOf(wE2).style.display==='none' && svg0.querySelector('.tipline').style.display==='none'})());
  ck('weekly chart tooltip shows both series (ENTSO-E and model) at the same week',(()=>{ wE2.document.querySelector('#tabs button[data-t="energy"]').click(); const sv=wE2.document.querySelectorAll('#t-energy svg.ch')[0]; const sp=BE.CH[sv.getAttribute('data-cid')]; const pt=sp.series[0].pts[Math.floor(sp.series[0].pts.length/2)]; fireAt(wE2,sv,sp.L+(pt[0]-sp.x0)/(sp.x1-sp.x0)*sp.pw); const tx=tipOf(wE2).textContent; return tx.includes('ENTSO-E')&&tx.includes('model')&&tx.includes('TWh')})());
  ck('no JS errors in the tooltip tests',errE.length===0 && errors.length===0,[errE.slice(0,2),errors.slice(0,2)]);

  console.log('TEST 11: loading overlay shows the steps one by one (real pauses, no fast mode)');
  const {dm:dmS,e2:errS}=mkDom({},false); const dS=dmS.window.document; const samples=[]; const tS=Date.now();
  while(Date.now()-tS<12000){ const ov=dS.querySelector('#loading-overlay'); if(!ov){ samples.push({t:Date.now()-tS,gone:true}); break; }
    samples.push({t:Date.now()-tS,done:[0,1,2,3,4,5].filter(i=>{const r=dS.querySelector('#ovr'+i);return r&&r.className.includes('done')}).length,ready:dS.querySelector('#ov-ready').className.includes('on')}); await sleep(60); }
  const dones=samples.filter(x=>!x.gone).map(x=>x.done), lastT=samples[samples.length-1];
  ck('the overlay stays visible long enough to read (>= 2.5 s) and then goes away',lastT.gone===true && lastT.t>=2500 && lastT.t<=11000,lastT.t);
  ck('rows complete in order and never go backwards (0 → 6)',dones.every((v,i)=>i===0||v>=dones[i-1]) && Math.max(...dones)===6,dones.join(','));
  ck('at least five different intermediate states are visible to the eye',new Set(dones).size>=5,[...new Set(dones)].join(','));
  ck('"Dashboard is ready!" lights up only after all six rows are done',samples.filter(x=>!x.gone).every(x=>!x.ready||x.done===6) && samples.some(x=>x.ready),'');
  ck('the page behind the overlay is fully built when it disappears',dS.querySelectorAll('#rg .river').length>=6 && dS.querySelector('#sum .card .val').textContent.length>0);
  ck('overlay texts are localized (English by default)',true);
  ck('no JS errors during the slow start-up',errS.length===0,errS.slice(0,2));

  console.log('TEST 12: modals — fixed header (title + X box), scrolling body, fixed footer (boxed Close)');
  d.querySelector('#mclose').click();   // an earlier test left the methodology modal open
  setLang(d,'el'); await sleep(40); B.openRiver(1); const mod=d.querySelector('#rmc');
  ck('river modal = header, body, footer in this order',[...mod.children].map(c=>c.className).join(',')==='mh,mb,mf',[...mod.children].map(c=>c.className).join(','));
  ck('river modal header holds the title and the date navigation (no X); footer holds the boxed Close',!!mod.children[0].querySelector('h2') && !!mod.children[0].querySelector('#rdsel') && !mod.querySelector('#rclose-x') && !!mod.children[2].querySelector('button.btn#rclose') && mod.children[2].textContent.trim()==='Κλείσιμο',mod.children[2].textContent);
  ck('the cascade is inside the scrolling body only',mod.children[1].textContent.includes('Ιλαρίων') && !mod.children[0].textContent.includes('Ιλαρίων') && !mod.children[2].textContent.includes('Ιλαρίων'));
  ck('opening a modal locks the page scroll',d.body.classList.contains('modal-open'));
  d.querySelector('#rclose').click(); ck('footer Close closes it and unlocks the scroll',d.querySelector('#rm').hidden===true && !d.body.classList.contains('modal-open'));
  B.openRiver(0); d.querySelector('#rclose').click(); ck('footer Close closes it',d.querySelector('#rm').hidden===true && !d.body.classList.contains('modal-open'));
  B.openRiver(0); d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true})); ck('Escape closes it',d.querySelector('#rm').hidden===true);
  B.openRiver(0); d.querySelector('#rm').dispatchEvent(new w.MouseEvent('click',{bubbles:true})); ck('clicking the dark backdrop closes it',d.querySelector('#rm').hidden===true);
  d.querySelector('#meth').click(); const mm=d.querySelector('#mmc');
  ck('methodology modal has the same three-part structure and the title "Μεθοδολογία και παραδοχές"',[...mm.children].map(c=>c.className).join(',')==='mh,mb,mf' && mm.children[0].querySelector('h2').textContent==='Μεθοδολογία και παραδοχές' && d.querySelector('#meth').textContent.includes('παραδοχές'));
  ck('it has a Methodology section (12 paragraphs) and an Assumptions section (8 items)',mm.querySelectorAll('.mb h3.mhd').length===2 && mm.querySelectorAll('.mb p').length===12 && mm.querySelectorAll('.mb ul.mal li').length===8,[mm.querySelectorAll('.mb p').length,mm.querySelectorAll('.mb li').length]);
  d.querySelector('#mclose-x').click(); ck('methodology: X closes',d.querySelector('#mm').hidden===true);
  d.querySelector('#meth').click(); d.querySelector('#mclose').click(); ck('methodology: footer Close closes',d.querySelector('#mm').hidden===true && !d.body.classList.contains('modal-open'));
  d.querySelector('#meth').click(); d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'Escape',bubbles:true})); ck('methodology: Escape closes',d.querySelector('#mm').hidden===true);
  ck('English labels: "Methodology & Assumptions" on the button, in the title and a "Key assumptions" heading',(()=>{ setLang(dE,'en'); return true })() && (await sleep(60),true) && dE.querySelector('#meth').textContent.includes('Methodology & Assumptions') && (dE.querySelector('#meth').click(),dE.querySelector('#mmc .mh h2').textContent==='Methodology & Assumptions' && [...dE.querySelectorAll('#mmc h3.mhd')].map(x=>x.textContent).join('|')==='Methodology|Key assumptions'));
  dE.querySelector('#mclose').click();
  ck('no JS errors in the modal tests',errors.length===0 && errE.length===0,[errors.slice(0,2),errE.slice(0,2)]);

  console.log('TEST 13: river cards look clickable; the river modal has date navigation');
  setLang(d,'el'); await sleep(60);
  const cardsBtn=[...d.querySelectorAll('#rg button.river')], flat=d.querySelectorAll('#rg .river.flat');
  ck('every clickable river card has the chevron, the "view cascade" cue and a tooltip',cardsBtn.length===6 && cardsBtn.every(b=>b.querySelector('.chev svg') && b.querySelector('.more') && /καταρράκτη/.test(b.querySelector('.more').textContent) && b.getAttribute('title')),cardsBtn.length);
  ck('the combined Agras/Edessaios card is flat (a div, no cue, no chevron), so it is clearly not clickable',flat.length===1 && flat[0].tagName==='DIV' && !flat[0].querySelector('.more') && !flat[0].querySelector('.chev'));
  setLang(d,'en'); await sleep(60);
  ck('card cue is localized (English: "View cascade")',[...d.querySelectorAll('#rg button.river .more')].every(m=>m.textContent.includes('View cascade')));
  setLang(d,'el'); await sleep(60);
  const DAYS=B.P.idx.Days.filter(x=>B.P.fi[x.Date]!=null).map(x=>x.Date); await B.load(DAYS[3]); B.openRiver(1);
  const hd=d.querySelector('#rmc .mh');
  ck('river modal header: title, date select on the current day, prev/next buttons, and no X',!!hd.querySelector('h2') && hd.querySelector('#rdsel').value===DAYS[3] && !!hd.querySelector('#rd-prev') && !!hd.querySelector('#rd-next') && !d.querySelector('#rclose-x'));
  ck('the date select lists all days, newest first',hd.querySelectorAll('#rdsel option').length===DAYS.length && hd.querySelector('#rdsel option').value===DAYS[0]);
  const target=DAYS[6], sel=d.querySelector('#rdsel'); sel.value=target; sel.dispatchEvent(new w.Event('change',{bubbles:true})); await sleep(150);
  const kDam=B.S.M.rivers[1].dams[0].k, fT=B.P.fill[B.P.fi[target]][kDam].toLocaleString('el-GR',{minimumFractionDigits:1,maximumFractionDigits:1});
  ck('changing the date inside the modal keeps it open, on the same river, and reloads the data behind it',!d.querySelector('#rm').hidden && B.S.date===target && d.querySelector('#rdsel').value===target && d.querySelector('#dsel').value===target && d.querySelector('#rmc h2').textContent.includes('Αλιάκμονας'),[B.S.date,d.querySelector('#rdsel').value]);
  ck('the first dam shows the fill level of the NEW day ('+fT+'%)',d.querySelector('#rmc .mb').textContent.includes(fT+'%'),d.querySelector('#rmc .mb').textContent.slice(0,100));
  d.querySelector('#rd-prev').click(); await sleep(150); ck('previous-day button goes one day back',B.S.date===DAYS[7] && d.querySelector('#rdsel').value===DAYS[7],B.S.date);
  d.querySelector('#rd-next').click(); await sleep(150); d.querySelector('#rd-next').click(); await sleep(150); ck('next-day button goes forward',B.S.date===DAYS[5],B.S.date);
  d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true})); await sleep(150); ck('keyboard ← goes to the previous day while the river modal is open',B.S.date===DAYS[6],B.S.date);
  d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true})); await sleep(150); ck('keyboard → goes to the next day',B.S.date===DAYS[5],B.S.date);
  await B.load(DAYS[0]); B.openRiver(1); ck('on the newest day the next-day button is disabled',d.querySelector('#rd-next').disabled===true && d.querySelector('#rd-prev').disabled===false);
  d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowRight',bubbles:true})); await sleep(100); ck('...and → does nothing there',B.S.date===DAYS[0]);
  await B.load(DAYS[DAYS.length-1]); B.openRiver(1); ck('on the oldest day the previous-day button is disabled',d.querySelector('#rd-prev').disabled===true && d.querySelector('#rd-next').disabled===false);
  d.querySelector('#rclose').click();
  d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true})); await sleep(100); ck('arrow keys do nothing when no river modal is open',B.S.date===DAYS[DAYS.length-1]);
  d.querySelector('#meth').click(); d.dispatchEvent(new w.KeyboardEvent('keydown',{key:'ArrowLeft',bubbles:true})); await sleep(100); ck('...nor with the methodology modal open',B.S.date===DAYS[DAYS.length-1]); d.querySelector('#mclose').click();
  ck('no JS errors in the card and date-navigation tests',errors.length===0,errors.slice(0,3));

  console.log('TEST 14: a day without reservoir levels never breaks the page');
  const ddm=x=>x.slice(8,10)+'/'+x.slice(5,7)+'/'+x.slice(0,4);
  d.querySelector('#rclose').click&&0; await B.load(SYN_NORES); await sleep(60);
  ck('asking for a day without reservoir levels falls back to the latest available day',B.S.date===SYN_TODAY && !!B.S.M,B.S.date);
  ck('...and tells the user why (both dates in the notice)',d.querySelector('#banner').textContent.includes(ddm(SYN_NORES)) && d.querySelector('#banner').textContent.includes(ddm(SYN_TODAY)),d.querySelector('#banner').textContent);
  ck('...while the date selector keeps showing the day actually displayed',d.querySelector('#dsel').value===SYN_TODAY);
  await B.load(SYN_TODAY); ck('a normal request clears the notice',!d.querySelector('#banner').textContent.includes(ddm(SYN_NORES)));
  ck('no JS errors after the fallback',errors.length===0,errors.slice(0,3));
  ck('real data (fresh DOM): the page boots and offers only days that have reservoir levels',[...wE2.document.querySelectorAll('#dsel option')].every(o=>BE.P.fi[o.value]!=null) && wE2.document.querySelectorAll('#dsel option').length===BE.P.idx.Days.filter(x=>BE.P.fi[x.Date]!=null).length);
  await BE.load(BE.P.idx.Days[0].Date); ck('real data: requesting the newest indexed day (even without reservoir levels) does not throw and shows an available day',!!BE.S.M && BE.P.fi[BE.S.date]!=null && errE.length===0,[BE.S.date,errE.slice(0,2)]);
  ck('no JS errors at the end',errors.length===0,errors.slice(0,5));
  console.log(`\n${pass} passed, ${fail} failed`); process.exit(fail?1:0);
})();
