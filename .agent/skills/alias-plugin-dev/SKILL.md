---
name: alias-plugin-dev
description: Use when building, reviewing, compiling, or debugging Autodesk Alias OpenAlias C++ plugins in this repo; provides self-contained plugin patterns distilled from official examples and requires Autodesk Alias docs MCP lookup for exact API details.
---

# Alias Plugin Dev

Use this skill for Autodesk Alias/OpenAlias C++ plugin work in this repository.

This skill is intentionally self-contained. It was distilled from official Autodesk Alias plugin examples, but do not assume `Autodesk_Original_Files`, `ODS`, or experiment folders exist in a GitHub clone. If those files exist locally, they can be used as extra read-only reference, but they are not required.

## Core Rule

Do not build from memory alone. Use this skill for the standard plugin structure, then query the Autodesk Alias docs MCP server for exact class names, method signatures, return codes, and edge cases.

Preferred MCP lookups:

- `search_alias_docs` for discovery.
- `get_doc_by_title` for exact API pages.
- `get_code_examples` for class-specific examples when available.

If confidence is below 95% on behavior, target Alias version, menu placement, input selection, output objects, or build environment, ask a focused follow-up question before editing.

## Standard Workflow

1. Define the plugin type: momentary command, continuous interactive tool, option-box command, data import/export command, or history-related command.
2. Define inputs: picked objects, active window, file path, option-box values, or no input.
3. Define outputs: new geometry, modified DAG nodes, selected objects, files, prompt-line output, shaders/materials, or references.
4. Query the MCP docs for the involved API classes before coding.
5. Implement the smallest plugin that satisfies the behavior.
6. Add defensive `statusCode` checks and prompt/stdout diagnostics.
7. Build only in a Visual Studio x64 Native Tools environment or state that build was not run.
8. Test by unloading any old plugin, building, loading in Alias Plug-in Manager, running the command, and checking the prompt line/output.

## Plugin Architecture

An OpenAlias plugin is a DLL renamed to `.plugin`. It exports two C entry points:

- `plugin_init`: called when Alias loads the plugin.
- `plugin_exit`: called when Alias unloads the plugin.

The usual structure is:

```cpp
#include <AlUniverse.h>
#include <AlLiveData.h>
#include <AlFunction.h>
#include <AlFunctionHandle.h>

static AlFunctionHandle g_handle;
static AlMomentaryFunction g_function;

static void runPlugin(void)
{
    AlPrintf(kPrompt, "Plugin completed.");
}

extern "C" PLUGINAPI_DECL int plugin_init(const char* dirName)
{
    AlUniverse::initialize();

    if (g_function.create("pl_MyPlugin", runPlugin) != sSuccess) {
        AlPrintf(kPrompt, "Failed to create plugin function.");
        return 1;
    }

    if (g_handle.create("My Plugin", &g_function) != sSuccess) {
        AlPrintf(kPrompt, "Failed to create plugin handle.");
        return 1;
    }

    g_handle.setAttributeString("MyPlugin");
    g_handle.addToMenu("al_goto");

    AlPrintf(kPrompt, "My Plugin installed.");
    return 0;
}

extern "C" PLUGINAPI_DECL int plugin_exit(void)
{
    g_handle.removeFromMenu();
    g_handle.deleteObject();
    g_function.deleteObject();
    return 0;
}
```

Before finalizing, verify the exact signatures and return values against the MCP docs because Alias SDK versions can differ.

## Function Types

Use a momentary function for a menu/palette command that runs once:

```cpp
static AlMomentaryFunction g_function;
g_function.create("pl_CommandName", runCommand);
```

Use a continuous function for interactive tools that respond to mouse/keyboard events:

```cpp
static AlContinuousFunction g_function;
g_function.create(
    "pl_ToolName",
    initFunc,
    downFunc,
    moveFunc,
    upFunc,
    cleanupFunc,
    TRUE
);
```

For continuous tools, use the docs to verify event callback signatures and `AlContinuousFunction::translateInput` behavior before coding.

## Option Boxes

Use `AlEditor` when the command needs user-editable parameters.

Pattern:

```cpp
#include <AlEditor.h>

static AlEditor* g_editor = nullptr;
static int g_mode = 0;
static bool g_enableFeature = true;

static void modeChanged(int value)
{
    g_mode = value;
}

static void enableFeatureChanged(const bool value)
{
    g_enableFeature = value;
}

// In plugin_init, after handle creation:
g_editor = new AlEditor("My Plugin Options", "pl_MyPlugin");
g_editor->addRadio("Mode", "One:0,Two:1", g_mode, modeChanged);
g_editor->addCheckbox("Enable Feature", g_enableFeature, enableFeatureChanged);
g_editor->create();
g_handle.setOptionBox("My Plugin Options", "pl_MyPlugin");

// In plugin_exit:
delete g_editor;
g_editor = nullptr;
```

Always delete the editor in `plugin_exit`.

## Menu And Palette Attachment

Common IDs observed in Alias plugin patterns:

- `al_goto`: Utilities menu.
- `al_file`: File menu.
- `mp_objtools`: Object Edit palette.
- `mp_pick`: Pick palette.
- `mp_objdisplay`: Object Display menu/palette area.

Use docs/MCP lookup for exact IDs if attaching to other menus or palettes.

`addToMenu` appends to the menu. `appendToMenu` inserts near the top in some examples. Confirm behavior if menu order matters.

## Common API Patterns

Prompt/status output:

```cpp
AlPrintf(kPrompt, "Short user-facing result.");
AlPrintf(kStdout, "Debug detail: %d", value);
```

Initialize before using Alias API:

```cpp
AlUniverse::initialize();
```

Screen redraw after scene mutation:

```cpp
AlUniverse::redrawScreen();
```

Do not assume boolean redraw arguments are correct. Check the docs for redraw flags if custom redraw behavior is needed.

Pick-list iteration pattern:

```cpp
#include <AlPickList.h>
#include <AlIterator.h>

class PickIterator : public AlIterator {
public:
    int func(AlObject* object) override
    {
        if (!object) return 0;
        // Process object after converting to the required type.
        return 0;
    }
};

PickIterator iter;
int result = 0;
AlPickList::applyIteratorToItems(&iter, result);
```

DAG traversal pattern:

```cpp
for (AlDagNode* node = AlUniverse::firstDagNode(); node != nullptr; ) {
    AlDagNode* next = node->nextNode();
    // Process node.
    delete node;
    node = next;
}
```

Geometry operations usually need a wrapper object plus a DAG node object, for example curve/surface classes and their node classes. Always verify ownership and deletion rules in the docs for the specific class.

## Typical Class Lookup Map

Use these class names as MCP search starting points:

- Plugin lifecycle/UI: `AlUniverse`, `AlFunction`, `AlFunctionHandle`, `AlMomentaryFunction`, `AlContinuousFunction`, `AlEditor`, `AlStatusHandler`.
- Scene graph: `AlObject`, `AlDagNode`, `AlGroupNode`, `AlIterator`, `AlPickList`, `AlPickable`.
- Curves: `AlCurve`, `AlCurveNode`, `AlCurveCV`, `AlCurvePoint`.
- Surfaces/trims: `AlSurface`, `AlSurfaceNode`, `AlSurfaceCV`, `AlSurfacePoint`, `AlCurveOnSurface`, `AlTrimRegion`, `AlTrimBoundary`, `AlTrimCurve`.
- Mesh/polyset: `AlMesh`, `AlMeshNode`, `AlPolyset`, `AlPolysetNode`, `AlPolygon`, `AlPolysetVertex`.
- Analysis: `AlMeasure`, `AlIntersect`, `AlTesselate`.
- Data/reference: `AlBlindData`, `AlReferenceFile`, `AlReferenceFileSet`, `AlReferenceUpdate`.
- Rendering/materials: `AlShader`, `AlTexture`, `AlLayer`, `AlLight`, `AlCamera`.

## Build Pattern

Typical Windows plugin build uses Visual Studio C++ tools and Alias libraries:

```bat
cl.exe -c /nologo /MD /EHsc /W3 /I"C:\Program Files\Autodesk\Alias<version>\ODS\Common\include" MyPlugin.cpp
link.exe /nologo /DLL /opt:noref /incremental:no "C:\Program Files\Autodesk\Alias<version>\lib\libAliasCore.lib" user32.lib gdi32.lib /out:MyPlugin.plugin MyPlugin.obj
```

Adjust `Alias<version>` to the installed product/version. If the user has Alias 2026, do not hard-code Alias 2025 paths.

For standalone OpenModel executables, use `libalias_api.lib` instead of `libAliasCore.lib` and build as a console executable, not a `.plugin` DLL.

## Quality Checklist

Before finishing plugin work:

- Confirm the plugin type and menu/palette location.
- Confirm the required selected object types and behavior when nothing is selected.
- Confirm all relevant API signatures with the MCP docs.
- Check `statusCode` returns for create/mutate operations.
- Use `AlPrintf(kPrompt, ...)` for user-facing completion/errors.
- Use `AlPrintf(kStdout, ...)` for debug details.
- Clean up handles, functions, editors, and wrapper objects according to docs.
- Do not write generated code or build artifacts into Autodesk-provided folders.
- If the plugin is loaded in Alias, unload it before rebuilding to avoid locked output files.

## Optional Local References

If a developer has Autodesk ODS examples locally, use them only as read-only supplementary reference. The skill must remain useful without them. Good examples to look for by filename are `resetTransforms.cpp`, `continuousFuncExample.cpp`, `pick.cpp`, `calcDistanceExample.cpp`, `intersectionExample.cpp`, `blindData.cpp`, and OpenModel examples for curve/surface creation.