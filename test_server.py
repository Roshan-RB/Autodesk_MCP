"""Regression checks for the Autodesk Alias documentation MCP server."""

import json
from pathlib import Path

from server.mcp_server import (
    SERVER_INSTRUCTIONS,
    get_chunk_search_index,
    get_code_examples,
    get_doc_by_title,
    get_docs,
    list_available_docs,
    normalize_loaded_doc_content,
    search_alias_docs,
    search_code_examples,
    search_docs,
    mcp,
)


def _assert(condition: bool, message: str) -> None:
    """Raise a descriptive assertion error."""
    if not condition:
        raise AssertionError(message)


def _assert_top_result(query: str, expected_title: str, expected_section: str | None = None) -> None:
    """Run a search query and validate the top-ranked result."""
    results = search_docs(query, get_docs(), max_results=5)
    _assert(results, f'Expected search results for "{query}"')

    top_result = results[0]
    _assert(
        top_result["title"] == expected_title,
        f'Expected top result "{expected_title}" for "{query}", got "{top_result["title"]}"',
    )

    if expected_section is not None:
        _assert(
            top_result.get("section_title") == expected_section,
            (
                f'Expected top section "{expected_section}" for "{query}", '
                f'got "{top_result.get("section_title")}"'
            ),
        )


def _assert_any_title(results: list[dict], expected_titles: set[str], context: str) -> None:
    """Verify that at least one result title is in an expected title set."""
    result_titles = [result["title"] for result in results]
    _assert(
        any(title in expected_titles for title in result_titles),
        f"Expected one of {sorted(expected_titles)} for {context}, got {result_titles}",
    )


PLUGIN_EXAMPLE_TITLES = {
    "Attaching a plug-in to a menu or palette",
    "Command history plug-in example",
    "Momentary plug-in example",
    "Continuous plug-in example",
    "Reference Data plug-in example",
}

EXPECTED_WEBSITE_TOC_TITLES = {
    "Alias Programmers' Interfaces (API)",
    "AlCanvas",
    "AlLinkItemT, AlListT",
    "AlModelTool",
    "AlToolMeshFromNurbs",
    "AlToolMeshMerge",
    "AlToolStitch",
}


def test_seed_index_coverage() -> None:
    """Verify the committed seed manifest includes known website TOC pages."""
    index_path = Path(__file__).parent / "data" / "docs" / "index.json"
    index_payload = json.loads(index_path.read_text(encoding="utf-8"))
    pages = index_payload["pages"]
    titles = [page["title"] for page in pages]
    missing_titles = EXPECTED_WEBSITE_TOC_TITLES - set(titles)

    _assert(not missing_titles, f"Missing expected TOC titles: {sorted(missing_titles)}")
    _assert(len(titles) == len(set(titles)), "Expected unique titles in seed index")
    _assert(index_payload["total_pages"] == len(pages), "Expected total_pages to match pages length")


def test_server_instructions() -> None:
    """Verify MCP initialization exposes usage guidance to clients."""
    _assert(mcp.instructions == SERVER_INSTRUCTIONS, "Expected FastMCP instructions to be configured")
    _assert("Autodesk Alias Programmers' Interfaces" in SERVER_INSTRUCTIONS, "Expected Alias docs scope")
    _assert("search_alias_docs" in SERVER_INSTRUCTIONS, "Expected search workflow guidance")
    _assert("get_doc_by_title" in SERVER_INSTRUCTIONS, "Expected full-doc workflow guidance")
    _assert("get_code_examples" in SERVER_INSTRUCTIONS, "Expected code-example workflow guidance")


def test_load_and_index() -> None:
    """Verify docs load and the chunk index builds."""
    docs = get_docs()
    index = get_chunk_search_index(docs)

    _assert(len(docs) >= 200, f"Expected at least 200 docs, found {len(docs)}")
    _assert(index["chunk_count"] > len(docs), "Expected more chunks than documents")
    _assert(index["avg_doc_len"] > 0, "Expected a positive average chunk length")


def test_search_rankings() -> None:
    """Protect the key query regressions we have already validated manually."""
    _assert_top_result("Mouse Move", "Momentary, Continuous and History plug-ins", "Mouse Move")
    _assert_top_result("doUpdates FALSE", "Making your code run faster", "Making your code run faster")
    _assert_top_result("AlCurve", "AlCurve", "AlCurve")
    _assert_top_result("Adding your plug-in to the UI", "Adding your plug-in to the UI")


def test_search_followup_guidance() -> None:
    """Verify discovery search tells agents how to fetch complete pages."""
    output = search_alias_docs("plug-in", max_results=2)
    _assert("## Next step" in output, "Expected next-step guidance in markdown search output")
    _assert("get_doc_by_title" in output, "Expected full-page retrieval guidance")
    _assert("get_code_examples" in output, "Expected code-block retrieval guidance")
    _assert("Suggested exact titles:" in output, "Expected exact-title suggestions")


def test_get_doc_by_title() -> None:
    """Verify the full-doc lookup still returns the requested page."""
    output = get_doc_by_title("AlCurve")
    _assert(output.startswith("# AlCurve"), "Expected AlCurve document header")
    _assert("**URL:**" in output, "Expected formatted URL in document output")
    _assert("Interface to Alias NURBS curves geometry." in output, "Expected AlCurve content in output")


def test_loaded_doc_content_cleanup() -> None:
    """Verify stale scraped page chrome is removed before docs are indexed."""
    doc = {
        "title": "AlModelTool",
        "content": (
            "Alias 2026 Help | AlModelTool | Autodesk\n"
            "===============\n\n"
            "*   [Help Home](https://help.autodesk.com/view/ALIAS/2026/ENU/)\n"
            "Quick Links\n"
        ),
        "raw_content": (
            "Alias 2026 Help | AlModelTool | Autodesk\n"
            "===============\n\n"
            "*   [Help Home](https://help.autodesk.com/view/ALIAS/2026/ENU/)\n"
            "Quick Links\n\n"
            "Share\n\n"
            "AlModelTool\n"
            "===========\n\n"
            "Base class for all model tools.\n\n"
            "Share\n\n"
            "*   [Email](mailto:test)\n"
        ),
    }

    normalize_loaded_doc_content(doc)

    _assert(doc["content"].startswith("AlModelTool"), "Expected cleaned content to start at real page heading")
    _assert("Base class for all model tools." in doc["content"], "Expected useful body content after cleanup")
    _assert("Help Home" not in doc["content"], "Expected Help Home navigation to be removed")
    _assert("Quick Links" not in doc["content"], "Expected Quick Links navigation to be removed")


def test_code_example_search() -> None:
    """Verify the code-focused retrieval path favors example pages."""
    docs = get_docs()

    plug_in_results = search_code_examples("plug-in", docs, max_results=5)
    _assert(plug_in_results, 'Expected code example results for "plug-in"')
    _assert_any_title(plug_in_results, PLUGIN_EXAMPLE_TITLES, '"plug-in" code search')
    _assert(plug_in_results[0].get("code_snippet"), "Expected a code snippet for plug-in results")

    history_results = search_code_examples("history plug-ins", docs, max_results=5)
    _assert(history_results, 'Expected code example results for "history plug-ins"')
    _assert(
        history_results[0]["title"] == "Command history plug-in example",
        (
            'Expected top code example result "Command history plug-in example" '
            f'for "history plug-ins", got "{history_results[0]["title"]}"'
        ),
    )


def test_get_code_examples() -> None:
    """Verify the MCP-facing code example tool output shape."""
    output = get_code_examples("plug-in")
    _assert("Found" in output and "code example results" in output, "Expected code example header")
    _assert(
        any(title in output for title in PLUGIN_EXAMPLE_TITLES),
        "Expected a known plug-in code page in output",
    )
    _assert("```" in output, "Expected fenced code block in output")

    exact_title_output = get_code_examples("Attaching a plug-in to a menu or palette")
    _assert(
        "## 1. Attaching a plug-in to a menu or palette [code]" in exact_title_output,
        "Expected exact page-title query to rank the matching page first",
    )
    _assert(
        'h.installOnMenu( "al_goto", FALSE /* top */ );' in exact_title_output,
        "Expected exact page-title query to include menu attachment code",
    )
    _assert(
        "Removing the plug-in from the menus at plugin_exit() time:" in exact_title_output,
        "Expected exact page-title query to include nearby context for later code blocks",
    )

    momentary_output = get_code_examples("Momentary plug-in example", max_results=1)
    _assert("## 1. Momentary plug-in example [code]" in momentary_output, "Expected momentary example first")
    _assert("PLUGINAPI_DECL int plugin_init( const char *dirName )" in momentary_output, "Expected full plugin_init code")
    _assert("PLUGINAPI_DECL int plugin_exit( void )" in momentary_output, "Expected full plugin_exit code")


def test_json_outputs() -> None:
    """Verify the optional JSON response mode for all exposed tools."""
    search_payload = json.loads(search_alias_docs("Mouse Move", response_format="json"))
    _assert(search_payload["query"] == "Mouse Move", "Expected search query in JSON payload")
    _assert(search_payload["count"] >= 1, "Expected search result count in JSON payload")
    _assert(search_payload["results"][0]["title"] == "Momentary, Continuous and History plug-ins", "Expected top JSON search result")
    _assert("next_step" in search_payload, "Expected JSON search payload to include next_step guidance")
    _assert(search_payload["next_step"]["suggested_titles"], "Expected JSON next_step to include suggested titles")

    code_payload = json.loads(get_code_examples("plug-in", response_format="json"))
    _assert(code_payload["topic"] == "plug-in", "Expected code example topic in JSON payload")
    _assert(
        code_payload["results"][0]["title"] in PLUGIN_EXAMPLE_TITLES,
        "Expected top JSON code result to be a known plug-in example page",
    )
    _assert(code_payload["results"][0]["code_snippet"], "Expected code snippet in JSON code result")

    list_payload = json.loads(list_available_docs(response_format="json"))
    _assert(list_payload["total_count"] >= 200, "Expected total doc count in JSON list payload")
    _assert(any(doc["title"] == "AlCurve" for doc in list_payload["docs"]), "Expected AlCurve in JSON list payload")

    doc_payload = json.loads(get_doc_by_title("AlCurve", response_format="json"))
    _assert(doc_payload["found"] is True, "Expected found=true for JSON doc lookup")
    _assert(doc_payload["doc"]["title"] == "AlCurve", "Expected AlCurve JSON doc title")
    _assert("Interface to Alias NURBS curves geometry." in doc_payload["doc"]["content"], "Expected AlCurve content in JSON doc payload")


def test_invalid_response_format() -> None:
    """Verify tool validation for unsupported response formats."""
    message = get_code_examples("plug-in", response_format="xml")
    _assert("Invalid response_format" in message, "Expected invalid response format validation message")


def test_list_available_docs() -> None:
    """Verify the doc listing still renders class and guide sections."""
    output = list_available_docs()
    _assert("Available documentation pages" in output, "Expected list header")
    _assert("### Class Reference" in output, "Expected class section")
    _assert("### Guides & Concepts" in output, "Expected guide section")
    _assert("**AlCurve**" in output, "Expected AlCurve in class listing")

    payload = json.loads(list_available_docs(response_format="json"))
    docs_by_title = {doc["title"]: doc for doc in payload["docs"]}
    _assert(docs_by_title["AlCurve"]["category"] == "class", "Expected AlCurve to be classified as class")
    _assert(
        docs_by_title["Allocation of Input Values"]["category"] == "guide",
        "Expected Allocation of Input Values to be classified as guide",
    )
    if "Alias Programmers' Interfaces (API)" in docs_by_title:
        _assert(
            docs_by_title["Alias Programmers' Interfaces (API)"]["category"] == "guide",
            "Expected Alias Programmers' Interfaces (API) to be classified as guide",
        )


def main() -> None:
    """Run the regression suite as a standalone script."""
    test_seed_index_coverage()
    print("PASS test_seed_index_coverage")

    test_server_instructions()
    print("PASS test_server_instructions")

    test_load_and_index()
    print("PASS test_load_and_index")

    test_search_rankings()
    print("PASS test_search_rankings")

    test_search_followup_guidance()
    print("PASS test_search_followup_guidance")

    test_get_doc_by_title()
    print("PASS test_get_doc_by_title")

    test_loaded_doc_content_cleanup()
    print("PASS test_loaded_doc_content_cleanup")

    test_code_example_search()
    print("PASS test_code_example_search")

    test_get_code_examples()
    print("PASS test_get_code_examples")

    test_json_outputs()
    print("PASS test_json_outputs")

    test_invalid_response_format()
    print("PASS test_invalid_response_format")

    test_list_available_docs()
    print("PASS test_list_available_docs")

    print("All regression checks passed.")


if __name__ == "__main__":
    main()
