from pathlib import Path

import pytest

from solidlsp import SolidLanguageServer
from solidlsp.ls_config import Language


@pytest.mark.bsl
class TestBSLLanguageServer:
    @pytest.mark.parametrize("language_server", [Language.BSL], indirect=True)
    @pytest.mark.parametrize("repo_path", [Language.BSL], indirect=True)
    def test_ls_is_running(self, language_server: SolidLanguageServer, repo_path: Path) -> None:
        """Test that the language server starts and stops successfully."""
        # The fixture already handles start and stop
        assert language_server.is_running()
        assert Path(language_server.language_server.repository_root_path).resolve() == repo_path.resolve()

    @pytest.mark.parametrize("language_server", [Language.BSL], indirect=True)
    @pytest.mark.parametrize("repo_path", [Language.BSL], indirect=True)
    def test_find_document_symbols(self, language_server: SolidLanguageServer, repo_path: Path) -> None:
        """Test that the language server can find document symbols."""
        # Get document symbols for main.bsl
        main_bsl_path = str(repo_path / "main.bsl")
        document_symbols = language_server.request_document_symbols(main_bsl_path)

        # Should find symbols: Greet function, Add function, Main procedure
        all_symbols, root_symbols = document_symbols.get_all_symbols_and_roots()
        assert len(root_symbols) >= 1, f"Expected at least 1 root symbol but got {len(root_symbols)}"

        # Check that expected symbol names are present
        symbol_names = [s["name"] for s in all_symbols]
        assert any("Greet" in name for name in symbol_names), f"Expected 'Greet' function in symbols, got: {symbol_names}"

    @pytest.mark.parametrize("language_server", [Language.BSL], indirect=True)
    @pytest.mark.parametrize("repo_path", [Language.BSL], indirect=True)
    def test_find_definition_within_file(self, language_server: SolidLanguageServer, repo_path: Path) -> None:
        """Test that the language server can find definitions within a file."""
        main_bsl_path = str(repo_path / "main.bsl")

        # In main.bsl:
        # Line 14 (0-indexed: 13): Greeting = Greet(UserName);
        # Find definition of Greet function (defined on line 4, 0-indexed: 3)
        # Position on "Greet" in the call (after "Greeting = ")
        definition_location_list = language_server.request_definition(main_bsl_path, 13, 16)

        assert definition_location_list, f"Expected non-empty definition_location_list but got {definition_location_list=}"
        assert len(definition_location_list) >= 1
        definition_location = definition_location_list[0]
        assert definition_location["uri"].endswith("main.bsl")
        # Definition of Greet function should be on line 4 (0-indexed: 3)
        assert definition_location["range"]["start"]["line"] == 3

    @pytest.mark.parametrize("language_server", [Language.BSL], indirect=True)
    @pytest.mark.parametrize("repo_path", [Language.BSL], indirect=True)
    def test_find_references_within_file(self, language_server: SolidLanguageServer, repo_path: Path) -> None:
        """Test that the language server can find references within a file."""
        main_bsl_path = str(repo_path / "main.bsl")

        # Find references for Greet function
        # Greet is defined on line 4 (0-indexed: 3), character 9 (on the 'G')
        references = language_server.request_references(main_bsl_path, 3, 9)

        assert references, f"Expected non-empty references for Greet but got {references=}"
        # Should find at least one reference (the call on line 14)
        assert len(references) >= 1, f"Expected at least 1 reference for Greet but got {len(references)}"

        # Verify that one of the references is in main.bsl
        main_bsl_refs = [r for r in references if r["uri"].endswith("main.bsl")]
        assert len(main_bsl_refs) >= 1, f"Expected at least 1 reference in main.bsl but got {len(main_bsl_refs)}"
