from enum import Enum
import time
from typing import Any, Dict, List
import uuid
from fastapi import WebSocket
from loguru import logger
import asyncio
from dataclasses import dataclass
import traceback

from pydantic import BaseModel

HEARTBEAT_INTERVAL = 30
HEARTBEAT_TIMEOUT = 60

class MessageType(str, Enum):
    PEERS = "peers"
    PING = "ping"
    PONG = "pong"
    UPDATE = "update"

class Message(BaseModel):
    type: MessageType
    data: Any = None

class Connection:
    id: str
    client_id: str
    ws: WebSocket = None
    data: Any = None
    last_heartbeat: float = 0
    
    def __init__(self, id: str, client_id: str, ws: WebSocket, data: Any = None):
        self.id = id
        self.client_id = client_id
        self.ws = ws
        self.data = data
        self.last_heartbeat = time.time()
        
    def update_heartbeat(self):
        self.last_heartbeat = time.time()

class ConnectionData(Dict[str, Connection]):
    pass

class ConnectionManager:
    """WebSocket连接管理器"""
    def __init__(self):
        # client_id -> connection_id -> connection
        self.active_connections: Dict[str, ConnectionData] = {}
        self.lock = asyncio.Lock()
        
    async def connect(self, client_id: str, websocket: WebSocket, data: Any = None) -> Connection:
        """建立新的WebSocket连接"""
        try:
            logger.info(f"WebSocket连接管理器: 正在接受连接 client_id={client_id}")
            logger.debug(f"WebSocket headers: {dict(websocket.headers)}")
            await websocket.accept()
            logger.info(f"WebSocket连接管理器: 握手成功, 客户端IP={websocket.client.host}")
            
            async with self.lock:
                connection_id = f"{client_id}_{time.time()}"
                connection = Connection(id=connection_id, client_id=client_id, ws=websocket, data=data)
                
                if client_id not in self.active_connections:
                    self.active_connections[client_id] = {}
                    
                self.active_connections[client_id][connection_id] = connection
                connections_count = len(self.active_connections[client_id])
                logger.info(f"WebSocket连接管理器: 连接已添加 client_id={client_id}, connection_id={connection_id}, 当前连接数={connections_count}")
                return connection
        except Exception as e:
            error_details = traceback.format_exc()
            logger.error(f"WebSocket连接管理器: 连接失败 client_id={client_id}, 错误={str(e)}")
            logger.debug(f"WebSocket连接错误详情:\n{error_details}")
            raise
        
    async def disconnect(self, client_id: str, websocket: WebSocket):
        """断开WebSocket连接"""
        try:
            async with self.lock:
                if client_id not in self.active_connections:
                    logger.warning(f"WebSocket连接管理器: 无法断开连接, client_id={client_id} 不存在")
                    return
                    
                for connection_id, connection in list(self.active_connections[client_id].items()):
                    if connection.ws == websocket:
                        self.active_connections[client_id].pop(connection_id)
                        logger.info(f"WebSocket连接管理器: 连接已断开 client_id={client_id}, connection_id={connection_id}")
                        
                        if len(self.active_connections[client_id]) == 0:
                            self.active_connections.pop(client_id)
                            logger.info(f"WebSocket连接管理器: 移除客户端 client_id={client_id} (无活动连接)")
                        return
        except Exception as e:
            logger.error(f"WebSocket连接管理器: 断开连接时出错 client_id={client_id}, 错误={str(e)}")
        
    async def send_message(self, client_id: str, message: Message):
        """向指定客户端的所有连接发送消息"""
        if client_id not in self.active_connections:
            logger.warning(f"WebSocket连接管理器: 发送消息失败, client_id={client_id} 不存在")
            return
            
        connections = self.active_connections[client_id]
        disconnect_connections = []
        
        for connection_id, connection in connections.items():
            try:
                await connection.ws.send_json(message.dict())
                logger.debug(f"WebSocket连接管理器: 消息已发送 client_id={client_id}, connection_id={connection_id}, 消息类型={message.type}")
            except Exception as e:
                logger.error(f"WebSocket连接管理器: 发送消息失败 client_id={client_id}, connection_id={connection_id}, 错误={str(e)}")
                disconnect_connections.append(connection)
                
        for connection in disconnect_connections:
            await self.disconnect(client_id, connection.ws)
            
    async def broadcast(self, message: Message):
        """向所有连接广播消息"""
        logger.info(f"WebSocket连接管理器: 开始广播消息 类型={message.type}, 客户端数={len(self.active_connections)}")
        for client_id in self.active_connections:
            await self.send_message(client_id, message)