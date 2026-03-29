"""
LRU Cache — O(1) get/put 的最近最少使用缓存

核心数据结构：双向链表 + 哈希表
- 双向链表维护访问顺序（最近访问在头部，最久未访问在尾部）
- 哈希表实现 O(1) 的键值查找

演示特性：
  • get / put 均为 O(1)
  • 容量满时自动淘汰最久未使用的条目
  • 支持 delete / clear 操作
  • 线程安全（可选）
  • 可视化缓存状态
"""

from __future__ import annotations
import threading
from typing import Any, Optional


class _Node:
    """双向链表节点"""
    __slots__ = ("key", "value", "prev", "next")

    def __init__(self, key: int, value: Any):
        self.key = key
        self.value = value
        self.prev: Optional[_Node] = None
        self.next: Optional[_Node] = None


class LRUCache:
    """
    线程安全的 LRU 缓存。

    >>> cache = LRUCache(capacity=3)
    >>> cache.put(1, "a")
    >>> cache.put(2, "b")
    >>> cache.put(3, "c")
    >>> cache.get(1)          # 访问 key=1，移到最前
    'a'
    >>> cache.put(4, "d")     # 容量满，淘汰最久未用的 key=2
    >>> cache.get(2) is None
    True
    """

    def __init__(self, capacity: int, thread_safe: bool = False):
        if capacity <= 0:
            raise ValueError("capacity must be > 0")
        self._capacity = capacity
        self._map: dict[int, _Node] = {}
        # 哨兵节点简化边界操作
        self._head = _Node(0, None)  # 最近使用
        self._tail = _Node(0, None)  # 最久未用
        self._head.next = self._tail
        self._tail.prev = self._head
        self._lock = threading.Lock() if thread_safe else None
        self._hits = 0
        self._misses = 0

    # ── 公开 API ───────────────────────────────────────────

    def get(self, key: int) -> Any:
        """获取值，存在则移到链表头部并返回值，否则返回 None。"""
        with self._lock or _dummy_context():
            node = self._map.get(key)
            if node is None:
                self._misses += 1
                return None
            self._move_to_head(node)
            self._hits += 1
            return node.value

    def put(self, key: int, value: Any) -> None:
        """插入/更新键值对。容量满时淘汰尾部节点。"""
        with self._lock or _dummy_context():
            node = self._map.get(key)
            if node:
                node.value = value
                self._move_to_head(node)
            else:
                new_node = _Node(key, value)
                self._map[key] = new_node
                self._add_to_head(new_node)
                if len(self._map) > self._capacity:
                    removed = self._remove_tail()
                    del self._map[removed.key]

    def delete(self, key: int) -> bool:
        """删除指定键，返回是否成功。"""
        with self._lock or _dummy_context():
            node = self._map.get(key)
            if node is None:
                return False
            self._remove_node(node)
            del self._map[key]
            return True

    def clear(self) -> None:
        """清空缓存。"""
        with self._lock or _dummy_context():
            self._map.clear()
            self._head.next = self._tail
            self._tail.prev = self._head
            self._hits = 0
            self._misses = 0

    @property
    def size(self) -> int:
        return len(self._map)

    @property
    def hit_rate(self) -> float:
        total = self._hits + self._misses
        return self._hits / total if total else 0.0

    # ── 链表操作（私有）───────────────────────────────────

    def _add_to_head(self, node: _Node) -> None:
        node.prev = self._head
        node.next = self._head.next
        self._head.next.prev = node
        self._head.next = node

    def _remove_node(self, node: _Node) -> None:
        node.prev.next = node.next
        node.next.prev = node.prev

    def _move_to_head(self, node: _Node) -> None:
        self._remove_node(node)
        self._add_to_head(node)

    def _remove_tail(self) -> _Node:
        node = self._tail.prev
        self._remove_node(node)
        return node

    # ── 可视化 ─────────────────────────────────────────────

    def visualize(self) -> str:
        """返回缓存状态的字符串表示（从最近到最久）。"""
        items: list[str] = []
        cur = self._head.next
        while cur is not self._tail:
            items.append(f"{cur.key}:{cur.value}")
            cur = cur.next
        arrow = " <-> ".join(items) if items else "(empty)"
        return f"[HEAD <-> {arrow} <-> TAIL]  size={self.size}/{self._capacity}"


class _dummy_context:
    """配合可选锁的空上下文管理器。"""
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass


# ── 演示 ──────────────────────────────────────────────────

def demo():
    print("=" * 60)
    print("  LRU Cache 演示")
    print("=" * 60)

    cache = LRUCache(capacity=3)
    print(f"\n初始化: capacity=3")
    print(cache.visualize())

    # 基本操作
    print("\n--- 基本操作 ---")
    cache.put(1, "Apple")
    print(f"put(1, 'Apple')  → {cache.visualize()}")
    cache.put(2, "Banana")
    print(f"put(2, 'Banana') → {cache.visualize()}")
    cache.put(3, "Cherry")
    print(f"put(3, 'Cherry') → {cache.visualize()}")

    # 访问操作
    print("\n--- 访问 key=1 ---")
    val = cache.get(1)
    print(f"get(1) = {val!r}   → {cache.visualize()}")

    # 淘汰操作
    print("\n--- 淘汰测试 ---")
    cache.put(4, "Durian")
    print(f"put(4, 'Durian')  → 淘汰最久未用的 key=2")
    print(f"  {cache.visualize()}")
    print(f"  get(2) = {cache.get(2)!r}  (已淘汰)")

    # 更新操作
    print("\n--- 更新操作 ---")
    cache.put(1, "Apricot")
    print(f"put(1, 'Apricot') → {cache.visualize()}")

    # 删除操作
    print("\n--- 删除操作 ---")
    cache.delete(3)
    print(f"delete(3)         → {cache.visualize()}")

    # 统计
    print(f"\n--- 统计 ---")
    print(f"  size={cache.size}, hit_rate={cache.hit_rate:.1%}")
    print(f"  hits={cache._hits}, misses={cache._misses}")

    # 命中率测试
    print("\n" + "=" * 60)
    print("  命中率压力测试")
    print("=" * 60)
    cache2 = LRUCache(capacity=10)
    import random
    random.seed(42)
    for _ in range(10000):
        key = random.randint(1, 20)  # 20 个键，容量 10
        if random.random() < 0.6:
            cache2.get(key)
        else:
            cache2.put(key, f"val_{key}")
    print(f"\ncapacity=10, keys=1..20, 10000 次操作")
    print(f"  hits={cache2._hits}, misses={cache2._misses}")
    print(f"  hit_rate={cache2.hit_rate:.1%}")


if __name__ == "__main__":
    demo()
