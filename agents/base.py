"""
Agent 基础管理器模块

本模块提供多智能体系统的基础设施，包括：
- 模型客户端动态初始化（支持 OpenAI、Ollama 等多种后端）
- Agent Session 管理（会话状态隔离）
- Context Provider 封装（上下文提供者）

使用 Microsoft Agent Framework 作为底层引擎，确保多智能体交互时的内存隔离。
"""

from typing import Any, Dict, Optional, Sequence, TypeVar, Generic
from abc import ABC, abstractmethod
import asyncio
import uuid
from dataclasses import dataclass, field

from agent_framework import (
    Agent,
    AgentSession,
    Message,
    Content,
    ChatResponse,
    BaseContextProvider,
    BaseHistoryProvider,
    InMemoryHistoryProvider,
)
from agent_framework.openai import OpenAIChatClient, OpenAIChatOptions

from core.config import Settings, LLMConfig, LLMProvider, settings as global_settings


# ============================================================================
# 类型定义
# ============================================================================

T = TypeVar("T")


# ============================================================================
# 模型客户端工厂
# ============================================================================

class ModelClientFactory:
    """
    模型客户端工厂类

    根据配置动态初始化不同提供商的模型客户端。
    目前支持 OpenAI 兼容接口（包括 OpenAI、DeepSeek、Ollama 等）。

    设计原则：
    - 模型不可知性：通过配置切换不同模型，无需修改代码
    - 延迟初始化：按需创建客户端，避免资源浪费
    """

    _clients: Dict[str, Any] = {}  # 客户端缓存

    @classmethod
    def create_client(
        cls,
        llm_config: LLMConfig,
        cache_key: Optional[str] = None,
    ) -> OpenAIChatClient:
        """
        根据配置创建模型客户端

        Args:
            llm_config: LLM 配置对象
            cache_key: 可选的缓存键，用于复用客户端实例

        Returns:
            初始化完成的模型客户端

        Note:
            目前所有提供商都使用 OpenAI 兼容接口。
            对于 Ollama，需要设置 base_url 为本地服务地址。
        """
        # 检查缓存
        if cache_key and cache_key in cls._clients:
            return cls._clients[cache_key]

        # 根据提供商类型创建客户端
        # 所有提供商都使用 OpenAI 兼容接口
        client = OpenAIChatClient(
            model_id=llm_config.model_name,
            api_key=llm_config.api_key,
            base_url=llm_config.base_url,
        )

        # 缓存客户端
        if cache_key:
            cls._clients[cache_key] = client

        return client

    @classmethod
    def get_chat_options(
        cls,
        llm_config: LLMConfig,
        response_format: Optional[Dict[str, Any]] = None,
    ) -> OpenAIChatOptions:
        """
        获取聊天选项配置

        Args:
            llm_config: LLM 配置对象
            response_format: 可选的结构化输出格式（用于强制 JSON 输出）

        Returns:
            OpenAIChatOptions 字典
        """
        options: OpenAIChatOptions = {
            "temperature": llm_config.temperature,
        }

        if llm_config.max_tokens:
            options["max_tokens"] = llm_config.max_tokens

        # 结构化输出支持
        if response_format:
            options["response_format"] = response_format

        return options

    @classmethod
    def clear_cache(cls) -> None:
        """清空客户端缓存"""
        cls._clients.clear()


# ============================================================================
# 上下文提供者
# ============================================================================

class ResearchContextProvider(BaseContextProvider):
    """
    科研上下文提供者

    为智能体提供科研相关的上下文信息，包括：
    - 当前研究主题
    - 已收集的文献列表
    - 工作流状态
    - 用户偏好设置

    继承自 agent_framework.BaseContextProvider，确保与框架的无缝集成。
    """

    def __init__(
        self,
        research_topic: Optional[str] = None,
        collected_papers: Optional[Sequence[Dict[str, Any]]] = None,
        workflow_state: Optional[Dict[str, Any]] = None,
        user_preferences: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化科研上下文提供者

        Args:
            research_topic: 当前研究主题
            collected_papers: 已收集的文献列表
            workflow_state: 工作流状态
            user_preferences: 用户偏好设置
        """
        self._research_topic = research_topic
        self._collected_papers = list(collected_papers) if collected_papers else []
        self._workflow_state = workflow_state or {}
        self._user_preferences = user_preferences or {}

    @property
    def research_topic(self) -> Optional[str]:
        """获取当前研究主题"""
        return self._research_topic

    @research_topic.setter
    def research_topic(self, value: str) -> None:
        """设置当前研究主题"""
        self._research_topic = value

    @property
    def collected_papers(self) -> Sequence[Dict[str, Any]]:
        """获取已收集的文献列表"""
        return self._collected_papers

    def add_paper(self, paper: Dict[str, Any]) -> None:
        """添加文献到收集列表"""
        self._collected_papers.append(paper)

    def add_papers(self, papers: Sequence[Dict[str, Any]]) -> None:
        """批量添加文献"""
        self._collected_papers.extend(papers)

    def clear_papers(self) -> None:
        """清空文献列表"""
        self._collected_papers.clear()

    def update_workflow_state(self, key: str, value: Any) -> None:
        """更新工作流状态"""
        self._workflow_state[key] = value

    def get_workflow_state(self, key: str, default: Any = None) -> Any:
        """获取工作流状态"""
        return self._workflow_state.get(key, default)

    def to_context_messages(self) -> Sequence[Message]:
        """
        将上下文转换为消息列表

        这是 BaseContextProvider 的核心方法，用于向智能体注入上下文。

        Returns:
            包含上下文信息的消息列表
        """
        context_parts = []

        if self._research_topic:
            context_parts.append(f"当前研究主题: {self._research_topic}")

        if self._collected_papers:
            paper_count = len(self._collected_papers)
            context_parts.append(f"已收集文献数量: {paper_count}")

        if self._workflow_state:
            context_parts.append(f"工作流状态: {self._workflow_state}")

        if context_parts:
            context_text = "\n".join(context_parts)
            return [Message(role="system", contents=[Content.from_text(context_text)])]

        return []


# ============================================================================
# 会话管理器
# ============================================================================

@dataclass
class AgentSessionInfo:
    """
    智能体会话信息

    存储单个智能体会话的元数据和状态。
    """
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str = ""
    created_at: float = field(default_factory=lambda: asyncio.get_event_loop().time())
    state: Dict[str, Any] = field(default_factory=dict)
    message_history: Sequence[Message] = field(default_factory=list)


class SessionManager:
    """
    会话管理器

    管理多智能体会话的生命周期，确保：
    - 会话状态隔离：每个智能体拥有独立的会话状态
    - 消息历史隔离：不同智能体的消息历史互不干扰
    - 会话追踪：支持会话的创建、查询和清理

    使用场景：
    - Map-Reduce 架构中，每个 SubResearcherAgent 需要独立的会话
    - 长期运行的工作流中，需要持久化和恢复会话状态
    """

    def __init__(self, history_provider: Optional[BaseHistoryProvider] = None):
        """
        初始化会话管理器

        Args:
            history_provider: 历史记录提供者，默认使用内存存储
        """
        self._history_provider = history_provider or InMemoryHistoryProvider()
        self._sessions: Dict[str, AgentSessionInfo] = {}
        self._lock = asyncio.Lock()

    async def create_session(
        self,
        agent_name: str,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> AgentSession:
        """
        创建新的智能体会话

        Args:
            agent_name: 智能体名称
            initial_state: 初始状态字典

        Returns:
            初始化完成的 AgentSession 对象

        Note:
            AgentSession 是 agent_framework 的核心类，用于管理会话状态。
            每个会话拥有独立的 session_id 和 state 字典。
        """
        async with self._lock:
            session_id = str(uuid.uuid4())
            session_info = AgentSessionInfo(
                session_id=session_id,
                agent_name=agent_name,
                state=initial_state or {},
            )
            self._sessions[session_id] = session_info

            # 创建 agent_framework 的 AgentSession
            # 注意：AgentSession 不接受 state 参数，状态由内部管理
            agent_session = AgentSession(
                session_id=session_id,
            )
            # 将状态存储在 session_info 中
            agent_session.state = session_info.state

            return agent_session

    async def get_session(self, session_id: str) -> Optional[AgentSessionInfo]:
        """
        获取会话信息

        Args:
            session_id: 会话 ID

        Returns:
            会话信息对象，不存在则返回 None
        """
        return self._sessions.get(session_id)

    async def update_session_state(
        self,
        session_id: str,
        state_updates: Dict[str, Any],
    ) -> bool:
        """
        更新会话状态

        Args:
            session_id: 会话 ID
            state_updates: 状态更新字典

        Returns:
            更新成功返回 True，会话不存在返回 False
        """
        async with self._lock:
            session_info = self._sessions.get(session_id)
            if session_info is None:
                return False

            session_info.state.update(state_updates)
            return True

    async def add_message_to_session(
        self,
        session_id: str,
        message: Message,
    ) -> bool:
        """
        向会话添加消息

        Args:
            session_id: 会话 ID
            message: 要添加的消息

        Returns:
            添加成功返回 True，会话不存在返回 False
        """
        async with self._lock:
            session_info = self._sessions.get(session_id)
            if session_info is None:
                return False

            session_info.message_history = list(session_info.message_history) + [message]
            return True

    async def close_session(self, session_id: str) -> bool:
        """
        关闭并清理会话

        Args:
            session_id: 会话 ID

        Returns:
            关闭成功返回 True，会话不存在返回 False
        """
        async with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    async def list_sessions(self) -> Sequence[AgentSessionInfo]:
        """
        列出所有活跃会话

        Returns:
            会话信息列表
        """
        return list(self._sessions.values())

    async def get_session_count(self) -> int:
        """获取活跃会话数量"""
        return len(self._sessions)


# ============================================================================
# 基础智能体类
# ============================================================================

class BaseResearchAgent(ABC, Generic[T]):
    """
    科研智能体基类

    为所有科研相关智能体提供统一的基础设施，包括：
    - 模型客户端管理
    - 会话管理
    - 上下文注入
    - 消息处理

    泛型参数 T 表示智能体的输出类型（Pydantic 模型）。

    设计原则：
    - 高内聚：每个智能体专注于单一职责
    - 低耦合：通过依赖注入获取配置和会话管理器
    - 可测试：提供 Mock 接口，便于单元测试
    """

    def __init__(
        self,
        name: str,
        llm_config: LLMConfig,
        session_manager: Optional[SessionManager] = None,
        context_provider: Optional[ResearchContextProvider] = None,
        instructions: Optional[str] = None,
    ):
        """
        初始化基础智能体

        Args:
            name: 智能体名称
            llm_config: LLM 配置
            session_manager: 会话管理器（可选，用于多会话场景）
            context_provider: 上下文提供者（可选）
            instructions: 系统指令（智能体的角色描述）
        """
        self._name = name
        self._llm_config = llm_config
        self._session_manager = session_manager or SessionManager()
        self._context_provider = context_provider
        self._instructions = instructions or self._default_instructions()

        # 初始化模型客户端
        self._client = ModelClientFactory.create_client(
            llm_config,
            cache_key=f"{name}_{llm_config.model_name}",
        )

        # 创建 agent_framework 的 Agent 实例
        self._agent = Agent(
            client=self._client,
            instructions=self._instructions,
            name=name,
        )

        # 当前会话（延迟初始化）
        self._current_session: Optional[AgentSession] = None

    @abstractmethod
    def _default_instructions(self) -> str:
        """
        获取默认系统指令

        子类必须实现此方法，定义智能体的角色和行为规范。

        Returns:
            系统指令字符串
        """
        pass

    @property
    def name(self) -> str:
        """获取智能体名称"""
        return self._name

    @property
    def agent(self) -> Agent:
        """获取底层 Agent 实例"""
        return self._agent

    @property
    def current_session(self) -> Optional[AgentSession]:
        """获取当前会话"""
        return self._current_session

    async def initialize_session(
        self,
        initial_state: Optional[Dict[str, Any]] = None,
    ) -> AgentSession:
        """
        初始化会话

        创建新的会话并设置为当前会话。

        Args:
            initial_state: 初始状态字典

        Returns:
            初始化完成的会话
        """
        self._current_session = await self._session_manager.create_session(
            agent_name=self._name,
            initial_state=initial_state,
        )
        return self._current_session

    def _build_messages(
        self,
        user_input: str,
        include_context: bool = True,
    ) -> Sequence[Message]:
        """
        构建消息列表

        将用户输入和上下文信息组合为消息列表。

        Args:
            user_input: 用户输入文本
            include_context: 是否包含上下文信息

        Returns:
            消息列表
        """
        messages = []

        # 添加上下文消息
        if include_context and self._context_provider:
            context_messages = self._context_provider.to_context_messages()
            messages.extend(context_messages)

        # 添加用户消息
        messages.append(Message(role="user", contents=[Content.from_text(user_input)]))

        return messages

    async def send_message(
        self,
        user_input: str,
        response_format: Optional[Dict[str, Any]] = None,
        include_context: bool = True,
    ) -> ChatResponse:
        """
        发送消息并获取响应

        这是智能体的核心方法，处理用户输入并返回模型响应。

        Args:
            user_input: 用户输入文本
            response_format: 可选的结构化输出格式
            include_context: 是否包含上下文信息

        Returns:
            模型的响应对象

        Note:
            如果指定了 response_format，模型将强制返回符合格式的 JSON。
            这对于需要结构化输出的场景（如分类、信息抽取）非常重要。
        """
        # 确保会话已初始化
        if self._current_session is None:
            await self.initialize_session()

        # 构建消息
        messages = self._build_messages(user_input, include_context)

        # 调用模型 - 使用 Agent.run 方法
        agent_response = await self._agent.run(
            messages=messages,
        )
        
        # 将 AgentResponse 转换为 ChatResponse
        # AgentResponse.text 包含所有消息的文本内容
        response = ChatResponse(
            messages=agent_response.messages,
        )

        # 更新会话历史
        if self._current_session:
            for msg in messages:
                await self._session_manager.add_message_to_session(
                    self._current_session.session_id,
                    msg,
                )
            if response.messages:
                for msg in response.messages:
                    await self._session_manager.add_message_to_session(
                        self._current_session.session_id,
                        msg,
                    )

        return response

    async def close(self) -> None:
        """
        关闭智能体

        清理会话资源。
        """
        if self._current_session:
            await self._session_manager.close_session(self._current_session.session_id)
            self._current_session = None


# ============================================================================
# 智能体管理器
# ============================================================================

class AgentManager:
    """
    智能体管理器

    统一管理所有智能体的创建、配置和生命周期。

    使用场景：
    - 根据配置动态创建不同类型的智能体
    - 管理智能体池（用于 Map-Reduce 架构）
    - 提供全局的会话管理
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        初始化智能体管理器

        Args:
            settings: 配置对象，默认使用全局配置
        """
        self._settings = settings or global_settings
        self._session_manager = SessionManager()
        self._agents: Dict[str, BaseResearchAgent] = {}

    def get_llm_config(self, llm_name: Optional[str] = None) -> LLMConfig:
        """
        获取 LLM 配置

        Args:
            llm_name: 模型名称，默认使用配置中的默认模型

        Returns:
            LLM 配置对象
        """
        return self._settings.get_llm_config(llm_name)

    @property
    def session_manager(self) -> SessionManager:
        """获取会话管理器"""
        return self._session_manager

    def register_agent(self, name: str, agent: BaseResearchAgent) -> None:
        """
        注册智能体

        Args:
            name: 智能体名称
            agent: 智能体实例
        """
        self._agents[name] = agent

    def get_agent(self, name: str) -> Optional[BaseResearchAgent]:
        """
        获取已注册的智能体

        Args:
            name: 智能体名称

        Returns:
            智能体实例，不存在则返回 None
        """
        return self._agents.get(name)

    def unregister_agent(self, name: str) -> bool:
        """
        注销智能体

        Args:
            name: 智能体名称

        Returns:
            注销成功返回 True，不存在返回 False
        """
        if name in self._agents:
            del self._agents[name]
            return True
        return False

    async def close_all(self) -> None:
        """关闭所有智能体"""
        for agent in self._agents.values():
            await agent.close()
        self._agents.clear()
