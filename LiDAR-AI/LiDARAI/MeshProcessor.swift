import Foundation

struct Triangle: Hashable, Sendable {
    var a: Int; var b: Int; var c: Int; var classification: UInt8
    var indices: [Int] { [a,b,c] }
}
struct Bounds: Sendable {
    var min: SIMD3<Float>; var max: SIMD3<Float>
    var size: SIMD3<Float> { max-min }
    var center: SIMD3<Float> { (min+max)/2 }
    func contains(_ p: SIMD3<Float>) -> Bool {
        p.x >= min.x && p.x <= max.x && p.y >= min.y && p.y <= max.y && p.z >= min.z && p.z <= max.z
    }
}
struct ScanMesh: Sendable {
    var vertices: [SIMD3<Float>] = []
    var normals: [SIMD3<Float>] = []
    var faces: [Triangle] = []
    var bounds: Bounds? {
        guard let p = vertices.first else { return nil }
        var lo=p, hi=p
        for v in vertices { for i in 0..<3 { lo[i]=Swift.min(lo[i],v[i]); hi[i]=Swift.max(hi[i],v[i]) } }
        return Bounds(min:lo,max:hi)
    }
    mutating func append(_ m: ScanMesh) {
        let offset=vertices.count
        vertices += m.vertices; normals += m.normals
        faces += m.faces.map { Triangle(a:$0.a+offset,b:$0.b+offset,c:$0.c+offset,classification:$0.classification) }
    }
    func cropped(to box: Bounds, omitRoom: Bool) -> ScanMesh {
        var m=self
        m.faces=faces.filter { f in
            (!omitRoom || ![UInt8(1),2,3].contains(f.classification)) && f.indices.allSatisfy { box.contains(vertices[$0]) }
        }
        return m.compact()
    }
    func compact() -> ScanMesh {
        var out=ScanMesh(), remap=[Int:Int]()
        for f in faces {
            var ids=[Int]()
            for i in f.indices {
                if let j=remap[i] { ids.append(j) } else {
                    let j=out.vertices.count; remap[i]=j; ids.append(j)
                    out.vertices.append(vertices[i]); out.normals.append(i<normals.count ? normals[i] : .zero)
                }
            }
            out.faces.append(Triangle(a:ids[0],b:ids[1],c:ids[2],classification:f.classification))
        }
        return out
    }
    func centeredMM() -> ScanMesh {
        guard let b=bounds else { return self }
        var m=self; m.vertices=vertices.map { ($0-b.center)*1000 }; return m
    }
}
private struct Cell: Hashable { let x:Int; let y:Int; let z:Int }
private struct FaceKey: Hashable {
    let a:Int; let b:Int; let c:Int
    init(_ a:Int,_ b:Int,_ c:Int) { let s=[a,b,c].sorted(); self.a=s[0]; self.b=s[1]; self.c=s[2] }
}
private struct Accum { var p=SIMD3<Float>.zero; var n=SIMD3<Float>.zero; var count:Float=0 }
enum MeshProcessor {
    static func cross(_ a:SIMD3<Float>,_ b:SIMD3<Float>) -> SIMD3<Float> {
        SIMD3(a.y*b.z-a.z*b.y,a.z*b.x-a.x*b.z,a.x*b.y-a.y*b.x)
    }
    static func length2(_ a:SIMD3<Float>) -> Float { a.x*a.x+a.y*a.y+a.z*a.z }
    static func normalized(_ a:SIMD3<Float>) -> SIMD3<Float> { let l=sqrt(length2(a)); return l>0 ? a/l : .zero }
    static func cluster(_ mesh:ScanMesh, cell:Float) -> ScanMesh {
        guard let b=mesh.bounds, cell>0 else { return mesh }
        var lookup=[Cell:Int](), sums=[Accum](), map=[Int]()
        map.reserveCapacity(mesh.vertices.count)
        for (i,p) in mesh.vertices.enumerated() {
            let q=(p-b.min)/cell
            let key=Cell(x:Int(floor(q.x)),y:Int(floor(q.y)),z:Int(floor(q.z)))
            let j:Int
            if let old=lookup[key] { j=old } else { j=sums.count; lookup[key]=j; sums.append(Accum()) }
            sums[j].p += p; if i<mesh.normals.count { sums[j].n += mesh.normals[i] }; sums[j].count += 1; map.append(j)
        }
        var out=ScanMesh(vertices:sums.map{$0.p/$0.count},normals:sums.map{normalized($0.n)},faces:[])
        var seen=Set<FaceKey>()
        for f in mesh.faces {
            let a=map[f.a], b=map[f.b], c=map[f.c]
            guard a != b, b != c, a != c, length2(cross(out.vertices[b]-out.vertices[a],out.vertices[c]-out.vertices[a])) > 1e-12 else { continue }
            if seen.insert(FaceKey(a,b,c)).inserted { out.faces.append(Triangle(a:a,b:b,c:c,classification:f.classification)) }
        }
        return out.compact()
    }
    static func simplify(_ source:ScanMesh, target:Int) -> ScanMesh {
        let goal=max(1,target)
        guard source.faces.count>goal, let box=source.bounds else { return source.compact() }
        let extent=max(box.size.x,max(box.size.y,box.size.z))
        guard extent>0 else { return ScanMesh() }
        var low=extent/4096, high=extent*1.01, best:ScanMesh?=nil
        for _ in 0..<19 {
            if Task.isCancelled { return best ?? ScanMesh() }
            let mid=(low+high)/2, m=cluster(source,cell:mid)
            if m.faces.count>goal { low=mid } else {
                high=mid
                if !m.faces.isEmpty && m.faces.count>(best?.faces.count ?? 0) { best=m }
            }
        }
        if let best=best { return best }
        let sorted=source.faces.sorted { l,r in
            let p=(source.vertices[l.a]+source.vertices[l.b]+source.vertices[l.c])/3
            let q=(source.vertices[r.a]+source.vertices[r.b]+source.vertices[r.c])/3
            if p.x != q.x { return p.x<q.x }; if p.y != q.y { return p.y<q.y }; return p.z<q.z
        }
        var result=source; result.faces=(0..<goal).map { sorted[$0*sorted.count/goal] }; return result.compact()
    }
    static func roundedForOBJ(_ mesh:ScanMesh) -> ScanMesh {
        var m=mesh
        m.vertices=mesh.vertices.map { p in SIMD3((p.x*10).rounded()/10,(p.y*10).rounded()/10,(p.z*10).rounded()/10) }
        var seen=Set<FaceKey>()
        m.faces=m.faces.filter { f in
            length2(cross(m.vertices[f.b]-m.vertices[f.a],m.vertices[f.c]-m.vertices[f.a]))>0 && seen.insert(FaceKey(f.a,f.b,f.c)).inserted
        }
        return m.compact()
    }
    static func className(_ n:UInt8) -> String {
        switch n { case 1:return "wall"; case 2:return "floor"; case 3:return "ceiling"; case 4:return "table"; case 5:return "seat"; case 6:return "window"; case 7:return "door"; default:return "unclassified" }
    }
    static func number(_ x:Float) -> String { String(format:"%.1f",locale:Locale(identifier:"en_US_POSIX"),Double(x == 0 ? 0 : x)) }
    static func dimensions(_ b:Bounds?) -> String { guard let s=b?.size else {return "0.0 x 0.0 x 0.0"}; return [s.x,s.y,s.z].map(number).joined(separator:" x ") }
    static func obj(_ m:ScanMesh, original:Bounds?) -> String {
        var counts=[UInt8:Int](); for f in m.faces { counts[f.classification,default:0]+=1 }
        let classes=counts.keys.sorted().map { "\(className($0))=\(counts[$0]!)" }.joined(separator:", ")
        var lines=["# LiDAR AI OBJ | units: mm | Y up | centered AABB", "# exported_bbox_xyz_mm: \(dimensions(m.bounds))", "# raw_scan_bbox_xyz_mm: \(dimensions(original))", "# vertices: \(m.vertices.count) | triangles: \(m.faces.count)", "# ARKit face classes: \(classes)", "# Approximate sensor geometry; not metrology; open surfaces possible."]
        lines += m.vertices.map { "v \(number($0.x)) \(number($0.y)) \(number($0.z))" }
        lines += m.faces.map { "f \($0.a+1) \($0.b+1) \($0.c+1)" }
        return lines.joined(separator:"\n")+"\n"
    }
    static func prompt(_ obj:String) -> String {
        "Вот 3D-скан объекта в Wavefront OBJ. Единицы: мм, Y вверх. Определи геометрию, оцени габариты, отверстия, плоскости и симметрию. Отметь шум, пропуски и неопределенность. Не выдумывай невидимые поверхности. Предложи исправленный OBJ или параметрический OpenSCAD-код с размерами и допущениями.\n\n"+obj
    }
}
