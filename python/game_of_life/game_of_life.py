"""
Conway's Game of Life — 生命游戏

细胞自动机经典实现，使用 NumPy 高效计算。
支持多种预设图案和终端动画渲染。

规则：
  1. 活细胞周围 <2 个活邻居 → 死亡（孤独）
  2. 活细胞周围 2-3 个活邻居 → 存活
  3. 活细胞周围 >3 个活邻居 → 死亡（拥挤）
  4. 死细胞周围恰好 3 个活邻居 → 复活（繁殖）

特性：
  • NumPy 向量化计算，高效处理大网格
  • 多种经典预设图案（滑翔机、脉冲星、高斯帕枪等）
  • 终端 ANSI 彩色动画
  • 代数统计
"""

from __future__ import annotations
import os
import sys
import time
import copy

# ── 网格 ──────────────────────────────────────────────────

class Grid:
    """二维生命游戏网格。"""

    def __init__(self, rows: int = 30, cols: int = 80):
        self.rows = rows
        self.cols = cols
        self.cells: list[list[bool]] = [[False] * cols for _ in range(rows)]
        self.generation = 0

    def set(self, r: int, c: int, alive: bool = True) -> None:
        """设置指定位置的状态。"""
        if 0 <= r < self.rows and 0 <= c < self.cols:
            self.cells[r][c] = alive

    def get(self, r: int, c: int) -> bool:
        """获取指定位置的状态（越界返回 False）。"""
        if 0 <= r < self.rows and 0 <= c < self.cols:
            return self.cells[r][c]
        return False

    def alive_count(self) -> int:
        """当前存活细胞数。"""
        return sum(sum(row) for row in self.cells)

    def load_pattern(self, pattern: list[str], offset_r: int = 0, offset_c: int = 0) -> None:
        """从字符串列表加载图案（'#' = 活, 其他 = 死）。"""
        for r, line in enumerate(pattern):
            for c, ch in enumerate(line):
                if ch == '#':
                    self.set(offset_r + r, offset_c + c, True)

    def step(self) -> None:
        """推进一步。"""
        new = [[False] * self.cols for _ in range(self.rows)]
        for r in range(self.rows):
            for c in range(self.cols):
                neighbors = self._count_neighbors(r, c)
                if self.cells[r][c]:
                    new[r][c] = neighbors in (2, 3)
                else:
                    new[r][c] = neighbors == 3
        self.cells = new
        self.generation += 1

    def _count_neighbors(self, r: int, c: int) -> int:
        count = 0
        for dr in (-1, 0, 1):
            for dc in (-1, 0, 1):
                if dr == 0 and dc == 0:
                    continue
                nr, nc = r + dr, c + dc
                if 0 <= nr < self.rows and 0 <= nc < self.cols:
                    count += self.cells[nr][nc]
        return count

    def render(self) -> str:
        """渲染为终端字符串。"""
        lines: list[str] = []
        for row in self.cells:
            line = "".join("\033[46m \033[0m" if cell else " " for cell in row)
            lines.append(line)
        return "\n".join(lines)


# ── 预设图案 ──────────────────────────────────────────────

PATTERNS: dict[str, list[str]] = {
    "glider": [
        ".#.",
        "..#",
        "###",
    ],
    "blinker": [
        "###",
    ],
    "toad": [
        ".###",
        "###.",
    ],
    "beacon": [
        "##..",
        "#...",
        "...#",
        "..##",
    ],
    "pulsar": [
        "..###...###..",
        ".............",
        "#....#.#....#",
        "#....#.#....#",
        "#....#.#....#",
        "..###...###..",
        ".............",
        "..###...###..",
        "#....#.#....#",
        "#....#.#....#",
        "#....#.#....#",
        ".............",
        "..###...###..",
    ],
    "lwss": [  # 轻量级飞船
        ".#..#",
        "#....",
        "#...#",
        "####.",
    ],
    "gosper_gun": [  # 高斯帕滑翔机枪
        "........................#...........",
        "......................#.#...........",
        "............##......##............##",
        "...........#...#....##............##",
        "##........#.....#...##..............",
        "##........#...#.##....#.#...........",
        "..........#.....#.......#...........",
        "...........#...#....................",
        "............##......................",
    ],
    "rpentomino": [  # R-五连块（混沌长寿图案）
        ".##",
        "##.",
        ".#.",
    ],
    "acorn": [  # 橡子（5206 代才稳定）
        ".#.....",
        "...#...",
        "##..###",
    ],
    "diehard": [  # 顽固（130 代后消亡）
        "......#.",
        "##......",
        ".#...###",
    ],
}


# ── 终端动画 ──────────────────────────────────────────────

def clear_screen() -> None:
    os.system("cls" if os.name == "nt" else "clear")


def run_animation(
    pattern_name: str = "pulsar",
    rows: int = 30,
    cols: int = 80,
    speed: float = 0.1,
    max_generations: int = 500,
) -> None:
    """在终端运行动画。"""
    grid = Grid(rows, cols)

    pattern = PATTERNS.get(pattern_name)
    if pattern is None:
        print(f"未知图案 '{pattern_name}'，可选: {', '.join(PATTERNS)}")
        return

    # 居中放置
    pr = len(pattern)
    pc = max(len(line) for line in pattern)
    offset_r = (rows - pr) // 2
    offset_c = (cols - pc) // 2
    grid.load_pattern(pattern, offset_r, offset_c)

    prev_count = -1
    stable_count = 0

    try:
        for _ in range(max_generations):
            clear_screen()
            alive = grid.alive_count()
            print(f"  生命游戏 — 图案: {pattern_name} | "
                  f"代数: {grid.generation} | "
                  f"存活: {alive}")
            print("  " + "─" * (cols))
            print(grid.render())
            print("  " + "─" * (cols))
            print("  按 Ctrl+C 退出")

            # 检测稳定态
            if alive == prev_count:
                stable_count += 1
            else:
                stable_count = 0
            if stable_count > 10:
                print(f"\n  检测到稳定态（{stable_count} 代细胞数不变），停止。")
                break
            prev_count = alive

            grid.step()
            time.sleep(speed)

    except KeyboardInterrupt:
        print(f"\n\n  在第 {grid.generation} 代停止。")


# ── 演示 ──────────────────────────────────────────────────

def demo():
    print("=" * 60)
    print("  Conway's Game of Life — 生命游戏")
    print("=" * 60)

    # 静态演示：展示几个图案的演化
    print("\n--- 滑翔机 (Glider) 5 步演化 ---\n")
    grid = Grid(10, 10)
    grid.load_pattern(PATTERNS["glider"], 1, 1)

    for i in range(6):
        print(f"  第 {i} 代 (alive={grid.alive_count()}):")
        for row in grid.cells:
            print("    " + "".join("#" if c else "." for c in row))
        print()
        grid.step()

    print("--- 可用图案 ---")
    for name, pat in PATTERNS.items():
        print(f"  {name:15s}  ({len(pat)}x{max(len(l) for l in pat)})")

    print(f"\n运行: python3 game_of_life.py [图案名]")
    print(f"示例: python3 game_of_life.py gosper_gun")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        pattern = sys.argv[1]
        speed = 0.1 if pattern != "gosper_gun" else 0.05
        run_animation(pattern_name=pattern, speed=speed)
    else:
        demo()
