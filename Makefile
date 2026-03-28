# ============================================================================
# EpistemicFlow Makefile
# 封装常用的工程命令，简化开发和部署流程
# ============================================================================

# 默认目标
.DEFAULT_GOAL := help

# 颜色定义
BLUE := \033[0;34m
GREEN := \033[0;32m
YELLOW := \033[0;33m
RED := \033[0;31m
NC := \033[0m # No Color

# ============================================================================
# 帮助信息
# ============================================================================
.PHONY: help
help: ## 显示帮助信息
	@echo "$(BLUE)EpistemicFlow - AI驱动的自动化科研平台$(NC)"
	@echo ""
	@echo "$(GREEN)可用命令:$(NC)"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  $(YELLOW)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""

# ============================================================================
# Docker Compose 命令
# ============================================================================
.PHONY: up
up: ## 启动所有服务（后台运行）
	@echo "$(BLUE)启动 EpistemicFlow 服务...$(NC)"
	docker-compose up -d
	@echo "$(GREEN)服务已启动！$(NC)"
	@echo "$(YELLOW)访问地址: http://localhost:8000$(NC)"
	@echo "$(YELLOW)API 文档: http://localhost:8000/docs$(NC)"

.PHONY: down
down: ## 停止并删除所有服务
	@echo "$(BLUE)停止 EpistemicFlow 服务...$(NC)"
	docker-compose down
	@echo "$(GREEN)服务已停止！$(NC)"

.PHONY: restart
restart: down up ## 重启所有服务

.PHONY: logs
logs: ## 查看所有服务的日志
	docker-compose logs -f

.PHONY: logs-api
logs-api: ## 查看 API 服务的日志
	docker-compose logs -f api

.PHONY: logs-db
logs-db: ## 查看 PostgreSQL 数据库的日志
	docker-compose logs -f db

.PHONY: ps
ps: ## 查看所有服务的状态
	docker-compose ps

# ============================================================================
# Docker 构建命令
# ============================================================================
.PHONY: build
build: ## 重新构建所有服务
	@echo "$(BLUE)构建 Docker 镜像...$(NC)"
	docker-compose build --no-cache
	@echo "$(GREEN)构建完成！$(NC)"

.PHONY: rebuild
rebuild: down build up ## 重新构建并启动所有服务

.PHONY: build-api
build-api: ## 仅构建 API 服务
	@echo "$(BLUE)构建 API 服务镜像...$(NC)"
	docker-compose build api
	@echo "$(GREEN)构建完成！$(NC)"

# ============================================================================
# 数据库管理命令
# ============================================================================
.PHONY: migrate
migrate: ## 执行数据库迁移
	@echo "$(BLUE)执行数据库迁移...$(NC)"
	docker-compose exec api alembic upgrade head
	@echo "$(GREEN)数据库迁移完成！$(NC)"

.PHONY: migrate-down
migrate-down: ## 回滚数据库迁移
	@echo "$(BLUE)回滚数据库迁移...$(NC)"
	docker-compose exec api alembic downgrade -1
	@echo "$(GREEN)数据库迁移已回滚！$(NC)"

.PHONY: migrate-create
migrate-create: ## 创建新的数据库迁移（需要提供迁移名称）
	@read -p "请输入迁移名称: " name; \
	docker-compose exec api alembic revision --autogenerate -m "$$name"

.PHONY: db-shell
db-shell: ## 进入 PostgreSQL 数据库 Shell
	docker-compose exec db psql -U epistemicflow -d epistemicflow

.PHONY: db-backup
db-backup: ## 备份数据库
	@echo "$(BLUE)备份数据库...$(NC)"
	@mkdir -p ./backups
	@docker-compose exec -T db pg_dump -U epistemicflow epistemicflow > ./backups/epistemicflow_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "$(GREEN)数据库备份完成！$(NC)"

.PHONY: db-restore
db-restore: ## 恢复数据库（需要提供备份文件名）
	@read -p "请输入备份文件名（如: epistemicflow_20240101_120000.sql）: " file; \
	if [ -f "./backups/$$file" ]; then \
		echo "$(BLUE)恢复数据库...$(NC)"; \
		docker-compose exec -T db psql -U epistemicflow -d epistemicflow < ./backups/$$file; \
		echo "$(GREEN)数据库恢复完成！$(NC)"; \
	else \
		echo "$(RED)备份文件不存在: ./backups/$$file$(NC)"; \
		exit 1; \
	fi

.PHONY: db-reset
db-reset: down ## 重置数据库（删除所有数据）
	@echo "$(RED)警告: 此操作将删除所有数据库数据！$(NC)"
	@read -p "确认重置数据库？(yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(BLUE)删除数据库数据卷...$(NC)"; \
		docker volume rm epistemicflow_postgres-data 2>/dev/null || true; \
		echo "$(GREEN)数据库已重置！$(NC)"; \
		echo "$(YELLOW)运行 'make up' 重新启动服务$(NC)"; \
	else \
		echo "$(YELLOW)操作已取消$(NC)"; \
	fi

# ============================================================================
# 开发命令
# ============================================================================
.PHONY: dev
dev: ## 启动开发环境（带热重载）
	@echo "$(BLUE)启动开发环境...$(NC)"
	@docker-compose -f docker-compose.yml -f docker-compose.dev.yml up

.PHONY: shell
shell: ## 进入 API 容器的 Shell
	docker-compose exec api /bin/bash

.PHONY: install
install: ## 安装 Python 依赖
	@echo "$(BLUE)安装 Python 依赖...$(NC)"
	pip install -r requirements.txt
	@echo "$(GREEN)依赖安装完成！$(NC)"

.PHONY: install-dev
install-dev: ## 安装开发依赖
	@echo "$(BLUE)安装开发依赖...$(NC)"
	pip install -r requirements.txt
	pip install -e ".[dev]"
	@echo "$(GREEN)开发依赖安装完成！$(NC)"

# ============================================================================
# 测试命令
# ============================================================================
.PHONY: test
test: ## 运行所有测试
	@echo "$(BLUE)运行测试...$(NC)"
	docker-compose exec api pytest tests/ -v
	@echo "$(GREEN)测试完成！$(NC)"

.PHONY: test-unit
test-unit: ## 运行单元测试
	@echo "$(BLUE)运行单元测试...$(NC)"
	docker-compose exec api pytest tests/ -v -m unit
	@echo "$(GREEN)单元测试完成！$(NC)"

.PHONY: test-integration
test-integration: ## 运行集成测试
	@echo "$(BLUE)运行集成测试...$(NC)"
	docker-compose exec api pytest tests/ -v -m integration
	@echo "$(GREEN)集成测试完成！$(NC)"

.PHONY: test-cov
test-cov: ## 运行测试并生成覆盖率报告
	@echo "$(BLUE)运行测试并生成覆盖率报告...$(NC)"
	docker-compose exec api pytest tests/ -v --cov=. --cov-report=html --cov-report=term
	@echo "$(GREEN)覆盖率报告已生成: htmlcov/index.html$(NC)"

.PHONY: lint
lint: ## 运行代码检查
	@echo "$(BLUE)运行代码检查...$(NC)"
	docker-compose exec api ruff check .
	docker-compose exec api mypy .
	@echo "$(GREEN)代码检查完成！$(NC)"

.PHONY: format
format: ## 格式化代码
	@echo "$(BLUE)格式化代码...$(NC)"
	docker-compose exec api black .
	docker-compose exec api ruff check --fix .
	@echo "$(GREEN)代码格式化完成！$(NC)"

# ============================================================================
# 清理命令
# ============================================================================
.PHONY: clean
clean: ## 清理临时文件和缓存
	@echo "$(BLUE)清理临时文件...$(NC)"
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type f -name "*.pyo" -delete 2>/dev/null || true
	find . -type f -name "*.pyd" -delete 2>/dev/null || true
	find . -type f -name ".DS_Store" -delete 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	@echo "$(GREEN)清理完成！$(NC)"

.PHONY: clean-docker
clean-docker: ## 清理 Docker 资源（镜像、容器、卷）
	@echo "$(RED)警告: 此操作将删除所有 Docker 资源！$(NC)"
	@read -p "确认清理 Docker 资源？(yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		echo "$(BLUE)清理 Docker 资源...$(NC)"; \
		docker-compose down -v --rmi all --remove-orphans; \
		docker system prune -a -f; \
		echo "$(GREEN)Docker 资源清理完成！$(NC)"; \
	else \
		echo "$(YELLOW)操作已取消$(NC)"; \
	fi

.PHONY: clean-all
clean-all: clean clean-docker ## 清理所有临时文件和 Docker 资源

# ============================================================================
# 监控命令
# ============================================================================
.PHONY: health
health: ## 检查服务健康状态
	@echo "$(BLUE)检查服务健康状态...$(NC)"
	@echo ""
	@echo "$(GREEN)API 服务:$(NC)"
	@curl -s http://localhost:8000/health | jq . || echo "  $(RED)不可访问$(NC)"
	@echo ""
	@echo "$(GREEN)数据库服务:$(NC)"
	@docker-compose exec -T db pg_isready -U epistemicflow || echo "  $(RED)不可用$(NC)"
	@echo ""
	@echo "$(GREEN)容器状态:$(NC)"
	@docker-compose ps

.PHONY: stats
stats: ## 查看资源使用统计
	docker stats --no-stream --format "table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

# ============================================================================
# 部署命令
# ============================================================================
.PHONY: deploy
deploy: ## 部署到生产环境
	@echo "$(BLUE)部署到生产环境...$(NC)"
	@echo "$(YELLOW)注意: 请确保已配置生产环境变量$(NC)"
	@read -p "确认部署到生产环境？(yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		make build; \
		make down; \
		docker-compose -f docker-compose.yml -f docker-compose.prod.yml up -d; \
		echo "$(GREEN)部署完成！$(NC)"; \
	else \
		echo "$(YELLOW)操作已取消$(NC)"; \
	fi

.PHONY: backup
backup: ## 备份所有数据（数据库 + 存储文件）
	@echo "$(BLUE)备份所有数据...$(NC)"
	@mkdir -p ./backups
	@docker-compose exec -T db pg_dump -U epistemicflow epistemicflow > ./backups/epistemicflow_db_$(shell date +%Y%m%d_%H%M%S).sql
	@tar -czf ./backups/epistemicflow_storage_$(shell date +%Y%m%d_%H%M%S).tar.gz ./storage
	@echo "$(GREEN)备份完成！$(NC)"

# ============================================================================
# 信息命令
# ============================================================================
.PHONY: info
info: ## 显示系统信息
	@echo "$(BLUE)EpistemicFlow 系统信息$(NC)"
	@echo ""
	@echo "$(GREEN)版本:$(NC) 0.1.0"
	@echo "$(GREEN)Python 版本:$(NC) $(shell python --version 2>/dev/null || echo "未安装")"
	@echo "$(GREEN)Docker 版本:$(NC) $(shell docker --version 2>/dev/null || echo "未安装")"
	@echo "$(GREEN)Docker Compose 版本:$(NC) $(shell docker-compose --version 2>/dev/null || echo "未安装")"
	@echo ""
	@echo "$(GREEN)服务状态:$(NC)"
	@docker-compose ps --format json 2>/dev/null | jq -r '.[] | "  \(.Service): \(.State)' || echo "  服务未运行"

.PHONY: env
env: ## 显示环境变量（仅开发环境）
	@echo "$(BLUE)环境变量:$(NC)"
	@docker-compose exec api env | grep -E '^(APP_|DB_|LLM_|DEFAULT_|WORKFLOW_|LOG_)' | sort

# ============================================================================
# 快速开始
# ============================================================================
.PHONY: quickstart
quickstart: ## 快速开始（安装依赖 + 启动服务）
	@echo "$(BLUE)快速开始 EpistemicFlow...$(NC)"
	@echo ""
	@echo "$(YELLOW)1. 检查 Docker 环境...$(NC)"
	@docker --version > /dev/null 2>&1 || (echo "$(RED)错误: Docker 未安装$(NC)" && exit 1)
	@docker-compose --version > /dev/null 2>&1 || (echo "$(RED)错误: Docker Compose 未安装$(NC)" && exit 1)
	@echo "$(GREEN)✓ Docker 环境正常$(NC)"
	@echo ""
	@echo "$(YELLOW)2. 构建镜像...$(NC)"
	@make build
	@echo ""
	@echo "$(YELLOW)3. 启动服务...$(NC)"
	@make up
	@echo ""
	@echo "$(YELLOW)4. 执行数据库迁移...$(NC)"
	@sleep 10
	@make migrate
	@echo ""
	@echo "$(GREEN)✓ EpistemicFlow 启动成功！$(NC)"
	@echo ""
	@echo "$(BLUE)访问地址:$(NC) http://localhost:8000"
	@echo "$(BLUE)API 文档:$(NC) http://localhost:8000/docs"
	@echo ""
	@echo "$(YELLOW)常用命令:$(NC)"
	@echo "  make logs      - 查看日志"
	@echo "  make test      - 运行测试"
	@echo "  make down      - 停止服务"
	@echo "  make shell     - 进入容器"
