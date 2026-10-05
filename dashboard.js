let rawData = [];
let currentLang = 'en'; 
let totalsChartInstance = null;

const CASCADE_ORDER = [
    { id: "Kremasta", nameEn: "Kremasta", nameGr: "Κρεμαστά", sys: "Acheloos", color: "#3b82f6" },     
    { id: "Kastraki", nameEn: "Kastraki", nameGr: "Καστράκι", sys: "Acheloos", color: "#3b82f6" },
    { id: "Stratos1", nameEn: "Stratos 1", nameGr: "Στράτος 1", sys: "Acheloos", color: "#3b82f6", boundary: true }, 
    
    { id: "Ilarionas", nameEn: "Ilarionas", nameGr: "Ιλαρίωνας", sys: "Aliakmonas", color: "#06b6d4" },   
    { id: "Polyfyto", nameEn: "Polyfyto", nameGr: "Πολύφυτο", sys: "Aliakmonas", color: "#06b6d4" },
    { id: "Sfikia", nameEn: "Sfikia", nameGr: "Σφηκιά", sys: "Aliakmonas", color: "#06b6d4" },
    { id: "Asomata", nameEn: "Asomata", nameGr: "Ασώματα", sys: "Aliakmonas", color: "#06b6d4", boundary: true },   
    
    { id: "Thesavros", nameEn: "Thesavros", nameGr: "Θησαυρός", sys: "Nestos", color: "#10b981" },      
    { id: "Platanovrysi", nameEn: "Platanovrysi", nameGr: "Πλατανόβρυση", sys: "Nestos", color: "#10b981", boundary: true }, 
    
    { id: "PAoou", nameEn: "Aoou Springs", nameGr: "Πηγές Αώου", sys: "Arachthos", color: "#a855f7" },   
    { id: "Pournari1", nameEn: "Pournari 1", nameGr: "Πουρνάρι 1", sys: "Arachthos", color: "#a855f7" },
    { id: "Pournari2", nameEn: "Pournari 2", nameGr: "Πουρνάρι 2", sys: "Arachthos", color: "#a855f7", boundary: true }, 
    
    { id: "Agras", nameEn: "Agras", nameGr: "Άγρας", sys: "Edessaios", color: "#f97316" },          
    { id: "Edessaios", nameEn: "Edessaios", nameGr: "Εδεσσαίος", sys: "Edessaios", color: "#f97316", boundary: true }, 
    
    { id: "Ladonas", nameEn: "Ladonas", nameGr: "Λάδωνας", sys: "Peloponnese", color: "#eab308", boundary: true },      
    
    { id: "Plastiras", nameEn: "Plastiras", nameGr: "Πλαστήρας", sys: "Tavropos", color: "#6366f1" }     
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
        totalsChartTitle: "Daily Generation: ISP vs SCADA",
        totalsChartSub: "Units dynamically sorted by River Cascade",
        labelTotalISP: "TOTAL ISP (MWH)",
        labelTotalSCADA: "TOTAL SCADA (MWH)",
        legendCascadesTitle: "RIVER CASCADES",
        legendDataTypeTitle: "DATA TYPE",
        legendTypeISP: "ISP (Solid)",
        legendTypeSCADA: "SCADA (Striped)"
    },
    el: {
        title: "Greek Hydro, Pump & Reservoir Analytics",
        dateLabel: "Ημερομηνία:",
        tabTotals: "Ημερήσια Επισκόπηση (ISP vs SCADA)",
        totalsChartTitle: "Ημερήσια Παραγωγή: Πρόγραμμα vs Πραγματικό",
        totalsChartSub: "Ταξινόμηση μονάδων ανά Υδατικό Σύστημα",
        labelTotalISP: "ΣΥΝΟΛΟ ISP (MWH)",
        labelTotalSCADA: "ΣΥΝΟΛΟ SCADA (MWH)",
        legendCascadesTitle: "ΥΔΑΤΙΚΑ ΣΥΣΤΗΜΑΤΑ",
        legendDataTypeTitle: "ΤΥΠΟΣ ΔΕΔΟΜΕΝΩΝ",
        legendTypeISP: "Πρόγραμμα (Συμπαγές)",
        legendTypeSCADA: "Πραγματικό (Ριγέ)"
    }
};

function setLang(lang) {
    currentLang = lang;
    const t = i18n[lang];
    document.getElementById('pageTitle').innerText = t.title;
    document.getElementById('mainTitle').innerText = t.title;
    document.getElementById('dateLabel').innerText = t.dateLabel;
    document.getElementById('tabBtnTotals').innerText = t.tabTotals;
    document.getElementById('totalsChartTitle').innerText = t.totalsChartTitle;
    document.getElementById('totalsChartSub').innerText = t.totalsChartSub;
    document.getElementById('labelTotalISP').innerText = t.labelTotalISP;
    document.getElementById('labelTotalSCADA').innerText = t.labelTotalSCADA;
    document.getElementById('legendCascadesTitle').innerText = t.legendCascadesTitle;
    document.getElementById('legendDataTypeTitle').innerText = t.legendDataTypeTitle;
    document.getElementById('legendTypeISP').innerText = t.legendTypeISP;
    document.getElementById('legendTypeSCADA').innerText = t.legendTypeSCADA;
    
    document.getElementById('btnGr').className = lang === 'el' ? "flex-1 md:flex-none flex items-center justify-center px-4 rounded bg-indigo-500 text-white transition" : "flex-1 md:flex-none flex items-center justify-center px-4 rounded text-slate-400 hover:text-white transition";
    document.getElementById('btnEn').className = lang === 'en' ? "flex-1 md:flex-none flex items-center justify-center px-4 rounded bg-indigo-500 text-white transition" : "flex-1 md:flex-none flex items-center justify-center px-4 rounded text-slate-400 hover:text-white transition";
    
    populateLegend();
    if (rawData.length > 0) renderCharts();
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
                    { 
                        label: 'ISP', 
                        data: ispData, 
                        backgroundColor: ispColors, 
                        borderColor: 'transparent',
                        borderWidth: 0, 
                        borderRadius: 2 
                    },
                    { 
                        label: 'SCADA', 
                        data: scadaData, 
                        backgroundColor: scadaPatterns, 
                        borderColor: ispColors, 
                        borderWidth: 1, 
                        borderRadius: 2 
                    }
                ]
            },
            options: { 
                responsive: true, 
                maintainAspectRatio: false, 
                plugins: { 
                    datalabels: { display: false },
                    legend: { display: false } 
                }, 
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