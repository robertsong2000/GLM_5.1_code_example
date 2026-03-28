/*
 * 内存泄漏检测器 — 演示程序
 *
 * 编译: gcc -o demo main.c leak_detector.c
 * 运行: ./demo
 */
#include "leak_detector.h"
#include <stdio.h>
#include <string.h>

/* ── 测试 1: 正常分配与释放 ── */
static void test_normal(void)
{
    printf("=== 测试 1: 正常分配与释放 ===\n");
    int *arr = (int *)malloc(5 * sizeof(int));
    for (int i = 0; i < 5; i++) arr[i] = i * 10;
    printf("  arr = [%d, %d, %d, %d, %d]\n", arr[0], arr[1], arr[2], arr[3], arr[4]);
    free(arr);
    printf("  → 正常释放完成\n\n");
}

/* ── 测试 2: 内存泄漏（故意不释放） ── */
static void test_leak(void)
{
    printf("=== 测试 2: 内存泄漏（不释放） ===\n");
    char *str = (char *)malloc(100);
    strncpy(str, "Hello, Leak Detector!", 100);
    printf("  str = \"%s\"\n", str);
    printf("  → 故意不释放 str，将在报告中显示\n\n");
    /* 故意不 free(str); */
}

/* ── 测试 3: 多处泄漏 ── */
static void test_multi_leak(void)
{
    printf("=== 测试 3: 多处泄漏 ===\n");
    double *d1 = (double *)malloc(sizeof(double) * 10);
    double *d2 = (double *)malloc(sizeof(double) * 20);
    printf("  d1 = %p (80 字节)\n", (void *)d1);
    printf("  d2 = %p (160 字节)\n", (void *)d2);
    printf("  → 两处均不释放\n\n");
    /* 故意不释放 */
}

/* ── 测试 4: Double Free 检测 ── */
static void test_double_free(void)
{
    printf("=== 测试 4: 重复释放（Double Free） ===\n");
    int *p = (int *)malloc(sizeof(int));
    *p = 42;
    printf("  *p = %d\n", *p);
    free(p);
    printf("  第一次释放完成\n");
    free(p);  /* 第二次释放 — 应该被检测到 */
    printf("\n");
}

/* ── 测试 5: 释放未分配的地址 ── */
static void test_invalid_free(void)
{
    printf("=== 测试 5: 释放未分配的地址 ===\n");
    int stack_var = 123;
    free(&stack_var);  /* 释放栈变量 — 应该被检测到 */
    printf("\n");
}

/* ── 测试 6: 缓冲区溢出检测 ── */
static void test_buffer_overflow(void)
{
    printf("=== 测试 6: 缓冲区溢出（Canary 覆盖检测） ===\n");
    char *buf = (char *)malloc(8);  /* 分配 8 字节 */
    printf("  分配 8 字节缓冲区\n");

    /* 故意越界写入，覆盖 canary */
    printf("  故意写入 12 字节（越界 4 字节）...\n");
    for (int i = 0; i < 12; i++) {
        buf[i] = 'X';
    }

    free(buf);  /* 释放时应检测到 canary 被覆盖 */
    printf("\n");
}

/* ── 测试 7: 验证填充模式 ── */
static void test_fill_pattern(void)
{
    printf("=== 测试 7: 填充模式验证 ===\n");
    unsigned char *mem = (unsigned char *)malloc(16);

    /* 检查分配后的填充是否为 0xAB */
    printf("  分配后内存内容 (应为 0xAB): ");
    int all_ab = 1;
    for (int i = 0; i < 16; i++) {
        printf("%02X ", mem[i]);
        if (mem[i] != FILL_ALLOC) all_ab = 0;
    }
    printf("\n  → %s\n\n", all_ab ? "✓ 全部为 0xAB" : "✗ 填充异常");

    free(mem);
}

/* ── 主程序 ── */
int main(void)
{
    printf("╔═══════════════════════════════════════════════╗\n");
    printf("║     内存泄漏检测器 — 功能演示                  ║\n");
    printf("╚═══════════════════════════════════════════════╝\n\n");

    test_normal();           /* 正常场景 */
    test_leak();             /* 单个泄漏 */
    test_multi_leak();       /* 多处泄漏 */
    test_double_free();      /* Double free */
    test_invalid_free();     /* 无效释放 */
    test_buffer_overflow();  /* 缓冲区溢出 */
    test_fill_pattern();     /* 填充模式 */

    printf("═══════════════════════════════════════════════\n");
    printf("  所有测试执行完毕，生成泄漏报告...\n");
    printf("═══════════════════════════════════════════════\n");

    debug_report();

    return 0;
}
