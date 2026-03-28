package main

import (
	"encoding/json"
	"fmt"
	"os"
)

func loadTodos() []Todo {
	data, err := os.ReadFile(dataFile)
	if err != nil {
		return []Todo{}
	}
	var todos []Todo
	if err := json.Unmarshal(data, &todos); err != nil {
		fmt.Println("警告: 数据文件损坏，使用空列表")
		return []Todo{}
	}
	return todos
}

func saveTodos(todos []Todo) {
	data, err := json.MarshalIndent(todos, "", "  ")
	if err != nil {
		fmt.Println("错误: 无法序列化数据")
		os.Exit(1)
	}
	if err := os.WriteFile(dataFile, data, 0644); err != nil {
		fmt.Println("错误: 无法写入数据文件")
		os.Exit(1)
	}
}

func nextID(todos []Todo) int {
	maxID := 0
	for _, t := range todos {
		if t.ID > maxID {
			maxID = t.ID
		}
	}
	return maxID + 1
}
