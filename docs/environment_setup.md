# 环境与依赖说明

## 1. 环境管理原则

当前项目统一使用 `uv` 管理：

- Python 版本
- 虚拟环境
- 依赖安装
- 锁文件
- 运行命令

我们不在项目里混用 `pip`、`poetry`、`conda env` 作为主入口。

可以安装系统 Python，也可以通过已有解释器创建环境，但项目级执行统一通过 `uv` 完成。

## 2. 当前项目状态

当前仓库已经完成以下初始化：

- 已存在 [pyproject.toml](/Users/admin/weichy/strategy_agent/pyproject.toml)
- 已存在 [uv.lock](/Users/admin/weichy/strategy_agent/uv.lock)
- 已创建本地虚拟环境 `/Users/admin/weichy/strategy_agent/.venv`
- 已安装 `google-adk`

## 3. 常用命令

### 安装或同步依赖

```bash
UV_CACHE_DIR=.uv-cache uv sync
```

说明：

- `UV_CACHE_DIR=.uv-cache` 用于把 `uv` 缓存放在项目目录下
- 这样可以避免某些环境下默认缓存目录不可写的问题

### 添加依赖

```bash
UV_CACHE_DIR=.uv-cache uv add <package>
```

例如：

```bash
UV_CACHE_DIR=.uv-cache uv add pandas
```

### 运行 Python 脚本

```bash
UV_CACHE_DIR=.uv-cache uv run python your_script.py
```

### 执行临时代码

```bash
UV_CACHE_DIR=.uv-cache uv run python - <<'PY'
print("hello")
PY
```

## 4. 依赖管理约定

### 约定 1：所有运行入口都走 `uv run`

例如：

- `uv run python ...`
- `uv run pytest`
- `uv run strategy-agent`

### 约定 2：新增依赖必须写入 `pyproject.toml`

不允许仅在本地虚拟环境中临时安装而不入库。

### 约定 3：提交依赖变更时同步提交 `uv.lock`

这样能保证团队环境尽量一致。

### 约定 4：尽量区分运行依赖和开发依赖

后续如果引入测试、格式化、类型检查工具，建议使用 `uv add --dev`。

## 5. 当前核心依赖

第一批基础依赖已经明确：

- `google-adk`

后续随着系统设计推进，可能再补：

- 数据处理：`pandas`、`pyarrow`
- API 服务：`fastapi`
- 测试：`pytest`

但这些要在设计文档明确后再逐步加入，不着急一次性装满。

## 6. 为什么要统一用 uv

选择 `uv` 的主要原因：

- 安装和解析速度快
- 锁文件和环境管理体验统一
- 比较适合从空仓库快速起一个 Python 项目
- 后续 CI / 本地开发 / Agent 自动执行都更容易统一命令入口

## 7. 当前注意事项

### 注意 1：`.venv` 不入库

已经通过 `.gitignore` 忽略。

### 注意 2：`.uv-cache` 不入库

已经通过 `.gitignore` 忽略。

### 注意 3：如果未来需要固定 Python 版本

可以进一步在项目文档中明确推荐版本，必要时再补更严格的运行约束。

## 8. 后续建议

当我们开始进入实现阶段时，建议再补一份：

- `docs/development_workflow.md`

内容包括：

- 启动方式
- 测试方式
- 文档更新约定
- 分支与提交规范
