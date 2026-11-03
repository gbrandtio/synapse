import Cocoa
import FlutterMacOS

class MainFlutterWindow: NSWindow {
  override func awakeFromNib() {
    let flutterViewController = FlutterViewController()
    flutterViewController.backgroundColor = .white
    self.contentViewController = flutterViewController
    self.setContentSize(NSSize(width: 1180, height: 780))
    self.contentMinSize = NSSize(width: 860, height: 560)
    self.center()

    // A plain white window, whatever the system's light or dark setting is.
    self.appearance = NSAppearance(named: .aqua)
    self.backgroundColor = .white
    self.titlebarAppearsTransparent = true
    self.titleVisibility = .hidden

    RegisterGeneratedPlugins(registry: flutterViewController)

    super.awakeFromNib()
  }
}
