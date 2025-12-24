"""
Provides BSL (1C:Enterprise) specific instantiation of the LanguageServer class.
Contains various configurations and settings specific to BSL Language Server.

BSL Language Server is an open-source language server for 1C:Enterprise 8 and OneScript.
See: https://github.com/1c-syntax/bsl-language-server

You can configure the following options in ls_specific_settings (in serena_config.yml):

    ls_specific_settings:
      bsl:
        ls_jar_path: '/path/to/bsl-language-server-exec.jar'  # Path to the BSL LS JAR file
        ls_java_home_path: '/path/to/java'  # Optional: Custom Java home path
        configuration_path: '/path/to/.bsl-language-server.json'  # Optional: BSL LS config file

Example configuration:

    ls_specific_settings:
      bsl:
        ls_jar_path: '/home/user/.local/bsl-language-server-0.25.2-exec.jar'
"""

import dataclasses
import logging
import os
import pathlib
from typing import cast

from overrides import override

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import Language, LanguageServerConfig
from solidlsp.ls_utils import FileUtils, PlatformUtils
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings

log = logging.getLogger(__name__)


# BSL Language Server download URL (latest stable version)
BSL_LS_VERSION = "0.25.2"
BSL_LS_JAR_NAME = f"bsl-language-server-{BSL_LS_VERSION}-exec.jar"
BSL_LS_DOWNLOAD_URL = f"https://github.com/1c-syntax/bsl-language-server/releases/download/v{BSL_LS_VERSION}/{BSL_LS_JAR_NAME}"


@dataclasses.dataclass
class BSLRuntimeDependencyPaths:
    """
    Stores the paths to the runtime dependencies of BSL Language Server
    """

    java_path: str
    java_home_path: str
    ls_jar_path: str


class BSLLanguageServer(SolidLanguageServer):
    """
    Provides BSL (1C:Enterprise) specific instantiation of the LanguageServer class.
    Contains various configurations and settings specific to BSL Language Server.
    """

    @override
    def is_ignored_dirname(self, dirname: str) -> bool:
        # Ignore common 1C:Enterprise build/cache directories
        return super().is_ignored_dirname(dirname) or dirname in [
            "build",
            "bin",
            "out",
        ]

    def __init__(self, config: LanguageServerConfig, repository_root_path: str, solidlsp_settings: SolidLSPSettings):
        """
        Creates a BSL Language Server instance.
        This class is not meant to be instantiated directly. Use LanguageServer.create() instead.
        """
        runtime_dependency_paths = self._setup_runtime_dependencies(solidlsp_settings)
        self.runtime_dependency_paths = runtime_dependency_paths

        # Create command to execute the BSL Language Server
        cmd = [
            self.runtime_dependency_paths.java_path,
            "-jar",
            self.runtime_dependency_paths.ls_jar_path,
            "lsp",
            "--stdio",
        ]

        # Check for custom configuration file
        if solidlsp_settings.ls_specific_settings:
            bsl_settings = solidlsp_settings.get_ls_specific_settings(Language.BSL)
            config_path = bsl_settings.get("configuration_path")
            if config_path and os.path.exists(config_path):
                cmd.extend(["--configuration", config_path])
                log.info(f"Using BSL LS configuration from: {config_path}")

        # Set environment variables including JAVA_HOME
        proc_env = {"JAVA_HOME": self.runtime_dependency_paths.java_home_path}

        super().__init__(
            config,
            repository_root_path,
            ProcessLaunchInfo(cmd=cmd, env=proc_env, cwd=repository_root_path),
            "bsl",
            solidlsp_settings,
        )

    @classmethod
    def _setup_runtime_dependencies(cls, solidlsp_settings: SolidLSPSettings) -> BSLRuntimeDependencyPaths:
        """
        Setup runtime dependencies for BSL Language Server and return paths.
        """
        platform_id = PlatformUtils.get_platform_id()

        # Verify platform support
        assert (
            platform_id.value.startswith("win-") or platform_id.value.startswith("linux-") or platform_id.value.startswith("osx-")
        ), "Only Windows, Linux and macOS platforms are supported for BSL in SolidLSP at the moment"

        # Check if user specified custom Java home path
        java_home_path = None
        java_path = None

        if solidlsp_settings and solidlsp_settings.ls_specific_settings:
            bsl_settings = solidlsp_settings.get_ls_specific_settings(Language.BSL)
            custom_java_home = bsl_settings.get("ls_java_home_path")
            if custom_java_home:
                log.info(f"Using custom Java home path from configuration: {custom_java_home}")
                java_home_path = custom_java_home

                # Determine java executable path based on platform
                if platform_id.value.startswith("win-"):
                    java_path = os.path.join(java_home_path, "bin", "java.exe")
                else:
                    java_path = os.path.join(java_home_path, "bin", "java")

        # If no custom Java home path, download and use bundled Java
        if java_home_path is None:
            # Runtime dependency information (same as other Java-based LS)
            runtime_dependencies = {
                "java": {
                    "win-x64": {
                        "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-win32-x64-1.42.0-561.vsix",
                        "archiveType": "zip",
                        "java_home_path": "extension/jre/21.0.7-win32-x86_64",
                        "java_path": "extension/jre/21.0.7-win32-x86_64/bin/java.exe",
                    },
                    "linux-x64": {
                        "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-linux-x64-1.42.0-561.vsix",
                        "archiveType": "zip",
                        "java_home_path": "extension/jre/21.0.7-linux-x86_64",
                        "java_path": "extension/jre/21.0.7-linux-x86_64/bin/java",
                    },
                    "linux-arm64": {
                        "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-linux-arm64-1.42.0-561.vsix",
                        "archiveType": "zip",
                        "java_home_path": "extension/jre/21.0.7-linux-aarch64",
                        "java_path": "extension/jre/21.0.7-linux-aarch64/bin/java",
                    },
                    "osx-x64": {
                        "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-darwin-x64-1.42.0-561.vsix",
                        "archiveType": "zip",
                        "java_home_path": "extension/jre/21.0.7-macosx-x86_64",
                        "java_path": "extension/jre/21.0.7-macosx-x86_64/bin/java",
                    },
                    "osx-arm64": {
                        "url": "https://github.com/redhat-developer/vscode-java/releases/download/v1.42.0/java-darwin-arm64-1.42.0-561.vsix",
                        "archiveType": "zip",
                        "java_home_path": "extension/jre/21.0.7-macosx-aarch64",
                        "java_path": "extension/jre/21.0.7-macosx-aarch64/bin/java",
                    },
                },
            }

            java_dependency = runtime_dependencies["java"][platform_id.value]

            static_dir = os.path.join(cls.ls_resources_dir(solidlsp_settings), "bsl_language_server")
            os.makedirs(static_dir, exist_ok=True)

            java_dir = os.path.join(static_dir, "java")
            os.makedirs(java_dir, exist_ok=True)

            java_home_path = os.path.join(java_dir, java_dependency["java_home_path"])
            java_path = os.path.join(java_dir, java_dependency["java_path"])

            if not os.path.exists(java_path):
                log.info(f"Downloading Java for {platform_id.value}...")
                FileUtils.download_and_extract_archive(java_dependency["url"], java_dir, java_dependency["archiveType"])

                if not platform_id.value.startswith("win-"):
                    os.chmod(java_path, 0o755)

        assert java_path and os.path.exists(java_path), f"Java executable not found at {java_path}"

        ls_jar_path = cls._find_or_download_bsl_ls_jar(solidlsp_settings)

        return BSLRuntimeDependencyPaths(java_path=java_path, java_home_path=java_home_path, ls_jar_path=ls_jar_path)

    @classmethod
    def _find_or_download_bsl_ls_jar(cls, solidlsp_settings: SolidLSPSettings) -> str:
        """
        Find or download BSL Language Server JAR file.
        """
        # Check if user specified a custom JAR path
        if solidlsp_settings and solidlsp_settings.ls_specific_settings:
            bsl_settings = solidlsp_settings.get_ls_specific_settings(Language.BSL)
            config_jar_path = bsl_settings.get("ls_jar_path")
            if config_jar_path:
                if os.path.exists(config_jar_path):
                    log.info(f"Using BSL LS JAR from configuration: {config_jar_path}")
                    return config_jar_path
                else:
                    log.warning(f"Configured BSL LS JAR path does not exist: {config_jar_path}")

        # Download the BSL Language Server JAR if not found
        static_dir = os.path.join(cls.ls_resources_dir(solidlsp_settings), "bsl_language_server")
        os.makedirs(static_dir, exist_ok=True)

        jar_path = os.path.join(static_dir, BSL_LS_JAR_NAME)

        if not os.path.exists(jar_path):
            log.info(f"Downloading BSL Language Server v{BSL_LS_VERSION}...")
            FileUtils.download_and_extract_archive(BSL_LS_DOWNLOAD_URL, jar_path, "binary")

        assert os.path.exists(jar_path), f"BSL Language Server JAR not found at {jar_path}"

        return jar_path

    @staticmethod
    def _get_initialize_params(repository_absolute_path: str) -> InitializeParams:
        """
        Returns the initialize params for the BSL Language Server.
        """
        if not os.path.isabs(repository_absolute_path):
            repository_absolute_path = os.path.abspath(repository_absolute_path)

        root_uri = pathlib.Path(repository_absolute_path).as_uri()
        initialize_params = {
            "clientInfo": {"name": "Serena BSL Client", "version": "1.0.0"},
            "locale": "en",
            "rootPath": repository_absolute_path,
            "rootUri": root_uri,
            "capabilities": {
                "textDocument": {
                    "synchronization": {"dynamicRegistration": True, "didSave": True},
                    "completion": {
                        "dynamicRegistration": True,
                        "completionItem": {
                            "snippetSupport": False,
                            "documentationFormat": ["markdown", "plaintext"],
                        },
                    },
                    "hover": {"dynamicRegistration": True, "contentFormat": ["markdown", "plaintext"]},
                    "definition": {"dynamicRegistration": True, "linkSupport": True},
                    "references": {"dynamicRegistration": True},
                    "documentSymbol": {
                        "dynamicRegistration": True,
                        "hierarchicalDocumentSymbolSupport": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                    },
                    "formatting": {"dynamicRegistration": True},
                    "rangeFormatting": {"dynamicRegistration": True},
                    "codeAction": {"dynamicRegistration": True},
                    "codeLens": {"dynamicRegistration": True},
                    "rename": {"dynamicRegistration": True},
                    "foldingRange": {"dynamicRegistration": True},
                    "callHierarchy": {"dynamicRegistration": True},
                },
                "workspace": {
                    "workspaceFolders": True,
                    "didChangeConfiguration": {"dynamicRegistration": True},
                    "symbol": {
                        "dynamicRegistration": True,
                        "symbolKind": {"valueSet": list(range(1, 27))},
                    },
                    "configuration": True,
                },
            },
            "initializationOptions": {},
            "processId": os.getpid(),
            "workspaceFolders": [
                {
                    "uri": root_uri,
                    "name": os.path.basename(repository_absolute_path),
                }
            ],
        }
        return cast(InitializeParams, initialize_params)

    def _start_server(self) -> None:
        """
        Starts the BSL Language Server
        """

        def execute_client_command_handler(params: dict) -> list:
            return []

        def do_nothing(params: dict) -> None:
            return

        def window_log_message(msg: dict) -> None:
            log.info(f"LSP: window/logMessage: {msg}")

        self.server.on_request("client/registerCapability", do_nothing)
        self.server.on_notification("window/logMessage", window_log_message)
        self.server.on_request("workspace/executeClientCommand", execute_client_command_handler)
        self.server.on_notification("$/progress", do_nothing)
        self.server.on_notification("textDocument/publishDiagnostics", do_nothing)

        log.info("Starting BSL Language Server process")
        self.server.start()
        initialize_params = self._get_initialize_params(self.repository_root_path)

        log.info("Sending initialize request from LSP client to LSP server and awaiting response")
        init_response = self.server.send.initialize(initialize_params)

        capabilities = init_response["capabilities"]
        assert "textDocumentSync" in capabilities, "Server must support textDocumentSync"
        assert "definitionProvider" in capabilities, "Server must support go to definition"
        assert "referencesProvider" in capabilities, "Server must support find references"
        assert "documentSymbolProvider" in capabilities, "Server must support document symbols"

        self.server.notify.initialized({})
        self.completions_available.set()
