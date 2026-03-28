"""
数据库基础模型
定义所有模型共享的基类和工具函数
"""

from datetime import datetime
from typing import Any, Dict, Optional


class BaseModel:
    """基础模型类，提供通用方法"""

    def to_dict(self, exclude: Optional[list] = None) -> Dict[str, Any]:
        """将模型实例转换为字典

        Args:
            exclude: 要排除的字段列表

        Returns:
            包含模型数据的字典
        """
        result = {}
        exclude_set = set(exclude or [])

        # 获取实例的所有属性，排除私有属性和方法
        for key, value in vars(self).items():
            if key.startswith("_"):
                continue
            if key in exclude_set:
                continue
            # 处理特殊类型
            if isinstance(value, datetime):
                value = value.isoformat()
            result[key] = value

        return result

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典更新模型属性

        Args:
            data: 包含更新数据的字典
        """
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)
