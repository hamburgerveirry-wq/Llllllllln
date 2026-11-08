from pathlib import Path

bridge = Path("project/native/src/bridge.cpp")
source = bridge.read_text()
a = source.index("static bool own_memory(ggml_backend_dev_t dev) {")
b = source.index("\n}", a) + 2
replacement = "\n".join([
    "static bool own_memory(ggml_backend_dev_t dev) {",
    "#if defined(__APPLE__) || defined(__ANDROID__)",
    "    // Android GPUs share system RAM; do not count Mali/Dimensity memory",
    "    // as separate VRAM when estimating safe model placement.",
    "    (void)dev; return false;",
    "#else",
    "    return dev && ggml_backend_dev_type(dev) == GGML_BACKEND_DEVICE_TYPE_GPU;",
    "#endif",
    "}",
])
source = source[:a] + replacement + source[b:]

token = 'const bool explicit_backend = requested != "auto"'
if "unsafe_mali_vulkan" not in source:
    idx = source.index(token)
    line_start = source.rfind("\n", 0, idx) + 1
    indent = source[line_start:idx]
    lines = [
        "const std::string description = ggml_backend_dev_description(dev);",
        "std::string lower_description = description;",
        "std::transform(lower_description.begin(), lower_description.end(),",
        "    lower_description.begin(), ::tolower);",
        "#if defined(__ANDROID__)",
        "// Block the known-risk Mali Vulkan path until driver stability is verified.",
        'const bool unsafe_mali_vulkan = lower == "vulkan"',
        '    && (lower_description.find("mali") != std::string::npos',
        '        || lower_description.find("immortalis") != std::string::npos);',
        "if (unsafe_mali_vulkan) {",
        '    if (requested == "auto") {',
        '        if (skipped.empty()) skipped = "Vulkan (Mali safety block)";',
        "        continue;",
        "    }",
        '    if (requested == "vulkan") throw std::runtime_error(',
        '        "Vulkan is temporarily blocked on Mali/Immortalis to protect device stability. Select Auto or CPU.");',
        "}",
        "#endif",
    ]
    block = "\n".join(indent + line for line in lines) + "\n"
    source = source[:line_start] + block + source[line_start:]
bridge.write_text(source)

page = Path("project/lib/features/hosting/presentation/device_hosting_page.dart")
source = page.read_text()
import_line = "import '../../../core/l10n/l10n.dart';"
shared_import = "import '../../../core/providers/shared_providers.dart';"
if shared_import not in source:
    if import_line not in source:
        raise SystemExit("Could not locate hosting page imports")
    source = source.replace(import_line, import_line + "\n" + shared_import, 1)

first = source.index("    final state = ref.watch(deviceHostingProvider);")
last_line = "    final controller = ref.read(deviceHostingProvider.notifier);"
last = source.index(last_line, first) + len(last_line)
state_lines = [
    "    final state = ref.watch(deviceHostingProvider);",
    "    final manager = ref.watch(modelManagerProvider);",
    "    final model = manager.loadedModel;",
    "    final engine = ref.read(llamaEngineProvider);",
    "    final canStart = model != null && engine.isLoaded && !manager.isLoadingModel;",
    "    final controller = ref.read(deviceHostingProvider.notifier);",
]
source = source[:first] + "\n".join(state_lines) + source[last:]

old_button = "\n".join([
    "                                : model == null",
    "                                    ? null",
    "                                    : () =>",
    "                                          controller.start(port: _defaultPort),",
])
new_button = "\n".join([
    "                                : !canStart",
    "                                    ? null",
    "                                    : () =>",
    "                                          controller.start(port: _defaultPort),",
])
if old_button in source:
    source = source.replace(old_button, new_button, 1)
elif new_button not in source:
    raise SystemExit("API Start button pattern was not found")

old_note = "\n".join([
    "                    const SizedBox(height: AppDesign.sm),",
    "                    Text(",
    "                      'Uses the currently loaded model. The server is limited to your local network; it is not exposed as a public internet API.',",
])
new_note = "\n".join([
    "                    if (!state.running && !state.starting) ...[",
    "                      const SizedBox(height: AppDesign.sm),",
    "                      Text(",
    "                        model == null",
    "                            ? 'Load a model from this app before starting the API server.'",
    "                            : !engine.isLoaded",
    "                                ? 'The model is listed as loaded, but its inference engine is not ready yet. Reload the model before starting the server.'",
    "                                : manager.isLoadingModel",
    "                                    ? 'Wait for model loading to finish.'",
    "                                    : 'The local model is ready to serve.',",
    "                        style: context.text.bodyMuted,",
    "                      ),",
    "                    ],",
    "                    const SizedBox(height: AppDesign.sm),",
    "                    Text(",
    "                      'Uses the currently loaded model. The server is limited to your local network; it is not exposed as a public internet API.',",
])
if old_note in source:
    source = source.replace(old_note, new_note, 1)
elif new_note not in source:
    raise SystemExit("API readiness hint insertion point was not found")
page.write_text(source)
print("Applied Android UMA accounting, Mali Vulkan safety block, and API readiness gating.")
