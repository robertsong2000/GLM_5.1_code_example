package main

import (
	"fmt"
	"os"
	"sort"
	"strconv"
	"strings"
	"time"

	"github.com/spf13/cobra"
)

// Todo 表示一条待办事项
type Todo struct {
	ID        int       `json:"id"`
	Title     string    `json:"title"`
	Completed bool      `json:"completed"`
	Priority  int       `json:"priority"` // 1=高, 2=中, 3=低
	CreatedAt time.Time `json:"created_at"`
}

const dataFile = "todos.json"

func main() {
	var priority int
	var showAll bool
	var filterStatus string

	rootCmd := &cobra.Command{
		Use:   "todo",
		Short: "CLI 待办事项管理器",
	}

	// add 命令
	addCmd := &cobra.Command{
		Use:   "add <title>",
		Short: "添加新的待办事项",
		Args:  cobra.MinimumNArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			todos := loadTodos()
			title := strings.Join(args, " ")
			todo := Todo{
				ID:        nextID(todos),
				Title:     title,
				Completed: false,
				Priority:  priority,
				CreatedAt: time.Now(),
			}
			todos = append(todos, todo)
			saveTodos(todos)
			printTodos([]Todo{todo}, "已添加待办事项:")
		},
	}
	addCmd.Flags().IntVarP(&priority, "priority", "p", 3, "优先级: 1=高, 2=中, 3=低")

	// list 命令
	listCmd := &cobra.Command{
		Use:   "list",
		Short: "列出所有待办事项",
		Run: func(cmd *cobra.Command, args []string) {
			todos := loadTodos()
			if len(todos) == 0 {
				fmt.Println("没有待办事项，使用 todo add <title> 添加")
				return
			}

			// 过滤
			var filtered []Todo
			for _, t := range todos {
				if !showAll && t.Completed {
					continue
				}
				if filterStatus == "done" && !t.Completed {
					continue
				}
				if filterStatus == "undone" && t.Completed {
					continue
				}
				filtered = append(filtered, t)
			}

			// 按优先级排序
			sort.Slice(filtered, func(i, j int) bool {
				return filtered[i].Priority < filtered[j].Priority
			})

			printTodos(filtered, "待办事项列表")
		},
	}
	listCmd.Flags().BoolVarP(&showAll, "all", "a", false, "显示已完成的事项")
	listCmd.Flags().StringVarP(&filterStatus, "status", "s", "", "过滤状态: done/undone")

	// done 命令
	doneCmd := &cobra.Command{
		Use:   "done <id>",
		Short: "标记待办事项为完成",
		Args:  cobra.ExactArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			id, err := strconv.Atoi(args[0])
			if err != nil {
				fmt.Println("错误: ID 必须是数字")
				os.Exit(1)
			}
			todos := loadTodos()
			found := false
			for i, t := range todos {
				if t.ID == id {
					todos[i].Completed = true
					found = true
					fmt.Printf("已完成: [%d] %s\n", t.ID, t.Title)
					break
				}
			}
			if !found {
				fmt.Printf("未找到 ID 为 %d 的待办事项\n", id)
				os.Exit(1)
			}
			saveTodos(todos)
		},
	}

	// undone 命令
	undoneCmd := &cobra.Command{
		Use:   "undone <id>",
		Short: "取消完成标记",
		Args:  cobra.ExactArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			id, err := strconv.Atoi(args[0])
			if err != nil {
				fmt.Println("错误: ID 必须是数字")
				os.Exit(1)
			}
			todos := loadTodos()
			found := false
			for i, t := range todos {
				if t.ID == id {
					todos[i].Completed = false
					found = true
					fmt.Printf("已取消完成: [%d] %s\n", t.ID, t.Title)
					break
				}
			}
			if !found {
				fmt.Printf("未找到 ID 为 %d 的待办事项\n", id)
				os.Exit(1)
			}
			saveTodos(todos)
		},
	}

	// rm 命令
	rmCmd := &cobra.Command{
		Use:   "rm <id>",
		Short: "删除待办事项",
		Args:  cobra.ExactArgs(1),
		Run: func(cmd *cobra.Command, args []string) {
			id, err := strconv.Atoi(args[0])
			if err != nil {
				fmt.Println("错误: ID 必须是数字")
				os.Exit(1)
			}
			todos := loadTodos()
			found := false
			for i, t := range todos {
				if t.ID == id {
					todos = append(todos[:i], todos[i+1:]...)
					found = true
					fmt.Printf("已删除: [%d] %s\n", t.ID, t.Title)
					break
				}
			}
			if !found {
				fmt.Printf("未找到 ID 为 %d 的待办事项\n", id)
				os.Exit(1)
			}
			saveTodos(todos)
		},
	}

	// edit 命令
	editCmd := &cobra.Command{
		Use:   "edit <id> <new-title>",
		Short: "编辑待办事项标题",
		Args:  cobra.MinimumNArgs(2),
		Run: func(cmd *cobra.Command, args []string) {
			id, err := strconv.Atoi(args[0])
			if err != nil {
				fmt.Println("错误: ID 必须是数字")
				os.Exit(1)
			}
			newTitle := strings.Join(args[1:], " ")
			todos := loadTodos()
			found := false
			for i, t := range todos {
				if t.ID == id {
					todos[i].Title = newTitle
					found = true
					fmt.Printf("已编辑: [%d] %s -> %s\n", t.ID, t.Title, newTitle)
					break
				}
			}
			if !found {
				fmt.Printf("未找到 ID 为 %d 的待办事项\n", id)
				os.Exit(1)
			}
			saveTodos(todos)
		},
	}

	// clear 命令
	clearCmd := &cobra.Command{
		Use:   "clear",
		Short: "清除所有已完成的待办事项",
		Run: func(cmd *cobra.Command, args []string) {
			todos := loadTodos()
			var remaining []Todo
			cleared := 0
			for _, t := range todos {
				if t.Completed {
					cleared++
				} else {
					remaining = append(remaining, t)
				}
			}
			saveTodos(remaining)
			fmt.Printf("已清除 %d 个已完成的事项\n", cleared)
		},
	}

	// stats 命令
	statsCmd := &cobra.Command{
		Use:   "stats",
		Short: "显示统计信息",
		Run: func(cmd *cobra.Command, args []string) {
			todos := loadTodos()
			total := len(todos)
			done := 0
			pending := 0
			priorityCount := map[int]int{1: 0, 2: 0, 3: 0}
			for _, t := range todos {
				if t.Completed {
					done++
				} else {
					pending++
				}
				priorityCount[t.Priority]++
			}
			fmt.Println("========== 统计信息 ==========")
			fmt.Printf("  总计: %d\n", total)
			fmt.Printf("  已完成: %d\n", done)
			fmt.Printf("  待完成: %d\n", pending)
			fmt.Printf("  高优先级: %d | 中优先级: %d | 低优先级: %d\n",
				priorityCount[1], priorityCount[2], priorityCount[3])
			if total > 0 {
				fmt.Printf("  完成率: %.1f%%\n", float64(done)/float64(total)*100)
			}
			fmt.Println("==============================")
		},
	}

	rootCmd.AddCommand(addCmd, listCmd, doneCmd, undoneCmd, rmCmd, editCmd, clearCmd, statsCmd)

	if err := rootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}

func printTodos(todos []Todo, header string) {
	fmt.Printf("\n  %s\n", header)
	fmt.Println("  ─────────────────────────────────────────────────────")
	for _, t := range todos {
		status := " "
		if t.Completed {
			status = "✓"
		}
		priorityLabel := map[int]string{1: "高", 2: "中", 3: "低"}
		fmt.Printf("  [%s] %d. %-30s 优先级:%s  %s\n",
			status, t.ID, t.Title, priorityLabel[t.Priority],
			t.CreatedAt.Format("2006-01-02 15:04"))
	}
	fmt.Println("  ─────────────────────────────────────────────────────")
	fmt.Printf("  共 %d 项\n\n", len(todos))
}
