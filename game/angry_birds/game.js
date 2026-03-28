// ============================================================
//  愤怒的小鸟 — 纯 Canvas 2D 实现
// ============================================================

const canvas = document.getElementById('gameCanvas');
const ctx = canvas.getContext('2d');

// Canvas resolution
const W = 960;
const H = 600;
canvas.width = W;
canvas.height = H;

// ---- Constants ----
const GRAVITY = 0.35;
const FRICTION = 0.75;
const RESTITUTION = 0.4;
const GROUND_Y = H - 80;
const SLING_X = 155;
const SLING_Y = GROUND_Y - 80;
const MAX_PULL = 90;
const LAUNCH_POWER = 0.18;

// ---- Colors ----
const COLORS = {
    sky1: '#87CEEB',
    sky2: '#E0F0FF',
    ground: '#8B7355',
    grass: '#4CAF50',
    slingshot: '#5D4037',
    slingshotDark: '#3E2723',
    rubber: '#4E342E',
};

// ---- Block material configs ----
const MATERIAL = {
    wood:  { color: '#C8A04A', stroke: '#8B6914', hp: 80 },
    stone: { color: '#9E9E9E', stroke: '#616161', hp: 160 },
    ice:   { color: '#B3E5FC', stroke: '#4FC3F7', hp: 40 },
    glass: { color: '#E1F5FE', stroke: '#81D4FA', hp: 30 },
};

// ---- Game state ----
let gameState = 'start'; // start | aiming | flying | settling | levelComplete | gameOver
let score = 0;
let currentLevel = 0;
let birdsLeft = 0;
let currentBird = null;
let blocks = [];
let pigs = [];
let particles = [];
let trajectory = [];
let settleTimer = 0;

// ---- Mouse / Touch ----
let mouse = { x: 0, y: 0, down: false };

// ============================================================
//  Utility helpers
// ============================================================
function dist(x1, y1, x2, y2) {
    const dx = x2 - x1;
    const dy = y2 - y1;
    return Math.sqrt(dx * dx + dy * dy);
}

function clamp(v, lo, hi) {
    return Math.max(lo, Math.min(hi, v));
}

function rand(a, b) {
    return a + Math.random() * (b - a);
}

function randInt(a, b) {
    return Math.floor(rand(a, b + 1));
}

function lerp(a, b, t) {
    return a + (b - a) * t;
}

// ============================================================
//  Particle system
// ============================================================
function spawnParticles(x, y, color, count) {
    for (let i = 0; i < count; i++) {
        particles.push({
            x, y,
            vx: rand(-4, 4),
            vy: rand(-6, 0),
            life: rand(20, 50),
            maxLife: 50,
            size: rand(2, 6),
            color,
        });
    }
}

function spawnScorePopup(x, y, pts) {
    particles.push({
        x, y,
        vx: 0,
        vy: -1.5,
        life: 60,
        maxLife: 60,
        isText: true,
        text: '+' + pts,
        color: '#ffd700',
        size: 20,
    });
}

function updateParticles() {
    for (let i = particles.length - 1; i >= 0; i--) {
        const p = particles[i];
        p.x += p.vx;
        p.y += p.vy;
        if (!p.isText) {
            p.vy += 0.15;
        }
        p.life--;
        if (p.life <= 0) {
            particles.splice(i, 1);
        }
    }
}

function drawParticles() {
    for (const p of particles) {
        const alpha = clamp(p.life / p.maxLife, 0, 1);
        if (p.isText) {
            ctx.save();
            ctx.globalAlpha = alpha;
            ctx.fillStyle = p.color;
            ctx.font = `bold ${p.size}px sans-serif`;
            ctx.textAlign = 'center';
            ctx.fillText(p.text, p.x, p.y);
            ctx.restore();
        } else {
            ctx.save();
            ctx.globalAlpha = alpha;
            ctx.fillStyle = p.color;
            ctx.fillRect(p.x - p.size / 2, p.y - p.size / 2, p.size, p.size);
            ctx.restore();
        }
    }
}

// ============================================================
//  Game Object classes
// ============================================================

class Bird {
    constructor(x, y, color) {
        this.x = x;
        this.y = y;
        this.radius = 15;
        this.vx = 0;
        this.vy = 0;
        this.color = color || '#FF4444';
        this.launched = false;
        this.alive = true;
        this.grounded = false;
        this.groundTimer = 0;
        this.rotation = 0;
        this.trail = [];
    }

    update() {
        if (!this.launched) return;

        this.vy += GRAVITY;
        this.x += this.vx;
        this.y += this.vy;
        this.rotation += this.vx * 0.04;

        // Trail
        if (this.trail.length === 0 || dist(this.x, this.y, this.trail[this.trail.length - 1].x, this.trail[this.trail.length - 1].y) > 12) {
            this.trail.push({ x: this.x, y: this.y });
            if (this.trail.length > 60) this.trail.shift();
        }

        // Ground collision
        if (this.y + this.radius > GROUND_Y) {
            this.y = GROUND_Y - this.radius;
            this.vy *= -RESTITUTION;
            this.vx *= FRICTION;
            if (Math.abs(this.vy) < 1) {
                this.vy = 0;
                this.grounded = true;
            }
        }

        // Walls
        if (this.x - this.radius < 0) {
            this.x = this.radius;
            this.vx *= -0.5;
        }
        if (this.x + this.radius > W) {
            this.x = W - this.radius;
            this.vx *= -0.5;
        }

        // Remove if off screen or stopped
        if (this.grounded) {
            this.groundTimer++;
            this.vx *= 0.96;
        }
        if (this.groundTimer > 120 || this.y > H + 50) {
            this.alive = false;
        }
    }

    draw() {
        // Trail
        for (let i = 0; i < this.trail.length; i++) {
            const alpha = (i / this.trail.length) * 0.3;
            ctx.beginPath();
            ctx.arc(this.trail[i].x, this.trail[i].y, 3, 0, Math.PI * 2);
            ctx.fillStyle = `rgba(255, 255, 255, ${alpha})`;
            ctx.fill();
        }

        ctx.save();
        ctx.translate(this.x, this.y);
        ctx.rotate(this.rotation);

        // Body
        const r = this.radius;
        ctx.beginPath();
        ctx.arc(0, 0, r, 0, Math.PI * 2);
        ctx.fillStyle = this.color;
        ctx.fill();
        ctx.strokeStyle = darkenColor(this.color, 40);
        ctx.lineWidth = 2;
        ctx.stroke();

        // Belly
        ctx.beginPath();
        ctx.arc(2, 4, r * 0.5, 0, Math.PI * 2);
        ctx.fillStyle = lightenColor(this.color, 60);
        ctx.fill();

        // Eyes
        const eyeX = -3;
        const eyeY = -4;
        // Eye whites
        ctx.beginPath();
        ctx.ellipse(eyeX - 3, eyeY, 5, 6, 0, 0, Math.PI * 2);
        ctx.fillStyle = 'white';
        ctx.fill();
        ctx.beginPath();
        ctx.ellipse(eyeX + 5, eyeY, 5, 6, 0, 0, Math.PI * 2);
        ctx.fillStyle = 'white';
        ctx.fill();
        // Pupils
        ctx.beginPath();
        ctx.arc(eyeX - 1, eyeY, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = '#111';
        ctx.fill();
        ctx.beginPath();
        ctx.arc(eyeX + 7, eyeY, 2.5, 0, Math.PI * 2);
        ctx.fillStyle = '#111';
        ctx.fill();

        // Eyebrows (angry)
        ctx.strokeStyle = '#111';
        ctx.lineWidth = 2.5;
        ctx.beginPath();
        ctx.moveTo(eyeX - 7, eyeY - 7);
        ctx.lineTo(eyeX + 1, eyeY - 4);
        ctx.stroke();
        ctx.beginPath();
        ctx.moveTo(eyeX + 11, eyeY - 7);
        ctx.lineTo(eyeX + 3, eyeY - 4);
        ctx.stroke();

        // Beak
        ctx.beginPath();
        ctx.moveTo(4, 2);
        ctx.lineTo(14, 2);
        ctx.lineTo(4, 8);
        ctx.closePath();
        ctx.fillStyle = '#FF9800';
        ctx.fill();

        ctx.restore();
    }
}

class Block {
    constructor(x, y, w, h, material) {
        this.x = x;
        this.y = y;
        this.w = w;
        this.h = h;
        this.material = material;
        this.vx = 0;
        this.vy = 0;
        this.hp = MATERIAL[material].hp;
        this.maxHp = this.hp;
        this.alive = true;
        this.rotation = 0;
        this.angularVel = 0;
    }

    update() {
        this.vy += GRAVITY * 0.5;
        this.x += this.vx;
        this.y += this.vy;
        this.vx *= 0.99;

        // Ground
        if (this.y + this.h / 2 > GROUND_Y) {
            this.y = GROUND_Y - this.h / 2;
            this.vy *= -RESTITUTION * 0.5;
            this.vx *= FRICTION;
            if (Math.abs(this.vy) < 0.5) this.vy = 0;
        }

        // Walls
        if (this.x - this.w / 2 < 0) {
            this.x = this.w / 2;
            this.vx *= -0.5;
        }
        if (this.x + this.w / 2 > W) {
            this.x = W - this.w / 2;
            this.vx *= -0.5;
        }

        // Break check
        if (this.hp <= 0) {
            this.alive = false;
            spawnParticles(this.x, this.y, MATERIAL[this.material].color, 12);
        }
    }

    draw() {
        const hpRatio = this.hp / this.maxHp;
        const mat = MATERIAL[this.material];

        ctx.save();

        // Block body
        ctx.fillStyle = mat.color;
        ctx.globalAlpha = 0.5 + hpRatio * 0.5;
        ctx.fillRect(this.x - this.w / 2, this.y - this.h / 2, this.w, this.h);

        // Stroke
        ctx.strokeStyle = mat.stroke;
        ctx.lineWidth = 2;
        ctx.strokeRect(this.x - this.w / 2, this.y - this.h / 2, this.w, this.h);

        // Damage cracks
        if (hpRatio < 0.7) {
            ctx.strokeStyle = 'rgba(0,0,0,0.3)';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(this.x - this.w * 0.3, this.y - this.h * 0.4);
            ctx.lineTo(this.x + this.w * 0.1, this.y + this.h * 0.3);
            ctx.stroke();
        }
        if (hpRatio < 0.4) {
            ctx.beginPath();
            ctx.moveTo(this.x + this.w * 0.2, this.y - this.h * 0.3);
            ctx.lineTo(this.x - this.w * 0.2, this.y + this.h * 0.4);
            ctx.stroke();
        }

        // Material detail
        if (this.material === 'wood') {
            ctx.strokeStyle = 'rgba(139,105,20,0.3)';
            ctx.lineWidth = 1;
            for (let i = -2; i <= 2; i++) {
                ctx.beginPath();
                ctx.moveTo(this.x - this.w / 2 + 4, this.y + i * (this.h / 6));
                ctx.lineTo(this.x + this.w / 2 - 4, this.y + i * (this.h / 6));
                ctx.stroke();
            }
        } else if (this.material === 'ice') {
            ctx.fillStyle = 'rgba(255,255,255,0.3)';
            ctx.fillRect(this.x - this.w / 2 + 3, this.y - this.h / 2 + 3, this.w * 0.4, this.h * 0.3);
        }

        ctx.restore();
    }

    takeDamage(amount) {
        this.hp -= amount;
        if (this.hp <= 0) {
            this.alive = false;
            spawnParticles(this.x, this.y, MATERIAL[this.material].color, 12);
        }
    }
}

class Pig {
    constructor(x, y, radius) {
        this.x = x;
        this.y = y;
        this.radius = radius || 18;
        this.vx = 0;
        this.vy = 0;
        this.hp = 60;
        this.maxHp = 60;
        this.alive = true;
        this.expression = 'normal'; // normal | worried | dead
        this.hurtTimer = 0;
    }

    update() {
        this.vy += GRAVITY * 0.5;
        this.x += this.vx;
        this.y += this.vy;
        this.vx *= 0.99;

        // Ground
        if (this.y + this.radius > GROUND_Y) {
            this.y = GROUND_Y - this.radius;
            this.vy *= -RESTITUTION * 0.5;
            this.vx *= FRICTION;
            if (Math.abs(this.vy) < 0.5) this.vy = 0;
        }

        // Walls
        if (this.x - this.radius < 0) {
            this.x = this.radius;
            this.vx *= -0.5;
        }
        if (this.x + this.radius > W) {
            this.x = W - this.radius;
            this.vx *= -0.5;
        }

        if (this.hurtTimer > 0) this.hurtTimer--;

        // Expression
        const hpRatio = this.hp / this.maxHp;
        if (hpRatio < 0.3) this.expression = 'worried';
        if (this.hp <= 0) {
            this.expression = 'dead';
            this.alive = false;
            spawnParticles(this.x, this.y, '#81C784', 15);
        }
    }

    draw() {
        ctx.save();
        ctx.translate(this.x, this.y);

        const r = this.radius;

        // Body
        ctx.beginPath();
        ctx.arc(0, 0, r, 0, Math.PI * 2);
        ctx.fillStyle = '#66BB6A';
        ctx.fill();
        ctx.strokeStyle = '#388E3C';
        ctx.lineWidth = 2;
        ctx.stroke();

        // Ears
        ctx.beginPath();
        ctx.ellipse(-r * 0.6, -r * 0.7, r * 0.25, r * 0.3, -0.3, 0, Math.PI * 2);
        ctx.fillStyle = '#81C784';
        ctx.fill();
        ctx.stroke();
        ctx.beginPath();
        ctx.ellipse(r * 0.6, -r * 0.7, r * 0.25, r * 0.3, 0.3, 0, Math.PI * 2);
        ctx.fillStyle = '#81C784';
        ctx.fill();
        ctx.stroke();

        // Snout
        ctx.beginPath();
        ctx.ellipse(0, 3, r * 0.45, r * 0.35, 0, 0, Math.PI * 2);
        ctx.fillStyle = '#A5D6A7';
        ctx.fill();
        ctx.strokeStyle = '#388E3C';
        ctx.lineWidth = 1;
        ctx.stroke();

        // Nostrils
        ctx.beginPath();
        ctx.ellipse(-4, 3, 2.5, 3, 0, 0, Math.PI * 2);
        ctx.fillStyle = '#388E3C';
        ctx.fill();
        ctx.beginPath();
        ctx.ellipse(4, 3, 2.5, 3, 0, 0, Math.PI * 2);
        ctx.fillStyle = '#388E3C';
        ctx.fill();

        // Eyes
        if (this.expression === 'dead') {
            // X eyes
            ctx.strokeStyle = '#333';
            ctx.lineWidth = 2;
            [-6, 6].forEach(ex => {
                ctx.beginPath();
                ctx.moveTo(ex - 3, -5);
                ctx.lineTo(ex + 3, -1);
                ctx.stroke();
                ctx.beginPath();
                ctx.moveTo(ex + 3, -5);
                ctx.lineTo(ex - 3, -1);
                ctx.stroke();
            });
        } else {
            // Normal eyes
            ctx.beginPath();
            ctx.arc(-6, -4, 4, 0, Math.PI * 2);
            ctx.fillStyle = 'white';
            ctx.fill();
            ctx.beginPath();
            ctx.arc(6, -4, 4, 0, Math.PI * 2);
            ctx.fillStyle = 'white';
            ctx.fill();

            const pupilOffset = this.expression === 'worried' ? 0 : 1;
            ctx.beginPath();
            ctx.arc(-5 + pupilOffset, -4, 2, 0, Math.PI * 2);
            ctx.fillStyle = '#333';
            ctx.fill();
            ctx.beginPath();
            ctx.arc(7 + pupilOffset, -4, 2, 0, Math.PI * 2);
            ctx.fillStyle = '#333';
            ctx.fill();

            if (this.expression === 'worried') {
                // Worried mouth
                ctx.beginPath();
                ctx.arc(0, 10, 4, 0, Math.PI, true);
                ctx.strokeStyle = '#333';
                ctx.lineWidth = 1.5;
                ctx.stroke();
            }
        }

        // Damage indicator
        if (this.hurtTimer > 0) {
            ctx.globalAlpha = this.hurtTimer / 15;
            ctx.beginPath();
            ctx.arc(0, 0, r + 3, 0, Math.PI * 2);
            ctx.strokeStyle = '#ff0';
            ctx.lineWidth = 2;
            ctx.stroke();
        }

        ctx.restore();
    }

    takeDamage(amount) {
        this.hp -= amount;
        this.hurtTimer = 15;
    }
}

// ============================================================
//  Color helpers
// ============================================================
function darkenColor(hex, amount) {
    const r = Math.max(0, parseInt(hex.slice(1, 3), 16) - amount);
    const g = Math.max(0, parseInt(hex.slice(3, 5), 16) - amount);
    const b = Math.max(0, parseInt(hex.slice(5, 7), 16) - amount);
    return `rgb(${r},${g},${b})`;
}

function lightenColor(hex, amount) {
    const r = Math.min(255, parseInt(hex.slice(1, 3), 16) + amount);
    const g = Math.min(255, parseInt(hex.slice(3, 5), 16) + amount);
    const b = Math.min(255, parseInt(hex.slice(5, 7), 16) + amount);
    return `rgb(${r},${g},${b})`;
}

// ============================================================
//  Level definitions
// ============================================================
const LEVELS = [
    // Level 1 — simple intro
    {
        birds: 3,
        birdColors: ['#FF4444', '#FF4444', '#FF4444'],
        build: () => {
            const bx = 600;
            blocks.push(new Block(bx, GROUND_Y - 15, 25, 30, 'wood'));
            blocks.push(new Block(bx + 60, GROUND_Y - 15, 25, 30, 'wood'));
            blocks.push(new Block(bx + 30, GROUND_Y - 45, 80, 15, 'wood'));
            pigs.push(new Pig(bx + 30, GROUND_Y - 18));
        }
    },
    // Level 2 — stacked
    {
        birds: 3,
        birdColors: ['#FF4444', '#2196F3', '#FF4444'],
        build: () => {
            const bx = 580;
            // Bottom supports
            blocks.push(new Block(bx, GROUND_Y - 20, 20, 40, 'wood'));
            blocks.push(new Block(bx + 80, GROUND_Y - 20, 20, 40, 'wood'));
            // Platform
            blocks.push(new Block(bx + 40, GROUND_Y - 50, 110, 15, 'wood'));
            // Top supports
            blocks.push(new Block(bx + 20, GROUND_Y - 72, 15, 30, 'ice'));
            blocks.push(new Block(bx + 60, GROUND_Y - 72, 15, 30, 'ice'));
            // Top platform
            blocks.push(new Block(bx + 40, GROUND_Y - 95, 70, 12, 'wood'));
            // Pigs
            pigs.push(new Pig(bx + 40, GROUND_Y - 18));
            pigs.push(new Pig(bx + 40, GROUND_Y - 63));
        }
    },
    // Level 3 — stone fortress
    {
        birds: 4,
        birdColors: ['#FF4444', '#FF4444', '#2196F3', '#FF4444'],
        build: () => {
            const bx = 550;
            // Left wall
            blocks.push(new Block(bx, GROUND_Y - 40, 15, 80, 'stone'));
            // Right wall
            blocks.push(new Block(bx + 130, GROUND_Y - 40, 15, 80, 'stone'));
            // Roof
            blocks.push(new Block(bx + 65, GROUND_Y - 88, 150, 15, 'stone'));
            // Inner supports
            blocks.push(new Block(bx + 35, GROUND_Y - 15, 20, 30, 'wood'));
            blocks.push(new Block(bx + 95, GROUND_Y - 15, 20, 30, 'wood'));
            // Inner top
            blocks.push(new Block(bx + 65, GROUND_Y - 45, 85, 12, 'ice'));
            // Pigs inside
            pigs.push(new Pig(bx + 65, GROUND_Y - 18));
            pigs.push(new Pig(bx + 45, GROUND_Y - 58, 14));
            pigs.push(new Pig(bx + 85, GROUND_Y - 58, 14));
        }
    },
    // Level 4 — twin towers
    {
        birds: 5,
        birdColors: ['#FF4444', '#FF4444', '#2196F3', '#FF4444', '#FF4444'],
        build: () => {
            // Tower 1
            const t1 = 520;
            blocks.push(new Block(t1, GROUND_Y - 20, 20, 40, 'stone'));
            blocks.push(new Block(t1 + 50, GROUND_Y - 20, 20, 40, 'stone'));
            blocks.push(new Block(t1 + 25, GROUND_Y - 50, 80, 15, 'wood'));
            blocks.push(new Block(t1 + 25, GROUND_Y - 72, 15, 30, 'ice'));
            blocks.push(new Block(t1 + 25, GROUND_Y - 95, 50, 12, 'wood'));
            pigs.push(new Pig(t1 + 25, GROUND_Y - 18));

            // Tower 2
            const t2 = 700;
            blocks.push(new Block(t2, GROUND_Y - 20, 20, 40, 'stone'));
            blocks.push(new Block(t2 + 50, GROUND_Y - 20, 20, 40, 'stone'));
            blocks.push(new Block(t2 + 25, GROUND_Y - 50, 80, 15, 'wood'));
            blocks.push(new Block(t2 + 25, GROUND_Y - 72, 15, 30, 'ice'));
            blocks.push(new Block(t2 + 25, GROUND_Y - 95, 50, 12, 'wood'));
            pigs.push(new Pig(t2 + 25, GROUND_Y - 18));

            // Bridge
            blocks.push(new Block((t1 + t2) / 2 + 25, GROUND_Y - 50, 100, 12, 'ice'));
            pigs.push(new Pig((t1 + t2) / 2 + 25, GROUND_Y - 63, 14));
        }
    },
    // Level 5 — the fortress
    {
        birds: 5,
        birdColors: ['#FF4444', '#2196F3', '#FF4444', '#FF4444', '#2196F3'],
        build: () => {
            const bx = 500;
            // Base walls
            blocks.push(new Block(bx, GROUND_Y - 30, 15, 60, 'stone'));
            blocks.push(new Block(bx + 160, GROUND_Y - 30, 15, 60, 'stone'));
            // First floor
            blocks.push(new Block(bx + 80, GROUND_Y - 70, 180, 15, 'stone'));
            // First floor supports
            blocks.push(new Block(bx + 45, GROUND_Y - 35, 15, 30, 'wood'));
            blocks.push(new Block(bx + 115, GROUND_Y - 35, 15, 30, 'wood'));
            // Second floor walls
            blocks.push(new Block(bx + 20, GROUND_Y - 100, 12, 45, 'wood'));
            blocks.push(new Block(bx + 140, GROUND_Y - 100, 12, 45, 'wood'));
            // Second floor
            blocks.push(new Block(bx + 80, GROUND_Y - 130, 150, 12, 'wood'));
            // Top decoration
            blocks.push(new Block(bx + 80, GROUND_Y - 150, 40, 25, 'ice'));
            // Pigs
            pigs.push(new Pig(bx + 55, GROUND_Y - 18));
            pigs.push(new Pig(bx + 105, GROUND_Y - 18));
            pigs.push(new Pig(bx + 80, GROUND_Y - 88));
            pigs.push(new Pig(bx + 80, GROUND_Y - 142, 14));
        }
    },
];

// ============================================================
//  Level loading
// ============================================================
function loadLevel(idx) {
    if (idx >= LEVELS.length) idx = 0;
    currentLevel = idx;
    const lvl = LEVELS[idx];
    blocks = [];
    pigs = [];
    particles = [];
    trajectory = [];
    birdsLeft = lvl.birds;
    currentBird = null;
    gameState = 'aiming';

    lvl.build();

    // Prepare first bird
    prepareNextBird();

    updateUI();
}

function prepareNextBird() {
    if (birdsLeft <= 0) {
        // Check if all pigs dead → level complete, else → game over after settle
        gameState = 'settling';
        settleTimer = 90;
        return;
    }
    const lvl = LEVELS[currentLevel];
    const colorIdx = lvl.birds - birdsLeft;
    const color = lvl.birdColors[colorIdx] || '#FF4444';
    currentBird = new Bird(SLING_X, SLING_Y, color);
    gameState = 'aiming';
    updateUI();
}

// ============================================================
//  Collision detection
// ============================================================
function circleRectCollision(circle, rect) {
    const cx = clamp(circle.x, rect.x - rect.w / 2, rect.x + rect.w / 2);
    const cy = clamp(circle.y, rect.y - rect.h / 2, rect.y + rect.h / 2);
    const d = dist(circle.x, circle.y, cx, cy);
    return d < circle.radius;
}

function circleCircleCollision(a, b) {
    return dist(a.x, a.y, b.x, b.y) < a.radius + b.radius;
}

function rectRectCollision(a, b) {
    return Math.abs(a.x - b.x) < (a.w + b.w) / 2 &&
           Math.abs(a.y - b.y) < (a.h + b.h) / 2;
}

function resolveCollisions() {
    if (!currentBird || !currentBird.launched) return;

    const bird = currentBird;

    // Bird vs blocks
    for (const block of blocks) {
        if (!block.alive) continue;
        if (circleRectCollision(bird, block)) {
            const speed = Math.sqrt(bird.vx * bird.vx + bird.vy * bird.vy);
            const damage = speed * 8;
            block.takeDamage(damage);

            // Push block
            block.vx += bird.vx * 0.3;
            block.vy += bird.vy * 0.2;

            // Slow bird
            bird.vx *= 0.5;
            bird.vy *= 0.5;

            if (speed > 3) {
                spawnParticles(bird.x, bird.y, MATERIAL[block.material].color, 5);
            }
        }
    }

    // Bird vs pigs
    for (const pig of pigs) {
        if (!pig.alive) continue;
        if (circleCircleCollision(bird, pig)) {
            const speed = Math.sqrt(bird.vx * bird.vx + bird.vy * bird.vy);
            const damage = speed * 12;
            pig.takeDamage(damage);

            pig.vx += bird.vx * 0.4;
            pig.vy += bird.vy * 0.3;

            bird.vx *= 0.4;
            bird.vy *= 0.4;

            if (speed > 2) {
                spawnParticles(bird.x, bird.y, '#81C784', 5);
            }
        }
    }

    // Block vs block (simple)
    for (let i = 0; i < blocks.length; i++) {
        if (!blocks[i].alive) continue;
        for (let j = i + 1; j < blocks.length; j++) {
            if (!blocks[j].alive) continue;
            const a = blocks[i];
            const b = blocks[j];
            if (rectRectCollision(a, b)) {
                const overlapX = (a.w + b.w) / 2 - Math.abs(a.x - b.x);
                const overlapY = (a.h + b.h) / 2 - Math.abs(a.y - b.y);
                if (overlapX < overlapY) {
                    const sign = a.x < b.x ? -1 : 1;
                    a.x += sign * overlapX * 0.3;
                    b.x -= sign * overlapX * 0.3;
                    const relV = Math.abs(a.vx - b.vx);
                    if (relV > 2) {
                        a.takeDamage(relV * 2);
                        b.takeDamage(relV * 2);
                    }
                    a.vx *= -0.3;
                    b.vx *= -0.3;
                } else {
                    const sign = a.y < b.y ? -1 : 1;
                    a.y += sign * overlapY * 0.3;
                    b.y -= sign * overlapY * 0.3;
                    const relV = Math.abs(a.vy - b.vy);
                    if (relV > 2) {
                        a.takeDamage(relV * 2);
                        b.takeDamage(relV * 2);
                    }
                    a.vy *= -0.3;
                    b.vy *= -0.3;
                }
            }
        }
    }

    // Block vs pig
    for (const block of blocks) {
        if (!block.alive) continue;
        for (const pig of pigs) {
            if (!pig.alive) continue;
            // Approximate pig as a rect for this check
            const pigRect = { x: pig.x, y: pig.y, w: pig.radius * 2, h: pig.radius * 2 };
            if (rectRectCollision(block, pigRect)) {
                const relVx = Math.abs(block.vx - pig.vx);
                const relVy = Math.abs(block.vy - pig.vy);
                const relV = Math.sqrt(relVx * relVx + relVy * relVy);
                if (relV > 2) {
                    pig.takeDamage(relV * 4);
                    pig.vx += block.vx * 0.2;
                    pig.vy += block.vy * 0.15;
                }
            }
        }
    }
}

// ============================================================
//  Scoring
// ============================================================
function checkDeadObjects() {
    for (let i = pigs.length - 1; i >= 0; i--) {
        if (!pigs[i].alive) {
            const pts = 5000;
            score += pts;
            spawnScorePopup(pigs[i].x, pigs[i].y - 30, pts);
            pigs.splice(i, 1);
        }
    }
    for (let i = blocks.length - 1; i >= 0; i--) {
        if (!blocks[i].alive) {
            const pts = 500;
            score += pts;
            spawnScorePopup(blocks[i].x, blocks[i].y - 20, pts);
            blocks.splice(i, 1);
        }
    }
}

function checkLevelState() {
    if (pigs.length === 0) {
        // Level complete!
        const bonus = birdsLeft * 10000;
        score += bonus;
        gameState = 'levelComplete';
        showLevelComplete();
        return;
    }

    if (gameState === 'settling') {
        settleTimer--;
        if (settleTimer <= 0) {
            if (pigs.length > 0 && birdsLeft <= 0) {
                gameState = 'gameOver';
                showGameOver();
            }
        }
    }
}

// ============================================================
//  Drawing
// ============================================================
function drawBackground() {
    // Sky gradient
    const grad = ctx.createLinearGradient(0, 0, 0, GROUND_Y);
    grad.addColorStop(0, COLORS.sky1);
    grad.addColorStop(1, COLORS.sky2);
    ctx.fillStyle = grad;
    ctx.fillRect(0, 0, W, GROUND_Y);

    // Clouds
    drawCloud(120, 80, 60);
    drawCloud(350, 50, 45);
    drawCloud(600, 100, 55);
    drawCloud(820, 60, 40);

    // Hills
    ctx.fillStyle = '#7CB342';
    ctx.beginPath();
    ctx.moveTo(0, GROUND_Y);
    for (let x = 0; x <= W; x += 2) {
        const h = Math.sin(x * 0.005) * 20 + Math.sin(x * 0.012) * 10;
        ctx.lineTo(x, GROUND_Y - 15 - h);
    }
    ctx.lineTo(W, GROUND_Y);
    ctx.closePath();
    ctx.fill();

    // Ground
    ctx.fillStyle = COLORS.ground;
    ctx.fillRect(0, GROUND_Y, W, H - GROUND_Y);

    // Grass line
    ctx.fillStyle = COLORS.grass;
    ctx.fillRect(0, GROUND_Y - 4, W, 8);

    // Grass tufts
    ctx.fillStyle = '#66BB6A';
    for (let x = 0; x < W; x += 15) {
        const h = 4 + Math.sin(x * 0.3) * 3;
        ctx.beginPath();
        ctx.moveTo(x, GROUND_Y);
        ctx.lineTo(x + 3, GROUND_Y - h);
        ctx.lineTo(x + 6, GROUND_Y);
        ctx.fill();
    }
}

function drawCloud(x, y, size) {
    ctx.fillStyle = 'rgba(255,255,255,0.8)';
    ctx.beginPath();
    ctx.arc(x, y, size * 0.5, 0, Math.PI * 2);
    ctx.arc(x + size * 0.4, y - size * 0.15, size * 0.4, 0, Math.PI * 2);
    ctx.arc(x + size * 0.7, y, size * 0.35, 0, Math.PI * 2);
    ctx.arc(x + size * 0.35, y + size * 0.1, size * 0.35, 0, Math.PI * 2);
    ctx.fill();
}

function drawSlingshot(behind) {
    const sx = SLING_X;
    const sy = SLING_Y;
    const baseY = GROUND_Y;

    if (behind) {
        // Back band (drawn behind bird)
        if (currentBird && gameState === 'aiming') {
            ctx.strokeStyle = COLORS.rubber;
            ctx.lineWidth = 5;
            ctx.beginPath();
            ctx.moveTo(sx + 8, sy - 25);
            ctx.lineTo(currentBird.x, currentBird.y);
            ctx.stroke();
        }

        // Back post
        ctx.fillStyle = COLORS.slingshotDark;
        ctx.fillRect(sx + 2, sy - 30, 10, 45);
    } else {
        // Front band
        if (currentBird && gameState === 'aiming') {
            ctx.strokeStyle = COLORS.rubber;
            ctx.lineWidth = 5;
            ctx.beginPath();
            ctx.moveTo(sx - 8, sy - 25);
            ctx.lineTo(currentBird.x, currentBird.y);
            ctx.stroke();
        }

        // Main post
        ctx.fillStyle = COLORS.slingshot;
        // Base
        ctx.fillRect(sx - 6, sy + 5, 12, baseY - sy - 5);
        // Fork
        ctx.fillRect(sx - 12, sy - 30, 8, 40);
        ctx.fillRect(sx + 4, sy - 30, 8, 40);
        // Fork tips
        ctx.beginPath();
        ctx.arc(sx - 8, sy - 30, 5, 0, Math.PI * 2);
        ctx.fillStyle = COLORS.slingshotDark;
        ctx.fill();
        ctx.beginPath();
        ctx.arc(sx + 8, sy - 30, 5, 0, Math.PI * 2);
        ctx.fill();
    }
}

function drawTrajectory() {
    if (gameState !== 'aiming' || !currentBird || !mouse.down) return;

    const dx = SLING_X - currentBird.x;
    const dy = SLING_Y - currentBird.y;
    const vx = dx * LAUNCH_POWER;
    const vy = dy * LAUNCH_POWER;

    ctx.fillStyle = 'rgba(255,255,255,0.5)';
    let px = SLING_X;
    let py = SLING_Y;
    let pvx = vx;
    let pvy = vy;

    for (let i = 0; i < 40; i++) {
        pvx *= 1;
        pvy += GRAVITY;
        px += pvx;
        py += pvy;

        if (py > GROUND_Y || px > W || px < 0) break;

        if (i % 3 === 0) {
            const alpha = 1 - i / 40;
            ctx.globalAlpha = alpha * 0.6;
            ctx.beginPath();
            ctx.arc(px, py, 3, 0, Math.PI * 2);
            ctx.fill();
        }
    }
    ctx.globalAlpha = 1;
}

function drawWaitingBirds() {
    const lvl = LEVELS[currentLevel];
    const waiting = birdsLeft - (currentBird ? 1 : 0);
    for (let i = 0; i < waiting; i++) {
        const colorIdx = lvl.birds - waiting + i;
        const color = lvl.birdColors[colorIdx] || '#FF4444';
        const bx = 60 + i * 28;
        const by = GROUND_Y + 30;
        ctx.beginPath();
        ctx.arc(bx, by, 10, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
        ctx.strokeStyle = darkenColor(color, 40);
        ctx.lineWidth = 1.5;
        ctx.stroke();
    }
}

// ============================================================
//  Main game loop
// ============================================================
function update() {
    // Update bird
    if (currentBird) {
        currentBird.update();
    }

    // Update blocks
    for (const b of blocks) {
        if (b.alive) b.update();
    }

    // Update pigs
    for (const p of pigs) {
        if (p.alive) p.update();
    }

    // Collisions
    resolveCollisions();

    // Clean dead objects
    checkDeadObjects();

    // Particles
    updateParticles();

    // Check game state
    if (gameState === 'flying') {
        if (currentBird && !currentBird.alive) {
            birdsLeft--;
            currentBird = null;
            setTimeout(() => prepareNextBird(), 500);
        }
    }

    if (gameState === 'settling' || gameState === 'flying') {
        checkLevelState();
    }

    updateUI();
}

function draw() {
    ctx.clearRect(0, 0, W, H);

    drawBackground();
    drawWaitingBirds();

    // Slingshot back
    drawSlingshot(true);

    // Trajectory preview
    drawTrajectory();

    // Bird
    if (currentBird) {
        currentBird.draw();
    }

    // Slingshot front
    drawSlingshot(false);

    // Blocks
    for (const b of blocks) {
        if (b.alive) b.draw();
    }

    // Pigs
    for (const p of pigs) {
        if (p.alive) p.draw();
    }

    // Particles on top
    drawParticles();
}

function gameLoop() {
    if (gameState !== 'start' && gameState !== 'levelComplete' && gameState !== 'gameOver') {
        update();
    }
    draw();
    requestAnimationFrame(gameLoop);
}

// ============================================================
//  Input handling
// ============================================================
function getMousePos(e) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = W / rect.width;
    const scaleY = H / rect.height;
    return {
        x: (e.clientX - rect.left) * scaleX,
        y: (e.clientY - rect.top) * scaleY,
    };
}

canvas.addEventListener('mousedown', (e) => {
    e.preventDefault();
    const pos = getMousePos(e);
    mouse.x = pos.x;
    mouse.y = pos.y;
    mouse.down = true;

    if (gameState === 'aiming' && currentBird) {
        const d = dist(pos.x, pos.y, currentBird.x, currentBird.y);
        if (d < 40) {
            // Start dragging
        }
    }
});

canvas.addEventListener('mousemove', (e) => {
    e.preventDefault();
    const pos = getMousePos(e);
    mouse.x = pos.x;
    mouse.y = pos.y;

    if (gameState === 'aiming' && currentBird && mouse.down) {
        const dx = pos.x - SLING_X;
        const dy = pos.y - SLING_Y;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d > MAX_PULL) {
            currentBird.x = SLING_X + (dx / d) * MAX_PULL;
            currentBird.y = SLING_Y + (dy / d) * MAX_PULL;
        } else {
            currentBird.x = pos.x;
            currentBird.y = pos.y;
        }
    }

    // Cursor style
    if (gameState === 'aiming' && currentBird) {
        const d = dist(pos.x, pos.y, currentBird.x, currentBird.y);
        canvas.style.cursor = d < 40 ? 'grab' : 'default';
        if (mouse.down) canvas.style.cursor = 'grabbing';
    } else {
        canvas.style.cursor = 'default';
    }
});

canvas.addEventListener('mouseup', (e) => {
    e.preventDefault();
    if (gameState === 'aiming' && currentBird && mouse.down) {
        const dx = SLING_X - currentBird.x;
        const dy = SLING_Y - currentBird.y;
        const pullDist = Math.sqrt(dx * dx + dy * dy);

        if (pullDist > 10) {
            // Launch!
            currentBird.vx = dx * LAUNCH_POWER;
            currentBird.vy = dy * LAUNCH_POWER;
            currentBird.launched = true;
            gameState = 'flying';
        } else {
            // Reset position
            currentBird.x = SLING_X;
            currentBird.y = SLING_Y;
        }
    }
    mouse.down = false;
});

// Touch support
canvas.addEventListener('touchstart', (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    const mouseEvent = new MouseEvent('mousedown', {
        clientX: touch.clientX,
        clientY: touch.clientY,
    });
    canvas.dispatchEvent(mouseEvent);
}, { passive: false });

canvas.addEventListener('touchmove', (e) => {
    e.preventDefault();
    const touch = e.touches[0];
    const mouseEvent = new MouseEvent('mousemove', {
        clientX: touch.clientX,
        clientY: touch.clientY,
    });
    canvas.dispatchEvent(mouseEvent);
}, { passive: false });

canvas.addEventListener('touchend', (e) => {
    e.preventDefault();
    const mouseEvent = new MouseEvent('mouseup', {});
    canvas.dispatchEvent(mouseEvent);
}, { passive: false });

// ============================================================
//  UI management
// ============================================================
function updateUI() {
    document.getElementById('score').textContent = score;
    document.getElementById('level').textContent = currentLevel + 1;
    document.getElementById('birds-left').textContent = Math.max(0, birdsLeft - (currentBird && !currentBird.launched ? 1 : 0));
}

function showLevelComplete() {
    const overlay = document.getElementById('level-complete');
    overlay.classList.remove('hidden');
    document.getElementById('level-score').textContent = score;

    // Star rating
    const stars = Math.min(3, Math.ceil(birdsLeft / 2) + 1);
    const starDiv = document.getElementById('star-rating');
    starDiv.innerHTML = '';
    for (let i = 0; i < 3; i++) {
        starDiv.innerHTML += i < stars ? '\u2B50' : '\u2606';
    }
}

function showGameOver() {
    document.getElementById('game-over').classList.remove('hidden');
}

// Button handlers
document.getElementById('start-btn').addEventListener('click', () => {
    document.getElementById('start-screen').classList.add('hidden');
    score = 0;
    loadLevel(0);
});

document.getElementById('next-level-btn').addEventListener('click', () => {
    document.getElementById('level-complete').classList.add('hidden');
    loadLevel(currentLevel + 1);
});

document.getElementById('retry-btn').addEventListener('click', () => {
    document.getElementById('game-over').classList.add('hidden');
    score = Math.max(0, score - 5000);
    loadLevel(currentLevel);
});

// ============================================================
//  Start!
// ============================================================
gameLoop();
