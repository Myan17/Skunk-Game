/* ═══════════════════════════════════════════════════════════════
   SKUNK DICE GAME — APP CONTROLLER
   UI interactions, dice demo, battle orchestration
   ═══════════════════════════════════════════════════════════════ */

// ═══ INITIALIZATION ═══
document.addEventListener('DOMContentLoaded', () => {
    initFloatingDice();
    initNavScrollSpy();
    drawHeatmap('heatmap-canvas');
    setupHeatmapTooltip();
    populateThresholdTable();
    animateOnScroll();
});

// ═══ FLOATING DICE BACKGROUND ═══
function initFloatingDice() {
    const container = document.getElementById('floating-dice-container');
    if (!container) return;
    const diceEmojis = ['⚀', '⚁', '⚂', '⚃', '⚄', '⚅'];

    for (let i = 0; i < 25; i++) {
        const die = document.createElement('span');
        die.className = 'float-die';
        die.textContent = diceEmojis[Math.floor(Math.random() * 6)];
        die.style.left = `${Math.random() * 100}%`;
        die.style.fontSize = `${1.5 + Math.random() * 2}rem`;
        die.style.animationDuration = `${15 + Math.random() * 20}s`;
        die.style.animationDelay = `${-Math.random() * 30}s`;
        container.appendChild(die);
    }
}

// ═══ NAVIGATION SCROLL SPY ═══
function initNavScrollSpy() {
    const links = document.querySelectorAll('.nav-link');
    const sections = ['hero', 'rules', 'math', 'simulator', 'adaptive'];

    window.addEventListener('scroll', () => {
        const scrollY = window.scrollY + 100;

        for (let i = sections.length - 1; i >= 0; i--) {
            const section = document.getElementById(sections[i]);
            if (section && scrollY >= section.offsetTop) {
                links.forEach(l => l.classList.remove('active'));
                const activeLink = document.querySelector(`.nav-link[data-section="${sections[i]}"]`);
                if (activeLink) activeLink.classList.add('active');
                break;
            }
        }
    });
}

// ═══ SCROLL-TRIGGERED ANIMATIONS ═══
function animateOnScroll() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.classList.add('animate-in');
            }
        });
    }, { threshold: 0.1 });

    document.querySelectorAll('.rule-card, .formula-card, .explain-card, .heatmap-container, .threshold-table-wrapper').forEach(el => {
        observer.observe(el);
    });
}

// ═══ DICE DEMO ═══
let demoTurnTotal = 0;
let demoBanked = 0;
let demoRolling = false;

function rollDemoHandler() {
    if (demoRolling) return;
    demoRolling = true;

    const die1El = document.getElementById('demo-die-1');
    const die2El = document.getElementById('demo-die-2');
    const resultEl = document.getElementById('demo-result');

    // Reset visual state
    die1El.className = 'demo-die rolling';
    die2El.className = 'demo-die rolling';
    resultEl.textContent = '';
    resultEl.className = 'demo-result';

    // Animate rolling
    let rollCount = 0;
    const rollInterval = setInterval(() => {
        die1El.textContent = Math.floor(Math.random() * 6) + 1;
        die2El.textContent = Math.floor(Math.random() * 6) + 1;
        rollCount++;
        if (rollCount > 8) {
            clearInterval(rollInterval);
            finishDemoRoll();
        }
    }, 60);
}

function finishDemoRoll() {
    const [d1, d2] = rollDice();
    const die1El = document.getElementById('demo-die-1');
    const die2El = document.getElementById('demo-die-2');
    const resultEl = document.getElementById('demo-result');
    const turnTotalEl = document.getElementById('demo-turn-total');

    die1El.textContent = d1;
    die2El.textContent = d2;
    die1El.classList.remove('rolling');
    die2El.classList.remove('rolling');

    const outcome = classifyRoll(d1, d2);

    if (outcome === 'snake_eyes') {
        die1El.className = 'demo-die danger-state';
        die2El.className = 'demo-die danger-state';
        resultEl.textContent = `💀 SNAKE EYES! Lost all ${demoBanked + demoTurnTotal} points!`;
        resultEl.className = 'demo-result snake-result';
        demoTurnTotal = 0;
        demoBanked = 0;
        document.getElementById('demo-banked').textContent = '0';
    } else if (outcome === 'single_one') {
        if (d1 === 1) {
            die1El.className = 'demo-die danger-state';
            die2El.className = 'demo-die safe';
        } else {
            die1El.className = 'demo-die safe';
            die2El.className = 'demo-die danger-state';
        }
        resultEl.textContent = `✗ Single 1! Lost ${demoTurnTotal} turn points.`;
        resultEl.className = 'demo-result bust-result';
        demoTurnTotal = 0;
    } else {
        die1El.className = 'demo-die safe';
        die2El.className = 'demo-die safe';
        const sum = d1 + d2;
        demoTurnTotal += sum;
        resultEl.textContent = `✓ Safe! +${sum}`;
        resultEl.className = 'demo-result safe-result';
    }

    turnTotalEl.textContent = demoTurnTotal;
    demoRolling = false;
}

function bankDemoHandler() {
    if (demoRolling) return;
    demoBanked += demoTurnTotal;
    const resultEl = document.getElementById('demo-result');
    resultEl.textContent = `💰 Banked ${demoTurnTotal} points!`;
    resultEl.className = 'demo-result safe-result';
    demoTurnTotal = 0;
    document.getElementById('demo-turn-total').textContent = '0';
    document.getElementById('demo-banked').textContent = demoBanked;
}

function resetDemoHandler() {
    demoTurnTotal = 0;
    demoBanked = 0;
    demoRolling = false;
    document.getElementById('demo-die-1').textContent = '?';
    document.getElementById('demo-die-1').className = 'demo-die';
    document.getElementById('demo-die-2').textContent = '?';
    document.getElementById('demo-die-2').className = 'demo-die';
    document.getElementById('demo-result').textContent = 'Roll the dice!';
    document.getElementById('demo-result').className = 'demo-result';
    document.getElementById('demo-turn-total').textContent = '0';
    document.getElementById('demo-banked').textContent = '0';
}

// ═══ THRESHOLD TABLE ═══
function populateThresholdTable() {
    const tbody = document.querySelector('#threshold-table tbody');
    if (!tbody) return;

    for (let gt = 0; gt <= 200; gt += 10) {
        const threshold = Math.max(0, (200 - gt) / 11);
        let interp, interpClass;
        if (threshold === 0) { interp = 'Too risky!'; interpClass = 'accent-rose'; }
        else if (threshold < 10) { interp = 'Very conservative'; interpClass = 'accent-amber'; }
        else if (threshold < 18) { interp = 'Moderate risk'; interpClass = 'accent-cyan'; }
        else { interp = 'Can be aggressive'; interpClass = 'accent-emerald'; }

        const row = document.createElement('tr');
        row.innerHTML = `
            <td><span class="threshold-value">${gt}</span></td>
            <td><span class="threshold-value">${threshold.toFixed(1)}</span></td>
            <td style="color: var(--${interpClass})">${interp}</td>
            <td>
                <div class="threshold-bar" style="width: ${(threshold / 18.2) * 100}%; background: var(--${interpClass})"></div>
            </td>
        `;
        tbody.appendChild(row);
    }
}

// ═══ BOT BATTLE ═══
let battleWorker = null;
let battleRunning = false;

function startBattle() {
    if (battleRunning) return;

    // Get selected bots
    const checkboxes = document.querySelectorAll('#bot-checkboxes input[type="checkbox"]:checked');
    const botTypes = Array.from(checkboxes).map(cb => cb.value);

    if (botTypes.length < 2) {
        alert('Please select at least 2 bots!');
        return;
    }

    const target = parseInt(document.getElementById('target-score').value) || 100;
    const numGames = parseInt(document.getElementById('num-games').value) || 2000;
    const speed = parseInt(document.getElementById('sim-speed').value);

    // Show results area
    document.getElementById('battle-results').style.display = 'block';
    document.getElementById('btn-battle').disabled = true;
    document.getElementById('btn-battle').textContent = '⏳ Simulating...';
    battleRunning = true;

    // Run in batches to not block UI
    const batchSize = speed === 0 ? numGames : (speed === 1 ? 200 : 20);
    const bots = botTypes.map(t => createBot(t));
    const n = bots.length;
    const cumulativeWins = new Array(n).fill(0);
    const winRateHistory = new Array(n).fill(null).map(() => []);
    let gamesPlayed = 0;

    function runBatch() {
        const thisGamesBatch = Math.min(batchSize, numGames - gamesPlayed);
        const result = runTournamentBatch(botTypes, target, thisGamesBatch);

        for (let i = 0; i < n; i++) {
            cumulativeWins[i] += result.wins[i];
        }
        gamesPlayed += thisGamesBatch;

        // Record history
        for (let i = 0; i < n; i++) {
            winRateHistory[i].push((cumulativeWins[i] / gamesPlayed) * 100);
        }

        // Update progress
        const pct = (gamesPlayed / numGames) * 100;
        document.getElementById('battle-progress').style.width = `${pct}%`;
        document.getElementById('progress-text').textContent = `${pct.toFixed(0)}%`;

        // Update charts
        const labels = bots.map(b => b.name);
        const colors = bots.map(b => b.getColor());
        drawWinRateChart('winrate-chart', winRateHistory, labels, colors);
        updateStandings(bots, cumulativeWins, gamesPlayed);

        if (gamesPlayed < numGames) {
            const delay = speed === 0 ? 0 : (speed === 1 ? 50 : 300);
            setTimeout(runBatch, delay);
        } else {
            battleRunning = false;
            document.getElementById('btn-battle').disabled = false;
            document.getElementById('btn-battle').textContent = '⚔️ Start Battle';
        }
    }

    runBatch();
}

function updateStandings(bots, wins, totalGames) {
    const standings = document.getElementById('standings');
    if (!standings) return;

    const sorted = bots.map((b, i) => ({
        name: b.name,
        color: b.getColor(),
        wins: wins[i],
        winRate: (wins[i] / totalGames) * 100
    })).sort((a, b) => b.winRate - a.winRate);

    const maxWinRate = sorted[0]?.winRate || 1;

    standings.innerHTML = sorted.map((bot, rank) => `
        <div class="standing-row">
            <span class="standing-rank">${rank === 0 ? '👑' : '#' + (rank + 1)}</span>
            <span class="standing-name" style="color: ${bot.color}">${bot.name}</span>
            <span class="standing-winrate">${bot.winRate.toFixed(1)}%</span>
            <div class="standing-bar-container">
                <div class="standing-bar" style="width: ${(bot.winRate / maxWinRate) * 100}%; background: ${bot.color}"></div>
            </div>
        </div>
    `).join('');
}

// ═══ ADAPTIVE LEARNING ═══
let adaptiveRunning = false;

function startAdaptive() {
    if (adaptiveRunning) return;
    adaptiveRunning = true;

    const initialRisk = parseFloat(document.getElementById('adapt-initial-risk').value) || 1.0;
    const learningRate = parseFloat(document.getElementById('adapt-learning-rate').value) || 0.08;
    const numGames = parseInt(document.getElementById('adapt-games').value) || 3000;
    const opponent = document.getElementById('adapt-opponent').value;

    document.getElementById('adaptive-results').style.display = 'block';
    document.getElementById('btn-adaptive').disabled = true;
    document.getElementById('btn-adaptive').textContent = '⏳ Training...';

    // Run in batches
    const adaptive = new AdaptiveBot(initialRisk, learningRate);
    const opp = createBot(opponent);
    const riskHistory = [adaptive.riskFactor];
    const winRateHistory = [];
    let runningWins = 0;
    let gamesPlayed = 0;
    const batchSize = 100;

    function trainBatch() {
        const thisBatch = Math.min(batchSize, numGames - gamesPlayed);

        for (let g = 0; g < thisBatch; g++) {
            const bots = gamesPlayed % 2 === 0 ? [adaptive, opp] : [opp, adaptive];
            const adaptiveIdx = gamesPlayed % 2 === 0 ? 0 : 1;

            const result = playGame(bots, 100);
            const won = result.winner === adaptiveIdx;
            adaptive.recordResult(won);
            riskHistory.push(adaptive.riskFactor);

            if (won) runningWins++;
            gamesPlayed++;

            if (gamesPlayed % 10 === 0) {
                winRateHistory.push(runningWins / gamesPlayed);
            }
        }

        // Update charts
        drawRiskChart('risk-chart', riskHistory);
        drawAdaptiveWinRateChart('adaptive-winrate-chart', winRateHistory);

        if (gamesPlayed < numGames) {
            setTimeout(trainBatch, 30);
        } else {
            // Show summary
            const totalWinRate = runningWins / numGames;
            document.getElementById('adaptive-summary').innerHTML = `
                <h4>Learning Complete!</h4>
                <div class="summary-grid">
                    <div class="summary-item">
                        <span class="summary-value">${adaptive.riskFactor.toFixed(3)}</span>
                        <span class="summary-label">Final Risk Factor</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-value">${adaptive.bestRisk.toFixed(3)}</span>
                        <span class="summary-label">Best Risk Factor</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-value">${(adaptive.bestWinRate * 100).toFixed(1)}%</span>
                        <span class="summary-label">Peak Win Rate</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-value">${(totalWinRate * 100).toFixed(1)}%</span>
                        <span class="summary-label">Overall Win Rate</span>
                    </div>
                    <div class="summary-item">
                        <span class="summary-value">${adaptive.generation}</span>
                        <span class="summary-label">Generations</span>
                    </div>
                </div>
            `;

            adaptiveRunning = false;
            document.getElementById('btn-adaptive').disabled = false;
            document.getElementById('btn-adaptive').textContent = '🧠 Start Learning';
        }
    }

    trainBatch();
}
