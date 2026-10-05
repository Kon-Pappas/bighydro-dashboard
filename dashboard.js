let rawData = [];
let currentLang = 'en'; 
let totalsChartInstance = null;

const CASCADE_ORDER = [
    { id: "Kremasta", nameEn: "Kremasta", nameGr: "Κρεμαστά", sys: "Acheloos", color: "#3b82f6" },     
    { id: "Kastraki", nameEn: "Kastraki", nameGr: "Καστράκι", sys: "Acheloos", color: "#3b82f6" },
    { id: "Stratos1", nameEn: "Stratos 1", nameGr: "Στράτος 1", sys: "Acheloos", color: "#3b82f6", boundary: true }, 
    
    { id: "Ilarionas", nameEn: "Ilarionas", nameGr: "Ιλαρίωνας", sys: "Aliakmonas", color: "#06b6d4" },   
    { id: "Polyfyto", nameEn: "Polyfyto", nameGr: "Πολύφυτο", sys: "Aliakmonas", color: "#06b6d4" },
    { id: "Sfikia", nameEn: "Sfikia", nameGr: "Σφηκιά", sys: "Aliakmonas", color: "#06b6d4", pump: true },
    { id: "Asomata", nameEn: "Asomata", nameGr: "Ασώματα", sys: "Aliakmonas", color: "#06b6d4", boundary: true },   
    
    { id: "Thesavros", nameEn: "Thesavros", nameGr: "Θησαυρός", sys: "Nestos", color: "#10b981", pump: true },      
    { id: "Platanovrysi", nameEn: "Platanovrysi", nameGr: "Πλατανόβρυση", sys: "Nestos", color: "#10b981", boundary: true }, 
    
    { id: "PAoou", nameEn: "Aoou Springs", nameGr: "Πηγές Αώου", sys: "Arachthos", color: "#a855f7" },   
    { id: "Pournari1", nameEn: "Pournari 1", nameGr: "Πουρνάρι 1", sys: "Arachthos", color: "#a855f7" },
    { id: "Pournari2", nameEn: "Pournari 2", nameGr: "Πουρνάρι 2", sys: "Arachthos", color: "#a855f7", boundary: true }, 
    
    { id: "Agras", nameEn: "Agras", nameGr: "Άγρας", sys: "Edessaios", color: "#f97316" },          
    { id: "Edessaios", nameEn: "Edessaios", nameGr: "Εδεσσαίος", sys: "Edessaios", color: "#f97316", boundary: true }, 
    
    { id: "Ladonas", nameEn: "Ladonas", nameGr: "Λάδωνας", sys: "Peloponnese", color: "#eab308", boundary: true },      
    
    { id: "Plastiras", nameEn: "Plastiras", nameGr: "Πλαστήρας", sys: "Tavropos", color: "#6366f1" }     
];

// Φυσική ιεραρχία ποταμών (Upstream -> Downstream) με Χωρητικότητες (hm³) και Ισχύ (MW)
const RIVER_SYSTEMS = [
    {
        key: "Acheloos",
        nameEn: "Acheloos River Cascade",
        nameGr: "Υδατικό Σύστημα Αχελώου",
        color: "#3b82f6",
        units: [
            { id: "Kremasta", nameEn: "Kremasta", nameGr: "Κρεμαστά", cap: 2805.0, mw: 437.2 },
            { id: "Kastraki", nameEn: "Kastraki", nameGr: "Καστράκι", cap: 53.0, mw: 320.0 },
            { id: "Stratos1", nameEn: "Stratos 1", nameGr: "Στράτος 1", cap: 11.0, mw: 150.0 }
        ]
    },
    {
        key: "Aliakmonas",
        nameEn: "Aliakmonas River Cascade (incl. Pumping)",
        nameGr: "Υδατικό Σύστημα Αλιάκμονα (με Αντλησιοταμίευση)",
        color: "#06b6d4",
        units: [
            { id: "Ilarionas", nameEn: "Ilarionas", nameGr: "Ιλαρίωνας", cap: 412.0, mw: 153.0 },
            { id: "Polyfyto", nameEn: "Polyfyto", nameGr: "Πολύφυτο", cap: 1020.0, mw: 375.0 },
            { id: "Sfikia", nameEn: "Sfikia (Pump)", nameGr: "Σφηκιά (Αντλησιοταμίευση)", cap: 16.0, mw: 315.0, pump: true },
            { id: "Asomata", nameEn: "Asomata", nameGr: "Ασώματα", cap: 10.0, mw: 108.0 }
        ]
    },
    {
        key: "Nestos",
        nameEn: "Nestos River Cascade (incl. Pumping)",
        nameGr: "Υδατικό Σύστημα Νέστου (με Αντλησιοταμίευση)",
        color: "#10b981",
        units: [
            { id: "Thesavros", nameEn: "Thesavros (Pump)", nameGr: "Θησαυρός (Αντλησιοταμίευση)", cap: 570.0, mw: 384.0, pump: true },
            { id: "Platanovrysi", nameEn: "Platanovrysi", nameGr: "Πλατανόβρυση", cap: 12.0, mw: 116.0 }
        ]
    },
    {
        key: "Arachthos",
        nameEn: "Arachthos & Aoou Cascade",
        nameGr: "Υδατικό Σύστημα Άραχθου & Αώου",
        color: "#a855f7",
        units: [
            { id: "PAoou", nameEn: "Aoou Springs", nameGr: "Πηγές Αώου", cap: 145.0, mw: 210.0 },
            { id: "Pournari1", nameEn: "Pournari 1", nameGr: "Πουρνάρι 1", cap: 303.0, mw: 300.0 },
            { id: "Pournari2", nameEn: "Pournari 2", nameGr: "Πουρνάρι II", cap: 3.6, mw: 34.0 }
        ]
    }
];

const SYSTEM_GROUPS = [
    { key: "Acheloos", nameEn: "Acheloos", nameGr: "Αχελώος", color: "#3b82f6" },
    { key: "Aliakmonas", nameEn: "Aliakmonas", nameGr: "Αλιάκμονας", color: "#06b6d4" },
    { key: "Nestos", nameEn: "Nestos", nameGr: "Νέστος", color: "#10b981" },
    { key: "Arachthos", nameEn: "Arachthos & Aoou", nameGr: "Άραχθος & Αώος", color: "#a855f7" },
    { key: "Edessaios", nameEn: "Edessaios / Voras", nameGr: "Εδεσσαίος / Βόρας", color: "#f97316" },
    { key: "Peloponnese", nameEn: "Peloponnese", nameGr: "Πελοπόννησος", color: "#eab308" },
    { key: "Tavropos", nameEn: "Tavropos (Plastiras)", nameGr: "Ταυρωπός (Πλαστήρας)", color: "#6366f1" }
];

const i18n = {
    en: {
        title: "Greek Hydro, Pump & Reservoir Analytics",
        dateLabel: "Date:",
        tabTotals: "Daily Overview (ISP vs SCADA)",
        tabPump: "Pump & River Cascades",
        totalsChartTitle: "Daily Generation: ISP vs SCADA",
        totalsChartSub: "Units dynamically sorted by River Cascade",
        labelTotalISP: "TOTAL ISP (MWH)",
        labelTotalSCADA: "TOTAL SCADA (MWH)",
        legendCascadesTitle: "RIVER CASCADES",
        legendDataTypeTitle: "DATA TYPE",
        legendTypeISP: "ISP (Solid)",
        legendTypeSCADA: "SCADA (Striped)",
        cascadeTitle: "River Cascades & Pumping Topology",
        cascadeSub: "Upstream to Downstream flow, reservoir filling rates, volumes and generation",
        capacityLabel: "Capacity",
        powerLabel: "Max Power",
        fillingLabel: "Filling Rate",
        genLabel: "Daily Gen"
    },
    el: {
        title: "Greek Hydro, Pump & Reservoir Analytics",
        dateLabel: "Ημερομηνία:",
        tabTotals: "Ημερήσια Επισκόπηση (ISP vs SCADA)",
        tabPump: "Αντλησιοταμίευση & Υδατικά Συστήματα",
        totalsChartTitle: "Ημερήσια Παραγωγή: Πρόγραμμα vs Πραγματικό",
        totalsChartSub: "Ταξινόμηση μονάδων ανά Υδατικό Σύστημα",
        labelTotalISP: "ΣΥΝΟΛΟ ISP (MWH)",
        labelTotalSCADA: "ΣΥΝΟΛΟ SCADA (MWH)",
        legendCascadesTitle: "ΥΔΑΤΙΚΑ ΣΥΣΤΗΜΑΤΑ",
        legendDataTypeTitle: "ΤΥΠΟΣ ΔΕΔΟΜΕΝΩΝ",
        legendTypeISP: "Πρόγραμμα (Συμπαγές)",
        legendTypeSCADA: "Πραγματικό (Ριγέ)",
        cascadeTitle: "Υδατικά Συστήματα & Τοπολογία Αντλησιοταμίευσης",
        cascadeSub: "Ροή από τα ψηλότερα προς τα χαμηλότερα, ποσοστά πλήρωσης και ημερήσια παραγωγή",
        capacityLabel: "Χωρητικότητα",
        powerLabel: "Μέγ. Ισχύς",
        fillingLabel: "Πλήρωση",
        genLabel: "Ημ. Παραγωγή"
    }
};

function setLang(lang) {
    currentLang = lang;
    const t = i18n[lang];
    document.getElementById('pageTitle').innerText = t.title;
    document.getElementById('mainTitle').innerText = t.title;
    document.getElementById('dateLabel').innerText = t.dateLabel;
    document.getElementById('tabBtnTotals').innerText = t.tabTotals;
    document.getElementById('tabBtnPump').innerText = t.tabPump;
    document.getElementById('labelTotalISP').innerText = t.labelTotalISP;
    document.getElementById('labelTotalSCADA').innerText = t.labelTotalSCADA;
    document.getElementById('legendCascadesTitle').innerText = t.legendCascadesTitle;
    document.getElementById('legendDataTypeTitle').innerText = t.legendDataTypeTitle;
    document.getElementById('legendTypeISP').innerText = t.legendTypeISP;
    document.getElementById('legendTypeSCADA').innerText = t.legendTypeSCADA;
    document.getElementById('cascadeTitle').innerText = t.cascadeTitle;
    document.getElementById('cascadeSub').innerText = t.cascadeSub;
    
    document.getElementById('btnGr').className = lang === 'el' ? "flex-1 md:flex-none flex items-center justify-center px-4 rounded bg-indigo-500 text-white transition" : "flex-1 md:flex-none flex items-center justify-center px-4 rounded text-slate-400 hover:text-white transition";
    document.getElementById('btnEn').className = lang === 'en' ? "flex-1 md:flex-none flex items-center justify-center px-4 rounded bg-indigo-500 text-white transition" : "flex-1 md:flex-none flex items-center justify-center px-4 rounded text-slate-400 hover:text-white transition";
    
    populateLegend();
    if (rawData.length > 0) {
        renderCharts();
        renderRiverCascades();
    }
}

function populateLegend() {
    const listEl = document.getElementById('legendCascadesList');
    listEl.innerHTML = '';
    SYSTEM_GROUPS.forEach(sys => {
        const name = currentLang === 'el' ? sys.nameGr : sys.nameEn;
        listEl.insertAdjacentHTML('beforeend', `
            <div class="flex items-center gap-2">
                <div class="w-3 h-3 rounded-sm" style="background-color: ${sys.color};"></div>
                <span class="text-xs text-slate-300 font-medium">${name}</span>
            </div>
        `);
    });
}

const verticalDividersPlugin = {
    id: 'verticalDividers',
    afterDraw(chart) {
        const { ctx, chartArea: { top, bottom }, scales: { x } } = chart;
        ctx.save();
        ctx.strokeStyle = 'rgba(148, 163, 184, 0.3)';
        ctx.lineWidth = 1;
        ctx.setLineDash([4, 4]);

        CASCADE_ORDER.forEach((unit, index) => {
            if (unit.boundary && index < CASCADE_ORDER.length - 1) {
                const xPos1 = x.getPixelForValue(index);
                const xPos2 = x.getPixelForValue(index + 1);
                const xMid = (xPos1 + xPos2) / 2;
                ctx.beginPath();
                ctx.moveTo(xMid, top);
                ctx.lineTo(xMid, bottom);
                ctx.stroke();
            }
        });
        ctx.restore();
    }
};

function renderCharts() {
    if (rawData.length === 0) return;
    Chart.defaults.color = '#94a3b8';
    Chart.defaults.borderColor = '#334155';

    const selectedDate = document.getElementById('dateSelect').value;
    const dayData = rawData.find(row => row.Date === selectedDate);
    
    if (dayData) {
        let grandTotalISP = 0;
        let grandTotalSCADA = 0;

        const labels = CASCADE_ORDER.map(u => currentLang === 'el' ? u.nameGr : u.nameEn);
        const ispData = [];
        const scadaData = [];
        const ispColors = [];
        const scadaPatterns = [];

        CASCADE_ORDER.forEach(unit => {
            const sumISP = dayData.Hourly.reduce((sum, h) => sum + (h[`ISP_${unit.id}`] || 0), 0);
            const sumSCADA = dayData.Hourly.reduce((sum, h) => sum + (h[`SCADA_${unit.id}`] || 0), 0);
            
            grandTotalISP += sumISP;
            grandTotalSCADA += sumSCADA;

            ispData.push(sumISP);
            scadaData.push(sumSCADA);
            ispColors.push(unit.color);
            scadaPatterns.push(pattern.draw('diagonal', unit.color));
        });

        document.getElementById('valTotalISP').innerText = Math.round(grandTotalISP).toLocaleString('el-GR');
        document.getElementById('valTotalSCADA').innerText = Math.round(grandTotalSCADA).toLocaleString('el-GR');

        if (totalsChartInstance) totalsChartInstance.destroy();
        const ctxTotals = document.getElementById('totalsChart').getContext('2d');
        totalsChartInstance = new Chart(ctxTotals, {
            type: 'bar',
            data: {
                labels: labels,
                datasets: [
                    { label: 'ISP', data: ispData, backgroundColor: ispColors, borderColor: 'transparent', borderWidth: 0, borderRadius: 2 },
                    { label: 'SCADA', data: scadaData, backgroundColor: scadaPatterns, borderColor: ispColors, borderWidth: 1, borderRadius: 2 }
                ]
            },
            options: { 
                responsive: true, 
                maintainAspectRatio: false, 
                plugins: { datalabels: { display: false }, legend: { display: false } }, 
                scales: { 
                    x: { grid: { display: false } }, 
                    y: { 
                        grid: { 
                            color: ctx => ctx.tick.value === 0 ? 'rgba(255, 255, 255, 0.6)' : '#334155', 
                            lineWidth: ctx => ctx.tick.value === 0 ? 2 : 1,
                            borderDash: [4, 4] 
                        } 
                    } 
                } 
            },
            plugins: [verticalDividersPlugin]
        });
    }
}

// Render 2nd Tab: River Cascades & Pumping Topology
function renderRiverCascades() {
    if (rawData.length === 0) return;
    const selectedDate = document.getElementById('dateSelect').value;
    const dayData = rawData.find(row => row.Date === selectedDate);
    if (!dayData) return;

    const container = document.getElementById('riverCascadesContainer');
    container.innerHTML = '';

    RIVER_SYSTEMS.forEach(sys => {
        const sysName = currentLang === 'el' ? sys.nameGr : sys.nameEn;
        
        // Calculate river system totals
        let totalGenSCADA = 0;
        sys.units.forEach(u => {
            const sum = dayData.Hourly.reduce((acc, h) => acc + (h[`SCADA_${u.id}`] || 0), 0);
            totalGenSCADA += sum;
        });

        let unitsHtml = '';
        sys.units.forEach((u, idx) => {
            const uName = currentLang === 'el' ? u.nameGr : u.nameEn;
            const sumGen = dayData.Hourly.reduce((acc, h) => acc + (h[`SCADA_${u.id}`] || 0), 0);
            
            // Get filling rate if available in JSON reservoir data
            let fillRate = null;
            let fillPctStr = "N/A";
            if (dayData.Reservoir && dayData.Reservoir.Units && dayData.Reservoir.Units[u.id] !== undefined) {
                fillRate = dayData.Reservoir.Units[u.id];
                fillPctStr = (fillRate * 100).toFixed(1) + "%";
            }

            // Visual scaling for volume bar (Ensuring small reservoirs have a min height, giants are scaled)
            // Min height 30px, max height 120px proportional to log or visual clamp
            const barHeightPx = Math.max(35, Math.min(120, Math.sqrt(u.cap) * 2));
            const fillWidthPct = fillRate !== null ? Math.min(100, Math.max(5, fillRate * 100)) : 0;

            unitsHtml += `
                <div class="bg-slate-900/80 border border-slate-700/60 rounded-xl p-4 flex flex-col md:flex-row items-start md:items-center justify-between gap-4 relative">
                    <!-- Unit Info -->
                    <div class="flex items-center gap-3 w-full md:w-1/3">
                        <div class="w-2 h-10 rounded-full" style="background-color: ${sys.color};"></div>
                        <div>
                            <div class="flex items-center gap-2">
                                <h4 class="text-white font-bold text-sm">${uName}</h4>
                                ${u.pump ? '<span class="bg-purple-500/20 text-purple-300 text-[10px] font-bold px-2 py-0.5 rounded border border-purple-500/30">PUMP / PSH</span>' : ''}
                            </div>
                            <p class="text-xs text-slate-400 mt-0.5">${i18n[currentLang].powerLabel}: <span class="text-slate-200 font-semibold">${u.mw} MW</span> | ${i18n[currentLang].capacityLabel}: <span class="text-slate-200 font-semibold">${u.cap} hm³</span></p>
                        </div>
                    </div>

                    <!-- Reservoir Filling Bar (Visual Scale) -->
                    <div class="w-full md:w-1/3 flex flex-col gap-1">
                        <div class="flex justify-between text-[11px] text-slate-300 font-medium">
                            <span>${i18n[currentLang].fillingLabel}: <strong class="text-cyan-400">${fillPctStr}</strong></span>
                            <span class="text-slate-500">Upstream → Downstream</span>
                        </div>
                        <div class="w-full bg-slate-800 rounded-lg p-1 border border-slate-700/80 relative overflow-hidden" style="height: 28px;">
                            <div class="bg-gradient-to-r from-blue-600 to-cyan-500 h-full rounded transition-all duration-500 flex items-center justify-end pr-2" style="width: ${fillWidthPct}%;">
                                <span class="text-[10px] font-bold text-white drop-shadow">${fillRate !== null ? fillPctStr : ''}</span>
                            </div>
                        </div>
                    </div>

                    <!-- Daily Generation & Flow Arrow -->
                    <div class="w-full md:w-auto flex items-center justify-between md:justify-end gap-6">
                        <div class="text-right">
                            <span class="text-[10px] text-slate-400 uppercase tracking-wider block">${i18n[currentLang].genLabel}</span>
                            <span class="text-sm font-mono font-bold text-emerald-400">${Math.round(sumGen).toLocaleString('el-GR')} MWh</span>
                        </div>
                    </div>
                </div>

                ${idx < sys.units.length - 1 ? `
                    <div class="flex justify-center my-1">
                        <div class="flex items-center gap-1 text-cyan-400/70 text-xs font-bold bg-slate-800/60 px-3 py-1 rounded-full border border-slate-700/50">
                            <span>↓ Water Flow / Release</span>
                        </div>
                    </div>
                ` : `
                    <div class="flex justify-center my-1">
                        <div class="flex items-center gap-1 text-slate-500 text-xs font-medium bg-slate-900/40 px-3 py-0.5 rounded-full">
                            <span>🌊 Outflow to Sea / Final Basin</span>
                        </div>
                    </div>
                `}
            `;
        });

        container.insertAdjacentHTML('beforeend', `
            <div class="bg-slate-800/60 border border-slate-700 rounded-2xl p-5 shadow-lg space-y-4">
                <div class="flex flex-col md:flex-row justify-between items-start md:items-center border-b border-slate-700/60 pb-3 gap-2">
                    <div class="flex items-center gap-3">
                        <div class="w-4 h-4 rounded-md" style="background-color: ${sys.color};"></div>
                        <h3 class="text-base font-bold text-white tracking-wide">${sysName}</h3>
                    </div>
                    <div class="text-xs bg-slate-900/80 px-3 py-1.5 rounded-lg border border-slate-700 text-slate-300 font-medium">
                        Total System Generation: <strong class="text-emerald-400 font-mono">${Math.round(totalGenSCADA).toLocaleString('el-GR')} MWh</strong>
                    </div>
                </div>
                <div class="space-y-2 pt-2">
                    ${unitsHtml}
                </div>
            </div>
        `);
    });
}

function animateStep(stepNum, nextAction) {
    const row = document.getElementById(`loadRow${stepNum}`);
    const bar = document.getElementById(`loadBar${stepNum}`);
    const pct = document.getElementById(`loadPct${stepNum}`);
    
    if (row) row.classList.remove('opacity-0');
    setTimeout(() => {
        if (bar) bar.style.width = '100%';
        let start = 0;
        const interval = setInterval(() => {
            start += 15; 
            if (start >= 100) {
                start = 100;
                clearInterval(interval);
                if (pct) pct.innerHTML = `<svg class="w-3.5 h-3.5 text-emerald-400 inline" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="3" d="M5 13l4 4L19 7" /></svg>`;
                if (bar) bar.classList.replace('bg-blue-500', 'bg-emerald-500') || bar.classList.replace('bg-purple-500', 'bg-emerald-500');
            } else {
                if (pct) pct.innerText = start + '%';
            }
        }, 30);
        setTimeout(() => { if (nextAction) nextAction(); }, 400);
    }, 50);
}

window.addEventListener('load', () => {
    setTimeout(() => {
        animateStep(1, async () => {
            try {
                const response = await fetch('data/hydro_data.json');
                if (!response.ok) throw new Error("JSON file not found.");
                rawData = await response.json();
                
                animateStep(2, () => {
                    const dates = [...new Set(rawData.map(row => row.Date))].sort().reverse();
                    document.getElementById('dateSelect').innerHTML = dates.map(d => `<option value="${d}">${d}</option>`).join('');
                    if (dates.length > 0) document.getElementById('dateSelect').value = dates[0];
                    
                    animateStep(3, () => {
                        Chart.register(ChartDataLabels);
                        setLang('en'); 
                        
                        const finalRow = document.getElementById('loadRow_FINAL');
                        const spinner = document.getElementById('mainSpinner');
                        if (spinner) spinner.classList.add('hidden');
                        if (finalRow) {
                            finalRow.classList.remove('opacity-0', 'translate-y-2');
                            finalRow.classList.add('opacity-100', 'translate-y-0');
                        }
                        
                        setTimeout(() => {
                            const overlay = document.getElementById('loading-overlay');
                            if (overlay) {
                                overlay.classList.add('opacity-0');
                                setTimeout(() => overlay.style.display = 'none', 500); 
                            }
                        }, 800);
                    });
                });
            } catch (error) {
                console.error("Error fetching local data:", error);
                const overlay = document.getElementById('loading-overlay');
                if (overlay) overlay.style.display = 'none'; 
            }
        });
    }, 200);
});
