from pathlib import Path

ROOT = Path("project")

# Android phone/tablet GPUs share physical RAM with the OS. Treat all Android
# GPU allocations as host-memory pressure, even when the backend labels a Mali
# device as a discrete GPU.
bridge = ROOT / "native/src/bridge.cpp"
source = bridge.read_text()
old_memory = """// A card with its own memory (CUDA, Vulkan on a discrete GPU). Phone and
// Apple GPUs share the RAM, so what they take counts against the RAM.
static bool own_memory(ggml_backend_dev_t dev) {
#if defined(__APPLE__)
    (void)dev; return false;
#else
    return dev && ggml_backend_dev_type(dev) == GGML_BACKEND_DEVICE_TYPE_GPU;
#endif
}"""
new_memory = """// Android phone/tablet GPUs (including Vulkan devices reported as GPU rather
// than IGPU) share physical RAM with the OS. Never treat their allocations as
// separate VRAM in memory admission; they compete with SurfaceFlinger and apps.
static bool own_memory(ggml_backend_dev_t dev) {
#if defined(__ANDROID__) || defined(__APPLE__)
    (void)dev; return false;
#else
    return dev && ggml_backend_dev_type(dev) == GGML_BACKEND_DEVICE_TYPE_GPU;
#endif
}"""
if source.count(old_memory) != 1:
    raise SystemExit("Could not uniquely locate own_memory() for Android UMA correction")
bridge.write_text(source.replace(old_memory, new_memory, 1))

# Auto mode skips Mali Vulkan until its Android queue/driver path is validated.
# Explicit backend="vulkan" still forces the Vulkan bridge.
dart = ROOT / "lib/inference/ffi/llama_bindings.dart"
source = dart.read_text()
old_selection = """          if (preferred == null && name.contains('opencl') &&
              lib.providesSymbol('od_gpu_device_info_json')) {
            final info = lib
                .lookupFunction<Pointer<Utf8> Function(), Pointer<Utf8> Function()>(
                  'od_gpu_device_info_json',
                )()
                .toDartString();
            final devices = jsonDecode(info);
            final summary = devices is List
                ? devices
                    .map((device) => '${device['backend']} ${device['name']}')
                    .join(' ')
                    .toLowerCase()
                : '';
            // Prefer Vulkan for Mali/Immortalis when both Android variants
            // are present; OpenCL remains the automatic first choice for
            // Adreno, where its vendor-tuned kernels are the better path.
            if ((summary.contains('mali') || summary.contains('immortalis')) &&
                !summary.contains('adreno')) {
              skipped.add('$name: Mali/Immortalis detected; prefer Vulkan');
              continue;
            }
          }"""
new_selection = """          if (preferred == null && name.contains('vulkan') &&
              lib.providesSymbol('od_gpu_device_info_json')) {
            final info = lib
                .lookupFunction<Pointer<Utf8> Function(), Pointer<Utf8> Function()>(
                  'od_gpu_device_info_json',
                )()
                .toDartString();
            final devices = jsonDecode(info);
            final summary = devices is List
                ? devices
                    .map((device) => '${device['backend']} ${device['name']}')
                    .join(' ')
                    .toLowerCase()
                : '';
            // Mali Vulkan remains available when explicitly selected, but is
            // not auto-selected until its Android queue/driver path is validated.
            if (summary.contains('mali') || summary.contains('immortalis')) {
              skipped.add('$name: Mali Vulkan is experimental in Auto; select Vulkan explicitly to force it');
              continue;
            }
          }"""
if source.count(old_selection) != 1:
    raise SystemExit("Could not uniquely locate the existing Mali OpenCL/Vulkan auto-selection block")
dart.write_text(source.replace(old_selection, new_selection, 1))

print("Applied Android UMA accounting and Mali Vulkan Auto safety.")
