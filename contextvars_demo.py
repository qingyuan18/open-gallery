#!/usr/bin/env python3
"""
Python contextvars 使用示例
演示如何在异步和同步环境中使用上下文变量
"""

import contextvars
import asyncio
import threading
import time
from typing import Dict, Any

# 1. 创建上下文变量
user_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    'user_id',  # 变量名
    default='anonymous'  # 默认值
)

session_data_var: contextvars.ContextVar[Dict[str, Any]] = contextvars.ContextVar(
    'session_data',
    default={}
)

print("=== 1. 基本使用 ===")

# 设置值
user_id_var.set('user_123')
session_data_var.set({'session_id': 'sess_456', 'canvas_id': 'canvas_789'})

# 获取值
print(f"User ID: {user_id_var.get()}")
print(f"Session Data: {session_data_var.get()}")

print("\n=== 2. 默认值演示 ===")

# 创建新的上下文变量，没有设置值
new_var: contextvars.ContextVar[str] = contextvars.ContextVar('new_var', default='default_value')
print(f"New var (未设置): {new_var.get()}")

print("\n=== 3. 函数调用中的上下文传播 ===")

def inner_function():
    """内部函数可以访问外部设置的上下文变量"""
    print(f"  Inner function - User ID: {user_id_var.get()}")
    print(f"  Inner function - Session: {session_data_var.get()}")

def outer_function():
    """外部函数设置上下文变量"""
    user_id_var.set('user_outer')
    session_data_var.set({'level': 'outer'})
    print(f"Outer function - User ID: {user_id_var.get()}")
    inner_function()

outer_function()

print("\n=== 4. 异步函数中的上下文传播 ===")

async def async_task(task_name: str):
    """异步任务中的上下文变量"""
    print(f"Task {task_name} - User ID: {user_id_var.get()}")
    print(f"Task {task_name} - Session: {session_data_var.get()}")
    
    # 在异步任务中修改上下文变量
    user_id_var.set(f'user_{task_name}')
    print(f"Task {task_name} - Modified User ID: {user_id_var.get()}")
    
    await asyncio.sleep(0.1)
    print(f"Task {task_name} - After sleep User ID: {user_id_var.get()}")

async def main_async():
    """主异步函数"""
    user_id_var.set('main_user')
    session_data_var.set({'main': True})
    
    # 创建多个异步任务
    tasks = [
        async_task('A'),
        async_task('B'),
        async_task('C')
    ]
    
    await asyncio.gather(*tasks)
    
    print(f"Main async - Final User ID: {user_id_var.get()}")

# 运行异步示例
asyncio.run(main_async())

print("\n=== 5. 线程隔离演示 ===")

def thread_function(thread_name: str):
    """线程函数 - 每个线程有独立的上下文"""
    print(f"Thread {thread_name} - Initial User ID: {user_id_var.get()}")
    
    # 在线程中设置上下文变量
    user_id_var.set(f'thread_{thread_name}_user')
    print(f"Thread {thread_name} - Set User ID: {user_id_var.get()}")
    
    time.sleep(0.1)
    print(f"Thread {thread_name} - Final User ID: {user_id_var.get()}")

# 设置主线程的上下文
user_id_var.set('main_thread_user')
print(f"Main thread - User ID: {user_id_var.get()}")

# 创建多个线程
threads = []
for i in range(3):
    thread = threading.Thread(target=thread_function, args=(f'T{i}',))
    threads.append(thread)
    thread.start()

# 等待所有线程完成
for thread in threads:
    thread.join()

print(f"Main thread - Final User ID: {user_id_var.get()}")

print("\n=== 6. Context Copy 和 Run ===")

# 复制当前上下文
current_context = contextvars.copy_context()
print(f"Current context user_id: {current_context[user_id_var]}")

# 在新上下文中运行函数
def context_function():
    print(f"Context function - User ID: {user_id_var.get()}")
    user_id_var.set('context_modified')
    print(f"Context function - Modified User ID: {user_id_var.get()}")

print("Before context.run:")
print(f"Main - User ID: {user_id_var.get()}")

# 在复制的上下文中运行函数
current_context.run(context_function)

print("After context.run:")
print(f"Main - User ID: {user_id_var.get()}")  # 原上下文不受影响
