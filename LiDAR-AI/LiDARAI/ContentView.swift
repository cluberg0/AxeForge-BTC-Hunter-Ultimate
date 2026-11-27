import SwiftUI
import UIKit
import Combine
struct ContentView: View {
    @StateObject private var manager=ARMeshManager()
    @State private var mesh: ScanMesh?
    var body: some View {
        ZStack {
            ScannerView(manager:manager) { self.mesh=$0 }.opacity(mesh == nil ? 1 : 0).allowsHitTesting(mesh == nil)
            if let mesh=mesh { PreviewExportView(source:mesh) { self.mesh=nil }.background(Color(uiColor:.systemBackground)) }
        }.onReceive(NotificationCenter.default.publisher(for:UIApplication.didEnterBackgroundNotification)) { _ in manager.pause() }
    }
}
@main struct LiDARAIApp: App {
    var body: some Scene { WindowGroup { ContentView().preferredColorScheme(.dark) } }
}
