import ARKit
import RealityKit
import ModelIO
import SwiftUI
import Combine
import AVFoundation
import simd

final class ARMeshManager: NSObject, ObservableObject, ARSessionDelegate {
    @Published private(set) var running=false
    @Published private(set) var faceCount=0
    @Published private(set) var tracking="Ожидание"
    @Published private(set) var error: String?
    @Published private(set) var hasBox=false
    @Published var boxSize: Double=0.6
    @Published var distance: Double=0.65
    @Published var omitRoom=true
    let supported=ARWorldTrackingConfiguration.supportsSceneReconstruction(.meshWithClassification)
    weak var view: ARView?
    private var region: Bounds?
    private var outline: AnchorEntity?
    private var snapshot=ScanMesh()
    private var lastTime: TimeInterval = 0
    private var initialized=false
    private var resumeAfterInterruption=false
    private(set) var modelMesh: MDLMesh?

    func attach(_ ar: ARView) {
        guard view !== ar else { return }
        view=ar; ar.session.delegate=self; ar.session.delegateQueue = .main
        ar.automaticallyConfigureSession=false
        ar.debugOptions.insert(.showSceneUnderstanding)
    }
    private func configuration() -> ARWorldTrackingConfiguration {
        let c=ARWorldTrackingConfiguration(); c.sceneReconstruction = .meshWithClassification
        c.worldAlignment = .gravity; return c
    }
    func start() {
        guard supported, let ar=view else { error="Нужен iPhone Pro / iPad Pro с LiDAR."; return }
        switch AVCaptureDevice.authorizationStatus(for:.video) {
        case .authorized: break
        case .notDetermined:
            AVCaptureDevice.requestAccess(for:.video) { [weak self] granted in
                DispatchQueue.main.async { if granted { self?.start() } else { self?.error="Разрешите камеру в Настройках." } }
            }; return
        default: error="Разрешите камеру в Настройках."; return
        }
        error=nil; running=true
        if initialized { ar.session.run(configuration()) }
        else { initialized=true; ar.session.run(configuration(),options:[.resetTracking,.removeExistingAnchors]) }
    }
    func pause() { running=false; view?.session.pause(); tracking="Пауза" }
    func reset() {
        running=false; view?.session.pause(); initialized=false; region=nil; hasBox=false
        outline?.removeFromParent(); outline=nil; snapshot=ScanMesh(); modelMesh=nil; faceCount=0; lastTime=0; tracking="Сброшено"; error=nil
        start()
    }
    func setBox() {
        guard running, let frame=view?.session.currentFrame else { error="Сначала запустите сканер."; return }
        guard case .normal=frame.camera.trackingState else { error="Дождитесь нормального трекинга."; return }
        let t=frame.camera.transform
        let origin=SIMD3(t.columns.3.x,t.columns.3.y,t.columns.3.z)
        let forward = -SIMD3(t.columns.2.x,t.columns.2.y,t.columns.2.z)
        let center=origin+forward*Float(distance), half=SIMD3<Float>(repeating:Float(boxSize)/2)
        region=Bounds(min:center-half,max:center+half); hasBox=true; error=nil
        snapshot=ScanMesh(); faceCount=0; drawBox(center:center,size:Float(boxSize)); refresh(frame)
    }
    private func drawBox(center: SIMD3<Float>, size: Float) {
        outline?.removeFromParent(); guard let ar=view else {return}
        let anchor=AnchorEntity(world:center), h=size/2, thickness:Float=0.003
        let mat=UnlitMaterial(color:.systemCyan)
        for axis in 0..<3 { for a in [-h,h] { for b in [-h,h] {
            var dims=SIMD3<Float>(repeating:thickness); dims[axis]=size
            var p=SIMD3<Float>.zero; p[(axis+1)%3]=a; p[(axis+2)%3]=b
            let e=ModelEntity(mesh:.generateBox(size:dims),materials:[mat]); e.position=p; anchor.addChild(e)
        } } }
        ar.scene.addAnchor(anchor); outline=anchor
    }
    func session(_ session:ARSession,didUpdate frame:ARFrame) {
        guard running else {return}
        switch frame.camera.trackingState {
        case .normal: tracking="Стабильно"
        case .notAvailable: tracking="Нет трекинга"
        case .limited: tracking="Ограничено: двигайтесь медленно"
        }
        guard frame.timestamp-lastTime>0.8, hasBox else {return}; lastTime=frame.timestamp; refresh(frame)
    }
    func session(_ session: ARSession, didFailWithError error: Error) { self.error=error.localizedDescription; pause() }
    func sessionWasInterrupted(_ session: ARSession) { resumeAfterInterruption=running; running=false; tracking="Прервано" }
    func sessionInterruptionEnded(_ session: ARSession) { if resumeAfterInterruption { start() }; resumeAfterInterruption=false }
    private func refresh(_ frame:ARFrame) {
        guard let box=region else {return}
        var result=ScanMesh()
        for case let a as ARMeshAnchor in frame.anchors {
            result.append(Self.extract(a).cropped(to:box,omitRoom:omitRoom))
        }
        snapshot=result; faceCount=result.faces.count
    }
    func finish() -> ScanMesh? {
        if running, let frame=view?.session.currentFrame { refresh(frame) }
        guard !snapshot.faces.isEmpty else { error="В рамке пока нет полигонов. Наведитесь на объект и обойдите его."; return nil }
        pause(); let mesh=snapshot.centeredMM(); modelMesh=Self.makeMDL(mesh); return mesh
    }
    private static func vector(_ source: ARGeometrySource,_ i:Int) -> SIMD3<Float> {
        let p=source.buffer.contents().advanced(by:source.offset+i*source.stride)
        return SIMD3(p.load(as:Float.self),p.load(fromByteOffset:4,as:Float.self),p.load(fromByteOffset:8,as:Float.self))
    }
    private static func extract(_ anchor: ARMeshAnchor) -> ScanMesh {
        let g=anchor.geometry, t=anchor.transform
        var m=ScanMesh(); m.vertices.reserveCapacity(g.vertices.count); m.normals.reserveCapacity(g.vertices.count)
        for i in 0..<g.vertices.count {
            let p=vector(g.vertices,i), w=t*SIMD4(p.x,p.y,p.z,1)
            m.vertices.append(SIMD3(w.x,w.y,w.z))
            if i<g.normals.count { let n=vector(g.normals,i), q=t*SIMD4(n.x,n.y,n.z,0); m.normals.append(MeshProcessor.normalized(SIMD3(q.x,q.y,q.z))) } else { m.normals.append(.zero) }
        }
        let f=g.faces; guard f.indexCountPerPrimitive==3 else {return m}
        let ptr=f.buffer.contents()
        func index(_ i:Int) -> Int {
            let p=ptr.advanced(by:i*f.bytesPerIndex)
            switch f.bytesPerIndex { case 2:return Int(p.load(as:UInt16.self)); case 4:return Int(p.load(as:UInt32.self)); default:return -1 }
        }
        let c=g.classification
        for i in 0..<f.count {
            let a=index(i*3),b=index(i*3+1),d=index(i*3+2)
            guard [a,b,d].allSatisfy({$0>=0 && $0<m.vertices.count}), a != b, b != d, a != d else {continue}
            let label:UInt8
            if let c=c, i<c.count { label=c.buffer.contents().advanced(by:c.offset+i*c.stride).load(as:UInt8.self) } else { label=0 }
            m.faces.append(Triangle(a:a,b:b,c:d,classification:label))
        }
        return m
    }
    static func makeMDL(_ m:ScanMesh) -> MDLMesh {
        var values=[Float](); values.reserveCapacity(m.vertices.count*6)
        for (i,p) in m.vertices.enumerated() { let n=i<m.normals.count ? m.normals[i] : .zero; values += [p.x,p.y,p.z,n.x,n.y,n.z] }
        let ids=m.faces.flatMap{$0.indices.map{UInt32($0)}}
        let allocator=MDLMeshBufferDataAllocator()
        let vertexData=values.withUnsafeBufferPointer{Data(buffer:$0)}, indexData=ids.withUnsafeBufferPointer{Data(buffer:$0)}
        let vb=allocator.newBuffer(with:vertexData,type:.vertex), ib=allocator.newBuffer(with:indexData,type:.index)
        let desc=MDLVertexDescriptor()
        desc.attributes[0]=MDLVertexAttribute(name:MDLVertexAttributePosition,format:.float3,offset:0,bufferIndex:0)
        desc.attributes[1]=MDLVertexAttribute(name:MDLVertexAttributeNormal,format:.float3,offset:12,bufferIndex:0)
        desc.layouts[0]=MDLVertexBufferLayout(stride:24)
        let sub=MDLSubmesh(indexBuffer:ib,indexCount:ids.count,indexType:.uInt32,geometryType:.triangles,material:nil)
        return MDLMesh(vertexBuffer:vb,vertexCount:m.vertices.count,descriptor:desc,submeshes:[sub])
    }
}
