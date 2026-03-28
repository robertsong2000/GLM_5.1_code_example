/*
 * 简易多线程 HTTP 服务器
 * 纯 C + Socket 实现，支持：
 *   - 静态文件服务（www/ 目录）
 *   - /api/time  返回当前时间 JSON
 *   - /api/echo  POST 请求体原样返回
 *   - Connection: keep-alive
 *   - 304 Not Modified (If-Modified-Since)
 *   - 正确的 Content-Type 和 Content-Length
 *
 * 编译: gcc -o http_server http_server.c -lpthread
 * 运行: ./http_server [port] [www_dir]
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <fcntl.h>
#include <time.h>
#include <pthread.h>
#include <sys/socket.h>
#include <sys/stat.h>
#include <netinet/in.h>
#include <arpa/inet.h>

#define BUFSIZE        8192
#define MAX_HEADERS    64
#define MAX_PATH_LEN   512
#define KEEPALIVE_SEC  5
#define KEEPALIVE_REQ  100

/* ─── HTTP 请求结构 ─── */

typedef struct {
    char method[16];
    char path[MAX_PATH_LEN];
    char version[16];
    char headers[MAX_HEADERS][2][256];  /* [name, value] */
    int  header_count;
    char *body;
    int   body_len;
} http_request;

/* ─── 工具函数 ─── */

/* 根据 MIME 类型返回 Content-Type */
static const char *get_content_type(const char *path)
{
    const char *ext = strrchr(path, '.');
    if (!ext) return "application/octet-stream";

    if (strcmp(ext, ".html") == 0 || strcmp(ext, ".htm") == 0)
        return "text/html; charset=utf-8";
    if (strcmp(ext, ".css") == 0)
        return "text/css; charset=utf-8";
    if (strcmp(ext, ".js") == 0)
        return "application/javascript; charset=utf-8";
    if (strcmp(ext, ".json") == 0)
        return "application/json; charset=utf-8";
    if (strcmp(ext, ".png") == 0)
        return "image/png";
    if (strcmp(ext, ".jpg") == 0 || strcmp(ext, ".jpeg") == 0)
        return "image/jpeg";
    if (strcmp(ext, ".gif") == 0)
        return "image/gif";
    if (strcmp(ext, ".svg") == 0)
        return "image/svg+xml";
    if (strcmp(ext, ".ico") == 0)
        return "image/x-icon";
    if (strcmp(ext, ".txt") == 0)
        return "text/plain; charset=utf-8";
    return "application/octet-stream";
}

/* URL 解码（处理 %XX） */
static void url_decode(char *dst, const char *src, size_t dst_size)
{
    size_t j = 0;
    for (size_t i = 0; src[i] && j < dst_size - 1; i++) {
        if (src[i] == '%' && src[i+1] && src[i+2]) {
            char hex[3] = { src[i+1], src[i+2], '\0' };
            dst[j++] = (char)strtol(hex, NULL, 16);
            i += 2;
        } else if (src[i] == '+') {
            dst[j++] = ' ';
        } else {
            dst[j++] = src[i];
        }
    }
    dst[j] = '\0';
}

/* 去除路径中的 "." 和 ".." 防止目录穿越 */
static int sanitize_path(const char *req_path, char *safe_path, size_t size)
{
    char decoded[MAX_PATH_LEN];
    url_decode(decoded, req_path, sizeof(decoded));

    /* 跳过开头的 / */
    const char *p = decoded;
    while (*p == '/') p++;

    /* 简单检查不允许 ".." */
    if (strstr(p, "..") != NULL)
        return -1;

    snprintf(safe_path, size, "%s", p);
    return 0;
}

/* 格式化 HTTP 日期 (RFC 1123) */
static void format_http_time(time_t t, char *buf, size_t size)
{
    struct tm *tm = gmtime(&t);
    strftime(buf, size, "%a, %d %b %Y %H:%M:%S GMT", tm);
}

/* 解析 HTTP 日期字符串 */
static time_t parse_http_time(const char *s)
{
    struct tm tm = {0};
    /* 尝试 RFC 1123 格式 */
    if (strptime(s, "%a, %d %b %Y %H:%M:%S GMT", &tm))
        return timegm(&tm);
    /* 尝试 RFC 850 格式 */
    if (strptime(s, "%A, %d-%b-%y %H:%M:%S GMT", &tm))
        return timegm(&tm);
    /* 尝试 asctime 格式 */
    if (strptime(s, "%a %b %d %H:%M:%S %Y", &tm))
        return timegm(&tm);
    return 0;
}

/* 从请求中获取指定 header 的值 */
static const char *get_header(const http_request *req, const char *name)
{
    for (int i = 0; i < req->header_count; i++) {
        if (strcasecmp(req->headers[i][0], name) == 0)
            return req->headers[i][1];
    }
    return NULL;
}

/* ─── HTTP 解析 ─── */

/*
 * 从 socket 读取完整 HTTP 请求（头部 + body）。
 * 返回:
 *   >0  读到的请求总字节数
 *   0   连接关闭
 *   -1  错误
 */
static int recv_request(int fd, http_request *req)
{
    char buf[BUFSIZE];
    int total = 0;
    int header_end = -1;

    memset(req, 0, sizeof(*req));
    req->body = NULL;
    req->body_len = 0;

    /* 1. 读取直到找到 \r\n\r\n（头部结束） */
    while (total < (int)sizeof(buf) - 1) {
        int n = recv(fd, buf + total, 1, 0);
        if (n <= 0) return n == 0 ? 0 : -1;
        total += n;
        buf[total] = '\0';

        if (total >= 4 &&
            buf[total-4] == '\r' && buf[total-3] == '\n' &&
            buf[total-2] == '\r' && buf[total-1] == '\n') {
            header_end = total - 4;
            break;
        }
    }

    if (header_end < 0) return -1;
    /* 在空行 \r\n 处截断（保留最后一个 header 的 \r\n） */
    buf[header_end + 2] = '\0';  /* blank line starts at header_end+2 */

    /* 2. 解析请求行: METHOD PATH VERSION */
    char *line = buf;
    char *crlf = strstr(line, "\r\n");
    if (!crlf) return -1;
    *crlf = '\0';

    if (sscanf(line, "%15s %511s %15s", req->method, req->path, req->version) != 3)
        return -1;

    /* 3. 解析头部字段 */
    line = crlf + 2;
    req->header_count = 0;
    while (line < buf + header_end && req->header_count < MAX_HEADERS) {
        crlf = strstr(line, "\r\n");
        if (!crlf) break;
        *crlf = '\0';

        char *colon = strchr(line, ':');
        if (colon) {
            *colon = '\0';
            char *val = colon + 1;
            while (*val == ' ') val++;
            strncpy(req->headers[req->header_count][0], line, 255);
            strncpy(req->headers[req->header_count][1], val, 255);
            req->header_count++;
        }
        line = crlf + 2;
    }

    /* 4. 读取 body（如果有 Content-Length） */
    const char *cl_str = get_header(req, "Content-Length");
    if (cl_str) {
        int content_len = atoi(cl_str);
        if (content_len > 0 && content_len < BUFSIZE) {
            req->body = malloc(content_len + 1);
            if (!req->body) return -1;
            int received = 0;
            while (received < content_len) {
                int n = recv(fd, req->body + received, content_len - received, 0);
                if (n <= 0) { free(req->body); req->body = NULL; return -1; }
                received += n;
            }
            req->body[content_len] = '\0';
            req->body_len = content_len;
        }
    }

    return total;
}

/* ─── 响应发送 ─── */

/* 发送完整响应：状态行 + 头部 + body */
static void send_response(int fd, int status, const char *status_text,
                          const char *content_type,
                          const char *extra_headers,
                          const char *body, int body_len)
{
    char head[BUFSIZE];
    int hlen = snprintf(head, sizeof(head),
        "HTTP/1.1 %d %s\r\n"
        "Content-Type: %s\r\n"
        "Content-Length: %d\r\n"
        "Server: c-http-server/1.0\r\n"
        "%s"
        "\r\n",
        status, status_text, content_type, body_len,
        extra_headers ? extra_headers : "");

    send(fd, head, hlen, 0);
    if (body && body_len > 0)
        send(fd, body, body_len, 0);
}

/* 发送文件内容作为响应 */
static void send_file_response(int fd, const char *filepath,
                               const http_request *req)
{
    struct stat st;
    if (stat(filepath, &st) < 0 || S_ISDIR(st.st_mode)) {
        const char *body = "<html><body><h1>404 Not Found</h1></body></html>";
        send_response(fd, 404, "Not Found", "text/html; charset=utf-8",
                      NULL, body, (int)strlen(body));
        return;
    }

    /* 304 Not Modified 检查 */
    const char *ims = get_header(req, "If-Modified-Since");
    if (ims) {
        time_t ims_time = parse_http_time(ims);
        if (ims_time >= st.st_mtime) {
            char extra[256];
            char lm[128];
            format_http_time(st.st_mtime, lm, sizeof(lm));
            snprintf(extra, sizeof(extra), "Last-Modified: %s\r\n", lm);
            send_response(fd, 304, "Not Modified", get_content_type(filepath),
                          extra, "", 0);
            return;
        }
    }

    /* 读取文件 */
    FILE *fp = fopen(filepath, "rb");
    if (!fp) {
        const char *body = "<html><body><h1>403 Forbidden</h1></body></html>";
        send_response(fd, 403, "Forbidden", "text/html; charset=utf-8",
                      NULL, body, (int)strlen(body));
        return;
    }

    char *file_buf = malloc(st.st_size);
    if (!file_buf) {
        fclose(fp);
        const char *body = "<html><body><h1>500 Internal Server Error</h1></body></html>";
        send_response(fd, 500, "Internal Server Error", "text/html; charset=utf-8",
                      NULL, body, (int)strlen(body));
        return;
    }

    int nread = (int)fread(file_buf, 1, st.st_size, fp);
    fclose(fp);

    char extra[512];
    char lm[128], date[128];
    format_http_time(st.st_mtime, lm, sizeof(lm));
    format_http_time(time(NULL), date, sizeof(date));
    snprintf(extra, sizeof(extra),
             "Last-Modified: %s\r\n"
             "Date: %s\r\n"
             "Cache-Control: max-age=60\r\n",
             lm, date);

    send_response(fd, 200, "OK", get_content_type(filepath),
                  extra, file_buf, nread);
    free(file_buf);
}

/* ─── API 路由处理 ─── */

static void handle_api_time(int fd)
{
    time_t now = time(NULL);
    struct tm *tm_info = localtime(&now);
    char time_str[64];
    strftime(time_str, sizeof(time_str), "%Y-%m-%dT%H:%M:%S", tm_info);

    char body[256];
    int blen = snprintf(body, sizeof(body), "{\"time\": \"%s\"}", time_str);

    char date[128];
    char extra[256];
    format_http_time(now, date, sizeof(date));
    snprintf(extra, sizeof(extra), "Date: %s\r\n", date);

    send_response(fd, 200, "OK", "application/json; charset=utf-8",
                  extra, body, blen);
}

static void handle_api_echo(int fd, const http_request *req)
{
    char date[128];
    char extra[256];
    format_http_time(time(NULL), date, sizeof(date));
    snprintf(extra, sizeof(extra), "Date: %s\r\n", date);

    if (req->body && req->body_len > 0) {
        send_response(fd, 200, "OK", "text/plain; charset=utf-8",
                      extra, req->body, req->body_len);
    } else {
        const char *empty = "";
        send_response(fd, 200, "OK", "text/plain; charset=utf-8",
                      extra, empty, 0);
    }
}

/* ─── 连接处理线程 ─── */

static const char *g_www_dir = "./www";

static void *handle_client(void *arg)
{
    int fd = *(int *)arg;
    free(arg);

    /* 设置超时，用于 keep-alive */
    struct timeval tv = { .tv_sec = KEEPALIVE_SEC, .tv_usec = 0 };
    setsockopt(fd, SOL_SOCKET, SO_RCVTIMEO, &tv, sizeof(tv));

    int requests = 0;
    int keep_alive = 1;

    while (keep_alive && requests < KEEPALIVE_REQ) {
        http_request req;
        int ret = recv_request(fd, &req);
        if (ret <= 0)
            break;

        requests++;

        /* 判断是否 keep-alive */
        const char *conn = get_header(&req, "Connection");
        if (conn && strcasecmp(conn, "close") == 0)
            keep_alive = 0;
        /* HTTP/1.1 默认 keep-alive，HTTP/1.0 默认关闭 */
        if (strcmp(req.version, "HTTP/1.0") == 0) {
            if (!conn || strcasecmp(conn, "keep-alive") != 0)
                keep_alive = 0;
        }

        printf("[%s] %s %s\n",
               req.method, req.path,
               keep_alive ? "(keep-alive)" : "(close)");

        /* ── 路由 ── */

        if (strcmp(req.path, "/api/time") == 0) {
            handle_api_time(fd);
        }
        else if (strcmp(req.path, "/api/echo") == 0 &&
                 strcmp(req.method, "POST") == 0) {
            handle_api_echo(fd, &req);
        }
        else if (strcmp(req.path, "/") == 0) {
            char filepath[MAX_PATH_LEN];
            snprintf(filepath, sizeof(filepath), "%s/index.html", g_www_dir);
            send_file_response(fd, filepath, &req);
        }
        else {
            /* 静态文件 */
            char safe[MAX_PATH_LEN];
            if (sanitize_path(req.path, safe, sizeof(safe)) < 0) {
                const char *body = "<html><body><h1>403 Forbidden</h1></body></html>";
                send_response(fd, 403, "Forbidden", "text/html; charset=utf-8",
                              NULL, body, (int)strlen(body));
            } else {
                char filepath[MAX_PATH_LEN];
                snprintf(filepath, sizeof(filepath), "%s/%s", g_www_dir, safe);
                send_file_response(fd, filepath, &req);
            }
        }

        if (req.body) free(req.body);
    }

    close(fd);
    return NULL;
}

/* ─── main ─── */

int main(int argc, char *argv[])
{
    int port = 8080;
    if (argc >= 2) port = atoi(argv[1]);
    if (argc >= 3) g_www_dir = argv[2];

    /* 检查 www 目录 */
    struct stat st;
    if (stat(g_www_dir, &st) < 0 || !S_ISDIR(st.st_mode)) {
        fprintf(stderr, "Error: www directory '%s' not found.\n", g_www_dir);
        return 1;
    }

    /* 创建 socket */
    int server_fd = socket(AF_INET, SOCK_STREAM, 0);
    if (server_fd < 0) {
        perror("socket");
        return 1;
    }

    /* 允许地址复用 */
    int opt = 1;
    setsockopt(server_fd, SOL_SOCKET, SO_REUSEADDR, &opt, sizeof(opt));

    struct sockaddr_in addr = {
        .sin_family = AF_INET,
        .sin_addr.s_addr = INADDR_ANY,
        .sin_port = htons(port)
    };

    if (bind(server_fd, (struct sockaddr *)&addr, sizeof(addr)) < 0) {
        perror("bind");
        close(server_fd);
        return 1;
    }

    if (listen(server_fd, 128) < 0) {
        perror("listen");
        close(server_fd);
        return 1;
    }

    printf("HTTP Server started on port %d\n", port);
    printf("Serving static files from: %s\n", g_www_dir);
    printf("Routes:\n");
    printf("  GET  /             -> index.html\n");
    printf("  GET  /<file>       -> static file from www/\n");
    printf("  GET  /api/time     -> current time JSON\n");
    printf("  POST /api/echo     -> echo request body\n");
    printf("Press Ctrl+C to stop.\n\n");

    /* 主循环：接受连接，创建线程处理 */
    while (1) {
        struct sockaddr_in client_addr;
        socklen_t client_len = sizeof(client_addr);
        int *client_fd = malloc(sizeof(int));

        *client_fd = accept(server_fd, (struct sockaddr *)&client_addr, &client_len);
        if (*client_fd < 0) {
            perror("accept");
            free(client_fd);
            continue;
        }

        /* 设置线程为 detach 模式，自动回收资源 */
        pthread_t tid;
        pthread_attr_t attr;
        pthread_attr_init(&attr);
        pthread_attr_setdetachstate(&attr, PTHREAD_CREATE_DETACHED);

        if (pthread_create(&tid, &attr, handle_client, client_fd) != 0) {
            perror("pthread_create");
            close(*client_fd);
            free(client_fd);
        }
        pthread_attr_destroy(&attr);
    }

    close(server_fd);
    return 0;
}
