from fastapi import Depends, WebSocket, WebSocketDisconnect
from loguru import logger
from pydantic import BaseModel
import traceback
import json

from labelu.internal.clients.ws import sampleConnectionManager
from labelu.internal.common.websocket import ConnectionData, Message, MessageType
from labelu.internal.dependencies.user import verify_ws_token
    
class TaskSampleWsPayload(BaseModel):
    task_id: int
    user_id: int
    username: str
    sample_id: int
    
def get_task_sample_connection_payloads(conns: ConnectionData):
    if not conns:
        return Message(
            type=MessageType.PEERS,
            data=[]
        )
        
    return Message(
        type=MessageType.PEERS,
        data=[
            TaskSampleWsPayload(
                task_id=conn.data.task_id,
                user_id=conn.data.user_id,
                username=conn.data.username,
                sample_id=conn.data.sample_id
            ) for conn in conns
        ]
    )

    
async def task_ws_endpoint(websocket: WebSocket, task_id: int, sample_id: int, user=Depends(verify_ws_token)):
    # 记录WebSocket连接请求详情
    logger.info(f"WebSocket连接请求: URL=/ws/task/{task_id}/{sample_id}, 客户端IP={websocket.client.host}")
    logger.debug(f"WebSocket请求头: {dict(websocket.headers)}")
    logger.debug(f"WebSocket查询参数: {dict(websocket.query_params)}")
    
    if not user:
        logger.warning(f"WebSocket认证失败: task_id={task_id}, sample_id={sample_id}, IP={websocket.client.host}")
        await websocket.close(code=1008, reason="Unauthorized")
        return
    
    logger.info(f"WebSocket用户认证成功: user_id={user.id}, username={user.username}")
    client_id = f"task_{task_id}"
    
    async def sync_peers():
        connections = sampleConnectionManager.active_connections
        current_connections = connections.get(client_id, {})
        sample_payload = get_task_sample_connection_payloads(current_connections.values())
        
        await sampleConnectionManager.send_message(client_id=client_id, message=sample_payload)
        logger.debug(f"同步peers完成: task_id={task_id}, 连接数={len(current_connections)}")
        
    
    connection = None
    
    async def cleanup():
        logger.info(f"清理WebSocket连接: client_id={client_id}, user_id={user.id if user else 'unknown'}")
        await sampleConnectionManager.disconnect(client_id, websocket)
        await sync_peers()
    
    try:
        # 记录尝试建立WebSocket连接
        logger.info(f"尝试接受WebSocket连接: task_id={task_id}, sample_id={sample_id}, user_id={user.id}")
        
        connection = await sampleConnectionManager.connect(
            client_id,
            websocket,
            data=TaskSampleWsPayload(
                task_id=task_id,
                user_id=user.id,
                username=user.username,
                sample_id=sample_id,
            )
        )
        
        # 记录WebSocket连接成功
        logger.info(f"WebSocket连接成功: client_id={client_id}, user_id={user.id}, connection_id={connection.id}")
        
        await sync_peers()
        
        while True:
            try:
                data = await websocket.receive_text()
                message = Message.parse_raw(data)
                
                if message.type == MessageType.PONG:
                    connection.update_heartbeat()
                    logger.debug(f"收到PONG消息: client_id={client_id}, connection_id={connection.id}")
                
            except WebSocketDisconnect as e:
                logger.info(f"WebSocket断开连接: client_id={client_id}, 状态码={e.code}")
                break
            
    except WebSocketDisconnect as e:
        logger.info(f"WebSocket在连接建立过程中断开: client_id={client_id}, 状态码={e.code}")
    except Exception as e:
        error_details = traceback.format_exc()
        logger.error(f"WebSocket错误: client_id={client_id}, 错误类型={type(e).__name__}, 错误信息={str(e)}")
        logger.debug(f"WebSocket错误详情:\n{error_details}")
    finally:
        await cleanup()