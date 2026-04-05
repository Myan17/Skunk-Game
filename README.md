# SKUNK Dice Game — Strategy, Simulation & Interactive Analysis

Welcome to a complete engineering and mathematical breakdown of the classic dice game "SKUNK." This project features a mathematically proven set of AI bots, automated tournament simulators, and a self-improving algorithm that successfully teaches itself how to beat its opponents over time. It has been built with an emphasis on code quality, testing reliability, and mathematical rigor.

---

## Table of Contents

1. [Game Context & Rules](#game-context--rules)
2. [Quick Start](#quick-start)
3. [Interactive Web Frontend](#interactive-web-frontend)
4. [Project Structure & Key Components](#project-structure--key-components)
5. [Professional Interview Summary](#professional-interview-summary)
6. [Bot Intelligence & Algorithms](#bot-intelligence--algorithms)
7. [Simulation & Testing Architecture](#simulation--testing-architecture)

---

## Game Context & Rules

**SKUNK** is a simple push-your-luck dice game played by two or more players aiming to be the first to reach a target score (usually 100 points). Players take turns rolling two standard six-sided dice, choosing to either accumulate their scores or voluntarily pass the dice to lock in their points.

| What You Roll | Result |
| :--- | :--- |
| **Safe Roll (No 1s)** | Add the sum of both dice to your current **turn total**. You can roll again or stop to bank the points. |
| **Single "1"** | Your turn ends immediately. You score **zero points** for this turn, but keep your previously banked score. |
| **Snake Eyes (Two 1s)** | Catastrophic failure. Your turn ends and **your entire banked game score resets to zero**. |

---

## Quick Start
Get the project running instantly on your local machine:

```bash
# Clone the repository and navigate into the project
cd UMFIA_project

# Launch the visual web dashboard
cd visualization
python3 -m http.server 8000
# Then visit http://localhost:8000 in your browser

# Or run the console-based tournament analysis
cd ..
python3 skunk_game.py

# Run the automated testing suite
python3 -m venv .venv
source .venv/bin/activate
pip install pytest
pytest test_skunk_game.py -v
```

---

## Interactive Web Frontend

Because data and mathematics are best understood visually, this repository includes a beautiful, responsive web-based visual dashboard for the SKUNK game. You can watch the bots play against each other in real-time, view the convergence of the self-learning bots, and interact with the game engine seamlessly directly from your browser. 

### View Online (GitHub Pages)
The web visualization is continually deployed to GitHub Pages via an automated Continuous Deployment action. Experience the live interactive visualization at:
**[https://Myan17.github.io/Skunk-Game/](https://Myan17.github.io/Skunk-Game/)**

---

## Project Structure & Key Components

Understanding the repository is simple. We separated the computational game logic side from the user interface presentation side:

```text
UMFIA_project/
├── skunk_game.py                  # Core backend engine & algorithmic bots
├── test_skunk_game.py             # 75-test automated reliability suite
├── README.md                      # Project documentation
├── .gitignore                     # Git configuration rules
├── .github/workflows/             
│   └── deploy-pages.yml           # CI/CD instructions for GitHub Actions
└── visualization/                 # Web Interface Codebase
    ├── index.html                 # Main dashboard structure
    ├── style.css                  # Custom styling (dark mode, animations, etc)
    ├── app.js                     # User interface logic & chart controllers
    ├── engine.js                  # JavaScript port of the Python game logic
    └── charts.js                  # Dedicated rendering scripts for graphs
```

### Key Technologies Inside the Components

**The Python Game Engine (`skunk_game.py`)**
This script acts as the brain. It holds the core `skunk_turn()` functional logic which processes mathematical outcomes for turns, calculates probability, runs full backend tournaments, and stores the decision-making rules for our 9 unique AI bots (such as the Mathematical Expected Value Bot, and the Adaptive Machine-Learning Bot). 

**The Automated Quality Assurance (`test_skunk_game.py`)**
A highly rigorous testing pipeline built utilizing `pytest`. We implemented "dependency injection" into our dice roller, meaning our test suite can feed *pre-determined* fake dice outputs to the system. This eliminates all randomness during testing, ensuring we can verify exactly how bots handle niche edge cases accurately every single time.

**The Web Dashboard (`visualization/`)**
A robust frontend built from scratch using HTML5 Canvas, modern CSS, and vanilla ES6 JavaScript that runs the game directly in your browser.

---

## Professional Interview Summary

*This section addresses core engineering and mathematical logic questions regarding the principles behind this project.*

### 1. Is there an optimal way to play this game?

**Yes, but "optimal" is highly dependent on your end goal.**

If your goal is to cleanly **maximize the points you receive on an isolated turn**, you must rely strictly on probability and expected value. According to statistical modeling, the mathematically optimal moment to stop rolling is dictated by a specific threshold formula. You should roll the dice only when `11 × (current turn points) + (total banked points) < 200`. Before passing this threshold, another roll will statistically net you higher rewards than what you risk losing. Our internal `ExpectedValueBot` abides ruthlessly by this mathematical rule.

However, if your goal is to actually **win the game against human or AI opponents**, you must embrace context-awareness rather than pure math. A strict statistical bot might play it incredibly safe, while the opponent next to them is only five points away from victory. Our `ContextAwareBot` evaluates the dynamic reality of the game state—drastically amplifying its aggressiveness if it is losing (risky catch-up) and tightening its conservatism if it is comfortably winning (lead protection). Through simulating over 10,000 algorithmic matchups, this Context-Aware strategy repeatedly dominated mathematically strict bots. 

### 2. Does the risk preference of your algorithm matter and should it be consistent throughout the rounds of play?

**Risk preference matters immensely, and it should absolutely never remain consistent.**

Remaining stubbornly consistent is empirically the fastest way to lose. As a player accrues a larger banked score over consecutive rounds, the real-world penalty of rolling "snake eyes" (a total wipe of the accrued bank) becomes substantially more severe.

- At the genesis of a game with $0 in the bank, you have virtually nothing to lose; your risk appetite should be immensely large to build momentum.
- Later in the session, holding 90 banked points, taking unnecessary risk is extremely dangerous; you should become heavily conservative.

All advanced bots in our engine (like `ContextAwareBot` and `ExpectedValueBot`) naturally step down their risk appetites proportionally to their accumulating scores. Furthermore, their risk scales alongside their opponents. If a trailing player notices the leader is preparing to win, extreme, inconsistent risk becomes the only logical, optimal path to victory.

### 3. If you believe there is an optimal way to play, do you think there is a solution to determine your probability of winning? Would it depend on how other players play their game?

**Yes, we accurately established our probability of winning through computational simulation (Monte Carlo analysis). This probability is entirely dependent on the specific play-style of your opponents.**

Because SKUNK involves multi-player variables, dynamic targets, and unpredictable behavior profiles, an exact "Golden Mathematical Equation" to guarantee victory likelihood does not easily exist. However, evaluating win probability is highly achievable by utilizing software to simulate 10,000 consecutive identical games in less than a second. 

Our analysis directly revealed:
- When competing against **aggressive opponents**, our optimal bots achieve their highest likelihoods of victory, effectively allowing aggressive players to constantly bankrupt themselves via over-rolling. 
- When competing against **quiet, conservative opponents**, our win probability noticeably compresses, as our bot must tactically output slow but steady growth to outpace them.

This proves that an objective "win probability percentage" operates less like a constant scientific law and more like a live, fluctuating baseline dictated entirely by the surrounding competitive environment. 

### 4. How would you consider writing a program to test out multiple skunk-bots with different logic playing against one another? Could you write a skunk-bot that improves its logic dynamically depending on its historical performance?

**Engineering the Testing Framework:**
To analyze differing logic bots effectively, we authored a `TournamentManager` infrastructure within Python. Our primary engineering concern was mathematical fairness; for instance, the player acting "first" possesses a minor mathematical advantage. To neutralize this, our framework uniformly rotates seating positions across the thousands of automated matches. Crucially, the simulator meticulously archives post-game performance metrics—calculating exact numeric win-rates, frequency of snake-eyes, and average margins of victory for downstream analysis.

**Dynamically Self-Improving Systems:**
Yes, we engineered an AI specifically to achieve this. The `AdaptiveBot` within our codebase operates on evolutionary machine-learning principles. The bot carries an internal "risk scaling multiplier." Following the conclusion of any game:
- **Victory:** It slightly reinforces its current multiplier, building confidence in what works.
- **Defeat:** It broadens its exploration, gently adjusting its multiplier to safely test new risk paradigms.
Left entirely to its own devices over thousands of iterations, this algorithm organically maps its optimal trajectory, independently arriving at the precise numerical strategy required to overcome whatever specific opponents it happens to be facing that day.

---

## Bot Intelligence & Algorithms

While the exact equations driving the logic can become highly complex, understanding our AI bots is relatively straightforward. Below is a layman review of the various logic profiles our system utilizes:

1. **Conservative Bot:** Highly risk-averse. Banks points extremely early in every turn. Rarely loses points, but consistently lags behind.
2. **Aggressive Bot:** Deeply risk-tolerant. Aims for huge point totals but regularly bankrupts itself with risky dice combinations. 
3. **Expected Value Bot (Level 1 Optimum):** Operates purely on the `(200 - Game Total) / 11` probability threshold formula. Clinically precise, but ignores its opponents. 
4. **Context Aware Bot (Level 2 Optimum):** Adjusts the mathematical formula on the fly depending on what human or bot opponents are currently doing with their scores. This is the top-performing intelligence in the suite.
5. **Monte Carlo Bot (Simulation Engine):** Refuses to predict. Instead, before making any decision, it runs 500 imaginary futures in a fraction of a second and chooses the action that worked best on average.
6. **Adaptive Bot (Machine Learning):** Starts with basic instructions but rewrites its own code regarding risk tolerance based entirely on whether it lost or won its last game. 

---

## Simulation & Testing Architecture

Code stability and rules-enforcement are paramount when evaluating mathematical strategy.

The included test suite (`test_skunk_game.py`) currently runs **75 unique programmatic assertions**. We do not leave dice probability up to chance during tests: we implemented structural code that allows us to inject precise dice outcomes directly into the engine, proving without a doubt that every variation of Snake Eyes, Single Ones, and Banked scores flawlessly functions exactly as documented under every fringe scenario.

This comprehensive testing base represents the foundation of the analytical data visualizer and ensures our math models are verified both theoretically, computationally, and visually.
