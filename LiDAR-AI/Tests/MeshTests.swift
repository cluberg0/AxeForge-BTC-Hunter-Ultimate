import Foundation
@main struct MeshTests {
    static func main() {
        var m=ScanMesh()
        let n=70
        for y in 0...n { for x in 0...n { m.vertices.append(SIMD3(Float(x)/100,Float(y)/100,0)); m.normals.append(SIMD3(0,0,1)) } }
        for y in 0..<n { for x in 0..<n {
            let a=y*(n+1)+x,b=a+1,c=a+n+1,d=c+1
            m.faces += [Triangle(a:a,b:b,c:c,classification:4),Triangle(a:b,b:d,c:c,classification:4)]
        } }
        let cropped=m.cropped(to:Bounds(min:SIMD3(0,0,-1),max:SIMD3(0.3,0.3,1)),omitRoom:false)
        precondition(cropped.faces.count>0 && cropped.faces.count<m.faces.count)
        precondition(cropped.vertices.allSatisfy{$0.x<=0.3 && $0.y<=0.3})
        let centered=m.centeredMM(); precondition(abs(centered.bounds!.size.x-700)<0.01)
        for target in [200,500,1200,2500] {
            let result=MeshProcessor.simplify(m,target:target)
            precondition(result.faces.count<=target && !result.faces.isEmpty)
            let mm=MeshProcessor.roundedForOBJ(result.centeredMM())
            let obj=MeshProcessor.obj(mm,original:centered.bounds)
            let lines=obj.split(separator:"\n")
            precondition(lines.filter{$0.hasPrefix("v ")}.count==mm.vertices.count)
            precondition(lines.filter{$0.hasPrefix("f ")}.count==mm.faces.count)
            for f in mm.faces { precondition(f.indices.allSatisfy{$0>=0 && $0<mm.vertices.count}); precondition(Set(f.indices).count==3) }
            precondition(obj.contains("table=")); precondition(obj.utf8.allSatisfy{$0<128})
            print("PASS target \(target): \(mm.faces.count) faces, \(mm.vertices.count) vertices, \(obj.utf8.count) bytes")
        }
        var room=m; room.faces=[Triangle(a:0,b:1,c:n+1,classification:2)]
        precondition(room.cropped(to:Bounds(min:SIMD3(-1,-1,-1),max:SIMD3(1,1,1)),omitRoom:true).faces.isEmpty)
        print("PASS bounds, crop, classification, OBJ indices, ASCII")
    }
}
