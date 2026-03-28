"""
弹簧质点物理模拟系统 (Spring-Mass Physics Simulation)

基于 Verlet 积分的弹簧质点系统，包含多种演示场景。

操作说明:
  鼠标左键拖拽  — 拖动质点
  鼠标右键点击  — 固定/释放质点
  1~4 键        — 切换场景
  R 键          — 重置当前场景
  空格键         — 暂停/继续
  G 键          — 开关重力
  ESC           — 退出
"""

import pygame
import sys
import math
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

# ============================================================
# 全局常量
# ============================================================
WIDTH, HEIGHT = 1200, 800
FPS = 60
SUB_STEPS = 8  # 每帧物理子步数，越高越稳定
BG_COLOR = (18, 18, 24)
GRAVITY = pygame.math.Vector2(0, 980)  # 重力加速度 (px/s²)

# 颜色定义
COLOR_NODE = (220, 220, 240)
COLOR_NODE_FIXED = (255, 80, 80)
COLOR_NODE_HOVER = (80, 200, 255)
COLOR_SPRING = (100, 180, 255)
COLOR_SPRING_STRESSED = (255, 140, 60)
COLOR_TEXT = (180, 180, 200)
COLOR_HIGHLIGHT = (255, 220, 80)
COLOR_PANEL_BG = (30, 30, 42)


# ============================================================
# 物理对象
# ============================================================
class Node:
    """质点 — 使用 Verlet 积分"""

    __slots__ = (
        "pos", "old_pos", "acc", "mass",
        "fixed", "radius", "dragging",
    )

    def __init__(self, x: float, y: float, mass: float = 1.0, fixed: bool = False):
        self.pos = pygame.math.Vector2(x, y)
        self.old_pos = pygame.math.Vector2(x, y)
        self.acc = pygame.math.Vector2(0, 0)
        self.mass = mass
        self.fixed = fixed
        self.radius = max(4, min(12, int(mass * 6)))
        self.dragging = False

    def apply_force(self, force: pygame.math.Vector2):
        self.acc += force / self.mass

    def update(self, dt: float):
        if self.fixed or self.dragging:
            self.old_pos = pygame.math.Vector2(self.pos)
            self.acc = pygame.math.Vector2(0, 0)
            return
        # Verlet 积分: x_new = 2*x - x_old + a*dt²
        velocity = self.pos - self.old_pos
        # 全局阻尼 (0.995 ≈ 空气阻力)
        velocity *= 0.995
        new_pos = self.pos + velocity + self.acc * (dt * dt)
        self.old_pos = pygame.math.Vector2(self.pos)
        self.pos = new_pos
        self.acc = pygame.math.Vector2(0, 0)

        # 边界约束
        if self.pos.y > HEIGHT - 10:
            self.pos.y = HEIGHT - 10
        if self.pos.x < 10:
            self.pos.x = 10
        if self.pos.x > WIDTH - 10:
            self.pos.x = WIDTH - 10
        if self.pos.y < 10:
            self.pos.y = 10


class Spring:
    """弹簧约束"""

    __slots__ = ("a", "b", "rest_length", "stiffness", "damping", "tear_distance")

    def __init__(
        self,
        a: Node,
        b: Node,
        stiffness: float = 0.8,
        damping: float = 0.02,
        rest_length: Optional[float] = None,
        tear_distance: Optional[float] = None,
    ):
        self.a = a
        self.b = b
        self.rest_length = rest_length if rest_length else a.pos.distance_to(b.pos)
        self.stiffness = stiffness
        self.damping = damping
        # 超过此距离弹簧断裂（None 表示不会断裂）
        self.tear_distance = tear_distance

    @property
    def stretch_ratio(self) -> float:
        """当前拉伸比 (>1 拉伸, <1 压缩)"""
        dist = self.a.pos.distance_to(self.b.pos)
        return dist / self.rest_length if self.rest_length > 0 else 1.0

    @property
    def is_broken(self) -> bool:
        if self.tear_distance is None:
            return False
        return self.a.pos.distance_to(self.b.pos) > self.tear_distance


class CircleObstacle:
    """圆形障碍物，用于碰撞"""

    def __init__(self, x: float, y: float, radius: float):
        self.pos = pygame.math.Vector2(x, y)
        self.radius = radius

    def collide(self, node: Node):
        diff = node.pos - self.pos
        dist = diff.length()
        if dist < self.radius + node.radius and dist > 0:
            normal = diff / dist
            node.pos = self.pos + normal * (self.radius + node.radius)


# ============================================================
# 物理世界
# ============================================================
class PhysicsWorld:
    def __init__(self):
        self.nodes: List[Node] = []
        self.springs: List[Spring] = []
        self.obstacles: List[CircleObstacle] = []
        self.gravity_enabled = True

    def clear(self):
        self.nodes.clear()
        self.springs.clear()
        self.obstacles.clear()

    def add_node(self, x, y, mass=1.0, fixed=False) -> Node:
        node = Node(x, y, mass, fixed)
        self.nodes.append(node)
        return node

    def add_spring(self, a: Node, b: Node, **kwargs) -> Spring:
        spring = Spring(a, b, **kwargs)
        self.springs.append(spring)
        return spring

    def add_obstacle(self, x, y, radius) -> CircleObstacle:
        obs = CircleObstacle(x, y, radius)
        self.obstacles.append(obs)
        return obs

    def step(self, dt: float):
        sub_dt = dt / SUB_STEPS
        for _ in range(SUB_STEPS):
            # 施加重力
            if self.gravity_enabled:
                for node in self.nodes:
                    if not node.fixed and not node.dragging:
                        node.apply_force(GRAVITY * node.mass)

            # 弹簧约束求解 (基于位置的动力学方法)
            for spring in self.springs:
                if spring.is_broken:
                    continue
                diff = spring.b.pos - spring.a.pos
                dist = diff.length()
                if dist == 0:
                    continue
                # 位移修正
                error = dist - spring.rest_length
                correction = diff / dist * error * spring.stiffness

                # 速度阻尼
                vel_a = spring.a.pos - spring.a.old_pos
                vel_b = spring.b.pos - spring.b.old_pos
                relative_vel = vel_b - vel_a
                damping_correction = relative_vel * spring.damping

                if not spring.a.fixed and not spring.a.dragging:
                    if not spring.b.fixed and not spring.b.dragging:
                        spring.a.pos += correction * 0.5 - damping_correction * 0.5
                        spring.b.pos -= correction * 0.5 + damping_correction * 0.5
                    else:
                        spring.a.pos += correction - damping_correction
                elif not spring.b.fixed and not spring.b.dragging:
                    spring.b.pos -= correction + damping_correction

            # Verlet 积分更新
            for node in self.nodes:
                node.update(sub_dt)

            # 障碍物碰撞
            for obs in self.obstacles:
                for node in self.nodes:
                    if not node.fixed:
                        obs.collide(node)

        # 移除断裂的弹簧
        self.springs = [s for s in self.springs if not s.is_broken]


# ============================================================
# 场景构建器
# ============================================================
def scene_pendulum(world: PhysicsWorld):
    """场景1: 弹簧摆 — 单弹簧 + 重球"""
    world.clear()
    anchor = world.add_node(300, 150, mass=1.0, fixed=True)
    ball = world.add_node(450, 350, mass=2.0)
    world.add_spring(anchor, ball, stiffness=0.5, damping=0.01)

    # 多个弹簧摆
    anchor2 = world.add_node(600, 120, fixed=True)
    ball2 = world.add_node(700, 320, mass=1.5)
    world.add_spring(anchor2, ball2, stiffness=0.3, damping=0.01)

    ball3 = world.add_node(800, 280, mass=2.5)
    world.add_spring(ball2, ball3, stiffness=0.6, damping=0.01)

    # 弹簧链
    anchor3 = world.add_node(950, 100, fixed=True)
    prev = anchor3
    for i in range(6):
        node = world.add_node(950 + i * 15, 100 + (i + 1) * 60, mass=0.8)
        world.add_spring(prev, node, stiffness=0.7, damping=0.02)
        prev = node


def scene_bridge(world: PhysicsWorld):
    """场景2: 悬索桥"""
    world.clear()
    cols = 20
    spacing = 45
    start_x = 100
    y_top = 200
    y_bot = 280

    top_nodes = []
    bot_nodes = []

    for i in range(cols):
        fixed = i == 0 or i == cols - 1
        top = world.add_node(start_x + i * spacing, y_top, mass=1.0, fixed=fixed)
        bot = world.add_node(start_x + i * spacing, y_bot, mass=1.5, fixed=fixed)
        top_nodes.append(top)
        bot_nodes.append(bot)

    for i in range(cols - 1):
        # 水平弹簧
        world.add_spring(top_nodes[i], top_nodes[i + 1], stiffness=0.8, damping=0.03)
        world.add_spring(bot_nodes[i], bot_nodes[i + 1], stiffness=0.8, damping=0.03)
        # 竖直弹簧
        world.add_spring(top_nodes[i], bot_nodes[i], stiffness=0.9, damping=0.02)
        # 剪切弹簧 (对角线)
        world.add_spring(top_nodes[i], bot_nodes[i + 1], stiffness=0.4, damping=0.02)
        world.add_spring(bot_nodes[i], top_nodes[i + 1], stiffness=0.4, damping=0.02)

    world.add_spring(top_nodes[-1], bot_nodes[-1], stiffness=0.9, damping=0.02)


def scene_cloth(world: PhysicsWorld):
    """场景3: 布料网格"""
    world.clear()
    rows, cols = 15, 20
    spacing = 28
    start_x = 200
    start_y = 80

    grid = [[None] * cols for _ in range(rows)]

    for r in range(rows):
        for c in range(cols):
            fixed = (r == 0 and c % 4 == 0)
            node = world.add_node(
                start_x + c * spacing,
                start_y + r * spacing,
                mass=0.6,
                fixed=fixed,
            )
            grid[r][c] = node

    for r in range(rows):
        for c in range(cols):
            # 结构弹簧 (水平)
            if c < cols - 1:
                world.add_spring(grid[r][c], grid[r][c + 1], stiffness=0.7, damping=0.02)
            # 结构弹簧 (垂直)
            if r < rows - 1:
                world.add_spring(grid[r][c], grid[r + 1][c], stiffness=0.7, damping=0.02)
            # 剪切弹簧 (对角线)
            if r < rows - 1 and c < cols - 1:
                world.add_spring(grid[r][c], grid[r + 1][c + 1], stiffness=0.3, damping=0.01)
            if r < rows - 1 and c > 0:
                world.add_spring(grid[r][c], grid[r + 1][c - 1], stiffness=0.3, damping=0.01)
            # 弯曲弹簧 (隔一个)
            if c < cols - 2:
                world.add_spring(grid[r][c], grid[r][c + 2], stiffness=0.2, damping=0.01)
            if r < rows - 2:
                world.add_spring(grid[r][c], grid[r + 2][c], stiffness=0.2, damping=0.01)

    # 添加障碍球
    world.add_obstacle(500, 450, 80)


def scene_softbody(world: PhysicsWorld):
    """场景4: 软体球 — 可撕裂"""
    world.clear()

    # 软体球 1
    _create_softbody(world, 250, 200, radius=80, num_points=16, mass=1.0, stiffness=0.6)

    # 软体球 2
    _create_softbody(world, 600, 150, radius=60, num_points=14, mass=1.5, stiffness=0.5)

    # 弹性绳索 (可撕裂)
    anchor = world.add_node(900, 80, fixed=True)
    prev = anchor
    for i in range(10):
        node = world.add_node(900 + i * 30, 80 + (i + 1) * 40, mass=1.0)
        world.add_spring(
            prev, node,
            stiffness=0.5, damping=0.02,
            tear_distance=prev.pos.distance_to(node.pos) * 4,
        )
        prev = node

    # 地面障碍
    world.add_obstacle(400, 600, 60)
    world.add_obstacle(700, 550, 50)


def _create_softbody(
    world: PhysicsWorld, cx, cy, radius, num_points, mass, stiffness
):
    """创建一个软体圆形"""
    center = world.add_node(cx, cy, mass=mass * 2)
    ring = []
    for i in range(num_points):
        angle = 2 * math.pi * i / num_points
        x = cx + radius * math.cos(angle)
        y = cy + radius * math.sin(angle)
        node = world.add_node(x, y, mass=mass)
        ring.append(node)
        # 径向弹簧
        world.add_spring(center, node, stiffness=stiffness, damping=0.02)

    # 环形弹簧
    for i in range(num_points):
        j = (i + 1) % num_points
        world.add_spring(ring[i], ring[j], stiffness=stiffness * 1.2, damping=0.02)
        # 隔一个连接 (增加刚性)
        k = (i + 2) % num_points
        world.add_spring(ring[i], ring[k], stiffness=stiffness * 0.5, damping=0.01)


# ============================================================
# 渲染器
# ============================================================
class Renderer:
    def __init__(self, screen: pygame.Surface):
        self.screen = screen
        self.font = pygame.font.SysFont("menlo", 14)
        self.title_font = pygame.font.SysFont("menlo", 18, bold=True)
        self.hovered_node: Optional[Node] = None
        self.dragged_node: Optional[Node] = None
        self.mouse_pos = pygame.math.Vector2(0, 0)

    def draw_spring_coil(self, a_pos, b_pos, stretch: float, num_coils=12, amplitude=8):
        """绘制弹簧线圈效果"""
        diff = b_pos - a_pos
        dist = diff.length()
        if dist < 1:
            return

        direction = diff / dist
        normal = pygame.math.Vector2(-direction.y, direction.x)

        # 根据拉伸调整颜色
        if stretch > 1.5:
            color = COLOR_SPRING_STRESSED
        else:
            t = min(1.0, max(0.0, (stretch - 0.8) / 0.7))
            r = int(COLOR_SPRING[0] + (COLOR_SPRING_STRESSED[0] - COLOR_SPRING[0]) * t)
            g = int(COLOR_SPRING[1] + (COLOR_SPRING_STRESSED[1] - COLOR_SPRING[1]) * t)
            b = int(COLOR_SPRING[2] + (COLOR_SPRING_STRESSED[2] - COLOR_SPRING[2]) * t)
            color = (r, g, b)

        # 弹簧端点留白
        margin = 12
        if dist < margin * 2:
            pygame.draw.line(self.screen, color, a_pos, b_pos, 2)
            return

        start = a_pos + direction * margin
        end = b_pos - direction * margin
        coil_len = dist - 2 * margin

        points = [a_pos, start]
        for i in range(num_coils + 1):
            t = i / num_coils
            pos = start + (end - start) * t
            wave = math.sin(t * num_coils * math.pi) * amplitude
            pos = pos + normal * wave
            points.append(pos)
        points.append(end)
        points.append(b_pos)

        int_points = [(int(p.x), int(p.y)) for p in points]
        if len(int_points) >= 2:
            pygame.draw.lines(self.screen, color, False, int_points, 2)

    def draw_node(self, node: Node):
        is_hovered = (node == self.hovered_node)
        if node.fixed:
            color = COLOR_NODE_FIXED
            # 画固定标记（小三角）
            size = node.radius + 3
            points = [
                (int(node.pos.x), int(node.pos.y - size)),
                (int(node.pos.x - size), int(node.pos.y + size)),
                (int(node.pos.x + size), int(node.pos.y + size)),
            ]
            pygame.draw.polygon(self.screen, color, points)
            pygame.draw.polygon(self.screen, (255, 255, 255), points, 2)
        elif is_hovered:
            pygame.draw.circle(self.screen, COLOR_NODE_HOVER, (int(node.pos.x), int(node.pos.y)), node.radius + 3)
            pygame.draw.circle(self.screen, (255, 255, 255), (int(node.pos.x), int(node.pos.y)), node.radius, 2)
        else:
            pygame.draw.circle(self.screen, COLOR_NODE, (int(node.pos.x), int(node.pos.y)), node.radius)
            pygame.draw.circle(
                self.screen, (120, 120, 140),
                (int(node.pos.x), int(node.pos.y)), node.radius, 1,
            )

    def draw_obstacle(self, obs: CircleObstacle):
        pos = (int(obs.pos.x), int(obs.pos.y))
        pygame.draw.circle(self.screen, (50, 55, 70), pos, int(obs.radius))
        pygame.draw.circle(self.screen, (80, 85, 100), pos, int(obs.radius), 2)
        # 内部纹理
        pygame.draw.circle(self.screen, (60, 65, 80), pos, int(obs.radius * 0.7), 1)

    def draw_world(self, world: PhysicsWorld, scene_name: str, paused: bool):
        self.screen.fill(BG_COLOR)

        # 绘制障碍物
        for obs in world.obstacles:
            self.draw_obstacle(obs)

        # 绘制弹簧
        for spring in world.springs:
            self.draw_spring_coil(
                spring.a.pos, spring.b.pos,
                spring.stretch_ratio,
            )

        # 绘制质点
        for node in world.nodes:
            self.draw_node(node)

        # 绘制拖拽线
        if self.dragged_node:
            pygame.draw.line(
                self.screen, COLOR_HIGHLIGHT,
                (int(self.dragged_node.pos.x), int(self.dragged_node.pos.y)),
                (int(self.mouse_pos.x), int(self.mouse_pos.y)),
                1,
            )

        # 信息面板
        self._draw_info_panel(world, scene_name, paused)

    def _draw_info_panel(self, world: PhysicsWorld, scene_name: str, paused: bool):
        panel_w, panel_h = 260, 200
        panel_x = WIDTH - panel_w - 15
        panel_y = 15

        # 半透明背景
        panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        panel_surf.fill((*COLOR_PANEL_BG, 200))
        self.screen.blit(panel_surf, (panel_x, panel_y))
        pygame.draw.rect(self.screen, (60, 60, 80), (panel_x, panel_y, panel_w, panel_h), 1)

        title = self.title_font.render(scene_name, True, COLOR_HIGHLIGHT)
        self.screen.blit(title, (panel_x + 10, panel_y + 10))

        status = "PAUSED" if paused else "RUNNING"
        status_color = (255, 100, 100) if paused else (100, 255, 100)

        lines = [
            (f"Status: {status}", status_color),
            (f"Gravity: {'ON' if world.gravity_enabled else 'OFF'}", COLOR_TEXT),
            (f"Nodes: {len(world.nodes)}", COLOR_TEXT),
            (f"Springs: {len(world.springs)}", COLOR_TEXT),
            ("", COLOR_TEXT),
            ("Left-drag: Move node", (140, 140, 160)),
            ("Right-click: Pin/Unpin", (140, 140, 160)),
            ("1-4: Switch scene", (140, 140, 160)),
            ("R: Reset  Space: Pause", (140, 140, 160)),
            ("G: Toggle gravity", (140, 140, 160)),
        ]

        for i, (text, color) in enumerate(lines):
            if text:
                surf = self.font.render(text, True, color)
                self.screen.blit(surf, (panel_x + 10, panel_y + 36 + i * 16))

    def find_node_at(self, pos: pygame.math.Vector2, max_dist=20) -> Optional[Node]:
        """找到鼠标位置最近的质点"""
        best = None
        best_dist = max_dist
        for node in self.nodes_ref:
            d = (pygame.math.Vector2(node.pos.x, node.pos.y) - pos).length()
            if d < best_dist:
                best_dist = d
                best = node
        return best


# ============================================================
# 主程序
# ============================================================
def main():
    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("Spring-Mass Physics Simulation | 弹簧质点物理模拟")
    clock = pygame.time.Clock()

    world = PhysicsWorld()
    renderer = Renderer(screen)

    scenes = {
        1: ("Scene 1: Spring Pendulins (弹簧摆)", scene_pendulum),
        2: ("Scene 2: Suspension Bridge (悬索桥)", scene_bridge),
        3: ("Scene 3: Cloth Grid (布料网格)", scene_cloth),
        4: ("Scene 4: Soft Body (软体+撕裂)", scene_softbody),
    }
    current_scene = 1
    paused = False

    def load_scene(idx):
        nonlocal current_scene
        current_scene = idx
        scenes[idx][1](world)
        renderer.nodes_ref = world.nodes

    load_scene(1)

    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        dt = min(dt, 1.0 / 30)  # 限制最大 dt，防止爆炸

        # 事件处理
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4):
                    load_scene(event.key - pygame.K_0)
                elif event.key == pygame.K_r:
                    load_scene(current_scene)
                elif event.key == pygame.K_SPACE:
                    paused = not paused
                elif event.key == pygame.K_g:
                    world.gravity_enabled = not world.gravity_enabled

            elif event.type == pygame.MOUSEMOTION:
                renderer.mouse_pos = pygame.math.Vector2(event.pos)
                renderer.hovered_node = renderer.find_node_at(renderer.mouse_pos)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                mouse = pygame.math.Vector2(event.pos)
                node = renderer.find_node_at(mouse)
                if node:
                    if event.button == 1:  # 左键拖拽
                        renderer.dragged_node = node
                        node.dragging = True
                    elif event.button == 3:  # 右键固定/释放
                        node.fixed = not node.fixed

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button == 1 and renderer.dragged_node:
                    renderer.dragged_node.dragging = False
                    renderer.dragged_node = None

        # 拖拽更新
        if renderer.dragged_node:
            renderer.dragged_node.pos = pygame.math.Vector2(renderer.mouse_pos)
            renderer.dragged_node.old_pos = pygame.math.Vector2(renderer.mouse_pos)

        # 物理步进
        if not paused:
            world.step(dt)

        # 渲染
        scene_name = scenes[current_scene][0]
        renderer.draw_world(world, scene_name, paused)
        pygame.display.flip()

    pygame.quit()
    sys.exit()


if __name__ == "__main__":
    main()
