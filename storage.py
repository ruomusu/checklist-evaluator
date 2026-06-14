"""
DynamoDB 存储模块
- 统一数据源：每次评估生成唯一时间戳 Sort Key
- 高光状态通过 UpdateItem 原地翻转，不删除不重建
- 用户认证（复用同一表，USER#info 作为 Sort Key）
"""

import time
import bcrypt
from datetime import datetime, timezone, timedelta
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key

from config import Config
from logger import log

_BJT = timezone(timedelta(hours=8))
TABLE_NAME = "jiaxuaya-checklist"

# 用户信息 Sort Key 前缀
USER_SK = "USER#info"


def _get_table():
    """获取 DynamoDB Table 资源"""
    dynamodb = boto3.resource("dynamodb", region_name=Config.AWS_REGION)
    return dynamodb.Table(TABLE_NAME)


# ========================
# 用户认证相关
# ========================

def register_user(username: str, password: str) -> dict:
    """
    注册新用户

    Args:
        username: 用户名
        password: 明文密码

    Returns:
        dict: 用户信息

    Raises:
        ValueError: 用户已存在
    """
    table = _get_table()

    # 检查用户是否已存在
    existing = table.get_item(Key={
        "trainee_name": username,
        "service_timestamp": USER_SK,
    })
    if existing.get("Item"):
        raise ValueError("用户名已存在")

    # 加密密码
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    now = datetime.now(_BJT).strftime("%Y-%m-%d %H:%M:%S")

    item = {
        "trainee_name": username,
        "service_timestamp": USER_SK,
        "password_hash": password_hash,
        "role": "user",
        "created_at": now,
    }

    table.put_item(Item=item)
    log(f"用户注册 | username={username}", stage="AUTH")

    # 返回时移除敏感信息
    item.pop("password_hash", None)
    return item


def verify_user(username: str, password: str) -> bool:
    """
    验证用户密码

    Args:
        username: 用户名
        password: 明文密码

    Returns:
        bool: 密码是否正确
    """
    table = _get_table()

    resp = table.get_item(Key={
        "trainee_name": username,
        "service_timestamp": USER_SK,
    })
    item = resp.get("Item")
    if not item:
        return False

    password_hash = item.get("password_hash", "")
    return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))


def get_user(username: str) -> Optional[dict]:
    """
    获取用户信息

    Args:
        username: 用户名

    Returns:
        dict: 用户信息，不存在返回 None
    """
    table = _get_table()

    resp = table.get_item(Key={
        "trainee_name": username,
        "service_timestamp": USER_SK,
    })
    item = resp.get("Item")
    if not item:
        return None

    # 移除敏感信息
    item.pop("password_hash", None)
    return item


def get_all_users() -> list[dict]:
    """
    获取所有用户列表

    Returns:
        list[dict]: 用户列表
    """
    table = _get_table()

    # 使用 GSI 或 Scan 查询所有 USER#info 记录
    # 这里用 Scan（生产环境建议用 GSI）
    response = table.scan(
        FilterExpression="begins_with(service_timestamp, :sk)",
        ExpressionAttributeValues={":sk": "USER#"},
    )

    users = []
    for item in response.get("Items", []):
        user = {
            "trainee_name": item.get("trainee_name"),
            "role": item.get("role"),
            "created_at": item.get("created_at"),
        }
        users.append(user)

    # 继续查询更多（如果数据量大的话）
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression="begins_with(service_timestamp, :sk)",
            ExpressionAttributeValues={":sk": "USER#"},
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        for item in response.get("Items", []):
            user = {
                "trainee_name": item.get("trainee_name"),
                "role": item.get("role"),
                "created_at": item.get("created_at"),
            }
            users.append(user)

    return users


def get_all_history() -> list[dict]:
    """
    获取所有用户的所有历史记录（仅管理员可用）

    Returns:
        list[dict]: 所有历史记录
    """
    table = _get_table()

    # Scan 查询所有非用户信息的记录
    response = table.scan(
        FilterExpression="NOT begins_with(service_timestamp, :sk)",
        ExpressionAttributeValues={":sk": "USER#"},
    )

    items = response.get("Items", [])

    # 继续查询更多
    while "LastEvaluatedKey" in response:
        response = table.scan(
            FilterExpression="NOT begins_with(service_timestamp, :sk)",
            ExpressionAttributeValues={":sk": "USER#"},
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))

    # 按用户和时间倒序排列
    items.sort(key=lambda x: (x.get("trainee_name", ""), x.get("created_at", "")), reverse=True)

    return items


# ========================
# 评估报告相关
# ========================

def save_report(
    trainee_name: str,
    service_type: str,
    report_data: str,
    is_highlighted: bool = False,
) -> dict:
    """
    保存评估报告

    Sort Key 规则：{SERVICE_TYPE}#{timestamp}
    每次评估都是唯一记录，不覆盖。
    """
    table = _get_table()
    now = datetime.now(_BJT)
    created_at = now.strftime("%Y-%m-%d %H:%M:%S")
    ts = int(time.time())
    sort_key = f"{service_type.upper()}#{ts}"

    item = {
        "trainee_name": trainee_name,
        "service_timestamp": sort_key,
        "service_type": service_type.upper(),
        "report_data": report_data,
        "created_at": created_at,
        "is_highlighted": is_highlighted,
    }

    table.put_item(Item=item)
    log(f"DynamoDB 写入 | PK={trainee_name} | SK={sort_key}", stage="REPORT")
    return item


def get_history(trainee_name: str) -> list[dict]:
    """查询某新人的所有历史记录，按时间倒序"""
    table = _get_table()
    response = table.query(
        KeyConditionExpression=Key("trainee_name").eq(trainee_name),
        ScanIndexForward=False,
    )
    items = response.get("Items", [])
    log(f"DynamoDB 查询 | PK={trainee_name} | {len(items)} 条", stage="KB")
    return items


def toggle_highlight(trainee_name: str, service_timestamp: str) -> bool:
    """
    原地翻转 is_highlighted 状态

    Returns:
        bool: 翻转后的新状态
    """
    table = _get_table()

    # 先读当前状态
    resp = table.get_item(Key={
        "trainee_name": trainee_name,
        "service_timestamp": service_timestamp,
    })
    item = resp.get("Item")
    if not item:
        raise ValueError("记录不存在")

    new_state = not item.get("is_highlighted", False)

    # 原地更新
    table.update_item(
        Key={
            "trainee_name": trainee_name,
            "service_timestamp": service_timestamp,
        },
        UpdateExpression="SET is_highlighted = :val",
        ExpressionAttributeValues={":val": new_state},
    )

    log(f"DynamoDB toggle | PK={trainee_name} | SK={service_timestamp} | → {new_state}", stage="REPORT")
    return new_state