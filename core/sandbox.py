"""
Docker 沙箱执行模块

本模块提供安全的代码执行环境，用于运行 agent_framework 生成的实验代码。
核心特性：
- 严格隔离：无特权容器，限制网络访问，资源配额
- 自愈机制：集成 Debugging Agent，自动修复运行时错误
- 日志捕获：实时收集 stdout/stderr，支持 SSE 流式推送
- 超时控制：防止无限循环和资源耗尽

设计原则：
- 最小权限原则：容器以非 root 用户运行
- 防御深度：多层安全限制（seccomp、capabilities、cgroups）
- 可观测性：完整的执行日志和性能指标
"""

from typing import Optional, Dict, Any, List, Tuple, AsyncIterator
from dataclasses import dataclass, field
from enum import Enum
import asyncio
import json
import tempfile
import os
import time
from pathlib import Path
from datetime import datetime

# Docker SDK（可选依赖）
try:
    import docker
    from docker.models.containers import Container
    from docker.errors import DockerException, APIError, ContainerError
    DOCKER_AVAILABLE = True
except ImportError:
    docker = None
    Container = None
    DockerException = Exception
    APIError = Exception
    ContainerError = Exception
    DOCKER_AVAILABLE = False

# 本地导入
from core.config import settings
from agents.base import ModelClientFactory, LLMConfig


# ============================================================================
# 枚举和常量定义
# ============================================================================

class SandboxStatus(str, Enum):
    """沙箱状态枚举"""
    PENDING = "pending"          # 等待执行
    RUNNING = "running"          # 正在执行
    SUCCESS = "success"          # 执行成功
    FAILED = "failed"            # 执行失败
    TIMEOUT = "timeout"          # 执行超时
    DEBUGGING = "debugging"      # 正在调试修复


class ExecutionEnvironment(str, Enum):
    """执行环境枚举"""
    PYTHON_311 = "python:3.11-slim"
    PYTHON_310 = "python:3.10-slim"
    PYTHON_39 = "python:3.9-slim"
    CUSTOM = "custom"


# 安全配置常量
DEFAULT_TIMEOUT = 300  # 默认超时时间（秒）
DEFAULT_MEMORY_LIMIT = "512m"  # 默认内存限制
DEFAULT_CPU_QUOTA = 50000  # 默认 CPU 配额（50% of one CPU）
MAX_DEBUG_DEPTH = 3  # 最大调试深度
SECCOMP_PROFILE = {
    "defaultAction": "SCMP_ACT_ERRNO",
    "architectures": ["SCMP_ARCH_X86_64", "SCMP_ARCH_X86"],
    "syscalls": [
        {"names": ["read", "write", "open", "close", "stat", "fstat", "lstat",
                   "mmap", "mprotect", "munmap", "brk", "ioctl", "access",
                   "pipe", "dup2", "getpid", "socket", "connect", "sendto",
                   "recvfrom", "sendmsg", "recvmsg", "shutdown", "bind",
                   "listen", "accept", "getsockname", "getpeername",
                   "socketpair", "setsockopt", "getsockopt", "clone",
                   "execve", "exit", "wait4", "kill", "uname", "fcntl",
                   "flock", "fsync", "fdatasync", "truncate", "ftruncate",
                   "getdents", "getcwd", "chdir", "fchdir", "rename",
                   "mkdir", "rmdir", "unlink", "readlink", "symlink",
                   "chmod", "fchmod", "chown", "fchown", "lchown",
                   "umask", "gettimeofday", "getrlimit", "getrusage",
                   "sysinfo", "times", "getuid", "getgid", "setuid",
                   "setgid", "geteuid", "getegid", "setpgid", "getppid",
                   "getpgrp", "setsid", "setreuid", "setregid", "getgroups",
                   "setgroups", "setresuid", "getresuid", "setresgid",
                   "getresgid", "getpgid", "setfsuid", "setfsgid",
                   "getsid", "capget", "capset", "rt_sigpending",
                   "rt_sigtimedwait", "rt_sigqueueinfo", "rt_sigsuspend",
                   "sigaltstack", "utime", "statfs", "fstatfs",
                   "getpriority", "setpriority", "sched_setparam",
                   "sched_getparam", "sched_setscheduler", "sched_getscheduler",
                   "sched_get_priority_max", "sched_get_priority_min",
                   "sched_rr_get_interval", "mlock", "munlock", "mlockall",
                   "munlockall", "vhangup", "pivot_root", "_sysctl",
                   "prctl", "arch_prctl", "adjtimex", "setrlimit", "chroot",
                   "sync", "acct", "settimeofday", "mount", "umount2",
                   "swapon", "swapoff", "reboot", "sethostname",
                   "setdomainname", "iopl", "ioperm", "init_module",
                   "delete_module", "quotactl", "gettid", "readahead",
                   "setxattr", "lsetxattr", "fsetxattr", "getxattr",
                   "lgetxattr", "fgetxattr", "listxattr", "llistxattr",
                   "flistxattr", "removexattr", "lremovexattr",
                   "fremovexattr", "tkill", "time", "futex", "sched_setaffinity",
                   "sched_getaffinity", "set_thread_area", "io_setup",
                   "io_destroy", "io_getevents", "io_submit", "io_cancel",
                   "get_thread_area", "epoll_create", "epoll_ctl",
                   "epoll_wait", "remap_file_pages", "getdents64",
                   "set_tid_address", "restart_syscall", "semtimedop",
                   "fadvise64", "timer_create", "timer_settime",
                   "timer_gettime", "timer_getoverrun", "timer_delete",
                   "clock_settime", "clock_gettime", "clock_getres",
                   "clock_nanosleep", "exit_group", "epoll_wait",
                   "epoll_ctl", "tgkill", "utimes", "mbind", "set_mempolicy",
                   "get_mempolicy", "mq_open", "mq_unlink", "mq_timedsend",
                   "mq_timedreceive", "mq_notify", "mq_getsetattr",
                   "kexec_load", "waitid", "add_key", "request_key",
                   "keyctl", "ioprio_set", "ioprio_get", "inotify_init",
                   "inotify_add_watch", "inotify_rm_watch", "migrate_pages",
                   "openat", "mkdirat", "mknodat", "fchownat", "futimesat",
                   "newfstatat", "unlinkat", "renameat", "linkat",
                   "symlinkat", "readlinkat", "fchmodat", "faccessat",
                   "pselect6", "ppoll", "unshare", "set_robust_list",
                   "get_robust_list", "splice", "sync_file_range", "tee",
                   "vmsplice", "move_pages", "utimensat", "epoll_pwait",
                   "signalfd", "timerfd_create", "eventfd", "fallocate",
                   "timerfd_settime", "timerfd_gettime", "accept4",
                   "signalfd4", "eventfd2", "epoll_create1", "dup3",
                   "pipe2", "inotify_init1", "preadv", "pwritev",
                   "rt_tgsigqueueinfo", "perf_event_open", "recvmmsg",
                   "fanotify_init", "fanotify_mark", "prlimit64",
                   "name_to_handle_at", "open_by_handle_at", "clock_adjtime",
                   "syncfs", "sendmmsg", "setns", "getcpu", "process_vm_readv",
                   "process_vm_writev", "kcmp", "finit_module", "sched_setattr",
                   "sched_getattr", "renameat2", "seccomp", "getrandom",
                   "memfd_create", "kexec_file_load", "bpf", "execveat",
                   "userfaultfd", "membarrier", "mlock2", "copy_file_range",
                   "preadv2", "pwritev2", "pkey_mprotect", "pkey_alloc",
                   "pkey_free", "statx"],
         "action": "SCMP_ACT_ALLOW"}
    ]
}


# ============================================================================
# 数据类定义
# ============================================================================

@dataclass
class ExecutionResult:
    """
    代码执行结果

    记录沙箱执行的完整信息，包括输出、错误、性能指标等。
    """
    status: SandboxStatus
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    execution_time_ms: float = 0.0
    memory_used_mb: float = 0.0
    cpu_time_ms: float = 0.0
    error_message: Optional[str] = None
    debug_attempts: int = 0
    debug_history: List[Dict[str, Any]] = field(default_factory=list)
    artifacts: Dict[str, str] = field(default_factory=dict)  # 输出文件路径映射
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SandboxConfig:
    """
    沙箱配置

    定义沙箱的安全限制和资源配额。
    """
    # 基础配置
    image: str = "python:3.11-slim"
    timeout: int = DEFAULT_TIMEOUT
    working_dir: str = "/workspace"

    # 资源限制
    memory_limit: str = DEFAULT_MEMORY_LIMIT
    cpu_quota: int = DEFAULT_CPU_QUOTA
    pids_limit: int = 100

    # 安全配置
    disable_network: bool = True
    read_only_root: bool = False
    drop_all_capabilities: bool = True
    no_new_privileges: bool = True

    # 调试配置
    max_debug_depth: int = MAX_DEBUG_DEPTH
    enable_debugging: bool = True

    # 挂载配置
    volumes: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # 环境变量
    environment: Dict[str, str] = field(default_factory=dict)


# ============================================================================
# Debugging Agent（调试智能体）
# ============================================================================

class DebuggingAgent:
    """
    调试智能体

    当沙箱执行失败时，自动分析错误并尝试修复代码。
    支持多轮调试，每轮都会生成修复建议并重新执行。

    核心能力：
    - 错误分析：解析 traceback，识别错误类型和位置
    - 代码修复：基于错误上下文生成修复代码
    - 学习机制：记录修复历史，避免重复错误
    """

    def __init__(
        self,
        llm_config: LLMConfig,
        max_debug_depth: int = MAX_DEBUG_DEPTH,
    ):
        """
        初始化调试智能体

        Args:
            llm_config: LLM 配置
            max_debug_depth: 最大调试深度
        """
        self._llm_config = llm_config
        self._max_debug_depth = max_debug_depth
        self._client = ModelClientFactory.create_client(
            llm_config,
            cache_key=f"debugging_agent_{llm_config.model_name}",
        )

    def _build_debug_prompt(
        self,
        original_code: str,
        error_output: str,
        attempt: int,
        previous_fixes: List[str],
    ) -> str:
        """
        构建调试提示词

        Args:
            original_code: 原始代码
            error_output: 错误输出
            attempt: 当前尝试次数
            previous_fixes: 之前的修复尝试

        Returns:
            调试提示词
        """
        prompt = f"""你是一个专业的 Python 代码调试专家。请分析以下错误并修复代码。

## 原始代码
```python
{original_code}
```

## 错误信息
```
{error_output}
```

## 调试历史
当前是第 {attempt + 1} 次尝试（最多 {self._max_debug_depth} 次）。
"""
        if previous_fixes:
            prompt += "\n### 之前的修复尝试（均未成功）：\n"
            for i, fix in enumerate(previous_fixes, 1):
                prompt += f"\n**尝试 {i}:**\n```\n{fix}\n```\n"

        prompt += """
## 任务要求
1. 仔细分析错误信息，定位问题根源
2. 生成修复后的完整代码（不要只给出修改部分）
3. 确保修复后的代码能够正确执行
4. 如果是依赖问题，在代码开头添加必要的 import 或 pip install 命令
5. 如果是逻辑错误，修正算法或数据处理流程

## 输出格式
请直接输出修复后的完整 Python 代码，不要添加任何解释或注释。
代码应该以 ```python 开头，以 ``` 结尾。
"""
        return prompt

    async def debug_and_fix(
        self,
        original_code: str,
        error_output: str,
        attempt: int,
        previous_fixes: List[str],
    ) -> str:
        """
        调试并生成修复代码

        Args:
            original_code: 原始代码
            error_output: 错误输出
            attempt: 当前尝试次数
            previous_fixes: 之前的修复尝试

        Returns:
            修复后的代码
        """
        from agent_framework import Message, Content

        prompt = self._build_debug_prompt(
            original_code,
            error_output,
            attempt,
            previous_fixes,
        )

        messages = [Message(role="user", contents=[Content.from_text(prompt)])]

        options = ModelClientFactory.get_chat_options(self._llm_config)

        response = await self._client.get_response(messages=messages, options=options)

        # 提取代码块
        fixed_code = ""
        if response.messages:
            content = response.messages[0].contents[0].text
            # 提取 ```python ... ``` 之间的内容
            if "```python" in content:
                start = content.find("```python") + len("```python")
                end = content.find("```", start)
                if end > start:
                    fixed_code = content[start:end].strip()
            else:
                # 如果没有代码块标记，直接使用整个响应
                fixed_code = content.strip()

        return fixed_code


# ============================================================================
# Docker 沙箱执行器
# ============================================================================

class DockerSandbox:
    """
    Docker 沙箱执行器

    提供安全的代码执行环境，支持：
    - 严格隔离的容器执行
    - 自动调试和错误修复
    - 实时日志流式输出
    - 资源使用监控

    使用示例：
    ```python
    sandbox = DockerSandbox()
    result = await sandbox.execute(
        code="print('Hello, World!')",
        config=SandboxConfig(timeout=60)
    )
    print(result.stdout)  # Hello, World!
    ```
    """

    def __init__(
        self,
        config: Optional[SandboxConfig] = None,
        llm_config: Optional[LLMConfig] = None,
    ):
        """
        初始化 Docker 沙箱

        Args:
            config: 沙箱配置
            llm_config: LLM 配置（用于调试智能体）
        """
        self._config = config or SandboxConfig()
        self._llm_config = llm_config

        # 检查 Docker 是否可用
        if not DOCKER_AVAILABLE:
            raise ImportError(
                "Docker SDK 未安装。请运行: pip install docker>=7.0.0\n"
                "或者使用 MockDockerSandbox 进行测试。"
            )

        # 初始化 Docker 客户端
        try:
            self._client = docker.from_env()
        except DockerException as e:
            raise RuntimeError(f"无法连接到 Docker 守护进程: {e}")

        # 调试智能体（延迟初始化）
        self._debugging_agent: Optional[DebuggingAgent] = None

        # 执行历史
        self._execution_history: List[ExecutionResult] = []

    def _get_debugging_agent(self) -> DebuggingAgent:
        """获取或创建调试智能体"""
        if self._debugging_agent is None:
            if self._llm_config is None:
                # 使用默认配置
                self._llm_config = settings.get_llm_config()
            self._debugging_agent = DebuggingAgent(
                self._llm_config,
                self._config.max_debug_depth,
            )
        return self._debugging_agent

    def _build_container_config(
        self,
        code: str,
        input_files: Optional[Dict[str, str]] = None,
    ) -> Dict[str, Any]:
        """
        构建容器配置

        Args:
            code: 要执行的代码
            input_files: 输入文件映射 {文件名: 文件内容}

        Returns:
            Docker 容器配置字典
        """
        # 创建临时目录用于代码和输入文件
        temp_dir = tempfile.mkdtemp(prefix="sandbox_")

        # 写入代码文件
        code_path = os.path.join(temp_dir, "main.py")
        with open(code_path, "w", encoding="utf-8") as f:
            f.write(code)

        # 写入输入文件
        if input_files:
            for filename, content in input_files.items():
                file_path = os.path.join(temp_dir, filename)
                with open(file_path, "w", encoding="utf-8") as f:
                    f.write(content)

        # 构建挂载配置
        volumes = {
            temp_dir: {
                "bind": self._config.working_dir,
                "mode": "rw" if not self._config.read_only_root else "ro",
            }
        }
        volumes.update(self._config.volumes)

        # 构建安全配置
        security_opt = []
        if self._config.no_new_privileges:
            security_opt.append("no-new-privileges")

        # 构建能力配置
        cap_drop = ["ALL"] if self._config.drop_all_capabilities else []

        # 构建环境变量
        environment = {
            "PYTHONUNBUFFERED": "1",  # 禁用缓冲，实时输出
            "PYTHONDONTWRITEBYTECODE": "1",  # 不生成 .pyc 文件
        }
        environment.update(self._config.environment)

        return {
            "image": self._config.image,
            "command": f"python {self._config.working_dir}/main.py",
            "volumes": volumes,
            "working_dir": self._config.working_dir,
            "environment": environment,
            "mem_limit": self._config.memory_limit,
            "cpu_quota": self._config.cpu_quota,
            "pids_limit": self._config.pids_limit,
            "network_disabled": self._config.disable_network,
            "security_opt": security_opt,
            "cap_drop": cap_drop,
            "detach": True,  # 后台运行
            "stdout": True,
            "stderr": True,
            "remove": False,  # 不自动删除，需要获取日志
            "user": "nobody",  # 非 root 用户运行
        }

    async def _run_container(
        self,
        container_config: Dict[str, Any],
        timeout: int,
    ) -> Tuple[int, str, str, Dict[str, Any]]:
        """
        运行容器并收集输出

        Args:
            container_config: 容器配置
            timeout: 超时时间（秒）

        Returns:
            (exit_code, stdout, stderr, stats)
        """
        container: Optional[Container] = None

        try:
            # 创建容器
            container = self._client.containers.run(**container_config)

            # 等待容器完成（带超时）
            start_time = time.time()
            while True:
                container.reload()
                status = container.status

                if status == "exited":
                    break

                if time.time() - start_time > timeout:
                    # 超时，强制停止
                    container.stop(timeout=5)
                    raise asyncio.TimeoutError(f"执行超时（{timeout}秒）")

                await asyncio.sleep(0.1)

            # 获取输出
            stdout = container.logs(stdout=True, stderr=False).decode("utf-8")
            stderr = container.logs(stdout=False, stderr=True).decode("utf-8")

            # 获取退出码
            exit_code = container.attrs["State"]["ExitCode"]

            # 获取资源使用统计
            stats = container.stats(stream=False)

            return exit_code, stdout, stderr, stats

        finally:
            # 清理容器
            if container:
                try:
                    container.remove(force=True)
                except APIError:
                    pass

    async def execute(
        self,
        code: str,
        input_files: Optional[Dict[str, str]] = None,
        config_override: Optional[SandboxConfig] = None,
    ) -> ExecutionResult:
        """
        执行代码

        这是沙箱的核心方法，执行代码并返回结果。
        如果启用了调试功能，失败时会自动尝试修复。

        Args:
            code: 要执行的 Python 代码
            input_files: 输入文件映射 {文件名: 文件内容}
            config_override: 配置覆盖（可选）

        Returns:
            执行结果对象
        """
        config = config_override or self._config
        start_time = time.time()

        # 初始化结果对象
        result = ExecutionResult(
            status=SandboxStatus.PENDING,
            debug_history=[],
        )

        # 当前代码和修复历史
        current_code = code
        previous_fixes: List[str] = []
        attempt = 0

        while attempt <= (config.max_debug_depth if config.enable_debugging else 0):
            result.status = SandboxStatus.RUNNING
            result.debug_attempts = attempt

            try:
                # 构建容器配置
                container_config = self._build_container_config(
                    current_code,
                    input_files,
                )

                # 运行容器
                exit_code, stdout, stderr, stats = await self._run_container(
                    container_config,
                    config.timeout,
                )

                # 更新结果
                result.exit_code = exit_code
                result.stdout = stdout
                result.stderr = stderr
                result.execution_time_ms = (time.time() - start_time) * 1000

                # 提取资源使用信息
                if stats:
                    memory_stats = stats.get("memory_stats", {})
                    result.memory_used_mb = memory_stats.get("max_usage", 0) / (1024 * 1024)

                    cpu_stats = stats.get("cpu_stats", {})
                    precpu_stats = stats.get("precpu_stats", {})
                    if cpu_stats and precpu_stats:
                        cpu_delta = cpu_stats.get("cpu_usage", {}).get("total_usage", 0) - \
                                   precpu_stats.get("cpu_usage", {}).get("total_usage", 0)
                        result.cpu_time_ms = cpu_delta / 1000000  # 纳秒转毫秒

                # 检查执行结果
                if exit_code == 0:
                    result.status = SandboxStatus.SUCCESS
                    break
                else:
                    result.status = SandboxStatus.FAILED
                    result.error_message = stderr or f"退出码: {exit_code}"

                    # 记录调试历史
                    result.debug_history.append({
                        "attempt": attempt,
                        "code": current_code,
                        "error": result.error_message,
                        "timestamp": datetime.now().isoformat(),
                    })

                    # 如果启用了调试且未达到最大深度，尝试修复
                    if config.enable_debugging and attempt < config.max_debug_depth:
                        result.status = SandboxStatus.DEBUGGING

                        debugging_agent = self._get_debugging_agent()
                        fixed_code = await debugging_agent.debug_and_fix(
                            current_code,
                            result.error_message,
                            attempt,
                            previous_fixes,
                        )

                        if fixed_code and fixed_code != current_code:
                            previous_fixes.append(fixed_code)
                            current_code = fixed_code
                            attempt += 1
                            continue
                        else:
                            # 无法生成有效修复，退出循环
                            break
                    else:
                        break

            except asyncio.TimeoutError as e:
                result.status = SandboxStatus.TIMEOUT
                result.error_message = str(e)
                break

            except DockerException as e:
                result.status = SandboxStatus.FAILED
                result.error_message = f"Docker 错误: {e}"
                break

            except Exception as e:
                result.status = SandboxStatus.FAILED
                result.error_message = f"未知错误: {e}"
                break

        # 记录执行历史
        self._execution_history.append(result)

        return result

    async def execute_stream(
        self,
        code: str,
        input_files: Optional[Dict[str, str]] = None,
        config_override: Optional[SandboxConfig] = None,
    ) -> AsyncIterator[Dict[str, Any]]:
        """
        流式执行代码

        与 execute 方法类似，但通过 SSE 实时推送执行状态和日志。

        Args:
            code: 要执行的 Python 代码
            input_files: 输入文件映射
            config_override: 配置覆盖

        Yields:
            执行状态事件字典
        """
        config = config_override or self._config
        start_time = time.time()

        # 发送开始事件
        yield {
            "event": "start",
            "data": {
                "status": "pending",
                "timestamp": datetime.now().isoformat(),
            }
        }

        current_code = code
        previous_fixes: List[str] = []
        attempt = 0

        while attempt <= (config.max_debug_depth if config.enable_debugging else 0):
            # 发送执行事件
            yield {
                "event": "execution",
                "data": {
                    "status": "running",
                    "attempt": attempt,
                    "timestamp": datetime.now().isoformat(),
                }
            }

            try:
                container_config = self._build_container_config(
                    current_code,
                    input_files,
                )

                # 创建容器
                container = self._client.containers.run(**container_config)

                # 流式读取日志
                stdout_buffer = []
                stderr_buffer = []

                for line in container.logs(stream=True, stdout=True, stderr=True):
                    line_str = line.decode("utf-8").strip()

                    # 判断是 stdout 还是 stderr
                    if line_str:
                        if "error" in line_str.lower() or "exception" in line_str.lower():
                            stderr_buffer.append(line_str)
                            yield {
                                "event": "stderr",
                                "data": {
                                    "line": line_str,
                                    "timestamp": datetime.now().isoformat(),
                                }
                            }
                        else:
                            stdout_buffer.append(line_str)
                            yield {
                                "event": "stdout",
                                "data": {
                                    "line": line_str,
                                    "timestamp": datetime.now().isoformat(),
                                }
                            }

                # 等待容器完成
                container.wait(timeout=config.timeout)
                exit_code = container.attrs["State"]["ExitCode"]

                # 清理容器
                container.remove(force=True)

                stdout = "\n".join(stdout_buffer)
                stderr = "\n".join(stderr_buffer)

                if exit_code == 0:
                    # 执行成功
                    yield {
                        "event": "complete",
                        "data": {
                            "status": "success",
                            "exit_code": exit_code,
                            "stdout": stdout,
                            "stderr": stderr,
                            "execution_time_ms": (time.time() - start_time) * 1000,
                            "timestamp": datetime.now().isoformat(),
                        }
                    }
                    break
                else:
                    # 执行失败
                    error_message = stderr or f"退出码: {exit_code}"

                    yield {
                        "event": "error",
                        "data": {
                            "status": "failed",
                            "exit_code": exit_code,
                            "error": error_message,
                            "timestamp": datetime.now().isoformat(),
                        }
                    }

                    # 尝试调试修复
                    if config.enable_debugging and attempt < config.max_debug_depth:
                        yield {
                            "event": "debugging",
                            "data": {
                                "status": "debugging",
                                "attempt": attempt + 1,
                                "timestamp": datetime.now().isoformat(),
                            }
                        }

                        debugging_agent = self._get_debugging_agent()
                        fixed_code = await debugging_agent.debug_and_fix(
                            current_code,
                            error_message,
                            attempt,
                            previous_fixes,
                        )

                        if fixed_code and fixed_code != current_code:
                            previous_fixes.append(fixed_code)
                            current_code = fixed_code
                            attempt += 1
                            continue
                        else:
                            break
                    else:
                        break

            except asyncio.TimeoutError:
                yield {
                    "event": "timeout",
                    "data": {
                        "status": "timeout",
                        "timestamp": datetime.now().isoformat(),
                    }
                }
                break

            except Exception as e:
                yield {
                    "event": "error",
                    "data": {
                        "status": "failed",
                        "error": str(e),
                        "timestamp": datetime.now().isoformat(),
                    }
                }
                break

    def get_execution_history(self) -> List[ExecutionResult]:
        """获取执行历史"""
        return self._execution_history

    def clear_history(self) -> None:
        """清空执行历史"""
        self._execution_history.clear()

    async def health_check(self) -> bool:
        """
        健康检查

        检查 Docker 守护进程是否可用。

        Returns:
            健康状态
        """
        try:
            self._client.ping()
            return True
        except DockerException:
            return False

    async def pull_image(self, image: Optional[str] = None) -> bool:
        """
        拉取 Docker 镜像

        Args:
            image: 镜像名称，默认使用配置中的镜像

        Returns:
            拉取成功返回 True
        """
        image_name = image or self._config.image
        try:
            self._client.images.pull(image_name)
            return True
        except DockerException:
            return False


# ============================================================================
# 便捷函数
# ============================================================================

async def execute_in_sandbox(
    code: str,
    timeout: int = DEFAULT_TIMEOUT,
    enable_debugging: bool = True,
    llm_config: Optional[LLMConfig] = None,
) -> ExecutionResult:
    """
    在沙箱中执行代码（便捷函数）

    Args:
        code: Python 代码
        timeout: 超时时间（秒）
        enable_debugging: 是否启用调试
        llm_config: LLM 配置

    Returns:
        执行结果
    """
    config = SandboxConfig(
        timeout=timeout,
        enable_debugging=enable_debugging,
    )
    sandbox = DockerSandbox(config, llm_config)
    return await sandbox.execute(code)
