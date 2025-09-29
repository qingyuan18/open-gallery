"""
Strands专门化Agent工具
实现"Agents as Tools"模式，每个专门的agent作为工具被主agent调用
"""
import traceback
from strands import Agent, tool
try:
    from strands.models import BedrockModel
except ImportError:
    BedrockModel = None
from pydantic import Field

# generate_image 导入已移除 - 主Agent直接使用generate_image_with_context


# 系统提示词定义
PLANNER_SYSTEM_PROMPT = """
You are a design planning specialist. Your role is to:
1. Analyze user requests and break them down into actionable steps
2. Create detailed execution plans with numbered steps and clear descriptions
3. Identify when tasks require other specialists (image generation, analysis, etc.)
4. Provide clear, structured plans that other agents can follow

Create comprehensive plans that include:
- Clear objectives and goals
- Step-by-step execution sequence
- Resource requirements
- Timeline considerations
- Dependencies between tasks
- Success criteria for each step

Format your plans in a clear, organized manner that is easy to follow and implement.
"""

# IMAGE_DESIGNER_SYSTEM_PROMPT 已移除 - 主Agent直接处理图像生成

# COORDINATOR_SYSTEM_PROMPT removed - coordination is now handled by the main agent


def create_default_model():
    """创建默认的Bedrock模型实例"""
    if BedrockModel:
        try:
            return BedrockModel(
                model_id="us.anthropic.claude-3-7-sonnet-20250219-v1:0",
                region_name="us-west-2"
            )
        except Exception as e:
            print(f"⚠️ Failed to create BedrockModel: {e}")
            return None
    return None


@tool
async def planner_agent(task: str = Field(..., description="The task or project that needs planning")) -> str:
    """
    Specialized planning agent that creates detailed execution plans.

    Args:
        task: The task or project that needs planning
    """
    try:
        print("🎯 Routing to Planner Agent")
        print(f"🔍 DEBUG: Planning task: {task}")

        # 创建规划专家agent
        model = create_default_model()
        if not model:
            return "❌ Failed to create model for planner"

        print(f"🔍 DEBUG: Created planner model: {model}")

        planner = Agent(
            model=model,
            system_prompt=PLANNER_SYSTEM_PROMPT,
        )
        print(f"🔍 DEBUG: Created planner agent with no additional tools")

        formatted_task = f"""
Please create a detailed execution plan for the following task: {task}

Provide a comprehensive plan that includes:
- Clear step-by-step instructions with numbered steps
- Resource requirements for each step
- Timeline considerations and estimated durations
- Dependencies between tasks
- Success criteria for each step
- Potential challenges and mitigation strategies

Consider what specialists might be needed for each step and provide actionable guidance that can be easily followed and implemented.
"""
        print(f"🔍 DEBUG: Formatted planning task: {formatted_task}")

        print("🔍 DEBUG: Calling planner agent with streaming...")

        # 使用异步流式调用替代同步调用
        try:
            print("🔍 DEBUG: Calling planner with async streaming...")
            response_parts = []
            async for event in planner.stream_async(formatted_task):
                # 收集响应内容
                if isinstance(event, dict):
                    if 'data' in event and isinstance(event['data'], str):
                        response_parts.append(event['data'])
                    elif 'event' in event and 'contentBlockDelta' in event['event']:
                        delta = event['event']['contentBlockDelta']['delta']
                        if 'text' in delta:
                            response_parts.append(delta['text'])
                elif isinstance(event, str):
                    response_parts.append(event)
                elif hasattr(event, 'content'):
                    response_parts.append(event.content)

            response_text = ''.join(response_parts)

        except Exception as e:
            print(f"🔍 DEBUG: Planner async streaming error: {e}")
            print(f"🔍 DEBUG: Planner error traceback: {traceback.format_exc()}")
            response_text = f"❌ Planning Error: {str(e)}"

        print(f"🔍 DEBUG: Planner response: {response_text}")
        return f"📋 Planning Complete:\n{response_text}"

    except Exception as e:
        print(f"🔍 DEBUG: Planning Error: {str(e)}")
        traceback.print_exc()
        return f"❌ Planning Error: {str(e)}"


# image_designer_agent 已移除 - 主Agent直接使用generate_image_with_context


def get_specialized_agents():
    """返回所有专门化agent工具的列表"""
    return [
        planner_agent,
        # image_designer_agent 已移除 - 主Agent直接使用generate_image_with_context
        # coordinator_agent 已移除 - 主Agent直接承担协调职责
    ]