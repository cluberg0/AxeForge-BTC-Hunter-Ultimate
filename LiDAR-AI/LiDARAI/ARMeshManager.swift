import ARKit
import RealityKit
import ModelIO
import SwiftUI
import Combine
import AVFoundation
import CoreVideo
import simd

private struct DepthSample {
    let point: SIMD3<Float>
    let depth: Float
}
private struct Voxel: Hashable {
    let x: Int32, y: Int32, z: Int32
    init(_ p: SIMD3<Float>, step: Float) {
        x=Int32(floor(p.x/step)); y=Int32(floor(p.y/step)); z=Int32(floor(p.z/step))
    }
}
private struct TriKey: Hashable {
    let a: Int, b: Int, c: Int
    init(_ a: Int,_ b: Int,_ c: Int) { let s=[a,b,c].sorted(); self.a=s[0]; self.b=s[1]; self.c=s[2] }
}
private struct DepthFusion {
    var mesh=ScanMesh()
    var lookup=[Voxel:Int]()
    var faces=Set<TriKey>()
    var weights=[Int]()
    let spacing:Float
    init(spacing: Float) { self.spacing=spacing }
    mutating func index(_ p: SIMD3<Float>, normal: SIMD3<Float>) -> Int? {
        let key=Voxel(p,step:spacing)
        if let i=lookup[key] {
            let w=Float(min(weights[i],24))
            mesh.vertices[i]=(mesh.vertices[i]*w+p)/(w+1)
            mesh.normals[i]=MeshProcessor.normalized(mesh.normals[i]*w+normal)
            weights[i]=min(weights[i]+1,24)
            return i
        }
        guard mesh.vertices.count<85000 else { return nil }
        let i=mesh.vertices.count; lookup[key]=i
        mesh.vertices.append(p); mesh.normals.append(normal); weights.append(1); return i
    }
    mutating func add(_ a: DepthSample,_ b: DepthSample,_ c: DepthSample,label: UInt8) -> Bool {
        guard mesh.faces.count<160000 else { return false }
        let z=min(a.depth,min(b.depth,c.depth))
        let maxDepthJump=max(0.018,z*0.035)
        guard max(abs(a.depth-b.depth),max(abs(a.depth-c.depth),abs(b.depth-c.depth)))<maxDepthJump else { return false }
        let p=a.point,q=b.point,r=c.point
        let longest=max(simd_distance(p,q),max(simd_distance(q,r),simd_distance(r,p)))
        guard longest<max(0.025,z*0.05) else {return false}
        let cross=simd_cross(q-p,r-p)
        guard simd_length_squared(cross)>1e-12 else {return false}
        let normal=simd_normalize(cross)
        guard let i=index(p,normal:normal),let j=index(q,normal:normal),let k=index(r,normal:normal), i != j, j != k, i != k else {return false}
        if faces.insert(TriKey(i,j,k)).inserted { mesh.faces.append(Triangle(a:i,b:j,c:k,classification:label)) }
        return true
    }
    func snapshot() -> ScanMesh {
        var m=mesh
        m.faces=m.faces.filter { f in simd_length_squared(simd_cross(m.vertices[f.b]-m.vertices[f.a],m.vertices[f.c]-m.vertices[f.a]))>1e-12 }
        return m.compact()
    }
}

final class ARMeshManager: NSObject, ObservableObject, ARSessionDelegate {
    @Published private(set) var running=false
    @Published private(set) var faceCount=0
    @Published private(set) var vertexCount=0
    @Published private(set) var tracking="Камера не запущена"
    @Published private(set) var error: String?
    @Published private(set) var hasBox=false
    @Published private(set) var sectors=Array(repeating:false,count:24)
    @Published private(set) var depthDistance:Float?
    @Published private(set) var frameTriangles=0
    @Published private(set) var captureFrames=0
    @Published private(set) var hint="Запустите камеру и наведите прицел на объект."
    @Published var boxSize: Double=0.35
    @Published var distance: Double=0.65
    @Published var autoDepth=true
    @Published var omitRoom=true
    @Published var showOverlay=true { didSet { overlay?.isEnabled=showOverlay } }
    var coverage:Int { Int((Double(sectors.filter{$0}.count)/24.0*100).rounded()) }
    let supported=ARWorldTrackingConfiguration.supportsSceneReconstruction(.meshWithClassification) && ARWorldTrackingConfiguration.supportsFrameSemantics(.sceneDepth)
    weak var view: ARView?
    private var region: Bounds?
    private var outline: AnchorEntity?
    private var overlay: AnchorEntity?
    private var overlayModel: ModelEntity?
    private var fusion=DepthFusion(spacing:0.006)
    private var sectorHits=Array(repeating:0,count:24)
    private var sectorLastPosition=[Int:SIMD3<Float>]()
    private var lastTime: TimeInterval=0
    private var lastRender: TimeInterval=0
    private var lastClassify: TimeInterval = -100
    private var lastPose: SIMD3<Float>?
    private var labels=[Voxel:UInt8]()
    private var initialized=false
    private var resumeAfterInterruption=false
    private(set) var modelMesh: MDLMesh?

    func attach(_ ar: ARView) {
        guard view !== ar else { return }
        view=ar
        ar.automaticallyConfigureSession=false
        ar.session.delegate=self; ar.session.delegateQueue = .main
        ar.renderOptions.insert(.disableMotionBlur)
        ar.environment.sceneUnderstanding.options.remove(.occlusion)
        DispatchQueue.main.async { [weak self] in self?.start() }
    }
    private func configuration() -> ARWorldTrackingConfiguration {
        let c=ARWorldTrackingConfiguration()
        c.sceneReconstruction = .meshWithClassification
        c.frameSemantics.insert(.sceneDepth)
        c.worldAlignment = .gravity
        return c
    }
    func start() {
        guard supported, let ar=view else { error="Нужен iPhone / iPad с LiDAR и sceneDepth."; return }
        switch AVCaptureDevice.authorizationStatus(for:.video) {
        case .authorized: break
        case .notDetermined:
            AVCaptureDevice.requestAccess(for:.video) { [weak self] granted in
                DispatchQueue.main.async { if granted { self?.start() } else { self?.error="Разрешите камеру в Настройках." } }
            }; return
        default: error="Разрешите камеру в Настройках."; return
        }
        error=nil; running=true; lastPose=nil
        if initialized { ar.session.run(configuration()) }
        else { initialized=true; ar.session.run(configuration(),options:[.resetTracking,.removeExistingAnchors]) }
        hint=hasBox ? "Медленно обходите объект вокруг." : "Наведите прицел на середину объекта и нажмите «Сканировать объект»."
    }
    func pause() { running=false; view?.session.pause(); tracking="Пауза" }
    private func clearCapture() {
        region=nil; hasBox=false; outline?.removeFromParent(); outline=nil
        overlay?.removeFromParent(); overlay=nil; overlayModel=nil
        fusion=DepthFusion(spacing:Float(max(0.004,min(0.010,boxSize/80))))
        labels.removeAll(); sectors=Array(repeating:false,count:24)
        sectorHits=Array(repeating:0,count:24); sectorLastPosition.removeAll()
        faceCount=0; vertexCount=0; frameTriangles=0; captureFrames=0
        lastPose=nil; lastTime=0; lastRender=0; lastClassify = -100; modelMesh=nil
    }
    func reset() {
        pause(); initialized=false; clearCapture(); error=nil; depthDistance=nil
        start()
    }
    private static func cameraPosition(_ frame:ARFrame)->SIMD3<Float> {
        let t=frame.camera.transform.columns.3; return SIMD3(t.x,t.y,t.z)
    }
    private static func centerDepth(_ frame:ARFrame)->Float? {
        guard let d=frame.sceneDepth else {return nil}
        let b=d.depthMap
        CVPixelBufferLockBaseAddress(b,.readOnly); defer {CVPixelBufferUnlockBaseAddress(b,.readOnly)}
        guard let base=CVPixelBufferGetBaseAddress(b) else {return nil}
        let w=CVPixelBufferGetWidth(b), h=CVPixelBufferGetHeight(b), stride=CVPixelBufferGetBytesPerRow(b)/MemoryLayout<Float>.stride
        let ptr=base.assumingMemoryBound(to:Float.self)
        guard w>10,h>10 else {return nil}
        var values=[Float]()
        for y in (h/2-3)...(h/2+3) {for x in (w/2-3)...(w/2+3) {
            let z=ptr[y*stride+x]; if z.isFinite,z>=0.15,z<=2.0 { values.append(z) }
        }}
        guard values.count>=12 else {return nil}; values.sort(); return values[values.count/2]
    }
    func setBox() {
        guard running,let frame=view?.session.currentFrame else {error="Запустите камеру.";return}
        guard case .normal=frame.camera.trackingState else {error="Дождитесь стабилизации трекинга.";return}
        let t=frame.camera.transform
        let origin=Self.cameraPosition(frame)
        let forward = -SIMD3(t.columns.2.x,t.columns.2.y,t.columns.2.z)
        let z:Float
        if autoDepth {
            guard let d=Self.centerDepth(frame) else {error="LiDAR не видит поверхность. Подойдите на 20–100 см, наведитесь и попробуйте снова.";return}
            z=d+min(Float(boxSize)*0.23,0.16)
        } else { z=Float(distance) }
        clearCapture()
        let center=origin+forward*z,half=SIMD3<Float>(repeating:Float(boxSize)/2)
        region=Bounds(min:center-half,max:center+half); hasBox=true; error=nil
        drawBox(center:center,size:Float(boxSize))
        hint="Обходите объект по кругу, затем снимите его сверху."
        refresh(frame,force:true)
    }
    private func drawBox(center: SIMD3<Float>,size:Float) {
        guard let ar=view else {return}
        let anchor=AnchorEntity(world:center),h=size/2, thickness:Float=0.0018
        let mat=UnlitMaterial(color:.white)
        for axis in 0..<3 {for a in [-h,h] {for b in [-h,h] {
            var dims=SIMD3<Float>(repeating:thickness); dims[axis]=size
            var p=SIMD3<Float>.zero; p[(axis+1)%3]=a; p[(axis+2)%3]=b
            let e=ModelEntity(mesh:.generateBox(size:dims),materials:[mat]);e.position=p;anchor.addChild(e)
        }}}
        ar.scene.addAnchor(anchor); outline=anchor
        let captured=AnchorEntity(world:SIMD3<Float>.zero); ar.scene.addAnchor(captured); overlay=captured
        captured.isEnabled=showOverlay
    }
    func session(_ session:ARSession,didUpdate frame:ARFrame) {
        guard running, frame.timestamp-lastTime>0.35 else {return}
        lastTime=frame.timestamp
        depthDistance=Self.centerDepth(frame)
        switch frame.camera.trackingState {
        case .normal: tracking="Трекинг OK"
        case .notAvailable: tracking="Нет трекинга";return
        case .limited: tracking="Двигайтесь медленнее";return
        }
        guard hasBox else {return}
        refresh(frame,force:false)
    }
    func session(_ session:ARSession,didFailWithError error: Error) {self.error=error.localizedDescription;pause()}
    func sessionWasInterrupted(_ session:ARSession) {resumeAfterInterruption=running; running=false; tracking="Прервано"}
    func sessionInterruptionEnded(_ session:ARSession) {if resumeAfterInterruption {start()};resumeAfterInterruption=false}
    private func updateLabels(_ frame:ARFrame,box:Bounds) {
        var next=[Voxel:UInt8]()
        for case let anchor as ARMeshAnchor in frame.anchors {
            let m=Self.extract(anchor)
            for f in m.faces where f.classification != 0 {
                let p=(m.vertices[f.a]+m.vertices[f.b]+m.vertices[f.c])/3
                if box.contains(p) {next[Voxel(p,step:0.035)]=f.classification}
            }
        }
        labels=next
    }
    private func refresh(_ frame:ARFrame,force:Bool) {
        guard let box=region,let depth=frame.sceneDepth else {hint="Нет карты глубины LiDAR.";return}
        let position=Self.cameraPosition(frame)
        if !force,let p=lastPose,simd_distance(p,position)<0.018 {return}
        if frame.timestamp-lastClassify>1.5 {updateLabels(frame,box:box);lastClassify=frame.timestamp}
        let buffer=depth.depthMap,conf=depth.confidenceMap
        CVPixelBufferLockBaseAddress(buffer,.readOnly)
        if let conf=conf {CVPixelBufferLockBaseAddress(conf,.readOnly)}
        defer { CVPixelBufferUnlockBaseAddress(buffer,.readOnly);if let conf=conf {CVPixelBufferUnlockBaseAddress(conf,.readOnly)} }
        guard let base=CVPixelBufferGetBaseAddress(buffer),CVPixelBufferGetPixelFormatType(buffer)==kCVPixelFormatType_DepthFloat32 else {hint="Неподдерживаемая карта глубины.";return}
        let w=CVPixelBufferGetWidth(buffer),h=CVPixelBufferGetHeight(buffer),stride=CVPixelBufferGetBytesPerRow(buffer)/4
        guard w>3,h>3 else {return}
        let ptr=base.assumingMemoryBound(to:Float.self)
        let confidence=conf.flatMap{CVPixelBufferGetBaseAddress($0)?.assumingMemoryBound(to:UInt8.self)}
        let cs=conf.map{CVPixelBufferGetBytesPerRow($0)} ?? 0
        let cw=conf.map{CVPixelBufferGetWidth($0)} ?? 0, ch=conf.map{CVPixelBufferGetHeight($0)} ?? 0
        let K=frame.camera.intrinsics, res=frame.camera.imageResolution
        let sx=Float(w)/Float(res.width),sy=Float(h)/Float(res.height)
        let fx=K.columns.0.x*sx,fy=K.columns.1.y*sy,cx=K.columns.2.x*sx,cy=K.columns.2.y*sy
        let t=frame.camera.transform
        let step=2, cols=(w-1)/step+1,rows=(h-1)/step+1
        var samples=Array<DepthSample?>(repeating:nil,count:cols*rows)
        for j in 0..<rows {for i in 0..<cols {
            let x=i*step,y=j*step,z=ptr[y*stride+x]
            guard z.isFinite,z>=0.15,z<=2.0 else {continue}
            if let c=confidence,cw==w,ch==h,c[y*cs+x]<1 {continue}
            let camera=SIMD4((Float(x)-cx)*z/fx,-(Float(y)-cy)*z/fy,-z,1)
            let q=t*camera,p=SIMD3(q.x,q.y,q.z)
            if box.contains(p) {samples[j*cols+i]=DepthSample(point:p,depth:z)}
        }}
        var accepted=0
        func label(_ a:DepthSample,_ b:DepthSample,_ c:DepthSample)->UInt8 {
            labels[Voxel((a.point+b.point+c.point)/3,step:0.035)] ?? 0
        }
        func triangle(_ i:Int,_ j:Int,_ k:Int) {
            guard let a=samples[i],let b=samples[j],let c=samples[k] else {return}
            let l=label(a,b,c)
            if omitRoom && [UInt8(1),2,3].contains(l) {return}
            if fusion.add(a,b,c,label:l) {accepted+=1}
        }
        for y in 0..<(rows-1) {for x in 0..<(cols-1) {
            let a=y*cols+x,b=a+1,c=a+cols,d=c+1
            triangle(a,c,b);triangle(b,c,d)
        }}
        frameTriangles=accepted;faceCount=fusion.mesh.faces.count;vertexCount=fusion.mesh.vertices.count
        if accepted>=20 {
            lastPose=position; captureFrames+=1
            updateCoverage(position,center:box.center)
            hint=coverage>=85 ? "Почти все ракурсы пройдены. Проверьте пропуски сетки." : "Обходите объект. Бирюзовое покрытие — сохранённые треугольники."
        } else { hint="Мало глубины в рамке. Подойдите ближе или измените угол." }
        if fusion.mesh.faces.count>=160000 || fusion.mesh.vertices.count>=85000 { hint="Лимит памяти скана достигнут. Завершите скан." }
        if force || frame.timestamp-lastRender>0.6 { render();lastRender=frame.timestamp }
    }
    private func updateCoverage(_ p:SIMD3<Float>,center:SIMD3<Float>) {
        let v=p-center,flat=sqrt(v.x*v.x+v.z*v.z)
        guard simd_length(v)>0.12,flat>0.08 else {return}
        var angle=atan2(v.z,v.x);if angle<0 {angle+=2*Float.pi}
        let az=min(11,Int(angle/(2*Float.pi)*12))
        let elev=atan2(v.y,flat)
        guard elev > -Float.pi/6 else {return}
        let index=az+(elev>Float.pi/7 ? 12:0)
        if let prev=sectorLastPosition[index],simd_distance(prev,p)<0.015 {return}
        sectorLastPosition[index]=p;sectorHits[index]+=1
        if sectorHits[index]>=2 && !sectors[index] {var s=sectors;s[index]=true;sectors=s}
    }
    private func render() {
        guard let overlay=overlay,!fusion.mesh.faces.isEmpty else {return}
        let m=fusion.mesh, step=max(1,(m.faces.count+34999)/35000)
        var indices=[UInt32]();indices.reserveCapacity(min(m.faces.count,35000)*3)
        for i in stride(from:0,to:m.faces.count,by:step) {
            let f=m.faces[i];indices += [UInt32(f.a),UInt32(f.b),UInt32(f.c)]
        }
        var descriptor=MeshDescriptor(name:"CapturedSurface")
        descriptor.positions=MeshBuffers.Positions(m.vertices)
        descriptor.normals=MeshBuffers.Normals(m.normals)
        descriptor.primitives = .triangles(indices)
        do {
            let resource=try MeshResource.generate(from:[descriptor])
            var material=UnlitMaterial(color:UIColor.systemTeal.withAlphaComponent(0.72))
            if #available(iOS 18.0, *) { material.faceCulling = .none }
            if let model=overlayModel {model.model=ModelComponent(mesh:resource,materials:[material])}
            else {let model=ModelEntity(mesh:resource,materials:[material]);overlay.addChild(model);overlayModel=model}
        } catch {hint="Не удалось показать сетку: \(error.localizedDescription)"}
    }
    func finish()->ScanMesh? {
        let raw=fusion.snapshot()
        guard !raw.faces.isEmpty else {error="Нет захваченной геометрии. Выберите объект и дождитесь бирюзового покрытия.";return nil}
        pause();let mesh=raw.centeredMM();modelMesh=Self.makeMDL(mesh);return mesh
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
