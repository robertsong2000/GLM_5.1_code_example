/**
 * 虚拟滚动列表引擎
 *
 * 核心思路：
 * 1. 用 estimatedHeight 预估所有行高，维护一个 positions[] 累加数组
 * 2. 滚动时通过二分查找快速定位可视区的起始索引
 * 3. 仅渲染可视区 ± buffer 的 DOM 节点（不超过 30 个）
 * 4. 每次渲染后测量真实高度，修正 positions[] 并在必要时补偿滚动偏移
 */

const TOTAL = 100000;          // 总数据量
const ESTIMATED_HEIGHT = 50;   // 预估行高（px）
const BUFFER = 5;              // 可视区上下各缓冲的行数
const MAX_RENDER = 30;         // 最多渲染的 DOM 节点数
const CONTAINER_HEIGHT = 600;  // 容器高度

// ─── 数据生成 ────────────────────────────────────────────
// 模拟动态行高：部分行有额外描述文本，高度更大
const data = Array.from({ length: TOTAL }, (_, i) => {
  const index = i + 1;
  const hasDescription = index % 7 === 0;
  const hasTags = index % 13 === 0;
  return {
    id: index,
    title: `Item #${index}`,
    description: hasDescription
      ? `这是第 ${index} 条数据的详细描述信息，包含一些额外内容来模拟动态行高。`
      : null,
    tags: hasTags
      ? ['标签A', '标签B', '标签C']
      : null,
  };
});

// ─── 位置管理（支持动态行高的核心）────────────────────
// positions[i] = { top, height, bottom } 表示第 i 行的几何信息
let positions = [];
let measuredHeights = new Map(); // 已测量的真实高度

function initPositions() {
  positions = new Array(TOTAL);
  for (let i = 0; i < TOTAL; i++) {
    const height = ESTIMATED_HEIGHT;
    const top = i > 0 ? positions[i - 1].bottom : 0;
    positions[i] = { top, height, bottom: top + height };
  }
}

/** 获取第 i 行的预估高度（已测量则返回真实值） */
function getItemHeight(index) {
  return measuredHeights.get(index) ?? ESTIMATED_HEIGHT;
}

/** 用二分查找，在 positions 中找到 scrollTop 对应的起始行索引 */
function findStartIndex(scrollTop) {
  let low = 0;
  let high = positions.length - 1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (positions[mid].bottom > scrollTop) {
      high = mid - 1;
    } else {
      low = mid + 1;
    }
  }
  return low;
}

/** 在测量到真实高度后，更新该行及后续所有行的位置 */
function updatePositions(index) {
  const realHeight = measuredHeights.get(index);
  if (realHeight === undefined) return;

  const oldHeight = positions[index].height;
  if (oldHeight === realHeight) return; // 没变化

  positions[index].height = realHeight;
  positions[index].bottom = positions[index].top + realHeight;

  // 从 index+1 开始，逐个修正 top/bottom
  for (let i = index + 1; i < TOTAL; i++) {
    positions[i].top = positions[i - 1].bottom;
    const h = getItemHeight(i);
    positions[i].height = h;
    positions[i].bottom = positions[i].top + h;
  }
}

// ─── DOM 元素引用 ─────────────────────────────────────────
const container = document.getElementById('virtual-list');
const scrollContent = document.getElementById('scroll-content');
const renderedCountEl = document.getElementById('rendered-count');
const scrollInfoEl = document.getElementById('scroll-info');

// 撑开总高度，让容器出现滚动条
function updateTotalHeight() {
  const totalHeight = positions[positions.length - 1].bottom;
  scrollContent.style.height = `${totalHeight}px`;
}

// ─── 渲染逻辑 ─────────────────────────────────────────────
let lastStartIdx = -1;
let lastEndIdx = -1;

function render(force = false) {
  const scrollTop = container.scrollTop;

  // 定位起始行
  let startIdx = Math.max(0, findStartIndex(scrollTop) - BUFFER);

  // 向下扫描，计算可视区内能容纳多少行（限制 MAX_RENDER）
  let visibleHeight = 0;
  let endIdx = startIdx;
  while (endIdx < TOTAL && visibleHeight < CONTAINER_HEIGHT + BUFFER * ESTIMATED_HEIGHT) {
    visibleHeight += positions[endIdx].height;
    endIdx++;
  }
  endIdx = Math.min(endIdx + BUFFER, TOTAL);
  // 严格限制最大渲染数
  if (endIdx - startIdx > MAX_RENDER) {
    endIdx = startIdx + MAX_RENDER;
  }

  if (!force && startIdx === lastStartIdx && endIdx === lastEndIdx) {
    return; // 没变化，跳过
  }

  lastStartIdx = startIdx;
  lastEndIdx = endIdx;

  // 使用 offsetTop 定位，而非 transform（避免子元素定位问题）
  const offsetY = positions[startIdx].top;

  // 构建HTML片段（比逐个 createElement 更快）
  let html = `<div class="items-wrapper" style="position:absolute;top:${offsetY}px;left:0;right:0;">`;

  for (let i = startIdx; i < endIdx; i++) {
    const item = data[i];
    const isEven = i % 2 === 0;
    html += `<div class="list-item ${isEven ? 'even' : ''}" data-index="${i}">`;
    html += `<div class="item-index">${item.id}</div>`;
    html += `<div class="item-body">`;
    html += `<div class="item-title">${item.title}</div>`;
    if (item.description) {
      html += `<div class="item-desc">${item.description}</div>`;
    }
    if (item.tags) {
      html += `<div class="item-tags">${item.tags.map(t => `<span class="tag">${t}</span>`).join('')}</div>`;
    }
    html += `</div></div>`;
  }

  html += '</div>';
  scrollContent.innerHTML = html;

  // 更新统计信息
  renderedCountEl.textContent = `已渲染: ${endIdx - startIdx} 个节点`;

  // 测量真实高度并修正位置
  measureAndCorrect(startIdx, endIdx);
}

/** 渲染后测量真实 DOM 高度，修正 positions 数组 */
function measureAndCorrect(startIdx, endIdx) {
  const items = scrollContent.querySelectorAll('.list-item');
  let diff = 0; // 累积高度偏差

  items.forEach((el) => {
    const idx = parseInt(el.dataset.index, 10);
    const realHeight = el.offsetHeight;
    const prevHeight = getItemHeight(idx);
    if (realHeight !== prevHeight) {
      measuredHeights.set(idx, realHeight);
      diff += realHeight - prevHeight;
    }
  });

  if (diff !== 0) {
    // 仅修正当前渲染区域内的位置（精确计算）
    for (let i = startIdx; i < endIdx; i++) {
      const top = i > 0 ? positions[i - 1].bottom : 0;
      const h = getItemHeight(i);
      positions[i].top = top;
      positions[i].height = h;
      positions[i].bottom = top + h;
    }
    // 对后续未测量的行，整体平移 diff（无需逐行重算）
    for (let i = endIdx; i < TOTAL; i++) {
      positions[i].top += diff;
      positions[i].bottom += diff;
    }
    updateTotalHeight();
  }
}

// ─── 滚动事件（requestAnimationFrame 节流）───────────────
let ticking = false;

container.addEventListener('scroll', () => {
  if (!ticking) {
    requestAnimationFrame(() => {
      scrollInfoEl.textContent = `滚动位置: ${Math.round(container.scrollTop)}px`;
      render();
      ticking = false;
    });
    ticking = true;
  }
});

// 窗口 resize 时重新渲染
window.addEventListener('resize', () => {
  if (!ticking) {
    requestAnimationFrame(() => {
      render(true);
      ticking = false;
    });
    ticking = true;
  }
});

// ─── 初始化 ──────────────────────────────────────────────
function init() {
  initPositions();
  updateTotalHeight();
  render(true);
  console.log(`虚拟列表已初始化: ${TOTAL} 条数据`);
}

init();
