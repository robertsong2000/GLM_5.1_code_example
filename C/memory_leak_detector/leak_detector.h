#ifndef LEAK_DETECTOR_H
#define LEAK_DETECTOR_H

#include <stddef.h>

/*
 * 内存泄漏检测器
 *
 * 内存布局（每次 malloc(size) 实际分配）:
 *
 *   [header]              [用户数据 size 字节]           [canary]
 *   ┌──────────┐  ┌───┬───┬───┬─────────┐  ┌───────────┐
 *   │ alloc_t  │  │AB │AB │AB │ ...     │  │ 0xDEADBEEF│
 *   │ metadata │  │   │   │   │         │  │ (4 bytes)  │
 *   └──────────┘  └───┴───┴───┴─────────┘  └───────────┘
 *   ↑             ↑                         ↑
 *   real_ptr      returned ptr              canary position
 *
 * - 分配时用户区填充 0xAB
 * - 释放时用户区填充 0xCD
 * - canary 在释放时检查是否被覆盖（缓冲区溢出检测）
 */

#define CANARY_VALUE    0xDEADBEEFu
#define CANARY_SIZE     sizeof(unsigned int)
#define FILL_ALLOC      0xAB
#define FILL_FREE       0xCD
#define MAX_RECORDS     4096

/* 分配记录 */
typedef struct {
    void       *user_ptr;       /* 返回给用户的指针 */
    size_t      size;           /* 用户请求的大小 */
    const char *file;           /* 分配所在文件 */
    int         line;           /* 分配所在行号 */
    int         active;         /* 1=已分配未释放, 0=已释放/空 */
} alloc_record_t;

/* 核心函数 */
void  *debug_malloc(size_t size, const char *file, int line);
void   debug_free(void *ptr, const char *file, int line);
void   debug_report(void);

/* 替换宏 —— 在使用本头文件的编译单元中自动替换 malloc/free */
#define malloc(size)  debug_malloc((size), __FILE__, __LINE__)
#define free(ptr)     debug_free((ptr), __FILE__, __LINE__)

#endif /* LEAK_DETECTOR_H */
