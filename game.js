"use strict";

const canvas = document.querySelector("#game-canvas");
const ctx = canvas.getContext("2d");
const chartCanvas = document.querySelector("#population-chart");
const chartCtx = chartCanvas.getContext("2d");

const ui = {
  humanCount: document.querySelector("#human-count"),
  zombieCount: document.querySelector("#zombie-count"),
  rescuedCount: document.querySelector("#rescued-count"),
  targetCount: document.querySelector("#target-count"),
  healthFill: document.querySelector("#health-fill"),
  overlay: document.querySelector("#game-overlay"),
  overlayKicker: document.querySelector("#overlay-kicker"),
  overlayTitle: document.querySelector("#overlay-title"),
  overlayMessage: document.querySelector("#overlay-message"),
  startButton: document.querySelector("#start-button"),
  pauseButton: document.querySelector("#pause-button"),
};

const WORLD = { width: canvas.width, height: canvas.height, margin: 22 };
const SETTINGS = {
  startingCivilians: 14,
  startingZombies: 3,
  rescueTarget: 8,
  maxZombies: 28,
};

const COLORS = {
  human: "#51c9ff",
  zombie: "#82d949",
  player: "#ffd460",
  danger: "#ff655e",
  bullet: "#fffbd7",
  road: "#131b19",
};

const clamp = (value, min, max) => Math.max(min, Math.min(max, value));
const random = (min, max) => Math.random() * (max - min) + min;
const distance = (a, b) => Math.hypot(a.x - b.x, a.y - b.y);

function normalize(x, y) {
  const length = Math.hypot(x, y) || 1;
  return { x: x / length, y: y / length };
}

function keepInWorld(entity) {
  entity.x = clamp(entity.x, WORLD.margin + entity.radius, WORLD.width - WORLD.margin - entity.radius);
  entity.y = clamp(entity.y, WORLD.margin + entity.radius, WORLD.height - WORLD.margin - entity.radius);
}

class Entity {
  constructor(x, y, radius) {
    this.x = x;
    this.y = y;
    this.radius = radius;
    this.vx = 0;
    this.vy = 0;
  }

  move(deltaTime) {
    this.x += this.vx * deltaTime;
    this.y += this.vy * deltaTime;
    keepInWorld(this);
  }
}

class Civilian extends Entity {
  constructor(x, y) {
    super(x, y, 8);
    this.speed = random(44, 65);
    this.directionTimer = 0;
    this.infection = 0;
    this.changeDirection();
  }

  changeDirection() {
    const angle = random(0, Math.PI * 2);
    this.vx = Math.cos(angle) * this.speed * 0.42;
    this.vy = Math.sin(angle) * this.speed * 0.42;
    this.directionTimer = random(1.2, 3.3);
  }

  update(deltaTime, zombies) {
    this.directionTimer -= deltaTime;
    let nearestZombie = null;
    let nearestDistance = Infinity;

    for (const zombie of zombies) {
      const currentDistance = distance(this, zombie);
      if (currentDistance < nearestDistance) {
        nearestDistance = currentDistance;
        nearestZombie = zombie;
      }
    }

    if (nearestZombie && nearestDistance < 145) {
      const away = normalize(this.x - nearestZombie.x, this.y - nearestZombie.y);
      const panic = 1 + (145 - nearestDistance) / 145;
      this.vx = away.x * this.speed * panic;
      this.vy = away.y * this.speed * panic;
      this.directionTimer = 0.25;
    } else if (this.directionTimer <= 0) {
      this.changeDirection();
    }

    this.move(deltaTime);
  }

  draw(context) {
    context.save();
    context.translate(this.x, this.y);

    if (this.infection > 0) {
      context.beginPath();
      context.arc(0, 0, this.radius + 6, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * this.infection);
      context.strokeStyle = COLORS.danger;
      context.lineWidth = 2;
      context.stroke();
    }

    context.beginPath();
    context.arc(0, 0, this.radius, 0, Math.PI * 2);
    context.fillStyle = COLORS.human;
    context.shadowColor = COLORS.human;
    context.shadowBlur = 12;
    context.fill();

    context.fillStyle = "rgba(4, 16, 20, 0.8)";
    context.fillRect(-3, -2, 2, 2);
    context.fillRect(1, -2, 2, 2);
    context.restore();
  }
}

class Zombie extends Entity {
  constructor(x, y, level = 0) {
    super(x, y, random(9, 12));
    this.speed = random(33, 44) + Math.min(level * 0.35, 12);
    this.angle = 0;
  }

  update(deltaTime, player, civilians, zombies) {
    let target = player;
    let targetDistance = distance(this, player);

    for (const civilian of civilians) {
      const currentDistance = distance(this, civilian);
      if (currentDistance < targetDistance) {
        targetDistance = currentDistance;
        target = civilian;
      }
    }

    const direction = normalize(target.x - this.x, target.y - this.y);
    this.angle = Math.atan2(direction.y, direction.x);
    this.vx = direction.x * this.speed;
    this.vy = direction.y * this.speed;

    // A small separation force prevents zombies from stacking into one dot.
    for (const other of zombies) {
      if (other === this) continue;
      const currentDistance = distance(this, other);
      if (currentDistance > 0 && currentDistance < this.radius * 2.1) {
        this.vx += ((this.x - other.x) / currentDistance) * 22;
        this.vy += ((this.y - other.y) / currentDistance) * 22;
      }
    }

    this.move(deltaTime);
  }

  draw(context) {
    context.save();
    context.translate(this.x, this.y);
    context.rotate(this.angle);
    context.beginPath();
    context.arc(0, 0, this.radius, 0, Math.PI * 2);
    context.fillStyle = COLORS.zombie;
    context.shadowColor = COLORS.zombie;
    context.shadowBlur = 10;
    context.fill();

    context.strokeStyle = "#274019";
    context.lineWidth = 3;
    context.beginPath();
    context.moveTo(-this.radius - 4, -3);
    context.lineTo(-this.radius + 1, 1);
    context.moveTo(-this.radius - 3, 5);
    context.lineTo(-this.radius + 2, 3);
    context.stroke();

    context.fillStyle = "#13200d";
    context.fillRect(2, -5, 3, 3);
    context.fillRect(5, 2, 3, 3);
    context.restore();
  }
}

class Player extends Entity {
  constructor() {
    super(WORLD.width / 2, WORLD.height / 2, 12);
    this.speed = 190;
    this.health = 100;
    this.hitCooldown = 0;
    this.fireCooldown = 0;
    this.angle = 0;
  }

  update(deltaTime, keys, aimPoint) {
    let horizontal = 0;
    let vertical = 0;

    if (keys.has("KeyA") || keys.has("ArrowLeft")) horizontal -= 1;
    if (keys.has("KeyD") || keys.has("ArrowRight")) horizontal += 1;
    if (keys.has("KeyW") || keys.has("ArrowUp")) vertical -= 1;
    if (keys.has("KeyS") || keys.has("ArrowDown")) vertical += 1;

    const movement = normalize(horizontal, vertical);
    const isMoving = horizontal !== 0 || vertical !== 0;
    this.vx = isMoving ? movement.x * this.speed : 0;
    this.vy = isMoving ? movement.y * this.speed : 0;
    this.angle = Math.atan2(aimPoint.y - this.y, aimPoint.x - this.x);
    this.hitCooldown = Math.max(0, this.hitCooldown - deltaTime);
    this.fireCooldown = Math.max(0, this.fireCooldown - deltaTime);
    this.move(deltaTime);
  }

  draw(context) {
    context.save();
    context.translate(this.x, this.y);
    context.rotate(this.angle);
    context.shadowColor = COLORS.player;
    context.shadowBlur = 18;
    context.fillStyle = COLORS.player;
    context.beginPath();
    context.moveTo(17, 0);
    context.lineTo(-10, -10);
    context.lineTo(-6, 0);
    context.lineTo(-10, 10);
    context.closePath();
    context.fill();
    context.shadowBlur = 0;
    context.fillStyle = "#17160d";
    context.fillRect(2, -2, 11, 4);
    context.restore();
  }
}

class Bullet extends Entity {
  constructor(x, y, angle) {
    super(x, y, 3);
    this.vx = Math.cos(angle) * 510;
    this.vy = Math.sin(angle) * 510;
    this.life = 1.25;
  }

  update(deltaTime) {
    this.x += this.vx * deltaTime;
    this.y += this.vy * deltaTime;
    this.life -= deltaTime;
  }

  draw(context) {
    context.save();
    context.beginPath();
    context.arc(this.x, this.y, this.radius, 0, Math.PI * 2);
    context.fillStyle = COLORS.bullet;
    context.shadowColor = COLORS.bullet;
    context.shadowBlur = 9;
    context.fill();
    context.restore();
  }
}

class Game {
  constructor() {
    this.keys = new Set();
    this.pointer = { x: WORLD.width * 0.75, y: WORLD.height / 2 };
    this.state = "ready";
    this.elapsed = 0;
    this.lastFrame = 0;
    this.spawnTimer = 0;
    this.chartTimer = 0;
    this.rescued = 0;
    this.civilians = [];
    this.zombies = [];
    this.bullets = [];
    this.populationHistory = [];
    this.player = new Player();
    this.bindEvents();
    this.reset();
    requestAnimationFrame((time) => this.loop(time));
  }

  bindEvents() {
    window.addEventListener("keydown", (event) => {
      const gameKeys = ["ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Space"];
      if (gameKeys.includes(event.code)) event.preventDefault();
      this.keys.add(event.code);

      if (event.code === "KeyP" && !event.repeat) this.togglePause();
      if (event.code === "Space" && !event.repeat) this.fire();
    });

    window.addEventListener("keyup", (event) => this.keys.delete(event.code));
    window.addEventListener("blur", () => {
      this.keys.clear();
      if (this.state === "running") this.pause();
    });

    canvas.addEventListener("pointermove", (event) => {
      const bounds = canvas.getBoundingClientRect();
      this.pointer.x = ((event.clientX - bounds.left) / bounds.width) * WORLD.width;
      this.pointer.y = ((event.clientY - bounds.top) / bounds.height) * WORLD.height;
    });

    canvas.addEventListener("pointerdown", () => {
      canvas.focus();
      this.fire();
    });

    ui.startButton.addEventListener("click", () => {
      if (this.state === "paused") this.resume();
      else this.start();
    });
    ui.pauseButton.addEventListener("click", () => this.togglePause());
  }

  reset() {
    this.elapsed = 0;
    this.spawnTimer = 5.8;
    this.chartTimer = 0;
    this.rescued = 0;
    this.player = new Player();
    this.bullets = [];
    this.civilians = Array.from({ length: SETTINGS.startingCivilians }, () => {
      const point = this.randomSpawn(150);
      return new Civilian(point.x, point.y);
    });
    this.zombies = Array.from({ length: SETTINGS.startingZombies }, () => {
      const point = this.edgeSpawn();
      return new Zombie(point.x, point.y);
    });
    this.populationHistory = [
      { humans: this.civilians.length, zombies: this.zombies.length },
    ];
    this.updateInterface();
    this.drawChart();
  }

  start() {
    this.reset();
    this.state = "running";
    this.lastFrame = performance.now();
    ui.overlay.classList.add("hidden");
    ui.pauseButton.disabled = false;
    ui.pauseButton.textContent = "Pause";
    canvas.focus();
  }

  pause() {
    if (this.state !== "running") return;
    this.state = "paused";
    ui.overlayKicker.textContent = "RADIO SILENCE";
    ui.overlayTitle.textContent = "Game paused";
    ui.overlayMessage.textContent = "Catch your breath. The outbreak will wait until you return.";
    ui.startButton.textContent = "Resume mission";
    ui.overlay.classList.remove("hidden");
    ui.pauseButton.textContent = "Resume";
  }

  resume() {
    if (this.state !== "paused") return;
    this.state = "running";
    this.lastFrame = performance.now();
    ui.overlay.classList.add("hidden");
    ui.pauseButton.textContent = "Pause";
    canvas.focus();
  }

  togglePause() {
    if (this.state === "running") this.pause();
    else if (this.state === "paused") this.resume();
  }

  fire() {
    if (this.state !== "running" || this.player.fireCooldown > 0) return;
    this.player.fireCooldown = 0.22;
    const muzzleX = this.player.x + Math.cos(this.player.angle) * 18;
    const muzzleY = this.player.y + Math.sin(this.player.angle) * 18;
    this.bullets.push(new Bullet(muzzleX, muzzleY, this.player.angle));
  }

  randomSpawn(minimumPlayerDistance = 0) {
    let point;
    let attempts = 0;
    do {
      point = {
        x: random(WORLD.margin + 25, WORLD.width - WORLD.margin - 25),
        y: random(WORLD.margin + 25, WORLD.height - WORLD.margin - 25),
      };
      attempts += 1;
    } while (distance(point, this.player) < minimumPlayerDistance && attempts < 30);
    return point;
  }

  edgeSpawn() {
    const side = Math.floor(random(0, 4));
    const padding = WORLD.margin + 8;
    if (side === 0) return { x: random(padding, WORLD.width - padding), y: padding };
    if (side === 1) return { x: WORLD.width - padding, y: random(padding, WORLD.height - padding) };
    if (side === 2) return { x: random(padding, WORLD.width - padding), y: WORLD.height - padding };
    return { x: padding, y: random(padding, WORLD.height - padding) };
  }

  spawnZombie() {
    if (this.zombies.length >= SETTINGS.maxZombies) return;
    const point = this.edgeSpawn();
    this.zombies.push(new Zombie(point.x, point.y, this.elapsed / 15));
  }

  update(deltaTime) {
    this.elapsed += deltaTime;
    this.spawnTimer -= deltaTime;
    this.chartTimer -= deltaTime;

    this.player.update(deltaTime, this.keys, this.pointer);
    for (const civilian of this.civilians) civilian.update(deltaTime, this.zombies);
    for (const zombie of this.zombies) {
      zombie.update(deltaTime, this.player, this.civilians, this.zombies);
    }
    for (const bullet of this.bullets) bullet.update(deltaTime);

    if (this.keys.has("Space")) this.fire();

    if (this.spawnTimer <= 0) {
      this.spawnZombie();
      this.spawnTimer = Math.max(2.25, 5.8 - this.elapsed * 0.035);
    }

    this.handleBulletHits();
    this.handleCivilianContacts(deltaTime);
    this.handlePlayerHits();
    this.bullets = this.bullets.filter(
      (bullet) =>
        bullet.life > 0 &&
        bullet.x > 0 &&
        bullet.x < WORLD.width &&
        bullet.y > 0 &&
        bullet.y < WORLD.height,
    );

    if (this.chartTimer <= 0) {
      this.populationHistory.push({
        humans: this.civilians.length,
        zombies: this.zombies.length,
      });
      this.populationHistory = this.populationHistory.slice(-38);
      this.chartTimer = 1;
      this.drawChart();
    }

    this.updateInterface();
    this.checkEndState();
  }

  handleBulletHits() {
    const hitBullets = new Set();
    const hitZombies = new Set();

    for (const bullet of this.bullets) {
      for (const zombie of this.zombies) {
        if (distance(bullet, zombie) < bullet.radius + zombie.radius) {
          hitBullets.add(bullet);
          hitZombies.add(zombie);
          break;
        }
      }
    }

    this.bullets = this.bullets.filter((bullet) => !hitBullets.has(bullet));
    this.zombies = this.zombies.filter((zombie) => !hitZombies.has(zombie));
  }

  handleCivilianContacts(deltaTime) {
    const rescued = new Set();
    const infected = new Set();

    for (const civilian of this.civilians) {
      if (distance(this.player, civilian) < this.player.radius + civilian.radius + 5) {
        rescued.add(civilian);
        continue;
      }

      let beingBitten = false;
      for (const zombie of this.zombies) {
        if (distance(civilian, zombie) < civilian.radius + zombie.radius + 2) {
          beingBitten = true;
          break;
        }
      }

      if (beingBitten) civilian.infection += deltaTime * 0.78;
      else civilian.infection = Math.max(0, civilian.infection - deltaTime * 0.18);

      if (civilian.infection >= 1) infected.add(civilian);
    }

    if (rescued.size > 0) this.rescued += rescued.size;
    for (const civilian of infected) {
      this.zombies.push(new Zombie(civilian.x, civilian.y, this.elapsed / 15));
    }

    this.civilians = this.civilians.filter(
      (civilian) => !rescued.has(civilian) && !infected.has(civilian),
    );
  }

  handlePlayerHits() {
    if (this.player.hitCooldown > 0) return;
    for (const zombie of this.zombies) {
      if (distance(this.player, zombie) < this.player.radius + zombie.radius) {
        this.player.health = Math.max(0, this.player.health - 18);
        this.player.hitCooldown = 0.72;
        const knockback = normalize(this.player.x - zombie.x, this.player.y - zombie.y);
        this.player.x += knockback.x * 26;
        this.player.y += knockback.y * 26;
        keepInWorld(this.player);
        break;
      }
    }
  }

  checkEndState() {
    if (this.rescued >= SETTINGS.rescueTarget) {
      this.end("won");
    } else if (this.player.health <= 0) {
      this.end("lost", "You were overwhelmed before the evacuation was complete.");
    } else if (this.civilians.length === 0) {
      this.end("lost", "No civilians remain in the city. The outbreak has taken everyone.");
    }
  }

  end(result, message = "You reached the rescue target and opened a safe route out of the city.") {
    this.state = result;
    ui.overlayKicker.textContent = result === "won" ? "MISSION COMPLETE" : "CITY OVERRUN";
    ui.overlayTitle.textContent = result === "won" ? "The survivors made it" : "The outbreak wins";
    ui.overlayMessage.textContent = `${message} Final count: ${this.rescued} rescued, ${this.zombies.length} zombies.`;
    ui.startButton.textContent = "Play again";
    ui.overlay.classList.remove("hidden");
    ui.pauseButton.disabled = true;
  }

  updateInterface() {
    ui.humanCount.textContent = this.civilians.length;
    ui.zombieCount.textContent = this.zombies.length;
    ui.rescuedCount.textContent = `${this.rescued} / ${SETTINGS.rescueTarget}`;
    ui.targetCount.textContent = SETTINGS.rescueTarget;
    ui.healthFill.style.width = `${this.player.health}%`;
  }

  drawBackground() {
    ctx.fillStyle = COLORS.road;
    ctx.fillRect(0, 0, WORLD.width, WORLD.height);

    ctx.strokeStyle = "rgba(188, 255, 69, 0.035)";
    ctx.lineWidth = 1;
    for (let x = 20; x < WORLD.width; x += 40) {
      ctx.beginPath();
      ctx.moveTo(x, 0);
      ctx.lineTo(x, WORLD.height);
      ctx.stroke();
    }
    for (let y = 20; y < WORLD.height; y += 40) {
      ctx.beginPath();
      ctx.moveTo(0, y);
      ctx.lineTo(WORLD.width, y);
      ctx.stroke();
    }

    ctx.fillStyle = "rgba(255, 255, 255, 0.025)";
    const blocks = [
      [48, 48, 185, 74],
      [728, 52, 184, 92],
      [56, 445, 205, 102],
      [711, 452, 197, 95],
    ];
    for (const [x, y, width, height] of blocks) {
      ctx.fillRect(x, y, width, height);
      ctx.strokeStyle = "rgba(255, 255, 255, 0.045)";
      ctx.strokeRect(x, y, width, height);
    }

    ctx.save();
    ctx.setLineDash([18, 22]);
    ctx.strokeStyle = "rgba(255, 212, 96, 0.12)";
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(0, WORLD.height / 2);
    ctx.lineTo(WORLD.width, WORLD.height / 2);
    ctx.stroke();
    ctx.restore();

    ctx.strokeStyle = "rgba(188, 255, 69, 0.15)";
    ctx.strokeRect(WORLD.margin, WORLD.margin, WORLD.width - WORLD.margin * 2, WORLD.height - WORLD.margin * 2);
  }

  draw() {
    this.drawBackground();
    for (const civilian of this.civilians) civilian.draw(ctx);
    for (const zombie of this.zombies) zombie.draw(ctx);
    for (const bullet of this.bullets) bullet.draw(ctx);
    this.player.draw(ctx);

    if (this.player.hitCooldown > 0) {
      ctx.fillStyle = `rgba(255, 70, 60, ${Math.min(0.18, this.player.hitCooldown * 0.16)})`;
      ctx.fillRect(0, 0, WORLD.width, WORLD.height);
    }

    ctx.fillStyle = "rgba(235, 244, 239, 0.46)";
    ctx.font = "700 11px ui-monospace, monospace";
    ctx.letterSpacing = "1px";
    ctx.fillText(`OUTBREAK TIME  ${Math.floor(this.elapsed).toString().padStart(3, "0")}s`, 36, 47);
  }

  drawChart() {
    const width = chartCanvas.width;
    const height = chartCanvas.height;
    const padding = 8;
    chartCtx.clearRect(0, 0, width, height);

    chartCtx.strokeStyle = "rgba(255,255,255,0.07)";
    chartCtx.lineWidth = 1;
    for (let row = 1; row < 4; row += 1) {
      const y = (height / 4) * row;
      chartCtx.beginPath();
      chartCtx.moveTo(0, y);
      chartCtx.lineTo(width, y);
      chartCtx.stroke();
    }

    const maximum = Math.max(
      SETTINGS.startingCivilians,
      ...this.populationHistory.map((point) => Math.max(point.humans, point.zombies)),
    );

    const drawLine = (key, color) => {
      chartCtx.beginPath();
      this.populationHistory.forEach((point, index) => {
        const usableWidth = width - padding * 2;
        const x =
          this.populationHistory.length === 1
            ? padding
            : padding + (index / (this.populationHistory.length - 1)) * usableWidth;
        const y = height - padding - (point[key] / maximum) * (height - padding * 2);
        if (index === 0) chartCtx.moveTo(x, y);
        else chartCtx.lineTo(x, y);
      });
      chartCtx.strokeStyle = color;
      chartCtx.lineWidth = 2;
      chartCtx.lineJoin = "round";
      chartCtx.stroke();
    };

    drawLine("humans", COLORS.human);
    drawLine("zombies", COLORS.zombie);
  }

  loop(timestamp) {
    const deltaTime = Math.min((timestamp - this.lastFrame) / 1000 || 0, 0.04);
    this.lastFrame = timestamp;
    if (this.state === "running") this.update(deltaTime);
    this.draw();
    requestAnimationFrame((time) => this.loop(time));
  }
}

new Game();
