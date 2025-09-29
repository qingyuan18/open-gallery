#!/usr/bin/env python3
"""
测试重复文本修复的脚本
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

# 模拟事件数据
mock_events = [
    {
        'event': {
            'contentBlockDelta': {
                'delta': {
                    'text': '安'
                }
            }
        }
    },
    {
        'event': {
            'contentBlockDelta': {
                'delta': {
                    'text': '哥'
                }
            }
        }
    },
    {
        'event': {
            'contentBlockDelta': {
                'delta': {
                    'text': '拉'
                }
            }
        }
    },
    {
        'event': {
            'contentBlockDelta': {
                'delta': {
                    'text': '兔'
                }
            }
        }
    },
    {
        'event': {
            'contentBlockDelta': {
                'delta': {
                    'text': '子'
                }
            }
        }
    }
]

async def test_handle_agent_event():
    """测试事件处理函数是否正确处理delta事件"""
    
    # 模拟WebSocket发送函数
    sent_messages = []
    
    async def mock_send_websocket(session_id, event):
        sent_messages.append(event)
        print(f"📤 Sent: {event}")
    
    # 导入并测试handle_agent_event函数
    import sys
    import os
    sys.path.append(os.path.join(os.path.dirname(__file__), 'server'))
    
    # 模拟send_user_websocket_message函数
    import services.strands_service as strands_service
    strands_service.send_user_websocket_message = mock_send_websocket
    
    # 测试每个事件
    session_id = "test_session"
    for event in mock_events:
        await strands_service.handle_agent_event(event, session_id)
    
    # 验证结果
    print(f"\n📊 总共发送了 {len(sent_messages)} 条消息")
    
    # 检查是否有重复的delta事件
    delta_messages = [msg for msg in sent_messages if msg.get('type') == 'delta']
    print(f"📝 Delta消息数量: {len(delta_messages)}")
    
    # 重建完整文本
    full_text = ''.join([msg['text'] for msg in delta_messages])
    print(f"🔤 重建的完整文本: '{full_text}'")
    
    # 验证文本是否正确
    expected_text = "安哥拉兔子"
    if full_text == expected_text:
        print("✅ 文本重建正确，没有重复")
        return True
    else:
        print(f"❌ 文本重建错误，期望: '{expected_text}', 实际: '{full_text}'")
        return False

async def test_response_collection():
    """测试响应收集逻辑是否正确"""
    
    response_parts = []
    
    # 模拟主循环中的响应收集逻辑
    for event in mock_events:
        # 只收集响应内容用于保存到数据库，不重复处理delta
        if isinstance(event, dict) and 'event' in event and 'contentBlockDelta' in event['event']:
            delta = event['event']['contentBlockDelta']['delta']
            if 'text' in delta:
                response_parts.append(delta['text'])
    
    full_response = ''.join(response_parts)
    expected_response = "安哥拉兔子"
    
    print(f"\n📝 收集的响应部分: {response_parts}")
    print(f"🔤 完整响应: '{full_response}'")
    
    if full_response == expected_response:
        print("✅ 响应收集正确")
        return True
    else:
        print(f"❌ 响应收集错误，期望: '{expected_response}', 实际: '{full_response}'")
        return False

async def main():
    """主测试函数"""
    print("🧪 开始测试重复文本修复...")
    
    # 测试事件处理
    print("\n1️⃣ 测试事件处理函数...")
    event_test_passed = await test_handle_agent_event()
    
    # 测试响应收集
    print("\n2️⃣ 测试响应收集逻辑...")
    collection_test_passed = await test_response_collection()
    
    # 总结
    print("\n📋 测试结果总结:")
    print(f"   事件处理: {'✅ 通过' if event_test_passed else '❌ 失败'}")
    print(f"   响应收集: {'✅ 通过' if collection_test_passed else '❌ 失败'}")
    
    if event_test_passed and collection_test_passed:
        print("\n🎉 所有测试通过！重复文本问题已修复。")
    else:
        print("\n⚠️ 部分测试失败，需要进一步检查。")

if __name__ == "__main__":
    asyncio.run(main())
