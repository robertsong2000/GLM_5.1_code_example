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
