# LangGraph to AWS Strands Migration Guide

本文档描述了将项目从LangGraph agent迁移到AWS Strands agent的详细变更。

## 迁移概述

### 主要变更
1. **依赖更新**: 移除LangGraph相关依赖，添加AWS Strands依赖
2. **服务模块**: 创建新的`strands_service.py`替换`langgraph_service.py`
3. **工具格式**: 将LangChain工具格式转换为Strands工具格式
4. **多Agent模式**: 使用Strands内置swarm工具替换langgraph_swarm
5. **上下文管理**: 实现新的上下文管理系统

## 文件变更详情

### 1. 依赖配置 (`server/requirements.txt`)
**移除的依赖:**
- `langgraph`
- `langchain_ollama`
- `langchain_openai`
- `langgraph-swarm`

**添加的依赖:**
- `strands-agents`
- `strands-agents-tools`

### 2. 新增文件

#### `server/services/strands_service.py`
- 替换原来的`langgraph_service.py`
- 实现`strands_agent()`和`strands_multi_agent()`函数
- 支持多种模型提供商：Bedrock、OpenAI、Anthropic、Ollama
- 集成Strands swarm工具用于多agent协作

#### `server/services/strands_context.py`
- 实现上下文管理系统
- 在工具调用中传递session_id、canvas_id等信息
- 提供`SessionContextManager`上下文管理器

#### `server/tools/strands_write_plan.py`
- Strands格式的计划制定工具
- 从LangChain `@tool`装饰器转换为Strands `@tool`装饰器

#### `server/tools/strands_image_generators.py`
- Strands格式的图像生成工具
- 保持原有的图像生成功能
- 使用上下文管理器获取session信息

#### `server/tools/strands_specialized_agents.py`
- 实现"Agents as Tools"模式的专门化agent
- 包含2个专门agent：planner_agent, image_designer_agent
- 每个agent都有特定的专业领域和工具集，专注于设计和创作任务
- coordinator_agent已移除，协调功能由主Agent直接承担

#### `server/test_strands_migration.py`
- 迁移测试脚本
- 验证所有组件是否正常工作

### 3. 修改的文件

#### `server/services/chat_service.py`
**变更:**
- 导入: `from services.langgraph_service import langgraph_agent, langgraph_multi_agent` 
  → `from services.strands_service import strands_agent, strands_multi_agent`
- 函数调用: `langgraph_multi_agent()` → `strands_multi_agent()`

## 功能对比

### 单Agent模式
| 功能 | LangGraph | Strands |
|------|-----------|---------|
| Agent创建 | `create_react_agent()` | `Agent()` |
| 流式处理 | `agent.astream()` | `agent.stream_async()` |
| 工具集成 | LangChain tools | Strands tools |
| 模型支持 | LangChain models | Strands models |

### 多Agent模式
| 功能 | LangGraph | Strands |
|------|-----------|---------|
| 多Agent框架 | `langgraph_swarm` | "Agents as Tools"模式 |
| Agent协作 | 手动handoff工具 | 自然语言路由 |
| 并行处理 | 自定义并行agent | 专门的parallel_data_extractor |
| 协调模式 | 固定handoff链 | 智能orchestrator路由 |

## 保持的功能

1. **前端接口**: WebSocket通信协议保持不变
2. **工具功能**: 图像生成、计划制定等核心功能保持不变
3. **模型支持**: 继续支持Bedrock、OpenAI、Anthropic、Ollama
4. **流式处理**: 保持实时流式响应
5. **数据库集成**: 聊天记录持久化功能不变

## 新增功能

1. **智能Swarm配置**: 根据任务类型自动推荐swarm配置
2. **上下文管理**: 更好的工具间信息传递
3. **灵活的协作模式**: 支持多种agent协作模式
4. **简化的工具定义**: 更简洁的工具定义语法

## 使用指南

### 启动服务
```bash
# 安装新依赖
pip install strands-agents strands-agents-tools

# 运行测试
python server/test_strands_migration.py

# 启动服务
python server/main.py
```

### 配置说明

#### 模型配置
Strands支持的模型配置与原来保持一致：
```json
{
  "provider": "bedrock",
  "model": "us.anthropic.claude-3-7-sonnet-20250219-v1:0",
  "region": "us-west-2"
}
```

#### Swarm配置
新的多agent模式支持更灵活的配置：
- `swarm_size`: 2-10个agent
- `coordination_pattern`: "collaborative", "competitive", "hybrid"
- `task_type`: "image_generation", "planning", "analysis", "parallel_extraction"

## 故障排除

### 常见问题

1. **导入错误**: 确保安装了`strands-agents`和`strands-agents-tools`
2. **模型访问**: 确保AWS Bedrock模型访问权限已配置
3. **工具调用**: 检查上下文管理器是否正确设置

### 调试工具
- 运行`test_strands_migration.py`检查基本功能
- 检查WebSocket连接和消息格式
- 查看服务器日志中的错误信息

## 迁移验证

完成迁移后，请验证以下功能：
- [ ] 单agent对话功能正常
- [ ] 多agent swarm协作正常
- [ ] 图像生成功能正常
- [ ] 计划制定功能正常
- [ ] WebSocket实时通信正常
- [ ] 数据库记录保存正常

## 回滚方案

如需回滚到LangGraph版本：
1. 恢复`requirements.txt`中的LangGraph依赖
2. 修改`chat_service.py`导入回`langgraph_service`
3. 重新安装依赖：`pip install -r requirements.txt`

## 技术支持

如遇到问题，请检查：
1. AWS Strands文档：https://strandsagents.com/
2. 项目issue和日志
3. 模型访问权限和配置
