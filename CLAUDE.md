# 项目配置

## 运行环境

使用 uv 管理虚拟环境，不要使用 `python` 命令：

```bash
uv venv
source .venv/bin/activate
python3 <script>.py
```

- 不要使用 `python`（会报 command not found），使用 `python3`
- 如需安装依赖，使用 `uv pip install`

## 目录结构

- `frontend/` - 前端项目（HTML/CSS/JS），每个项目一个子目录
- `game/` - 游戏项目，所有游戏都放在此目录下，每个游戏一个子目录
