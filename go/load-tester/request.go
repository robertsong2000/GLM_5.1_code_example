package main

import (
	"crypto/tls"
	"net/http"
	"time"
)

func sendRequest(url, method string, timeout time.Duration) Result {
	client := &http.Client{
		Timeout: timeout,
		Transport: &http.Transport{
			TLSClientConfig: &tls.Config{InsecureSkipVerify: true},
			MaxIdleConns:    100,
		},
	}

	start := time.Now()
	req, err := http.NewRequest(method, url, nil)
	if err != nil {
		return Result{Error: err, Duration: 0}
	}

	resp, err := client.Do(req)
	duration := time.Since(start)

	if err != nil {
		return Result{Error: err, Duration: duration}
	}
	defer resp.Body.Close()

	return Result{
		StatusCode: resp.StatusCode,
		Duration:   duration,
	}
}
