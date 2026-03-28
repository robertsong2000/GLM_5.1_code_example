#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>
#include <termios.h>
#include <fcntl.h>
#include <sys/select.h>

/* ========== 常量定义 ========== */
#define ROWS 20
#define COLS 10
#define TRUE 1
#define FALSE 0

/* 7 种方块定义（每个 4 种旋转状态，每个状态 4 个坐标） */
static const int SHAPES[7][4][4][2] = {
    /* I */
    {{{0,1},{1,1},{2,1},{3,1}}, {{2,0},{2,1},{2,2},{2,3}},
     {{0,2},{1,2},{2,2},{3,2}}, {{1,0},{1,1},{1,2},{1,3}}},
    /* O */
    {{{1,0},{2,0},{1,1},{2,1}}, {{1,0},{2,0},{1,1},{2,1}},
     {{1,0},{2,0},{1,1},{2,1}}, {{1,0},{2,0},{1,1},{2,1}}},
    /* T */
    {{{1,0},{0,1},{1,1},{2,1}}, {{1,0},{1,1},{2,1},{1,2}},
     {{0,1},{1,1},{2,1},{1,2}}, {{1,0},{0,1},{1,1},{1,2}}},
    /* S */
    {{{1,0},{2,0},{0,1},{1,1}}, {{1,0},{1,1},{2,1},{2,2}},
     {{1,1},{2,1},{0,2},{1,2}}, {{0,0},{0,1},{1,1},{1,2}}},
    /* Z */
    {{{0,0},{1,0},{1,1},{2,1}}, {{2,0},{1,1},{2,1},{1,2}},
     {{0,1},{1,1},{1,2},{2,2}}, {{1,0},{0,1},{1,1},{0,2}}},
    /* J */
    {{{0,0},{0,1},{1,1},{2,1}}, {{1,0},{2,0},{1,1},{1,2}},
     {{0,1},{1,1},{2,1},{2,2}}, {{1,0},{1,1},{0,2},{1,2}}},
    /* L */
    {{{2,0},{0,1},{1,1},{2,1}}, {{1,0},{1,1},{1,2},{2,2}},
     {{0,1},{1,1},{2,1},{0,2}}, {{0,0},{1,0},{1,1},{1,2}}},
};

/* 方块颜色（ANSI 背景色） */
static const char *PIECE_COLORS[7] = {
    "\033[46m", /* I - 青色 */
    "\033[43m", /* O - 黄色 */
    "\033[45m", /* T - 紫色 */
    "\033[42m", /* S - 绿色 */
    "\033[41m", /* Z - 红色 */
    "\033[44m", /* J - 蓝色 */
    "\033[47m", /* L - 白色 */
};

#define RESET "\033[0m"
#define BOLD  "\033[1m"

/* ========== 游戏状态 ========== */
typedef struct {
    int board[ROWS][COLS];
    int cur_shape;
    int cur_rot;
    int cur_x, cur_y;
    int next_shape;
    int score;
    int level;
    int lines;
    int game_over;
} Game;

static struct termios orig_termios;

/* ========== 终端控制 ========== */
void enable_raw_mode(void) {
    tcgetattr(STDIN_FILENO, &orig_termios);
    struct termios raw = orig_termios;
    raw.c_lflag &= ~(ECHO | ICANON);
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &raw);
}

void disable_raw_mode(void) {
    tcsetattr(STDIN_FILENO, TCSAFLUSH, &orig_termios);
}

int kbhit(void) {
    struct timeval tv = {0, 0};
    fd_set fds;
    FD_ZERO(&fds);
    FD_SET(STDIN_FILENO, &fds);
    return select(STDIN_FILENO + 1, &fds, NULL, NULL, &tv);
}

/* ========== 游戏逻辑 ========== */
void init_game(Game *g) {
    memset(g->board, 0, sizeof(g->board));
    srand((unsigned)time(NULL));
    g->cur_shape = rand() % 7;
    g->cur_rot = 0;
    g->cur_x = 3;
    g->cur_y = 0;
    g->next_shape = rand() % 7;
    g->score = 0;
    g->level = 1;
    g->lines = 0;
    g->game_over = FALSE;
}

/* 检测方块是否可以放置在 (x, y) 位置 */
int can_place(Game *g, int shape, int rot, int x, int y) {
    for (int i = 0; i < 4; i++) {
        int bx = x + SHAPES[shape][rot][i][0];
        int by = y + SHAPES[shape][rot][i][1];
        if (bx < 0 || bx >= COLS || by >= ROWS) return FALSE;
        if (by >= 0 && g->board[by][bx]) return FALSE;
    }
    return TRUE;
}

/* 锁定当前方块到棋盘 */
void lock_piece(Game *g) {
    for (int i = 0; i < 4; i++) {
        int bx = g->cur_x + SHAPES[g->cur_shape][g->cur_rot][i][0];
        int by = g->cur_y + SHAPES[g->cur_shape][g->cur_rot][i][1];
        if (by >= 0 && by < ROWS && bx >= 0 && bx < COLS) {
            g->board[by][bx] = g->cur_shape + 1;
        }
    }
}

/* 消除满行并计分 */
int clear_lines(Game *g) {
    int cleared = 0;
    for (int r = ROWS - 1; r >= 0; r--) {
        int full = TRUE;
        for (int c = 0; c < COLS; c++) {
            if (!g->board[r][c]) { full = FALSE; break; }
        }
        if (full) {
            cleared++;
            for (int rr = r; rr > 0; rr--) {
                memcpy(g->board[rr], g->board[rr - 1], sizeof(int) * COLS);
            }
            memset(g->board[0], 0, sizeof(int) * COLS);
            r++; /* 重新检查当前行 */
        }
    }
    return cleared;
}

/* 生成新方块 */
void spawn_piece(Game *g) {
    g->cur_shape = g->next_shape;
    g->next_shape = rand() % 7;
    g->cur_rot = 0;
    g->cur_x = 3;
    g->cur_y = 0;
    if (!can_place(g, g->cur_shape, g->cur_rot, g->cur_x, g->cur_y)) {
        g->game_over = TRUE;
    }
}

/* 硬降：直接落到底部 */
void hard_drop(Game *g) {
    while (can_place(g, g->cur_shape, g->cur_rot, g->cur_x, g->cur_y + 1)) {
        g->cur_y++;
        g->score += 2;
    }
    lock_piece(g);
    int cleared = clear_lines(g);
    if (cleared > 0) {
        int pts[] = {0, 100, 300, 500, 800};
        g->score += pts[cleared] * g->level;
        g->lines += cleared;
        g->level = g->lines / 10 + 1;
    }
    spawn_piece(g);
}

/* 尝试旋转（含墙踢） */
void try_rotate(Game *g) {
    int new_rot = (g->cur_rot + 1) % 4;
    int kicks[][2] = {{0,0}, {-1,0}, {1,0}, {0,-1}, {-1,-1}, {1,-1}, {-2,0}, {2,0}};
    for (int i = 0; i < 8; i++) {
        if (can_place(g, g->cur_shape, new_rot,
                       g->cur_x + kicks[i][0], g->cur_y + kicks[i][1])) {
            g->cur_rot = new_rot;
            g->cur_x += kicks[i][0];
            g->cur_y += kicks[i][1];
            return;
        }
    }
}

/* ========== 渲染 ========== */
void draw_cell(int cell) {
    if (cell > 0) {
        printf("%s  %s", PIECE_COLORS[cell - 1], RESET);
    } else {
        printf("\033[90m·\033[0m ");
    }
}

/* 计算幽灵方块（预览落点）Y 坐标 */
int ghost_y(Game *g) {
    int gy = g->cur_y;
    while (can_place(g, g->cur_shape, g->cur_rot, g->cur_x, gy + 1)) gy++;
    return gy;
}

void draw(Game *g) {
    /* 隐藏光标并移动到左上角 */
    printf("\033[?25l\033[H");

    int ghost = ghost_y(g);

    /* 构建临时显示板（含当前方块和幽灵） */
    int disp[ROWS][COLS];
    memcpy(disp, g->board, sizeof(disp));

    /* 画幽灵方块 */
    if (ghost != g->cur_y) {
        for (int i = 0; i < 4; i++) {
            int bx = g->cur_x + SHAPES[g->cur_shape][g->cur_rot][i][0];
            int by = ghost + SHAPES[g->cur_shape][g->cur_rot][i][1];
            if (by >= 0 && by < ROWS && bx >= 0 && bx < COLS && !disp[by][bx]) {
                disp[by][bx] = -1; /* 幽灵标记 */
            }
        }
    }

    /* 画当前活动方块（覆盖幽灵） */
    for (int i = 0; i < 4; i++) {
        int bx = g->cur_x + SHAPES[g->cur_shape][g->cur_rot][i][0];
        int by = g->cur_y + SHAPES[g->cur_shape][g->cur_rot][i][1];
        if (by >= 0 && by < ROWS && bx >= 0 && bx < COLS) {
            disp[by][bx] = g->cur_shape + 1;
        }
    }

    printf(BOLD "  ╔══════════════════╗   ╔════════════╗\n" RESET);

    for (int r = 0; r < ROWS; r++) {
        if (r == 2) {
            /* 右侧信息面板在第3行开始 */
            printf("  ║ ");
            for (int c = 0; c < COLS; c++) {
                if (disp[r][c] == -1) {
                    printf("\033[90m[]\033[0m");
                } else if (disp[r][c] > 0) {
                    printf("%s  %s", PIECE_COLORS[disp[r][c] - 1], RESET);
                } else {
                    printf("\033[90m·\033[0m ");
                }
            }
            printf(" ║   ║ NEXT:      ║\n");
        } else if (r >= 3 && r <= 6) {
            /* 预览下一个方块 */
            printf("  ║ ");
            for (int c = 0; c < COLS; c++) {
                if (disp[r][c] == -1) {
                    printf("\033[90m[]\033[0m");
                } else if (disp[r][c] > 0) {
                    printf("%s  %s", PIECE_COLORS[disp[r][c] - 1], RESET);
                } else {
                    printf("\033[90m·\033[0m ");
                }
            }
            printf(" ║   ║ ");

            /* 在 4x4 网格中画下一个方块 */
            for (int dy = 0; dy < 4; dy++) {
                if (r - 3 != dy) continue;
                for (int dx = 0; dx < 4; dx++) {
                    int found = FALSE;
                    for (int p = 0; p < 4; p++) {
                        if (SHAPES[g->next_shape][0][p][0] == dx &&
                            SHAPES[g->next_shape][0][p][1] == dy) {
                            found = TRUE;
                            break;
                        }
                    }
                    if (found) {
                        printf("%s  %s", PIECE_COLORS[g->next_shape], RESET);
                    } else {
                        printf("  ");
                    }
                }
            }
            printf("    ║\n");
        } else if (r == 8) {
            printf("  ║ ");
            for (int c = 0; c < COLS; c++) {
                if (disp[r][c] == -1) {
                    printf("\033[90m[]\033[0m");
                } else if (disp[r][c] > 0) {
                    printf("%s  %s", PIECE_COLORS[disp[r][c] - 1], RESET);
                } else {
                    printf("\033[90m·\033[0m ");
                }
            }
            printf(" ║   ║ SCORE:     ║\n");
        } else if (r == 9) {
            printf("  ║ ");
            for (int c = 0; c < COLS; c++) {
                if (disp[r][c] == -1) {
                    printf("\033[90m[]\033[0m");
                } else if (disp[r][c] > 0) {
                    printf("%s  %s", PIECE_COLORS[disp[r][c] - 1], RESET);
                } else {
                    printf("\033[90m·\033[0m ");
                }
            }
            printf(" ║   ║ %s%-10d%s║\n", BOLD, g->score, RESET);
        } else if (r == 11) {
            printf("  ║ ");
            for (int c = 0; c < COLS; c++) {
                if (disp[r][c] == -1) {
                    printf("\033[90m[]\033[0m");
                } else if (disp[r][c] > 0) {
                    printf("%s  %s", PIECE_COLORS[disp[r][c] - 1], RESET);
                } else {
                    printf("\033[90m·\033[0m ");
                }
            }
            printf(" ║   ║ LEVEL:     ║\n");
        } else if (r == 12) {
            printf("  ║ ");
            for (int c = 0; c < COLS; c++) {
                if (disp[r][c] == -1) {
                    printf("\033[90m[]\033[0m");
                } else if (disp[r][c] > 0) {
                    printf("%s  %s", PIECE_COLORS[disp[r][c] - 1], RESET);
                } else {
                    printf("\033[90m·\033[0m ");
                }
            }
            printf(" ║   ║ %s%-10d%s║\n", BOLD, g->level, RESET);
        } else if (r == 14) {
            printf("  ║ ");
            for (int c = 0; c < COLS; c++) {
                if (disp[r][c] == -1) {
                    printf("\033[90m[]\033[0m");
                } else if (disp[r][c] > 0) {
                    printf("%s  %s", PIECE_COLORS[disp[r][c] - 1], RESET);
                } else {
                    printf("\033[90m·\033[0m ");
                }
            }
            printf(" ║   ║ LINES:     ║\n");
        } else if (r == 15) {
            printf("  ║ ");
            for (int c = 0; c < COLS; c++) {
                if (disp[r][c] == -1) {
                    printf("\033[90m[]\033[0m");
                } else if (disp[r][c] > 0) {
                    printf("%s  %s", PIECE_COLORS[disp[r][c] - 1], RESET);
                } else {
                    printf("\033[90m·\033[0m ");
                }
            }
            printf(" ║   ║ %s%-10d%s║\n", BOLD, g->lines, RESET);
        } else if (r == 17) {
            printf("  ║ ");
            for (int c = 0; c < COLS; c++) {
                if (disp[r][c] == -1) {
                    printf("\033[90m[]\033[0m");
                } else if (disp[r][c] > 0) {
                    printf("%s  %s", PIECE_COLORS[disp[r][c] - 1], RESET);
                } else {
                    printf("\033[90m·\033[0m ");
                }
            }
            printf(" ║   ║ ");
            printf("\033[90mq: quit   ←→: move\033[0m ║\n");
        } else if (r == 18) {
            printf("  ║ ");
            for (int c = 0; c < COLS; c++) {
                if (disp[r][c] == -1) {
                    printf("\033[90m[]\033[0m");
                } else if (disp[r][c] > 0) {
                    printf("%s  %s", PIECE_COLORS[disp[r][c] - 1], RESET);
                } else {
                    printf("\033[90m·\033[0m ");
                }
            }
            printf(" ║   ║ ");
            printf("\033[90m↑: rotate  ↓: soft \033[0m║\n");
        } else if (r == 19) {
            printf("  ║ ");
            for (int c = 0; c < COLS; c++) {
                if (disp[r][c] == -1) {
                    printf("\033[90m[]\033[0m");
                } else if (disp[r][c] > 0) {
                    printf("%s  %s", PIECE_COLORS[disp[r][c] - 1], RESET);
                } else {
                    printf("\033[90m·\033[0m ");
                }
            }
            printf(" ║   ║ ");
            printf("\033[90mspace: hard drop  \033[0m║\n");
        } else {
            printf("  ║ ");
            for (int c = 0; c < COLS; c++) {
                if (disp[r][c] == -1) {
                    printf("\033[90m[]\033[0m");
                } else if (disp[r][c] > 0) {
                    printf("%s  %s", PIECE_COLORS[disp[r][c] - 1], RESET);
                } else {
                    printf("\033[90m·\033[0m ");
                }
            }
            printf(" ║   ║            ║\n");
        }
    }

    printf(BOLD "  ╚══════════════════╝   ╚════════════╝\n" RESET);

    if (g->game_over) {
        printf("\n\033[31m   GAME OVER!  Press 'q' to quit.\033[0m\n");
    }

    fflush(stdout);
}

/* ========== 主循环 ========== */
int main(void) {
    Game game;
    init_game(&game);

    enable_raw_mode();
    atexit(disable_raw_mode);
    printf("\033[2J\033[H"); /* 清屏 */

    int drop_interval = 500000; /* 微秒 */

    while (!game.game_over) {
        draw(&game);

        /* 等待输入，每次循环等待一小段时间 */
        int elapsed = 0;
        int interval = 50000; /* 50ms 检查一次输入 */
        while (elapsed < drop_interval) {
            if (kbhit()) {
                char ch = getchar();
                if (ch == 'q' || ch == 'Q') goto quit;
                if (ch == '\033') {
                    getchar(); /* '[' */
                    ch = getchar();
                    switch (ch) {
                        case 'A': /* 上：旋转 */
                            try_rotate(&game);
                            break;
                        case 'B': /* 下：软降 */
                            if (can_place(&game, game.cur_shape, game.cur_rot,
                                          game.cur_x, game.cur_y + 1)) {
                                game.cur_y++;
                                game.score += 1;
                            }
                            break;
                        case 'C': /* 右 */
                            if (can_place(&game, game.cur_shape, game.cur_rot,
                                          game.cur_x + 1, game.cur_y)) {
                                game.cur_x++;
                            }
                            break;
                        case 'D': /* 左 */
                            if (can_place(&game, game.cur_shape, game.cur_rot,
                                          game.cur_x - 1, game.cur_y)) {
                                game.cur_x--;
                            }
                            break;
                    }
                } else if (ch == ' ') {
                    hard_drop(&game);
                    elapsed = drop_interval; /* 跳出等待 */
                }
                draw(&game);
            }
            usleep(interval);
            elapsed += interval;
        }

        /* 自动下落 */
        if (!game.game_over) {
            if (can_place(&game, game.cur_shape, game.cur_rot,
                          game.cur_x, game.cur_y + 1)) {
                game.cur_y++;
            } else {
                lock_piece(&game);
                int cleared = clear_lines(&game);
                if (cleared > 0) {
                    int pts[] = {0, 100, 300, 500, 800};
                    game.score += pts[cleared] * game.level;
                    game.lines += cleared;
                    game.level = game.lines / 10 + 1;
                }
                spawn_piece(&game);
            }
        }

        /* 根据等级调整下落速度 */
        drop_interval = 500000 - (game.level - 1) * 40000;
        if (drop_interval < 50000) drop_interval = 50000;
    }

    /* 游戏结束后等待退出 */
    draw(&game);
    while (1) {
        if (kbhit()) {
            char ch = getchar();
            if (ch == 'q' || ch == 'Q') break;
        }
        usleep(50000);
    }

quit:
    printf("\033[?25h\033[2J\033[H"); /* 显示光标并清屏 */
    printf("Tetris - Final Score: %d  Level: %d  Lines: %d\n",
           game.score, game.level, game.lines);
    printf("Thanks for playing!\n");
    return 0;
}
