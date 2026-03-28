"""
数据库基础模型
定义所有模型共享的基类和工具函数
"""

from datetime import datetime
from typing import Any, Dict, Optional
from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.ext.asyncio import AsyncAttrs


class Base(AsyncAttrs, DeclarativeBase):
    """所有模型的基类"""

    def to_dict(self, exclude: Optional[list] = None) -> Dict[str, Any]:
        """将模型实例转换为字典

        Args:
            exclude: 要排除的字段列表

        Returns:
            包含模型数据的字典
        """
        result = {}
        exclude_set = set(exclude or [])

        for column in self.__table__.columns:
            if column.name not in exclude_set:
                value = getattr(self, column.name)
                # 处理特殊类型
                if isinstance(value, datetime):
                    value = value.isoformat()
                result[column.name] = value

        return result

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """从字典更新模型属性

        Args:
            data: 包含更新数据的字典
        """
        for key, value in data.items():
            if hasattr(self, key):
                setattr(self, key, value)


class TimestampMixin:
    """时间戳混入类，提供 created_at 和 updated_at 字段"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        comment="创建时间",
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
        comment="更新时间",
    )
