# GLM 5.1 Code Examples

算法、前端、游戏与系统编程示例代码合集。

## 目录结构

```
├── python/
│   ├── merge_k_sorted_lists/    # 合并 K 个有序链表（最小堆）
│   ├── rate_limiter/            # 限流器（滑动窗口 / 令牌桶）
│   ├── markdown_parser/         # Markdown 解析器
│   ├── lru_cache/               # LRU 缓存（双向链表 + 哈希表）
│   ├── expression_evaluator/    # 表达式解析求值器（递归下降解析器）
│   └── game_of_life/            # Conway 生命游戏（细胞自动机）
├── C/
│   ├── http_server/             # 多线程 HTTP 服务器
│   ├── memory_leak_detector/    # 内存泄漏检测器
│   └── tetris/                  # 终端俄罗斯方块
├── frontend/
│   ├── debounce_search/         # 防抖搜索组件
│   ├── glassmorphism_card/      # 玻璃拟态卡片
│   ├── kanban_board/            # 拖拽看板
│   ├── particle_canvas/         # 粒子动画系统
│   ├── virtual_list/            # 虚拟滚动列表
│   ├── poetry_card/             # 诗词卡片
│   ├── audio_visualizer/        # 音频可视化（Web Audio API）
│   └── markdown_editor/         # Markdown 实时编辑器
├── game/
│   ├── angry_birds/             # 愤怒的小鸟
│   ├── breakout/                # 打砖块
│   ├── platformer/              # 平台跳跃冒险
│   ├── spring_mass/             # 弹簧质点物理模拟
│   └── snake/                   # 贪吃蛇
└── go/
    ├── todo-cli/                # 命令行待办工具
    ├── log-analyzer/            # 日志分析器
    └── load-tester/             # HTTP 压力测试工具
```

## Python 项目

### merge_k_sorted_lists.py

使用优先队列将 K 个升序链表合并为一个升序链表（O(N·logK)）。

```python
from merge_k_sorted_lists import merge_k_lists, build_list, list_to_values

lists = [build_list([1,4,5]), build_list([1,3,4]), build_list([2,6])]
result = list_to_values(merge_k_lists(lists))
# [1, 1, 2, 3, 4, 4, 5, 6]
```

### rate_limiter.py

支持滑动窗口和令牌桶两种限流算法，O(1) 每次请求。

```python
from rate_limiter import RateLimiter

rl = RateLimiter(algorithm="sliding_window", max_requests=100, window_seconds=60)
rl.allow_request("user_123")  # True or False
```

### lru_cache.py

双向链表 + 哈希表实现 O(1) 的 LRU 缓存，支持线程安全、命中率统计和状态可视化。

```python
from lru_cache import LRUCache

cache = LRUCache(capacity=3)
cache.put(1, "a")
cache.put(2, "b")
cache.get(1)          # "a" → 移到最前
cache.put(3, "c")
cache.put(4, "d")     # 淘汰 key=2
cache.visualize()     # [HEAD <-> 4:d <-> 1:a <-> 3:c <-> TAIL]
```

### expression_evaluator.py

递归下降解析器，将字符串表达式解析为 AST 并求值。支持变量赋值、函数调用。

```python
from expression_evaluator import evaluate

evaluate("1 + 2 * 3")           # [7.0]
evaluate("x = 10; x ** 2 + 1")  # [10.0, 101.0]
evaluate("sqrt(144) + sin(PI/2)") # [13.0]
```

### game_of_life.py

Conway 生命游戏，支持 10 种经典图案和终端动画。

```bash
python3 game_of_life.py              # 静态演示
python3 game_of_life.py gosper_gun   # 高斯帕滑翔机枪
python3 game_of_life.py pulsar       # 脉冲星
```

## C 语言项目

### C/http_server — 多线程 HTTP 服务器

C 语言实现的简易多线程 HTTP 服务器，支持静态文件服务和 API 路由。

```bash
cd C/http_server && make && ./http_server
```

### C/memory_leak_detector — 内存泄漏检测器

通过重载 malloc/free 检测内存问题，输出未释放内存的分配信息。

```bash
cd C/memory_leak_detector && make && ./test_leak
```

## 前端项目

所有前端项目均为纯 HTML/CSS/JS，浏览器直接打开 `index.html` 即可运行。

| 项目 | 说明 |
|------|------|
| **debounce_search** | 实时搜索组件，包含防抖功能和骨架屏 |
| **glassmorphism_card** | 玻璃拟态卡片，鼠标跟随 3D 变换效果 |
| **kanban_board** | 拖拽式看板，支持卡片在列间移动 |
| **particle_canvas** | Canvas 粒子动画，星座连线效果 |
| **virtual_list** | 虚拟滚动列表，优化大数据量渲染 |
| **poetry_card** | 古诗词卡片展示 |
| **audio_visualizer** | 音频可视化 — 麦克风/文件/演示音调，三种渲染模式 |
| **markdown_editor** | Markdown 实时编辑器 — 分栏预览、行号、工具栏 |

## 游戏项目

所有游戏均为 HTML5 Canvas + JS，浏览器直接打开即可游玩。

| 游戏 | 说明 |
|------|------|
| **angry_birds** | 愤怒的小鸟 — 弹弓发射、物理碰撞 |
| **breakout** | 打砖块 — 粒子特效、多关卡 |
| **platformer** | 平台跳跃 — 二段跳、移动平台、收集要素 |
| **snake** | 贪吃蛇 — 粒子特效、奖励食物、移动端支持 |

## 运行

```bash
# Python 脚本
cd python/<project>
python3 <script>.py

# C 项目
cd C/<project> && make && ./<executable>

# 前端 / 游戏
# 浏览器打开对应目录下的 index.html
```

## 环境

- Python 3.10+（无第三方依赖）
- GCC（C 项目）
- 现代浏览器（前端 / 游戏项目）
