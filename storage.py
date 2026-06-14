"""
DynamoDB 存储模块
- 统一数据源：每次评估生成唯一时间戳 Sort Key
- 高光状态通过 UpdateItem 原地翻转，不删除不重建
"""

import time
from datetime import datetime, timezone, timedelta

import boto3
from boto3.dynamodb.conditions import Key

from config import Config
from logger import log

_BJT = timezone(timedelta(hours=8))
TABLE_NAME = "jiaxuaya-checklist"


def _get_table():
    """获取 DynamoDB Table 资源"""
    dynamodb = boto3.resource("dynamodb", region_name=Config.AWS_REGION)
    return dynamodb.Table(TABLE_NAME)


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
