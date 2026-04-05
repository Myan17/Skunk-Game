/* ═══════════════════════════════════════════════════════════════
   SKUNK DICE GAME — CHART RENDERING
   Custom canvas-based charts (no dependencies)
   ═══════════════════════════════════════════════════════════════ */

const CHART_COLORS = [
    '#34d399', '#f43f5e', '#22d3ee', '#8b5cf6',
    '#fbbf24', '#f97316', '#ec4899', '#3b82f6'
];

// ═══ HEATMAP ═══
function drawHeatmap(canvasId) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;
    
    const displayW = 600;
    const displayH = 400;
    canvas.style.width = displayW + 'px';
    canvas.style.height = displayH + 'px';
    canvas.width = displayW * dpr;
    canvas.height = displayH * dpr;
    ctx.scale(dpr, dpr);
    
    const margin = { top: 30, right: 30, bottom: 45, left: 55 };
    const plotW = displayW - margin.left - margin.right;
    const plotH = displayH - margin.top - margin.bottom;

    // Range: game_total 0-200 (x), turn_total 0-30 (y)
    const maxG = 220;
    const maxT = 30;

    // Clear
    ctx.fillStyle = '#111118';
    ctx.fillRect(0, 0, displayW, displayH);

    // Draw cells
    const cellsX = 100;
    const cellsY = 60;
    const cellW = plotW / cellsX;
    const cellH = plotH / cellsY;

    for (let yi = 0; yi < cellsY; yi++) {
        for (let xi = 0; xi < cellsX; xi++) {
            const g = (xi / cellsX) * maxG;
            const t = ((cellsY - yi - 1) / cellsY) * maxT;
            const deltaE = (200 - 11 * t - g) / 36;

            const x = margin.left + xi * cellW;
            const y = margin.top + yi * cellH;

            if (deltaE > 0) {
                const intensity = Math.min(deltaE / 5, 1);
                const r = Math.round(20 + 30 * (1 - intensity));
                const green = Math.round(80 + 175 * intensity);
                const b = Math.round(60 + 100 * intensity);
                ctx.fillStyle = `rgb(${r}, ${green}, ${b})`;
            } else {
                const intensity = Math.min(Math.abs(deltaE) / 5, 1);
                const r = Math.round(80 + 175 * intensity);
                const green = Math.round(20 + 30 * (1 - intensity));
                const b = Math.round(30 + 40 * (1 - intensity));
                ctx.fillStyle = `rgb(${r}, ${green}, ${b})`;
            }

            ctx.fillRect(x, y, cellW + 0.5, cellH + 0.5);
        }
    }

    // Draw break-even line: 11*T + G = 200 → T = (200 - G) / 11
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.8)';
    ctx.lineWidth = 2;
    ctx.setLineDash([6, 4]);
    ctx.beginPath();
    for (let xi = 0; xi <= cellsX; xi++) {
        const g = (xi / cellsX) * maxG;
        const t = Math.max(0, (200 - g) / 11);
        const x = margin.left + xi * cellW;
        const y = margin.top + (1 - t / maxT) * plotH;
        if (y >= margin.top && y <= margin.top + plotH) {
            if (xi === 0 || (200 - ((xi - 1) / cellsX) * maxG) / 11 < 0) {
                ctx.moveTo(x, y);
            } else {
                ctx.lineTo(x, y);
            }
        }
    }
    ctx.stroke();
    ctx.setLineDash([]);

    // Add "ROLL" and "STOP" labels
    ctx.font = '700 16px Inter';
    ctx.fillStyle = 'rgba(52, 211, 153, 0.7)';
    ctx.fillText('ROLL', margin.left + plotW * 0.15, margin.top + plotH * 0.7);
    ctx.fillStyle = 'rgba(244, 63, 94, 0.7)';
    ctx.fillText('STOP', margin.left + plotW * 0.65, margin.top + plotH * 0.3);

    // Axes
    ctx.strokeStyle = 'rgba(255,255,255,0.15)';
    ctx.lineWidth = 1;

    // X axis labels
    ctx.fillStyle = '#5a5a70';
    ctx.font = '11px JetBrains Mono';
    ctx.textAlign = 'center';
    for (let g = 0; g <= maxG; g += 40) {
        const x = margin.left + (g / maxG) * plotW;
        ctx.fillText(g.toString(), x, displayH - margin.bottom + 18);
        ctx.strokeStyle = 'rgba(255,255,255,0.05)';
        ctx.beginPath();
        ctx.moveTo(x, margin.top);
        ctx.lineTo(x, margin.top + plotH);
        ctx.stroke();
    }

    // Y axis labels
    ctx.textAlign = 'right';
    for (let t = 0; t <= maxT; t += 5) {
        const y = margin.top + (1 - t / maxT) * plotH;
        ctx.fillText(t.toString(), margin.left - 8, y + 4);
        ctx.strokeStyle = 'rgba(255,255,255,0.05)';
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(margin.left + plotW, y);
        ctx.stroke();
    }

    // Axis titles
    ctx.fillStyle = '#9898aa';
    ctx.font = '500 12px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('Game Total (G)', margin.left + plotW / 2, displayH - 5);

    ctx.save();
    ctx.translate(15, margin.top + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText('Turn Total (T)', 0, 0);
    ctx.restore();

    // Store dimensions for tooltip
    canvas._chartMeta = { margin, plotW, plotH, maxG, maxT };
}

// Heatmap tooltip handler
function setupHeatmapTooltip() {
    const canvas = document.getElementById('heatmap-canvas');
    const tooltip = document.getElementById('heatmap-tooltip');
    if (!canvas || !tooltip) return;

    canvas.addEventListener('mousemove', (e) => {
        const rect = canvas.getBoundingClientRect();
        const x = e.clientX - rect.left;
        const y = e.clientY - rect.top;
        const meta = canvas._chartMeta;
        if (!meta) return;

        const plotX = x - meta.margin.left;
        const plotY = y - meta.margin.top;

        if (plotX < 0 || plotX > meta.plotW || plotY < 0 || plotY > meta.plotH) {
            tooltip.style.display = 'none';
            return;
        }

        const g = Math.round((plotX / meta.plotW) * meta.maxG);
        const t = Math.round((1 - plotY / meta.plotH) * meta.maxT);
        const deltaE = (200 - 11 * t - g) / 36;
        const action = deltaE > 0 ? '🟢 ROLL' : '🔴 STOP';

        tooltip.innerHTML = `G=${g} T=${t}<br>ΔE = ${deltaE.toFixed(2)}<br>${action}`;
        tooltip.style.display = 'block';
        tooltip.style.left = (x + 15) + 'px';
        tooltip.style.top = (y - 10) + 'px';
    });

    canvas.addEventListener('mouseleave', () => {
        tooltip.style.display = 'none';
    });
}

// ═══ WIN RATE LINE CHART ═══
function drawWinRateChart(canvasId, data, labels, colors) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    const displayW = canvas.parentElement.clientWidth - 48;
    const displayH = 350;
    canvas.style.width = displayW + 'px';
    canvas.style.height = displayH + 'px';
    canvas.width = displayW * dpr;
    canvas.height = displayH * dpr;
    ctx.scale(dpr, dpr);

    const margin = { top: 20, right: 20, bottom: 50, left: 50 };
    const plotW = displayW - margin.left - margin.right;
    const plotH = displayH - margin.top - margin.bottom;

    ctx.fillStyle = '#16161f';
    ctx.fillRect(0, 0, displayW, displayH);

    // Find max value
    let maxVal = 0;
    for (const series of data) {
        for (const v of series) maxVal = Math.max(maxVal, v);
    }
    maxVal = Math.ceil(maxVal / 10) * 10;
    if (maxVal === 0) maxVal = 100;

    // Grid
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#5a5a70';
    ctx.font = '10px JetBrains Mono';
    ctx.textAlign = 'right';

    for (let v = 0; v <= maxVal; v += Math.max(5, Math.round(maxVal / 6))) {
        const y = margin.top + plotH - (v / maxVal) * plotH;
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(margin.left + plotW, y);
        ctx.stroke();
        ctx.fillText(`${v}%`, margin.left - 6, y + 3);
    }

    // Draw lines
    for (let s = 0; s < data.length; s++) {
        const series = data[s];
        const n = series.length;
        if (n < 2) continue;

        ctx.strokeStyle = colors[s % colors.length];
        ctx.lineWidth = 2;
        ctx.globalAlpha = 0.85;
        ctx.beginPath();

        for (let i = 0; i < n; i++) {
            const x = margin.left + (i / (n - 1)) * plotW;
            const y = margin.top + plotH - (series[i] / maxVal) * plotH;
            if (i === 0) ctx.moveTo(x, y);
            else ctx.lineTo(x, y);
        }
        ctx.stroke();
        ctx.globalAlpha = 1;
    }

    // Legend
    const legendY = displayH - 12;
    ctx.font = '500 10px JetBrains Mono';
    ctx.textAlign = 'left';
    let legendX = margin.left;

    for (let s = 0; s < labels.length; s++) {
        ctx.fillStyle = colors[s % colors.length];
        ctx.fillRect(legendX, legendY - 6, 12, 3);
        ctx.fillText(labels[s], legendX + 16, legendY);
        legendX += ctx.measureText(labels[s]).width + 30;
    }

    // X axis label
    ctx.fillStyle = '#5a5a70';
    ctx.font = '10px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('Games Played', margin.left + plotW / 2, displayH - 28);
}

// ═══ RISK FACTOR CHART ═══
function drawRiskChart(canvasId, riskHistory) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    const displayW = canvas.parentElement.clientWidth - 48;
    const displayH = 300;
    canvas.style.width = displayW + 'px';
    canvas.style.height = displayH + 'px';
    canvas.width = displayW * dpr;
    canvas.height = displayH * dpr;
    ctx.scale(dpr, dpr);

    const margin = { top: 20, right: 20, bottom: 40, left: 50 };
    const plotW = displayW - margin.left - margin.right;
    const plotH = displayH - margin.top - margin.bottom;

    ctx.fillStyle = '#16161f';
    ctx.fillRect(0, 0, displayW, displayH);

    const minR = 0.2;
    const maxR = 2.6;

    // Grid
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#5a5a70';
    ctx.font = '10px JetBrains Mono';
    ctx.textAlign = 'right';

    for (let v = 0.5; v <= 2.5; v += 0.5) {
        const y = margin.top + plotH - ((v - minR) / (maxR - minR)) * plotH;
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(margin.left + plotW, y);
        ctx.stroke();
        ctx.fillText(v.toFixed(1), margin.left - 6, y + 3);
    }

    // Reference line at 1.0
    ctx.strokeStyle = 'rgba(251, 191, 36, 0.3)';
    ctx.lineWidth = 1;
    ctx.setLineDash([5, 3]);
    const refY = margin.top + plotH - ((1.0 - minR) / (maxR - minR)) * plotH;
    ctx.beginPath();
    ctx.moveTo(margin.left, refY);
    ctx.lineTo(margin.left + plotW, refY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw risk factor line
    const n = riskHistory.length;
    // Subsample if too many points
    const step = Math.max(1, Math.floor(n / 500));

    ctx.strokeStyle = '#ec4899';
    ctx.lineWidth = 1.5;
    ctx.globalAlpha = 0.9;
    ctx.beginPath();

    for (let i = 0; i < n; i += step) {
        const x = margin.left + (i / (n - 1)) * plotW;
        const y = margin.top + plotH - ((riskHistory[i] - minR) / (maxR - minR)) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Labels
    ctx.fillStyle = '#ec4899';
    ctx.font = '10px JetBrains Mono';
    ctx.textAlign = 'left';
    ctx.fillRect(margin.left + 5, margin.top + 5, 12, 3);
    ctx.fillText('Risk Factor', margin.left + 22, margin.top + 10);

    ctx.fillStyle = '#fbbf24';
    ctx.fillRect(margin.left + 120, margin.top + 5, 12, 3);
    ctx.fillText('Baseline (1.0)', margin.left + 137, margin.top + 10);

    ctx.fillStyle = '#5a5a70';
    ctx.font = '10px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('Generation', margin.left + plotW / 2, displayH - 8);
}

// ═══ ADAPTIVE WIN RATE CHART ═══
function drawAdaptiveWinRateChart(canvasId, winRateHistory) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const dpr = window.devicePixelRatio || 1;

    const displayW = canvas.parentElement.clientWidth - 48;
    const displayH = 300;
    canvas.style.width = displayW + 'px';
    canvas.style.height = displayH + 'px';
    canvas.width = displayW * dpr;
    canvas.height = displayH * dpr;
    ctx.scale(dpr, dpr);

    const margin = { top: 20, right: 20, bottom: 40, left: 50 };
    const plotW = displayW - margin.left - margin.right;
    const plotH = displayH - margin.top - margin.bottom;

    ctx.fillStyle = '#16161f';
    ctx.fillRect(0, 0, displayW, displayH);

    // Grid
    ctx.strokeStyle = 'rgba(255,255,255,0.05)';
    ctx.lineWidth = 1;
    ctx.fillStyle = '#5a5a70';
    ctx.font = '10px JetBrains Mono';
    ctx.textAlign = 'right';

    for (let v = 0; v <= 100; v += 10) {
        const y = margin.top + plotH - (v / 100) * plotH;
        ctx.beginPath();
        ctx.moveTo(margin.left, y);
        ctx.lineTo(margin.left + plotW, y);
        ctx.stroke();
        ctx.fillText(`${v}%`, margin.left - 6, y + 3);
    }

    // 50% reference
    ctx.strokeStyle = 'rgba(251, 191, 36, 0.3)';
    ctx.setLineDash([5, 3]);
    const refY = margin.top + plotH - 0.5 * plotH;
    ctx.beginPath();
    ctx.moveTo(margin.left, refY);
    ctx.lineTo(margin.left + plotW, refY);
    ctx.stroke();
    ctx.setLineDash([]);

    // Draw win rate
    const n = winRateHistory.length;
    if (n < 2) return;

    ctx.strokeStyle = '#22d3ee';
    ctx.lineWidth = 2;
    ctx.globalAlpha = 0.9;
    ctx.beginPath();

    for (let i = 0; i < n; i++) {
        const x = margin.left + (i / (n - 1)) * plotW;
        const y = margin.top + plotH - (winRateHistory[i]) * plotH;
        if (i === 0) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
    }
    ctx.stroke();
    ctx.globalAlpha = 1;

    // Label
    ctx.fillStyle = '#22d3ee';
    ctx.font = '10px JetBrains Mono';
    ctx.textAlign = 'left';
    ctx.fillRect(margin.left + 5, margin.top + 5, 12, 3);
    ctx.fillText('Cumulative Win Rate', margin.left + 22, margin.top + 10);

    ctx.fillStyle = '#fbbf24';
    ctx.fillRect(margin.left + 180, margin.top + 5, 12, 3);
    ctx.fillText('50% (random)', margin.left + 197, margin.top + 10);

    ctx.fillStyle = '#5a5a70';
    ctx.font = '10px Inter';
    ctx.textAlign = 'center';
    ctx.fillText('Games (×10)', margin.left + plotW / 2, displayH - 8);
}
