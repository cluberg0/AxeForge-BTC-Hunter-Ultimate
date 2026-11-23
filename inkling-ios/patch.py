#!/usr/bin/env python3
"""Adapt official llama.cpp SwiftUI app to InklingRunner with no vendored engine."""
import sys
from pathlib import Path

root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path("llama-src").resolve()
example = root / "examples" / "llama.swiftui" / "llama.swiftui"
lib = root / "examples" / "llama.swiftui" / "llama.cpp.swift" / "LibLlama.swift"

def patch(path, changes):
    src = path.read_text(encoding="utf-8")
    for before, after in changes:
        occurrences = src.count(before)
        if occurrences != 1:
            raise RuntimeError(f"{path}: upstream code changed ({occurrences} matches for {before[:70]!r})")
        src = src.replace(before, after, 1)
    path.write_text(src, encoding="utf-8")
    print("Updated", path)

patch(lib, [
    ("let model = llama_model_load_from_file(path, model_params)", """
        // CPU mode saves GPU-side buffers; Metal toggle applies to next load.
        model_params.n_gpu_layers = UserDefaults.standard.bool(forKey: "inkling_use_gpu") ? 99 : 0
        let model = llama_model_load_from_file(path, model_params)""".strip("\n")),
    ("ctx_params.n_ctx = 2048", """ctx_params.n_ctx = 512
        ctx_params.n_batch = 128
        ctx_params.n_ubatch = 32"""),
])
patch(example / "UI" / "ContentView.swift", [
    ('@State private var multiLineText = ""', '''@State private var multiLineText = ""
    @AppStorage("inkling_use_gpu") private var useMetal = false'''),
    ('Button("Send")', 'Button("Отправить")'),
    ('Button("Bench")', 'Button("Тест")'),
    ('Button("Clear")', 'Button("Очистить")'),
    ('Button("Copy")', 'Button("Копировать")'),
    ('Text("View Models")', 'Text("Модели и загрузки")'),
    ('''                NavigationLink(destination: DrawerView(llamaState: llamaState)) {''',
     '''                Toggle("Metal GPU (нужна дополнительная память)", isOn: $useMetal)
                    .font(.footnote)
                LoadCustomButton(llamaState: llamaState)
                NavigationLink(destination: DrawerView(llamaState: llamaState)) {'''),
    ('.navigationBarTitle("Model Settings", displayMode: .inline)\n\n        }',
     '.navigationBarTitle("InklingRunner", displayMode: .inline)\n\n        }'),
])
patch(example / "UI" / "LoadCustomButton.swift", [
    ('Text("Load Custom Model")', 'Text("Импортировать GGUF из Файлов")'),
    ('''                    let gotAccess = file.startAccessingSecurityScopedResource()
                    if !gotAccess { return }

                    do {
                        try llamaState.loadModel(modelUrl: file.absoluteURL)
                    } catch let err {
                        print("Error: \(err.localizedDescription)")
                    }

                    file.stopAccessingSecurityScopedResource()''',
    '''                    let scoped = file.startAccessingSecurityScopedResource()
                    defer { if scoped { file.stopAccessingSecurityScopedResource() } }
                    do {
                        // Copy from security-scoped URL for persistent mmap access.
                        let documents = FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0]
                        let destination = documents.appendingPathComponent(file.lastPathComponent)
                        if !FileManager.default.fileExists(atPath: destination.path) {
                            try FileManager.default.copyItem(at: file, to: destination)
                        }
                        try llamaState.loadModel(modelUrl: destination)
                    } catch let err {
                        print("InklingRunner import/load error: \(err.localizedDescription)")
                    }''')
])
patch(example / "Models" / "LlamaState.swift", [
    ('messageLog += "Loading model...\\n"', 'messageLog += "Загружаю модель...\\n"'),
    ('messageLog += "Loaded model \(modelUrl.lastPathComponent)\\n"',
     'messageLog += "Модель загружена: \(modelUrl.lastPathComponent)\\n"'),
])
print("Patches completed; physical-device compatibility is not proven.")
