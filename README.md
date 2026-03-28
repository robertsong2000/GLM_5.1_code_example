# GLM 5.1 Code Examples

算法与系统设计示例代码合集。

## 文件说明

| 文件 | 说明 | 时间复杂度 |
|------|------|-----------|
| `merge_k_sorted_lists.py` | 合并 K 个有序链表（最小堆） | O(N·logK) |
| `rate_limiter.py` | 限流器（滑动窗口 / 令牌桶） | O(1) 每次请求 |

### merge_k_sorted_lists.py

使用优先队列将 K 个升序链表合并为一个升序链表。

```python
from merge_k_sorted_lists import merge_k_lists, build_list, list_to_values

lists = [build_list([1,4,5]), build_list([1,3,4]), build_list([2,6])]
result = list_to_values(merge_k_lists(lists))
# [1, 1, 2, 3, 4, 4, 5, 6]
```

### rate_limiter.py

支持滑动窗口和令牌桶两种限流算法，特性：

- 多用户隔离（不同用户独立计数）
- 线程安全
- 内存过期自动清理

```python
from rate_limiter import RateLimiter

rl = RateLimiter(algorithm="sliding_window", max_requests=100, window_seconds=60)
rl.allow_request("user_123")  # True or False
```

## 运行

```bash
python3 merge_k_sorted_lists.py
python3 rate_limiter.py
```

## 环境

- Python 3.10+
- 无第三方依赖
