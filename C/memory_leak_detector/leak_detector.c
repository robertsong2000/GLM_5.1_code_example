/*
 * 内存泄漏检测器 — 实现文件
 *
 * 重要: 系统头文件必须在本文件的头文件之前 include，
 *       否则 malloc/free 宏会破坏系统头文件的声明。
 */

/* 1) 先包含所有系统头文件 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* 2) 再包含我们自己的头文件（会 #define malloc / free） */
#include "leak_detector.h"

/* 3) 在本文件内部取消宏，使用真正的 libc malloc/free */
#undef malloc
#undef free

/* ── 全局分配表 ───────────────────────────────────────── */
static alloc_record_t g_records[MAX_RECORDS];
static int            g_count = 0;
static size_t         g_total_allocated = 0;
static size_t         g_total_freed     = 0;

/* ── 内部辅助 ─────────────────────────────────────────── */

/* 从 user_ptr 读取 canary（紧贴用户区末尾之后） */
static unsigned int *canary_ptr(void *user_ptr, size_t size)
{
    return (unsigned int *)((char *)user_ptr + size);
}

/* 在分配表中查找活跃记录 */
static alloc_record_t *find_active(void *user_ptr)
{
    for (int i = 0; i < g_count; i++) {
        if (g_records[i].active && g_records[i].user_ptr == user_ptr)
            return &g_records[i];
    }
    return NULL;
}

/* 在分配表中查找已释放记录（反向查找最近的） */
static alloc_record_t *find_freed(void *user_ptr)
{
    for (int i = g_count - 1; i >= 0; i--) {
        if (g_records[i].user_ptr == user_ptr && !g_records[i].active)
            return &g_records[i];
    }
    return NULL;
}

/* ── 公共 API ─────────────────────────────────────────── */

void *debug_malloc(size_t size, const char *file, int line)
{
    if (size == 0) {
        fprintf(stderr, "[LEAK] %s:%d — malloc(0) 被调用，已忽略\n", file, line);
        return NULL;
    }

    if (g_count >= MAX_RECORDS) {
        fprintf(stderr, "[LEAK] 分配表已满 (%d)，无法跟踪更多分配\n", MAX_RECORDS);
        return NULL;
    }

    /*
     * 实际堆布局:
     *
     *   [ 用户数据 size 字节 ] [ canary 4 字节 ]
     *   ↑
     *   user_ptr (= real_ptr)
     *
     * 元数据存放在全局表 g_records 中，不占用堆空间。
     */
    size_t real_size = size + CANARY_SIZE;
    void  *real_ptr  = malloc(real_size);  /* 真正的 libc malloc */
    if (!real_ptr) {
        fprintf(stderr, "[LEAK] %s:%d — malloc 失败 (请求 %zu 字节)\n",
                file, line, size);
        return NULL;
    }

    void *user_ptr = real_ptr;

    /* 填充分配模式 0xAB */
    memset(user_ptr, FILL_ALLOC, size);

    /* 在末尾写入 canary */
    *canary_ptr(user_ptr, size) = CANARY_VALUE;

    /* 登记到全局表 */
    alloc_record_t *rec = &g_records[g_count++];
    rec->user_ptr = user_ptr;
    rec->size     = size;
    rec->file     = file;
    rec->line     = line;
    rec->active   = 1;

    g_total_allocated += size;

    return user_ptr;
}

void debug_free(void *ptr, const char *file, int line)
{
    if (!ptr) {
        /* free(NULL) 合法，静默忽略 */
        return;
    }

    /* 优先查找活跃记录（处理地址复用的情况） */
    alloc_record_t *rec = find_active(ptr);
    if (rec) {
        /* 找到活跃记录，正常释放流程 */
    } else {
        /* 没有活跃记录，检查是否是 double free 或无效地址 */
        alloc_record_t *freed = find_freed(ptr);
        if (freed) {
            fprintf(stderr, "[LEAK] %s:%d — 重复释放（double free）！"
                    "指针 %p 已在之前释放\n"
                    "    原分配位置: %s:%d\n",
                    file, line, ptr, freed->file, freed->line);
        } else {
            fprintf(stderr, "[LEAK] %s:%d — 释放未分配的地址 %p！\n",
                    file, line, ptr);
        }
        return;
    }

    /* ── 缓冲区溢出检测：检查 canary ── */
    unsigned int canary = *canary_ptr(rec->user_ptr, rec->size);
    if (canary != CANARY_VALUE) {
        fprintf(stderr, "[LEAK] %s:%d — 缓冲区溢出检测！canary 被覆盖\n"
                "    分配位置: %s:%d (大小 %zu)\n"
                "    期望: 0x%08X  实际: 0x%08X\n",
                file, line,
                rec->file, rec->line, rec->size,
                CANARY_VALUE, canary);
    }

    /* 填充释放模式 0xCD */
    memset(rec->user_ptr, FILL_FREE, rec->size);

    /* 标记为已释放 */
    rec->active = 0;
    g_total_freed += rec->size;

    /* 调用真正的 libc free */
    free(rec->user_ptr);
}

void debug_report(void)
{
    size_t leak_bytes = 0;
    int    leak_count = 0;

    printf("\n");
    printf("============================================================\n");
    printf("          内存泄漏检测报告 (Memory Leak Report)\n");
    printf("============================================================\n");
    printf("  总分配次数: %-10d  总分配字节: %zu\n", g_count, g_total_allocated);
    printf("  总释放字节: %zu\n", g_total_freed);
    printf("------------------------------------------------------------\n");

    int has_leaks = 0;
    for (int i = 0; i < g_count; i++) {
        if (g_records[i].active) {
            if (!has_leaks) {
                printf("  [!] 未释放的内存块:\n");
                has_leaks = 1;
            }
            leak_bytes += g_records[i].size;
            leak_count++;
            printf("      %s:%-4d  ->  %zu 字节  (地址 %p)\n",
                   g_records[i].file, g_records[i].line,
                   g_records[i].size, (void *)g_records[i].user_ptr);
        }
    }

    if (!has_leaks) {
        printf("  [OK] 没有检测到内存泄漏\n");
    }

    printf("------------------------------------------------------------\n");
    printf("  泄漏块数: %d    泄漏总字节: %zu\n", leak_count, leak_bytes);
    printf("============================================================\n");
    printf("\n");
}
