# GLM 5.1 Code Examples

算法、前端、游戏与系统编程示例代码合集。

## 目录结构

```
├── merge_k_sorted_lists.py      # 合并 K 个有序链表（最小堆）
├── rate_limiter.py              # 限流器（滑动窗口 / 令牌桶）
├── C/
│   ├── http_server/             # 多线程 HTTP 服务器
│   └── memory_leak_detector/    # 内存泄漏检测器
├── frontend/
│   ├── debounce_search/         # 防抖搜索组件
│   ├── glassmorphism_card/      # 玻璃拟态卡片
│   ├── kanban_board/            # 拖拽看板
│   ├── particle_canvas/         # 粒子动画系统
│   └── virtual_list/            # 虚拟滚动列表
└── game/
    ├── angry_birds/             # 愤怒的小鸟
    ├── breakout/                # 打砖块
    └── platformer/              # 平台跳跃冒险
```

## Python 算法

### merge_k_sorted_lists.py

使用优先队列将 K 个升序链表合并为一个升序链表（O(N·logK)）。

```python
from merge_k_sorted_lists import merge_k_lists, build_list, list_to_values

lists = [build_list([1,4,5]), build_list([1,3,4]), build_list([2,6])]
result = list_to_values(merge_k_lists(lists))
# [1, 1, 2, 3, 4, 4, 5, 6]
```

### rate_limiter.py

支持滑动窗口和令牌桶两种限流算法，O(1) 每次请求。特性：

- 多用户隔离（不同用户独立计数）
- 线程安全
- 内存过期自动清理

```python
from rate_limiter import RateLimiter

rl = RateLimiter(algorithm="sliding_window", max_requests=100, window_seconds=60)
rl.allow_request("user_123")  # True or False
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

## 游戏项目

所有游戏均为 HTML5 Canvas + JS，浏览器直接打开即可游玩。

| 游戏 | 说明 |
|------|------|
| **angry_birds** | 愤怒的小鸟 — 弹弓发射、物理碰撞 |
| **breakout** | 打砖块 — 粒子特效、多关卡 |
| **platformer** | 平台跳跃 — 二段跳、移动平台、收集要素 |

## 运行

```bash
# Python 脚本
python3 merge_k_sorted_lists.py
python3 rate_limiter.py

# C 项目
cd C/<project> && make && ./<executable>

# 前端 / 游戏
# 浏览器打开对应目录下的 index.html
```

## 环境

- Python 3.10+（无第三方依赖）
- GCC（C 项目）
- 现代浏览器（前端 / 游戏项目）
