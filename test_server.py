"""Regression checks for the V2 Autodesk Alias documentation MCP server."""

import json

from server.mcp_server_v2 import (
    get_chunk_search_index,
    get_code_examples,
    get_doc_by_title,
    get_docs,
    list_available_docs,
    search_alias_docs,
    search_code_examples,
    search_docs,
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


def test_get_doc_by_title() -> None:
    """Verify the full-doc lookup still returns the requested page."""
    output = get_doc_by_title("AlCurve")
    _assert(output.startswith("# AlCurve"), "Expected AlCurve document header")
    _assert("**URL:**" in output, "Expected formatted URL in document output")
    _assert("Interface to Alias NURBS curves geometry." in output, "Expected AlCurve content in output")


def test_code_example_search() -> None:
    """Verify the code-focused retrieval path favors example pages."""
    docs = get_docs()

    plug_in_results = search_code_examples("plug-in", docs, max_results=5)
    _assert(plug_in_results, 'Expected code example results for "plug-in"')
    _assert(
        plug_in_results[0]["title"] == "Attaching a plug-in to a menu or palette",
        (
            'Expected top code example result "Attaching a plug-in to a menu or palette" '
            f'for "plug-in", got "{plug_in_results[0]["title"]}"'
        ),
    )
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
    _assert("Attaching a plug-in to a menu or palette" in output, "Expected known plug-in code page in output")
    _assert("```" in output, "Expected fenced code block in output")


def test_json_outputs() -> None:
    """Verify the optional JSON response mode for all exposed tools."""
    search_payload = json.loads(search_alias_docs("Mouse Move", response_format="json"))
    _assert(search_payload["query"] == "Mouse Move", "Expected search query in JSON payload")
    _assert(search_payload["count"] >= 1, "Expected search result count in JSON payload")
    _assert(search_payload["results"][0]["title"] == "Momentary, Continuous and History plug-ins", "Expected top JSON search result")

    code_payload = json.loads(get_code_examples("plug-in", response_format="json"))
    _assert(code_payload["topic"] == "plug-in", "Expected code example topic in JSON payload")
    _assert(code_payload["results"][0]["title"] == "Attaching a plug-in to a menu or palette", "Expected top JSON code result")
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


def main() -> None:
    """Run the regression suite as a standalone script."""
    test_load_and_index()
    print("PASS test_load_and_index")

    test_search_rankings()
    print("PASS test_search_rankings")

    test_get_doc_by_title()
    print("PASS test_get_doc_by_title")

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

    print("All V2 regression checks passed.")


if __name__ == "__main__":
    main()
