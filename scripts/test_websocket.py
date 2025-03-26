#!/usr/bin/env python3
"""
WebSocket连接测试工具

用于测试LabelU应用的WebSocket连接并诊断问题
"""

import argparse
import asyncio
import json
import ssl
import sys
import traceback
import urllib.parse
from websockets.client import connect, WebSocketClientProtocol
from websockets.exceptions import InvalidStatusCode, WebSocketException

async def test_websocket(url, headers=None, timeout=5):
    """测试WebSocket连接并输出详细信息"""
    print(f"尝试连接WebSocket: {url}")
    print(f"自定义头信息: {headers or {}}")
    
    try:
        # 连接前输出debug信息
        url_parts = urllib.parse.urlparse(url)
        print(f"协议: {url_parts.scheme}")
        print(f"主机: {url_parts.netloc}")
        print(f"路径: {url_parts.path}")
        print(f"查询参数: {url_parts.query}")
        
        # 设置连接选项
        kwargs = {
            "extra_headers": headers,
            "open_timeout": timeout
        }
        
        # 处理SSL
        if url.startswith("wss://"):
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE if args.insecure else ssl.CERT_REQUIRED
            kwargs["ssl"] = ctx
            
        # 异步连接WebSocket
        start_time = asyncio.get_event_loop().time()
        async with connect(url, **kwargs) as websocket:
            elapsed = asyncio.get_event_loop().time() - start_time
            print(f"✅ 连接成功! (耗时 {elapsed:.2f}秒)")
            print(f"WebSocket握手状态码: 101 Switching Protocols (如预期)")
            
            # 发送PING消息
            ping_msg = json.dumps({"type": "ping", "data": None})
            print(f"发送消息: {ping_msg}")
            await websocket.send(ping_msg)
            
            # 等待响应
            print("等待服务器响应...")
            response = await asyncio.wait_for(websocket.recv(), timeout=timeout)
            print(f"收到响应: {response}")
            
            # 尝试解析peers信息
            try:
                data = json.loads(response)
                if data.get("type") == "peers":
                    peers = data.get("data", [])
                    print(f"当前连接的用户数: {len(peers)}")
                    if peers:
                        for i, peer in enumerate(peers):
                            print(f"  用户 {i+1}: {peer.get('username')} (ID: {peer.get('user_id')})")
            except json.JSONDecodeError:
                print("无法解析服务器响应为JSON")
                
            print("\n诊断结果: WebSocket连接正常工作")
            return True
            
    except InvalidStatusCode as e:
        elapsed = asyncio.get_event_loop().time() - start_time
        print(f"❌ 连接失败! HTTP状态码: {e.status_code} (耗时 {elapsed:.2f}秒)")
        print(f"响应头: {e.headers}")
        
        if e.status_code == 404:
            print("\n诊断结果: WebSocket路由不存在")
            print("可能原因:")
            print("1. URL路径不正确，可能缺少API前缀")
            print("2. 后端未注册WebSocket路由")
            print("3. Nginx配置未正确代理WebSocket请求到后端")
        elif e.status_code == 401 or e.status_code == 403:
            print("\n诊断结果: 认证失败")
            print("可能原因:")
            print("1. Token无效或已过期")
            print("2. 权限不足")
            print("3. Token格式不正确")
        else:
            print(f"\n诊断结果: 服务器返回非预期的HTTP状态码 {e.status_code}")
            
    except ssl.SSLError as e:
        print(f"❌ SSL/TLS错误: {str(e)}")
        print("\n诊断结果: SSL/TLS连接问题")
        print("可能原因:")
        print("1. 自签名证书，尝试使用 --insecure 选项")
        print("2. 证书已过期或不匹配域名")
        print("3. 证书链不完整")
        
    except asyncio.TimeoutError:
        print(f"❌ 连接超时 (超过 {timeout} 秒)")
        print("\n诊断结果: 服务器未响应")
        print("可能原因:")
        print("1. 服务器未运行或不可达")
        print("2. 防火墙阻止了连接")
        print("3. 网络问题")
        
    except WebSocketException as e:
        print(f"❌ WebSocket异常: {str(e)}")
        print("\n诊断结果: WebSocket协议错误")
        print("可能原因:")
        print("1. 服务器不支持WebSocket或配置错误")
        print("2. Nginx配置缺少WebSocket支持")
        print("3. 中间件或防火墙干扰WebSocket连接")
        
    except ConnectionRefusedError:
        print("❌ 连接被拒绝")
        print("\n诊断结果: 服务器拒绝连接")
        print("可能原因:")
        print("1. 服务器未运行")
        print("2. 端口不正确")
        print("3. 防火墙阻止了连接")
        
    except Exception as e:
        print(f"❌ 未知错误: {str(e)}")
        traceback.print_exc()
        
    return False

def parse_url(url):
    """解析URL并处理相对路径"""
    if not url.startswith(('ws://', 'wss://')):
        # 假设是相对路径，转换为绝对URL
        return f"ws://localhost:8000{url if url.startswith('/') else '/' + url}"
    return url

def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description="WebSocket连接测试工具")
    parser.add_argument("--url", required=True, help="WebSocket服务器URL")
    parser.add_argument("--token", help="认证Token")
    parser.add_argument("--header", action="append", help="自定义HTTP头 (格式: Key:Value)")
    parser.add_argument("--timeout", type=int, default=5, help="连接超时时间(秒)")
    parser.add_argument("--insecure", action="store_true", help="忽略SSL证书验证")
    return parser.parse_args()

async def main():
    """主函数"""
    # 解析命令行参数
    global args
    args = parse_args()
    url = parse_url(args.url)
    
    # 处理token
    if args.token and "?" not in url:
        url = f"{url}?token={args.token}"
    elif args.token:
        url = f"{url}&token={args.token}"
        
    # 处理headers
    headers = {}
    if args.header:
        for header in args.header:
            if ":" in header:
                key, value = header.split(":", 1)
                headers[key.strip()] = value.strip()
                
    # 测试连接
    success = await test_websocket(url, headers, args.timeout)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    asyncio.run(main()) 