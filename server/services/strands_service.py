"""
Strands Agent Service
统一的 AWS Strands Agent 服务（单 agent + tools 模式）
"""
import json
import traceback
from typing import Dict, Any

from strands import Agent
try:
    from strands.models import BedrockModel
    from strands.models.openai import OpenAIModel
    from strands.models.anthropic import AnthropicModel
    from strands.models.ollama import OllamaModel
except ImportError:
    from strands.models import BedrockModel
    # 如果导入失败，使用BedrockModel作为fallback
    try:
        from strands.models.openai import OpenAIModel
    except ImportError:
        OpenAIModel = BedrockModel
    try:
        from strands.models.anthropic import AnthropicModel
    except ImportError:
        AnthropicModel = BedrockModel
    try:
        from strands.models.ollama import OllamaModel
    except ImportError:
        OllamaModel = BedrockModel

from services.db_service import db_service
from services.config_service import config_service
from services.websocket_service import send_to_websocket, send_to_user_websocket
from services.strands_context import SessionContextManager, set_intention_result
from services.user_context import get_current_user_id

from tools.strands_intention import analyze_edit_intention




def _process_message_content_for_agent(content):
    """
    处理消息内容，过滤掉图像消息或将其转换为文本描述
    确保传递给Agent的内容是纯文本格式
    """
    if isinstance(content, str):
        # 如果是字符串，检查是否包含图像引用
        if '/api/file/' in content and ('im_' in content or '.jpg' in content or '.png' in content):
            # 这是包含图像引用的消息，转换为文本描述
            return "[图像消息]"
        return content

    elif isinstance(content, list):
        # 如果是列表，过滤掉图像内容，保留文本内容
        text_parts = []
        for item in content:
            if isinstance(item, dict):
                if item.get('type') == 'text' and 'text' in item:
                    text_parts.append(item['text'])
                elif item.get('type') == 'image_url':
                    text_parts.append("[图像]")
            elif isinstance(item, str):
                text_parts.append(item)

        return ' '.join(text_parts) if text_parts else None

    else:
        # 其他类型，尝试转换为字符串
        return str(content) if content else None


# 全局变量来跟踪已发送的事件，防止重复
_sent_events = set()


# Map toolUseId to tool name for better logging
_tool_call_names = {}
# Track current tool use per session for better logging/id propagation
_current_tool_use_by_session = {}



async def send_user_websocket_message(session_id: str, event: dict):
    """Send WebSocket message to the current user"""
    try:
        user_id = get_current_user_id()
        await send_to_user_websocket(session_id, event, user_id)
    except Exception as e:
        # Fallback to broadcast if user context is not available
        print(f"⚠️ User context not available, falling back to broadcast: {e}")
        await send_to_websocket(session_id, event)


def _extract_tool_result_texts(tool_result) -> list:
    """从 toolResult 结构中提取所有文本内容"""
    texts = []
    if isinstance(tool_result, dict) and 'content' in tool_result:
        for content in tool_result['content']:
            if isinstance(content, dict) and content.get('type') == 'text' and 'text' in content:
                texts.append(content['text'])
    return texts


def _extract_first_json_object(text: str):
    """Extract the first top-level JSON object from a text stream.
    Handles leading/trailing non-JSON text and ignores braces inside strings.
    Returns a parsed dict if found, else None.
    """
    try:
        in_str = False
        esc = False
        depth = 0
        start = -1
        for i, ch in enumerate(text):
            if esc:
                esc = False
                continue
            if ch == '\\':
                esc = True
                continue
            if ch == '"':
                in_str = not in_str
                continue
            if in_str:
                continue
            if ch == '{':
                if depth == 0:
                    start = i
                depth += 1
            elif ch == '}':
                if depth > 0:
                    depth -= 1
                    if depth == 0 and start != -1:
                        candidate = text[start:i+1]
                        try:
                            return json.loads(candidate)
                        except Exception:
                            # continue searching if this candidate fails
                            pass
        return None
    except Exception:
        return None

def create_model_instance(text_model: Dict[str, Any]):
    """创建模型实例"""
    model = text_model.get('model')
    provider = text_model.get('provider')
    url = text_model.get('url')
    api_key = config_service.app_config.get(provider, {}).get("api_key", "")
    max_tokens = text_model.get('max_tokens', 8148)

    if provider == 'ollama':
        try:
            return OllamaModel(
                model=model,
                base_url=url,
            )
        except:
            return BedrockModel(model_id=model)
    elif provider == 'bedrock':
        region = config_service.app_config.get(provider, {}).get("region", "us-west-2")
        return BedrockModel(
            model_id=model,
            region_name=region,
            max_tokens=max_tokens,
            temperature=0
        )
    elif provider == 'anthropic':
        try:
            return AnthropicModel(
                model=model,
                api_key=api_key,
                max_tokens=max_tokens,
                temperature=0
            )
        except:
            return BedrockModel(model_id=model)
    elif provider == 'siliconflow':
        try:
            return OpenAIModel(
                client_args={
                    "api_key": api_key,
                    "base_url": url
                },
                model_id=model,
                max_tokens=max_tokens,
                temperature=0.7
            )
        except Exception as e:
            print(f"❌ Failed to create OpenAIModel for siliconflow: {e}")
            # 不要降级到BedrockModel，因为deepseek模型ID在Bedrock中无效
            raise Exception(f"Failed to create siliconflow model: {e}")
    else:
        try:
            return OpenAIModel(
                model=model,
                api_key=api_key,
                base_url=url,
                temperature=0,
                max_tokens=max_tokens,
            )
        except:
            return BedrockModel(model_id=model)


async def strands_agent(messages, canvas_id, session_id, text_model, image_model, video_model=None, system_prompt: str = None, auto_model_selection: bool = True):
    """单个 Strands Agent 处理"""
    try:
        model = create_model_instance(text_model)

        available_tools = []

        print(f"🔍 DEBUG: image_model={image_model}, video_model={video_model}")

        # Always expose contextual tools directly
        available_tools.append("generate_image_with_context: Generate images based on text descriptions")
        available_tools.append("generate_video_with_context: Generate videos based on text descriptions and optionally input images")

        # Intent classification is executed BEFORE this agent via a child agent.
        # The resulting generation_model is available via session context; tools will fall back to it if model_override is omitted.


        tools_description = "\n".join([f"- {tool}" for tool in available_tools])

        # 根据auto_model_selection参数动态调整系统提示
        if auto_model_selection:
            intent_guidance = """
When users request image or video generation:
1. Intent classification has ALREADY been performed BEFORE this agent run by a dedicated child agent. Do NOT call use_agent again. Use the provided generation_model by passing it via model_override when invoking generation tools. If model_override is omitted, tools will fall back to the session's generation_model (if available).
2. Create a detailed, descriptive prompt for the content
3. Use the appropriate generation tool:
   - If generation_model starts with 'flux-': call generate_image_with_context
   - If generation_model starts with 'h3-': call generate_video_with_context
4. Always pass the detected generation_model via model_override when calling generation tools. Valid values:
   - flux-kontext (single image edit)
   - qwen-image-multiple (multiple image edit)
   - flux-t2i (text-to-image)
   - h3-t2v (text-to-video)
   - h3-i2v (image-to-video)
   Important: Explicitly pass model_override=generation_model for precision and traceability.
"""
        else:
            intent_guidance = """
When users request image or video generation:
1. 自动模型选择已关闭，请直接使用用户界面选择的模型进行生成。
2. Create a detailed, descriptive prompt for the content
3. Use the appropriate generation tool based on user's interface model selection:
   - For image generation: call generate_image_with_context
   - For video generation: call generate_video_with_context
4. DO NOT pass model_override parameter - let the tools use the user's selected models from the interface.
"""

        agent_system_prompt = system_prompt or f"""
You are a professional AI assistant with image and video generation capabilities.

Available tools:
{tools_description}

{intent_guidance}

5. Choose appropriate aspect ratios based on the content
6. The tools support both text-to-image/video and image-to-image/video modes
7. For I2I/I2V, you can specify an input_image or use use_previous_image=True
8. For each single user request/turn, call at most ONE generation tool (image or video). Do NOT call generation tools multiple times in the same turn unless the user explicitly asks to refine or generate another version. After receiving the first successful tool result, provide the final answer and stop further tool calls in this turn.

IMPORTANT - Context Usage:
- Image tool has use_previous_image=True by default, which automatically uses the most recent image from this conversation
- Video tool has use_previous_image=True by default, which automatically uses the most recent image for I2V generation
- Use use_previous_image=TRUE when the user wants to EDIT, MODIFY, or BUILD UPON an existing image/video
- Use use_previous_image=FALSE when the user wants a COMPLETELY NEW, UNRELATED content or explicitly asks for a "new" creation
- IMPORTANT: Some models (like flux-t2i, h3-t2v) are text-only models and don't support input images. The tools will automatically ignore use_previous_image for these models
- If no previous image exists in the conversation, the tools will inform you appropriately

For other tasks, use your general knowledge and reasoning capabilities.
Be helpful, accurate, and creative in your responses.
"""

        # 获取历史消息并转换为Strands格式
        try:
            # 获取数据库中的历史消息
            historical_messages = db_service.get_chat_history(session_id)
            print(f"🔍 DEBUG: Retrieved {len(historical_messages)} historical messages from database")

            # 将当前传入的messages与历史消息合并，去重
            all_messages = []

            # 添加历史消息，过滤掉图像内容
            for hist_msg in historical_messages:
                if hist_msg.get('role') and hist_msg.get('content'):
                    # 处理content，过滤掉图像消息或转换为文本描述
                    content = hist_msg['content']
                    processed_content = _process_message_content_for_agent(content)

                    if processed_content:  # 只添加有效的文本内容
                        # 转换为Bedrock标准消息格式
                        all_messages.append({
                            'role': hist_msg['role'],
                            'content': [
                                {
                                    'text': processed_content
                                }
                            ]
                        })

            # 添加当前消息（如果不在历史中）
            for current_msg in messages:
                if current_msg.get('role') and current_msg.get('content'):
                    # 简单去重：检查最后几条消息是否已存在
                    is_duplicate = False
                    for existing_msg in all_messages[-3:]:  # 只检查最后3条避免性能问题
                        if (existing_msg.get('role') == current_msg.get('role') and
                            existing_msg.get('content') == current_msg.get('content')):
                            is_duplicate = True
                            break

                    if not is_duplicate:
                        # 转换当前消息为Bedrock标准格式
                        content = current_msg['content']
                        if isinstance(content, str):
                            formatted_content = [{'text': content}]
                        elif isinstance(content, list):
                            # 转换列表格式，确保使用Bedrock格式
                            formatted_content = []
                            for item in content:
                                if isinstance(item, dict):
                                    if item.get('type') == 'text' and 'text' in item:
                                        formatted_content.append({'text': item['text']})
                                    elif 'text' in item and 'type' not in item:
                                        formatted_content.append({'text': item['text']})
                                    elif isinstance(item.get('text'), str):
                                        formatted_content.append({'text': item['text']})
                                elif isinstance(item, str):
                                    formatted_content.append({'text': item})
                            if not formatted_content:
                                formatted_content = [{'text': str(content)}]
                        else:
                            formatted_content = [{'text': str(content)}]

                        all_messages.append({
                            'role': current_msg['role'],
                            'content': formatted_content
                        })

            print(f"🔍 DEBUG: Total messages for agent: {len(all_messages)}")

            # 获取最后一条用户消息作为当前prompt
            user_prompt = ""
            for msg in reversed(all_messages):
                if msg.get('role') == 'user':
                    user_prompt = msg.get('content', '')
                    break

            if not user_prompt:
                user_prompt = "Hello, how can I help you?"

        except Exception as e:
            print(f"❌ Error retrieving chat history: {e}")
            # 降级处理：只使用当前传入的消息
            all_messages = []
            for msg in messages:
                if msg.get('role') and msg.get('content'):
                    # 转换为Bedrock标准格式
                    content = msg['content']
                    if isinstance(content, str):
                        formatted_content = [{'text': content}]
                    elif isinstance(content, list):
                        formatted_content = content  # 假设已经是正确格式
                    else:
                        formatted_content = [{'text': str(content)}]

                    all_messages.append({
                        'role': msg['role'],
                        'content': formatted_content
                    })

            user_prompt = ""
            for msg in reversed(messages):
                if msg.get('role') == 'user':
                    user_prompt = msg.get('content', '')
                    break

            if not user_prompt:
                user_prompt = "Hello, how can I help you?"

        # 使用上下文管理器，传递当前用户ID
        try:
            current_user_id = get_current_user_id()
        except Exception:
            current_user_id = None

        # 准备模型上下文
        model_context = {'image': image_model}
        if video_model:
            model_context['video'] = video_model

        with SessionContextManager(session_id, canvas_id, model_context, user_id=current_user_id):
            print(f"💬 Processing: {user_prompt[:50]}...")

            # 创建带有上下文信息的工具
            tools = []
            # Run child intent agent BEFORE building main tools and store result in session context
            # 只有在开启自动模型选择时才执行意图识别
            try:
                intent_set = False
                if auto_model_selection:
                    child_system_prompt = (
                        "You are an intent classifier for image/video editing and generation.\n"
                        "Output STRICT JSON only, no extra text.\n"
                        "Fields:\n"
                        "  - mode: \"single_img_edit\" | \"multiple_img_edit\" | \"text_to_image\" | \"text_to_video\" | \"image_to_video\"\n"
                        "  - generation_model: one of \"flux-kontext\", \"qwen-image-multiple\", \"flux-t2i\", \"h3-t2v\", \"h3-i2v\"\n"
                        "  - input_image_num: integer (only when mode=multiple_img_edit). Decide from the user's text if they ask for 2 or 3 images; default to 2.\n"
                        "  - reasoning: short Chinese explanation\n"
                        "Rules:\n"
                        "  - Analyze ONLY the user's current request text (no tool usage).\n"
                        "  - For VIDEO generation requests:\n"
                        "    * If user explicitly mentions using/editing/based on an existing image/photo (keywords: '图', '照片', 'image', 'photo', 'picture', 'i2v', '基于', '根据'), choose mode=\"image_to_video\" and generation_model=\"h3-i2v\"\n"
                        "    * Otherwise, for pure text-to-video requests (keywords: '生成视频', '创建视频', 'generate video', 'create video', 't2v'), choose mode=\"text_to_video\" and generation_model=\"h3-t2v\"\n"
                        "  - For IMAGE generation requests:\n"
                        "    * If user wants to merge/blend/combine multiple images (keywords: '融合', '合并', '结合', '混合', 'blend', 'merge', 'combine'), choose mode=\"multiple_img_edit\" and generation_model=\"qwen-image-multiple\"\n"
                        "    * If user wants to edit/modify a single image (keywords: '修改', '编辑', '改变', 'edit', 'modify', 'change'), choose mode=\"single_img_edit\" and generation_model=\"flux-kontext\"\n"
                        "    * Otherwise, for pure text-to-image requests, choose mode=\"text_to_image\" and generation_model=\"flux-t2i\"\n"
                        "  - If the user references three images explicitly (e.g., '第三张', '三张', 'image 3', '图3', 'three', 'third'), set input_image_num to 3. Otherwise set to 2.\n"
                        "  - Do not include any additional commentary. JSON only.\n"
                        "  - Start your response with '{' (left brace). Do NOT use code fences or backticks.\n"
                    )

                    # Tighten child model to avoid code fences; add stop sequences when using Bedrock
                    child_model = model
                    try:
                        if isinstance(model, BedrockModel):
                            region = config_service.app_config.get('bedrock', {}).get('region', 'us-west-2')
                            child_model = BedrockModel(
                                model_id=text_model.get('model'),
                                region_name=region,
                                max_tokens=text_model.get('max_tokens', 8192),
                                temperature=0,
                                stop_sequences=["```", "```json"]
                            )
                    except Exception as _e:
                        print(f"⚠️ Failed to create tightened child model: {_e}")
                        child_model = model

                    child_agent = Agent(
                        model=child_model,
                        tools=[],  # 意图分类不需要工具
                        system_prompt=child_system_prompt
                    )

                    parsed_result = None
                    buffer = ""
                    async for ev in child_agent.stream_async(user_prompt):
                        if isinstance(ev, dict) and 'event' in ev and 'contentBlockDelta' in ev['event']:
                            delta = ev['event']['contentBlockDelta']['delta']
                            if 'text' in delta:
                                buffer += delta['text']
                                candidate = _extract_first_json_object(buffer)
                                if isinstance(candidate, dict):
                                    parsed_result = candidate
                                    break
                        elif isinstance(ev, str):
                            buffer += ev
                            candidate = _extract_first_json_object(buffer)
                            if isinstance(candidate, dict):
                                parsed_result = candidate
                                break
                        # If the SDK provides a messageStop or similar, we could break there and parse once
                        # For now we incrementally try to parse as JSON as text accumulates
                        if parsed_result is not None:
                            break

                    if isinstance(parsed_result, dict):
                        set_intention_result(parsed_result)
                        mode = parsed_result.get('mode'); gm = parsed_result.get('generation_model')
                        print(f"🧭 [child] intent agent parsed → mode={mode}, generation_model={gm}")
                        intent_set = True
                    else:
                        print("⚠️ [child] intent agent did not produce parsable JSON; will fallback to keyword intention tool")

                # Fallback to local keyword tool if the child agent produced nothing usable
                if auto_model_selection and not intent_set:
                    try:
                        kw = analyze_edit_intention(prompt=user_prompt)
                        try:
                            parsed = json.loads(kw) if isinstance(kw, str) else None
                        except Exception:
                            parsed = None
                        if isinstance(parsed, dict):
                            set_intention_result(parsed)
                            mode = parsed.get('mode'); gm = parsed.get('generation_model')
                            print(f"🧭 [fallback] analyze_edit_intention → mode={mode}, generation_model={gm}")
                        else:
                            print("⚠️ analyze_edit_intention returned non-JSON; intention not stored")
                    except Exception as _ie:
                        print(f"⚠️ Failed to run intention fallback: {_ie}")

                # 如果关闭了自动模型选择，打印提示信息
                if not auto_model_selection:
                    print("🔧 自动模型选择已关闭，将使用用户界面选择的模型")
            except Exception as _child_e:
                print(f"⚠️ Child intent agent error: {_child_e}")


            # Intent classification is executed by a child agent BEFORE main agent; do not register intent tools here
            print("🧭 Intent pre-classified by child agent; generation tools only in main agent")


            # Always use contextual tools directly (remove smart ComfyUI router)
            from tools.strands_image_generators import create_generate_image_with_context
            contextual_generate_image = create_generate_image_with_context(session_id, canvas_id, image_model, current_user_id)
            tools.append(contextual_generate_image)

            # Always add video generation tool (use default if frontend didn't provide)
            from tools.strands_video_generators import create_generate_video_with_context
            _video_model = video_model if video_model else {"provider": "comfyui", "model": "h3-t2v"}
            contextual_generate_video = create_generate_video_with_context(session_id, canvas_id, _video_model, current_user_id)
            tools.append(contextual_generate_video)

            print(f"🔍 DEBUG: Using tools: {[tool.__name__ for tool in tools]}")

            # 创建带有上下文工具的agent，并设置历史消息
            agent = Agent(
                model=model,
                tools=tools,
                system_prompt=agent_system_prompt
            )

            # 设置历史消息到agent中，让模型能够访问完整的对话上下文
            if len(all_messages) > 1:  # 如果有历史消息
                # 将历史消息转换为Strands Agent期望的格式
                agent.messages = all_messages[:-1]  # 除了最后一条用户消息，其他都作为历史
                print(f"🔍 DEBUG: Set {len(agent.messages)} historical messages to agent")

                # DEBUG: historical message logs suppressed to reduce noise
                # for i, msg in enumerate(agent.messages):
                #     print(f"🔍 DEBUG: Historical message {i}: role={msg.get('role')}, content_type={type(msg.get('content'))}")
                #     content = msg.get('content', [])
                #     if isinstance(content, list) and len(content) > 0:
                #         first_block = content[0]
                #         if isinstance(first_block, dict) and 'text' in first_block:
                #             text_content = first_block['text']
                #             print(f"🔍 DEBUG: Content preview: {text_content[:100]}...")
                #         else:
                #             print(f"🔍 DEBUG: Content block: {first_block}")
                #     else:
                #         print(f"🔍 DEBUG: Content (unexpected format): {content}")

                # DEBUG: Current user prompt log suppressed

            print(f"✅ Agent created with {len(tools)} tools")

            # 使用异步流式调用替代同步调用
            print("🔍 DEBUG: Calling agent with async streaming...")

            try:
                # 使用异步流式调用
                response_parts = []
                tool_results = []  # 收集工具调用结果
                async for event in agent.stream_async(user_prompt):

                    # 处理流式事件并发送到前端
                    await handle_agent_event(event, session_id)

                    # 收集响应内容用于保存到数据库
                    if isinstance(event, dict) and 'event' in event and 'contentBlockDelta' in event['event']:
                        delta = event['event']['contentBlockDelta']['delta']
                        if 'text' in delta:
                            response_parts.append(delta['text'])

                    # 收集工具调用结果（工具已直接保存图像/视频消息，这里只收集文本用于回复消息）
                    if isinstance(event, dict) and 'toolResult' in event:
                        for text in _extract_tool_result_texts(event['toolResult']):
                            tool_results.append(text)
                            print(f"🔍 DEBUG: Collected tool result: {text[:100]}...")
                    # 兼容另一种事件形态：toolResult 位于顶层 message.content[*].toolResult
                    elif isinstance(event, dict) and isinstance(event.get('message'), dict):
                        contents = event['message'].get('content')
                        for item in (contents if isinstance(contents, list) else []):
                            if isinstance(item, dict) and 'toolResult' in item:
                                for text in _extract_tool_result_texts(item['toolResult']):
                                    tool_results.append(text)
                                    print(f"🔍 DEBUG: Collected tool result (message envelope): {text[:100]}...")


                # 保存完整的文本消息到数据库（包括工具结果）
                all_content = response_parts + tool_results
                response_text = ''.join(all_content)
                if response_text.strip():  # 只保存非空消息
                    text_message = {
                        'role': 'assistant',
                        'content': response_text
                    }
                    db_service.create_message(session_id, 'assistant', json.dumps(text_message))
                    print(f"🔍 DEBUG: Saved message with {len(response_parts)} text parts and {len(tool_results)} tool results")

            except Exception as e:
                print(f"❌ Agent error: {e}")
                await send_user_websocket_message(session_id, {
                    'type': 'error',
                    'error': str(e)
                })

        # 'done' 事件由 chat_service 在任务结束时统一发送

    except Exception as e:
        print('Error in strands_agent', e)
        traceback.print_exc()
        await send_user_websocket_message(session_id, {
            'type': 'error',
            'error': str(e)
        })


async def handle_agent_event(event, session_id):
    """处理 Agent 事件"""
    if not isinstance(event, dict):
        return



    # 只处理重要的事件，减少噪音
    # 有些 SDK 版本会把当前工具调用信息放在顶层（不在 inner_event 里）
    if isinstance(event.get('current_tool_use'), dict):
        cur = event['current_tool_use']
        tool_use_id = cur.get('toolUseId', '')
        tool_name = cur.get('name', '')
        if tool_use_id:
            # 记录映射和当前会话的工具ID，便于后续 argument/stop 日志对齐
            _tool_call_names[tool_use_id] = tool_name or _tool_call_names.get(tool_use_id, '')
            prev = _current_tool_use_by_session.get(session_id)
            if prev != tool_use_id:
                _current_tool_use_by_session[session_id] = tool_use_id
                # 去重后打印“开始”日志（若之前未由 contentBlockStart 触发）
                event_key = f"tool_call_{session_id}_{tool_use_id}"
                if event_key not in _sent_events:
                    _sent_events.add(event_key)
                    print(f"🔧 Tool call started: {tool_name} (ID: {tool_use_id}) [from current_tool_use]")
                    await send_user_websocket_message(session_id, {
                        'type': 'tool_call',
                        'id': tool_use_id,
                        'name': tool_name,
                        'arguments': ''
                    })

    if 'event' in event:
        inner_event = event['event']

        # 处理工具调用开始
        if 'contentBlockStart' in inner_event:
            start = inner_event['contentBlockStart']['start']
            if 'toolUse' in start:
                tool_use = start['toolUse']
                tool_call_id = tool_use.get('toolUseId', '')

                # 检查是否已经发送过这个tool_call事件
                event_key = f"tool_call_{session_id}_{tool_call_id}"
                if event_key in _sent_events:
                    print(f"🔄 Skipping duplicate tool_call event: {tool_call_id}")
                    return

                # 记录 toolUseId 到工具名的映射，用于后续结果日志
                tool_name = tool_use.get('name', '')
                _tool_call_names[tool_call_id] = tool_name

                _sent_events.add(event_key)
                print(f"🔧 Tool call started: {tool_name} (ID: {tool_call_id})")
                await send_user_websocket_message(session_id, {
                    'type': 'tool_call',
                    'id': tool_call_id,
                    'name': tool_name,
                    'arguments': ''
                })

        # 某些实现会在这里给出 messageStop: tool_use，表示模型已发出工具调用并暂停等待
        elif 'messageStop' in inner_event:
            stop = inner_event['messageStop'] or {}
            reason = stop.get('stopReason') or stop.get('reason')
            if reason == 'tool_use':
                tool_use_id = _current_tool_use_by_session.get(session_id, '')
                tool_name = _tool_call_names.get(tool_use_id, '')
                print(f"🔧 Message stopped for tool_use → pending execution. Current tool: {tool_name} (ID: {tool_use_id})")


        # 处理文本和工具参数增量
        elif 'contentBlockDelta' in inner_event:
            delta = inner_event['contentBlockDelta']['delta']
            if 'text' in delta:
                await send_user_websocket_message(session_id, {
                    'type': 'delta',
                    'text': delta['text']
                })
            elif 'toolUse' in delta:
                await send_user_websocket_message(session_id, {
                    'type': 'tool_call_arguments',
                    'id': _current_tool_use_by_session.get(session_id, ''),
                    'text': delta['toolUse'].get('input', '')
                })

        # 处理工具调用完成
        elif 'contentBlockStop' in inner_event:
            stop_info = inner_event['contentBlockStop']
            if 'toolUse' in stop_info:
                tool_use = stop_info.get('toolUse', {})
                tool_use_id = tool_use.get('toolUseId', '')
                tool_name = _tool_call_names.get(tool_use_id, tool_use.get('name', ''))
                print(f"🔧 Tool call completed: {tool_use_id} ({tool_name})")

    # 处理工具调用结果（顶层 toolResult 或 message.content[*].toolResult 两种事件形态之一）
    if 'toolResult' in event:
        await _forward_tool_result(event['toolResult'], session_id)
    elif isinstance(event.get('message'), dict):
        contents = event['message'].get('content')
        for item in (contents if isinstance(contents, list) else []):
            if isinstance(item, dict) and 'toolResult' in item:
                await _forward_tool_result(item['toolResult'], session_id, source='message envelope')


async def _forward_tool_result(tool_result, session_id: str, source: str = ''):
    """将工具结果文本作为 delta 转发到前端"""
    if not isinstance(tool_result, dict):
        return
    tool_use_id = tool_result.get('toolUseId', 'unknown')
    tool_name = _tool_call_names.get(tool_use_id, '')
    suffix = f" [{source}]" if source else ''
    print(f"🔧 Tool result received: {tool_use_id} ({tool_name}){suffix}")

    for text in _extract_tool_result_texts(tool_result):
        print(f"🔍 DEBUG: Tool ({tool_name}) result: {text[:200]}...")
        await send_user_websocket_message(session_id, {
            'type': 'delta',
            'text': text
        })
