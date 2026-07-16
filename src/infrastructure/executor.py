import asyncio
import os
import signal
import sys
from dataclasses import dataclass

from src.infrastructure.script_files import ScriptFileResolver
from src.models.process import FileProcessSource, Process, ProcessType


@dataclass(frozen=True)
class ExecutionResult:
    return_code: int
    output: str


class ProcessTimeoutError(TimeoutError):
    def __init__(self, timeout_seconds: float, output: str) -> None:
        self.output = output
        super().__init__(f"process exceeded {timeout_seconds:g} seconds")


class ProcessExecutor:
    def __init__(
        self,
        timeout_seconds: float,
        max_output_bytes: int,
        script_files: ScriptFileResolver,
    ) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_output_bytes = max_output_bytes
        self._script_files = script_files

    async def execute(
        self,
        process: Process,
        arguments: tuple[str, ...],
    ) -> ExecutionResult:
        command, working_directory = self._command(process, arguments)
        child = await asyncio.create_subprocess_exec(
            *command,
            cwd=working_directory,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            start_new_session=True,
        )
        if child.stdout is None:
            raise RuntimeError("process output stream was not created")
        output_task = asyncio.create_task(self._read_output(child.stdout))
        try:
            await asyncio.wait_for(
                child.wait(),
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            await self._kill_process_tree(child)
            output = await output_task
            raise ProcessTimeoutError(
                self._timeout_seconds,
                self._decode(output),
            ) from None
        except asyncio.CancelledError:
            await self._kill_process_tree(child)
            await output_task
            raise

        output = await output_task
        return ExecutionResult(
            return_code=child.returncode,
            output=self._decode(output),
        )

    @staticmethod
    async def _kill_process_tree(child: asyncio.subprocess.Process) -> None:
        if child.returncode is None:
            try:
                os.killpg(child.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        await child.wait()

    def _command(
        self,
        process: Process,
        arguments: tuple[str, ...],
    ) -> tuple[tuple[str, ...], str | None]:
        if isinstance(process.source, FileProcessSource):
            path = str(self._script_files.resolve(process.source.path))
            if process.type is ProcessType.BASH:
                command = ("/usr/bin/env", "bash", path, *arguments)
            else:
                command = (sys.executable, path, *arguments)
            return command, str(self._script_files.root)

        if process.type is ProcessType.BASH:
            command = ("/usr/bin/env", "bash", "-c", process.source.content)
            if arguments:
                command = (*command, process.name, *arguments)
        else:
            command = (sys.executable, "-c", process.source.content, *arguments)
        return command, None

    async def _read_output(self, stream: asyncio.StreamReader) -> bytes:
        captured = bytearray()
        truncated = False
        while chunk := await stream.read(65_536):
            remaining = self._max_output_bytes - len(captured)
            if remaining > 0:
                captured.extend(chunk[:remaining])
            if len(chunk) > remaining:
                truncated = True

        if not truncated:
            return bytes(captured)

        suffix = b"\n[output truncated]\n"
        if self._max_output_bytes < len(suffix):
            return bytes(captured[: self._max_output_bytes])
        keep = self._max_output_bytes - len(suffix)
        return bytes(captured[:keep]) + suffix

    @staticmethod
    def _decode(output: bytes) -> str:
        return output.decode(errors="replace")
