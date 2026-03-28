package main

import "fmt"

type ColorPalette struct {
	enabled bool
}

func NewColorPalette(disabled bool) *ColorPalette {
	return &ColorPalette{enabled: !disabled}
}

func (c *ColorPalette) Red(s string) string {
	if !c.enabled {
		return s
	}
	return fmt.Sprintf("\033[31m%s\033[0m", s)
}

func (c *ColorPalette) Green(s string) string {
	if !c.enabled {
		return s
	}
	return fmt.Sprintf("\033[32m%s\033[0m", s)
}

func (c *ColorPalette) Yellow(s string) string {
	if !c.enabled {
		return s
	}
	return fmt.Sprintf("\033[33m%s\033[0m", s)
}

func (c *ColorPalette) Cyan(s string) string {
	if !c.enabled {
		return s
	}
	return fmt.Sprintf("\033[36m%s\033[0m", s)
}

func (c *ColorPalette) Bold(s string) string {
	if !c.enabled {
		return s
	}
	return fmt.Sprintf("\033[1m%s\033[0m", s)
}
