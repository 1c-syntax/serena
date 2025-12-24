"""
Provides BSL (1C:Enterprise) specific instantiation of the LanguageServer class.
Contains various configurations and settings specific to BSL Language Server.

BSL Language Server is an open-source language server for 1C:Enterprise 8 and OneScript.
See: https://github.com/1c-syntax/bsl-language-server

The language server is automatically downloaded from GitHub releases as a platform-specific
ZIP file that includes a bundled runtime, so no separate Java installation is required.
The latest stable version is detected automatically via GitHub API.

You can configure the following options in ls_specific_settings (in serena_config.yml):

    ls_specific_settings:
      bsl:
        ls_executable_path: '/path/to/bsl-language-server'  # Path to custom BSL LS executable
        configuration_path: '/path/to/.bsl-language-server.json'  # Optional: BSL LS config file

Example configuration:

    ls_specific_settings:
      bsl:
        configuration_path: '/home/user/project/.bsl-language-server.json'
"""

import dataclasses
import logging
import os
import pathlib
import stat
from typing import cast

import requests
from overrides import override

from solidlsp.ls import SolidLanguageServer
from solidlsp.ls_config import Language, LanguageServerConfig
from solidlsp.ls_utils import FileUtils, PlatformUtils
from solidlsp.lsp_protocol_handler.lsp_types import InitializeParams
from solidlsp.lsp_protocol_handler.server import ProcessLaunchInfo
from solidlsp.settings import SolidLSPSettings

log = logging.getLogger(__name__)


# BSL Language Server GitHub repository info
BSL_LS_GITHUB_ORG = "1c-syntax"
BSL_LS_GITHUB_REPO = "bsl-language-server"
# Fallback version if GitHub API is unavailable
BSL_LS_FALLBACK_VERSION = "0.25.2"


def _get_latest_bsl_ls_version() -> str:
    """
    Fetches the latest stable release version from GitHub API.
    Returns the version tag (e.g., "v0.25.2") or falls back to a hardcoded version if API is unavailable.
    """
    try:
        response = requests.get(
            f"https://api.github.com/repos/{BSL_LS_GITHUB_ORG}/{BSL_LS_GITHUB_REPO}/releases/latest",
            headers={"Accept": "application/vnd.github.v3+json", "User-Agent": "Serena-SolidLSP"},
            timeout=10,
        )
        if response.status_code == 200:
            release_info = response.json()
            tag_name = release_info.get("tag_name", "")
            if tag_name:
                log.info(f"Detected latest BSL Language Server version: {tag_name}")
                return tag_name
    except Exception as e:
        log.warning(f"Could not fetch latest BSL LS version from GitHub API: {e}")

    log.info(f"Using fallback BSL Language Server version: v{BSL_LS_FALLBACK_VERSION}")
    return f"v{BSL_LS_FALLBACK_VERSION}"


def _get_download_url(version: str, platform_key: str) -> str:
    """
    Constructs the download URL for a specific version and platform.
    """
    return f"https://github.com/{BSL_LS_GITHUB_ORG}/{BSL_LS_GITHUB_REPO}/releases/download/{version}/bsl-language-server_{platform_key}.zip"


@dataclasses.dataclass
class BSLRuntimeDependencyPaths:
    """
    Stores the paths to the runtime dependencies of BSL Language Server
    """

    executable_path: str


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
            self.runtime_dependency_paths.executable_path,
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

        super().__init__(
            config,
            repository_root_path,
            ProcessLaunchInfo(cmd=cmd, cwd=repository_root_path),
            "bsl",
            solidlsp_settings,
        )

    @classmethod
    def _setup_runtime_dependencies(cls, solidlsp_settings: SolidLSPSettings) -> BSLRuntimeDependencyPaths:
        """
        Setup runtime dependencies for BSL Language Server and return paths.
        Downloads platform-specific ZIP from GitHub releases if not already installed.
        Automatically detects the latest version via GitHub API.
        """
        platform_id = PlatformUtils.get_platform_id()

        # Verify platform support and determine platform key for download
        if platform_id.value.startswith("win-"):
            platform_key = "win"
            executable_name = "bsl-language-server.exe"
        elif platform_id.value.startswith("linux-"):
            platform_key = "nix"
            executable_name = "bsl-language-server"
        elif platform_id.value.startswith("osx-"):
            platform_key = "mac"
            executable_name = "bsl-language-server"
        else:
            raise AssertionError("Only Windows, Linux and macOS platforms are supported for BSL in SolidLSP at the moment")

        # Check if user specified custom executable path
        if solidlsp_settings and solidlsp_settings.ls_specific_settings:
            bsl_settings = solidlsp_settings.get_ls_specific_settings(Language.BSL)
            custom_executable = bsl_settings.get("ls_executable_path")
            if custom_executable:
                if os.path.exists(custom_executable):
                    log.info(f"Using custom BSL LS executable from configuration: {custom_executable}")
                    return BSLRuntimeDependencyPaths(executable_path=custom_executable)
                else:
                    log.warning(f"Configured BSL LS executable path does not exist: {custom_executable}")

        # Get latest version from GitHub API
        version = _get_latest_bsl_ls_version()

        # Setup directory for BSL Language Server
        static_dir = os.path.join(cls.ls_resources_dir(solidlsp_settings), "bsl_language_server")
        os.makedirs(static_dir, exist_ok=True)

        # Path to the extracted BSL LS directory
        # ZIP extracts with different structure per platform:
        # - Windows: bsl-language-server/bsl-language-server.exe
        # - Linux: bsl-language-server/bin/bsl-language-server
        # - macOS: bsl-language-server.app/Contents/MacOS/bsl-language-server
        bsl_ls_dir = os.path.join(static_dir, f"bsl-language-server-{version}")

        if platform_key == "win":
            executable_path = os.path.join(bsl_ls_dir, "bsl-language-server", executable_name)
        elif platform_key == "nix":
            executable_path = os.path.join(bsl_ls_dir, "bsl-language-server", "bin", executable_name)
        else:  # mac
            executable_path = os.path.join(bsl_ls_dir, "bsl-language-server.app", "Contents", "MacOS", executable_name)

        # Download and extract if not already present
        if not os.path.exists(executable_path):
            download_url = _get_download_url(version, platform_key)
            log.info(f"Downloading BSL Language Server {version} for {platform_key}...")
            FileUtils.download_and_extract_archive(download_url, bsl_ls_dir, "zip")

            # Make executable on Unix platforms
            if not platform_id.value.startswith("win-") and os.path.exists(executable_path):
                os.chmod(
                    executable_path,
                    stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR | stat.S_IRGRP | stat.S_IXGRP | stat.S_IROTH | stat.S_IXOTH,
                )

        assert os.path.exists(executable_path), f"BSL Language Server executable not found at {executable_path}"

        return BSLRuntimeDependencyPaths(executable_path=executable_path)

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
