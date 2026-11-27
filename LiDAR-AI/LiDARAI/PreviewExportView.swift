import SwiftUI
import SceneKit
import UIKit

private struct Prepared: Sendable {
    let mesh: ScanMesh
    let obj: String
    let prompt: String
}
private struct ShareItem: Identifiable { let id=UUID(); let url: URL }
private struct ShareSheet: UIViewControllerRepresentable {
    let url:URL
    func makeUIViewController(context:Context)->UIActivityViewController { UIActivityViewController(activityItems:[url],applicationActivities:nil) }
    func updateUIViewController(_ uiViewController:UIActivityViewController,context:Context) {}
}
struct PreviewExportView: View {
    let source:ScanMesh
    let onBack:()->Void
    @State private var target:Double=1200
    @State private var wire=true
    @State private var result:Prepared?
    @State private var scene=SCNScene()
    @State private var share:ShareItem?
    @State private var message=""
    @State private var preparing=true
    var body: some View {
        VStack(spacing:10) {
            HStack { Button(action:onBack) { Label("Сканер",systemImage:"chevron.left") }; Spacer(); Text("AI-подготовка").font(.headline); Spacer() }.padding(.horizontal)
            SceneView(scene:scene,pointOfView:nil,options:[.allowsCameraControl,.autoenablesDefaultLighting]).frame(minHeight:180).background(Color.black).clipShape(RoundedRectangle(cornerRadius:18)).padding(.horizontal)
            Picker("Вид",selection:$wire) { Text("Сетка / Полигоны").tag(true); Text("Сплошной").tag(false) }.pickerStyle(.segmented).padding(.horizontal).onChange(of:wire) { value in scene.rootNode.childNode(withName:"mesh",recursively:true)?.geometry?.firstMaterial?.fillMode=value ? .lines:.fill }
            ScrollView {
                VStack(alignment:.leading,spacing:12) {
                    Text("Габариты X × Y × Z, мм").font(.caption).foregroundStyle(.secondary)
                    Text(MeshProcessor.dimensions(source.bounds)).font(.title2.monospacedDigit())
                    if let result=result { Text("После редукции: \(MeshProcessor.dimensions(result.mesh.bounds)) мм").font(.caption) }
                    Text("Детализация для AI").font(.headline)
                    HStack { Text("200"); Slider(value:$target,in:200...2500,step:50); Text("\(Int(target))").monospacedDigit() }
                    if preparing { ProgressView("Упрощение сетки…") }
                    if let result=result {
                        Text("\(source.faces.count) → \(result.mesh.faces.count) треугольников · \(result.mesh.vertices.count) вершин").font(.subheadline)
                        Text("OBJ: \(result.obj.count) символов · ≈ \(result.obj.utf8.count/3) токенов").font(.caption)
                        Text("Промпт + OBJ: ≈ \(result.prompt.utf8.count/3) токенов (грубая оценка, не токенизатор).").font(.caption).foregroundStyle(.secondary)
                    }
                    Text("LiDAR не является измерительным инструментом миллиметровой точности. Упрощение может изменить габариты, отверстия и мелкие детали.").font(.caption).foregroundStyle(.secondary)
                    Button { export() } label: { Label("Экспорт .OBJ для ChatGPT",systemImage:"square.and.arrow.up").frame(maxWidth:.infinity) }.buttonStyle(.borderedProminent).disabled(preparing || result?.mesh.faces.isEmpty != false)
                    Button { if let result=result { UIPasteboard.general.string=result.prompt; message="Промпт и OBJ скопированы" } } label: { Label("Скопировать промпт + данные",systemImage:"doc.on.doc").frame(maxWidth:.infinity) }.buttonStyle(.bordered).disabled(preparing || result?.mesh.faces.isEmpty != false)
                    if !message.isEmpty { Text(message).font(.caption).foregroundStyle(.secondary) }
                }.padding()
            }.background(.thinMaterial,in:RoundedRectangle(cornerRadius:18)).padding(.horizontal)
        }.padding(.vertical)
        .task(id:Int(target)) {
            preparing=true; message=""
            let goal=Int(target), input=source
            do { try await Task.sleep(nanoseconds:180_000_000) } catch { return }
            let work=Task.detached(priority:.userInitiated) { () -> Prepared in
                var meters=input; meters.vertices=input.vertices.map{$0/1000}
                var m=MeshProcessor.simplify(meters,target:goal); m.vertices=m.vertices.map{$0*1000}
                if let b=m.bounds { m.vertices=m.vertices.map{$0-b.center} }
                m=MeshProcessor.roundedForOBJ(m)
                let obj=MeshProcessor.obj(m,original:input.bounds)
                return Prepared(mesh:m,obj:obj,prompt:MeshProcessor.prompt(obj))
            }
            let prepared=await withTaskCancellationHandler(operation:{await work.value},onCancel:{work.cancel()})
            guard !Task.isCancelled else {return}
            result=prepared; scene=Self.makeScene(prepared.mesh,wire:wire); preparing=false
        }
        .sheet(item:$share) { ShareSheet(url:$0.url) }
    }
    private func export() {
        guard let result=result else {return}
        do {
            let dir=FileManager.default.temporaryDirectory.appendingPathComponent(UUID().uuidString,isDirectory:true)
            try FileManager.default.createDirectory(at:dir,withIntermediateDirectories:true)
            let url=dir.appendingPathComponent("LiDAR-AI-v2.obj"); try result.obj.write(to:url,atomically:true,encoding:.utf8)
            share=ShareItem(url:url)
        } catch { message=error.localizedDescription }
    }
    private static func makeScene(_ mesh:ScanMesh,wire:Bool)->SCNScene {
        let scene=SCNScene(); scene.background.contents=UIColor(white:0.06,alpha:1)
        guard let b=mesh.bounds,!mesh.faces.isEmpty else {return scene}
        let s=max(0.001,max(b.size.x,max(b.size.y,b.size.z)))
        let vertices=mesh.vertices.map { p -> SCNVector3 in let q=(p-b.center)/s; return SCNVector3(q.x,q.y,q.z) }
        let normals=mesh.normals.map{SCNVector3($0.x,$0.y,$0.z)}
        let ids=mesh.faces.flatMap{$0.indices.map{Int32($0)}}
        let element=SCNGeometryElement(indices:ids,primitiveType:.triangles)
        let geometry=SCNGeometry(sources:[SCNGeometrySource(vertices:vertices),SCNGeometrySource(normals:normals)],elements:[element])
        let material=SCNMaterial(); material.diffuse.contents=UIColor.systemTeal; material.isDoubleSided=true; material.fillMode=wire ? .lines:.fill; geometry.materials=[material]
        let node=SCNNode(geometry:geometry); node.name="mesh"; scene.rootNode.addChildNode(node)
        let camera=SCNNode(); camera.camera=SCNCamera(); camera.camera?.zNear=0.01; camera.camera?.zFar=100; camera.position=SCNVector3(1.5,1.1,1.8); camera.look(at:SCNVector3Zero); scene.rootNode.addChildNode(camera)
        return scene
    }
}
