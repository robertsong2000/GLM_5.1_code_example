package main

import (
	"flag"
	"fmt"
	"os"
	"os/signal"
	"sync"
	"sync/atomic"
	"syscall"
	"time"
)

type Result struct {
	StatusCode int
	Duration   time.Duration
	Error      error
}

type Report struct {
	TotalRequests   int64
	SuccessCount    int64
	FailCount       int64
	StatusCodes     map[int]int64
	TotalDuration   time.Duration
	MinDuration     time.Duration
	MaxDuration     time.Duration
	Errors          map[string]int
	Percentiles     map[float64]time.Duration
	RPS             float64
	MeanLatency     time.Duration
	TestDuration    time.Duration
	URL             string
	Concurrency     int
	TotalRequestsIn int64
}

func main() {
	url := flag.String("url", "", "目标 URL（必填）")
	concurrency := flag.Int("c", 10, "并发数")
	totalReqs := flag.Int64("n", 100, "总请求数")
	duration := flag.Duration("d", 0, "持续时间（如 10s, 1m），设置后忽略 -n")
	timeout := flag.Duration("timeout", 10*time.Second, "单个请求超时")
	method := flag.String("m", "GET", "HTTP 方法")
	output := flag.String("o", "", "输出 HTML 报告文件路径")
	flag.Parse()

	if *url == "" {
		fmt.Println("用法: load-tester -url <URL> [-c 并发数] [-n 总请求数] [-d 持续时间]")
		flag.PrintDefaults()
		os.Exit(1)
	}

	fmt.Printf("\n开始负载测试: %s\n", *url)
	fmt.Printf("并发数: %d | 方法: %s | 超时: %s\n", *concurrency, *method, *timeout)
	if *duration > 0 {
		fmt.Printf("模式: 持续 %s\n\n", *duration)
	} else {
		fmt.Printf("模式: %d 次请求\n\n", *totalReqs)
	}

	// 收集结果
	var results []Result
	var resultsMu sync.Mutex
	var sentCount int64

	// 信号捕获
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	// 实时统计显示
	stopDisplay := make(chan struct{})
	go func() {
		ticker := time.NewTicker(500 * time.Millisecond)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				sent := atomic.LoadInt64(&sentCount)
				succ, fail := int64(0), int64(0)
				resultsMu.Lock()
				for _, r := range results {
					if r.Error == nil {
						succ++
					} else {
						fail++
					}
				}
				resultsMu.Unlock()
				fmt.Printf("\r  已发送: %d | 成功: %d | 失败: %d    ", sent, succ, fail)
			case <-stopDisplay:
				return
			}
		}
	}()

	startTime := time.Now()

	if *duration > 0 {
		// 持续时间模式
		runWithDuration(*url, *method, *concurrency, *duration, *timeout, &results, &resultsMu, &sentCount, sigCh)
	} else {
		// 固定请求数模式
		runWithCount(*url, *method, *concurrency, *totalReqs, *timeout, &results, &resultsMu, &sentCount, sigCh)
	}

	close(stopDisplay)
	testDuration := time.Since(startTime)

	// 生成报告
	report := generateReport(results, testDuration, *url, *concurrency, atomic.LoadInt64(&sentCount))
	printReport(report)

	// HTML 报告
	if *output != "" {
		html := generateHTMLReport(report)
		if err := os.WriteFile(*output, []byte(html), 0644); err != nil {
			fmt.Printf("错误: 无法写入报告文件: %v\n", err)
		} else {
			fmt.Printf("\nHTML 报告已保存到: %s\n", *output)
		}
	}
}

func runWithCount(url, method string, concurrency int, totalReqs int64, timeout time.Duration,
	results *[]Result, resultsMu *sync.Mutex, sentCount *int64, sigCh chan os.Signal) {

	var wg sync.WaitGroup
	reqCh := make(chan int64, totalReqs)

	// 填充请求通道
	for i := int64(0); i < totalReqs; i++ {
		reqCh <- i
	}
	close(reqCh)

	// 启动 workers
	for i := 0; i < concurrency; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for range reqCh {
				select {
				case <-sigCh:
					return
				default:
				}
				result := sendRequest(url, method, timeout)
				atomic.AddInt64(sentCount, 1)
				resultsMu.Lock()
				*results = append(*results, result)
				resultsMu.Unlock()
			}
		}()
	}
	wg.Wait()
}

func runWithDuration(url, method string, concurrency int, duration, timeout time.Duration,
	results *[]Result, resultsMu *sync.Mutex, sentCount *int64, sigCh chan os.Signal) {

	ctx := make(chan struct{})
	go func() {
		time.Sleep(duration)
		close(ctx)
	}()

	var wg sync.WaitGroup
	for i := 0; i < concurrency; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for {
				select {
				case <-ctx:
					return
				case <-sigCh:
					return
				default:
				}
				result := sendRequest(url, method, timeout)
				atomic.AddInt64(sentCount, 1)
				resultsMu.Lock()
				*results = append(*results, result)
				resultsMu.Unlock()
			}
		}()
	}
	wg.Wait()
}
