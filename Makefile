# SuperBizAgent Makefile
# Python 版 (FastAPI + LangChain + LangGraph)

# 配置变量
SERVER_URL = http://localhost:9900
UPLOAD_API = $(SERVER_URL)/api/upload
DOCS_DIR = aiops-docs
HEALTH_CHECK_API = $(SERVER_URL)/milvus/health
DOCKER_COMPOSE_FILE = docker-compose.yml
MILVUS_CONTAINER = milvus-standalone

# 颜色输出
GREEN = \033[0;32m
YELLOW = \033[0;33m
RED = \033[0;31m
NC = \033[0m # No Color

.PHONY: help init start stop restart check upload clean up down status wait

# 默认目标：显示帮助信息
help:
	@echo "$(GREEN)SuperBizAgent Makefile (Python版)$(NC)"
	@echo ""
	@echo "可用命令："
	@echo "  $(YELLOW)make init$(NC)    - 🚀 一键初始化（启动Docker → 启动服务 → 上传文档）"
	@echo "  $(YELLOW)make up$(NC)      - 启动 Docker Compose（Milvus 向量数据库）"
	@echo "  $(YELLOW)make down$(NC)    - 停止 Docker Compose"
	@echo "  $(YELLOW)make status$(NC)  - 查看 Docker 容器状态"
	@echo "  $(YELLOW)make start$(NC)   - 启动 FastAPI 服务（后台运行）"
	@echo "  $(YELLOW)make stop$(NC)    - 停止 FastAPI 服务"
	@echo "  $(YELLOW)make restart$(NC) - 重启 FastAPI 服务"
	@echo "  $(YELLOW)make check$(NC)   - 检查服务器是否运行"
	@echo "  $(YELLOW)make upload$(NC)  - 上传 aiops-docs 目录下的所有文档"
	@echo "  $(YELLOW)make clean$(NC)   - 清理临时文件"
	@echo ""
	@echo "使用示例："
	@echo "  1. 一键初始化: make init"
	@echo "  2. 手动启动: make up && make start && make upload"
	@echo "  3. 停止服务: make stop && make down"

# 一键初始化
init:
	@echo "$(GREEN)🚀 SuperBizAgent 一键启动...$(NC)"
	@echo ""
	@echo "$(YELLOW)正在构建并启动全部服务 (Milvus + App)...$(NC)"
	@docker compose up -d --build
	@echo ""
	@$(MAKE) wait
	@echo ""
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo "$(GREEN)✅ 启动完成！知识库已自动向量化，服务已就绪$(NC)"
	@echo "$(GREEN)═══════════════════════════════════════════════════════$(NC)"
	@echo ""
	@echo "$(GREEN)🌐 访问地址:$(NC)"
	@echo "   Web UI:  $(SERVER_URL)"
	@echo "   Attu:    http://localhost:8000"
	@echo ""

# 等待服务就绪
wait:
	@echo "$(YELLOW)⏳ 等待服务就绪...$(NC)"
	@max_attempts=120; attempt=0; \
	while [ $$attempt -lt $$max_attempts ]; do \
		if curl -s -f $(HEALTH_CHECK_API) > /dev/null 2>&1; then \
			echo "$(GREEN)✅ 服务已就绪！$(NC)"; \
			exit 0; \
		fi; \
		attempt=$$((attempt + 1)); \
		printf "$(YELLOW)   等待中... [$$attempt/$$max_attempts]$(NC)\r"; \
		sleep 2; \
	done; \
	echo ""; \
	echo "$(RED)❌ 启动超时！$(NC)"; \
	echo "查看日志: docker compose logs app"; \
	exit 1

# 启动全部服务
up:
	@echo "$(YELLOW)🐳 启动全部服务...$(NC)"
	@docker compose up -d --build
	@$(MAKE) wait
	@echo "$(GREEN)✅ 全部服务运行中$(NC)"

# 停止全部服务
down:
	@echo "$(YELLOW)🛑 停止全部服务...$(NC)"
	@docker compose down
	@echo "$(GREEN)✅ 已停止$(NC)"

# 重启
restart:
	@echo "$(YELLOW)🔄 重启全部服务...$(NC)"
	@docker compose down
	@docker compose up -d --build
	@$(MAKE) wait
	@echo "$(GREEN)✅ 重启完成$(NC)"

# 查看日志
logs:
	@docker compose logs -f app

# 重新灌入知识库
reindex:
	@echo "$(YELLOW)📤 重新索引知识库文档...$(NC)"
	@for file in $(DOCS_DIR)/*.md; do \
		filename=$$(basename "$$file"); \
		echo "  上传: $$filename"; \
		curl -s -X POST $(UPLOAD_API) -F "file=@$$file" -H "Accept: application/json" > /dev/null; \
		sleep 0.5; \
	done
	@echo "$(GREEN)✅ 索引完成$(NC)"

# 检查服务器是否运行
check:
	@echo "$(YELLOW)🔍 检查服务状态...$(NC)"
	@if curl -s -f $(HEALTH_CHECK_API) > /dev/null 2>&1; then \
		echo "$(GREEN)✅ 服务运行正常 ($(SERVER_URL))$(NC)"; \
	else \
		echo "$(RED)❌ 服务未运行！执行 make init 启动$(NC)"; \
		exit 1; \
	fi

# 查看容器状态
status:
	@docker compose ps

# 清理临时文件
clean:
	@echo "$(YELLOW)🧹 清理临时文件...$(NC)"
	@rm -rf uploads/*.tmp
	@rm -f server.pid server.log
	@echo "$(GREEN)✅ 清理完成$(NC)"

# 显示文档列表
list-docs:
	@echo "$(YELLOW)📚 $(DOCS_DIR) 目录下的文档:$(NC)"
	@if [ -d "$(DOCS_DIR)" ]; then \
		ls -lh $(DOCS_DIR)/*.md 2>/dev/null || echo "$(RED)没有找到 .md 文件$(NC)"; \
	else \
		echo "$(RED)目录 $(DOCS_DIR) 不存在$(NC)"; \
	fi
