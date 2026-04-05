/* ═══════════════════════════════════════════════════════════════
   SKUNK DICE GAME — CORE ENGINE (JavaScript Port)
   Full port of skunk_game.py for browser-based simulation
   ═══════════════════════════════════════════════════════════════ */

// ═══ DICE MECHANICS ═══
function rollDice() {
    return [Math.floor(Math.random() * 6) + 1, Math.floor(Math.random() * 6) + 1];
}

function classifyRoll(d1, d2) {
    if (d1 === 1 && d2 === 1) return 'snake_eyes';
    if (d1 === 1 || d2 === 1) return 'single_one';
    return 'safe';
}

// ═══ BOT STRATEGIES ═══
class SkunkBot {
    constructor(name) {
        this.name = name;
        this.wins = 0;
        this.gamesPlayed = 0;
    }
    decide(turnTotal, gameTotal, target, allScores, playerIndex, rollNumber) {
        return false;
    }
    getColor() { return '#888'; }
}

class ConservativeBot extends SkunkBot {
    constructor(threshold = 15) {
        super(`Conservative(${threshold})`);
        this.threshold = threshold;
    }
    decide(turnTotal, gameTotal, target, allScores, playerIndex, rollNumber) {
        return turnTotal < this.threshold;
    }
    getColor() { return '#34d399'; }
}

class AggressiveBot extends SkunkBot {
    constructor(threshold = 30) {
        super(`Aggressive(${threshold})`);
        this.threshold = threshold;
    }
    decide(turnTotal, gameTotal, target, allScores, playerIndex, rollNumber) {
        return turnTotal < this.threshold;
    }
    getColor() { return '#f43f5e'; }
}

class ExpectedValueBot extends SkunkBot {
    constructor() {
        super('ExpectedValue');
    }
    decide(turnTotal, gameTotal, target, allScores, playerIndex, rollNumber) {
        return 11 * turnTotal + gameTotal < 200;
    }
    getColor() { return '#22d3ee'; }
}

class ContextAwareBot extends SkunkBot {
    constructor() {
        super('ContextAware');
    }
    decide(turnTotal, gameTotal, target, allScores, playerIndex, rollNumber) {
        const myScore = gameTotal;
        const potentialScore = gameTotal + turnTotal;
        const otherScores = allScores.filter((_, i) => i !== playerIndex);
        const maxOther = otherScores.length > 0 ? Math.max(...otherScores) : 0;

        let evThreshold = Math.max(0, (200 - gameTotal) / 11);
        let threshold = evThreshold;

        if (maxOther >= target * 0.85) {
            let urgency = (maxOther - target * 0.85) / (target * 0.15);
            urgency = Math.min(urgency, 1.0);
            threshold += urgency * 15;
        }

        if (myScore > maxOther + 20) {
            threshold = Math.max(threshold - 5, 8);
        }

        if (maxOther >= target) {
            if (potentialScore <= maxOther) return true;
            else threshold = Math.max(threshold, 10);
        }

        if (potentialScore >= target) return false;

        const distanceToTarget = target - myScore;
        if (distanceToTarget <= 25 && turnTotal >= distanceToTarget) return false;

        return turnTotal < threshold;
    }
    getColor() { return '#8b5cf6'; }
}

class FixedRollBot extends SkunkBot {
    constructor(numRolls = 3) {
        super(`FixedRoll(${numRolls})`);
        this.numRolls = numRolls;
    }
    decide(turnTotal, gameTotal, target, allScores, playerIndex, rollNumber) {
        if (gameTotal + turnTotal >= target) return false;
        return rollNumber < this.numRolls;
    }
    getColor() { return '#fbbf24'; }
}

class RandomBot extends SkunkBot {
    constructor(rollProb = 0.6) {
        super(`Random(${Math.round(rollProb * 100)}%)`);
        this.rollProb = rollProb;
    }
    decide(turnTotal, gameTotal, target, allScores, playerIndex, rollNumber) {
        if (gameTotal + turnTotal >= target) return false;
        return Math.random() < this.rollProb;
    }
    getColor() { return '#f97316'; }
}

class AdaptiveBot extends SkunkBot {
    constructor(initialRisk = 1.0, learningRate = 0.05) {
        super(`Adaptive(r=${initialRisk.toFixed(2)})`);
        this.riskFactor = initialRisk;
        this.learningRate = learningRate;
        this.riskHistory = [initialRisk];
        this.recentWins = [];
        this.windowSize = 50;
        this.bestRisk = initialRisk;
        this.bestWinRate = 0.0;
        this.generation = 0;
    }

    decide(turnTotal, gameTotal, target, allScores, playerIndex, rollNumber) {
        const otherScores = allScores.filter((_, i) => i !== playerIndex);
        const maxOther = otherScores.length > 0 ? Math.max(...otherScores) : 0;
        const evThreshold = Math.max(0, (200 - gameTotal) / 11) * this.riskFactor;

        if (gameTotal + turnTotal >= target) return false;
        if (maxOther >= target && gameTotal + turnTotal <= maxOther) return true;

        return turnTotal < evThreshold;
    }

    recordResult(won) {
        this.recentWins.push(won ? 1 : 0);
        if (this.recentWins.length > this.windowSize) this.recentWins.shift();

        const currentWinRate = this.recentWins.reduce((a, b) => a + b, 0) / this.recentWins.length;

        if (currentWinRate > this.bestWinRate && this.recentWins.length >= 20) {
            this.bestWinRate = currentWinRate;
            this.bestRisk = this.riskFactor;
        }

        this.generation++;

        if (won) {
            this.riskFactor += gaussianRandom() * 0.02;
        } else {
            const perturbation = gaussianRandom() * this.learningRate;
            const pullToBest = (this.bestRisk - this.riskFactor) * 0.1;
            this.riskFactor += perturbation + pullToBest;
        }

        this.riskFactor = Math.max(0.3, Math.min(2.5, this.riskFactor));
        this.riskHistory.push(this.riskFactor);
        this.name = `Adaptive(r=${this.riskFactor.toFixed(2)},gen=${this.generation})`;
    }

    getColor() { return '#ec4899'; }
}

// ═══ UTILITY ═══
function gaussianRandom() {
    let u = 0, v = 0;
    while (u === 0) u = Math.random();
    while (v === 0) v = Math.random();
    return Math.sqrt(-2.0 * Math.log(u)) * Math.cos(2.0 * Math.PI * v);
}

// ═══ CORE TURN FUNCTION ═══
function skunkTurn(target, scores, playerIndex, strategy) {
    scores = [...scores];
    const gameTotal = scores[playerIndex];
    let turnTotal = 0;
    let rollNumber = 0;

    while (true) {
        rollNumber++;

        const shouldRoll = strategy.decide(
            turnTotal, gameTotal, target, scores, playerIndex, rollNumber
        );

        if (!shouldRoll) {
            scores[playerIndex] = gameTotal + turnTotal;
            return { scores, outcome: 'bank', turnTotal, rolls: rollNumber - 1 };
        }

        const [d1, d2] = rollDice();
        const outcome = classifyRoll(d1, d2);

        if (outcome === 'snake_eyes') {
            scores[playerIndex] = 0;
            return { scores, outcome: 'snake_eyes', turnTotal: 0, rolls: rollNumber };
        }

        if (outcome === 'single_one') {
            scores[playerIndex] = gameTotal;
            return { scores, outcome: 'single_one', turnTotal: 0, rolls: rollNumber };
        }

        turnTotal += d1 + d2;
    }
}

// ═══ GAME ENGINE ═══
function playGame(bots, target = 100) {
    const n = bots.length;
    let scores = new Array(n).fill(0);
    let gameOver = false;
    let targetReachedBy = -1;

    while (true) {
        for (let i = 0; i < n; i++) {
            if (gameOver && i <= targetReachedBy) continue;

            const result = skunkTurn(target, scores, i, bots[i]);
            scores = result.scores;

            if (scores[i] >= target && !gameOver) {
                gameOver = true;
                targetReachedBy = i;
            }
        }

        if (gameOver) break;
    }

    let winner = 0;
    for (let i = 1; i < n; i++) {
        if (scores[i] > scores[winner]) winner = i;
    }

    return { winner, scores };
}

// ═══ BOT FACTORY ═══
function createBot(type) {
    switch (type) {
        case 'conservative-12': return new ConservativeBot(12);
        case 'conservative-15': return new ConservativeBot(15);
        case 'conservative-18': return new ConservativeBot(18);
        case 'aggressive-28': return new AggressiveBot(28);
        case 'ev': return new ExpectedValueBot();
        case 'context': return new ContextAwareBot();
        case 'fixed-3': return new FixedRollBot(3);
        case 'random-65': return new RandomBot(0.65);
        default: return new ConservativeBot(15);
    }
}

// ═══ TOURNAMENT ═══
function runTournamentBatch(botTypes, target, batchSize) {
    const bots = botTypes.map(t => createBot(t));
    const n = bots.length;
    const wins = new Array(n).fill(0);
    const totalScores = new Array(n).fill(0);

    for (let g = 0; g < batchSize; g++) {
        const rotation = g % n;
        const rotated = [...bots.slice(rotation), ...bots.slice(0, rotation)];
        const rotatedMap = [...Array(n).keys()].map(i => (i + rotation) % n);
        const reverseMap = new Array(n);
        for (let i = 0; i < n; i++) reverseMap[rotatedMap[i]] = i;

        const result = playGame(rotated, target);
        const winnerOriginal = rotatedMap[result.winner];
        wins[winnerOriginal]++;

        for (let i = 0; i < n; i++) {
            totalScores[rotatedMap[i]] += result.scores[i];
        }
    }

    return {
        wins,
        totalScores,
        bots: bots.map(b => ({ name: b.name, color: b.getColor() }))
    };
}

// ═══ ADAPTIVE LEARNING ═══
function runAdaptiveBatch(initialRisk, learningRate, opponentType, batchSize) {
    const adaptive = new AdaptiveBot(initialRisk, learningRate);
    const opponent = createBot(opponentType);
    
    const riskHistory = [adaptive.riskFactor];
    const winRateHistory = [];
    let runningWins = 0;

    for (let g = 0; g < batchSize; g++) {
        const bots = g % 2 === 0 ? [adaptive, opponent] : [opponent, adaptive];
        const adaptiveIdx = g % 2 === 0 ? 0 : 1;
        
        const result = playGame(bots, 100);
        const won = result.winner === adaptiveIdx;
        
        adaptive.recordResult(won);
        riskHistory.push(adaptive.riskFactor);

        if (won) runningWins++;
        if ((g + 1) % 10 === 0) {
            winRateHistory.push(runningWins / (g + 1));
        }
    }

    return {
        riskHistory,
        winRateHistory,
        finalRisk: adaptive.riskFactor,
        bestRisk: adaptive.bestRisk,
        bestWinRate: adaptive.bestWinRate,
        generation: adaptive.generation,
        totalWinRate: runningWins / batchSize
    };
}
