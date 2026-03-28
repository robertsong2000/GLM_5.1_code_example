package main

import (
	"bufio"
	"flag"
	"fmt"
	"io"
	"os"
	"os/signal"
	"regexp"
	"strings"
	"sync"
	"syscall"
	"time"
)

// Stats 日志统计信息
type Stats struct {
	mu          sync.Mutex
	TotalLines  int
	LevelCount  map[string]int
	KeywordHits map[string]int
	ErrorLines  []string
	StartTime   time.Time
}

func NewStats() *Stats {
	return &Stats{
		LevelCount:  make(map[string]int),
		KeywordHits: make(map[string]int),
		StartTime:   time.Now(),
	}
}

func (s *Stats) IncrLevel(level string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.LevelCount[strings.ToUpper(level)]++
}

func (s *Stats) IncrKeyword(keyword string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.KeywordHits[keyword]++
}

func (s *Stats) AddError(line string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	if len(s.ErrorLines) < 100 {
		s.ErrorLines = append(s.ErrorLines, line)
	}
}

func (s *Stats) Snapshot() (int, map[string]int, map[string]int, []string, time.Duration) {
	s.mu.Lock()
	defer s.mu.Unlock()

	levelCopy := make(map[string]int)
	for k, v := range s.LevelCount {
		levelCopy[k] = v
	}
	kwCopy := make(map[string]int)
	for k, v := range s.KeywordHits {
		kwCopy[k] = v
	}
	errCopy := make([]string, len(s.ErrorLines))
	copy(errCopy, s.ErrorLines)

	return s.TotalLines, levelCopy, kwCopy, errCopy, time.Since(s.StartTime)
}

func main() {
	filePath := flag.String("f", "", "日志文件路径（留空则读 stdin）")
	filterPattern := flag.String("filter", "", "正则过滤表达式（只显示匹配行）")
	keywords := flag.String("keywords", "", "关键词统计（逗号分隔），如: timeout,error,panic")
	alertLevel := flag.String("alert", "", "告警级别，达到该级别时高亮显示（ERROR,FATAL,PANIC）")
	interval := flag.Int("interval", 5, "统计刷新间隔（秒）")
	noColor := flag.Bool("no-color", false, "禁用颜色输出")
	flag.Parse()

	stats := NewStats()

	// 编译正则
	var filterRe *regexp.Regexp
	if *filterPattern != "" {
		var err error
		filterRe, err = regexp.Compile(*filterPattern)
		if err != nil {
			fmt.Fprintf(os.Stderr, "错误: 无效的正则表达式: %v\n", err)
			os.Exit(1)
		}
	}

	// 关键词列表
	var keywordList []string
	if *keywords != "" {
		keywordList = strings.Split(*keywords, ",")
		for i, kw := range keywordList {
			keywordList[i] = strings.TrimSpace(kw)
		}
	}

	color := NewColorPalette(*noColor)

	// 打开文件或 stdin
	var reader io.Reader
	if *filePath != "" {
		f, err := os.Open(*filePath)
		if err != nil {
			fmt.Fprintf(os.Stderr, "错误: 无法打开文件: %v\n", err)
			os.Exit(1)
		}
		defer f.Close()
		reader = f
	} else {
		reader = os.Stdin
	}

	// 信号处理
	sigCh := make(chan os.Signal, 1)
	signal.Notify(sigCh, syscall.SIGINT, syscall.SIGTERM)

	// 定时打印统计
	done := make(chan struct{})
	go func() {
		ticker := time.NewTicker(time.Duration(*interval) * time.Second)
		defer ticker.Stop()
		for {
			select {
			case <-ticker.C:
				printStats(stats, color)
			case <-done:
				return
			}
		}
	}()

	// 日志级别正则
	levelRe := regexp.MustCompile(`(?i)\b(ERROR|WARN(?:ING)?|INFO|DEBUG|FATAL|PANIC|TRACE)\b`)

	// 主处理循环
	scanner := bufio.NewScanner(reader)
	lineCh := make(chan string, 1000)

	// 读取 goroutine
	go func() {
		defer close(lineCh)
		for scanner.Scan() {
			line := scanner.Text()
			select {
			case lineCh <- line:
			default:
				// 丢弃溢出行
			}
		}
	}()

	// 处理循环
	running := true
	for running {
		select {
		case line, ok := <-lineCh:
			if !ok {
				running = false
				continue
			}
			stats.mu.Lock()
			stats.TotalLines++
			stats.mu.Unlock()

			// 检测日志级别
			matches := levelRe.FindStringSubmatch(line)
			if len(matches) > 1 {
				level := strings.ToUpper(matches[1])
				if level == "WARNING" {
					level = "WARN"
				}
				stats.IncrLevel(level)

				// 收集错误行
				if level == "ERROR" || level == "FATAL" || level == "PANIC" {
					stats.AddError(line)
				}

				// 告警检查
				if *alertLevel != "" && level == strings.ToUpper(*alertLevel) {
					fmt.Println(color.Red(">>> 告警: " + line))
				}
			}

			// 关键词统计
			lineLower := strings.ToLower(line)
			for _, kw := range keywordList {
				if strings.Contains(lineLower, strings.ToLower(kw)) {
					stats.IncrKeyword(kw)
				}
			}

			// 过滤输出
			if filterRe != nil {
				if filterRe.MatchString(line) {
					fmt.Println(highlightMatch(line, filterRe, color))
				}
			}

		case <-sigCh:
			running = false
		}
	}

	close(done)

	// 最终统计
	fmt.Println()
	printStats(stats, color)
	printErrors(stats, color)
}

func printStats(stats *Stats, color *ColorPalette) {
	total, levels, keywords, _, elapsed := stats.Snapshot()

	fmt.Println()
	fmt.Println(color.Cyan("╔══════════════════════════════════════════════╗"))
	fmt.Println(color.Cyan("║          实时日志统计面板                    ║"))
	fmt.Println(color.Cyan("╠══════════════════════════════════════════════╣"))
	fmt.Printf(color.Cyan("║")+" 运行时间: %-34s "+color.Cyan("║")+"\n", elapsed.Round(time.Second))
	fmt.Printf(color.Cyan("║")+" 总行数:   %-34d "+color.Cyan("║")+"\n", total)

	if len(levels) > 0 {
		fmt.Println(color.Cyan("╠══════════════════════════════════════════════╣"))
		fmt.Println(color.Cyan("║") + " 日志级别统计:                               " + color.Cyan("║"))
		for _, level := range []string{"ERROR", "FATAL", "PANIC", "WARN", "INFO", "DEBUG", "TRACE"} {
			if count, ok := levels[level]; ok {
				var label string
				switch level {
				case "ERROR", "FATAL", "PANIC":
					label = color.Red(fmt.Sprintf("  %-6s: %d", level, count))
				case "WARN":
					label = color.Yellow(fmt.Sprintf("  %-6s: %d", level, count))
				case "INFO":
					label = color.Green(fmt.Sprintf("  %-6s: %d", level, count))
				default:
					label = fmt.Sprintf("  %-6s: %d", level, count)
				}
				fmt.Printf(color.Cyan("║")+"%s"+color.Cyan("║")+"\n", label)
			}
		}
	}

	if len(keywords) > 0 {
		fmt.Println(color.Cyan("╠══════════════════════════════════════════════╣"))
		fmt.Println(color.Cyan("║") + " 关键词命中:                                  " + color.Cyan("║"))
		for kw, count := range keywords {
			fmt.Printf(color.Cyan("║")+"  %-12s: %-22d "+color.Cyan("║")+"\n", kw, count)
		}
	}

	fmt.Println(color.Cyan("╚══════════════════════════════════════════════╝"))
}

func printErrors(stats *Stats, color *ColorPalette) {
	_, _, _, errors, _ := stats.Snapshot()
	if len(errors) == 0 {
		return
	}
	fmt.Println()
	fmt.Println(color.Red("最近的错误日志:"))
	fmt.Println(color.Red("────────────────────────────────────────"))
	for i, line := range errors {
		if i >= 10 {
			fmt.Printf(color.Red("... 还有 %d 条错误日志\n"), len(errors)-10)
			break
		}
		// 截断过长的行
		if len(line) > 120 {
			line = line[:120] + "..."
		}
		fmt.Printf(color.Red("  %s\n"), line)
	}
}

func highlightMatch(line string, re *regexp.Regexp, color *ColorPalette) string {
	return re.ReplaceAllStringFunc(line, func(match string) string {
		return color.Bold(color.Yellow(match))
	})
}
