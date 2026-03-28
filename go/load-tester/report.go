package main

import (
	"fmt"
	"sort"
	"strings"
	"time"
)

func generateReport(results []Result, testDuration time.Duration, url string, concurrency int, totalSent int64) Report {
	report := Report{
		URL:             url,
		Concurrency:     concurrency,
		TotalRequests:   int64(len(results)),
		TotalRequestsIn: totalSent,
		TestDuration:    testDuration,
		StatusCodes:     make(map[int]int64),
		Errors:          make(map[string]int),
		MinDuration:     time.Hour,
		MaxDuration:     0,
	}

	var totalDur time.Duration
	var durations []time.Duration

	for _, r := range results {
		if r.Error != nil {
			report.FailCount++
			errMsg := r.Error.Error()
			// 截断过长的错误信息
			if len(errMsg) > 80 {
				errMsg = errMsg[:80] + "..."
			}
			report.Errors[errMsg]++
		} else {
			report.SuccessCount++
			report.StatusCodes[r.StatusCode]++
		}

		totalDur += r.Duration
		durations = append(durations, r.Duration)

		if r.Duration < report.MinDuration {
			report.MinDuration = r.Duration
		}
		if r.Duration > report.MaxDuration {
			report.MaxDuration = r.Duration
		}
	}

	if len(results) > 0 {
		report.TotalDuration = totalDur
		report.MeanLatency = totalDur / time.Duration(len(results))
		report.RPS = float64(len(results)) / testDuration.Seconds()
	}

	// 计算百分位
	report.Percentiles = calcPercentiles(durations)

	return report
}

func calcPercentiles(durations []time.Duration) map[float64]time.Duration {
	if len(durations) == 0 {
		return map[float64]time.Duration{}
	}

	sort.Slice(durations, func(i, j int) bool {
		return durations[i] < durations[j]
	})

	percentiles := []float64{50, 75, 90, 95, 99}
	result := make(map[float64]time.Duration)
	for _, p := range percentiles {
		idx := int(float64(len(durations)-1) * p / 100)
		result[p] = durations[idx]
	}
	return result
}

func printReport(r Report) {
	fmt.Println()
	fmt.Println("╔════════════════════════════════════════════════════════╗")
	fmt.Println("║              负载测试报告                              ║")
	fmt.Println("╠════════════════════════════════════════════════════════╣")
	fmt.Printf("║  目标 URL:     %-40s ║\n", truncate(r.URL, 40))
	fmt.Printf("║  测试时长:     %-40s ║\n", r.TestDuration.Round(time.Millisecond))
	fmt.Printf("║  并发数:       %-40d ║\n", r.Concurrency)
	fmt.Printf("║  总请求数:     %-40d ║\n", r.TotalRequests)
	fmt.Println("╠════════════════════════════════════════════════════════╣")
	fmt.Println("║                    结果概览                            ║")
	fmt.Println("╠════════════════════════════════════════════════════════╣")

	successRate := float64(0)
	if r.TotalRequests > 0 {
		successRate = float64(r.SuccessCount) / float64(r.TotalRequests) * 100
	}
	fmt.Printf("║  成功率:       \033[32m%-40.1f\033[0m %% ║\n", successRate)
	fmt.Printf("║  失败数:       %-40d ║\n", r.FailCount)
	fmt.Printf("║  RPS:          \033[33m%-40.1f\033[0m    ║\n", r.RPS)

	fmt.Println("╠════════════════════════════════════════════════════════╣")
	fmt.Println("║                    延迟分布                            ║")
	fmt.Println("╠════════════════════════════════════════════════════════╣")
	fmt.Printf("║  最小:         %-40s ║\n", r.MinDuration.Round(time.Microsecond))
	fmt.Printf("║  平均:         %-40s ║\n", r.MeanLatency.Round(time.Microsecond))
	fmt.Printf("║  最大:         %-40s ║\n", r.MaxDuration.Round(time.Microsecond))

	fmt.Println("╠════════════════════════════════════════════════════════╣")
	fmt.Println("║                    百分位延迟                          ║")
	fmt.Println("╠════════════════════════════════════════════════════════╣")
	for _, p := range []float64{50, 75, 90, 95, 99} {
		if d, ok := r.Percentiles[p]; ok {
			fmt.Printf("║  P%-3.0f:         %-40s ║\n", p, d.Round(time.Microsecond))
		}
	}

	if len(r.StatusCodes) > 0 {
		fmt.Println("╠════════════════════════════════════════════════════════╣")
		fmt.Println("║                    状态码分布                          ║")
		fmt.Println("╠════════════════════════════════════════════════════════╣")
		// 排序状态码
		codes := make([]int, 0, len(r.StatusCodes))
		for code := range r.StatusCodes {
			codes = append(codes, code)
		}
		sort.Ints(codes)
		for _, code := range codes {
			count := r.StatusCodes[code]
			bar := strings.Repeat("█", int(float64(count)/float64(r.TotalRequests)*30))
			fmt.Printf("║  %d:  %-6d %-30s ║\n", code, count, bar)
		}
	}

	if len(r.Errors) > 0 {
		fmt.Println("╠════════════════════════════════════════════════════════╣")
		fmt.Println("║                    错误详情                            ║")
		fmt.Println("╠════════════════════════════════════════════════════════╣")
		for errMsg, count := range r.Errors {
			fmt.Printf("║  x%-3d %s\n", count, truncate(errMsg, 48))
		}
	}

	fmt.Println("╚════════════════════════════════════════════════════════╝")
	fmt.Println()
}

func truncate(s string, maxLen int) string {
	if len(s) <= maxLen {
		return s
	}
	return s[:maxLen-3] + "..."
}
