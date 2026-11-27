import SwiftUI
import RealityKit

struct ARSurface: UIViewRepresentable {
    let manager:ARMeshManager
    func makeUIView(context:Context)->ARView {let v=ARView(frame:.zero,cameraMode:.ar,automaticallyConfigureSession:false);manager.attach(v);return v}
    func updateUIView(_ uiView:ARView,context:Context){}
}
struct ScannerView: View {
    @ObservedObject var manager:ARMeshManager
    let onFinish:(ScanMesh)->Void
    @State private var showSettings=false
    @State private var confirmReplace=false
    var body:some View {
        ZStack {
            if manager.supported { ARSurface(manager:manager).ignoresSafeArea() } else {Color.black.ignoresSafeArea()}
            if manager.running && !manager.hasBox {
                ZStack {
                    RoundedRectangle(cornerRadius:16).stroke(.white.opacity(0.9),style:StrokeStyle(lineWidth:1.5,dash:[10,5])).frame(width:122,height:122)
                    Image(systemName:"plus").font(.title.weight(.thin)).foregroundStyle(.cyan)
                }.allowsHitTesting(false)
            }
            VStack(spacing:10) {
                VStack(alignment:.leading,spacing:9) {
                    HStack {
                        Label("LiDAR AI 2.0",systemImage:"viewfinder").font(.headline)
                        Spacer()
                        Text(manager.tracking).font(.caption).foregroundStyle(manager.running ? .green:.secondary)
                        Button{showSettings=true}label:{Image(systemName:"slider.horizontal.3").font(.title3)}.buttonStyle(.plain)
                    }
                    HStack(alignment:.center) {
                        ZStack {
                            Circle().stroke(.white.opacity(0.15),lineWidth:6)
                            Circle().trim(from:0,to:Double(manager.coverage)/100).stroke(.cyan,style:StrokeStyle(lineWidth:6,lineCap:.round)).rotationEffect(.degrees(-90))
                            Text("\(manager.coverage)%").font(.system(size:20,weight:.bold,design:.monospaced))
                        }.frame(width:62,height:62)
                        VStack(alignment:.leading,spacing:4) {
                            Text("Покрытие ракурсов").font(.subheadline.weight(.semibold))
                            Text("\(manager.sectors.filter{$0}.count) из 24 направлений").font(.caption).foregroundStyle(.secondary)
                            HStack(spacing:4) {Text("Верх").frame(width:38,alignment:.leading);sectorRow(12)}
                            HStack(spacing:4) {Text("Бока").frame(width:38,alignment:.leading);sectorRow(0)}
                        }
                        Spacer(minLength:0)
                    }
                    ProgressView(value:Double(manager.coverage),total:100).tint(.cyan)
                    HStack {
                        Label("\(manager.faceCount)",systemImage:"triangle").font(.subheadline.monospacedDigit())
                        Spacer()
                        Label("\(manager.vertexCount)",systemImage:"point.3.connected.trianglepath.dotted").font(.subheadline.monospacedDigit())
                        Spacer()
                        Text(manager.depthDistance.map{String(format:"%.0f см",Double($0)*100)} ?? "— см").font(.subheadline.monospacedDigit())
                    }
                    Text("Процент — оценка охвата ракурсов, не полнота поверхности. Дно не учитывается.").font(.caption2).foregroundStyle(.secondary)
                }.padding(14).background(.ultraThinMaterial,in:RoundedRectangle(cornerRadius:20))
                Spacer()
                if !manager.supported {Text("Нужен iPhone / iPad с LiDAR.").padding().background(.regularMaterial,in:RoundedRectangle(cornerRadius:12))}
                if let error=manager.error {Text(error).font(.footnote).padding(10).background(.regularMaterial,in:RoundedRectangle(cornerRadius:12))}
                VStack(spacing:10) {
                    Text(manager.hint).font(.footnote).multilineTextAlignment(.center).frame(maxWidth:.infinity)
                    if manager.hasBox {
                        HStack {
                            Label("Захвачено: \(manager.captureFrames) кадров",systemImage:"checkmark.circle").font(.caption)
                            Spacer()
                            Button {manager.showOverlay.toggle()} label:{Image(systemName:manager.showOverlay ? "eye":"eye.slash")}.buttonStyle(.borderless)
                        }
                    } else {
                        HStack {Text("Размер рамки");Spacer();Text(String(format:"%.0f см",manager.boxSize*100)).monospacedDigit()}.font(.caption)
                        Slider(value:$manager.boxSize,in:0.15...1.5,step:0.05).tint(.cyan)
                    }
                    if !manager.hasBox {
                        Button{ if manager.running {manager.setBox()}else{manager.start()} }label:{
                            Label(manager.running ? "Сканировать объект":"Запустить камеру",systemImage:"viewfinder").frame(maxWidth:.infinity).padding(.vertical,5)
                        }.buttonStyle(.borderedProminent).tint(.teal)
                    } else {
                        HStack {
                            Button{if manager.running{manager.pause()}else{manager.start()}}label:{Label(manager.running ? "Пауза":"Продолжить",systemImage:manager.running ? "pause.fill":"play.fill").frame(maxWidth:.infinity)}.buttonStyle(.bordered)
                            Button{confirmReplace=true}label:{Label("Заново",systemImage:"arrow.counterclockwise").frame(maxWidth:.infinity)}.buttonStyle(.bordered)
                        }
                        Button{if let m=manager.finish(){onFinish(m)}}label:{Label("Завершить скан",systemImage:"checkmark.circle.fill").frame(maxWidth:.infinity).padding(.vertical,5)}.buttonStyle(.borderedProminent).tint(.teal).disabled(manager.faceCount==0)
                    }
                }.padding(14).background(.regularMaterial,in:RoundedRectangle(cornerRadius:20)).disabled(!manager.supported)
            }.padding()
        }
        .alert("Удалить текущий скан?",isPresented:$confirmReplace) {Button("Отмена",role:.cancel){};Button("Начать заново",role:.destructive){manager.reset()}} message:{Text("Накопленная сетка будет удалена.")}
        .sheet(isPresented:$showSettings) {
            NavigationStack {
                Form {
                    Section("Выбор объекта") {
                        Toggle("Автоматическая дистанция LiDAR",isOn:$manager.autoDepth)
                        if !manager.autoDepth {HStack {Text("Дистанция");Slider(value:$manager.distance,in:0.2...1.5,step:0.05);Text(String(format:"%.2f м",manager.distance))}}
                        HStack{Text("Сторона рамки");Slider(value:$manager.boxSize,in:0.15...1.5,step:0.05);Text(String(format:"%.2f м",manager.boxSize))}
                        Text("Параметры области применяются при следующем выборе объекта.").font(.caption)
                    }.disabled(manager.hasBox)
                    Section("Отображение и фильтрация"){
                        Toggle("Показывать накопленную сетку",isOn:$manager.showOverlay)
                        Toggle("Исключать распознанные стены, пол и потолок",isOn:$manager.omitRoom).disabled(manager.hasBox)
                    }
                    Section("Как сканировать") {
                        Text("Положите неподвижный объект на поверхность. Держите камеру примерно в 20–100 см, наведите прицел на центр видимой поверхности, задайте размер рамки и начните. Медленно обойдите предмет и снимите его сверху. Не вращайте сам объект. Прозрачные, блестящие и очень мелкие детали LiDAR может не увидеть.")
                    }
                }.navigationTitle("Настройки сканера").toolbar{ToolbarItem(placement:.confirmationAction){Button("Готово"){showSettings=false}}}
            }
        }
    }
    private func sectorRow(_ offset:Int)->some View {
        HStack(spacing:3) {ForEach(0..<12,id:\.self){i in RoundedRectangle(cornerRadius:2).fill(manager.sectors[i+offset] ? Color.cyan:Color.white.opacity(0.13)).frame(height:10)}}
        .font(.caption2)
    }
}
