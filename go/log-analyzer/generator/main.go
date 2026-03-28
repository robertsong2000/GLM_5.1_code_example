package main

import (
	"fmt"
	"math/rand"
	"os"
	"time"
)

// 模拟日志生成器，用于测试 log-analyzer
func main() {
	levels := []string{"DEBUG", "INFO", "INFO", "INFO", "WARN", "WARN", "ERROR", "ERROR", "FATAL", "PANIC"}
	messages := map[string][]string{
		"DEBUG": {
			"Cache lookup for key user:1234",
			"Query executed in 12ms",
			"Connection pool status: 8/20 active",
		},
		"INFO": {
			"Request processed successfully: GET /api/users",
			"User login from 192.168.1.100",
			"Background job completed: email-batch-001",
			"Server started on port 8080",
		},
		"WARN": {
			"High memory usage detected: 85%",
			"Slow query detected: 2500ms for SELECT * FROM orders",
			"Rate limit approaching for client app-001",
			"Connection timeout retry: attempt 2/3",
		},
		"ERROR": {
			"Database connection failed: timeout after 30s",
			"Failed to process payment: card declined",
			"Panic recovery in handler /api/checkout",
			"timeout: context deadline exceeded for RPC call",
		},
		"FATAL": {
			"Out of memory: cannot allocate 256MB",
			"Disk full: unable to write WAL log",
		},
		"PANIC": {
			"nil pointer dereference in user service",
			"goroutine stack overflow detected",
		},
	}

	rand.Seed(time.Now().UnixNano())

	for {
		level := levels[rand.Intn(len(levels))]
		msgs := messages[level]
		msg := msgs[rand.Intn(len(msgs))]
		timestamp := time.Now().Format("2006-01-02 15:04:05.000")

		fmt.Printf("[%s] %s %s\n", timestamp, level, msg)

		// 随机间隔
		interval := time.Duration(100+rand.Intn(900)) * time.Millisecond
		time.Sleep(interval)

		// 偶尔暂停模拟日志间隙
		if rand.Float64() < 0.05 {
			time.Sleep(2 * time.Second)
		}

		// 检查是否需要退出
		select {
		case <-time.After(time.Nanosecond):
		default:
		}
	}

	_ = os.Stdout.Sync()
}
