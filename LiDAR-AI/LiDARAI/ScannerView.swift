import SwiftUI
import RealityKit

struct ARSurface: UIViewRepresentable {
    let manager: ARMeshManager
    func makeUIView(context:Context) -> ARView { let v=ARView(frame:.zero,cameraMode:.ar,automaticallyConfigureSession:false); manager.attach(v); return v }
    func updateUIView(_ uiView:ARView,context:Context) {}
}
struct ScannerView: View {
    @ObservedObject var manager: ARMeshManager
    let onFinish:(ScanMesh)->Void
    var body: some View {
        ZStack {
            if manager.supported { ARSurface(manager:manager).ignoresSafeArea() } else { Color.black.ignoresSafeArea() }
            VStack(spacing:12) {
                HStack {
                    Label("LiDAR AI",systemImage:"viewfinder").font(.headline)
                    Spacer()
                    VStack(alignment:.trailing) { Text("\(manager.faceCount) △").font(.title3.monospacedDigit()); Text(manager.tracking).font(.caption) }
                }.padding().background(.regularMaterial,in:RoundedRectangle(cornerRadius:18))
                Spacer()
                if manager.running && !manager.hasBox { Image(systemName:"plus").font(.largeTitle.weight(.thin)).foregroundStyle(.cyan); Spacer() }
                if !manager.supported { Text("Устройство не поддерживает реконструкцию LiDAR.").padding().background(.regularMaterial,in:RoundedRectangle(cornerRadius:12)) }
                if let error=manager.error { Text(error).font(.footnote).padding(8).background(.regularMaterial,in:RoundedRectangle(cornerRadius:10)) }
                VStack(alignment:.leading,spacing:10) {
                    Text("Область сканирования").font(.headline)
                    HStack { Text("Сторона рамки"); Spacer(); Text(String(format:"%.2f м",manager.boxSize)).monospacedDigit() }
                    Slider(value:$manager.boxSize,in:0.2...1.5,step:0.05)
                    HStack { Text("Дистанция до центра"); Spacer(); Text(String(format:"%.2f м",manager.distance)).monospacedDigit() }
                    Slider(value:$manager.distance,in:0.2...1.5,step:0.05)
                    Toggle("Исключать стены, пол и потолок",isOn:$manager.omitRoom)
                    Button { manager.setBox() } label: { Label(manager.hasBox ? "Переставить рамку" : "Зафиксировать рамку по прицелу",systemImage:"cube.transparent").frame(maxWidth:.infinity) }.buttonStyle(.bordered).disabled(!manager.running)
                    Text("Бирюзовая рамка ограничивает экспорт. Сетка ARKit видна и за её пределами. Изменение размера/дистанции применяется при перестановке рамки.").font(.caption).foregroundStyle(.secondary)
                    HStack {
                        Button { if manager.running {manager.pause()} else {manager.start()} } label: { Label(manager.running ? "Пауза" : "Старт",systemImage:manager.running ? "pause.fill":"play.fill").frame(maxWidth:.infinity) }.buttonStyle(.borderedProminent)
                        Button { manager.reset() } label: { Label("Сброс",systemImage:"arrow.counterclockwise").frame(maxWidth:.infinity) }.buttonStyle(.bordered)
                    }
                    Button { if let mesh=manager.finish() {onFinish(mesh)} } label: { Label("Завершить скан",systemImage:"checkmark.circle").frame(maxWidth:.infinity) }.buttonStyle(.borderedProminent).tint(.teal).disabled(manager.faceCount==0)
                }.padding().background(.regularMaterial,in:RoundedRectangle(cornerRadius:22)).disabled(!manager.supported)
            }.padding()
        }
    }
}
